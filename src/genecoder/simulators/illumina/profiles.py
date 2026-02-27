"""Profile utilities for the Illumina simulator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
import json
import warnings

from ...config.loader import VersionedProfile, load_mapping_file
from ...simulation_engine.profiles import normalize_profile as _normalize_profile


__all__ = [
    "IlluminaProfile",
    "ILLUMINA_PROFILES",
    "ILLUMINA_PROFILE_PRESETS",
    "_parse_quality_profile",
    "_validate_profile",
    "_load_profile_file",
    "_resolve_profile",
]


def _parse_quality_profile(value: str) -> Sequence[float]:
    path = Path(value)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
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
            data = yaml.safe_load(text)
        if not isinstance(data, Sequence):
            raise ValueError("quality profile must be a list")
        return [float(x) for x in data]
    return [float(x) for x in value.split(",") if x]


@dataclass
class IlluminaProfile:
    substitution_rate: float
    insertion_rate: float
    deletion_rate: float
    read_length: int
    coverage: float

    def __post_init__(self) -> None:
        for name, value in (
            ("substitution_rate", self.substitution_rate),
            ("insertion_rate", self.insertion_rate),
            ("deletion_rate", self.deletion_rate),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.read_length <= 0:
            raise ValueError("read_length must be positive")
        if self.coverage <= 0:
            raise ValueError("coverage must be positive")


_REQUIRED_KEYS = {"substitution_rate", "insertion_rate", "deletion_rate", "read_length", "coverage"}


def _validate_profile(data: Mapping[str, Any]) -> IlluminaProfile:
    unexpected = set(data.keys()) - _REQUIRED_KEYS
    if unexpected:
        keys = ", ".join(sorted(unexpected))
        hint = " Use 'coverage' instead of 'coverage_depth'." if "coverage_depth" in unexpected else ""
        raise ValueError(f"Illumina profile has unsupported key(s): {keys}.{hint}")
    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Illumina profile missing required key(s): {', '.join(sorted(missing))}")
    return IlluminaProfile(
        substitution_rate=float(data["substitution_rate"]),
        insertion_rate=float(data["insertion_rate"]),
        deletion_rate=float(data["deletion_rate"]),
        read_length=int(data["read_length"]),
        coverage=float(data["coverage"]),
    )


def _load_profile_file(path: str | Path) -> Mapping[str, Any]:
    return load_mapping_file(path)


_BASE_PRESETS: dict[str, dict[str, float | int]] = {
    "miseq": {"substitution_rate": 0.001, "insertion_rate": 0.0001, "deletion_rate": 0.0001, "read_length": 250, "coverage": 1},
    "hiseq": {"substitution_rate": 0.0005, "insertion_rate": 0.00005, "deletion_rate": 0.00005, "read_length": 150, "coverage": 1},
    "novaseq": {"substitution_rate": 0.0003, "insertion_rate": 0.00003, "deletion_rate": 0.00003, "read_length": 150, "coverage": 1},
    "nova": {"substitution_rate": 0.0003, "insertion_rate": 0.00003, "deletion_rate": 0.00003, "read_length": 150, "coverage": 1},
    "miseq_v3": {"substitution_rate": 0.0009, "insertion_rate": 0.00012, "deletion_rate": 0.00012, "read_length": 300, "coverage": 1.5},
    "hiseq_high_coverage": {"substitution_rate": 0.00045, "insertion_rate": 0.00005, "deletion_rate": 0.00005, "read_length": 150, "coverage": 2.5},
    "novaseq_s4": {"substitution_rate": 0.00025, "insertion_rate": 0.00002, "deletion_rate": 0.00002, "read_length": 150, "coverage": 3.0},
    "nextseq": {"substitution_rate": 0.0006, "insertion_rate": 0.00006, "deletion_rate": 0.00006, "read_length": 100, "coverage": 1.2},
}

ILLUMINA_PROFILE_PRESETS: dict[str, VersionedProfile] = {
    name: VersionedProfile(schema_version=1, kind="illumina", name=name, parameters=params)
    for name, params in _BASE_PRESETS.items()
}
# Deprecated raw dictionaries kept for compatibility.
ILLUMINA_PROFILES: dict[str, dict[str, float | int]] = {k: dict(v) for k, v in _BASE_PRESETS.items()}


def _resolve_profile(profile: str | Mapping[str, Any] | None) -> tuple[IlluminaProfile | None, Mapping[str, Any]]:
    resolved = _normalize_profile(profile, kind="illumina", presets=ILLUMINA_PROFILE_PRESETS, allow_legacy_dict=False)
    if resolved is None:
        return None, {}
    if isinstance(profile, Mapping):
        warnings.warn("Raw dict-based Illumina profile loading is deprecated.", DeprecationWarning, stacklevel=2)
    raw = dict(resolved.parameters)
    defaults = _validate_profile(raw)
    return defaults, raw
