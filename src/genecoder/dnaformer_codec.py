"""DNAformer error correction codec using optional :mod:`dnaformer`."""

from __future__ import annotations

from typing import Any, Tuple, TYPE_CHECKING

_HAS_DNAFORMER = False

if TYPE_CHECKING:
    import dnaformer
else:  # pragma: no cover - optional dependency
    try:
        import dnaformer
        _HAS_DNAFORMER = True
    except Exception:  # pragma: no cover - missing optional dependency
        dnaformer = None
        _HAS_DNAFORMER = False


def _require_dnaformer() -> None:  # pragma: no cover - helper
    """Ensure :mod:`dnaformer` is installed."""
    if not _HAS_DNAFORMER:
        raise ImportError(
            "dnaformer is required for DNAformer encoding. Install it via 'pip install dnaformer'."
        )


def encode_data_dnaformer(data: bytes, model_name: str = "dnaformer-small") -> Tuple[bytes, Any]:
    """Encode ``data`` using the DNAformer model."""
    _require_dnaformer()
    assert dnaformer is not None
    model = dnaformer.DNAformer(model_name)
    encoded = model.encode(data)
    return encoded, {"model_name": model_name}


def decode_data_dnaformer(encoded: bytes, info: Any) -> Tuple[bytes, int]:
    """Decode DNAformer encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_dnaformer()
    assert dnaformer is not None
    model = dnaformer.DNAformer(info["model_name"])
    decoded = model.decode(encoded)
    return decoded, 0


from typing import Callable


def register(register_fec: Callable[[str, Callable[[bytes], Tuple[bytes, Any]], Callable[[bytes, Any], Tuple[bytes, int]]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("dnaformer", encode_data_dnaformer, decode_data_dnaformer)
