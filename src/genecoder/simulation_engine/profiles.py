from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from genecoder.config.loader import load_mapping_file
from genecoder.profiles.registry import (
    LegacyProfilePolicy,
    VersionedProfile,
    policy_from_legacy_flag,
    resolve_versioned_profile,
)


def _load_mapping(path: str | Path) -> Mapping[str, Any]:
    return load_mapping_file(path)


def normalize_profile(
    value: str | Mapping[str, Any] | None,
    *,
    kind: str,
    presets: Mapping[str, VersionedProfile],
    allow_legacy_dict: bool = False,
    policy: LegacyProfilePolicy | None = None,
) -> VersionedProfile | None:
    effective_policy = policy or policy_from_legacy_flag(allow_legacy_dict=allow_legacy_dict)
    return resolve_versioned_profile(
        value,
        kind=kind,
        presets=presets,
        policy=effective_policy,
    )


def resolve_profile(
    value: str | Mapping[str, Any] | None,
    *,
    kind: str,
    presets: Mapping[str, VersionedProfile],
    policy: LegacyProfilePolicy = "compat",
) -> VersionedProfile | None:
    return resolve_versioned_profile(value, kind=kind, presets=presets, policy=policy)
