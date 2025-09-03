from pathlib import Path
import urllib.error
import urllib.request

import pytest

from genecoder.data_service import fetch_profile


def test_fetch_profile_offline_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fetching profiles offline raises a helpful error."""

    def fake_urlopen(url: str, *, timeout: int | None = None):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("GENECODER_OFFLINE", "1")
    monkeypatch.delenv("GENECODER_PROFILE_DIR", raising=False)

    with pytest.raises(RuntimeError, match="GENECODER_PROFILE_DIR"):
        fetch_profile("illumina_profile.json", cache_dir=tmp_path)
