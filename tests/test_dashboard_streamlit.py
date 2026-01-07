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


def test_dashboard_missing_plot_deps_emit_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())

    from genecoder import dashboard_streamlit as dash

    # Force fallback chart rendering in case pandas/altair are installed
    monkeypatch.setattr(dash, "pd", None)
    monkeypatch.setattr(dash, "alt", None)

    errors: list[str] = []

    def capture_error(message: object, *args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        errors.append(str(message))

    monkeypatch.setattr(streamlit, "error", capture_error)

    dash.main(str(results))

    assert errors
    assert any(
        "Plotting dependencies missing" in message
        and "pandas" in message
        and "altair" in message
        for message in errors
    )


def test_dashboard_summary_tables_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())

    tables: list[object] = []
    writes: list[object] = []

    def capture_table(data: object, *args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        tables.append(data)

    def capture_write(*args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        writes.extend(args)

    monkeypatch.setattr(streamlit, "table", capture_table)
    monkeypatch.setattr(streamlit, "write", capture_write)

    from genecoder import dashboard_streamlit as dash

    # Force fallback chart rendering in case pandas/altair are installed
    monkeypatch.setattr(dash, "pd", None)
    monkeypatch.setattr(dash, "alt", None)

    dash.main(str(results))

    assert any(
        isinstance(table, list)
        and any(
            isinstance(row, dict)
            and row.get("Metric") == "mean"
            and row.get("Value") == pytest.approx(25.0)
            for row in table
        )
        for table in tables
    )
    assert any(
        isinstance(table, list)
        and any(
            isinstance(row, dict)
            and row.get("Metric") == "Coverage"
            and row.get("Value") == pytest.approx(30.0)
            for row in table
        )
        for table in tables
    )
    assert any(
        isinstance(table, list)
        and any(
            isinstance(row, dict)
            and row.get("Window") == 1
            and row.get("GC%") == pytest.approx(10.0)
            for row in table
        )
        for table in tables
    )
    assert any(isinstance(entry, dict) and "GC%" in entry for entry in writes)


def test_dashboard_homopolymer_chart_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())

    tables: list[object] = []
    writes: list[object] = []

    def capture_table(data: object, *args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        tables.append(data)

    def capture_write(*args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        writes.extend(args)

    monkeypatch.setattr(streamlit, "table", capture_table)
    monkeypatch.setattr(streamlit, "write", capture_write)

    from genecoder import dashboard_streamlit as dash

    # Force fallback chart rendering in case pandas/altair are installed
    monkeypatch.setattr(dash, "pd", None)
    monkeypatch.setattr(dash, "alt", None)

    dash.main(str(results))

    assert tables
    expected_homopolymer_table = [
        {"Length": 0, "Count": 1},
        {"Length": 1, "Count": 2},
        {"Length": 2, "Count": 1},
        {"Length": 3, "Count": 0},
    ]
    assert any(table == expected_homopolymer_table for table in tables)
    assert any(
        isinstance(table, list)
        and any(
            isinstance(row, dict)
            and row.get("Metric") == "Coverage"
            and row.get("Value") == pytest.approx(30.0)
            for row in table
        )
        for table in tables
    )
    assert any(isinstance(entry, dict) and entry.get("Dropout") for entry in writes)


def test_dashboard_summary_plots_with_plotting_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())

    charts: list[object] = []

    def capture_altair_chart(
        chart: object, *args: object, **kwargs: object
    ) -> None:  # pragma: no cover - simple capture
        charts.append(chart)

    monkeypatch.setattr(streamlit, "altair_chart", capture_altair_chart)

    from genecoder import dashboard_streamlit as dash

    class FakeDataFrame:
        def __init__(self, data: object) -> None:
            self.data = data

        def dropna(self, *args: object, **kwargs: object) -> "FakeDataFrame":
            return self

    class FakePandas:
        DataFrame = FakeDataFrame

    class FakeChart:
        def __init__(self, data: object) -> None:
            self.data = data

        def mark_bar(self, *args: object, **kwargs: object) -> "FakeChart":
            return self

        def mark_line(self, *args: object, **kwargs: object) -> "FakeChart":
            return self

        def mark_boxplot(self, *args: object, **kwargs: object) -> "FakeChart":
            return self

        def encode(self, *args: object, **kwargs: object) -> "FakeChart":
            return self

        def properties(self, *args: object, **kwargs: object) -> "FakeChart":
            return self

    class FakeAlt:
        Chart = FakeChart

        class Bin:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

        @staticmethod
        def X(*args: object, **kwargs: object) -> tuple[object, ...]:
            return args

    monkeypatch.setattr(dash, "pd", FakePandas)
    monkeypatch.setattr(dash, "alt", FakeAlt)

    dash.main(str(results))

    assert charts
    assert all(isinstance(chart, FakeChart) for chart in charts)
