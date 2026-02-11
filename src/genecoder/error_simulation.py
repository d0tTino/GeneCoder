"""Utilities for simulating random sequencing errors in DNA sequences."""
from __future__ import annotations

import random
import warnings
from typing import Callable

from .random_utils import make_rng
from .plugin_api import Simulator
from .simulators import register_simulator as _register_simulator
from .formats import SequenceBatch
from .simulators.batch_utils import apply_legacy_simulator

__all__ = [
    "simulate_errors",
    "introduce_errors",
    "apply_substitutions",
    "apply_insertions",
    "apply_deletions",
    "Channel",
    "register",
    "INDEL_PROFILES",
    "ADAPTER_PROFILES",
    "DEFAULT_ADAPTER_PROFILE",
]

NUCLEOTIDES = ["A", "T", "C", "G"]


# Preset substitution/indel probability profiles for :class:`Channel`.
LEGACY_INDEL_PROFILES: dict[str, dict[str, float]] = {
    # Typical Illumina error characteristics favour substitutions over indels.
    "illumina": {
        "substitution_prob": 0.002,
        "insertion_prob": 0.0001,
        "deletion_prob": 0.0001,
    },
    # Nanopore devices tend to produce higher indel rates.
    "nanopore": {
        "substitution_prob": 0.01,
        "insertion_prob": 0.02,
        "deletion_prob": 0.02,
    },
}

# Adapter presets that delegate to richer simulator implementations.
ADAPTER_PROFILES: dict[str, dict[str, object]] = {
    "illumina_adapter": {
        "family": "illumina",
        "profile": "miseq_v3",
        "fallback": {
            "substitution_prob": 0.0009,
            "insertion_prob": 0.0001,
            "deletion_prob": 0.0001,
        },
    },
    "nanopore_adapter": {
        "family": "nanopore",
        "profile": "r10.4",
        "fallback": {
            "substitution_prob": 0.045,
            "insertion_prob": 0.015,
            "deletion_prob": 0.025,
        },
    },
}

INDEL_PROFILES: dict[str, dict[str, float]] = {
    **LEGACY_INDEL_PROFILES,
    **{name: profile["fallback"] for name, profile in ADAPTER_PROFILES.items()},
}

DEFAULT_ADAPTER_PROFILE = "illumina_adapter"


def _random_substitution(nucleotide: str, rng: random.Random) -> str:
    """Return a random nucleotide different from the input."""
    choices = [n for n in NUCLEOTIDES if n != nucleotide]
    return rng.choice(choices)


def simulate_errors(
    sequence: str,
    substitution_prob: float = 0.0,
    insertion_prob: float = 0.0,
    deletion_prob: float = 0.0,
    rng: random.Random | None = None,
) -> str:
    """Introduce random substitutions, insertions and deletions into ``sequence``.

    Parameters
    ----------
    sequence:
        Input DNA sequence.
    substitution_prob:
        Probability of substituting each nucleotide with a random one.
    insertion_prob:
        Probability of inserting a random nucleotide after each position.
    deletion_prob:
        Probability of deleting each nucleotide.
    rng:
        Optional :class:`random.Random` instance for deterministic behaviour.

    Raises
    ------
    ValueError
        If any of ``substitution_prob``, ``insertion_prob`` or ``deletion_prob``
        is outside the range [0.0, 1.0] or if their sum exceeds 1.0.

    Returns
    -------
    str
        The mutated DNA sequence.
    """
    warnings.warn(
        "genecoder.error_simulation is deprecated; use genecoder.channel_engine stages instead",
        DeprecationWarning,
        stacklevel=2,
    )

    if not 0.0 <= substitution_prob <= 1.0:
        raise ValueError("substitution_prob must be between 0 and 1")
    if not 0.0 <= insertion_prob <= 1.0:
        raise ValueError("insertion_prob must be between 0 and 1")
    if not 0.0 <= deletion_prob <= 1.0:
        raise ValueError("deletion_prob must be between 0 and 1")
    if substitution_prob + insertion_prob + deletion_prob > 1.0:
        raise ValueError("sum of error probabilities must not exceed 1")

    if rng is None:
        rng = make_rng()

    mutated: list[str] = []
    for nt in sequence:
        if nt.upper() not in NUCLEOTIDES:
            mutated.append(nt)
            continue
        # deletion
        if rng.random() < deletion_prob:
            continue

        # substitution
        if rng.random() < substitution_prob:
            nt = _random_substitution(nt, rng)

        mutated.append(nt)

        # insertion after the (possibly substituted) nucleotide
        if rng.random() < insertion_prob:
            mutated.append(rng.choice(NUCLEOTIDES))

    return "".join(mutated)


