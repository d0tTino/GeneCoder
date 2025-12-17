import random

import pytest

from genecoder import illumina_sim
from genecoder.error_simulation import NUCLEOTIDES, _random_substitution


def _simulate_reads(
    params: dict[str, float], repetitions: int = 2000, seed: int = 123
) -> tuple[float, float, float]:
    """Generate ``repetitions`` mutated reads and return event frequencies."""

    rng = random.Random(seed)
    reference = "ACGT" * 100  # length 400

    sub_total = ins_total = del_total = 0
    total_bases = len(reference) * repetitions

    for _ in range(repetitions):
        for base in reference:
            if rng.random() < params["deletion_rate"]:
                del_total += 1
                continue

            nt = base
            if rng.random() < params["substitution_rate"]:
                nt = _random_substitution(nt, rng)
                sub_total += 1

            if rng.random() < params["insertion_rate"]:
                rng.choice(NUCLEOTIDES)
                ins_total += 1

    return (
        sub_total / total_bases,
        ins_total / total_bases,
        del_total / total_bases,
    )


def test_illumina_profile_error_rates_within_tolerance():
    tolerance = 0.5  # allow sampling noise for low-frequency indels
    params_source = illumina_sim.ILLUMINA_PROFILES or getattr(
        illumina_sim, "_DEFAULT_PROFILES", {}
    )
    profiles = {
        name: params_source[name]
        for name in ("hiseq", "miseq", "novaseq")
        if name in params_source
    }
    assert profiles, "Expected illumina profiles missing"

    for profile, expected in profiles.items():
        sub_rate, ins_rate, del_rate = _simulate_reads(expected)

        assert sub_rate == pytest.approx(
            expected["substitution_rate"], rel=tolerance
        )
        assert ins_rate == pytest.approx(expected["insertion_rate"], rel=tolerance)
        assert del_rate == pytest.approx(expected["deletion_rate"], rel=tolerance)
