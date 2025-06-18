"""CLI submodules for GeneCoder."""

from .encode import (
    EncodingOptions,
    build_encoding_options,
    run_encoding_pipeline,
)
from .decode import (
    DecodingOptions,
    build_decoding_options,
    run_decoding_pipeline,
)
from .cli import main

__all__ = [
    "EncodingOptions",
    "build_encoding_options",
    "run_encoding_pipeline",
    "DecodingOptions",
    "build_decoding_options",
    "run_decoding_pipeline",
    "main",
]

