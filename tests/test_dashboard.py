import json
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def dummy_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = SimpleNamespace(
        title=lambda *a, **k: None,
        write=lambda *a, **k: None,
        header=lambda *a, **k: None,
        line_chart=lambda *a, **k: None,
        metric=lambda *a, **k: None,
        bar_chart=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", dummy)


def test_load_metrics_fixture() -> None:
    path = Path(__file__).parent / "data" / "metrics.json"
    from genecoder import dashboard
    expected = json.loads(path.read_text())
    assert dashboard._load_metrics(str(path)) == expected


def test_main_runs(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    path.write_text("{}")

    mod = importlib.reload(importlib.import_module("genecoder.dashboard"))
    mod.main(str(path))


def test_load_metrics_manifest(tmp_path: Path) -> None:
    metrics_path = Path(__file__).parent / "data" / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    manifest = {
        "file": "test.bin",
        "encoding_parameters": {"method": "base4_direct"},
        "metrics": metrics,
    }
    manifest_path = tmp_path / "test.manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    from genecoder import dashboard

    assert dashboard._load_metrics(str(manifest_path)) == metrics
