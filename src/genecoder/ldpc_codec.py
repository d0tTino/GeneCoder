"""LDPC encoding and decoding helpers using optional :mod:`pyldpc`."""

from __future__ import annotations

from typing import Any, Tuple, TYPE_CHECKING

_HAS_PYLDPC = False

if TYPE_CHECKING:
    import numpy as np
    from pyldpc import make_ldpc, decode, utils
else:
    try:  # pragma: no cover - optional dependency
        from pyldpc import make_ldpc, decode, utils
        # verify required functions are present and functional
        if callable(make_ldpc) and callable(decode):
            try:
                make_ldpc(8, d_v=2, d_c=4, systematic=True)
            except Exception:
                _HAS_PYLDPC = False
            else:
                _HAS_PYLDPC = True
        else:
            _HAS_PYLDPC = False
        import importlib.util
        if importlib.util.find_spec("numpy") is None:  # pragma: no cover
            np = None  # type: ignore
        else:
            import numpy as np  # type: ignore
    except Exception:  # pragma: no cover - missing optional dependency
        make_ldpc = decode = utils = None  # type: ignore
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
    global np
    if np is None:  # pragma: no cover - optional dependency
        import numpy as _np
        np = _np
    n_bits = len(data) * 8
    H, G = make_ldpc(n_bits, d_v=2, d_c=4, systematic=True)
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    message = np.pad(bits, (0, G.shape[1] - bits.size), "constant")[: G.shape[1]]
    codeword = utils.binaryproduct(G, message).astype(np.uint8)
    return np.packbits(codeword).tobytes(), {"H": H, "n_bits": bits.size}


def decode_data_ldpc(encoded: bytes, info: Any) -> Tuple[bytes, int]:
    """Decode LDPC encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_pyldpc()
    global np
    if np is None:  # pragma: no cover - optional dependency
        import numpy as _np
        np = _np
    H = info["H"]
    n_bits = info["n_bits"]
    bits = np.unpackbits(np.frombuffer(encoded, dtype=np.uint8))
    decoded = decode(H, bits, snr=2)
    data_bits = decoded[:n_bits]
    corrections = int((bits[:n_bits] != data_bits).sum())
    return np.packbits(data_bits).tobytes(), corrections


from typing import Callable


def register(register_fec: Callable[[str, Callable[[bytes], tuple[bytes, Any]], Callable[[bytes, Any], tuple[bytes, int]]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("ldpc", encode_data_ldpc, decode_data_ldpc)
