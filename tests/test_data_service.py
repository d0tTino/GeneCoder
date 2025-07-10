import os
from pathlib import Path
import urllib.request

import pytest

from genecoder.data_service import fetch_profile
from tests.test_cli import run_cli_command


def test_fetch_profile_download_and_cache(tmp_path: Path) -> None:
    base = Path(__file__).parent / "data"
    cache = tmp_path / "cache"
    url = base.resolve().as_uri()
    path = fetch_profile("illumina_profile.json", base_url=url, cache_dir=cache)
    assert path.is_file()
    assert path.read_bytes() == (base / "illumina_profile.json").read_bytes()
    # second call should use cache
    called = False

    def fake_open(url: str):
        nonlocal called
        called = True
        raise RuntimeError("network call")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    try:
        path2 = fetch_profile(
            "illumina_profile.json", base_url=url, cache_dir=cache
        )
    finally:
        monkeypatch.undo()
    assert path2 == path
    assert not called


def test_cli_data_fetch(tmp_path: Path) -> None:
    base = Path(__file__).parent / "data"
    env = os.environ.copy()
    env["GENECODER_DATA_DIR"] = str(tmp_path / "cache")
    src = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")
    result = run_cli_command([
        "data",
        "fetch",
        "illumina_profile.json",
        "--url",
        base.resolve().as_uri(),
    ], env=env)
    assert result.returncode == 0
    cached = Path(env["GENECODER_DATA_DIR"]) / "illumina_profile.json"
    assert cached.is_file()
