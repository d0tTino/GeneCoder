from __future__ import annotations

from pathlib import Path

import yaml

from genecoder.plugin_api import Codec as PluginCodec
from genecoder.sdk import ExperimentSpec, run_experiment, sweep


def test_api_facade_redirects_to_plugin_api() -> None:
    from genecoder.api import Codec

    assert Codec is PluginCodec


def test_run_experiment_supports_dataclass_and_yaml(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"gene-coder-sdk")

    output_obj = tmp_path / "decoded-object.bin"
    output_cfg = tmp_path / "decoded-config.bin"

    object_spec = ExperimentSpec(
        codec="reverse",
        fec_backend=None,
        channel=None,
        input_path=str(source),
        output_path=str(output_obj),
    )

    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "codec": "reverse",
                "fec_backend": None,
                "channel": None,
                "input_path": str(source),
                "output_path": str(output_cfg),
            }
        )
    )

    object_result = run_experiment(object_spec)
    config_result = run_experiment(config_path)

    assert object_result.decoded == source.read_bytes()
    assert config_result.decoded == source.read_bytes()
    assert object_result.metrics == config_result.metrics


def test_sweep_returns_immutable_runs(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"sweep-check")

    result = sweep(
        [
            {
                "codec": "reverse",
                "input_path": str(source),
                "output_path": str(tmp_path / "decoded-1.bin"),
            },
            {
                "codec": "reverse",
                "input_path": str(source),
                "output_path": str(tmp_path / "decoded-2.bin"),
            },
        ]
    )

    assert isinstance(result.runs, tuple)
    assert len(result.runs) == 2
    assert result.runs[0].decoded == source.read_bytes()
