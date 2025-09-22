"""Streaming helpers for large file processing."""

from __future__ import annotations

from typing import (
    Callable,
    Iterable,
    Iterator,
    Tuple,
    Union,
)
import os
import json
import hashlib
from pathlib import Path

from .encoders import encode_base4_direct, decode_base4_direct
from .error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from .utils import get_alphabet_maps
from .formats import SequenceBatch


EncodeFunc = Callable[[bytes], str]
DecodeFunc = Callable[[str], bytes]


def stream_encode(
    data_iter: Iterable[bytes],
    encode_fn: EncodeFunc,
    *,
    fec_encode: Callable[[bytes], tuple[bytes, object]] | None = None,
) -> Iterator[tuple[int, Union[str, Tuple[str, object]]]]:
    """Yield encoded DNA chunks with progress index and optional FEC."""

    for idx, chunk in enumerate(data_iter):
        if fec_encode:
            chunk, info = fec_encode(chunk)
            yield idx, (encode_fn(chunk), info)
        else:
            yield idx, encode_fn(chunk)


def stream_decode(
    dna_iter: Iterable[Union[str, Tuple[str, object]]],
    decode_fn: DecodeFunc,
    *,
    fec_decode: Callable[[bytes, object], tuple[bytes, int]] | None = None,
) -> Iterator[tuple[int, bytes]]:
    """Yield decoded binary chunks with progress index and optional FEC."""

    for idx, item in enumerate(dna_iter):
        if isinstance(item, tuple):
            dna, info = item
        else:
            dna, info = item, None
        chunk = decode_fn(dna)
        if fec_decode:
            chunk, _ = fec_decode(chunk, info)
        yield idx, chunk


def stream_encode_file(
    input_path: str,
    output_path: str,
    *,
    header: str,
    chunk_size: int = 1_000_000,
    manifest_path: str | None = None,
    resume: bool = False,
    add_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T,
    alphabet: str = "base4",
    batch_seed: int | None = None,
) -> int:
    """Encode ``input_path`` to ``output_path`` streaming chunks.

    Returns the total encoded DNA length. If ``manifest_path`` is not provided,
    ``<output_path>.stream.manifest`` is written with the SHA-256 hash and offset
    for each chunk.
    """

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if manifest_path is None:
        base, _ = os.path.splitext(output_path)
        manifest_path = base + ".stream.manifest"
    manifest_file = None
    processed_chunks = 0
    manifest_lines: list[dict[str, int | str]] = []
    verified_chunks: list[str] = []
    encode_map, _ = get_alphabet_maps(alphabet)
    if manifest_path:
        mode = "a" if resume else "w"
        if resume and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest_lines = [json.loads(line) for line in mf]
            processed_chunks = len(manifest_lines)
            # verify previously written chunks
            if processed_chunks:
                with open(input_path, "rb") as f_in:
                    for idx in range(processed_chunks):
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            raise ValueError(
                                "Manifest exceeds input file length during resume"
                            )
                        dna_iter = encode_base4_direct(
                            [chunk],
                            add_parity=add_parity,
                            k_value=k_value,
                            parity_rule=parity_rule,
                            encode_map=encode_map,
                            stream=True,
                        )
                        dna_chunk = next(iter(dna_iter))
                        verified_chunks.append(dna_chunk)
                        expected = hashlib.sha256(dna_chunk.encode()).hexdigest()
                        entry = manifest_lines[idx]
                        if (
                            entry["hash"] != expected
                            or entry["offset"] != idx * chunk_size
                        ):
                            raise ValueError(
                                f"Manifest hash mismatch at chunk {idx}"
                            )
        manifest_file = open(manifest_path, mode, encoding="utf-8")

    start_offset = processed_chunks * chunk_size

    existing_sequence = "".join(verified_chunks)
    if resume and os.path.exists(output_path):
        try:
            existing_batch = SequenceBatch.from_fasta(
                Path(output_path).read_text(encoding="utf-8")
            )
            parsed_sequence = existing_batch.primary_sequence()
            if parsed_sequence:
                existing_sequence = parsed_sequence
            if batch_seed is None:
                batch_seed = existing_batch.seed
        except (OSError, ValueError):
            existing_sequence = "".join(verified_chunks)

    def data_iter() -> Iterator[bytes]:
        with open(input_path, "rb") as f_in:
            if start_offset:
                f_in.seek(start_offset)
            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    sequence_parts: list[str] = []
    if existing_sequence:
        sequence_parts.append(existing_sequence)
    total_len = len(existing_sequence)
    offset = processed_chunks * chunk_size
    for dna_chunk in encode_base4_direct(
        data_iter(),
        add_parity=add_parity,
        k_value=k_value,
        parity_rule=parity_rule,
        encode_map=encode_map,
        stream=True,
    ):
        if manifest_file:
            chunk_hash = hashlib.sha256(dna_chunk.encode()).hexdigest()
            manifest_file.write(json.dumps({"offset": offset, "hash": chunk_hash}) + "\n")
            offset += chunk_size
        total_len += len(dna_chunk)
        sequence_parts.append(dna_chunk)
    if manifest_file:
        manifest_file.close()

    full_sequence = "".join(sequence_parts)

    batch = SequenceBatch.build(
        [(header, full_sequence)],
        batch_seed=batch_seed,
    )
    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write(batch.to_fasta(line_width=80))

    return total_len


