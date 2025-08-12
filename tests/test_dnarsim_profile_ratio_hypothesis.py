import pytest

pytest.importorskip("hypothesis")

from difflib import SequenceMatcher

from hypothesis import given, strategies as st

from genecoder.error_simulation import NUCLEOTIDES
from genecoder.simulators.nanopore import (
    NanoporeDNArSimChannel,
    DNARSIM_RATE_TABLES,
)


def _error_counts(original: str, mutated: str) -> tuple[int, int, int]:
    matcher = SequenceMatcher(a=original, b=mutated)
    subs = ins = dele = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            subs += max(i2 - i1, j2 - j1)
        elif tag == "insert":
            ins += j2 - j1
        elif tag == "delete":
            dele += i2 - i1
    return subs, ins, dele


@given(seq=st.text(alphabet=st.sampled_from(NUCLEOTIDES), min_size=200, max_size=400))
@pytest.mark.parametrize("profile", list(DNARSIM_RATE_TABLES.keys()))
def test_dnarsim_profile_sub_indel_ratio(seq: str, profile: str) -> None:
    channel = NanoporeDNArSimChannel(profile=profile)
    mutated = channel.simulate(seq)
    subs, ins, dele = _error_counts(seq, mutated)
    assert subs + ins + dele > 0
    observed_ratio = subs / (ins + dele)

    rates = DNARSIM_RATE_TABLES[profile]
    base_sub = 0.4 * channel.error_rate
    base_ins = base_del = 0.3 * channel.error_rate
    expected_sub = base_sub + rates["substitution_rate"]
    expected_indel = base_ins + rates["insertion_rate"] + base_del + rates["deletion_rate"]
    expected_ratio = expected_sub / expected_indel

    assert observed_ratio == pytest.approx(expected_ratio, rel=0.3)
