import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_main_renders(tmp_path: Path) -> None:
    data = {
        "gc_distribution": [0.1, 0.2, 0.3],
        "gc_content": 0.2,
        "homopolymer_runs": [1, 2, 3],
        "ecc_success_rates": {"hamming": 1.0},
        "decode_success_rate": 0.9,
    }
    results = tmp_path / "results.json"
    results.write_text(json.dumps(data))
    def run_app(path: str) -> None:
        from genecoder import dashboard as dash
        dash.main(path)

    app = AppTest.from_function(run_app, args=(str(results),))
    app.run()
    assert not app.exception
