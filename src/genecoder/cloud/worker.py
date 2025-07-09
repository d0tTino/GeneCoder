from __future__ import annotations

import argparse
import base64
import io
import os
import secrets
import tempfile
import uuid
import zipfile
from pathlib import Path

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from genecoder.cli import bundle as bundle_cli
from genecoder.plugin_manager import load_plugins

API_TOKEN: str | None = os.getenv("GENECODER_API_TOKEN")
security = HTTPBearer(auto_error=False)
app = FastAPI(title="GeneCoder Worker")


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None or credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


@app.on_event("startup")
def _startup() -> None:
    global API_TOKEN
    load_plugins()
    if API_TOKEN is None:
        API_TOKEN = secrets.token_urlsafe(16)
        print(f"Generated API token: {API_TOKEN}")


@app.post("/jobs")
def submit_job(payload: dict[str, Any], _token: None = Depends(verify_token)) -> dict[str, str]:
    if payload.get("type") != "bundle":
        raise HTTPException(status_code=400, detail="Unsupported job type")
    body = payload.get("payload")
    if not isinstance(body, dict) or "archive" not in body:
        raise HTTPException(status_code=400, detail="Missing archive")
    archive_b64 = body["archive"]
    if not isinstance(archive_b64, str):
        raise HTTPException(status_code=400, detail="Invalid archive")
    try:
        data = base64.b64decode(archive_b64)
    except Exception as exc:  # pragma: no cover - invalid base64
        raise HTTPException(status_code=400, detail="Invalid archive") from exc

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(tmpdir)
        tmp_path = Path(tmpdir)
        yaml_files = [p for p in tmp_path.iterdir() if p.suffix in {".yaml", ".yml"}]
        if not yaml_files:
            raise HTTPException(status_code=400, detail="Bundle file not found")
        args = argparse.Namespace(
            config=str(yaml_files[0]), cache_dir="bundle_runs", export_archive=None
        )
        bundle_cli._handle_run(args)

    return {"job_id": str(uuid.uuid4())}


def main() -> None:  # pragma: no cover - manual launch
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover - manual launch
    main()
