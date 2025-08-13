from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from genecoder.channel_sim import Channel
from genecoder.channel_config import ChannelConfig
from genecoder.simulators.pipeline import ChannelPipeline
from genecoder.channels.base import BaseChannel
from genecoder.random_utils import reset_rng


def test_parallel_pipeline_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(tmp_path / "m.json"))
    pipeline = ChannelPipeline([Channel(0.1), Channel(0.2)])
    seq = "ACGTACGTACGT"
    reset_rng()
    serial = pipeline.simulate(seq)
    cfg_threads = ChannelConfig(parallel=True, workers=2)
    reset_rng()
    parallel = pipeline.simulate(seq, config=cfg_threads)

    assert serial == parallel


class _DelayChannel(BaseChannel):
    def __init__(self, delay: float) -> None:
        self.delay = delay

    def simulate(self, sequence: str) -> str:
        import time

        time.sleep(self.delay)
        return sequence


def test_parallel_pipeline_concurrent(tmp_path: Path) -> None:
    pipeline = ChannelPipeline([_DelayChannel(0.1)])
    os.environ["GENECODER_METRICS_PATH"] = str(tmp_path / "m.json")
    seqs = ["AAAA", "TTTT", "CCCC", "GGGG"]

    start = time.perf_counter()
    for s in seqs:
        pipeline.simulate(s)
    serial_time = time.perf_counter() - start

    cfg = ChannelConfig(parallel=True, workers=2)
    from genecoder.parallel import parallel_map
    start = time.perf_counter()
    parallel_map(lambda s: pipeline.simulate(s, config=cfg), seqs, workers=2)
    parallel_time = time.perf_counter() - start

    assert parallel_time < serial_time * 0.75


def test_parallel_pipeline_multi_channel_concurrent(tmp_path: Path) -> None:
    """Ensure multiple sequences run concurrently when parallel=True."""
    pipeline = ChannelPipeline([_DelayChannel(0.1)])
    os.environ["GENECODER_METRICS_PATH"] = str(tmp_path / "m.json")
    seqs = ["AAAA", "CCCC", "GGGG", "TTTT", "ACAC", "TGTG"]

    start = time.perf_counter()
    for s in seqs:
        pipeline.simulate(s)
    serial_time = time.perf_counter() - start

    cfg = ChannelConfig(parallel=True, workers=3)
    from genecoder.parallel import parallel_map
    start = time.perf_counter()
    parallel_map(lambda s: pipeline.simulate(s, config=cfg), seqs, workers=3)
    parallel_time = time.perf_counter() - start

    # Allow a bit more leeway for slower CI environments
    assert parallel_time < serial_time * 0.75


