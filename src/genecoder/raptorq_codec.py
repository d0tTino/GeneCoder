"""RaptorQ encoding and decoding helpers using optional :mod:`raptorq`."""

# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any, Mapping, Tuple, TYPE_CHECKING

from .plugin_api import FEC

_HAS_RAPTORQ = False

if TYPE_CHECKING:
    import raptorq
    from raptorq import raptorq as _rq

else:  # pragma: no cover - optional dependency
    try:
        import raptorq
        try:
            from raptorq import raptorq as _rq
        except Exception:
            _rq = raptorq
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
        raptorq = None
        _rq = None
        _HAS_RAPTORQ = False


def _require_raptorq() -> None:  # pragma: no cover - helper
    """Ensure :mod:`raptorq` is installed."""
    if _rq is None:
        raise ImportError(
            "raptorq is required for RaptorQ encoding. Install it via 'pip install raptorq'."
        )
    if not _HAS_RAPTORQ:
        raise ImportError(
            "raptorq is required for RaptorQ encoding. Install it via 'pip install raptorq'."
        )


def encode_data_raptorq(data: bytes, symbol_size: int = 8) -> Tuple[bytes, Any]:
    """Encode ``data`` using a simple RaptorQ wrapper."""
    _require_raptorq()
    assert _rq is not None
    if symbol_size < 64:
        symbol_size = 64
    if hasattr(raptorq, "RaptorQ"):
        enc = raptorq.RaptorQ(data, symbol_size)
        encoded = enc.encode()
    else:
        enc = raptorq.Encoder.with_defaults(data, symbol_size)
        encoded = b"".join(enc.get_encoded_packets(0))
    return encoded, {"symbol_size": symbol_size, "orig_len": len(data)}


def decode_data_raptorq(encoded: bytes, info: Mapping[str, int]) -> Tuple[bytes, int]:
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


class RaptorqFEC(FEC):
    """RaptorQ FEC backend implementing :class:`BaseFEC`."""

    def encode(
        self, data: bytes, /, *, symbol_size: int = 8, **kwargs: Any
    ) -> Tuple[bytes, Mapping[str, int]]:  # noqa: ANN401
        return encode_data_raptorq(data, symbol_size)

    def decode(
        self, encoded: bytes, info: Mapping[str, int], /, **kwargs: Any
    ) -> Tuple[bytes, int]:  # noqa: ANN401
        return decode_data_raptorq(encoded, info)


from typing import Callable


def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("raptorq", RaptorqFEC)

