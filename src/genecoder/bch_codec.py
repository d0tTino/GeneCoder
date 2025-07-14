"""BCH encoding and decoding helpers using optional :mod:`bchlib`."""

from __future__ import annotations

from typing import Any, Mapping, Tuple, TYPE_CHECKING

_HAS_BCHLIB = False

if TYPE_CHECKING:
    import bchlib
else:  # pragma: no cover - optional dependency
    try:
        import bchlib
        try:
            # Verify library is functional; some wheels may load but fail
            bchlib.BCH(5, 2)
        except Exception:
            _HAS_BCHLIB = False
        else:
            _HAS_BCHLIB = True
    except Exception:  # pragma: no cover - missing optional dependency
        bchlib = None
        _HAS_BCHLIB = False


def _require_bchlib() -> None:  # pragma: no cover - helper
    """Ensure :mod:`bchlib` is installed."""
    if not _HAS_BCHLIB:
        raise ImportError(
            "bchlib is required for BCH encoding. Install it via 'pip install bchlib'."
        )


def encode_data_bch(data: bytes, m: int = 8, t: int = 4) -> Tuple[bytes, Any]:
    """Encode ``data`` using BCH error correction."""
    _require_bchlib()
    assert bchlib is not None
    bch = bchlib.BCH(m, t)
    ecc = bch.encode(data)
    return data + ecc, {"m": m, "t": t}


def decode_data_bch(encoded: bytes, info: Mapping[str, int]) -> Tuple[bytes, int]:
    """Decode BCH encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_bchlib()
    assert bchlib is not None
    bch = bchlib.BCH(info["m"], info["t"])
    data = encoded[:-bch.ecc_bytes]
    ecc = encoded[-bch.ecc_bytes:]
    decoded, corrected = bch.decode(data, ecc)
    if decoded is None:
        raise ValueError("BCH decode failed")
    return bytes(decoded), corrected


from typing import Callable


def register(
    register_fec: Callable[
        [
            str,
            Callable[[bytes], Tuple[bytes, Mapping[str, int]]],
            Callable[[bytes, Mapping[str, int]], Tuple[bytes, int]],
        ],
        None,
    ]
) -> None:
    """Register this module's FEC backend."""
    register_fec("bch", encode_data_bch, decode_data_bch)
