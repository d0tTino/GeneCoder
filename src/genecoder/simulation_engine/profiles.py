from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from genecoder.config.loader import (
    VersionedProfile,
    load_mapping_file,
    resolve_profile as _resolve_profile
)


def _load_mapping(path: str | Path) -> Mapping[str, Any]:
    return load_mapping_file(path)


def normalize_profile(
    value: str | Mapping[str, Any] | None,
    *,
    kind: str,
    presets: Mapping[str, VersionedProfile],
    allow_legacy_dict: bool = False,
) -> VersionedProfile | None:
    return _resolve_profile(
        value,
        kind=kind,
        presets=presets,
        allow_legacy_dict=allow_legacy_dict,
    )


def resolve_profile(
    value: str | Mapping[str, Any] | None,
    *,
    kind: str,
    presets: Mapping[str, VersionedProfile],
) -> VersionedProfile | None:
    return _resolve_profile(value, kind=kind, presets=presets, allow_legacy_dict=True)
