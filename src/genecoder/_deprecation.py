from __future__ import annotations

"""Shared helpers for deprecated module telemetry and warnings."""

from typing import Final
import warnings

from .metrics import increment

_DEPRECATION_NAMESPACE: Final[str] = "deprecated.module"


def record_deprecated_module_usage(module_name: str) -> None:
    """Increment structured counters for deprecated module usage."""

    normalized = module_name.replace("_", "-")
    increment(f"{_DEPRECATION_NAMESPACE}.total.imports")
    increment(f"{_DEPRECATION_NAMESPACE}.{normalized}.imports")


def warn_with_telemetry(*, module_name: str, message: str, stacklevel: int = 2) -> None:
    """Record deprecated module usage before emitting a deprecation warning."""

    record_deprecated_module_usage(module_name)
    warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)