# Backwards compatibility alias
introduce_errors = simulate_errors


def apply_substitutions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Apply random substitutions to ``sequence`` with probability ``prob``."""
    return simulate_errors(sequence, substitution_prob=prob, rng=rng)


def apply_insertions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Insert random nucleotides into ``sequence`` with probability ``prob``."""
    return simulate_errors(sequence, insertion_prob=prob, rng=rng)


def apply_deletions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    """Delete nucleotides from ``sequence`` with probability ``prob``."""
    return simulate_errors(sequence, deletion_prob=prob, rng=rng)




class Channel(Simulator):
    """Channel applying substitution, insertion and deletion errors.

    ``error_rate`` is a legacy convenience parameter. When provided, any unset
    substitution/insertion/deletion probabilities are set to the same clamped
    rate (0.0 to 1/3) so the total error probability never exceeds 1.0.
    """

    supports_batches = True

    def __init__(
        self,
        substitution_prob: float | None = None,
        insertion_prob: float | None = None,
        deletion_prob: float | None = None,
        error_rate: float | None = None,
        profile: str | None = None,
    ) -> None:
        warnings.warn(
            "Channel from genecoder.error_simulation is deprecated; use channel_engine stages via the channel pipeline",
            DeprecationWarning,
            stacklevel=2,
        )
        self._delegate: Simulator | None = None
        sub_prob = substitution_prob
        ins_prob = insertion_prob
        del_prob = deletion_prob

        if profile is not None:
            params = INDEL_PROFILES.get(profile.lower())
            if params is not None:
                sub_prob = params["substitution_prob"] if sub_prob is None else sub_prob
                ins_prob = params["insertion_prob"] if ins_prob is None else ins_prob
                del_prob = params["deletion_prob"] if del_prob is None else del_prob
            adapter = ADAPTER_PROFILES.get(profile.lower())
            if adapter is not None:
                family = adapter["family"]
                preset = adapter["profile"]
                if family == "illumina":
                    from .simulators.illumina import IlluminaChannel

                    self._delegate = IlluminaChannel(profile=str(preset))
                elif family == "nanopore":
                    from .simulators.nanopore import NanoporeChannel

                    self._delegate = NanoporeChannel(profile=str(preset))

        if error_rate is not None:
            clamped_rate = min(max(error_rate, 0.0), 1.0 / 3.0)
            sub_prob = clamped_rate if sub_prob is None else sub_prob
            ins_prob = clamped_rate if ins_prob is None else ins_prob
            del_prob = clamped_rate if del_prob is None else del_prob

        self._substitution_prob = 0.0 if sub_prob is None else sub_prob
        self.insertion_prob = 0.0 if ins_prob is None else ins_prob
        self.deletion_prob = 0.0 if del_prob is None else del_prob

    @property
    def substitution_prob(self) -> float:
        return self._substitution_prob

    @substitution_prob.setter
    def substitution_prob(self, value: float) -> None:
        self._substitution_prob = value

    # compatibility with older API expecting ``error_rate``
    @property
    def error_rate(self) -> float:
        warnings.warn(
            "Channel.error_rate is deprecated, use substitution_prob instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._substitution_prob

    @error_rate.setter
    def error_rate(self, value: float) -> None:
        warnings.warn(
            "Channel.error_rate is deprecated, use substitution_prob instead",
            DeprecationWarning,
            stacklevel=2,
        )
        clamped_rate = min(max(value, 0.0), 1.0 / 3.0)
        self._substitution_prob = clamped_rate
        self.insertion_prob = clamped_rate
        self.deletion_prob = clamped_rate

    def _simulate_string(self, sequence: str) -> str:
        if self._delegate is not None:
            return self._delegate.simulate(sequence)
        return simulate_errors(
            sequence,
            substitution_prob=self.substitution_prob,
            insertion_prob=self.insertion_prob,
            deletion_prob=self.deletion_prob,
            rng=make_rng(),
        )

    def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:
        if isinstance(sequence, SequenceBatch):
            return apply_legacy_simulator(sequence, self._simulate_string)
        return self._simulate_string(sequence)

    def with_profile(self, profile: str) -> "Channel":
        """Return a new channel configured to use ``profile``."""

        if profile.lower() not in INDEL_PROFILES:
            return type(self)(
                substitution_prob=self.substitution_prob,
                insertion_prob=self.insertion_prob,
                deletion_prob=self.deletion_prob,
            )
        return type(self)(profile=profile)


def register(
    registrar: Callable[[str, Simulator], None] = _register_simulator,
) -> None:
    """Register built-in error simulators."""

    registrar("simple", Channel(substitution_prob=0.05))
    registrar("indel", Channel())
    registrar("none", Channel())
