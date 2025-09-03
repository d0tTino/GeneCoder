"""Tests for the cloud worker running in offline mode."""

from __future__ import annotations

import base64
import tempfile
import zipfile
from pathlib import Path
import sys
import types
from typing import Any, Callable

import pytest


@pytest.fixture()
def worker_plugins(monkeypatch: pytest.MonkeyPatch) -> tuple[object, object]:
    """Return the worker and plugin manager with required modules stubbed."""

    # Minimal FastAPI stub so ``genecoder.cloud.worker`` can be imported
    fastapi_stub = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
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

    monkeypatch.setitem(sys.modules, "fastapi", fastapi_stub)

    from genecoder.cloud import worker
    from genecoder import plugin_manager as plugins

    yield worker, plugins


def _build_archive(bundle_path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        archive = Path(tmpdir) / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(bundle_path, arcname=bundle_path.name)
        return base64.b64encode(archive.read_bytes()).decode()


def test_worker_offline_blocks_network(
    worker_plugins: tuple[object, object],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    worker, plugins = worker_plugins
    worker.API_TOKEN = "tok"

    bundle_file = tmp_path / "b.yaml"
    bundle_file.write_text("encode:\n  input_files: []\n")
    archive_b64 = _build_archive(bundle_file)

    def fake_urlopen(*args: object, **kwargs: object) -> None:  # pragma: no cover
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
        with pytest.raises(RuntimeError):
            genecoder.install_registry_plugins("https://example.com/plugins.yaml")

    monkeypatch.setattr(worker.bundle_cli, "_handle_run", dummy)

    response = worker.create_job(
        {"type": "bundle", "payload": {"archive": archive_b64}},
        authorization="Bearer tok",
    )
    assert response["status"] == "ok"
    assert called["run"]

