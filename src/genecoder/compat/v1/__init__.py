"""Versioned compatibility adapters for legacy import paths."""

from genecoder._deprecation import warn_with_telemetry

warn_with_telemetry(
    module_name="genecoder.compat.v1",
    message="genecoder.compat.v1 adapters are deprecated compatibility bridges; migrate to genecoder.app and genecoder.sdk.",
    stacklevel=2,
)
