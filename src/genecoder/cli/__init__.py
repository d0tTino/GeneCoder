"""CLI submodules for GeneCoder."""

from ..options import EncodingOptions, DecodingOptions
from .options import (
    build_encoding_options,
    build_decoding_options,
    ChannelOptions,
    build_channel_options,
)
from .encode import run_encoding_pipeline, encode_files
from .decode import run_decoding_pipeline, decode_files
from ..core import run_pipeline
from .cli import main
from .channel import process_channel, run_channel
from .analyze import analyze_files
from .stats import collect_stats

__all__ = [
    "EncodingOptions",
    "ChannelOptions",
    "build_channel_options",
    "build_encoding_options",
    "encode_files",
    "run_encoding_pipeline",
    "DecodingOptions",
    "build_decoding_options",
    "decode_files",
    "run_decoding_pipeline",
    "run_pipeline",
    "analyze_files",
    "main",
    "process_channel",
    "run_channel",
    "collect_stats",
]

