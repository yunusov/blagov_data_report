import pandas as pd
import pytest

from src.main import load_orders


def test_load_orders_success(columns_xlsx, file_xlsx):
    """Читает валидный xlsx и возвращает DataFrame."""
    df = load_orders(file_xlsx)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == columns_xlsx
    assert len(df) == 2


def test_load_orders_permission_error(file_xlsx, monkeypatch):
    """Файл заблокирован -> PermissionError."""

    def fake_read_excel(*args, **kwargs):
        raise PermissionError("file is locked")

    monkeypatch.setattr("src.main.pd.read_excel", fake_read_excel)
    with pytest.raises(PermissionError):
        load_orders(file_xlsx)
