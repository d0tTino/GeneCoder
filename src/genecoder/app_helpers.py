from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple, cast

from .encoders import (
    encode_base4_direct,
    decode_base4_direct,
    encode_gc_balanced,
    decode_gc_balanced,
    calculate_gc_content,
)
from .utils import get_max_homopolymer_length
from .encoders import encode_triple_repeat, decode_triple_repeat
from .hamming_codec import encode_data_with_hamming, decode_data_with_hamming
from .huffman_coding import encode_huffman, decode_huffman
from .formats import to_fasta, from_fasta
from .error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from .reed_solomon_codec import encode_data_rs, decode_data_rs
from .plotting import (
    prepare_huffman_codeword_length_data,
    generate_codeword_length_histogram,
    prepare_nucleotide_frequency_data,
    generate_nucleotide_frequency_plot,
    calculate_windowed_gc_content,
    identify_homopolymer_regions,
    generate_sequence_analysis_plot,
)

import base64
import json
import re


@dataclass
class EncodeOptions:
    method: str
    add_parity: bool = False
    k_value: int = 7
    fec_method: str = "None"  # "None", "Triple-Repeat", "Hamming(7,4)"
    gc_min: float = 0.45
    gc_max: float = 0.55
    max_homopolymer: int = 3
    window_size: int = 50
    step_size: int = 10
    min_homopolymer_len: int = 4


@dataclass
class EncodeResult:
    fasta: str
    encoded_dna: str
    metrics: Dict[str, float]
    info_messages: List[str]
    huffman_table: Optional[Dict[int, str]] = None
    plots: Dict[str, Optional[str]] | None = None


@dataclass
class DecodeResult:
    decoded_bytes: bytes
    status_message: str
    fec_info: Optional[str] = None


