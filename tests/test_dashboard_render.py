from pathlib import Path

import pytest

try:  # pragma: no cover - skip if streamlit fails to import
    from streamlit.testing.v1 import AppTest
except Exception:
    pytest.skip("streamlit unavailable", allow_module_level=True)


def test_dashboard_main_renders(tmp_path: Path) -> None:
    metrics_file = Path(__file__).parent / "data" / "metrics.json"
    results = tmp_path / "results.json"
    results.write_text(metrics_file.read_text())
    def run_app(path: str) -> None:
        from genecoder import dashboard as dash
        dash.main(path)

    app = AppTest.from_function(run_app, args=(str(results),))
    app.run()
    assert not app.exception
