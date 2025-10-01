import json
from pathlib import Path

import pytest
from tests.test_cli import run_cli_command

try:  # pragma: no cover - skip if streamlit fails to import
    streamlit = pytest.importorskip("streamlit")
    bootstrap = pytest.importorskip("streamlit.web.bootstrap")
except Exception:
    pytest.skip("streamlit unavailable", allow_module_level=True)


def test_dashboard_cli_starts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = {
        "gc_distribution": [0.5],
        "gc_content": 0.5,
        "gc_variance": 0.0,
        "homopolymer_runs": [1],
        "ecc_success_rates": {"hamming": 1.0},
        "decode_success_rate": 1.0,
    }
    results = tmp_path / "results.json"
    results.write_text(json.dumps(data))

    called = False

    def fake_run(
        path: str,
        is_hello: bool,
        args: list[str],
        flag_options: dict,
        *,
        stop_immediately_for_testing: bool = False,
    ) -> None:
        nonlocal called
        assert Path(path).name == "dashboard_streamlit.py"
        assert args == [str(results)]
        called = True

    monkeypatch.setattr(bootstrap, "run", fake_run)
    res = run_cli_command(["dashboard", str(results)])
    assert res.returncode == 0, res.stderr
    assert called


def test_dashboard_summary_plots_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())

    charts: list[object] = []
    writes: list[object] = []

    def capture_bar_chart(
        data: object, *args: object, **kwargs: object
    ) -> None:  # pragma: no cover - simple capture
        charts.append(data)

    def capture_write(*args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        writes.extend(args)

    monkeypatch.setattr(streamlit, "bar_chart", capture_bar_chart)
    monkeypatch.setattr(streamlit, "write", capture_write)

    from genecoder import dashboard_streamlit as dash

    # Force fallback chart rendering in case pandas/altair are installed
    monkeypatch.setattr(dash, "pd", None)
    monkeypatch.setattr(dash, "alt", None)

    dash.main(str(results))

    def contains_chart(target: object) -> bool:
        return any(chart == target for chart in charts)

    assert contains_chart({"results": 0.0})
    assert contains_chart({"results": pytest.approx(2.0)})
    assert contains_chart({"results": 3.0})
    assert contains_chart({"results (Substitutions)": pytest.approx(2.0)})
    assert contains_chart({"results (Insertions)": pytest.approx(0.0)})
    assert contains_chart({"results (Deletions)": pytest.approx(0.0)})
    assert contains_chart({"results (Coverage)": pytest.approx(30.0)})
    assert [1, 3, 2] in charts
    assert any(isinstance(entry, dict) and "GC%" in entry for entry in writes)


def test_dashboard_homopolymer_chart_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())

    charts: list[object] = []
    writes: list[object] = []

    def capture_bar_chart(data: object, *args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        charts.append(data)

    def capture_write(*args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        writes.extend(args)

    monkeypatch.setattr(streamlit, "bar_chart", capture_bar_chart)
    monkeypatch.setattr(streamlit, "write", capture_write)

    from genecoder import dashboard_streamlit as dash

    # Force fallback chart rendering in case pandas/altair are installed
    monkeypatch.setattr(dash, "pd", None)
    monkeypatch.setattr(dash, "alt", None)

    dash.main(str(results))

    assert charts
    assert [1, 2, 1, 0] in charts
    assert any(chart == {"results": pytest.approx(30.0)} for chart in charts)
    assert any(isinstance(entry, dict) and entry.get("Dropout") for entry in writes)
