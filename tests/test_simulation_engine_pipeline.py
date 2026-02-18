from __future__ import annotations

import json

from genecoder.channel_config import ChannelConfig
from genecoder.channels.base import BaseChannel
from genecoder.formats import SequenceBatch
from genecoder.simulators.pipeline import ChannelPipeline


class _AppendChannel(BaseChannel):
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def simulate(self, sequence: str) -> str:
        return sequence + self.suffix


def test_channel_pipeline_records_structured_stage_metrics() -> None:
    pipeline = ChannelPipeline([_AppendChannel("A")])
    result = pipeline.simulate("X", config=ChannelConfig(dropout_rate=0.0, synthesis_loss=0.0))
    assert result == "XA"
    assert [m.stage for m in pipeline.last_stage_metrics] == ["synthesis", "storage_decay", "sequencing"]


def test_channel_pipeline_batch_contains_stage_metrics_json() -> None:
    pipeline = ChannelPipeline([_AppendChannel("A")])
    batch = SequenceBatch.build([("id", "X")], batch_id="b")
    out = pipeline.simulate(batch, config=ChannelConfig())
    assert isinstance(out, SequenceBatch)
    payload = json.loads(out.metadata["sim_stage_metrics"])
    assert [entry["stage"] for entry in payload] == ["synthesis", "storage_decay", "sequencing"]
