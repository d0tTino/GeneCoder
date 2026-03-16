import asyncio
import json
from pathlib import Path


import pytest

httpx = pytest.importorskip("httpx")
fastapi = pytest.importorskip("fastapi")

import web.main as main


def _request(method: str, url: str, **kwargs: object) -> httpx.Response:
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
            "metrics": {
                "original_size": 10,
                "dna_length": 20,
                "bits_per_nt": 1.5,
                "substitutions": 2,
                "insertions": 1,
                "deletions": 1,
                "coverage": 5,
                "constraint_violations": {
                    "count": 1,
                    "violations": [
                        {
                            "sequence_id": "oligo-1",
                            "type": "gc_low",
                            "length": 42,
                        }
                    ],
                    "type_counts": {"gc_low": 1},
                },
                "cost_per_recovered_bit": 0.0025,
                "reads_per_successful_decode": 12.0,
                "redundancy_cost_ratio": 1.8,
            },
        })
    )
    r = _request("GET", "/bundle-metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["files"] == 1
    assert data["total_original_size"] == 10
    assert data["total_dna_length"] == 20
    assert abs(data["avg_bits_per_nt"] - 1.5) < 1e-6
    assert data["total_substitutions"] == 2
    assert data["total_insertions"] == 1
    assert data["total_deletions"] == 1
    assert data["total_coverage"] == 5
    assert data["total_constraint_violations"] == 1



    assert abs(data["avg_cost_per_recovered_bit"] - 0.0025) < 1e-9
    assert abs(data["avg_reads_per_successful_decode"] - 12.0) < 1e-9
    assert abs(data["avg_redundancy_cost_ratio"] - 1.8) < 1e-9
