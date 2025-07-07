import argparse
import base64
import sys
from pathlib import Path
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


def test_install_signature_failure() -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()
    plugins.PLUGIN_CATALOG["signed"] = {"checksum": checksum, "signature": sig_b64}

    def fake_check_call(cmd):
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "pkg.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            raise AssertionError("install should not run")
        else:
            raise AssertionError(cmd)

    orig_compute = plugins.compute_checksum

    def fake_compute(
        data: bytes, *, signature: bytes | None = None, public_key: bytes | None = None
    ) -> str:
        if signature is not None:
            raise ValueError("bad sig")
        return orig_compute(data)

    with pytest.MonkeyPatch().context() as m:
        m.setattr(plugin_cli.subprocess, "check_call", fake_check_call)
        m.setattr(plugin_cli.plugins, "compute_checksum", fake_compute)
        key = Path("/tmp/pub.pem")
        key.write_text("PUB")
        m.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key))
        r = client.post("/plugins/install", headers=AUTH_HEADERS, json={"name": "signed"})
    assert r.status_code == 400


def test_install_signature_success(tmp_path) -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)
    sig = base64.b64encode(b"valid").decode()
    plugins.PLUGIN_CATALOG["signed"] = {"checksum": checksum, "signature": sig}

    pubkey_path = tmp_path / "pub.pem"
    pubkey_path.write_text("PUB")

    installs = []

    def fake_check_call(cmd):
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "pkg.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            installs.append(cmd)
        else:
            raise AssertionError(cmd)

    orig_compute = plugins.compute_checksum

    def fake_compute(
        data: bytes, *, signature: bytes | None = None, public_key: bytes | None = None
    ) -> str:
        if signature is not None:
            assert signature == b"valid"
            assert public_key == b"PUB"
        return orig_compute(data)

    with pytest.MonkeyPatch().context() as m:
        m.setattr(plugin_cli.subprocess, "check_call", fake_check_call)
        m.setattr(plugin_cli.plugins, "compute_checksum", fake_compute)
        m.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(pubkey_path))
        r = client.post("/plugins/install", headers=AUTH_HEADERS, json={"name": "signed"})
    assert r.status_code == 200
    assert installs


def test_rate_plugin() -> None:
    main.PLUGIN_RATINGS.clear()
    r = client.post('/plugins/rate', json={'name': 'demo', 'rating': 4})
    assert r.status_code == 200
    assert r.json()['average'] == 4
    r = client.post('/plugins/rate', json={'name': 'demo', 'rating': 2})
    assert r.status_code == 200
    assert r.json()['average'] == 3
