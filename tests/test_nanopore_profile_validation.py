from __future__ import annotations

import pytest

from genecoder.simulators.nanopore import NanoporeChannel


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"error_rate": 1.1}, "error_rate"),
        ({"substitution_rate": -0.1}, "substitution_rate"),
        ({"insertion_rate": "bad"}, "insertion_rate"),
        ({"deletion_rate": 2}, "deletion_rate"),
    ],
)
def test_invalid_base_rates(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        NanoporeChannel(**kwargs)


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"insertion_profile": {1: -0.1}}, "insertion_profile"),
        ({"deletion_profile": {"a": 0.2}}, "deletion_profile"),
        ({"context_insertions": {"AA": {1: 1.2}}}, "context_insertions"),
        ({"context_deletions": {"TT": {1: -0.2}}}, "context_deletions"),
        ({"context_insertions": {"AA": 0.5}}, "context_insertions"),
    ],
)
def test_invalid_profiles(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        NanoporeChannel(**kwargs)
