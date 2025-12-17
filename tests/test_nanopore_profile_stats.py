import random

import pytest

from genecoder.simulators import nanopore
from genecoder.simulators.error_metrics import MutationObservation
from genecoder.simulators.nanopore_batch import mutate_read_jit


def _simulate_reads(
    profile: str, repetitions: int = 500, seed: int = 321
) -> tuple[float, float, float]:
    params = nanopore.NANOPORE_PROFILES[profile]
    channel = nanopore.NanoporeChannel(
        substitution_rate=params.get("substitution_rate", 0.0),
        insertion_rate=params.get("insertion_rate", 0.0),
        deletion_rate=params.get("deletion_rate", 0.0),
        coverage=1,
    )
    channel.coverage = 1  # avoid consensus smoothing
    rng = random.Random(seed)
    reference = "ACGT" * 50

    observation = MutationObservation()

    for _ in range(repetitions):
        mutate_read_jit(  # type: ignore[arg-type]
            reference,
            None,
            rng,
            channel.substitution_rate,
            channel.insertion_rate,
            channel.deletion_rate,
            {},
            {},
            {},
            {},
            {},
            observation,
        )

    rates = observation.rates()
    return (
        rates["substitution_rate"],
        rates["insertion_rate"],
        rates["deletion_rate"],
    )


def test_nanopore_profile_error_rates_within_tolerance():
    tolerance = 0.15
    profiles = {
        name: nanopore.NANOPORE_PROFILES[name]
        for name in ("minion", "promethion", "r10")
        if name in nanopore.NANOPORE_PROFILES
    }
    assert profiles, "Expected nanopore profiles missing"

    for profile, expected in profiles.items():
        sub_rate, ins_rate, del_rate = _simulate_reads(profile)

        assert sub_rate == pytest.approx(
            expected["substitution_rate"], rel=tolerance
        )
        assert ins_rate == pytest.approx(expected["insertion_rate"], rel=tolerance)
        assert del_rate == pytest.approx(expected["deletion_rate"], rel=tolerance)
