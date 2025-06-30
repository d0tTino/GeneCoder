"""CLI submodules for GeneCoder."""

from ..options import EncodingOptions, DecodingOptions
from .encode import (
    build_encoding_options,
    run_encoding_pipeline,
)
from .decode import (
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

