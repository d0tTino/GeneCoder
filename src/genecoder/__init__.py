"""Core modules for DNA encoding experiments.

The package groups together a variety of utilities used throughout the
project:

- :mod:`encoders` implements several encoding strategies.
- :mod:`gc_constrained_encoder` and :mod:`error_correction` provide
  optional constraints and FEC routines.
- :mod:`hamming_codec` supplies classic error correcting codes.
- :mod:`formats` and :mod:`plotting` handle FASTA output and diagnostic
  graphs (using `matplotlib`).

All submodules are importable from ``genecoder`` for convenience.
"""

from .app_helpers import (
    EncodeOptions,
    EncodeResult,
    DecodeResult,
    perform_encoding,
    perform_decoding,
)

__version__ = "0.1.0"

__all__ = [
    "EncodeOptions",
    "EncodeResult",
    "DecodeResult",
    "perform_encoding",
    "perform_decoding",
    "__version__",
]
