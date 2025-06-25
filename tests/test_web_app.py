import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from web.main import app, index_path, helix_index_path

client = TestClient(app)


def test_root_route_serves_index_html() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "GeneCoder Web" in response.text


def test_static_index_served() -> None:
    response = client.get("/static/index.html")
    assert response.status_code == 200
    assert response.text == index_path.read_text(encoding="utf-8")


def test_helix_route_serves_ui() -> None:
    response = client.get("/helix")
    assert response.status_code == 200
    assert response.text == helix_index_path.read_text(encoding="utf-8")


def test_helix_ui_static() -> None:
    response = client.get("/helix-ui/index.html")
    assert response.status_code == 200
    assert response.text == helix_index_path.read_text(encoding="utf-8")
