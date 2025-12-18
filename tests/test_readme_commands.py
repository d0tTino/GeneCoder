import json
from pathlib import Path

from tests.test_cli import run_cli_command


def test_readme_sweep_example_dry_run(tmp_path: Path) -> None:
    cache_dir = tmp_path / "sweep_runs"
    metrics_path = tmp_path / "metrics.json"
    manifest_index = tmp_path / "manifest_index.json"

    result = run_cli_command(
        [
            "bundle",
            "sweep",
            "configs/rs_illumina_pipeline.yaml",
            "configs/fountain_nanopore_pipeline.yaml",
            "--cache-dir",
            str(cache_dir),
            "--metrics-path",
            str(metrics_path),
            "--manifest-index",
            str(manifest_index),
            "--dry-run",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert metrics_path.exists()
    assert manifest_index.exists()

    index_data = json.loads(manifest_index.read_text(encoding="utf-8"))
    runs = index_data.get("runs", [])
    assert len(runs) == 2
    for entry in runs:
        run_dir = Path(entry["run_dir"])
        assert run_dir.exists()
        assert any(run_dir.glob("encoded/*.manifest.json"))
        assert any(run_dir.glob("decoded/*.json"))
