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


def test_plugin_catalog_page() -> None:
    r = client.get("/plugin-catalog")
    assert r.status_code == 200
    assert "<!DOCTYPE html>" in r.text


def test_list_plugins() -> None:
    plugins.PLUGIN_CATALOG.clear()
    plugins.PLUGIN_CATALOG["demo"] = {"description": "Demo"}
    r = client.get("/plugins")
    assert r.status_code == 200
    assert "demo" in r.json().get("plugins", {})


def test_install_plugin() -> None:
    called = []

    def fake_install(args: argparse.Namespace) -> None:
        called.append(args.name)

    plugins.PLUGIN_CATALOG["demo"] = {}
    with pytest.MonkeyPatch().context() as m:
        m.setattr(plugin_cli, "_handle_install", fake_install)
        r = client.post("/plugins/install", headers=AUTH_HEADERS, json={"name": "demo"})
    assert r.status_code == 200
    assert called == ["demo"]


def test_install_requires_token() -> None:
    r = client.post("/plugins/install", json={"name": "demo"})
    assert r.status_code == 401
