from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from genecoder.encoders import (
    calculate_gc_content,
    decode_base4_direct,
    decode_gc_balanced,
    decode_triple_repeat,
    encode_base4_direct,
    encode_gc_balanced,
    encode_triple_repeat,
    get_max_homopolymer_length,
)
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.hamming_codec import decode_data_with_hamming, encode_data_with_hamming
from genecoder.huffman_coding import decode_huffman, encode_huffman


@dataclass(slots=True)
class EncodeRequest:
    data: bytes
    method: str
    add_parity: bool = False
    k_value: int = 7
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T
    pre_transform: Optional[str] = None
    channel: Optional[str] = None


@dataclass(slots=True)
class DecodeRequest:
    dna_sequence: str
    method: str
    check_parity: bool = False
    k_value: int = 7
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T
    pre_transform: Optional[str] = None
    channel: Optional[str] = None
    huffman_table: Optional[dict[int, str]] = None
    huffman_padding: int = 0
    gc_min: Optional[float] = None
    gc_max: Optional[float] = None
    max_homopolymer: Optional[int] = None
    pre_transform_padding_bits: int = 0


@dataclass(slots=True)
class SimulationResult:
    input_bytes: bytes = b""
    transformed_bytes: bytes = b""
    decoded_bytes: bytes = b""
    encoded_dna: str = ""
    channel_output_dna: str = ""
    parity_errors: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


StageHandler = Callable[[Any, SimulationResult], None]


class StageRegistry:
    def __init__(self) -> None:
        self.pre_transform_encode: Dict[str, StageHandler] = {"none": _encode_noop, "hamming_7_4": _encode_hamming_7_4}
        self.pre_transform_decode: Dict[str, StageHandler] = {"none": _decode_noop, "hamming_7_4": _decode_hamming_7_4}
        self.encoder: Dict[str, StageHandler] = {
            "base4_direct": _encode_base4_direct,
            "huffman": _encode_huffman,
            "gc_balanced": _encode_gc_balanced,
        }
        self.decoder: Dict[str, StageHandler] = {
            "base4_direct": _decode_base4_direct,
            "huffman": _decode_huffman,
            "gc_balanced": _decode_gc_balanced,
        }
        self.channel_encode: Dict[str, StageHandler] = {"none": _channel_noop, "triple_repeat": _channel_triple_repeat_encode}
        self.channel_decode: Dict[str, StageHandler] = {"none": _channel_noop, "triple_repeat": _channel_triple_repeat_decode}
        self.metrics: Dict[str, StageHandler] = {"default": _compute_metrics}


class GeneCoderPipeline:
    def __init__(self, registry: Optional[StageRegistry] = None) -> None:
        self.registry = registry or StageRegistry()

    def run_encode(self, request: EncodeRequest) -> SimulationResult:
        result = SimulationResult(input_bytes=request.data, transformed_bytes=request.data)
        pre = request.pre_transform or "none"
        channel = request.channel or "none"
        self.registry.pre_transform_encode[pre](request, result)
        self.registry.encoder[request.method](request, result)
        self.registry.channel_encode[channel](request, result)
        self.registry.metrics["default"](request, result)
        return result

    def run_decode(self, request: DecodeRequest) -> SimulationResult:
        result = SimulationResult(channel_output_dna=request.dna_sequence, encoded_dna=request.dna_sequence)
        pre = request.pre_transform or "none"
        channel = request.channel or "none"
        self.registry.channel_decode[channel](request, result)
        self.registry.decoder[request.method](request, result)
        self.registry.pre_transform_decode[pre](request, result)
        self.registry.metrics["default"](request, result)
        return result


def _encode_noop(_request: EncodeRequest, result: SimulationResult) -> None:
    result.metadata["pre_transform"] = "none"


def _decode_noop(_request: DecodeRequest, result: SimulationResult) -> None:
    result.metadata["pre_transform"] = "none"
    result.decoded_bytes = result.transformed_bytes


def _encode_hamming_7_4(_request: EncodeRequest, result: SimulationResult) -> None:
    transformed, padding = encode_data_with_hamming(result.input_bytes)
    result.transformed_bytes = transformed
    result.metadata["pre_transform"] = "hamming_7_4"
    result.metadata["pre_transform_padding_bits"] = padding


