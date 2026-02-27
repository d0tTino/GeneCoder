"""Compatibility utilities for simulating random sequencing errors in DNA sequences."""
from __future__ import annotations

import random
import warnings
from typing import Callable

from genecoder.random_utils import make_rng
from genecoder.plugin_api import Simulator
from genecoder.simulators import register_simulator as _register_simulator
from genecoder.formats import SequenceBatch
from genecoder.channel_engine import ChannelPipeline as RuntimeChannelPipeline
from genecoder.simulators.mutation_primitives import NUCLEOTIDES, random_substitution

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
    "NUCLEOTIDES",
    "_random_substitution",
]

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
INDEL_PROFILES = {**LEGACY_INDEL_PROFILES, **{name: profile["fallback"] for name, profile in ADAPTER_PROFILES.items()}}
DEFAULT_ADAPTER_PROFILE = "illumina_adapter"


def _random_substitution(nucleotide: str, rng: random.Random) -> str:
    return random_substitution(nucleotide, rng)


def _simulate_via_channel_graph(sequence: str, *, substitution_prob: float, insertion_prob: float, deletion_prob: float, rng: random.Random | None = None) -> str:
    runtime_rng = rng or make_rng()

    class _InlineErrorSimulator:
        supports_batches = False

        def simulate(self, seq: str) -> str:
            mutated: list[str] = []
            for nt in seq:
                if nt.upper() not in NUCLEOTIDES:
                    mutated.append(nt)
                    continue
                if runtime_rng.random() < deletion_prob:
                    continue
                if runtime_rng.random() < substitution_prob:
                    nt = random_substitution(nt, runtime_rng)
                mutated.append(nt)
                if runtime_rng.random() < insertion_prob:
                    mutated.append(runtime_rng.choice(NUCLEOTIDES))
            return "".join(mutated)

    runtime = RuntimeChannelPipeline.from_simulators([("indel", _InlineErrorSimulator())])
    batch = SequenceBatch.build([("error-sim", sequence)], batch_id="error-sim")
    simulated, _ = runtime.run(batch)
    return simulated.oligos[0].sequence if simulated.oligos else ""


def simulate_errors(sequence: str, substitution_prob: float = 0.0, insertion_prob: float = 0.0, deletion_prob: float = 0.0, rng: random.Random | None = None) -> str:
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
    return _simulate_via_channel_graph(
        sequence,
        substitution_prob=substitution_prob,
        insertion_prob=insertion_prob,
        deletion_prob=deletion_prob,
        rng=rng,
    )


introduce_errors = simulate_errors


def apply_substitutions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    return simulate_errors(sequence, substitution_prob=prob, rng=rng)


def apply_insertions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    return simulate_errors(sequence, insertion_prob=prob, rng=rng)


def apply_deletions(sequence: str, prob: float, rng: random.Random | None = None) -> str:
    return simulate_errors(sequence, deletion_prob=prob, rng=rng)


class Channel(Simulator):
    supports_batches = True

    def __init__(self, substitution_prob: float | None = None, insertion_prob: float | None = None, deletion_prob: float | None = None, error_rate: float | None = None, profile: str | None = None) -> None:
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

    @property
    def error_rate(self) -> float:
        warnings.warn("Channel.error_rate is deprecated, use substitution_prob instead", DeprecationWarning, stacklevel=2)
        return self._substitution_prob

    @error_rate.setter
    def error_rate(self, value: float) -> None:
        warnings.warn("Channel.error_rate is deprecated, use substitution_prob instead", DeprecationWarning, stacklevel=2)
        clamped_rate = min(max(value, 0.0), 1.0 / 3.0)
        self._substitution_prob = clamped_rate
        self.insertion_prob = clamped_rate
        self.deletion_prob = clamped_rate

    def _simulate_string(self, sequence: str) -> str:
        return _simulate_via_channel_graph(
            sequence,
            substitution_prob=self.substitution_prob,
            insertion_prob=self.insertion_prob,
            deletion_prob=self.deletion_prob,
            rng=make_rng(),
        )

    def simulate(self, sequence: str | SequenceBatch) -> str | SequenceBatch:
        class _ChannelShim:
            supports_batches = False

            def __init__(self, fn: Callable[[str], str]) -> None:
                self._fn = fn

            def simulate(self, seq: str) -> str:
                return self._fn(seq)

        runtime = RuntimeChannelPipeline.from_simulators([("indel", _ChannelShim(self._simulate_string))])
        if isinstance(sequence, SequenceBatch):
            result, _ = runtime.run(sequence)
            return result
        batch = SequenceBatch.build([("channel", sequence)], batch_id="channel")
        result, _ = runtime.run(batch)
        return result.oligos[0].sequence if result.oligos else ""

    def with_profile(self, profile: str) -> "Channel":
        if profile.lower() not in INDEL_PROFILES:
            return type(self)(substitution_prob=self.substitution_prob, insertion_prob=self.insertion_prob, deletion_prob=self.deletion_prob)
        return type(self)(profile=profile)


def register(registrar: Callable[[str, Simulator], None] = _register_simulator) -> None:
    registrar("simple", Channel(substitution_prob=0.05))
    registrar("indel", Channel())
    registrar("none", Channel())
