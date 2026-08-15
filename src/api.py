import requests
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
        resp = requests.get(url.replace("{order_id}", order_id), timeout=10)
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
        return resp.json()["status"]
    except (requests.exceptions.JSONDecodeError, KeyError) as exc:
        logger.error(f"Некорректный ответ API для заказа {order_id}: {exc}")
        raise
