from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, cast

import pytest
import genecoder.simulators.nanopore as nanopore
import genecoder.simulators.nanopore_external as nanopore_external

from genecoder.sdk.plugins import Codec, FEC
from genecoder.core import run_pipeline
from genecoder.fountain_codec import FountainFEC
from genecoder.plugin_manager import (
    CODEC_REGISTRY,
    init_plugins,
    register_fec,
    register_simulator,
)
from genecoder.reed_solomon_codec import ReedSolomonFEC, _HAS_REEDSOLO
from genecoder.simulators.illumina import IlluminaChannel


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct

        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct

        return decode_base4_direct(encoded)[0]


class _CombinedFountainRSFEC(FEC):
    """Apply Fountain FEC followed by Reed--Solomon protection."""

    def __init__(self) -> None:
        self._fountain = FountainFEC()
        self._reed_solomon = ReedSolomonFEC()

    def encode(
        self, data: bytes, /, **kwargs: object
    ) -> tuple[bytes, Mapping[str, Any]]:
        fountain_payload, fountain_info = self._fountain.encode(data)
        rs_payload, rs_info = self._reed_solomon.encode(fountain_payload)
        return rs_payload, {"fountain": fountain_info, "reed_solomon": rs_info}

    def decode(
        self, encoded: bytes, info: Mapping[str, Any], /, **kwargs: object
    ) -> tuple[bytes, int]:
        fountain_info = cast(Mapping[str, Any], info["fountain"])
        rs_info = cast(Mapping[str, Any], info["reed_solomon"])
        fountain_encoded, rs_corrections = self._reed_solomon.decode(encoded, rs_info)
        decoded, fountain_corrections = self._fountain.decode(
            fountain_encoded, fountain_info
        )
        return decoded, rs_corrections + fountain_corrections


@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_combined_fec_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")

    def fallback(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("fallback")

    monkeypatch.setattr(nanopore_external, "run_dnarsim_cli", fallback)
    monkeypatch.setattr(nanopore, "run_dnarsim_cli", fallback)

    init_plugins()
    CODEC_REGISTRY["base4"] = {
        "encode": _Base4Codec().encode,
        "decode": _Base4Codec().decode,
    }

    fec_name = "combined_fountain_rs"
    data = b"combined fec payload"

    sizing_fec = _CombinedFountainRSFEC()
    encoded_payload, _ = sizing_fec.encode(data)
    encoded_dna = _Base4Codec().encode(encoded_payload)
    read_length = ((len(encoded_dna) + 3) // 4) * 4

    register_fec(fec_name, _CombinedFountainRSFEC())
    register_simulator(
        "combined_illumina",
        IlluminaChannel(
            substitution_rate=0.0,
            insertion_rate=0.0,
            deletion_rate=0.0,
            coverage=1.0,
            read_length=read_length,
        ),
    )
    register_simulator(
        "combined_nanopore",
        nanopore.NanoporeChannel(
            error_rate=0.0,
            substitution_rate=0.0,
            insertion_rate=0.0,
            deletion_rate=0.0,
        ),
    )

    inp = tmp_path / "data.bin"
    inp.write_bytes(data)

    ecc_success_rates: dict[str, float] = {}

    for channel_name in ("combined_illumina", "combined_nanopore"):
        outp = tmp_path / f"{channel_name}.bin"
        result, metrics = run_pipeline(
            "base4", fec_name, channel_name, str(inp), str(outp)
        )

        assert result == data
        assert outp.read_bytes() == data

        ecc_rates = metrics.get("ecc_success_rates")
        assert isinstance(ecc_rates, dict)
        ecc_success_rates[channel_name] = ecc_rates.get(fec_name, 0.0)

    assert set(ecc_success_rates) == {"combined_illumina", "combined_nanopore"}
    for rate in ecc_success_rates.values():
        assert rate == pytest.approx(1.0)
