"""Streaming helpers for large file processing."""

from __future__ import annotations

import os
from typing import Iterable, Iterator

from .encoders import encode_base4_direct, decode_base4_direct
from .error_detection import PARITY_RULE_GC_EVEN_A_ODD_T


def stream_encode_file(
    input_path: str,
    output_path: str,
    *,
    header: str,
    chunk_size: int = 1_000_000,
    add_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T,
) -> int:
    """Encode ``input_path`` to ``output_path`` streaming chunks.

    Returns the total encoded DNA length.
    """

    def data_iter() -> Iterator[bytes]:
        with open(input_path, "rb") as f_in:
            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    total_len = 0
    line_width = 80
    buffer = ""
    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write(f">{header}\n")
        for dna_chunk in encode_base4_direct(
            data_iter(),
            add_parity=add_parity,
            k_value=k_value,
            parity_rule=parity_rule,
            stream=True,
        ):
            total_len += len(dna_chunk)
            buffer += dna_chunk
            while len(buffer) >= line_width:
                f_out.write(buffer[:line_width] + "\n")
                buffer = buffer[line_width:]
        if buffer:
            f_out.write(buffer + "\n")
    return total_len


def stream_decode_file(
    input_path: str,
    output_path: str,
    *,
    chunk_size: int = 1_000_000,
    check_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T,
) -> None:
    """Decode ``input_path`` FASTA file to ``output_path`` streaming chunks."""

    with open(input_path, "r", encoding="utf-8") as f_in:
        header_line = f_in.readline()
        if not header_line.startswith(">"):
            raise ValueError("Invalid FASTA input")

        def dna_iter() -> Iterator[str]:
            buffer = ""
            for line in f_in:
                line = line.strip()
                if not line or line.startswith(">"):
                    continue
                buffer += line
                while len(buffer) >= chunk_size * 4:
                    yield buffer[: chunk_size * 4]
                    buffer = buffer[chunk_size * 4 :]
            if buffer:
                yield buffer

        with open(output_path, "wb") as f_out:
            for decoded_chunk, _ in decode_base4_direct(
                dna_iter(),
                check_parity=check_parity,
                k_value=k_value,
                parity_rule=parity_rule,
                stream=True,
            ):
                f_out.write(decoded_chunk)
