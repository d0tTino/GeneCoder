"""Cloud worker stubs for tests."""

from genecoder._deprecation import warn_with_telemetry

from . import worker

__all__ = ["worker"]

warn_with_telemetry(
    module_name="genecoder.compat.legacy.cloud",
    message="genecoder.compat.legacy.cloud is deprecated and retained only for compatibility tests.",
    stacklevel=2,
)
