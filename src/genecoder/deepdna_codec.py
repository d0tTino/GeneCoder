"""DeepDNA error correction codec using optional :mod:`deepdna`."""

from __future__ import annotations

from typing import Any, Tuple, TYPE_CHECKING

_HAS_DEEPDNA = False

if TYPE_CHECKING:
    import deepdna
else:  # pragma: no cover - optional dependency
    try:
        import deepdna
        _HAS_DEEPDNA = True
    except Exception:  # pragma: no cover - missing optional dependency
        deepdna = None
        _HAS_DEEPDNA = False


def _require_deepdna() -> None:  # pragma: no cover - helper
    """Ensure :mod:`deepdna` is installed."""
    if not _HAS_DEEPDNA:
        raise ImportError(
            "deepdna is required for DeepDNA encoding. Install it via 'pip install deepdna'."
        )


def encode_data_deepdna(data: bytes, model_name: str = "deepdna-small") -> Tuple[bytes, Any]:
    """Encode ``data`` using the DeepDNA model."""
    _require_deepdna()
    assert deepdna is not None
    model = deepdna.DeepDNA(model_name)
    encoded = model.encode(data)
    return encoded, {"model_name": model_name}


def decode_data_deepdna(encoded: bytes, info: Any) -> Tuple[bytes, int]:
    """Decode DeepDNA encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_deepdna()
    assert deepdna is not None
    model = deepdna.DeepDNA(info["model_name"])
    decoded = model.decode(encoded)
    return decoded, 0


from typing import Callable


def register(register_fec: Callable[[str, Callable[[bytes], Tuple[bytes, Any]], Callable[[bytes, Any], Tuple[bytes, int]]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("deepdna", encode_data_deepdna, decode_data_deepdna)
