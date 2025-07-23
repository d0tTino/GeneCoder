from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

router = APIRouter()
security = HTTPBearer(auto_error=False)

API_TOKEN = os.getenv("GENECODER_API_TOKEN")

CATALOG_PATH = Path(__file__).with_name("catalog_data.json")
CHALLENGE_PATH = Path(__file__).with_name("challenge_data.json")


class PluginEntry(BaseModel):
    name: str
    version: str | None = None
    checksum: str | None = None
    signature: str | None = None


class ChallengeEntry(BaseModel):
    name: str
    points: int


_plugins: List[dict[str, object]] | None = None
_challenge: Dict[str, int] | None = None


def _load_plugins() -> List[dict[str, object]]:
    global _plugins
    if _plugins is None:
        if CATALOG_PATH.is_file():
            try:
                _plugins = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
            except Exception:
                _plugins = []
        else:
            _plugins = []
    return _plugins


def _save_plugins() -> None:
    if _plugins is not None:
        CATALOG_PATH.write_text(json.dumps(_plugins), encoding="utf-8")


def _load_challenge() -> Dict[str, int]:
    global _challenge
    if _challenge is None:
        if CHALLENGE_PATH.is_file():
            try:
                _challenge = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))
            except Exception:
                _challenge = {}
        else:
            _challenge = {}
    return _challenge


def _save_challenge() -> None:
    if _challenge is not None:
        CHALLENGE_PATH.write_text(json.dumps(_challenge), encoding="utf-8")


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if API_TOKEN and (credentials is None or credentials.credentials != API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing token")


@router.get("/plugins")
async def get_plugins() -> dict[str, object]:
    return {"plugins": _load_plugins()}


@router.post("/plugins")
async def add_plugin(
    entry: PluginEntry, _auth: None = Depends(verify_token)
) -> dict[str, str]:
    plugins = _load_plugins()
    plugins.append(entry.model_dump())
    _save_plugins()
    return {"status": "ok"}


@router.get("/challenge")
async def get_challenge() -> dict[str, object]:
    return {"entries": _load_challenge()}


@router.post("/challenge")
async def add_challenge_entry(
    entry: ChallengeEntry, _auth: None = Depends(verify_token)
) -> dict[str, str]:
    challenge = _load_challenge()
    challenge[entry.name] = entry.points
    _save_challenge()
    return {"status": "ok"}
