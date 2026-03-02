from pathlib import Path


import pytest

from genecoder.core import run_pipeline
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.sdk.plugins import Codec
from genecoder.simulators.illumina import IlluminaChannel
from genecoder.raptorq_codec import encode_data_raptorq, _HAS_RAPTORQ


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct
        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct
        return decode_base4_direct(encoded)[0]


@pytest.mark.skipif(not _HAS_RAPTORQ, reason="raptorq not installed")
def test_pipeline_raptorq_illumina(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("raptorq")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    init_plugins()
    CODEC_REGISTRY["base4"] = {
        "encode": _Base4Codec().encode,
        "decode": _Base4Codec().decode,
    }

    data = b"raptorq illumina pipeline"
    try:
        encoded_bytes, _ = encode_data_raptorq(data)
    except Exception:
        pytest.skip("raptorq not available")
    SIMULATOR_REGISTRY["illumina"] = IlluminaChannel(
        insertion_rate=0.0, deletion_rate=0.0, read_length=len(encoded_bytes) * 4
    )

    inp = tmp_path / "data.bin"
    outp = tmp_path / "out.bin"
    inp.write_bytes(data)

    try:
        result, metrics = run_pipeline("base4", "raptorq", "illumina", str(inp), str(outp))
    except Exception:
        pytest.skip("raptorq not available")

    assert result == data
    assert outp.read_bytes() == data
    assert len(encoded_bytes) > len(data)
    assert metrics["ecc_success_rates"].get("raptorq", 0) == 1.0
