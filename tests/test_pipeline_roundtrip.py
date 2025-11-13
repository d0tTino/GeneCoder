from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Sequence

import pytest

from genecoder.pipeline import run_pipeline
from genecoder import core
from genecoder.formats import SequenceBatch
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.channel_sim import Channel
from genecoder.api import Codec
from genecoder.reed_solomon_codec import _HAS_REEDSOLO
from genecoder.random_utils import reset_rng
from genecoder.simulators.batch_utils import RESULT_COVERAGE_KEY, RESULT_DROPOUT_FLAG_KEY


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


def _register_base_codec() -> None:
    CODEC_REGISTRY["base4"] = {
        "encode": _Base4Codec().encode,
        "decode": _Base4Codec().decode,
    }


def _setup_simple_channel(rate: float) -> None:
    existing = SIMULATOR_REGISTRY.get("simple")
    if existing is None:
        SIMULATOR_REGISTRY["simple"] = Channel(error_rate=rate)
        return
    SIMULATOR_REGISTRY["simple"] = type(existing)(error_rate=rate)


@pytest.mark.parametrize("fec_backend", ["reed_solomon", "fountain"])
def test_pipeline_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fec_backend: str
) -> None:
    if fec_backend == "reed_solomon" and not _HAS_REEDSOLO:
        pytest.skip("reedsolo not installed")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    _register_base_codec()
    _setup_simple_channel(rate=0.0)

    data = f"pipeline {fec_backend}".encode()
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, metrics, info = run_pipeline("base4", fec_backend, "simple", str(inp), str(outp))
    assert result == data
    assert metrics["gc_content"] >= 0.0
    assert outp.read_bytes() == data
    assert info is not None
    assert "batch_metadata" in info
    if fec_backend == "reed_solomon":
        assert "nsym" in info
        assert info["batch_metadata"]["batch_id"].startswith("base4")
    else:
        assert "seed" in info
        assert "chunk_size" in info
        assert info["batch_metadata"]["batch_id"].startswith("base4")
    assert len(metrics["oligo_metrics"]["dropout_flags"]) >= 1

    reset_rng()
    dna_batch, fec_info = core.encode("base4", fec_backend, data)
    simulated, subs, ins, dels, coverage = core.simulate("simple", dna_batch)
    if not isinstance(simulated, SequenceBatch):
        simulated = SequenceBatch.build(
            [
                (
                    dna_batch.first_header() or "batch_id=test oligo_index=1",
                    simulated if isinstance(simulated, str) else str(simulated),
                )
            ],
            batch_id=dna_batch.batch_id,
        )
    assert isinstance(simulated, SequenceBatch)
    decoded_core = core.decode("base4", fec_backend, simulated, fec_info)
    metrics_core = core.metrics(
        simulated,
        data,
        decoded_core,
        fec_backend,
        subs,
        ins,
        dels,
        coverage,
    )
    assert decoded_core == data
    assert metrics_core == metrics


def test_fountain_pipeline_invokes_channel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    _register_base_codec()
    _setup_simple_channel(rate=0.0)

    channel = SIMULATOR_REGISTRY["simple"]
    calls: list[SequenceBatch | str] = []

    original_simulate = channel.simulate

    def _recording_simulate(sequence: SequenceBatch | str) -> SequenceBatch | str:
        calls.append(sequence)
        return original_simulate(sequence)

    monkeypatch.setattr(channel, "simulate", _recording_simulate)

    data = b"fountain channel invocation"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, _, _ = run_pipeline("base4", "fountain", "simple", str(inp), str(outp))

    assert result == data
    assert outp.read_bytes() == data
    assert calls
    assert all(isinstance(item, SequenceBatch) for item in calls)


def _build_base_batch() -> SequenceBatch:
    return SequenceBatch.build(
        [
            (">fountain oligo 1", "AAAA"),
            (">fountain oligo 2", "CCCC"),
            (">fountain oligo 3", "GGGG"),
        ],
        batch_id="fountain-test",
    )


def _apply_dropout(
    batch: SequenceBatch,
    *,
    flags: Sequence[bool],
    coverage: Sequence[int | None],
    sequences: Sequence[str],
) -> SequenceBatch:
    mutated = SequenceBatch(
        batch_id=batch.batch_id,
        metadata=dict(batch.metadata),
        seed=batch.seed,
        oligos=[],
    )
    for oligo, dropped, cov, seq in zip(batch.oligos, flags, coverage, sequences):
        metadata = dict(oligo.metadata)
        metadata[RESULT_DROPOUT_FLAG_KEY] = "true" if dropped else "false"
        if cov is not None:
            metadata[RESULT_COVERAGE_KEY] = str(cov)
        elif RESULT_COVERAGE_KEY in metadata:
            metadata.pop(RESULT_COVERAGE_KEY)
        mutated.oligos.append(
            replace(
                oligo,
                sequence=seq,
                metadata=metadata,
            )
        )
    return mutated


