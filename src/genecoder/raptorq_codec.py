"""RaptorQ encoding and decoding helpers using optional :mod:`raptorq`."""

from __future__ import annotations

from typing import Any, Tuple, TYPE_CHECKING

_rq: Any | None = None

_HAS_RAPTORQ = False

if TYPE_CHECKING:
    import raptorq
else:  # pragma: no cover - optional dependency
    try:
        import raptorq  # type: ignore
        try:
            from raptorq import raptorq as _rq  # type: ignore
        except Exception:
            _rq = raptorq  # type: ignore
        if hasattr(_rq, "Encoder") and hasattr(_rq, "Decoder"):
            try:
                enc = _rq.Encoder.with_defaults(b"t", 1)
                packets = enc.get_encoded_packets(0)
                dec = _rq.Decoder.with_defaults(1, 1)
                result = None
                for pkt in packets:
                    result = dec.decode(pkt)
                    if result is not None:
                        break
                _HAS_RAPTORQ = result == b"t"
            except Exception:
                _HAS_RAPTORQ = False
        else:
            _HAS_RAPTORQ = False
    except Exception:  # pragma: no cover - missing optional dependency
        raptorq = None  # type: ignore
        _rq = None  # type: ignore
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
    assert _rq is not None
    if hasattr(raptorq, "RaptorQ"):
        enc = raptorq.RaptorQ(data, symbol_size)
        encoded = enc.encode()
    else:
        enc = raptorq.Encoder.with_defaults(data, symbol_size)
        encoded = b"".join(enc.get_encoded_packets(0))
    return encoded, {"symbol_size": symbol_size, "orig_len": len(data)}


def decode_data_raptorq(encoded: bytes, info: Any) -> Tuple[bytes, int]:
    """Decode RaptorQ encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_raptorq()
    assert _rq is not None
    if hasattr(raptorq, "RaptorQ"):
        dec = raptorq.Decoder(info["symbol_size"], info["orig_len"])
        data = dec.decode(encoded)
    else:
        dec_cls = getattr(raptorq.Decoder, "with_defaults", raptorq.Decoder)
        dec = dec_cls(info["orig_len"], info["symbol_size"])
        packet_len = info["symbol_size"] + 4
        data = None
        for i in range(0, len(encoded), packet_len):
            packet = encoded[i : i + packet_len]
            res = dec.decode(packet)
            if res is not None:
                data = res
                break
    if data is None:
        raise ValueError("RaptorQ decode failed")
    return data, 0


from typing import Callable


def register(register_fec: Callable[[str, Callable[[bytes], Tuple[bytes, Any]], Callable[[bytes, Any], Tuple[bytes, int]]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("raptorq", encode_data_raptorq, decode_data_raptorq)
