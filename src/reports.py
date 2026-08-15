from pathlib import Path

import pandas as pd

from src.utils.config import settings


def report_two_sources():
    orders = pd.read_excel(settings.orders_file)
    registry = pd.read_excel(settings.orders_for_check)

    registry = registry.rename(
        columns={
            "Номер заказа": "order_id",
            "Сумма заказа": "price",
            "Кол-во": "qty",
        }
    )

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
        (merged["price_orders"].round(2) != merged["price_registry"].round(2))
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

    Path("reports").mkdir(exist_ok=True)

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
        f.writelines(
            f"  {i}. {sku}: {rev:,.0f} ₽\n"
            for i, (sku, rev) in enumerate(top5.items(), 1)
        )
