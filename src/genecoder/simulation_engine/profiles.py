from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import json
import warnings
from pathlib import Path


@dataclass(frozen=True)
class VersionedProfile:
    schema_version: int
    kind: str
    name: str
    parameters: Mapping[str, Any]


def validate_profile_schema(profile: Mapping[str, Any], *, kind: str) -> VersionedProfile:
    schema_version = int(profile.get("schema_version", 1))
    if schema_version != 1:
        raise ValueError(f"Unsupported {kind} profile schema_version: {schema_version}")
    name = str(profile.get("name") or kind)
    params = profile.get("parameters")
    if not isinstance(params, Mapping):
        raise ValueError(f"{kind} profile requires 'parameters' mapping")
    return VersionedProfile(schema_version=schema_version, kind=kind, name=name, parameters=dict(params))


def _load_mapping(path: str | Path) -> Mapping[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except Exception:
            from genecoder.plugin_manager import yaml as yaml_module

            if yaml_module is None:
                raise
            yaml = yaml_module
        data = yaml.safe_load(text) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Profile file must map keys to values")
    return data


def resolve_profile(
    value: str | Mapping[str, Any] | None,
    *,
    kind: str,
    presets: Mapping[str, VersionedProfile],
) -> VersionedProfile | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        warnings.warn(
            f"Raw dict-based {kind} profiles are deprecated; use a versioned profile object.",
            DeprecationWarning,
            stacklevel=2,
        )
        if "parameters" not in value:
            value = {"schema_version": 1, "kind": kind, "name": "custom", "parameters": dict(value)}
        return validate_profile_schema(value, kind=kind)
    path = Path(value)
    if path.is_file():
        return validate_profile_schema(_load_mapping(path), kind=kind)
    return presets.get(str(value).lower())
