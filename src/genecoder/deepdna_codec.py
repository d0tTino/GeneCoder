"""DeepDNA error correction codec using optional :mod:`deepdna`."""

# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any, Mapping, Tuple, TYPE_CHECKING

from .plugin_api import FEC

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


def decode_data_deepdna(encoded: bytes, info: Mapping[str, str]) -> Tuple[bytes, int]:
    """Decode DeepDNA encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_deepdna()
    assert deepdna is not None
    model = deepdna.DeepDNA(info["model_name"])
    decoded = model.decode(encoded)
    return decoded, 0


class DeepDNAFEC(FEC):
    """DeepDNA FEC backend implementing :class:`BaseFEC`."""

    def encode(
        self, data: bytes, /, *, model_name: str = "deepdna-small", **kwargs: Any
    ) -> Tuple[bytes, Mapping[str, str]]:  # noqa: ANN401
        return encode_data_deepdna(data, model_name)

    def decode(
        self, encoded: bytes, info: Mapping[str, str], /, **kwargs: Any
    ) -> Tuple[bytes, int]:  # noqa: ANN401
        return decode_data_deepdna(encoded, info)


from typing import Callable


def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("deepdna", DeepDNAFEC)

