"""Core modules for DNA encoding experiments."""

__version__ = "0.1.0"

_LAZY_ATTRS = {
    "EncodeOptions",
    "EncodeResult",
    "DecodeResult",
    "perform_encoding",
    "perform_decoding",
}

__all__ = [*sorted(_LAZY_ATTRS), "__version__"]


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        from .app_helpers import (
            EncodeOptions,
            EncodeResult,
            DecodeResult,
            perform_encoding,
            perform_decoding,
        )
        globals().update({
            "EncodeOptions": EncodeOptions,
            "EncodeResult": EncodeResult,
            "DecodeResult": DecodeResult,
            "perform_encoding": perform_encoding,
            "perform_decoding": perform_decoding,
        })
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

