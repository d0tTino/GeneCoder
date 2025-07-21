import json
from pathlib import Path

import pytest
from tests.test_cli import run_cli_command

streamlit = pytest.importorskip("streamlit")
bootstrap = pytest.importorskip("streamlit.web.bootstrap")


def test_dashboard_cli_starts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = {"gc_distribution": [0.5], "homopolymer_runs": [1], "ecc_success_rates": {"hamming": 1.0}}
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
