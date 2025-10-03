from pathlib import Path

import pytest

from genecoder.pipeline import run_pipeline
from genecoder import core
from genecoder.formats import SequenceBatch
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.channel_sim import Channel
from genecoder.api import Codec
from genecoder.reed_solomon_codec import _HAS_REEDSOLO


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
    SIMULATOR_REGISTRY["simple"] = Channel(error_rate=rate)


@pytest.mark.parametrize("fec_backend", ["reed_solomon", "fountain"])
def test_pipeline_roundtrip(tmp_path: Path, fec_backend: str) -> None:
    if fec_backend == "reed_solomon" and not _HAS_REEDSOLO:
        pytest.skip("reedsolo not installed")
    init_plugins()
    _register_base_codec()
    _setup_simple_channel(rate=0.1)

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

    dna_batch, fec_info = core.encode("base4", fec_backend, data)
    selected_channel = "simple"
    if fec_backend == "fountain":
        selected_channel = None
    simulated, subs, ins, dels, coverage = core.simulate(selected_channel, dna_batch)
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


def test_pipeline_roundtrip_fountain_nanopore(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    _register_base_codec()

    data = b"pipeline fountain nanopore"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result, _, _ = run_pipeline(
        "base4",
        "fountain",
        "nanopore",
        str(inp),
        str(outp),
    )
    assert result == data
    assert outp.read_bytes() == data

