import argparse
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from src.reports import report_indicators, report_two_sources
from src.scheduler import Scheduler
from src.utils.config import settings
from src.utils.loguru_config import AppLogger

logger = AppLogger().get_logger()
REQUIRED_COLUMNS = {"order_id", "sku", "price", "qty", "status"}


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


def calc_revenue_by_sku(df):
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"В файле отсутствуют колонки: {missing}")

    revenue = {}
    for i, row in df.iterrows():
        if row["status"] == "cancelled":
            continue
        sku = row["sku"]
        amount = row["price"] * row["qty"]
        revenue[sku] = revenue.get(sku, 0) + amount
    return revenue


def process_data():
    start = time.time()
    try:
        logger.info("Старт process_data")
        df = load_orders(settings.orders_file)
        revenue = calc_revenue_by_sku(df)
        for sku, total in revenue.items():
            logger.info(f"{sku}: {total}")

        report_two_sources()
        report_indicators()

        elapsed = time.time() - start
        logger.info(f"process_data завершён за {elapsed:.2f} сек.")

        Path("reports/last_run.txt").write_text(
            datetime.now(UTC).isoformat(), encoding="utf-8"
        )
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
    parse_args()
    if settings.scheduler_interval > 0:
        Scheduler(process_data).start()
        threading.Event().wait()
    else:
        process_data()


if __name__ == "__main__":
    main()