def perform_encoding(data: bytes, options: EncodeOptions) -> EncodeResult:
    info_msgs: List[str] = []
    current_input = data
    fec_padding_bits = 0
    if options.fec_method == "Hamming(7,4)":
        if options.add_parity:
            info_msgs.append(
                "Info: 'Add Parity' ignored when Hamming(7,4) FEC selected."\
            )
        current_input, fec_padding_bits = encode_data_with_hamming(data)
    elif options.fec_method == "Reed-Solomon":
        if options.add_parity:
            info_msgs.append("Info: 'Add Parity' ignored when Reed-Solomon FEC selected.")
        current_input, rs_nsym = encode_data_rs(data)

    should_add_parity = options.add_parity and options.fec_method not in ("Hamming(7,4)", "Reed-Solomon")

    raw_dna = ""
    huffman_table: Optional[Dict[int, str]] = None
    num_padding_bits = 0
    method = options.method
    if method == "Base-4 Direct":
        raw_dna = cast(str, encode_base4_direct(
            current_input,
            should_add_parity,
            options.k_value,
            PARITY_RULE_GC_EVEN_A_ODD_T,
        ))
    elif method == "Huffman":
        raw_dna, huffman_table, num_padding_bits = encode_huffman(
            current_input,
            should_add_parity,
            options.k_value,
            PARITY_RULE_GC_EVEN_A_ODD_T,
        )
    elif method == "GC-Balanced":
        raw_dna = encode_gc_balanced(
            current_input,
            options.gc_min,
            options.gc_max,
            options.max_homopolymer,
        )
    else:
        raise ValueError(f"Unknown method '{method}'")

    final_dna = raw_dna
    if options.fec_method == "Triple-Repeat":
        final_dna = encode_triple_repeat(raw_dna)
        info_msgs.append("Triple-Repeat FEC applied.")
    elif options.fec_method == "Hamming(7,4)":
        info_msgs.append("Hamming(7,4) FEC applied.")
    elif options.fec_method == "Reed-Solomon":
        info_msgs.append("Reed-Solomon FEC applied.")

    header_parts = [
        f"method={method.lower().replace(' ', '_').replace('-', '_')}",
        "input_file=gui_input",
    ]
    if should_add_parity and method != "GC-Balanced":
        header_parts.extend(
            [f"parity_k={options.k_value}", f"parity_rule={PARITY_RULE_GC_EVEN_A_ODD_T}"]
        )
    if method == "Huffman" and huffman_table:
        serializable = {str(k): v for k, v in huffman_table.items()}
        params = {"table": serializable, "padding": num_padding_bits}
        header_parts.append(f"huffman_params={json.dumps(params)}")
    elif method == "GC-Balanced":
        header_parts.extend([
            f"gc_min={options.gc_min}",
            f"gc_max={options.gc_max}",
            f"max_homopolymer={options.max_homopolymer}",
        ])
    if options.fec_method == "Triple-Repeat":
        header_parts.append("fec=triple_repeat")
    elif options.fec_method == "Hamming(7,4)":
        header_parts.append("fec=hamming_7_4")
        header_parts.append(f"fec_padding_bits={fec_padding_bits}")
    elif options.fec_method == "Reed-Solomon":
        header_parts.append("fec=reed_solomon")
        header_parts.append(f"fec_nsym={rs_nsym}")

    fasta_header = " ".join(header_parts)
    fasta_str = to_fasta(final_dna, fasta_header, 80)

    original_size = len(data)
    final_len = len(final_dna)
    dna_bytes = final_len * 0.25
    compression_ratio = (
        original_size / dna_bytes if dna_bytes > 0 else (float("inf") if original_size > 0 else 0.0)
    )
    bits_per_nt = (original_size * 8) / final_len if final_len else 0.0

    metrics = {
        "original_size": original_size,
        "dna_length": final_len,
        "compression_ratio": compression_ratio,
        "bits_per_nt": bits_per_nt,
    }

    if method == "GC-Balanced":
        payload = raw_dna[1:] if raw_dna else ""
        metrics["actual_gc"] = calculate_gc_content(payload)
        metrics["max_homopolymer"] = get_max_homopolymer_length(payload)

    plots: Dict[str, Optional[str]] = {"codeword_hist": None, "nucleotide_freq": None, "sequence_analysis": None}
    if method == "Huffman" and huffman_table:
        length_counts = prepare_huffman_codeword_length_data(huffman_table)
        if any(length_counts.values()):
            buf = generate_codeword_length_histogram(length_counts)
            plots["codeword_hist"] = base64.b64encode(buf.getvalue()).decode("utf-8")
            buf.close()
    nucleotide_counts = prepare_nucleotide_frequency_data(final_dna)
    if any(nucleotide_counts.values()):
        buf = generate_nucleotide_frequency_plot(nucleotide_counts)
        plots["nucleotide_freq"] = base64.b64encode(buf.getvalue()).decode("utf-8")
        buf.close()

    gc_data = calculate_windowed_gc_content(final_dna, options.window_size, options.step_size)
    hp_data = identify_homopolymer_regions(final_dna, options.min_homopolymer_len)
    if (gc_data and gc_data[0]) or hp_data:
        buf = generate_sequence_analysis_plot(gc_data, hp_data, len(final_dna))
        plots["sequence_analysis"] = base64.b64encode(buf.getvalue()).decode("utf-8")
        buf.close()

    return EncodeResult(
        fasta=fasta_str,
        encoded_dna=final_dna,
        metrics=metrics,
        info_messages=info_msgs,
        huffman_table=huffman_table,
        plots=plots,
    )


