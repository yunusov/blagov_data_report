import pandas as pd
import pytest


@pytest.fixture
def file_xlsx(tmp_path):
    """Создаёт временный xlsx-файл с данными."""
    path = tmp_path / "orders.xlsx"
    data = {
        "order_id": [1, 2],
        "sku": ["A", "B"],
        "price": [10, 20],
        "qty": [2, 3],
        "status": ["delivered", "delivered"],
    }
    df = pd.DataFrame(data)
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def columns_xlsx():
    return ["order_id", "sku", "price", "qty", "status"]
