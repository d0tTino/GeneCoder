from __future__ import annotations

"""Utilities for creating encode manifests."""

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping


def generate_manifest(
    file_name: str,
    encoding_params: Any,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a manifest dictionary for an encoded file.

    ``encoding_params`` may be either a dataclass instance or a mapping. Passing
    anything else will raise :class:`ValueError`.
    """
    if is_dataclass(encoding_params) and not isinstance(encoding_params, type):
        params = asdict(encoding_params)
    elif isinstance(encoding_params, Mapping):
        params = dict(encoding_params)
    else:
        raise ValueError("encoding_params must be a dataclass or mapping")
    return {
        "file": file_name,
        "encoding_parameters": params,
        "metrics": dict(metrics),
    }
