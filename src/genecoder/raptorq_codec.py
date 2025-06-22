"""RaptorQ encoding and decoding helpers using optional :mod:`raptorq`."""

from __future__ import annotations

from typing import Any, Tuple, TYPE_CHECKING

_HAS_RAPTORQ = False

if TYPE_CHECKING:
    import raptorq
else:  # pragma: no cover - optional dependency
    try:
        import raptorq  # type: ignore
        _HAS_RAPTORQ = True
    except Exception:  # pragma: no cover - missing optional dependency
        raptorq = None  # type: ignore
        _HAS_RAPTORQ = False


def _require_raptorq() -> None:  # pragma: no cover - helper
    """Ensure :mod:`raptorq` is installed."""
    if not _HAS_RAPTORQ:
        raise ImportError(
            "raptorq is required for RaptorQ encoding. Install it via 'pip install raptorq'."
        )


def encode_data_raptorq(data: bytes, symbol_size: int = 8) -> Tuple[bytes, Any]:
    """Encode ``data`` using a simple RaptorQ wrapper."""
    _require_raptorq()
    assert raptorq is not None
    enc = raptorq.RaptorQ(data, symbol_size)
    return enc.encode(), {"symbol_size": symbol_size, "orig_len": len(data)}


def decode_data_raptorq(encoded: bytes, info: Any) -> Tuple[bytes, int]:
    """Decode RaptorQ encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_raptorq()
    assert raptorq is not None
    dec = raptorq.Decoder(info["symbol_size"], info["orig_len"])
    data = dec.decode(encoded)
    if data is None:
        raise ValueError("RaptorQ decode failed")
    return data, 0


from typing import Callable


def register(register_fec: Callable[[str, Callable[[bytes], Tuple[bytes, Any]], Callable[[bytes, Any], Tuple[bytes, int]]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("raptorq", encode_data_raptorq, decode_data_raptorq)
