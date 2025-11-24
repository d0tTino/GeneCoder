import json
from pathlib import Path

from genecoder.bundle_metrics import aggregate_metrics
from tests.test_cli import run_cli_command


def _write_manifest(run_dir: Path) -> None:
    manifest = {
        "file": "sample.bin",
        "encoding_parameters": {"method": "base4_direct"},
        "metrics": {
            "original_size": 10,
            "dna_length": 20,
            "bits_per_nt": 1.5,
            "substitutions": 2,
            "insertions": 1,
            "deletions": 1,
            "coverage": 5,
            "constraint_violations": {"count": 1},
        },
    }
    (run_dir / "file.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_cli_bundle_stats_matches_endpoint(tmp_path: Path) -> None:
    mdir = tmp_path / "run"
    mdir.mkdir()
    _write_manifest(mdir)

    expected = aggregate_metrics(tmp_path)

    result = run_cli_command(["stats", "bundle", "--runs", str(tmp_path)])
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)

    assert output == expected
