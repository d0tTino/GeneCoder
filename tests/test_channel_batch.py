from __future__ import annotations

import json
from pathlib import Path

import pytest

from genecoder.channel_config import ChannelConfig
from genecoder.cli.channel import process_channel
from genecoder.error_simulation import Channel as LegacyChannel
from genecoder.formats import SequenceBatch
from genecoder.simulators import (
    SIMULATOR_REGISTRY,
    ChannelPipeline,
    register_simulator,
)
from genecoder.simulators.batch_utils import (
    CONFIG_COVERAGE_KEY,
    CONFIG_DROPOUT_KEY,
    CONFIG_SYNTHESIS_KEY,
    RESULT_COVERAGE_KEY,
    RESULT_DROPOUT_FLAG_KEY,
    RESULT_MUTATION_LOG_KEY,
    RESULT_SYNTHESIS_FLAG_KEY,
)
from genecoder.simulators.illumina import IlluminaChannel


def _build_batch() -> SequenceBatch:
    return SequenceBatch.build(
        [
            ("oligo-1", "ACGTACGT"),
            ("oligo-2", "TGCATGCA"),
        ],
        batch_id="test-batch",
    )


def test_illumina_batch_dropout_statistics() -> None:
    batch = _build_batch()
    batch.metadata[CONFIG_DROPOUT_KEY] = "1.0"

    channel = IlluminaChannel()
    result = channel.simulate(batch)

    assert all(ol.sequence == "" for ol in result.oligos)
    assert all(ol.metadata[RESULT_DROPOUT_FLAG_KEY] == "true" for ol in result.oligos)

    histogram = json.loads(result.metadata["sim_coverage_histogram"])
    assert histogram == {"0": len(batch.oligos)}
    assert result.metadata["sim_dropout_total"] == str(len(batch.oligos))
    assert result.metadata["sim_dropout_fraction"] == "1.000000"


def test_illumina_batch_coverage_histogram() -> None:
    batch = _build_batch()
    batch.metadata[CONFIG_COVERAGE_KEY] = json.dumps({3: 1.0})

    channel = IlluminaChannel()
    result = channel.simulate(batch)

    for oligo in result.oligos:
        assert oligo.metadata[RESULT_COVERAGE_KEY] == "3"
        reads = json.loads(oligo.metadata[RESULT_MUTATION_LOG_KEY])
        assert len(reads) == 3

    histogram = json.loads(result.metadata["sim_coverage_histogram"])
    assert histogram == {"3": len(batch.oligos)}
    assert result.metadata["sim_total_reads"] == str(3 * len(batch.oligos))


def test_pipeline_records_synthesis_failures() -> None:
    batch = _build_batch()
    batch.metadata[CONFIG_SYNTHESIS_KEY] = "1.0"

    pipeline = ChannelPipeline([IlluminaChannel()])
    config = ChannelConfig(synthesis_loss=1.0)
    result = pipeline.simulate(batch, config=config)

    assert all(ol.metadata[RESULT_SYNTHESIS_FLAG_KEY] == "true" for ol in result.oligos)
    assert result.metadata["sim_synthesis_failures"] == str(len(batch.oligos))
    assert result.metadata["sim_synthesis_fraction"] == "1.000000"


def test_process_channel_enforces_constraints(tmp_path: Path) -> None:
    fasta = tmp_path / "input.fasta"
    fasta.write_text(">ol1\nACGTACGT\n>ol2\nTGCATGCA\n", encoding="utf-8")
    output = tmp_path / "output.fasta"

    with pytest.raises(ValueError):
        process_channel(
            str(fasta),
            str(output),
            [],
            {"min_length": 1, "max_length": 3, "max_homopolymer": 10},
            sub_prob=0.0,
            ins_prob=0.0,
            del_prob=0.0,
            config=ChannelConfig(),
        )


def test_legacy_simulator_adapter_adds_metadata() -> None:
    batch = _build_batch()
    name = "legacy_batch_adapter_test"
    register_simulator(name, LegacyChannel())
    try:
        entry = SIMULATOR_REGISTRY[name]
        channel = type(entry)(
            substitution_prob=0.0, insertion_prob=0.0, deletion_prob=0.0
        )
        result = channel.simulate(batch)

        for oligo in result.oligos:
            assert oligo.metadata[RESULT_COVERAGE_KEY] == "1"
            assert oligo.metadata[RESULT_DROPOUT_FLAG_KEY] == "false"
            logs = json.loads(oligo.metadata[RESULT_MUTATION_LOG_KEY])
            assert logs == [
                {
                    "read": oligo.sequence,
                    "substitutions": 0,
                    "insertions": 0,
                    "deletions": 0,
                }
            ]
    finally:
        SIMULATOR_REGISTRY.pop(name, None)
