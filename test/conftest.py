import pandas as pd
import pytest


@pytest.fixture
def file_xlsx(tmp_path):
    """Создаёт временный xlsx-файл с данными."""
    path = tmp_path / "orders.xlsx"
    data = {"order_id": [1, 2], "sku": ["A", "B"], "price": [10, 20], "qty": [2, 3]}
    df = pd.DataFrame(data)
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def columns_xlsx():
    return ["order_id", "sku", "price", "qty"]


@pytest.fixture
def mock_order_status(monkeypatch):
    """Мокает get_order_status, чтобы не ходить в сеть."""
    statuses = {}

    def fake_get_status(order_id):
        return statuses.get(order_id, "shipped")

    monkeypatch.setattr("src.main.get_order_status", fake_get_status)
    return statuses