from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from genecoder.pipeline import run_pipeline
from genecoder import core
from genecoder.formats import SequenceBatch
from genecoder.plugin_manager import CODEC_REGISTRY, FEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.channel_sim import Channel
from genecoder.api import Codec
from genecoder.reed_solomon_codec import _HAS_REEDSOLO
from genecoder.random_utils import reset_rng


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
    _setup_simple_channel(rate=0.0 if fec_backend == "fountain" else 0.1)

    data = f"pipeline {fec_backend}".encode()
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    observed_batches: list[SequenceBatch | None] = []
    if fec_backend == "fountain":
        original_decode = FEC_REGISTRY["fountain"]["decode"]

        def _recording_decode(
            encoded: bytes,
            info: Mapping[str, Any],
            /,
            *,
            survivor_batch: SequenceBatch | None = None,
            **kwargs: object,
        ) -> tuple[bytes, int]:
            observed_batches.append(survivor_batch)
            return original_decode(
                encoded,
                info,
                survivor_batch=survivor_batch,
                **kwargs,
            )

        monkeypatch.setitem(FEC_REGISTRY["fountain"], "decode", _recording_decode)

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
    decode_input = simulated
    decoded_core = core.decode(
        "base4",
        fec_backend,
        decode_input,
        fec_info,
        survivor_batch=decode_input if isinstance(decode_input, SequenceBatch) else None,
    )
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
    if fec_backend == "fountain":
        assert observed_batches
        assert all(isinstance(batch, SequenceBatch) for batch in observed_batches if batch is not None)
        assert observed_batches[-1] is decode_input
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

    class _IdentitySimulator:
        __genecoder_accepts_batch__ = True

        def simulate(self, sequence: SequenceBatch | str) -> SequenceBatch | str:
            return sequence

    SIMULATOR_REGISTRY[channel_name] = _IdentitySimulator()

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