def stream_decode_file(
    input_path: str,
    output_path: str,
    *,
    chunk_size: int = 1_000_000,
    manifest_path: str | None = None,
    resume: bool = False,
    check_parity: bool = False,
    k_value: int = 7,
    parity_rule: str = PARITY_RULE_GC_EVEN_A_ODD_T,
    alphabet: str = "base4",
) -> None:
    """Decode ``input_path`` FASTA file to ``output_path`` streaming chunks.

    If ``manifest_path`` is not provided, ``<output_path>.stream.manifest`` is
    used to track each chunk's offset and SHA-256 hash. Existing chunks are
    verified when ``resume`` is ``True``.
    """

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if manifest_path is None:
        base, _ = os.path.splitext(output_path)
        manifest_path = base + ".stream.manifest"
    manifest_file = None
    processed_chunks = 0
    manifest_lines: list[dict[str, int | str]] = []
    if manifest_path:
        mode = "a" if resume else "w"
        if resume and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest_lines = [json.loads(line) for line in mf]
            processed_chunks = len(manifest_lines)
            if processed_chunks and os.path.exists(output_path):
                with open(output_path, "rb") as verify_f:
                    for idx in range(processed_chunks):
                        chunk = verify_f.read(chunk_size)
                        if not chunk:
                            raise ValueError(
                                "Manifest exceeds output file length during resume"
                            )
                        expected = hashlib.sha256(chunk).hexdigest()
                        entry = manifest_lines[idx]
                        if (
                            entry["hash"] != expected
                            or entry["offset"] != idx * chunk_size
                        ):
                            raise ValueError(
                                f"Manifest hash mismatch at chunk {idx}"
                            )
        manifest_file = open(manifest_path, mode, encoding="utf-8")

    _, decode_map = get_alphabet_maps(alphabet)

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
        mode = "ab" if resume and os.path.exists(output_path) else "wb"
        with open(output_path, mode) as f_out:
            offset = processed_chunks * chunk_size
            for idx, (decoded_chunk, _) in enumerate(
                decode_base4_direct(
                    dna_iter(),
                    check_parity=check_parity,
                    k_value=k_value,
                    parity_rule=parity_rule,
                    decode_map=decode_map,
                    stream=True,
                )
            ):
                if idx < processed_chunks:
                    continue
                chunk_bytes = bytes(decoded_chunk)
                f_out.write(chunk_bytes)
                if manifest_file:
                    chunk_hash = hashlib.sha256(chunk_bytes).hexdigest()
                    manifest_file.write(
                        json.dumps({"offset": offset, "hash": chunk_hash}) + "\n"
                    )
                    offset += chunk_size
        if manifest_file:
            manifest_file.close()
