"""FrameD FEC backend implemented using CFFI."""

from __future__ import annotations

from typing import Any, Mapping, Tuple, TYPE_CHECKING

_HAS_FRAMED = False

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from cffi.api import FFI
    _ffi: FFI | None
    _lib: Any | None
else:  # pragma: no cover - optional dependency
    try:
        from cffi import FFI
        _ffi: FFI | None
        _lib: Any | None
        
        _ffi = FFI()
        _ffi.cdef(
            """
            void* framed_encode(const uint8_t* data, size_t len, size_t* out_len);
            void* framed_decode(const uint8_t* data, size_t len, size_t* out_len, int* corrected);
            void framed_free(void* ptr);
            """
        )
        _lib = _ffi.dlopen("libframed.so")
        _HAS_FRAMED = True
    except Exception:
        _ffi = None
        _lib = None
        _HAS_FRAMED = False


def _require_framed() -> None:  # pragma: no cover - helper
    """Ensure the FrameD library is available."""

    if not _HAS_FRAMED:
        raise ImportError(
            "FrameD is required for this FEC backend. Install it via 'pip install FrameD' "
            "and ensure libframed.so is in your library path."
        )


def encode_data_framed(data: bytes) -> Tuple[bytes, Any]:
    """Encode ``data`` using FrameD's C++ kernels."""

    _require_framed()
    assert _ffi is not None and _lib is not None
    out_len = _ffi.new("size_t*")
    buf = _lib.framed_encode(data, len(data), out_len)
    encoded = bytes(_ffi.buffer(buf, out_len[0]))
    _lib.framed_free(buf)
    return encoded, {}


def decode_data_framed(encoded: bytes, info: Mapping[str, Any]) -> Tuple[bytes, int]:
    """Decode bytes produced by :func:`encode_data_framed`."""

    _require_framed()
    assert _ffi is not None and _lib is not None
    out_len = _ffi.new("size_t*")
    corrected = _ffi.new("int*")
    buf = _lib.framed_decode(encoded, len(encoded), out_len, corrected)
    data = bytes(_ffi.buffer(buf, out_len[0]))
    _lib.framed_free(buf)
    return data, int(corrected[0])


from typing import Callable


def register(
    register_fec: Callable[
        [
            str,
            Callable[[bytes], Tuple[bytes, Mapping[str, Any]]],
            Callable[[bytes, Mapping[str, Any]], Tuple[bytes, int]],
        ],
        None,
    ]
) -> None:
    """Register this module's FEC backend."""

    register_fec("framed", encode_data_framed, decode_data_framed)
