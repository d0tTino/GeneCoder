from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_cli import run_cli_command

from genecoder.simulators.batch_utils import RESULT_COVERAGE_KEY, RESULT_DROPOUT_FLAG_KEY
from genecoder.simulators.illumina import IlluminaChannel
from genecoder.simulators.nanopore import NanoporeChannel


def _run_pipeline_with_config(
    tmp_path: Path,
    *,
    config: dict[str, object],
    seed: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, dict[str, object]]:
    input_file = tmp_path / "multi.bin"
    payload = bytes(range(64)) * 4
    input_file.write_bytes(payload)

    output_file = tmp_path / "decoded.bin"
    config_path = tmp_path / "pipeline.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    from genecoder.cli import pipeline as pipeline_module

    def _json_loader(data: object) -> object:
        if hasattr(data, "read"):
            return json.load(data)  # type: ignore[arg-type]
        if data:
            return json.loads(data)  # type: ignore[arg-type]
        return {}

    monkeypatch.setattr(
        pipeline_module,
        "yaml_module",
        SimpleNamespace(safe_load=_json_loader),
        raising=False,
    )

    env = os.environ.copy()
    env["GENECODER_SIM_SEED"] = seed

    result = run_cli_command(
        ["pipeline", str(input_file), str(output_file), "--config", str(config_path)],
        env=env,
    )
    assert result.returncode == 0, result.stderr

    metrics_path = output_file.with_suffix(output_file.suffix + ".json")
    metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = metrics_data.get("metrics", metrics_data)
    assert isinstance(metrics, dict)

    return output_file, metrics


@pytest.mark.usefixtures("mock_coverage_distribution")
def test_cli_pipeline_multi_oligo_illumina_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    multi_oligo_codec: str,
) -> None:
    original_simulate = IlluminaChannel._simulate_batch

    def _patched_simulate(self: IlluminaChannel, batch):  # type: ignore[override]
        result = original_simulate(self, batch)
        if hasattr(result, "oligos"):
            for source, mutated in zip(batch.oligos, result.oligos):
                flag = str(mutated.metadata.get(RESULT_DROPOUT_FLAG_KEY, "")).lower()
                if flag in {"true", "1", "yes"}:
                    mutated.sequence = source.sequence
            if result.oligos:
                mutated = result.oligos[0]
                mutated.metadata[RESULT_DROPOUT_FLAG_KEY] = "true"
                mutated.metadata[RESULT_COVERAGE_KEY] = "0"
        return result

    monkeypatch.setattr(IlluminaChannel, "_simulate_batch", _patched_simulate)

    output_file, metrics = _run_pipeline_with_config(
        tmp_path,
        config={
            "codec": multi_oligo_codec,
            "fec": "fountain",
            "channel": {
                "name": "illumina",
                "profile": "miseq",
                "coverage": 4,
                "dropout_rate": 0.0,
                "coverage_distribution": {"2": 1.0},
                "substitution_rate": 0.0,
                "insertion_rate": 0.0,
                "deletion_rate": 0.0,
            },
        },
        seed="424242",
        monkeypatch=monkeypatch,
    )

    dropout_count = metrics.get("dropout_count")
    assert isinstance(dropout_count, (int, float))

    channel_metrics = metrics.get("channel", {})
    assert isinstance(channel_metrics, dict)
    channel_dropout = channel_metrics.get("dropout", {})
    assert isinstance(channel_dropout, dict)
    assert channel_dropout.get("count") == dropout_count
    assert channel_dropout.get("fraction") is not None

    coverage_info = channel_metrics.get("coverage", {})
    assert isinstance(coverage_info, dict)
    coverage_hist = coverage_info.get("histogram")
    assert isinstance(coverage_hist, dict)
    assert coverage_hist
    assert all(isinstance(key, str) for key in coverage_hist)

    oligo_metrics = metrics.get("oligo_metrics", {})
    assert isinstance(oligo_metrics, dict)
    dropout_flags = oligo_metrics.get("dropout_flags")
    coverage_counts = oligo_metrics.get("coverage_counts")
    assert isinstance(dropout_flags, list)
    assert isinstance(coverage_counts, list)
    assert len(dropout_flags) == len(coverage_counts)
    assert len(dropout_flags) > 1

    ecc_rates = metrics.get("ecc_success_rates", {})
    assert isinstance(ecc_rates, dict)
    fountain_rate = ecc_rates.get("fountain")
    assert isinstance(fountain_rate, (int, float))
    assert 0.0 <= fountain_rate <= 1.0

    ecc_outcomes = oligo_metrics.get("ecc_success", {})
    assert isinstance(ecc_outcomes, dict)
    fountain_outcomes = ecc_outcomes.get("fountain")
    assert isinstance(fountain_outcomes, list)
    assert fountain_outcomes
    for value in fountain_outcomes:
        assert 0.0 <= value <= 1.0

    sequence_batch = metrics.get("sequence_batch", {})
    assert isinstance(sequence_batch, dict)
    metadata = sequence_batch.get("metadata", {})
    assert isinstance(metadata, dict)
    assert metadata.get("sim_dropout_total") == str(int(dropout_count))

    hist_meta = metadata.get("sim_coverage_histogram")
    assert isinstance(hist_meta, str)
    parsed_hist = json.loads(hist_meta)
    assert parsed_hist == coverage_hist

    assert output_file.read_bytes() == bytes(range(64)) * 4


