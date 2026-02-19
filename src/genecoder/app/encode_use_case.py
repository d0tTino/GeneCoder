from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast
import base64
import json
import logging

from genecoder.encoders import encode_base4_direct, encode_gc_balanced, encode_triple_repeat
from genecoder.gc_balancer import AdvancedGCBalancer
from genecoder.hamming_codec import encode_data_with_hamming
from genecoder.huffman_coding import encode_huffman
from genecoder.options import EncodingOptions
from genecoder.plugin_manager import FEC_REGISTRY
from genecoder.utils import get_alphabet_maps

logger = logging.getLogger(__name__)

encrypt_data: Callable[..., bytes] | None = None
compute_checksum: Callable[[bytes], str] | None = None


def _ensure_security_loaded() -> None:
    global encrypt_data, compute_checksum
    if encrypt_data is None or compute_checksum is None:
        from genecoder.security import compute_checksum as _chk, encrypt_data as _enc

        encrypt_data = _enc
        compute_checksum = _chk


@dataclass(frozen=True)
class EncodeRequest:
    data: bytes
    options: EncodingOptions
    input_name: str = "input.bin"


@dataclass(frozen=True)
class EncodeResponse:
    sequence: str
    header: str
    raw_sequence: str
    transformed_input: bytes
    fec_padding_bits: int


class EncodeUseCase:
    """Transport-agnostic encode orchestration and validation."""

    def execute(self, request: EncodeRequest) -> EncodeResponse:
        _ensure_security_loaded()
        options = request.options
        current_input = request.data
        fec_padding_bits = -1
        encode_map, _ = get_alphabet_maps(options.alphabet)
        sanitized_name = Path(request.input_name.replace("\\", "/")).name
        header_parts = [f"method={options.method}", f"input_file={sanitized_name}"]

        if options.fec == "hamming_7_4":
            current_input, fec_padding_bits = encode_data_with_hamming(request.data)
            header_parts.extend(["fec=hamming_7_4", f"fec_padding_bits={fec_padding_bits}"])
        elif options.fec and options.fec in FEC_REGISTRY:
            enc = FEC_REGISTRY[options.fec]
            encode_kwargs: dict[str, object | None] = {}
            if options.fec == "reed_solomon":
                encode_kwargs = {
                    "symbol_size": options.rs_symbol_size,
                    "primitive": options.rs_primitive,
                }
            elif options.fec == "fountain":
                encode_kwargs = {
                    "chunk_size": options.fountain_chunk_size,
                    "redundancy": options.fountain_redundancy,
                    "manifest_path": options.fountain_manifest,
                }
            encode_kwargs = {k: v for k, v in encode_kwargs.items() if v is not None}
            current_input, info = enc["encode"](request.data, **encode_kwargs)
            header_parts.append(f"fec={options.fec}")
            if info is not None:
                encoded_info = base64.b64encode(json.dumps(info).encode()).decode()
                header_parts.append(f"fec_info={encoded_info}")

        should_add_parity = options.add_parity and (options.fec is None or options.fec not in {"hamming_7_4", *FEC_REGISTRY.keys()})

        if options.method == "base4_direct":
            raw_dna = cast(
                str,
                encode_base4_direct(
                    current_input,
                    add_parity=should_add_parity,
                    k_value=options.k_value,
                    parity_rule=options.parity_rule,
                    encode_map=encode_map,
                    stream=False,
                ),
            )
        elif options.method == "huffman":
            raw_dna, huffman_table, num_padding_bits = encode_huffman(
                current_input,
                add_parity=should_add_parity,
                k_value=options.k_value,
                parity_rule=options.parity_rule,
                encode_map=encode_map,
            )
            huffman_params = {"table": {str(k): v for k, v in huffman_table.items()}, "padding": num_padding_bits}
            header_parts.append(f"huffman_params={json.dumps(huffman_params)}")
        elif options.method == "gc_balanced":
            raw_dna = encode_gc_balanced(current_input, options.gc_min, options.gc_max, options.max_homopolymer)
            header_parts.extend([f"gc_min={options.gc_min}", f"gc_max={options.gc_max}", f"max_homopolymer={options.max_homopolymer}"])
        elif options.method == "gc_balanced_advanced":
            raw_dna = AdvancedGCBalancer(options.gc_min, options.gc_max, options.max_homopolymer).encode(current_input)
            header_parts.extend([f"gc_min={options.gc_min}", f"gc_max={options.gc_max}", f"max_homopolymer={options.max_homopolymer}"])
        else:
            raise ValueError(f"Unknown encoding method '{options.method}'.")

        final_dna = encode_triple_repeat(raw_dna) if options.fec == "triple_repeat" else raw_dna
        if options.fec and options.fec not in {"triple_repeat", "hamming_7_4", *FEC_REGISTRY.keys()}:
            logger.warning("Unknown FEC method '%s'. No DNA-level FEC applied.", options.fec)
        if should_add_parity:
            header_parts.extend([f"parity_k={options.k_value}", f"parity_rule={options.parity_rule}"])
        if options.fec == "triple_repeat":
            header_parts.append("fec=triple_repeat")

        return EncodeResponse(
            sequence=final_dna,
            header=" ".join(header_parts),
            raw_sequence=raw_dna,
            transformed_input=current_input,
            fec_padding_bits=fec_padding_bits,
        )
