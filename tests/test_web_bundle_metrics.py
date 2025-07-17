import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

httpx = pytest.importorskip("httpx")
fastapi = pytest.importorskip("fastapi")

import web.main as main


def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:  # noqa: ANN401
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, url, **kwargs)

    return asyncio.run(_call())


def test_bundle_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENECODER_BUNDLE_DIR", str(tmp_path))
    main.BUNDLE_DIR = Path(tmp_path)
    mdir = tmp_path / "run"
    mdir.mkdir()
    (mdir / "file.manifest.json").write_text(
        json.dumps({
            "file": "x",
            "encoding_parameters": {"method": "base4_direct"},
            "metrics": {"original_size": 10, "dna_length": 20, "bits_per_nt": 1.5},
        })
    )
    r = _request("GET", "/bundle-metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["files"] == 1
    assert data["total_original_size"] == 10
    assert data["total_dna_length"] == 20
    assert abs(data["avg_bits_per_nt"] - 1.5) < 1e-6

