from pathlib import Path

import pytest

from genecoder.core import run_pipeline
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


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_pipeline_roundtrip_reed_solomon(tmp_path: Path) -> None:
    init_plugins()
    _register_base_codec()
    _setup_simple_channel(rate=0.1)

    data = b"pipeline RS"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result = run_pipeline("base4", "reed_solomon", "simple", str(inp), str(outp))
    assert result == data
    assert outp.read_bytes() == data


def test_pipeline_roundtrip_fountain(tmp_path: Path) -> None:
    pytest.importorskip("pyfinite")
    init_plugins()
    _register_base_codec()
    _setup_simple_channel(rate=0.1)

    data = b"pipeline fountain"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result = run_pipeline("base4", "fountain", "simple", str(inp), str(outp))
    assert result == data
    assert outp.read_bytes() == data


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

    result = run_pipeline(
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
    pytest.importorskip("pyfinite")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    _register_base_codec()

    data = b"pipeline fountain nanopore"
    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    result = run_pipeline(
        "base4",
        "fountain",
        "nanopore",
        str(inp),
        str(outp),
    )
    assert result == data
    assert outp.read_bytes() == data

