from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import tempfile
import uuid
from pathlib import Path

from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from genecoder.cli import bundle as bundle_cli
from genecoder.plugin_manager import load_plugins
from genecoder.cloud.utils import extract_zip_safely

API_TOKEN: str | None = os.getenv("GENECODER_API_TOKEN")
security = HTTPBearer(auto_error=False)
app = FastAPI(title="GeneCoder Worker")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit for extracted files
JOB_DIR = Path(os.getenv("GENECODER_JOB_DIR", "worker_jobs"))


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None or credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


@app.on_event("startup")  # type: ignore[misc]
def _startup() -> None:
    global API_TOKEN
    load_plugins()
    if API_TOKEN is None:
        API_TOKEN = secrets.token_urlsafe(16)
        print(f"Generated API token: {API_TOKEN}")


def _write_status(job_path: Path, data: dict[str, Any]) -> None:
    (job_path / "status.json").write_text(json.dumps(data), encoding="utf-8")


def _process_job(job_id: str) -> None:
    job_path = JOB_DIR / job_id
    archive_path = job_path / "archive.zip"
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            extract_zip_safely(archive_path.read_bytes(), tmpdir, max_file_size=MAX_FILE_SIZE)
        except ValueError:
            _write_status(job_path, {"status": "failed", "progress": 100})
            return
        tmp_path = Path(tmpdir)
        yaml_files = [p for p in tmp_path.iterdir() if p.suffix in {".yaml", ".yml"}]
        if not yaml_files:
            _write_status(job_path, {"status": "failed", "progress": 100})
            return
        args = argparse.Namespace(
            config=str(yaml_files[0]), cache_dir="bundle_runs", export_archive=None
        )
        try:
            bundle_cli._handle_run(args)
            _write_status(job_path, {"status": "completed", "progress": 100})
        except Exception:
            _write_status(job_path, {"status": "failed", "progress": 100})


@app.post("/jobs")  # type: ignore[misc]
def submit_job(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
    _token: None = Depends(verify_token),
) -> dict[str, str]:
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
        try:
            extract_zip_safely(data, tmpdir, max_file_size=MAX_FILE_SIZE)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid archive path"
            ) from exc
        tmp_path = Path(tmpdir)
        yaml_files = [p for p in tmp_path.iterdir() if p.suffix in {".yaml", ".yml"}]
        if not yaml_files:
            raise HTTPException(status_code=400, detail="Bundle file not found")

    job_id = str(uuid.uuid4())
    job_path = JOB_DIR / job_id
    job_path.mkdir(parents=True, exist_ok=True)
    (job_path / "archive.zip").write_bytes(data)
    _write_status(job_path, {"status": "running", "progress": 0})
    background_tasks.add_task(_process_job, job_id)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")  # type: ignore[misc]
def job_status(job_id: str, _token: None = Depends(verify_token)) -> dict[str, Any]:
    path = JOB_DIR / job_id / "status.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - corrupt file
        raise HTTPException(status_code=500, detail="Corrupt status") from exc


def main() -> None:  # pragma: no cover - manual launch
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover - manual launch
    main()
