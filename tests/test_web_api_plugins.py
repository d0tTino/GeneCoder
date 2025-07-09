import argparse
import base64
import json
import sys
import concurrent.futures
from pathlib import Path
from typing import Callable, Literal
import pytest
httpx = pytest.importorskip("httpx")
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import Request, Response
pytest.importorskip("fastapi_limiter")

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import web.main as main
from web import plugin_catalog
import genecoder.plugin_manager as plugins
from genecoder.cli import plugin as plugin_cli

main.API_TOKEN = "test-token"
client = TestClient(main.app)
AUTH_HEADERS = {"Authorization": f"Bearer {main.API_TOKEN}"}


class DummyResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, *exc: object) -> Literal[False]:
        return False

    def read(self) -> bytes:
        return self._data


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


def test_install_signature_missing_key() -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()
    plugins.PLUGIN_CATALOG["signed"] = {"checksum": checksum, "signature": sig_b64}

    def fake_check_call(cmd: list[str]) -> None:
        raise AssertionError("pip should not run")

    def fake_compute(*args: object, **kwargs: object) -> str:  # pragma: no cover - should not be called
        raise AssertionError("compute_checksum should not run")

    with pytest.MonkeyPatch().context() as m:
        m.setattr(plugin_cli.subprocess, "check_call", fake_check_call)
        m.setattr(plugin_cli.plugins, "compute_checksum", fake_compute)
        r = client.post("/plugins/install", headers=AUTH_HEADERS, json={"name": "signed"})
    assert r.status_code == 400


def test_install_signature_failure() -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()
    plugins.PLUGIN_CATALOG["signed"] = {"checksum": checksum, "signature": sig_b64}

    def fake_check_call(cmd: list[str]) -> None:
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "pkg.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            raise AssertionError("install should not run")
        else:
            raise AssertionError(cmd)

    orig_compute: Callable[[bytes], str] = plugins.compute_checksum

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


def test_install_signature_success(tmp_path: Path) -> None:
    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)
    sig = base64.b64encode(b"valid").decode()
    plugins.PLUGIN_CATALOG["signed"] = {"checksum": checksum, "signature": sig}

    pubkey_path = tmp_path / "pub.pem"
    pubkey_path.write_text("PUB")

    installs = []

    def fake_check_call(cmd: list[str]) -> None:
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "pkg.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            installs.append(cmd)
        else:
            raise AssertionError(cmd)

    orig_compute: Callable[[bytes], str] = plugins.compute_checksum

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
    r = client.post('/plugins/rate', headers=AUTH_HEADERS, json={'name': 'demo', 'rating': 4})
    assert r.status_code == 200
    assert r.json()['average'] == 4
    r = client.post('/plugins/rate', headers=AUTH_HEADERS, json={'name': 'demo', 'rating': 2})
    assert r.status_code == 200
    assert r.json()['average'] == 3


def test_get_plugin_rating() -> None:
    main.PLUGIN_RATINGS.clear()
    main.PLUGIN_RATINGS['demo'] = [3, 5]
    r = client.get('/plugins/rate', headers=AUTH_HEADERS, params={'name': 'demo'})
    assert r.status_code == 200
    assert r.json()['average'] == 4
    r = client.get('/plugins/rate', headers=AUTH_HEADERS, params={'name': 'missing'})
    assert r.status_code == 404


