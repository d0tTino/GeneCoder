import os
import json
from pathlib import Path
from typing import Dict, List, Optional

import portalocker
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import web.main as main

router = APIRouter()
security = HTTPBearer(auto_error=False)

CATALOG_PATH = os.getenv("GENECODER_CATALOG_PATH")
CHALLENGE_PATH = os.getenv("GENECODER_CHALLENGE_PATH")
CATALOG: List[Dict[str, Optional[str]]] = []
CHALLENGE: Dict[str, int] = {}


class PluginMetadata(BaseModel):
    name: str
    version: str
    checksum: str
    signature: Optional[str] = None


class ChallengeEntry(BaseModel):
    name: str
    points: int


def _load_catalog() -> None:
    global CATALOG
    if not CATALOG_PATH:
        return
    path = Path(CATALOG_PATH)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    items = data.get("plugins", [])
    if isinstance(items, list):
        CATALOG = [
            {
                "name": str(item.get("name", "")),
                "version": str(item.get("version", "")),
                "checksum": str(item.get("checksum", "")),
                "signature": item.get("signature"),
            }
            for item in items
            if item.get("name")
        ]


def _load_challenge() -> None:
    """Load challenge entries from ``CHALLENGE_PATH`` if configured."""
    global CHALLENGE
    if not CHALLENGE_PATH:
        return
    path = Path(CHALLENGE_PATH)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(data, dict):
        CHALLENGE = {str(k): int(v) for k, v in data.items() if isinstance(v, int)}


def _save_catalog() -> None:
    if not CATALOG_PATH:
        return
    path = Path(CATALOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"plugins": CATALOG})
    with portalocker.Lock(path, "a+", timeout=10, encoding="utf-8") as fh:
        fh.seek(0)
        fh.truncate(0)
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _save_challenge() -> None:
    if not CHALLENGE_PATH:
        return
    path = Path(CHALLENGE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(CHALLENGE)
    with portalocker.Lock(path, "a+", timeout=10, encoding="utf-8") as fh:
        fh.seek(0)
        fh.truncate(0)
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


@router.on_event("startup")
def _startup() -> None:
    _load_catalog()
    _load_challenge()


@router.on_event("shutdown")
def _shutdown() -> None:
    _save_catalog()
    _save_challenge()


def _verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None or credentials.credentials != main.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


@router.get("/plugins")
def list_plugins() -> Dict[str, List[Dict[str, Optional[str]]]]:
    return {"plugins": CATALOG}


@router.post("/plugins")
def add_plugin(
    meta: PluginMetadata,
    _: None = Depends(_verify_token),
) -> Dict[str, str]:
    for item in CATALOG:
        if item["name"] == meta.name and item["version"] == meta.version:
            raise HTTPException(status_code=409, detail="Plugin already exists")
    CATALOG.append(meta.dict())
    _save_catalog()
    return {"status": "ok"}


@router.get("/challenge")
def list_challenge() -> Dict[str, Dict[str, int]]:
    """Return current challenge rankings."""
    return {"entries": CHALLENGE}


@router.post("/challenge")
def add_challenge(
    entry: ChallengeEntry,
    _: None = Depends(_verify_token),
) -> Dict[str, str]:
    """Submit challenge points for a participant."""
    CHALLENGE[entry.name] = CHALLENGE.get(entry.name, 0) + entry.points
    _save_challenge()
    return {"status": "ok"}