@pytest.mark.usefixtures("mock_coverage_distribution")
def test_cli_pipeline_multi_oligo_nanopore_dropout_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    multi_oligo_codec: str,
) -> None:
    original_simulate = NanoporeChannel._simulate_batch

    def _patched_simulate(self: NanoporeChannel, batch):  # type: ignore[override]
        result = original_simulate(self, batch)
        if hasattr(result, "oligos"):
            for source, mutated in zip(batch.oligos, result.oligos):
                flag = str(mutated.metadata.get(RESULT_DROPOUT_FLAG_KEY, "")).lower()
                if flag in {"true", "1", "yes"}:
                    mutated.sequence = source.sequence
        return result

    monkeypatch.setattr(NanoporeChannel, "_simulate_batch", _patched_simulate)

    _output_file, metrics = _run_pipeline_with_config(
        tmp_path,
        config={
            "codec": multi_oligo_codec,
            "fec": "fountain",
            "channel": {
                "name": "nanopore",
                "profile": "r9.4",
                "dropout_rate": 1.0,
                "coverage_distribution": {"0": 1.0},
                "error_rate": 0.0,
                "substitution_rate": 0.0,
                "insertion_rate": 0.0,
                "deletion_rate": 0.0,
            },
        },
        seed="314159",
        monkeypatch=monkeypatch,
    )

    channel_metrics = metrics.get("channel", {})
    assert isinstance(channel_metrics, dict)

    dropout_info = channel_metrics.get("dropout", {})
    assert isinstance(dropout_info, dict)
    assert dropout_info.get("fraction") == pytest.approx(1.0)

    coverage_info = channel_metrics.get("coverage", {})
    assert isinstance(coverage_info, dict)
    histogram = coverage_info.get("histogram")
    assert isinstance(histogram, dict)

    oligo_metrics = metrics.get("oligo_metrics", {})
    assert isinstance(oligo_metrics, dict)
    dropout_flags = oligo_metrics.get("dropout_flags")
    coverage_counts = oligo_metrics.get("coverage_counts")
    assert isinstance(dropout_flags, list)
    assert isinstance(coverage_counts, list)
    assert dropout_flags
    assert all(dropout_flags)
    assert all(count == 0 for count in coverage_counts)

    assert set(histogram) == {"0"}
    assert histogram.get("0") == len(dropout_flags)

    dropout_count = metrics.get("dropout_count")
    assert isinstance(dropout_count, (int, float))
    assert int(dropout_count) == len(dropout_flags)

    sequence_batch = metrics.get("sequence_batch", {})
    assert isinstance(sequence_batch, dict)
    metadata = sequence_batch.get("metadata", {})
    assert isinstance(metadata, dict)
    dropout_fraction = metadata.get("sim_dropout_fraction")
    assert isinstance(dropout_fraction, str)
    assert float(dropout_fraction) == pytest.approx(1.0)

    hist_meta = metadata.get("sim_coverage_histogram")
    assert isinstance(hist_meta, str)
    parsed_hist = json.loads(hist_meta)
    assert parsed_hist.get("0") == len(dropout_flags)

    ecc_rates = metrics.get("ecc_success_rates", {})
    if isinstance(ecc_rates, dict) and "fountain" in ecc_rates:
        fountain_rate = ecc_rates["fountain"]
        assert isinstance(fountain_rate, (int, float))
        assert 0.0 <= fountain_rate <= 1.0

    ecc_outcomes = oligo_metrics.get("ecc_success", {})
    if isinstance(ecc_outcomes, dict) and "fountain" in ecc_outcomes:
        assert all(0.0 <= float(value) <= 1.0 for value in ecc_outcomes["fountain"])

