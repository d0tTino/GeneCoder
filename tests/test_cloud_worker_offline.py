import base64
import tempfile
import zipfile
from pathlib import Path
import sys
import types
from typing import Any, Callable

import pytest

# Provide a minimal FastAPI stub so the worker module can be imported without the
# external dependency.
try:  # pragma: no cover - real FastAPI is optional for tests
    import fastapi  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - executed when fastapi missing
    fastapi_stub = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
        def __init__(self) -> None:
            pass

        def post(
            self, *_args: object, **_kwargs: object
        ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator

    def Header(default: str | None = None) -> str | None:  # noqa: D401
        return default

    setattr(fastapi_stub, "FastAPI", FastAPI)
    setattr(fastapi_stub, "HTTPException", HTTPException)
    setattr(fastapi_stub, "Header", Header)
    sys.modules["fastapi"] = fastapi_stub

# Stub out the ``cryptography`` package used by plugin_security so the tests do
# not require the external dependency.
crypto_mod = types.ModuleType("cryptography")
crypto_exc = types.ModuleType("cryptography.exceptions")

class InvalidSignature(Exception):
    pass

setattr(crypto_exc, "InvalidSignature", InvalidSignature)
setattr(crypto_mod, "exceptions", crypto_exc)
sys.modules["cryptography"] = crypto_mod
sys.modules["cryptography.exceptions"] = crypto_exc

from genecoder.cloud import worker
from genecoder import plugin_manager as plugins


def _build_archive(bundle_path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        archive = Path(tmpdir) / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(bundle_path, arcname=bundle_path.name)
        return base64.b64encode(archive.read_bytes()).decode()


def test_worker_offline_blocks_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    worker.API_TOKEN = "tok"

    bundle_file = tmp_path / "b.yaml"
    bundle_file.write_text("encode:\n  input_files: []\n")
    archive_b64 = _build_archive(bundle_file)

    def fake_urlopen(*args: object, **kwargs: object) -> None:  # pragma: no cover - should not run
        raise AssertionError("network access attempted")

    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        plugins.subprocess,
        "check_call",
        lambda *args: (_ for _ in ()).throw(AssertionError("pip install attempted")),
    )
    monkeypatch.setenv("GENECODER_OFFLINE", "1")

    import genecoder

    called = {"run": False}

    def dummy(args: object) -> None:
        called["run"] = True
        genecoder.install_registry_plugins("https://example.com/plugins.yaml")

    monkeypatch.setattr(worker.bundle_cli, "_handle_run", dummy)

    response = worker.create_job(
        {"type": "bundle", "payload": {"archive": archive_b64}},
        authorization="Bearer tok",
    )
    assert response["status"] == "ok"
    assert called["run"]