def _decode_hamming_7_4(request: DecodeRequest, result: SimulationResult) -> None:
    decoded, corrected = decode_data_with_hamming(result.transformed_bytes, request.pre_transform_padding_bits)
    result.decoded_bytes = decoded
    result.metadata["pre_transform"] = "hamming_7_4"
    result.metadata["hamming_corrected"] = corrected


def _encode_base4_direct(request: EncodeRequest, result: SimulationResult) -> None:
    result.encoded_dna = encode_base4_direct(result.transformed_bytes, request.add_parity, request.k_value, request.parity_rule)


def _decode_base4_direct(request: DecodeRequest, result: SimulationResult) -> None:
    decoded, parity_errors = decode_base4_direct(result.encoded_dna, request.check_parity, request.k_value, request.parity_rule)
    result.transformed_bytes = decoded
    result.parity_errors = parity_errors


def _encode_huffman(request: EncodeRequest, result: SimulationResult) -> None:
    dna, table, padding = encode_huffman(result.transformed_bytes, request.add_parity, request.k_value, request.parity_rule)
    result.encoded_dna = dna
    result.metadata["huffman_table"] = table
    result.metadata["huffman_padding"] = padding


def _decode_huffman(request: DecodeRequest, result: SimulationResult) -> None:
    if request.huffman_table is None:
        raise ValueError("Huffman table is required for huffman decode stage.")
    decoded, parity_errors = decode_huffman(
        result.encoded_dna,
        request.huffman_table,
        request.huffman_padding,
        request.check_parity,
        request.k_value,
        request.parity_rule,
    )
    result.transformed_bytes = decoded
    result.parity_errors = parity_errors


def _encode_gc_balanced(_request: EncodeRequest, result: SimulationResult) -> None:
    result.metadata["gc_min"] = 0.45
    result.metadata["gc_max"] = 0.55
    result.metadata["max_homopolymer"] = 3
    result.encoded_dna = encode_gc_balanced(result.transformed_bytes, 0.45, 0.55, 3)


def _decode_gc_balanced(request: DecodeRequest, result: SimulationResult) -> None:
    result.transformed_bytes = decode_gc_balanced(
        result.encoded_dna,
        expected_gc_min=request.gc_min,
        expected_gc_max=request.gc_max,
        expected_max_homopolymer=request.max_homopolymer,
    )


def _channel_noop(_request: Any, result: SimulationResult) -> None:
    if result.encoded_dna and not result.channel_output_dna:
        result.channel_output_dna = result.encoded_dna
    elif result.channel_output_dna and not result.encoded_dna:
        result.encoded_dna = result.channel_output_dna


def _channel_triple_repeat_encode(_request: EncodeRequest, result: SimulationResult) -> None:
    result.channel_output_dna = encode_triple_repeat(result.encoded_dna)
    result.metadata["channel"] = "triple_repeat"


def _channel_triple_repeat_decode(_request: DecodeRequest, result: SimulationResult) -> None:
    decoded_dna, corrected, uncorrectable = decode_triple_repeat(result.channel_output_dna)
    result.encoded_dna = decoded_dna
    result.metadata["channel"] = "triple_repeat"
    result.metadata["channel_corrected"] = corrected
    result.metadata["channel_uncorrectable"] = uncorrectable


def _compute_metrics(_request: Any, result: SimulationResult) -> None:
    dna = result.channel_output_dna or result.encoded_dna
    result.metrics["input_bytes"] = float(len(result.input_bytes or result.transformed_bytes or result.decoded_bytes))
    result.metrics["dna_length"] = float(len(dna))
    if len(dna) > 0 and len(result.input_bytes) > 0:
        result.metrics["bits_per_nt"] = (len(result.input_bytes) * 8) / len(dna)
    if len(result.input_bytes) > 0:
        result.metrics["compression_ratio"] = len(dna) / len(result.input_bytes) if dna else 0.0
    if dna:
        payload = dna[1:] if _request.method == "gc_balanced" and len(dna) > 0 else dna
        result.metrics["gc_content"] = calculate_gc_content(payload)
        result.metrics["max_homopolymer"] = float(get_max_homopolymer_length(payload))
