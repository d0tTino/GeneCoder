from __future__ import annotations

import json
import os

import pytest

from genecoder.channel_config import ChannelConfig
from genecoder.channel_engine import ChannelPipeline as RuntimePipeline
from genecoder.error_simulation import Channel as LegacyErrorChannel
from genecoder.formats import SequenceBatch
from genecoder.simulators.decay import DegradationChannel
from genecoder.simulators.illumina import IlluminaChannel
from genecoder.simulators.nanopore import NanoporeChannel
from genecoder.simulators.pipeline import ChannelPipeline as LegacyPipeline


@pytest.mark.parametrize(
    ("name", "simulator"),
    [
        ("illumina", IlluminaChannel(profile="miseq")),
        ("nanopore", NanoporeChannel(profile="r10.4")),
        ("decay", DegradationChannel(deletion_prob=0.01, substitution_prob=0.02)),
    ],
)
def test_runtime_matches_legacy_pipeline_for_presets(name: str, simulator: object) -> None:
    batch = SequenceBatch.build([("oligo-1", "ACGTACGTACGT")], batch_id=f"{name}-batch")
    config = ChannelConfig()
    os.environ["GENECODER_SIM_SEED"] = "123"

    legacy = LegacyPipeline([simulator])
    legacy_result = legacy.simulate(batch, config=config)
    assert isinstance(legacy_result, SequenceBatch)

    runtime = RuntimePipeline.from_simulators([(name, simulator)])
    runtime_result, provenance = runtime.run(batch, seed=123)

    assert [o.sequence for o in runtime_result.oligos] == [o.sequence for o in legacy_result.oligos]
    assert json.loads(runtime_result.metadata.get("sim_mutation_totals", "{}")) == json.loads(
        legacy_result.metadata.get("sim_mutation_totals", "{}")
    )
    assert provenance


def test_legacy_error_channel_routes_to_runtime_consistently() -> None:
    channel = LegacyErrorChannel(substitution_prob=0.1, insertion_prob=0.05, deletion_prob=0.03)
    batch = SequenceBatch.build([("oligo-1", "ACGTACGT")], batch_id="legacy")

    out_a = channel.simulate(batch)
    out_b = channel.simulate(batch)

    assert isinstance(out_a, SequenceBatch)
    assert isinstance(out_b, SequenceBatch)
    assert len(out_a.oligos) == len(out_b.oligos)
