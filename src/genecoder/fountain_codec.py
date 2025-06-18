"""Simple Fountain code helpers using :mod:`pyfinite` for GF arithmetic."""

from __future__ import annotations

from typing import Any, Tuple, TYPE_CHECKING

_HAS_PYFINITE = False

if TYPE_CHECKING:
    from pyfinite import ffield
else:
    try:  # pragma: no cover - optional dependency
        from pyfinite import ffield
        _HAS_PYFINITE = True
    except Exception:  # pragma: no cover - missing optional dependency
        ffield = None  # type: ignore
        _HAS_PYFINITE = False


def _require_pyfinite() -> None:  # pragma: no cover - helper
    """Ensure :mod:`pyfinite` is installed."""
    if not _HAS_PYFINITE:
        raise ImportError(
            "pyfinite is required for Fountain encoding. Install it via 'pip install pyfinite'."
        )


def encode_data_fountain(data: bytes, chunk_size: int = 4) -> Tuple[bytes, Any]:
    """Encode ``data`` using a trivial Fountain scheme with one parity chunk."""
    _require_pyfinite()
    F = ffield.FField(8)
    blocks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
    if len(blocks[-1]) < chunk_size:
        blocks[-1] += bytes(chunk_size - len(blocks[-1]))
    parity = bytearray(chunk_size)
    for block in blocks:
        for i, b in enumerate(block):
            parity[i] = F.Add(parity[i], b)
    encoded = b"".join(blocks) + bytes(parity)
    info = {"chunk_size": chunk_size, "orig_len": len(data)}
    return encoded, info


def decode_data_fountain(encoded: bytes, info: Any) -> Tuple[bytes, int]:
    """Decode data encoded by :func:`encode_data_fountain`. Parity is ignored."""
    _require_pyfinite()
    chunk_size = info["chunk_size"]
    orig_len = info["orig_len"]
    blocks = [
        encoded[i : i + chunk_size] for i in range(0, len(encoded) - chunk_size, chunk_size)
    ]
    data = b"".join(blocks)[:orig_len]
    return data, 0


from typing import Callable


def register(register_fec: Callable[[str, Callable[[bytes], tuple[bytes, Any]], Callable[[bytes, Any], tuple[bytes, int]]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("fountain", encode_data_fountain, decode_data_fountain)
