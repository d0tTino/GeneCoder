"""Simple Illumina sequencing simulator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence
from pathlib import Path
import json
import random
import shutil
import subprocess
import logging

try:  # Optional at runtime
    from numba import njit
except Exception:  # pragma: no cover - fallback when numba missing
    from typing import Callable, TypeVar, ParamSpec

    P = ParamSpec("P")
    R = TypeVar("R")

    def njit(*args: object, **kwargs: object) -> Callable[[Callable[P, R]], Callable[P, R]]:
        def wrapper(func: Callable[P, R]) -> Callable[P, R]:
            return func

        return wrapper

from .base import BaseSimulator

from ..random_utils import make_rng
from ..api import Simulator
from ..error_simulation import _random_substitution, NUCLEOTIDES
from ..nanopore_sim import simulate_d2sim
from ..simulator_utils import _run_external, _parse_env_options
from . import register_simulator as _register_simulator

__all__ = [
    "IlluminaChannel",
    "IlluminaProfile",
    "IlluminaD2SimChannel",
    "IlluminaInSilicoSeqChannel",
    "simulate_insilicoseq",
    "register",
    "ILLUMINA_PROFILES",
]


# Helper to parse quality profiles from strings or files
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
    """Parameters controlling Illumina simulation behaviour."""

    substitution_rate: float
    insertion_rate: float
    deletion_rate: float
    read_length: int
    coverage: int

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
        coverage=int(data["coverage"]),
    )


# Load profile parameters from a JSON or YAML file
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
}


@njit(cache=True, forceobj=True)  # type: ignore[misc]
def _mutate_read_jit(
    read: str,
    quality: Sequence[float] | None,
    substitution_rate: float,
    insertion_rate: float,
    deletion_rate: float,
    context_errors: Dict[str, float],
    rng: random.Random,
) -> str:
    mutated: list[str] = []
    for idx, nt in enumerate(read):
        if rng.random() < deletion_rate:
            continue

        sub_rate = (
            quality[idx] if quality is not None and idx < len(quality) else substitution_rate
        )
        if context_errors and idx > 0:
            ctx = read[idx - 1 : idx + 1].upper()
            sub_rate *= context_errors.get(ctx, 1.0)

        if rng.random() < sub_rate:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)
        if rng.random() < insertion_rate:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


class IlluminaChannel(BaseSimulator):
    """Channel modeling basic Illumina read errors."""

    def __init__(
        self,
        substitution_rate: float = 0.001,
        insertion_rate: float = 0.0001,
        deletion_rate: float = 0.0001,
        coverage: int = 1,
        read_length: int = 150,
        quality_profile: Sequence[float] | None = None,
        context_errors: Dict[str, float] | None = None,
        profile: str | None = None,
        profile_path: str | None = None,
    ) -> None:
        if profile is not None:
            params = ILLUMINA_PROFILES.get(profile.lower())
            if params is not None:
                substitution_rate = float(
                    params.get("substitution_rate", substitution_rate)
                )
                insertion_rate = float(
                    params.get("insertion_rate", insertion_rate)
                )
                deletion_rate = float(
                    params.get("deletion_rate", deletion_rate)
                )
                read_length = int(params.get("read_length", read_length))
                coverage = int(params.get("coverage", coverage))
        if profile_path is not None:
            data = _load_profile_file(profile_path) or {}
            profile = _validate_profile(data)
            substitution_rate = profile.substitution_rate
            insertion_rate = profile.insertion_rate
            deletion_rate = profile.deletion_rate
            read_length = profile.read_length
            coverage = profile.coverage
            quality_profile = data.get("quality_profile", quality_profile)
            context_errors = data.get("context_errors", context_errors)
        else:
            profile = _validate_profile(
                {
                    "substitution_rate": substitution_rate,
                    "insertion_rate": insertion_rate,
                    "deletion_rate": deletion_rate,
                    "read_length": read_length,
                    "coverage": coverage,
                }
            )
            substitution_rate = profile.substitution_rate
            insertion_rate = profile.insertion_rate
            deletion_rate = profile.deletion_rate
            read_length = profile.read_length
            coverage = profile.coverage

        if isinstance(quality_profile, str):
            quality_profile = _parse_quality_profile(quality_profile)

        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            read_length=read_length,
            quality_profile=quality_profile,
        )
        self.context_errors = {
            k.upper(): float(v) for k, v in (context_errors or {}).items()
        }

    def _mutate_read(
        self, read: str, quality: Sequence[float] | None, rng: random.Random
    ) -> str:
        from typing import cast

        return cast(
            str,
            _mutate_read_jit(
                read,
                quality,
                self.substitution_rate,
                self.insertion_rate,
                self.deletion_rate,
                self.context_errors,
                rng,
            ),
        )

    @staticmethod
    def _consensus(reads: Iterable[str]) -> str:
        reads = list(reads)
        if not reads:
            return ""
        length = max(len(r) for r in reads)
        result = []
        for i in range(length):
            counts: Dict[str, int] = {}
            for r in reads:
                if i < len(r):
                    base = r[i]
                    counts[base] = counts.get(base, 0) + 1
            if counts:
                result.append(max(counts, key=lambda k: counts[k]))
        return "".join(result)

    def simulate(self, sequence: str) -> str:
        rng = make_rng()
        read_length = self.get_read_length(sequence)
        read = sequence[:read_length]
        quality = self.get_quality_profile(sequence, read_length)
        coverage = max(1, self.get_coverage(sequence))
        reads = [self._mutate_read(read, quality, rng) for _ in range(coverage)]
        if coverage == 1:
            return reads[0]
        return self._consensus(reads)

    def with_profile(self, profile: str) -> "IlluminaChannel":
        """Return a new channel configured to use ``profile``.

        Unknown profiles leave the channel unchanged.
        """

        if profile.lower() not in ILLUMINA_PROFILES:
            return self
        return type(self)(
            profile=profile,
            quality_profile=self.quality_profile,
            context_errors=dict(self.context_errors),
        )


class IlluminaD2SimChannel(Simulator):
    """Wrapper using the external ``d2sim`` simulator."""

    def __init__(self, error_rate: float = 0.05) -> None:
        self.error_rate = error_rate

    def simulate(self, sequence: str) -> str:
        return simulate_d2sim(sequence, error_rate=self.error_rate, rng=make_rng())


class IlluminaInSilicoSeqChannel(Simulator):
    """Use the ``insilicoseq`` CLI with a simple fallback."""

    def __init__(self, error_rate: float = 0.05, profile: str | None = None) -> None:
        self.error_rate = error_rate
        self.profile = profile

    def simulate(self, sequence: str) -> str:
        return simulate_insilicoseq(
            sequence, error_rate=self.error_rate, profile=self.profile
        )

    def with_profile(self, profile: str) -> "IlluminaInSilicoSeqChannel":
        """Return a new channel configured to use ``profile``."""

        return type(self)(error_rate=self.error_rate, profile=profile)


def simulate_insilicoseq(
    sequence: str, error_rate: float = 0.05, profile: str | None = None
) -> str:
    """Use the ``insilicoseq`` CLI if available, else fall back to ``IlluminaChannel``."""

    cmd = "insilicoseq"
    if shutil.which(cmd):
        cmd_list = [cmd, "-e", str(error_rate)]
        if profile:
            cmd_list += ["-p", profile]
        try:
            cmd_list += _parse_env_options(cmd)
            return _run_external(cmd_list, sequence)
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
            logging.getLogger(__name__).warning(
                "%s failed: %s; falling back to simple Illumina model",
                cmd,
                exc,
            )
    else:
        logging.getLogger(__name__).warning(
            "%s not found; falling back to simple Illumina model", cmd
        )
    return IlluminaChannel(substitution_rate=error_rate).simulate(sequence)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    registrar("illumina", IlluminaChannel())
    registrar("illumina_d2sim", IlluminaD2SimChannel())
    registrar("illumina_insilicoseq", IlluminaInSilicoSeqChannel())
