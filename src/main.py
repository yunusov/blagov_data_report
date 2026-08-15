import zipfile

import pandas as pd
import requests
from pandas.errors import EmptyDataError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from urllib3.exceptions import NameResolutionError

from src.utils.config import settings
from src.utils.loguru_config import AppLogger

logger = AppLogger().get_logger()
REQUIRED_COLUMNS = {"order_id", "sku", "price", "qty"}


def load_orders(path):
    try:
        df = pd.read_excel(path)
    except EmptyDataError:
        logger.error(f"Файл пустой: {path}")
        raise
    except FileNotFoundError:
        logger.error(f"Файл не найден: {path}")
        raise
    except PermissionError:
        logger.error(f"Файл заблокирован другим процессом: {path}")
        raise
    except (ValueError, zipfile.BadZipFile) as exc:
        logger.error(f"Некорректный Excel-файл {path}: {exc}")
        raise
    except ImportError as exc:
        logger.error(f"Не установлен движок для чтения Excel: {exc}")
        raise
    return df


def r_sleep_logger(retry_state):
    """Логирует информацию о повторе."""
    attempt = retry_state.attempt_number
    exception = retry_state.outcome.exception()
    logger.warning(
        f"Попытка {attempt} не удалась: {exception}. "
        f"Следующая попытка через {retry_state.next_action.sleep} сек."
    )


@retry(
    reraise=True,  # пробрасывать исходное исключение после всех попыток
    stop=stop_after_attempt(3),  # максимум 3 попытки
    wait=wait_exponential(
        multiplier=1, min=1, max=10
    ),  # пауза: 1, 2, 4 сек (экспоненциальная)
    retry=retry_if_exception_type(
        (
            requests.exceptions.ConnectionError,  # включает NameResolutionError
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,  # 5xx и 4xx после raise_for_status()
        )
    ),
    before_sleep=r_sleep_logger,  # логгировать попытку
)
def get_order_status(order_id):
    url = settings.order_status_api_url
    try:
        resp = requests.get(url.replace("{order_id}", order_id))
        resp.raise_for_status()
    except requests.exceptions.Timeout as exc:
        logger.error(f"Таймаут запроса для заказа {order_id}: {exc}")
        raise
    except requests.exceptions.ConnectionError as exc:
        logger.error(f"Ошибка соединения для заказа {order_id}: {exc}")
        raise
    except requests.exceptions.HTTPError as exc:
        logger.error(f"HTTP-ошибка для заказа {order_id}: {exc}")
        raise
    except NameResolutionError as exc:
        logger.error(f"Не удалось разрешить имя хоста: {exc}")
        raise
    try:
        return resp.json["status"]
    except (requests.exceptions.JSONDecodeError, KeyError) as exc:
        logger.error(f"Некорректный ответ API для заказа {order_id}: {exc}")
        raise


def calc_revenue_by_sku(df):
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"В файле отсутствуют колонки: {missing}")

    revenue = {}
    for i, row in df.iterrows():
        if get_order_status(row["order_id"]) == "cancelled":
            continue
        sku = row["sku"]
        amount = row["price"] * row["qty"]
        revenue[sku] = amount
    return revenue


def main():
    logger.info("Hello world!")
    try:
        df = load_orders(settings.orders_file)
        revenue = calc_revenue_by_sku(df)
        for sku, total in revenue.items():
            logger.info(sku, total)
    except Exception as e:
        # logger.exception("")
        logger.error(e)


if __name__ == "__main__":
    main()
