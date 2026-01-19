from __future__ import annotations

import types
import sys
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")
if yaml.safe_load("foo: 1") != {"foo": 1}:
    pytest.skip("Functional YAML parser required for bundle tests", allow_module_level=True)


def test_bundle_launches_dashboard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = Path(__file__).resolve().parents[1] / "configs" / "pipeline_metrics.yaml"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    metrics_path = tmp_path / "bundle_metrics.json"

    calls: list[tuple[str, ...]] = []
    module = types.ModuleType("genecoder.dashboard_streamlit")

    def _record_launch(*paths: str) -> None:
        calls.append(tuple(paths))

    module.launch = _record_launch  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "genecoder.dashboard_streamlit", module)

    result = run_cli_command(
        [
            "bundle",
            "run",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--metrics-path",
            str(metrics_path),
            "--launch-dashboard",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert calls == [(str(metrics_path),)]


def test_dashboard_missing_streamlit_warns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = types.ModuleType("genecoder.dashboard_streamlit")

    def _raise_missing(*_args: str) -> None:
        raise RuntimeError("streamlit is required to launch the dashboard")

    module.launch = _raise_missing  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "genecoder.dashboard_streamlit", module)

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text("{}")

    result = run_cli_command(["dashboard", str(metrics_path)])

    assert result.returncode == 0, result.stderr
    assert "Streamlit dashboard unavailable" in result.stderr
