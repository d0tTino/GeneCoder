"""Simple Fountain code helpers using :mod:`pyfinite` for GF arithmetic."""

# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any, Mapping, Tuple, TYPE_CHECKING

from .codecs import BaseFEC

_HAS_PYFINITE = False

if TYPE_CHECKING:
    from pyfinite import ffield
else:
    try:  # pragma: no cover - optional dependency
        from pyfinite import ffield
        _HAS_PYFINITE = True
    except Exception:  # pragma: no cover - missing optional dependency
        ffield = None
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
    if not data:
        return b"", {"chunk_size": chunk_size, "orig_len": 0}

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


def decode_data_fountain(
    encoded: bytes, info: Mapping[str, int]
) -> Tuple[bytes, int]:
    """Decode data encoded by :func:`encode_data_fountain`. Parity is ignored."""
    _require_pyfinite()
    chunk_size = info["chunk_size"]
    orig_len = info["orig_len"]
    blocks = [
        encoded[i : i + chunk_size] for i in range(0, len(encoded) - chunk_size, chunk_size)
    ]
    data = b"".join(blocks)[:orig_len]
    return data, 0


class FountainFEC(BaseFEC):
    """Simple Fountain code backend implementing :class:`BaseFEC`."""

    def encode(
        self, data: bytes, /, *, chunk_size: int = 4, **kwargs: Any
    ) -> Tuple[bytes, Mapping[str, int]]:  # noqa: ANN401
        return encode_data_fountain(data, chunk_size)

    def decode(
        self, encoded: bytes, info: Mapping[str, int], /, **kwargs: Any
    ) -> Tuple[bytes, int]:  # noqa: ANN401
        return decode_data_fountain(encoded, info)


from typing import Callable


def register(register_fec: Callable[[str, type[BaseFEC]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("fountain", FountainFEC)

