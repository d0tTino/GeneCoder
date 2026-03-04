from __future__ import annotations

import argparse
import json
from pathlib import Path

from genecoder.cli import pipeline as pipeline_cli
from genecoder.sdk import run_experiment


def _schema_shape(value):  # noqa: ANN001
    if isinstance(value, dict):
        return {key: _schema_shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_schema_shape(item) for item in value]
    return type(value).__name__


def test_cli_and_sdk_emit_same_run_schema_structure_for_seeded_profile_request(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"runtime-contract")

    output = tmp_path / "decoded.bin"

    cli_args = argparse.Namespace(
        seed=17,
        metrics_path=None,
        launch_dashboard=False,
        config=None,
        codec="reverse",
        fec=None,
        channel="simple",
        sub_rate=0.0,
        ins_rate=0.0,
        del_rate=0.0,
        explain_coding_stack=False,
        mpi_workers=None,
        input=str(source),
        output=str(output),
        emit_manifest_report=False,
    )
    pipeline_cli._handle_command(cli_args)
    cli_schema = json.loads(Path(str(output) + ".json").read_text(encoding="utf-8"))

    sdk_result = run_experiment(
        {
            "codec": "reverse",
            "input_path": str(source),
            "output_path": str(output),
            "channel": "simple",
            "profile": {
                "name": "simple",
                "parameters": {"substitution_prob": 0.0},
            },
            "seeds": {"global_seed": 17},
        }
    )

    assert _schema_shape(cli_schema) == _schema_shape(dict(sdk_result.canonical_run))
