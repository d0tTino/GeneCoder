import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_cli import run_cli_command
from genecoder.simulators.nanopore import NanoporeDNArSimChannel
from genecoder.simulators.illumina import IlluminaChannel, ILLUMINA_PROFILES


def test_pipeline_cli_profile_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    input_file = tmp_path / "msg.txt"
    input_file.write_text("hi")
    output_file = tmp_path / "out.txt"

    config = {
        "codec": "reverse",
        "channel": {"name": "nanopore_dnarsim", "profile": "r10.3"},
    }
    cfg_path = tmp_path / "pipe.yml"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    from genecoder.cli import pipeline as pipeline_module

    def _json_loader(data: object) -> object:
        if hasattr(data, "read"):
            return json.load(data)  # type: ignore[arg-type]
        if data:
            return json.loads(data)
        return {}

    monkeypatch.setattr(
        pipeline_module,
        "yaml_module",
        SimpleNamespace(safe_load=_json_loader),
        raising=False,
    )

    called: list[str | None] = []

    def fake_simulate(self: NanoporeDNArSimChannel, seq: str) -> str:
        called.append(self.profile)
        return seq

    monkeypatch.setattr(NanoporeDNArSimChannel, "simulate", fake_simulate)

    result = run_cli_command(
        ["pipeline", str(input_file), str(output_file), "--config", str(cfg_path)], env=env
    )
    assert result.returncode == 0, result.stderr
    assert called == ["r10.3"]
    assert output_file.read_text() == "hi"

    metrics_path = output_file.with_suffix(output_file.suffix + ".json")
    metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = metrics_data.get("metrics", metrics_data)

    assert metrics.get("dropout_count") == 0
    oligo_metrics = metrics.get("oligo_metrics", {})
    coverage_counts = oligo_metrics.get("coverage_counts")
    dropout_flags = oligo_metrics.get("dropout_flags")
    assert isinstance(coverage_counts, list)
    assert isinstance(dropout_flags, list)
    assert len(coverage_counts) == len(dropout_flags) == 1
    assert coverage_counts[0] >= 1
    seq_batch = metrics.get("sequence_batch", {})
    metadata = seq_batch.get("metadata", {}) if isinstance(seq_batch, dict) else {}
    assert isinstance(metadata, dict)
    assert metadata.get("sim_coverage_histogram") is not None

def test_pipeline_cli_illumina_profile_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    input_file = tmp_path / "msg2.txt"
    input_file.write_text("hi")
    output_file = tmp_path / "out2.txt"

    config = {
        "codec": "reverse",
        "channel": {"name": "illumina", "profile": "miseq"},
    }
    cfg_path = tmp_path / "pipe2.yml"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    from genecoder.cli import pipeline as pipeline_module

    def _json_loader(data: object) -> object:
        if hasattr(data, "read"):
            return json.load(data)  # type: ignore[arg-type]
        if data:
            return json.loads(data)
        return {}

    monkeypatch.setattr(
        pipeline_module,
        "yaml_module",
        SimpleNamespace(safe_load=_json_loader),
        raising=False,
    )

    called: list[tuple[float, float, float]] = []

    def fake_simulate(self: IlluminaChannel, seq: str) -> str:
        called.append((self.substitution_rate, self.insertion_rate, self.deletion_rate))
        return seq

    monkeypatch.setattr(IlluminaChannel, "simulate", fake_simulate)

    result = run_cli_command(
        ["pipeline", str(input_file), str(output_file), "--config", str(cfg_path)], env=env
    )
    assert result.returncode == 0, result.stderr
    expected = ILLUMINA_PROFILES["miseq"]
    assert called == [
        (
            expected["substitution_rate"],
            expected["insertion_rate"],
            expected["deletion_rate"],
        )
    ]
    assert output_file.read_text() == "hi"

    metrics_path = output_file.with_suffix(output_file.suffix + ".json")
    metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = metrics_data.get("metrics", metrics_data)

    assert metrics.get("dropout_count") == 0
    oligo_metrics = metrics.get("oligo_metrics", {})
    coverage_counts = oligo_metrics.get("coverage_counts")
    dropout_flags = oligo_metrics.get("dropout_flags")
    assert isinstance(coverage_counts, list)
    assert isinstance(dropout_flags, list)
    assert len(coverage_counts) == len(dropout_flags) == 1
    assert coverage_counts[0] >= 1
    seq_batch = metrics.get("sequence_batch", {})
    metadata = seq_batch.get("metadata", {}) if isinstance(seq_batch, dict) else {}
    assert isinstance(metadata, dict)
    assert metadata.get("sim_coverage_histogram") is not None
