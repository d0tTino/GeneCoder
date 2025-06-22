"""Generic streaming encode/decode helpers."""

from __future__ import annotations

from typing import Callable, Iterable, Iterator

EncodeFunc = Callable[[bytes], str]
DecodeFunc = Callable[[str], bytes]


def stream_encode(
    data_iter: Iterable[bytes],
    encode_fn: EncodeFunc,
    *,
    fec_encode: Callable[[bytes], tuple[bytes, object]] | None = None,
) -> Iterator[str]:
    """Yield encoded DNA chunks with optional FEC."""
    for chunk in data_iter:
        if fec_encode:
            chunk, _ = fec_encode(chunk)
        yield encode_fn(chunk)


def stream_decode(
    dna_iter: Iterable[str],
    decode_fn: DecodeFunc,
    *,
    fec_decode: Callable[[bytes, object], tuple[bytes, int]] | None = None,
) -> Iterator[bytes]:
    """Yield decoded binary chunks with optional FEC decoding."""
    for dna in dna_iter:
        chunk = decode_fn(dna)
        if fec_decode:
            chunk, _ = fec_decode(chunk, None)
        yield chunk
