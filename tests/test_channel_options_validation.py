import argparse
from pathlib import Path

import pytest
pytest.importorskip("yaml")


from src.genecoder.cli.options import build_channel_options


def _make_args(**kwargs: object) -> argparse.Namespace:
    defaults = dict(
        simulators=[],
        sub_prob=0.0,
        ins_prob=0.0,
        del_prob=0.0,
        seed=None,
        parallel=False,
        threads=None,
        processes=None,
        batch_workers=None,
        config=None,
        min_length=1,
        max_length=300,
        max_homopolymer=4,
        illumina_depth=None,
        nanopore_depth=None,
        illumina_quality=None,
        nanopore_quality=None,
        illumina_context=None,
        nanopore_context=None,
        illumina_sub_rate=None,
        illumina_ins_rate=None,
        illumina_del_rate=None,
        nanopore_sub_rate=None,
        nanopore_ins_rate=None,
        nanopore_del_rate=None,
        illumina_profile=None,
        nanopore_profile=None,
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
    cfg.write_text("simulators:\n  - name: simple\n")
    args = _make_args(config=str(cfg), sub_prob=0.1)
    with pytest.raises(ValueError, match="Probability options cannot"):
        build_channel_options(args)


def test_threads_and_processes_conflict() -> None:
    args = _make_args(simulators=["simple"], threads=2, processes=2)
    with pytest.raises(ValueError, match="Cannot specify both --threads and --processes"):
        build_channel_options(args)




def test_config_missing_simulators_error(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yml"
    cfg.write_text("synthesis:\n  max_length: 200\n")
    args = _make_args(config=str(cfg))
    with pytest.raises(ValueError, match="At least one simulator"):
        build_channel_options(args)




def test_min_length_invalid() -> None:
    args = _make_args(simulators=["simple"], min_length=0)
    with pytest.raises(ValueError, match="min_length"):
        build_channel_options(args)


def test_min_length_negative() -> None:
    args = _make_args(simulators=["simple"], min_length=-1)
    with pytest.raises(ValueError, match="min_length"):
        build_channel_options(args)


def test_max_length_invalid() -> None:
    args = _make_args(simulators=["simple"], max_length=0)
    with pytest.raises(ValueError, match="max_length"):
        build_channel_options(args)


def test_max_length_negative() -> None:
    args = _make_args(simulators=["simple"], max_length=-1)
    with pytest.raises(ValueError, match="max_length"):
        build_channel_options(args)


def test_min_length_greater_than_max() -> None:
    args = _make_args(simulators=["simple"], min_length=10, max_length=5)
    with pytest.raises(ValueError, match="min_length cannot be greater"):
        build_channel_options(args)


def test_batch_workers_invalid() -> None:
    args = _make_args(simulators=["simple"], batch_workers=0)
    with pytest.raises(ValueError, match="batch_workers"):
        build_channel_options(args)

