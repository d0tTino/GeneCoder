"""Minimal FastAPI worker used for unit tests."""

from __future__ import annotations

import argparse
import base64
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from genecoder._deprecation import warn_with_telemetry

from fastapi import FastAPI, HTTPException, Header

from genecoder.cli import bundle as bundle_cli
from genecoder.options import OFFLINE

app = FastAPI()

API_TOKEN: str | None = None


@app.post("/jobs")  # type: ignore[misc]
def create_job(job: dict[str, Any], authorization: str | None = Header(None)) -> dict[str, str]:
    """Handle bundle job uploads from tests."""
    if OFFLINE:
        raise HTTPException(status_code=503, detail="Offline mode")
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid token")

    if job.get("type") != "bundle":
        raise HTTPException(status_code=400, detail="Unsupported job type")
    archive_b64 = job.get("payload", {}).get("archive")
    if not archive_b64:
        raise HTTPException(status_code=400, detail="Missing archive")

    try:
        data = base64.b64decode(archive_b64)
    except Exception as exc:  # pragma: no cover - invalid base64
        raise HTTPException(status_code=400, detail="Invalid archive") from exc

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "bundle.zip"
        archive_path.write_bytes(data)
        with zipfile.ZipFile(archive_path) as zf:
            yaml_files: list[str] = []
            for info in zf.infolist():
                parts = Path(info.filename).parts
                if info.filename.startswith("/") or ".." in parts:
                    raise HTTPException(status_code=400, detail="Invalid path")
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise HTTPException(status_code=400, detail="Invalid path")
                if info.filename.endswith( (".yaml", ".yml") ):
                    yaml_files.append(info.filename)
            if len(yaml_files) != 1:
                raise HTTPException(status_code=400, detail="Bundle file not found")
            config_name = yaml_files[0]
            zf.extract(config_name, tmpdir)

        args = argparse.Namespace(
            config=str(Path(tmpdir) / config_name),
            cache_dir=str(Path(tmpdir) / "run"),
            export_archive=None,
            author=None,
            description=None,
        )
        bundle_cli._handle_run(args)
    return {"status": "ok"}

# Expose bundle_cli for monkeypatching in tests
__all__ = ["app", "API_TOKEN", "bundle_cli", "create_job"]

warn_with_telemetry(
    module_name="genecoder.compat.legacy.cloud.worker",
    message="genecoder.compat.legacy.cloud.worker is deprecated and retained only for compatibility tests.",
    stacklevel=2,
)
