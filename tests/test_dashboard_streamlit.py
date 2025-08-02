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
        "homopolymer_runs": [1],
        "ecc_success_rates": {"hamming": 1.0},
        "decode_success_rate": 1.0,
    }
    results = tmp_path / "results.json"
    results.write_text(json.dumps(data))

    called = False

    def fake_run(path: str, is_hello: bool, args: list[str], flag_options: dict, *, stop_immediately_for_testing: bool = False) -> None:
        nonlocal called
        assert Path(path).name == "dashboard.py"
        assert args == [str(results)]
        called = True

    monkeypatch.setattr(bootstrap, "run", fake_run)
    res = run_cli_command(["dashboard", str(results)])
    assert res.returncode == 0, res.stderr
    assert called


def test_dashboard_error_counts_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())

    charts: list[object] = []

    def capture_bar_chart(data: object, *args: object, **kwargs: object) -> None:  # pragma: no cover - simple capture
        charts.append(data)

    monkeypatch.setattr(streamlit, "bar_chart", capture_bar_chart)

    from genecoder import dashboard as dash

    dash.main(str(results))

    assert charts
    assert charts[-1] == {"Substitutions": 2, "Insertions": 0, "Deletions": 0}
