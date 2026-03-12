from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Tuple

import pytest

from genecoder.simulators.calibration.workflow import evaluate_thresholds
from genecoder.simulators.nanopore import NanoporeChannel, NANOPORE_PROFILES
from genecoder.simulators.nanopore_batch import mutate_read, observe_error_rates


def _simulate_many(
    channel: NanoporeChannel, sequence: str, runs: int = 1000
) -> Tuple[float, float]:
    rng = random.Random(0)
    ins = 0
    dels = 0
    for _ in range(runs):
        mutated = mutate_read(sequence, None, rng, channel)
        if len(mutated) > len(sequence):
            ins += 1
        if len(mutated) < len(sequence):
            dels += 1
    return ins / runs, dels / runs


@pytest.mark.parametrize(
    "sequence, expected_bias",
    [("AAAAA", True), ("ACGTACGT", False)],
)
def test_context_indel_rates(tmp_path: Path, sequence: str, expected_bias: bool) -> None:
    profile_path = tmp_path / "nanopore_context.yaml"
    profile_path.write_text(
        "substitution_rate: 0.0\n"
        "insertion_rate: 0.0\n"
        "deletion_rate: 0.0\n"
        "context_indels:\n"
        "  AA:\n"
        "    5:\n"
        "      insertions: 0.5\n"
        "      deletions: 0.5\n"
    )
    channel = NanoporeChannel(profile_path=str(profile_path))

    ins_rate, del_rate = _simulate_many(channel, sequence)
    control_ins, control_del = _simulate_many(channel, "ACGTACGT")

    if expected_bias:
        assert ins_rate > control_ins
        assert del_rate > control_del
    else:
        assert ins_rate <= control_ins
        assert del_rate <= control_del


def test_builtin_profile_context_bias() -> None:
    channel = NanoporeChannel(profile="minion")
    poly_ins, poly_del = _simulate_many(channel, "AAAAA")
    control_ins, control_del = _simulate_many(channel, "ACGTACGT")
    assert poly_ins > control_ins
    assert poly_del > control_del


@pytest.mark.parametrize("profile", sorted(NANOPORE_PROFILES))
def test_nanopore_profile_error_rates(profile: str) -> None:
    channel = NanoporeChannel(profile=profile)
    sequence = "ACGT" * 256
    reads = int(max(1, channel.coverage)) * 40
    observation = observe_error_rates(channel, sequence, reads=reads, seed=1234)
    rates = observation.rates()
    expected = NANOPORE_PROFILES[profile]
    for key in ("substitution_rate", "insertion_rate", "deletion_rate"):
        tolerance = max(0.005, 0.3 * float(expected[key]))
        assert abs(rates[key] - float(expected[key])) <= tolerance


def test_calibration_threshold_evaluation_flags_violations(tmp_path: Path) -> None:
    threshold_path = tmp_path / "thresholds.json"
    threshold_path.write_text(
        json.dumps(
            {
                "calibration": {
                    "delta_thresholds": {
                        "substitution_delta": 0.001,
                        "insertion_delta": 0.001,
                        "deletion_delta": 0.001,
                        "dropout_delta": 0.001,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    evaluation = evaluate_thresholds(
        {
            "substitution_delta": 0.002,
            "insertion_delta": 0.0,
            "deletion_delta": 0.0,
            "dropout_delta": 0.0,
        },
        threshold_path=threshold_path,
    )

    assert evaluation.passed is False
    assert "substitution_delta" in evaluation.violations
