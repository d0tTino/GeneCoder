from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import yaml

from genecoder.sdk import ExperimentRequest, ExperimentSpec, run_experiment


EXPECTED_REQUEST_FIELDS = {
    "codec",
    "input_path",
    "output_path",
    "fec_backend",
    "channel",
    "filter_mutated",
    "profile",
    "seeds",
    "matrix",
    "constraints",
    "artifacts",
}


def test_experiment_spec_alias_is_preserved() -> None:
    assert ExperimentSpec is ExperimentRequest


def test_experiment_request_field_surface_is_stable() -> None:
    assert {item.name for item in fields(ExperimentRequest)} == EXPECTED_REQUEST_FIELDS


def test_run_experiment_accepts_extended_yaml_contract(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"compat")

    config = tmp_path / "request.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "codec": "reverse",
                "input_path": str(source),
                "output_path": str(tmp_path / "decoded.bin"),
                "profile": {"name": "illumina", "parameters": {"substitution_rate": 0.01}},
                "seeds": {"global_seed": 9},
                "matrix": {"coverage": [5, 10]},
                "constraints": {"gc_min": 0.4, "gc_max": 0.6},
                "artifacts": {"emit_manifest": True},
            }
        ),
        encoding="utf-8",
    )

    result = run_experiment(config)

    assert result.decoded == source.read_bytes()
    assert "schema_version" in result.canonical_run
    assert result.artifact_paths["metrics"]