def test_catalog_fetch_error(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Failed catalog downloads return an empty list."""

    def handler(request: Request) -> Response:
        raise httpx.ConnectError("offline", request=request)

    transport = httpx.MockTransport(handler)

    def fake_urlopen(url: str) -> DummyResponse:
        request = Request("GET", url)
        transport.handle_request(request)
        raise AssertionError("unreachable")

    monkeypatch.setenv("GENECODER_PLUGIN_CATALOG_URL", "https://ex.com/catalog.yaml")
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    plugins.PLUGIN_CATALOG.clear()
    with caplog.at_level("WARNING"):
        plugins.fetch_plugin_catalog()
    assert "Failed to fetch plugin catalog" in caplog.text
    r = client.get("/plugins")
    assert r.status_code == 200
    assert r.json()["plugins"] == {}


def test_install_missing_public_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installing a signed plugin without a public key fails."""

    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()
    plugins.PLUGIN_CATALOG["signed"] = {"checksum": checksum, "signature": sig_b64}

    def fake_check_call(_cmd: list[str]) -> None:
        raise AssertionError("pip should not run")

    def fake_compute(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("compute_checksum should not run")

    with pytest.MonkeyPatch().context() as m:
        m.setattr(plugin_cli.subprocess, "check_call", fake_check_call)
        m.setattr(plugin_cli.plugins, "compute_checksum", fake_compute)
        r = client.post("/plugins/install", headers=AUTH_HEADERS, json={"name": "signed"})
    assert r.status_code == 400


def test_install_invalid_signature(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Invalid plugin signatures abort the installation."""

    pkg = b"PKG"
    checksum = plugins.compute_checksum(pkg)
    sig_b64 = base64.b64encode(b"sig").decode()
    plugins.PLUGIN_CATALOG["signed"] = {"checksum": checksum, "signature": sig_b64}

    key_path = tmp_path / "pub.pem"
    key_path.write_text("PUB")

    def fake_check_call(cmd: list[str]) -> None:
        if cmd[:4] == [sys.executable, "-m", "pip", "download"]:
            dest = cmd[cmd.index("-d") + 1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest) / "pkg.whl").write_bytes(pkg)
        elif cmd[:4] == [sys.executable, "-m", "pip", "install"]:
            raise AssertionError("install should not run")
        else:
            raise AssertionError(cmd)

    orig_compute: Callable[[bytes], str] = plugins.compute_checksum

    def fake_compute(
        data: bytes,
        *,
        signature: bytes | None = None,
        public_key: bytes | None = None,
    ) -> str:
        if signature is not None:
            raise ValueError("bad sig")
        return orig_compute(data)

    with pytest.MonkeyPatch().context() as m:
        m.setattr(plugin_cli.subprocess, "check_call", fake_check_call)
        m.setattr(plugin_cli.plugins, "compute_checksum", fake_compute)
        m.setenv("GENECODER_PLUGIN_PUBLIC_KEY", str(key_path))
        r = client.post("/plugins/install", headers=AUTH_HEADERS, json={"name": "signed"})
    assert r.status_code == 400


def test_rate_plugin_invalid() -> None:
    """Ratings outside 1-5 are rejected."""

    r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 0})
    assert r.status_code == 400
    r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 6})
    assert r.status_code == 400


def test_rate_plugin_persistence(tmp_path: Path) -> None:
    """Ratings are persisted and update the catalog."""

    main.PLUGIN_RATINGS.clear()
    path = tmp_path / "ratings.json"
    main.RATINGS_PATH = str(path)
    plugins.PLUGIN_CATALOG["demo"] = {}
    r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 5})
    assert r.status_code == 200
    assert r.json()["average"] == 5
    data = json.loads(path.read_text())
    assert data == {"demo": [5]}
    assert plugins.PLUGIN_CATALOG["demo"]["stars"] == 5
    r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 3})
    assert r.status_code == 200
    assert r.json()["average"] == 4
    data = json.loads(path.read_text())
    assert data == {"demo": [5, 3]}
    assert plugins.PLUGIN_CATALOG["demo"]["stars"] == 4


def test_concurrent_plugin_ratings(tmp_path: Path) -> None:
    """Concurrent rating requests produce a valid JSON file."""

    main.PLUGIN_RATINGS.clear()
    path = tmp_path / "ratings.json"
    main.RATINGS_PATH = str(path)
    plugins.PLUGIN_CATALOG["demo"] = {}

    def post_rating() -> None:
        r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 5})
        assert r.status_code == 200

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(post_rating) for _ in range(20)]
        for f in futures:
            f.result()

    data = json.loads(path.read_text())
    assert isinstance(data, dict)
    assert "demo" in data


def test_concurrent_ratings_file_valid(tmp_path: Path) -> None:
    """Ratings file stays valid with many concurrent updates."""

    main.PLUGIN_RATINGS.clear()
    path = tmp_path / "ratings.json"
    main.RATINGS_PATH = str(path)
    plugins.PLUGIN_CATALOG["demo"] = {}

    def post_rating() -> None:
        r = client.post("/plugins/rate", headers=AUTH_HEADERS, json={"name": "demo", "rating": 4})
        assert r.status_code == 200

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(post_rating) for _ in range(50)]
        for f in futures:
            f.result()

    # the resulting file should contain valid JSON with all ratings
    data = json.loads(path.read_text())
    assert isinstance(data, dict)
    assert "demo" in data


def test_plugin_catalog_crud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploading and listing catalog entries works and requires a token."""

    monkeypatch.setattr(plugin_catalog, "CATALOG_PATH", str(tmp_path / "cat.json"), raising=False)
    plugin_catalog.CATALOG.clear()

    r = client.get("/catalog/plugins")
    assert r.status_code == 200
    assert r.json() == {"plugins": []}

    payload = {"name": "demo", "version": "1.0", "checksum": "abc", "signature": "sig"}
    r = client.post("/catalog/plugins", json=payload)
    assert r.status_code == 401

    r = client.post("/catalog/plugins", headers=AUTH_HEADERS, json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r2 = client.get("/catalog/plugins")
    assert r2.status_code == 200
    assert r2.json()["plugins"] == [payload]