def test_fountain_channel_dropout_manifest_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("genecoder.pipeline.init_plugins", lambda: None)

    original_batch = _build_base_batch()
    mutated_batch = _apply_dropout(
        original_batch,
        flags=[False, True, False],
        coverage=[8, 0, 6],
        sequences=["AAAT", "", "GGGT"],
    )
    fec_info: dict[str, object] = {
        "batch_metadata": dict(original_batch.metadata),
        "seed": 17,
        "chunk_size": 4,
    }

    monkeypatch.setattr(
        core,
        "encode",
        lambda codec, fec, data: (original_batch, fec_info),
    )
    monkeypatch.setattr(
        core,
        "simulate",
        lambda channel_name, batch: (mutated_batch, 1, 0, 0, 5),
    )

    decode_calls: list[SequenceBatch] = []

    def _fake_decode(
        codec: str, fec_backend: str | None, dna: SequenceBatch, info: dict[str, object]
    ) -> bytes:
        decode_calls.append(dna)
        assert dna is mutated_batch
        assert info is fec_info
        return b"dropout-success"

    monkeypatch.setattr(core, "decode", _fake_decode)

    data = b"dropout-success"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, metrics, info = run_pipeline(
        "base4", "fountain", "simple", str(inp), str(outp)
    )

    assert decode_calls == [mutated_batch]
    assert result == data
    assert outp.read_bytes() == data

    dropout_flags = metrics["oligo_metrics"]["dropout_flags"]
    assert dropout_flags == [False, True, False]
    assert metrics["decode_success_rate"] == pytest.approx(1.0)

    assert info is fec_info
    channel_info = info.get("channel", {})
    assert channel_info.get("decode_success") is True
    assert channel_info.get("status") == "success"
    dropout_info = channel_info.get("dropout", {})
    assert dropout_info.get("count") == 1
    assert dropout_info.get("fraction") == pytest.approx(1 / 3)
    assert channel_info.get("oligo_count") == len(mutated_batch.primary_oligos())


def test_fountain_channel_dropout_manifest_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("genecoder.pipeline.init_plugins", lambda: None)

    original_batch = _build_base_batch()
    mutated_batch = _apply_dropout(
        original_batch,
        flags=[True, True, False],
        coverage=[0, 0, 3],
        sequences=["", "", "GGGA"],
    )
    fec_info: dict[str, object] = {
        "batch_metadata": dict(original_batch.metadata),
        "seed": 42,
        "chunk_size": 4,
    }

    monkeypatch.setattr(
        core,
        "encode",
        lambda codec, fec, data: (original_batch, fec_info),
    )
    monkeypatch.setattr(
        core,
        "simulate",
        lambda channel_name, batch: (mutated_batch, 0, 0, 0, 2),
    )

    decode_calls: list[SequenceBatch] = []

    def _failing_decode(
        codec: str, fec_backend: str | None, dna: SequenceBatch, info: dict[str, object]
    ) -> bytes:
        decode_calls.append(dna)
        assert dna is mutated_batch
        assert info is fec_info
        return b"corrupted-output"

    monkeypatch.setattr(core, "decode", _failing_decode)

    data = b"expected-but-lost"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, metrics, info = run_pipeline(
        "base4", "fountain", "simple", str(inp), str(outp)
    )

    assert decode_calls == [mutated_batch]
    assert result == b"corrupted-output"
    assert outp.read_bytes() == b"corrupted-output"

    dropout_flags = metrics["oligo_metrics"]["dropout_flags"]
    assert dropout_flags == [True, True, False]
    assert metrics["decode_success_rate"] == pytest.approx(0.0)

    assert info is fec_info
    channel_info = info.get("channel", {})
    assert channel_info.get("decode_success") is False
    assert channel_info.get("status") == "failed"
    dropout_info = channel_info.get("dropout", {})
    assert dropout_info.get("count") == 2
    assert dropout_info.get("fraction") == pytest.approx(2 / 3)
    assert channel_info.get("oligo_count") == len(mutated_batch.primary_oligos())


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_pipeline_roundtrip_rs_illumina(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    _register_base_codec()

    data = b"pipeline RS illumina"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, _, _ = run_pipeline(
        "base4",
        "reed_solomon",
        "illumina",
        str(inp),
        str(outp),
    )
    assert result == data
    assert outp.read_bytes() == data


@pytest.mark.parametrize("channel_name", ["nanopore", "illumina"])
def test_pipeline_roundtrip_fountain_channels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, channel_name: str
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    _register_base_codec()

    def _deterministic_simulate(channel_id: str | None, batch: SequenceBatch):
        mutated = SequenceBatch(
            batch_id=batch.batch_id,
            metadata=dict(batch.metadata),
            seed=batch.seed,
            oligos=[
                replace(
                    ol,
                    metadata={
                        **dict(ol.metadata),
                        RESULT_COVERAGE_KEY: "5",
                    },
                )
                for ol in batch.oligos
            ],
        )
        return mutated, 0, 0, 0, 5

    monkeypatch.setattr(core, "simulate", _deterministic_simulate)

    data = f"pipeline fountain {channel_name}".encode()
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, metrics, _ = run_pipeline(
        "base4",
        "fountain",
        channel_name,
        str(inp),
        str(outp),
    )
    assert result == data
    assert outp.read_bytes() == data
    coverage = metrics["oligo_metrics"]["coverage"]
    assert len(coverage) >= 1
    assert all(value is None or isinstance(value, int) for value in coverage)

