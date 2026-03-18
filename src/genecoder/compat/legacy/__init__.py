"""Compatibility-only implementations for deprecated public import paths.

This package is the single location for legacy shims. Do not add new product
features here; only forwarding logic and deprecation bridges are allowed.
"""

from genecoder._deprecation import warn_with_telemetry

from .sequence_pipeline import SequencePipeline

__all__ = ["SequencePipeline"]

warn_with_telemetry(
    module_name="genecoder.compat.legacy",
    message="genecoder.compat.legacy is deprecated; import supported interfaces from genecoder.app or genecoder.sdk.",
    stacklevel=2,
)
