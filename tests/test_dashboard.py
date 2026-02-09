import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def dummy_streamlit(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    calls: dict[str, list] = {
        "metric": [],
        "bar_chart": [],
        "dataframe": [],
        "write": [],
        "subheader": [],
    }

    def metric(*args, **kwargs) -> None:
        calls["metric"].append((args, kwargs))

    def bar_chart(*args, **kwargs) -> None:
        calls["bar_chart"].append((args, kwargs))

    def dataframe(*args, **kwargs) -> None:
        calls["dataframe"].append((args, kwargs))

    def write(*args, **kwargs) -> None:
        calls["write"].append((args, kwargs))

    def subheader(*args, **kwargs) -> None:
        calls["subheader"].append((args, kwargs))

    dummy = SimpleNamespace(
        title=lambda *a, **k: None,
        write=write,
        header=lambda *a, **k: None,
        subheader=subheader,
        line_chart=lambda *a, **k: None,
        metric=metric,
        bar_chart=bar_chart,
        error=lambda *a, **k: None,
        dataframe=dataframe,
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
    charts = [args[0] for args, _ in dummy_streamlit["bar_chart"]]
    assert {"rs": 0.8, "bch": 0.9} in charts
    assert {"metrics": 5.0} in charts
    assert {"metrics": 1.0} in charts
    assert {"metrics": 2.0} in charts

    # Decode success metric averages ECC rates
    assert dummy_streamlit["metric"], "metric not called"
    label, value = dummy_streamlit["metric"][0][0][:2]
    assert label == "Decode Success"
    assert value == "85.00%"


def test_calc_decode_success_fallback() -> None:
    from genecoder import dashboard

    data = {"ecc_success_rates": {"rs": 0.8, "bch": "x", "hamming": 1.0}}
    # average of numeric rates 0.8 and 1.0 -> 0.9
    assert dashboard._calc_decode_success(data) == pytest.approx(0.9)


def test_homopolymer_distribution_chart(
    tmp_path: Path, dummy_streamlit: dict[str, list]
) -> None:
    data = {"homopolymer_runs": [1, 2, 1]}
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(data))

    mod = importlib.reload(importlib.import_module("genecoder.dashboard"))
    mod.main(str(path))

    charts = [args[0] for args, _ in dummy_streamlit["bar_chart"]]
    assert [1, 2, 1] in charts


def test_display_coverage_and_constraint_metrics(
    tmp_path: Path, dummy_streamlit: dict[str, list]
) -> None:
    data = {
        "coverage_distribution": [1, 3, 2],
        "constraint_violations": {
            "count": 2,
            "violations": [
                {"sequence_id": "oligo-1", "type": "gc_low", "length": 48},
                {
                    "sequence_id": "oligo-2",
                    "types": ["length_short", "gc_low"],
                    "type": "length_short",
                    "length": 10,
                },
            ],
            "type_counts": {"gc_low": 2, "length_short": 1},
        },
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(data))

    mod = importlib.reload(importlib.import_module("genecoder.dashboard"))
    mod.main(str(path))

    # Ensure coverage distribution and constraint violation charts are rendered
    assert dummy_streamlit["bar_chart"], "bar_chart not called"
    charts = [args[0] for args, _ in dummy_streamlit["bar_chart"]]
    assert [1, 3, 2] in charts
    assert {"gc_low": 2, "length_short": 1} in charts
    assert dummy_streamlit["dataframe"], "dataframe not called"
    rows = dummy_streamlit["dataframe"][0][0][0]
    assert isinstance(rows, list)
    assert any(row.get("Sequence ID") == "oligo-1" for row in rows)


def test_error_histograms_rendered(
    tmp_path: Path, dummy_streamlit: dict[str, list]
) -> None:
    data = {
        "substitutions": [0, 1, 1, 2],
        "insertions": {"0": 2, "1": 1},
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(data))

    mod = importlib.reload(importlib.import_module("genecoder.dashboard"))
    mod.main(str(path))

    charts = [args[0] for args, _ in dummy_streamlit["bar_chart"]]
    assert [1, 2, 1] in charts
    assert [2, 1] in charts


def test_custom_constraint_limits_drive_flagged_oligos(
    tmp_path: Path, dummy_streamlit: dict[str, list]
) -> None:
    data = {
        "oligo_metrics": {
            "gc_percentages": [0.7, 0.1],
            "max_homopolymers": [4, 4],
            "dropout_flags": [0, 0],
        },
        "constraint_violations": {
            "limits": {"gc_min": 0.2, "gc_max": 0.8, "max_homopolymer": 6}
        },
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(data))

    mod = importlib.reload(importlib.import_module("genecoder.dashboard"))
    mod.pd = None
    mod.alt = None
    mod.main(str(path))

    flagged_tables = [
        args[0]
        for args, _ in dummy_streamlit["write"]
        if args
        and isinstance(args[0], list)
        and args[0]
        and isinstance(args[0][0], dict)
        and "Index" in args[0][0]
    ]
    assert flagged_tables, "flagged oligo table not written"
    flagged = flagged_tables[-1]
    assert [row.get("Index") for row in flagged] == [2]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("1", True),
        ("0", False),
        ("true", True),
        ("false", False),
        ("yes", True),
        ("no", False),
        ("bad-value", False),
    ],
)
def test_parse_bool(value: object, expected: bool) -> None:
    from genecoder import dashboard

    assert dashboard._parse_bool(value) is expected


def test_extract_oligo_records_handles_malformed_dropout_flags() -> None:
    from genecoder import dashboard

    records = dashboard._extract_oligo_records(
        {
            "oligo_metrics": {
                "gc_percentages": [0.4, 0.5, 0.6],
                "dropout_flags": ["true", "invalid", "off", None, object()],
            }
        }
    )

    assert [record.get("Dropout") for record in records] == [True, False, False, False, False]
