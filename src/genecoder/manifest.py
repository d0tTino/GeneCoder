from __future__ import annotations

"""Utilities for creating encode manifests."""

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

REQUIRED_ENCODING_KEYS: set[str] = {"method"}


def generate_manifest(
    file_name: str,
    encoding_params: Any,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a manifest dictionary for an encoded file."""
    if is_dataclass(encoding_params) and not isinstance(encoding_params, type):
        params = asdict(encoding_params)
    else:
        params = dict(encoding_params)

    missing = REQUIRED_ENCODING_KEYS - params.keys()
    if missing:
        raise ValueError(
            f"Missing required encoding parameters: {', '.join(sorted(missing))}"
        )

    return {
        "file": file_name,
        "encoding_parameters": params,
        "metrics": dict(metrics),
    }
