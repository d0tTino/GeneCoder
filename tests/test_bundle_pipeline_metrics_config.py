import hashlib
import json
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command

yaml = pytest.importorskip("yaml")
if yaml.safe_load("foo: 1") != {"foo": 1}:
    pytest.skip("Functional YAML parser required for bundle tests", allow_module_level=True)


def test_bundle_pipeline_metrics_config(tmp_path: Path) -> None:
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
            "--emit-manifest-report",
            "--allow-missing-fec",
        ]
    )
    assert result.returncode == 0, result.stderr

    metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "bundle_runs" in metrics_data
    assert "oligos_simulated" in metrics_data

    config_dict = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config_hash = hashlib.sha256(
        json.dumps(config_dict, sort_keys=True).encode("utf-8")
    ).hexdigest()

    run_root = cache_dir / config_hash
    run_dirs = sorted(run_root.iterdir())
    assert run_dirs, "bundle run directory missing"
    decoded_dir = run_dirs[-1] / "decoded"

    decoded_metrics_file = next(decoded_dir.glob("*.bin.json"))
    decoded_metrics = json.loads(decoded_metrics_file.read_text(encoding="utf-8"))
    manifest_path = decoded_metrics_file.with_suffix(".manifest.json")
    assert manifest_path.exists(), "decoded manifest missing"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data.get("metrics"), "manifest missing metrics payload"
    html_report_path = manifest_path.with_suffix(".html")
    assert html_report_path.exists(), "HTML manifest report missing"
    html_content = html_report_path.read_text(encoding="utf-8")
    assert "<html" in html_content.lower()
    metrics = decoded_metrics.get("metrics", {})

    channel = metrics.get("channel", {})
    assert "dropout" in channel
    dropout = channel.get("dropout", {})
    assert "count" in dropout

    sequence_batch = metrics.get("sequence_batch", {})
    metadata = sequence_batch.get("metadata", {}) if isinstance(sequence_batch, dict) else {}
    assert "sim_dropout_total" in metadata
    assert "sim_dropout_fraction" in metadata

    oligo_metrics = metrics.get("oligo_metrics", {})
    assert "dropout_flags" in oligo_metrics
    assert "coverage_counts" in oligo_metrics
