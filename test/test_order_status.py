import json

import pytest
import requests
from tenacity import wait_none

from src import api, main
from src.api import get_order_status


@pytest.fixture(autouse=True)
def disable_retry_delay():
    """Отключает задержки между ретраями tenacity для скорости тестов."""
    get_order_status.retry.wait = wait_none()
    yield


@pytest.fixture
def api_url(monkeypatch):
    """Подменяет URL API на тестовый."""
    monkeypatch.setattr(
        main.settings,
        "order_status_api_url",
        "https://api.test/orders/{order_id}/status",
    )


def _mock_response(status_code=200, json_data=None, raise_for_status=None):
    """Создаёт мок-ответ requests.Response."""
    resp = requests.Response()
    resp.status_code = status_code
    if json_data is not None:
        resp._content = json.dumps(json_data).encode("utf-8")
    if raise_for_status:
        resp.raise_for_status = raise_for_status
    return resp


def test_get_order_status_success(monkeypatch, api_url):
    """Успешный ответ API возвращает статус."""
    resp = _mock_response(json_data={"status": "shipped"})
    monkeypatch.setattr(api.requests, "get", lambda *a, **kw: resp)

    assert get_order_status("ORD-1") == "shipped"


def test_get_order_status_connection_error(monkeypatch, api_url):
    """Ошибка соединения пробрасывается после всех ретраев."""

    def raise_conn_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(api.requests, "get", raise_conn_error)

    with pytest.raises(requests.exceptions.ConnectionError):
        get_order_status("ORD-1")
