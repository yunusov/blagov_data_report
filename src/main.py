import argparse
from pathlib import Path
import time
import zipfile

import pandas as pd
import requests
from apscheduler.schedulers.background import BackgroundScheduler
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


class Scheduler:
    def start(self):
        logger.info("start")
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            process_data,
            "interval",
            seconds=settings.scheduler_interval,
        )
        scheduler.start()


def load_orders(path):
    try:
        logger.info(f"{path=}")
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


def report_two_sources():
    orders = pd.read_excel(settings.orders_file)
    registry = pd.read_excel(settings.orders_for_check)

    registry = registry.rename(columns={"Номер заказа": "order_id"})
    registry = registry.rename(columns={"Сумма заказа": "price"})
    registry = registry.rename(columns={"Кол-во": "qty"})

    Path("reports").mkdir(exist_ok=True)

    merged = pd.merge(
        orders,
        registry,
        on="order_id",
        how="outer",
        indicator=True,  # колонка _merge: both / left_only / right_only
        suffixes=("_orders", "_registry"),
    )
    counts = merged["_merge"].value_counts()

    result = {
        "совпало": int(counts.get("both", 0)),  # есть в обоих
        "только в выгрузке": int(counts.get("left_only", 0)),
        "только в реестре": int(counts.get("right_only", 0)),
    }

    diff_mask = (merged["_merge"] == "both") & (
        (merged["price_orders"] != merged["price_registry"])
        | (merged["qty_orders"] != merged["qty_registry"])
    )
    diffs = merged[diff_mask]
    # Заказы, которые есть только в реестре
    only_in_registry = merged[merged["_merge"] == "right_only"]

    # Заказы, которые есть только в выгрузке
    only_in_orders = merged[merged["_merge"] == "left_only"]

    with open("reports/reconciliation.txt", "w", encoding="utf-8") as f:
        f.write("=== СВЕРКА ДВУХ ИСТОЧНИКОВ ===\n")
        f.write(f"Всего заказов в выгрузке: {len(orders)}\n")
        f.write(f"Всего заказов в реестре:  {len(registry)}\n")
        f.write("\n\n")
        f.write(f"Совпало (есть в обоих):        {result['совпало']}\n")
        f.write(f"Только в выгрузке:             {result['только в выгрузке']}\n")
        f.writelines(f"  {order_id}\n" for order_id in only_in_orders["order_id"])
        f.write(f"Только в реестре:              {result['только в реестре']}\n")
        f.writelines(f"  {order_id}\n" for order_id in only_in_registry["order_id"])
        f.write(f"Расхождения по значениям:      {len(diffs)}\n")
        f.write("\n\n")
        f.write("=== РАСХОЖДЕНИЯ ПО ЗНАЧЕНИЯМ ===")
        f.writelines(
            f"\nЗаказ {row['order_id']}: \n"
            f"\tprice {row['price_orders']} vs {row['price_registry']}, "
            f"qty {row['qty_orders']} vs {row['qty_registry']}"
            for _, row in diffs.iterrows()
        )


def report_indicators():
    """Считает показатели по выгрузке: выручка по товару, доля возвратов, топ-5 по обороту."""
    df = pd.read_excel(settings.orders_file)

    # 1. Выручка по товару (SKU) — исключаем отменённые заказы
    active = df[df["status"] != "cancelled"].copy()
    active["revenue"] = active["price"] * active["qty"]
    revenue_by_sku = active.groupby("sku")["revenue"].sum().sort_values(ascending=False)

    # 2. Доля возвратов
    total_orders = len(df)
    returned = (df["status"] == "returned").sum()
    return_rate = returned / total_orders * 100 if total_orders else 0

    # 3. Топ-5 по обороту
    top5 = revenue_by_sku.head(5)

    # Вывод
    with open("reports/indicators.txt", "w", encoding="utf-8") as f:
        f.write("=== ПОКАЗАТЕЛИ ПО ВЫГРУЗКЕ ===\n")
        f.write(f"Всего заказов: {total_orders}\n")
        f.write(f"Доля возвратов: {return_rate:.1f}% ({returned} из {total_orders})\n")
        f.write("\n\n")
        f.write("=== ВЫРУЧКА ПО ТОВАРУ (SKU) ===\n")
        f.writelines(f"  {sku}: {rev:,.0f} ₽\n" for sku, rev in revenue_by_sku.items())
        f.write("\n\n")
        f.write("=== ТОП-5 ПО ОБОРОТУ ===\n")
        f.writelines(f"  {i}. {sku}: {rev:,.0f} ₽\n" for i, (sku, rev) in enumerate(top5.items(), 1))


def process_data():
    logger.info("process_data")
    try:
        # df = load_orders(settings.orders_file)
        # logger.info("load_orders")
        # revenue = calc_revenue_by_sku(df)
        # for sku, total in revenue.items():
        #     logger.info(sku, total)

        report_two_sources()
        report_indicators()
    except Exception as e:
        # logger.exception("")
        logger.error(e)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Генерация отчёта по заказам",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-f",
        "--orders-file",
        default=None,
        help="Путь к файлу с заказами (xlsx)",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Базовый URL API для проверки статусов",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Интервал срабатывания планировщика",
    )
    args = parser.parse_args()

    # Переопределяем настройки из CLI, если они переданы
    if args.orders_file:
        settings.orders_file = args.orders_file
    if args.api_url:
        settings.order_status_api_url = args.api_url
    if args.interval:
        settings.scheduler_interval = args.interval
    return args


def main():
    logger.info("Hello world!")
    parse_args()
    logger.info(f"{settings.scheduler_interval=}")
    if settings.scheduler_interval > 0:
        Scheduler().start()
        while True:
            time.sleep(1)
    else:
        process_data()


if __name__ == "__main__":
    main()
