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
PLUGIN_RATINGS: Dict[str, List[int]] = {}


class PluginMetadata(BaseModel):
    name: str
    version: str
    checksum: str
    signature: Optional[str] = None


class ChallengeEntry(BaseModel):
    name: str
    points: int


class RatingRequest(BaseModel):
    name: str
    rating: int


def _load_catalog() -> None:
    global CATALOG, PLUGIN_RATINGS
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
                **({"stars": float(item.get("stars", 0))} if "stars" in item else {}),
            }
            for item in items
            if item.get("name")
        ]

    ratings = data.get("ratings", {})
    if isinstance(ratings, dict):
        PLUGIN_RATINGS = {
            str(k): [int(x) for x in v if isinstance(x, int)]
            for k, v in ratings.items()
            if isinstance(v, list)
        }
    for entry in CATALOG:
        r = PLUGIN_RATINGS.get(entry["name"])
        if r:
            entry["stars"] = sum(r) / len(r)


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
    data = json.dumps({"plugins": CATALOG, "ratings": PLUGIN_RATINGS})
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


@router.post("/plugins/rate")
def rate_plugin(
    req: RatingRequest,
    _: None = Depends(_verify_token),
) -> Dict[str, float]:
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=400, detail="rating must be 1-5")
    if not any(item["name"] == req.name for item in CATALOG):
        raise HTTPException(status_code=404, detail="Plugin not found")
    ratings = PLUGIN_RATINGS.setdefault(req.name, [])
    ratings.append(req.rating)
    avg = sum(ratings) / len(ratings)
    for item in CATALOG:
        if item["name"] == req.name:
            item["stars"] = avg
            break
    _save_catalog()
    return {"average": avg}


@router.get("/plugins/rate")
def get_plugin_rating(name: str) -> Dict[str, float]:
    ratings = PLUGIN_RATINGS.get(name)
    if not ratings:
        raise HTTPException(status_code=404, detail="No ratings found")
    avg = sum(ratings) / len(ratings)
    return {"average": avg}


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
