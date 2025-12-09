from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")
if yaml.safe_load("foo: 1") != {"foo": 1}:
    pytest.skip("Functional YAML parser required for bundle tests", allow_module_level=True)
try:  # pragma: no cover - optional GUI dependencies
    from streamlit.testing.v1 import AppTest
except Exception:  # pragma: no cover - skip when Streamlit extras unavailable
    pytest.skip("streamlit extras unavailable", allow_module_level=True)


def test_pipeline_metrics_dashboard_roundtrip(tmp_path: Path) -> None:
    """Run the pipeline metrics config and ensure dashboard renders the output."""

    config_path = Path(__file__).resolve().parents[1] / "configs" / "pipeline_metrics.yaml"
    cache_dir = tmp_path / "bundle_cache"
    cache_dir.mkdir()
    metrics_path = tmp_path / "metrics.json"

    result = run_cli_command(
        [
            "bundle",
            "run",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--metrics-path",
            str(metrics_path),
        ]
    )
    assert result.returncode == 0, result.stderr

    metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics_data, "Pipeline run did not produce metrics output"

    def render_dashboard(path: str) -> None:
        from genecoder import dashboard as dash

        dash.main(path)

    app = AppTest.from_function(render_dashboard, args=(str(metrics_path),))
    app.run()

    assert not app.exception
    assert any(title.value == "GeneCoder Dashboard" for title in app.title)
    assert app.metric or app.markdown, "Dashboard did not render any elements"
