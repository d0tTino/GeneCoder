from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from genecoder.channel_sim import Channel
from genecoder.channel_config import ChannelConfig
from genecoder.simulators.pipeline import ChannelPipeline
from genecoder.channels.base import BaseChannel


def test_parallel_pipeline_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    monkeypatch.setenv("GENECODER_METRICS_PATH", str(tmp_path / "m.json"))
    pipeline = ChannelPipeline([Channel(0.1), Channel(0.2)])
    seq = "ACGTACGTACGT"
    serial = pipeline.simulate(seq)
    cfg_threads = ChannelConfig(parallel=True, workers=2)
    parallel = pipeline.simulate(seq, config=cfg_threads)

    expected = Channel(0.2).simulate(seq)
    assert serial != parallel
    assert parallel == expected


class _DelayChannel(BaseChannel):
    def __init__(self, delay: float) -> None:
        self.delay = delay

    def simulate(self, sequence: str) -> str:
        import time

        time.sleep(self.delay)
        return sequence


def test_parallel_pipeline_concurrent(tmp_path: Path) -> None:
    pipeline = ChannelPipeline([_DelayChannel(0.1), _DelayChannel(0.1)])
    os.environ["GENECODER_METRICS_PATH"] = str(tmp_path / "m.json")
    seq = "AAAA"

    start = time.perf_counter()
    pipeline.simulate(seq)
    serial_time = time.perf_counter() - start

    cfg = ChannelConfig(parallel=True, workers=2)
    start = time.perf_counter()
    pipeline.simulate(seq, config=cfg)
    parallel_time = time.perf_counter() - start

    assert parallel_time < serial_time * 0.75


