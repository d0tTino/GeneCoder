"""Coding stack contracts and compilation helpers."""

from .stack import (
    CodingContext,
    CodingLayer,
    LayerIO,
    compile_legacy_stack,
    compile_stack_from_config,
    normalize_stack_metrics,
)

__all__ = [
    "CodingContext",
    "CodingLayer",
    "LayerIO",
    "compile_legacy_stack",
    "compile_stack_from_config",
    "normalize_stack_metrics",
]