def perform_decoding(fasta_data: str) -> DecodeResult:
    parsed = from_fasta(fasta_data)
    if not parsed:
        raise ValueError("No valid FASTA records found")
    header, sequence = parsed[0]

    messages: List[str] = []
    fec_messages: List[str] = []
    sequence_for_decode = sequence
    if "fec=triple_repeat" in header:
        if len(sequence) % 3 == 0:
            sequence_for_decode, corrected, uncorrectable = decode_triple_repeat(sequence)
            msg = f"Triple-Repeat FEC: {corrected} corrected, {uncorrectable} uncorrectable."
            messages.append(msg)
            fec_messages.append(msg)
        else:
            msg = (
                f"Warning: FEC sequence length ({len(sequence)}) not multiple of 3. Using original sequence."
            )
            messages.append(msg)
            fec_messages.append(msg)

    method = None
    huffman_table = None
    num_padding_bits = 0
    if "method=huffman" in header and "huffman_params=" in header:
        method = "huffman"
        json_field_start = header.find("huffman_params=")
        json_part = header[json_field_start + len("huffman_params=") :]
        first = json_part.find("{")
        if first == -1:
            raise ValueError("JSON object for huffman_params not found")
        open_br = 0
        end_idx = -1
        for i, ch in enumerate(json_part[first:]):
            if ch == "{":
                open_br += 1
            elif ch == "}":
                open_br -= 1
            if open_br == 0:
                end_idx = first + i + 1
                break
        if end_idx == -1:
            raise ValueError("Huffman params JSON not closed")
        params = json.loads(json_part[first:end_idx])
        table_str = params.get("table")
        num_padding_bits = params.get("padding")
        if table_str is None or num_padding_bits is None:
            raise ValueError("Invalid Huffman parameters")
        huffman_table = {int(k): v for k, v in table_str.items()}
    elif "method=base4_direct" in header:
        method = "base4_direct"
    elif "method=gc_balanced" in header:
        method = "gc_balanced"
    else:
        raise ValueError("Could not determine decoding method")

    check_parity = False
    k_val = 7
    if method != "gc_balanced" and "parity_k=" in header and "parity_rule=" in header:
        check_parity = True
        parity_k_str = header.split("parity_k=")[1].split()[0]
        k_val = int(parity_k_str)

    decoded_bytes: bytes = b""
    parity_errors: List[int] = []
    if method == "base4_direct":
        decoded_tuple = decode_base4_direct(
            sequence_for_decode, check_parity, k_val, PARITY_RULE_GC_EVEN_A_ODD_T
        )
        decoded_bytes, parity_errors = cast(Tuple[bytes, List[int]], decoded_tuple)
    elif method == "huffman":
        if huffman_table is None:
            raise ValueError("Huffman parameters missing")
        decoded_bytes, parity_errors = decode_huffman(
            sequence_for_decode,
            huffman_table,
            num_padding_bits,
            check_parity,
            k_val,
            PARITY_RULE_GC_EVEN_A_ODD_T,
        )
    elif method == "gc_balanced":
        gc_min_match = re.search(r"gc_min=([\d.]+)", header)
        gc_max_match = re.search(r"gc_max=([\d.]+)", header)
        max_hp_match = re.search(r"max_homopolymer=(\d+)", header)
        gc_min = float(gc_min_match.group(1)) if gc_min_match else None
        gc_max = float(gc_max_match.group(1)) if gc_max_match else None
        max_hp = int(max_hp_match.group(1)) if max_hp_match else None
        decoded_bytes = decode_gc_balanced(
            sequence_for_decode,
            expected_gc_min=gc_min,
            expected_gc_max=gc_max,
            expected_max_homopolymer=max_hp,
        )
    else:
        raise ValueError("Internal method error")

    if method != "gc_balanced" and check_parity and parity_errors:
        messages.append(f"Parity error(s) at blocks: {parity_errors}.")

    if "fec=hamming_7_4" in header:
        fec_padding_match = re.search(r"fec_padding_bits=(\d+)", header)
        if fec_padding_match:
            fec_bits = int(fec_padding_match.group(1))
            decoded_bytes, corrected = decode_data_with_hamming(decoded_bytes, fec_bits)
            msg = f"Hamming(7,4) FEC: {corrected} corrected errors."
            messages.append(msg)
            fec_messages.append(msg)
        else:
            msg = "'fec_padding_bits' missing for Hamming FEC."
            messages.append(msg)
            fec_messages.append(msg)
    if "fec=reed_solomon" in header:
        nsym_match = re.search(r"fec_nsym=(\d+)", header)
        if nsym_match:
            nsym = int(nsym_match.group(1))
            decoded_bytes, corrected_rs = decode_data_rs(decoded_bytes, nsym)
            msg = f"Reed-Solomon FEC: {corrected_rs} corrections."
            messages.append(msg)
            fec_messages.append(msg)
        else:
            msg = "'fec_nsym' missing for Reed-Solomon FEC."
            messages.append(msg)
            fec_messages.append(msg)

    status = " ".join(messages) + " Decoding successful."
    fec_info = " ".join(fec_messages) if fec_messages else None

    return DecodeResult(decoded_bytes=decoded_bytes, status_message=status, fec_info=fec_info)

