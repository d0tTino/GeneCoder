"""LDPC encoding and decoding helpers using optional :mod:`pyldpc`."""

from __future__ import annotations

from typing import Any, Tuple, TYPE_CHECKING

_HAS_PYLDPC = False

if TYPE_CHECKING:
    import numpy as np
    from pyldpc import make_ldpc, encode, decode, get_message, utils
else:
    try:  # pragma: no cover - optional dependency
        import numpy as np
        from pyldpc import make_ldpc, encode, decode, get_message, utils
        _HAS_PYLDPC = True
    except Exception:  # pragma: no cover - missing optional dependency
        make_ldpc = encode = decode = get_message = utils = None  # type: ignore
        np = None  # type: ignore
        _HAS_PYLDPC = False


def _require_pyldpc() -> None:  # pragma: no cover - helper
    """Ensure :mod:`pyldpc` is installed."""
    if not _HAS_PYLDPC:
        raise ImportError(
            "pyldpc is required for LDPC encoding. Install it via 'pip install pyldpc'."
        )


def encode_data_ldpc(data: bytes) -> Tuple[bytes, Any]:
    """Encode ``data`` using a basic LDPC code.

    Parameters
    ----------
    data:
        Byte string to encode.

    Returns
    -------
    tuple
        ``(encoded_bytes, info)`` where ``info`` contains matrices needed for
        decoding.
    """
    _require_pyldpc()
    assert np is not None
    n_bits = len(data) * 8
    # ``make_ldpc`` expects the length of the encoded codeword (n). Use
    # twice the number of data bits to ensure the generated generator matrix
    # has enough columns for the message bits.
    n = n_bits * 2
    H, G = make_ldpc(n, d_v=2, d_c=4, systematic=True)
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    message = np.pad(bits, (0, G.shape[1] - bits.size), "constant")
    # Encode the message using a high SNR so no noise is introduced.
    codeword = encode(G, message, snr=100)
    return np.packbits(codeword > 0).tobytes(), {"H": H, "G": G, "n_bits": bits.size}


def decode_data_ldpc(encoded: bytes, info: Any) -> Tuple[bytes, int]:
    """Decode LDPC encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_pyldpc()
    assert np is not None
    H = info["H"]
    G = info["G"]
    n_bits = info["n_bits"]
    bits = np.unpackbits(np.frombuffer(encoded, dtype=np.uint8))
    decoded = decode(H, bits, snr=100)
    message = get_message(G, decoded)
    data_bits = message[:n_bits]
    corrections = int((decoded[: n_bits] != message[:n_bits]).sum())
    return np.packbits(data_bits).tobytes(), corrections


from typing import Callable


def register(register_fec: Callable[[str, Callable[[bytes], tuple[bytes, Any]], Callable[[bytes, Any], tuple[bytes, int]]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("ldpc", encode_data_ldpc, decode_data_ldpc)
