import pandas as pd
import pytest

from src.main import calc_revenue_by_sku


def _make_df(data):
    return pd.DataFrame(data)


def test_calc_revenue_by_sku_simple(mock_order_status, file_xlsx):
    """Считает выручку price * qty для каждого SKU."""
    df = pd.read_excel(file_xlsx)
    revenue = calc_revenue_by_sku(df)
    assert revenue == {"A": 20, "B": 60}


def test_calc_revenue_by_sku_skips_cancelled(mock_order_status, file_xlsx):
    """Пропускает заказы со статусом cancelled."""
    df = pd.read_excel(file_xlsx)
    mock_order_status[1] = "cancelled"

    revenue = calc_revenue_by_sku(df)
    assert revenue == {"B": 60}


def test_calc_revenue_by_sku_missing_columns():
    """Отсутствие обязательных колонок -> ValueError."""
    df = _make_df({
        "order_id": [1],
        "sku": ["A"],
    })
    with pytest.raises(ValueError, match="отсутствуют колонки"):
        calc_revenue_by_sku(df)