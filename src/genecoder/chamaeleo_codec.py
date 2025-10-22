from __future__ import annotations

"""Codec wrapper exposing Chamaeleo via the plugin system."""

from importlib import import_module
from functools import lru_cache
from typing import Callable, Any, Mapping, Sequence
from pathlib import Path
import tempfile

try:  # pragma: no cover - optional dependency
    from Chamaeleo.codec_factory import encode as _ce, decode as _cd
    _HAS_CHAMAELEO = True
except Exception:  # pragma: no cover - missing optional dependency
    _HAS_CHAMAELEO = False

from .plugin_manager import register_codec as _register_codec
from .api import Codec

__all__ = ["register"]


def _require() -> None:  # pragma: no cover - helper
    if not _HAS_CHAMAELEO:
        raise ImportError(
            "Chamaeleo is required for this codec. Install it via 'pip install Chamaeleo'."
        )


_MethodPath = tuple[str, str]


_METHOD_CANDIDATES: Mapping[str, Sequence[_MethodPath]] = {
    "chamaeleo_gc": (
        ("Chamaeleo.methods.gc", "GC"),
        ("Chamaeleo.methods.flowed", "YinYangCode"),
    ),
    "chamaeleo_fountain": (("Chamaeleo.methods.flowed", "DNAFountain"),),
    "chamaeleo_goldman": (("Chamaeleo.methods.fixed", "Goldman"),),
    "chamaeleo_church": (("Chamaeleo.methods.fixed", "Church"),),
    "chamaeleo_grass": (("Chamaeleo.methods.fixed", "Grass"),),
    "chamaeleo_blawat": (("Chamaeleo.methods.fixed", "Blawat"),),
}


_METHOD_INSTANCES: dict[str, object] = {}


def _load_method_class(codec_name: str) -> type[Any]:
    """Return the Chamaeleo method class for ``codec_name``."""

    candidates = _METHOD_CANDIDATES.get(codec_name)
    if not candidates:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown Chamaeleo codec '{codec_name}'.")

    _require()

    errors: list[Exception] = []
    for module_name, class_name in candidates:
        try:
            module = import_module(module_name)
            method_cls = getattr(module, class_name)
        except Exception as exc:  # pragma: no cover - import fallback
            errors.append(exc)
            continue
        else:
            return method_cls

    msg = f"Could not load a Chamaeleo method for codec '{codec_name}'."
    if errors:
        raise ImportError(msg) from errors[-1]
    raise ImportError(msg)


@lru_cache(maxsize=None)
def _method_class(codec_name: str) -> type[Any]:
    return _load_method_class(codec_name)


def _get_method(codec_name: str) -> object:
    method = _METHOD_INSTANCES.get(codec_name)
    if method is None:
        method_cls = _method_class(codec_name)
        method = method_cls()
        _METHOD_INSTANCES[codec_name] = method
    return method


def _encode_with_method(method: object, data: bytes) -> str:
    with tempfile.TemporaryDirectory() as td:
        in_file = Path(td) / "input.bin"
        out_file = Path(td) / "output.txt"
        in_file.write_bytes(data)
        _ce(method, str(in_file), str(out_file), need_index=False, segment_length=48)
        return out_file.read_text()


def _decode_with_method(method: object, text: str) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        in_file = Path(td) / "input.txt"
        out_file = Path(td) / "output.bin"
        in_file.write_text(text)
        _cd(method, input_path=str(in_file), output_path=str(out_file), has_index=False)
        data = out_file.read_bytes()
        return data.rstrip(b"\x00")


class ChamaeleoMethodCodec(Codec):
    """Codec using the external Chamaeleo library for a specific method."""

    codec_name: str

    def __init__(self) -> None:
        self._method: object | None = None

    def _ensure_method(self) -> object:
        if self._method is None:
            self._method = _get_method(self.codec_name)
        return self._method

    def encode(self, data: bytes, /, **kwargs: Any) -> str:  # noqa: ANN401
        _require()
        method = self._ensure_method()
        return _encode_with_method(method, data)

    def decode(self, encoded: str, /, **kwargs: Any) -> bytes:  # noqa: ANN401
        _require()
        method = self._ensure_method()
        return _decode_with_method(method, encoded)


def _codec_class_name(codec_name: str) -> str:
    return "".join(part.title() for part in codec_name.split("_"))


_CODECS: dict[str, type[ChamaeleoMethodCodec]] = {}
for name in _METHOD_CANDIDATES:
    class_name = _codec_class_name(name)
    _CODECS[name] = type(
        class_name,
        (ChamaeleoMethodCodec,),
        {"codec_name": name, "__module__": __name__},
    )


_DEFAULT_CODEC_NAME = "chamaeleo_gc"
_DEFAULT_CODEC = _CODECS[_DEFAULT_CODEC_NAME]()

SUPPORTED_CHAMAELEO_CODECS: tuple[str, ...] = tuple(_CODECS.keys())


def encode_chamaeleo(data: bytes) -> str:
    """Encode ``data`` using the default Chamaeleo method (GC)."""

    return _DEFAULT_CODEC.encode(data)


def decode_chamaeleo(text: str) -> bytes:
    """Decode ``text`` using the default Chamaeleo method (GC)."""

    return _DEFAULT_CODEC.decode(text)


def register(
    registrar: Callable[[str, type[Codec]], None] = _register_codec,
) -> None:
    """Register the available Chamaeleo codecs."""

    for name, codec in _CODECS.items():
        registrar(name, codec)
