import json
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def dummy_streamlit(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    calls: dict[str, list] = {"metric": [], "bar_chart": []}

    def metric(*args, **kwargs) -> None:
        calls["metric"].append((args, kwargs))

    def bar_chart(*args, **kwargs) -> None:
        calls["bar_chart"].append((args, kwargs))

    dummy = SimpleNamespace(
        title=lambda *a, **k: None,
        write=lambda *a, **k: None,
        header=lambda *a, **k: None,
        line_chart=lambda *a, **k: None,
        metric=metric,
        bar_chart=bar_chart,
        error=lambda *a, **k: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", dummy)
    return calls


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


def test_display_ecc_and_decode_metric(
    tmp_path: Path, dummy_streamlit: dict[str, list]
) -> None:
    data = {
        "ecc_success_rates": {"rs": 0.8, "bch": 0.9},
        "substitutions": 5,
        "insertions": 1,
        "deletions": 2,
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(data))

    mod = importlib.reload(importlib.import_module("genecoder.dashboard"))
    mod.main(str(path))

    # ECC success rates should be plotted
    assert dummy_streamlit["bar_chart"], "bar_chart not called"
    ecc_args, _ = dummy_streamlit["bar_chart"][0]
    assert {"rs": 0.8, "bch": 0.9} == ecc_args[0]
    assert len(dummy_streamlit["bar_chart"]) >= 2
    err_args, _ = dummy_streamlit["bar_chart"][1]
    assert {
        "Substitutions": 5,
        "Insertions": 1,
        "Deletions": 2,
    } == err_args[0]

    # Decode success metric averages ECC rates
    assert dummy_streamlit["metric"], "metric not called"
    label, value = dummy_streamlit["metric"][0][0][:2]
    assert label == "Decode Success"
    assert value == "85.00%"


def test_display_coverage_and_constraint_metrics(
    tmp_path: Path, dummy_streamlit: dict[str, list]
) -> None:
    data = {
        "coverage": 7,
        "constraint_violations": 2,
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(data))

    mod = importlib.reload(importlib.import_module("genecoder.dashboard"))
    mod.main(str(path))

    # Ensure coverage and constraint violation charts are rendered
    assert dummy_streamlit["bar_chart"], "bar_chart not called"
    charts = [args[0] for args, _ in dummy_streamlit["bar_chart"]]
    assert {"Coverage": 7} in charts
    assert {"Violations": 2} in charts
