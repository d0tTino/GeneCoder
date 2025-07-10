import argparse
from pathlib import Path

import pytest

from src.genecoder.cli.options import build_channel_options


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = dict(
        simulators=[],
        sub_prob=0.0,
        ins_prob=0.0,
        del_prob=0.0,
        seed=None,
        parallel=False,
        threads=None,
        processes=None,
        mpi=False,
        mpi_workers=None,
        config=None,
        min_length=1,
        max_length=300,
        max_homopolymer=4,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_only_simulators_ok() -> None:
    args = _make_args(simulators=["simple"])
    opts = build_channel_options(args)
    assert opts.simulators == ["simple"]


def test_only_probabilities_ok() -> None:
    args = _make_args(sub_prob=0.1)
    opts = build_channel_options(args)
    assert opts.sub_prob == 0.1


def test_simulators_and_probabilities_error() -> None:
    args = _make_args(simulators=["simple"], sub_prob=0.1)
    with pytest.raises(ValueError, match="Probability options cannot"):
        build_channel_options(args)


def test_no_simulators_or_probabilities_error() -> None:
    args = _make_args()
    with pytest.raises(ValueError, match="At least one simulator"):
        build_channel_options(args)


def test_config_and_probabilities_error(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("simulators:\n  - simple\n")
    args = _make_args(config=str(cfg), sub_prob=0.1)
    with pytest.raises(ValueError, match="Probability options cannot"):
        build_channel_options(args)

