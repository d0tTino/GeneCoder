"""Profile utilities for the Illumina simulator.

This module defines :data:`ILLUMINA_PROFILES`, a set of named presets that
represent common Illumina platforms and quality tiers.  Each profile combines
substitution, insertion, and deletion rates with default read-length and
coverage targets so callers can quickly swap between MiSeq-style high-fidelity
reads and NovaSeq-scale high-throughput runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
import json


__all__ = [
    "IlluminaProfile",
    "ILLUMINA_PROFILES",
    "_parse_quality_profile",
    "_validate_profile",
    "_load_profile_file",
]


def _parse_quality_profile(value: str) -> Sequence[float]:
    """Return a list of floats from ``value``.

    ``value`` may be a comma-separated list or a path to JSON/YAML.
    """

    path = Path(value)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:  # Optional at runtime
                import yaml
            except Exception:  # pragma: no cover - optional dependency
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
    """Parameters controlling Illumina simulation behaviour.

    The bundled :data:`ILLUMINA_PROFILES` cover MiSeq V3, HiSeq and NovaSeq
    quality tiers with adjusted coverage and read-length defaults to mirror each
    platform's typical output.
    """

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


_REQUIRED_KEYS = {
    "substitution_rate",
    "insertion_rate",
    "deletion_rate",
    "read_length",
    "coverage",
}


def _validate_profile(data: Mapping[str, Any]) -> IlluminaProfile:
    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        keys = ", ".join(sorted(missing))
        raise ValueError(f"Illumina profile missing required key(s): {keys}")
    return IlluminaProfile(
        substitution_rate=float(data["substitution_rate"]),
        insertion_rate=float(data["insertion_rate"]),
        deletion_rate=float(data["deletion_rate"]),
        read_length=int(data["read_length"]),
        coverage=float(data["coverage"]),
    )


def _load_profile_file(path: str | Path) -> Mapping[str, Any]:
    """Return profile parameters loaded from ``path``.

    The file may be JSON or YAML and must map keys to values.
    """

    text = Path(path).read_text(encoding="utf-8")
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        try:  # Optional at runtime
            import yaml
        except Exception:  # pragma: no cover - optional dependency
            from genecoder.plugin_manager import yaml as yaml_module

            if yaml_module is None:
                raise
            yaml = yaml_module
        data = yaml.safe_load(text) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Profile file must map keys to values")
    return data


# Preset parameter profiles for :class:`IlluminaChannel`.
ILLUMINA_PROFILES: dict[str, dict[str, float | int]] = {
    "miseq": {
        "substitution_rate": 0.001,
        "insertion_rate": 0.0001,
        "deletion_rate": 0.0001,
        "read_length": 250,
        "coverage": 1,
    },
    "hiseq": {
        "substitution_rate": 0.0005,
        "insertion_rate": 0.00005,
        "deletion_rate": 0.00005,
        "read_length": 150,
        "coverage": 1,
    },
    "novaseq": {
        "substitution_rate": 0.0003,
        "insertion_rate": 0.00003,
        "deletion_rate": 0.00003,
        "read_length": 150,
        "coverage": 1,
    },
    "nova": {
        "substitution_rate": 0.0003,
        "insertion_rate": 0.00003,
        "deletion_rate": 0.00003,
        "read_length": 150,
        "coverage": 1,
    },
    "miseq_v3": {
        "substitution_rate": 0.0009,
        "insertion_rate": 0.00012,
        "deletion_rate": 0.00012,
        "read_length": 300,
        "coverage": 1.5,
    },
    "hiseq_high_coverage": {
        "substitution_rate": 0.00045,
        "insertion_rate": 0.00005,
        "deletion_rate": 0.00005,
        "read_length": 150,
        "coverage": 2.5,
    },
    "novaseq_s4": {
        "substitution_rate": 0.00025,
        "insertion_rate": 0.00002,
        "deletion_rate": 0.00002,
        "read_length": 150,
        "coverage": 3.0,
    },
    "nextseq": {
        "substitution_rate": 0.0006,
        "insertion_rate": 0.00006,
        "deletion_rate": 0.00006,
        "read_length": 100,
        "coverage": 1.2,
    },
}
