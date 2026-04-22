from __future__ import annotations

from genecoder.formats import SequenceBatch
from genecoder.plugin_manager import CODEC_REGISTRY, init_plugins
from genecoder.runtime.models import DecodeStageInput, EncodeStageInput, SimulateStageInput
from genecoder.runtime.stages.decode import DecodeStageService
from genecoder.runtime.stages.encode import EncodeStageService
from genecoder.runtime.stages.simulate import SimulateStageService, batch_for_decode
from genecoder.sdk.plugins import Codec
from genecoder.simulators import SIMULATOR_REGISTRY
from genecoder.simulators.batch_utils import RESULT_DROPOUT_FLAG_KEY


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


def test_encode_stage_service_roundtrip_payload() -> None:
    _register_test_plugins()
    service = EncodeStageService()
    result = service.run(EncodeStageInput(codec="base4", fec=None, data=b"payload"))
    assert isinstance(result.encoded_batch, SequenceBatch)
    assert result.encoded_batch.primary_sequence()


def test_simulate_stage_service_passthrough_none_channel() -> None:
    service = SimulateStageService()
    result = service.run(SimulateStageInput(channel=None, dna="ACGT"))
    assert result.dna == "ACGT"
    assert result.substitutions is None
    assert result.coverage is None


def test_decode_stage_service_roundtrip() -> None:
    _register_test_plugins()
    encode_result = EncodeStageService().run(EncodeStageInput(codec="base4", fec=None, data=b"decode me"))
    decode_result = DecodeStageService().run(
        DecodeStageInput(
            codec="base4",
            fec=None,
            dna=encode_result.encoded_batch,
            fec_info=encode_result.fec_info,
        )
    )
    assert decode_result.decoded == b"decode me"


def test_batch_for_decode_filters_dropout() -> None:
    batch = SequenceBatch.build(
        [
            ("batch_id=test oligo_index=1", "ACGT"),
            ("batch_id=test oligo_index=2", "TGCA"),
        ],
        batch_id="test",
    )
    batch.oligos[1].metadata[RESULT_DROPOUT_FLAG_KEY] = True
    filtered = batch_for_decode(batch, filter_mutated=False)
    assert len(filtered.oligos) == 1
