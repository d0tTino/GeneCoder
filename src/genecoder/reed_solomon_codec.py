"""Reed--Solomon encoding and decoding utilities using ``reedsolo``.

This module provides minimal wrappers around the :mod:`reedsolo` library to
encode and decode byte strings with Reed--Solomon error correction. Only the
number of parity symbols (``nsym``) is currently exposed as a parameter.
"""

from __future__ import annotations

from typing import Tuple

from reedsolo import RSCodec, ReedSolomonError


def encode_data_rs(data: bytes, nsym: int = 10) -> Tuple[bytes, int]:
    """Encode ``data`` with Reed--Solomon FEC.

    Parameters
    ----------
    data:
        Byte string to encode.
    nsym:
        Number of parity symbols to append. Defaults to ``10``.

    Returns
    -------
    tuple
        ``(encoded_bytes, nsym)`` where ``encoded_bytes`` is the encoded output
        including parity symbols.
    """
    rs = RSCodec(nsym)
    encoded = rs.encode(data)
    return bytes(encoded), nsym


def decode_data_rs(encoded: bytes, nsym: int) -> Tuple[bytes, int]:
    """Decode Reed--Solomon encoded ``encoded`` bytes.

    Parameters
    ----------
    encoded:
        Encoded data including parity symbols.
    nsym:
        Number of parity symbols that were used during encoding.

    Returns
    -------
    tuple
        ``(decoded_bytes, corrections)`` where ``corrections`` is the number of
        symbols corrected during decoding.

    Raises
    ------
    ValueError
        If decoding fails due to too many errors.
    """
    rs = RSCodec(nsym)
    try:
        decoded, _full, err_pos = rs.decode(encoded)
    except ReedSolomonError as exc:  # pragma: no cover - error path
        raise ValueError(f"Reed-Solomon decode failed: {exc}") from exc
    return bytes(decoded), len(err_pos)
