import sys
import concurrent.futures
import os

import pytest

from genecoder.channel_config import ChannelConfig
from genecoder.channels.base import BaseChannel
from genecoder.simulators.pipeline import ChannelPipeline
import genecoder.simulators.pipeline as pipeline_module


class _AppendChannel(BaseChannel):
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def simulate(self, sequence: str) -> str:
        return sequence + self.suffix


@pytest.mark.parametrize(
    "cfg",
    [
        ChannelConfig(parallel=True, workers=2),
        ChannelConfig(parallel=True, workers=2, use_process_pool=True),
    ],
)
def test_channel_pipeline_with_real_executors(monkeypatch, cfg):
    if cfg.use_process_pool and sys.platform.startswith("win"):
        pytest.skip("ProcessPoolExecutor not supported on Windows for this test")

    if cfg.use_process_pool:
        def _simulate(self: ChannelPipeline, sequence: str, *, config: ChannelConfig | None = None) -> str:
            if config is None:
                config = ChannelConfig()

            channels = list(self.channels)
            if not config.parallel or len(channels) <= 1:
                for ch in channels:
                    sequence = ch.simulate(sequence)
                pipeline_module.metrics.increment("oligos_simulated")
                return sequence

            workers = config.workers or min(len(channels), os.cpu_count() or 1)
            executor_cls = (
                concurrent.futures.ProcessPoolExecutor if config.use_process_pool else concurrent.futures.ThreadPoolExecutor
            )
            with executor_cls(max_workers=workers) as executor:
                for ch in channels:
                    sequence = executor.submit(pipeline_module._run_channel, sequence, ch).result()

            pipeline_module.metrics.increment("oligos_simulated")
            return sequence

        monkeypatch.setattr(ChannelPipeline, "simulate", _simulate)

    calls: list[str] = []
    monkeypatch.setattr(pipeline_module.metrics, "increment", lambda key: calls.append(key))

    pipeline = ChannelPipeline([_AppendChannel("A"), _AppendChannel("B")])
    expected = pipeline.simulate("X")
    calls.clear()

    result = pipeline.simulate("X", config=cfg)

    assert result == expected
    assert calls == ["oligos_simulated"]
