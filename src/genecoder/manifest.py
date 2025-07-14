from __future__ import annotations

"""Utilities for creating encode manifests."""

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping
from pathlib import Path
import os

REQUIRED_ENCODING_KEYS: set[str] = {"method"}


def generate_manifest(
    file_name: str | os.PathLike[str],
    encoding_params: Mapping[str, Any] | object,
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

    missing_keys = REQUIRED_ENCODING_KEYS - params.keys()
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(f"Missing required encoding parameter(s): {missing}")

    file_basename = os.path.basename(Path(file_name).as_posix())

    return {
        "file": file_basename,
        "encoding_parameters": params,
        "metrics": dict(metrics),
    }
