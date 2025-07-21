from __future__ import annotations

"""Codec wrapper exposing Chamaeleo via the plugin system."""

from typing import Callable, Any, TYPE_CHECKING
from pathlib import Path
import tempfile

if TYPE_CHECKING:  # pragma: no cover - for typing
    from Chamaeleo.methods import gc as gc_typing

try:  # pragma: no cover - optional dependency
    from Chamaeleo.codec_factory import encode as _ce, decode as _cd
    from Chamaeleo.methods import gc as gc_mod
    _HAS_CHAMAELEO = True
except Exception:  # pragma: no cover - missing optional dependency
    _HAS_CHAMAELEO = False
    gc_mod = None

from .plugin_manager import register_codec as _register_codec

__all__ = ["register"]


def _require() -> None:  # pragma: no cover - helper
    if not _HAS_CHAMAELEO:
        raise ImportError(
            "Chamaeleo is required for this codec. Install it via 'pip install Chamaeleo'."
        )


_method: "gc_typing.GC" | None
if _HAS_CHAMAELEO:
    _method = gc_mod.GC()
else:  # pragma: no cover - optional dependency missing
    _method = None


def encode_chamaeleo(data: bytes) -> str:
    _require()
    assert _method is not None
    with tempfile.TemporaryDirectory() as td:
        in_file = Path(td) / "input.bin"
        out_file = Path(td) / "output.txt"
        in_file.write_bytes(data)
        _ce(_method, str(in_file), str(out_file), need_index=False, segment_length=48)
        return out_file.read_text()


def decode_chamaeleo(text: str) -> bytes:
    _require()
    assert _method is not None
    with tempfile.TemporaryDirectory() as td:
        in_file = Path(td) / "input.txt"
        out_file = Path(td) / "output.bin"
        in_file.write_text(text)
        _cd(_method, input_path=str(in_file), output_path=str(out_file), has_index=False)
        data = out_file.read_bytes()
        return data.rstrip(b"\x00")


def register(
    registrar: Callable[[str, Callable[[bytes], str], Callable[[str], bytes]], None] = _register_codec,
) -> None:
    """Register the Chamaeleo codec."""

    registrar("chamaeleo_gc", encode_chamaeleo, decode_chamaeleo)
