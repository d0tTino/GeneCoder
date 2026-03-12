from __future__ import annotations

import json
from pathlib import Path

from genecoder.results.repro_report import generate_reproducibility_report
from tests.test_cli import run_cli_command


def _make_run(
    path: Path,
    *,
    run_id: str,
    profile: str,
    seed: int,
    ber: float,
    runtime_total: float,
    decode_success: bool = True,
) -> None:
    payload = {
        "schema_version": "1.2",
        "run_id": run_id,
        "profiles": {"encoding": "reverse", "simulation": profile, "decode": "reverse"},
        "seeds": {
            "global": seed,
            "encode": seed,
            "simulate": seed,
            "decode": seed,
            "provenance": {},
        },
        "runtime": {
            "total_seconds": runtime_total,
            "encode_seconds": runtime_total / 3,
            "simulate_seconds": runtime_total / 3,
            "decode_seconds": runtime_total / 3,
        },
        "stages": {
            "encode": {"metrics": {}},
            "simulate": {"metrics": {}},
            "decode": {"metrics": {"decode_success": decode_success}},
        },
        "outcome": {
            "ber": ber,
            "decode_success": decode_success,
            "dropout_rate": 0.0,
            "gc_stress": 0.0,
            "homopolymer_stress": 0.0,
            "throughput": 1.0,
            "metrics": {},
        },
        "constraint_outcomes": {"summary": {}, "by_oligo": {}, "stages": []},
        "decode_outcomes": {
            "decode_success": decode_success,
            "decode_success_rate": 1.0 if decode_success else 0.0,
            "ecc_success_rates": {},
        },
        "provenance": {"source_format": "test", "generator": "test"},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_generate_reproducibility_report_pass(tmp_path: Path) -> None:
    run_a = tmp_path / "run_a.json"
    run_b = tmp_path / "run_b.json"
    _make_run(
        run_a, run_id="a", profile="illumina", seed=11, ber=0.0, runtime_total=1.0
    )
    _make_run(
        run_b, run_id="b", profile="illumina", seed=11, ber=0.0, runtime_total=1.1
    )

    report = generate_reproducibility_report([run_a, run_b])
    assert report["summary"]["comparison_count"] == 1
    assert report["summary"]["pass"] is True


def test_generate_reproducibility_report_detects_violation(tmp_path: Path) -> None:
    run_a = tmp_path / "run_a.json"
    run_b = tmp_path / "run_b.json"
    _make_run(
        run_a, run_id="a", profile="illumina", seed=11, ber=0.0, runtime_total=1.0
    )
    _make_run(
        run_b, run_id="b", profile="illumina", seed=11, ber=0.2, runtime_total=1.0
    )

    report = generate_reproducibility_report([run_a, run_b])
    assert report["summary"]["pass"] is False
    assert report["summary"]["tolerance_violations"] >= 1


def test_bundle_run_emit_repro_report(tmp_path: Path) -> None:
    bundle_cfg = tmp_path / "bundle.yml"
    in_file = tmp_path / "msg.txt"
    in_file.write_text("hello")
    import yaml

    bundle_cfg.write_text(
        yaml.safe_dump(
            {
                "encode": {"input_files": [str(in_file)], "method": "base4_direct"},
                "decode": {"method": "base4_direct"},
            }
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "runs"
    result = run_cli_command(
        [
            "bundle",
            "run",
            str(bundle_cfg),
            "--cache-dir",
            str(cache_dir),
            "--emit-repro-report",
        ]
    )
    assert result.returncode == 0, result.stderr
    reports = list(cache_dir.glob("*/*/reproducibility_report.json"))
    assert reports
