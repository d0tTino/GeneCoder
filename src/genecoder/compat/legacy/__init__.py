"""Compatibility-only implementations for deprecated public import paths.

This package is the single location for legacy shims. Do not add new product
features here; only forwarding logic and deprecation bridges are allowed.
"""

from .sequence_pipeline import SequencePipeline

__all__ = ["SequencePipeline"]
