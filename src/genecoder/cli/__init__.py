"""CLI submodules for GeneCoder."""

from ..options import EncodingOptions, DecodingOptions
from .options import (
    build_encoding_options,
    build_decoding_options,
    ChannelOptions,
    build_channel_options,
)
from .encode import run_encoding_pipeline
from .decode import run_decoding_pipeline
from .cli import main
from .channel import process_channel

__all__ = [
    "EncodingOptions",
    "ChannelOptions",
    "build_channel_options",
    "build_encoding_options",
    "run_encoding_pipeline",
    "DecodingOptions",
    "build_decoding_options",
    "run_decoding_pipeline",
    "main",
    "process_channel",
]

