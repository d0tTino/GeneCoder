"""DNAformer error correction codec using optional :mod:`dnaformer`."""

# ruff: noqa: ANN401

from __future__ import annotations

from typing import Any, Mapping, Tuple, TYPE_CHECKING

from .plugin_api import FEC

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


def decode_data_dnaformer(
    encoded: bytes, info: Mapping[str, str]
) -> Tuple[bytes, int]:
    """Decode DNAformer encoded ``encoded`` bytes using ``info`` from encoding."""
    _require_dnaformer()
    assert dnaformer is not None
    model = dnaformer.DNAformer(info["model_name"])
    decoded = model.decode(encoded)
    return decoded, 0


class DNAFormerFEC(FEC):
    """DNAformer FEC backend implementing :class:`BaseFEC`."""

    def encode(
        self, data: bytes, /, *, model_name: str = "dnaformer-small", **kwargs: Any
    ) -> Tuple[bytes, Mapping[str, str]]:  # noqa: ANN401
        return encode_data_dnaformer(data, model_name)

    def decode(
        self, encoded: bytes, info: Mapping[str, str], /, **kwargs: Any
    ) -> Tuple[bytes, int]:  # noqa: ANN401
        return decode_data_dnaformer(encoded, info)


from typing import Callable


def register(register_fec: Callable[[str, type[FEC]], None]) -> None:
    """Register this module's FEC backend."""
    register_fec("dnaformer", DNAFormerFEC)

