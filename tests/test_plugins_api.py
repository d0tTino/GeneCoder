import argparse
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import web.main as main
import genecoder.plugins as plugins
from genecoder.cli import plugin as plugin_cli

main.API_TOKEN = "test-token"
client = TestClient(main.app)
AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


def test_list_plugins(monkeypatch):
    plugins.PLUGIN_CATALOG.clear()
    plugins.PLUGIN_CATALOG["demo"] = {"description": "Demo"}
    r = client.get("/plugins")
    assert r.status_code == 200
    assert "demo" in r.json().get("plugins", {})


def test_install_plugin(monkeypatch):
    called = []

    def fake_install(args: argparse.Namespace) -> None:
        called.append(args.name)

    monkeypatch.setattr(plugin_cli, "_handle_install", fake_install)
    plugins.PLUGIN_CATALOG["demo"] = {}
    r = client.post("/plugins/install", headers=AUTH_HEADERS, json={"name": "demo"})
    assert r.status_code == 200
    assert called == ["demo"]


def test_install_requires_token():
    r = client.post("/plugins/install", json={"name": "demo"})
    assert r.status_code == 401
