from __future__ import annotations

import os
import urllib.request
from pathlib import Path

__all__ = ["get_cache_dir", "fetch_profile", "is_cached"]

DEFAULT_BASE_URL = "https://example.com/profiles"


def get_cache_dir() -> Path:
    env = os.getenv("GENECODER_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".genecoder" / "data"


def is_cached(profile: str, cache_dir: Path | None = None) -> bool:
    path = (cache_dir or get_cache_dir()) / profile
    return path.is_file()


def fetch_profile(
    profile: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    cache_dir: Path | None = None,
    refresh: bool = False,
) -> Path:
    """Download ``profile`` to ``cache_dir`` if needed and return its path."""
    cache_dir = cache_dir or get_cache_dir()
    dest = cache_dir / profile
    if dest.is_file() and not refresh:
        return dest
    cache_dir.mkdir(parents=True, exist_ok=True)
    url = f"{base_url.rstrip('/')}/{profile}"
    with urllib.request.urlopen(url) as resp:
        dest.write_bytes(resp.read())
    return dest
