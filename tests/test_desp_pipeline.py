from __future__ import annotations

from pathlib import Path
import json

import pytest

yaml = pytest.importorskip("yaml")

from genecoder.api import Codec
from genecoder.core import run_pipeline
from genecoder.encoders import decode_base4_direct, encode_base4_direct
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.reed_solomon_codec import _HAS_REEDSOLO
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.formats import SequenceBatch
import genecoder.desp_adapter as desp_adapter
from tests.test_cli import PROJECT_ROOT


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        return decode_base4_direct(encoded)[0]


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_desp_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensure the DeSP preset integrates with run_pipeline using a stub adapter."""

    config_path = PROJECT_ROOT / "configs" / "desp_pipeline.yaml"
    config = yaml.safe_load(config_path.read_text())
    sim_cfg = config["simulate"]["simulators"][0]
    assert sim_cfg["name"] == "desp"
    error_rate = float(sim_cfg["error_rate"])

    calls: list[tuple[str, float]] = []

    def _fake_simulate_adapter(
        command: str,
        sequence: str,
        rate: float,
        rng,
        extra_args=None,
    ) -> str:
        calls.append((command, rate))
        translate = str.maketrans("ACGT", "CGTA")
        return sequence.translate(translate)

    monkeypatch.setattr(desp_adapter, "_simulate_adapter", _fake_simulate_adapter)
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")

    init_plugins()
    CODEC_REGISTRY["base4_direct"] = {
        "encode": _Base4Codec().encode,
        "decode": _Base4Codec().decode,
    }
    SIMULATOR_REGISTRY["desp"] = desp_adapter.DeSPChannel(error_rate=error_rate)

    source_path = PROJECT_ROOT / "examples" / "pipeline_demo_input.txt"
    input_path = tmp_path / "input.txt"
    output_path = tmp_path / "output.bin"
    input_path.write_bytes(source_path.read_bytes())

    result, metrics = run_pipeline(
        "base4_direct", "reed_solomon", "desp", str(input_path), str(output_path)
    )

    assert result == source_path.read_bytes()
    assert output_path.read_bytes() == result
    assert calls and calls[0] == ("desp", error_rate)
    assert isinstance(metrics.get("substitutions"), int)
    assert isinstance(metrics.get("insertions"), int)
    assert isinstance(metrics.get("deletions"), int)


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_desp_multi_stage_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run a multi-stage DeSP channel config and ensure stages propagate."""

    input_fasta = tmp_path / "input.fasta"
    input_fasta.write_text(">seq\nACGTACGTACGT\n", encoding="utf-8")
    output_fasta = tmp_path / "output.fasta"

    config_data = {
        "input": str(input_fasta),
        "output": str(output_fasta),
        "simulators": [
            {
                "name": "desp",
                "stage": "synthesis",
                "error_rate": 0.08,
                "options": ["--model", "r10"],
            },
            {
                "name": "desp",
                "stage": "sequencing",
                "error_rate": 0.12,
                "options": "--temperature 5",
            },
        ],
        "pipeline": {
            "dropout_rate": 0.05,
        },
    }

    config_path = tmp_path / "multi_stage.yaml"
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    calls: list[tuple[str, float, tuple[str, ...]]] = []

    def _stub_simulate_adapter(
        command: str,
        sequence: str,
        rate: float,
        rng,
        extra_args=None,
    ) -> str:
        extra: tuple[str, ...] = tuple(extra_args or ())
        calls.append((command, rate, extra))
        return sequence

    monkeypatch.setattr(desp_adapter, "_simulate_adapter", _stub_simulate_adapter)
    monkeypatch.setenv("GENECODER_SIM_SEED", "11")

    init_plugins()

    from genecoder.cli import channel as channel_cli

    simulators, constraints, cfg, extra = channel_cli._load_config(str(config_path))
    channel_cli.process_channel(
        extra["input_file"],
        extra["output_file"],
        simulators,
        constraints,
        sub_prob=extra.get("sub_prob", 0.0),
        ins_prob=extra.get("ins_prob", 0.0),
        del_prob=extra.get("del_prob", 0.0),
        seed=extra.get("seed"),
        config=cfg,
        batch_workers=extra.get("batch_workers"),
    )

    assert len(calls) == 2
    assert calls[0][0] == "desp"
    assert calls[1][0] == "desp"
    assert "--stage" in calls[0][2]
    assert "--stage" in calls[1][2]
    assert set(calls[0][2]) >= {"--stage", "synthesis", "--model", "r10"}
    assert set(calls[1][2]) >= {"--stage", "sequencing", "--temperature", "5"}

    manifest_path = output_fasta.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stages = manifest.get("stages", [])
    assert isinstance(stages, list)
    assert len(stages) == 2
    first_stage = stages[0]
    assert first_stage.get("stage") == "synthesis"
    assert first_stage.get("parameters", {}).get("error_rate") == 0.08
    assert "--model" in first_stage.get("options", [])
    second_stage = stages[1]
    assert second_stage.get("stage") == "sequencing"
    assert second_stage.get("parameters", {}).get("error_rate") == 0.12
    assert "--temperature" in second_stage.get("options", [])

    batch = SequenceBatch.from_fasta(output_fasta.read_text(encoding="utf-8"))
    stage_meta_raw = batch.metadata.get("sim_stages")
    assert stage_meta_raw is not None
    parsed_stage_meta = json.loads(stage_meta_raw)
    assert parsed_stage_meta[0]["stage"] == "synthesis"
