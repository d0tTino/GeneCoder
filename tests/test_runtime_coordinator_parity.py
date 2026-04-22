from __future__ import annotations

from genecoder.core import run_canonical_pipeline
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.runtime.models import DecodeStageInput, EncodeStageInput, SimulateStageInput
from genecoder.runtime.stages import DecodeStageService, EncodeStageService, SimulateStageService, batch_for_decode
from genecoder.sdk.plugins import Codec
from genecoder.simulators import SIMULATOR_REGISTRY


class _Base4Codec(Codec):
    def encode(self, data: bytes) -> str:  # type: ignore[override]
        from genecoder.encoders import encode_base4_direct

        return encode_base4_direct(data)  # type: ignore[return-value]

    def decode(self, encoded: str) -> bytes:  # type: ignore[override]
        from genecoder.encoders import decode_base4_direct

        return decode_base4_direct(encoded)[0]


def _register_test_plugins() -> None:
    init_plugins()
    CODEC_REGISTRY["base4"] = {"encode": _Base4Codec().encode, "decode": _Base4Codec().decode}
    SIMULATOR_REGISTRY["simple"] = type(SIMULATOR_REGISTRY["simple"])(error_rate=0.0)


def test_canonical_coordinator_parity_with_stages() -> None:
    _register_test_plugins()
    payload = b"coordinator parity"

    encode_out = EncodeStageService().run(EncodeStageInput(codec="base4", fec=None, data=payload))
    simulate_out = SimulateStageService().run(
        SimulateStageInput(channel="simple", dna=encode_out.encoded_batch)
    )
    decode_input = batch_for_decode(simulate_out.dna, filter_mutated=False)
    decode_out = DecodeStageService().run(
        DecodeStageInput(
            codec="base4",
            fec=None,
            dna=decode_input,
            fec_info=encode_out.fec_info,
            filter_mutated=False,
            survivor_batch=decode_input,
        )
    )

    coordinated = run_canonical_pipeline("base4", None, "simple", payload, filter_mutated=False)

    assert coordinated.decoded == decode_out.decoded
    assert coordinated.encoded_batch.combined_sequence() == encode_out.encoded_batch.combined_sequence()
    assert coordinated.simulated_batch.combined_sequence() == simulate_out.dna.combined_sequence()
