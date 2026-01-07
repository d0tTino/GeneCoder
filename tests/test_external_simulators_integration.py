"""Integration checks for optional external simulators."""

from __future__ import annotations

import shutil

import pytest

from genecoder import (
    d2sim_adapter,
    desp_adapter,
    dnarsim_adapter,
    insilicoseq_adapter,
    squigulator_adapter,
)


TEST_SEQUENCE = "ACGTACGTACGT"


@pytest.mark.skipif(shutil.which("d2sim") is None, reason="d2sim not installed")
def test_d2sim_integration() -> None:
    result = d2sim_adapter.simulate_d2sim(TEST_SEQUENCE, error_rate=0.1)

    assert isinstance(result, str)
    assert result


@pytest.mark.skipif(shutil.which("squigulator") is None, reason="squigulator not installed")
def test_squigulator_integration() -> None:
    result = squigulator_adapter.simulate_squigulator(TEST_SEQUENCE, error_rate=0.1)

    assert isinstance(result, str)
    assert result


@pytest.mark.skipif(shutil.which("dnarsim") is None, reason="dnarsim not installed")
def test_dnarsim_integration_with_profile() -> None:
    result = dnarsim_adapter.simulate_dnarsim(
        TEST_SEQUENCE,
        error_rate=0.1,
        profile="r9",
    )

    assert isinstance(result, str)
    assert result


@pytest.mark.skipif(shutil.which("insilicoseq") is None, reason="insilicoseq not installed")
def test_insilicoseq_integration_with_profile() -> None:
    result = insilicoseq_adapter.simulate_insilicoseq(
        TEST_SEQUENCE,
        error_rate=0.1,
        profile="miseq",
    )

    assert isinstance(result, str)
    assert result


@pytest.mark.skipif(shutil.which("desp") is None, reason="desp not installed")
def test_desp_integration() -> None:
    result = desp_adapter.simulate_desp(TEST_SEQUENCE, error_rate=0.1)

    assert isinstance(result, str)
    assert result
