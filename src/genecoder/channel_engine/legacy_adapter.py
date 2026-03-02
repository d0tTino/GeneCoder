"""Legacy error-simulation adapter routed through :mod:`genecoder.channel_engine`."""
from __future__ import annotations

import random
import warnings
from typing import Callable

from genecoder.plugin_api import Simulator
from genecoder.formats import SequenceBatch
from genecoder.random_utils import make_rng
from genecoder.simulators import register_simulator as _register_simulator
from genecoder.simulators.mutation_primitives import NUCLEOTIDES, random_substitution

from .pipeline import ChannelPipeline

LEGACY_INDEL_PROFILES = {
    "illumina": {"substitution_prob": 0.002, "insertion_prob": 0.0001, "deletion_prob": 0.0001},
    "nanopore": {"substitution_prob": 0.01, "insertion_prob": 0.02, "deletion_prob": 0.02},
}
ADAPTER_PROFILES = {
    "illumina_adapter": {
        "family": "illumina",
        "profile": "miseq_v3",
        "fallback": {"substitution_prob": 0.0009, "insertion_prob": 0.0001, "deletion_prob": 0.0001},
    },
    "nanopore_adapter": {
        "family": "nanopore",
        "profile": "r10.4",
        "fallback": {"substitution_prob": 0.045, "insertion_prob": 0.015, "deletion_prob": 0.025},
    },
}
INDEL_PROFILES = {
    **LEGACY_INDEL_PROFILES,
    **{name: profile["fallback"] for name, profile in ADAPTER_PROFILES.items()},
}
DEFAULT_ADAPTER_PROFILE = "illumina_adapter"


class _InlineErrorSimulator:
    supports_batches = False

    def __init__(self, *, substitution_prob: float, insertion_prob: float, deletion_prob: float, rng: random.Random) -> None:
        self.substitution_prob = substitution_prob
        self.insertion_prob = insertion_prob
        self.deletion_prob = deletion_prob
        self.rng = rng

    def simulate(self, seq: str) -> str:
        mutated: list[str] = []
        for nt in seq:
            if nt.upper() not in NUCLEOTIDES:
                mutated.append(nt)
                continue
            if self.rng.random() < self.deletion_prob:
                continue
            if self.rng.random() < self.substitution_prob:
                nt = random_substitution(nt, self.rng)
            mutated.append(nt)
            if self.rng.random() < self.insertion_prob:
                mutated.append(self.rng.choice(NUCLEOTIDES))
        return "".join(mutated)


def simulate_errors(sequence: str, substitution_prob: float = 0.0, insertion_prob: float = 0.0, deletion_prob: float = 0.0, rng: random.Random | None = None) -> str:
    warnings.warn(
        "genecoder.error_simulation is deprecated; use genecoder.channel_engine stages instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if substitution_prob + insertion_prob + deletion_prob > 1.0:
        raise ValueError("sum of error probabilities must not exceed 1")
    runtime_rng = rng or make_rng()
    runtime = ChannelPipeline.from_simulators(
        [
            (
                "indel",
                _InlineErrorSimulator(
                    substitution_prob=substitution_prob,
                    insertion_prob=insertion_prob,
                    deletion_prob=deletion_prob,
                    rng=runtime_rng,
                ),
            )
        ]
    )
    batch = SequenceBatch.build([("error-sim", sequence)], batch_id="error-sim")
    simulated, _ = runtime.run(batch)
    return simulated.oligos[0].sequence if simulated.oligos else ""


introduce_errors = simulate_errors


def apply_substitutions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    return simulate_errors(sequence, substitution_prob=prob, rng=rng)


def apply_insertions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    return simulate_errors(sequence, insertion_prob=prob, rng=rng)


def apply_deletions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    return simulate_errors(sequence, deletion_prob=prob, rng=rng)


class Channel(Simulator):
    supports_batches = True

    def __init__(self, substitution_prob: float = 0.0, insertion_prob: float = 0.0, deletion_prob: float = 0.0, error_rate: float | None = None, profile: str | None = None) -> None:
        if profile and profile.lower() in INDEL_PROFILES:
            params = INDEL_PROFILES[profile.lower()]
            substitution_prob = params["substitution_prob"]
            insertion_prob = params["insertion_prob"]
            deletion_prob = params["deletion_prob"]
        if error_rate is not None:
            rate = min(max(error_rate, 0.0), 1.0 / 3.0)
            substitution_prob = insertion_prob = deletion_prob = rate
        self.substitution_prob = substitution_prob
        self.insertion_prob = insertion_prob
        self.deletion_prob = deletion_prob

    def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:
        def _run(seq: str) -> str:
            return simulate_errors(
                seq,
                substitution_prob=self.substitution_prob,
                insertion_prob=self.insertion_prob,
                deletion_prob=self.deletion_prob,
                rng=make_rng(),
            )

        if isinstance(sequence, SequenceBatch):
            runtime = ChannelPipeline.from_simulators([("indel", type("_S", (), {"supports_batches": False, "simulate": staticmethod(_run)})())])
            out, _ = runtime.run(sequence)
            return out
        return _run(sequence)

    def with_profile(self, profile: str) -> "Channel":
        return type(self)(profile=profile)


def register(registrar: Callable[[str, Simulator], None] = _register_simulator) -> None:
    registrar("simple", Channel(substitution_prob=0.05))
    registrar("indel", Channel())
    registrar("none", Channel())
