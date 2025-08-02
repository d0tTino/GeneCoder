import json
from pathlib import Path

from tests.test_cli import run_cli_command


def test_pipeline_outputs_metrics(tmp_path: Path) -> None:
    inp = tmp_path / "in.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(b"hello")

    result = run_cli_command(["pipeline", str(inp), str(outp), "--codec", "reverse"])
    assert result.returncode == 0, result.stderr
    metrics_path = outp.with_suffix(outp.suffix + ".json")
    data = json.loads(metrics_path.read_text())
    metrics = data.get("metrics", data)
    assert isinstance(metrics.get("gc_distribution"), list)
    assert isinstance(metrics.get("homopolymer_runs"), list)
    assert isinstance(metrics.get("ecc_success_rates"), dict)
