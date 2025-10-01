from __future__ import annotations

import random
from dataclasses import replace
from pathlib import Path

import pytest

from genecoder.encoders import decode_base4_direct, encode_base4_direct
from genecoder.formats import SequenceBatch
from genecoder.reed_solomon_codec import ReedSolomonFEC, _HAS_REEDSOLO
from genecoder.fountain_codec import (
    FountainFEC,
    droplet_batch_to_bytes,
    encode_data_fountain,
)
from genecoder.cli.channel import process_channel
from genecoder.channel_config import ChannelConfig
from genecoder.simulators.illumina import IlluminaChannel


@pytest.mark.slow
@pytest.mark.skipif(not _HAS_REEDSOLO, reason="reedsolo not installed")
def test_reed_solomon_multi_oligo_correction(
    mock_coverage_distribution, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mutate Reed--Solomon encoded oligos and ensure decoding succeeds."""

    monkeypatch.setenv("GENECODER_SIM_SEED", "314159")

    data = b"multi-oligo reed solomon integration"
    fec = ReedSolomonFEC()
    encoded_bytes, info = fec.encode(data, nsym=32)

    rng = random.Random(1234)
    mutated_bytes = bytearray(encoded_bytes)
    error_positions = rng.sample(range(len(mutated_bytes)), k=min(4, len(mutated_bytes)))
    for pos in error_positions:
        mutated_bytes[pos] ^= 0x01

    dna_payload = encode_base4_direct(bytes(mutated_bytes))
    batch = SequenceBatch.build(
        [("integration", dna_payload)], batch_id="rs", max_oligo_length=96
    )
    assert len(batch.oligos) > 1

    recovered_dna = "".join(ol.sequence for ol in batch.oligos)
    roundtrip_bytes = decode_base4_direct(recovered_dna)[0]
    decoded, corrections = fec.decode(roundtrip_bytes, info)

    assert decoded == data
    assert corrections >= len(error_positions)


@pytest.mark.slow
def test_fountain_multi_oligo_dropout_recovery(
    mock_coverage_distribution, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drop and perturb Fountain droplets while maintaining successful decode."""

    monkeypatch.setenv("GENECODER_SIM_SEED", "271828")

    data = b"multi-oligo fountain integration payload" * 2
    batch, info = encode_data_fountain(
        data,
        chunk_size=6,
        seed=7,
        redundancy=2.2,
    )
    assert len(batch.oligos) > int(info["k"])

    rng = random.Random(4321)
    total = len(batch.oligos)
    required = int(info["k"])
    max_drop = max(0, total - required)
    drop_count = min(max(1, total // 5), max_drop)
    drop_indices = set(rng.sample(range(total), drop_count)) if drop_count else set()

    survivors = [
        replace(oligo, metadata=dict(oligo.metadata))
        for idx, oligo in enumerate(batch.oligos)
        if idx not in drop_indices
    ]

    mutated_batch = SequenceBatch(
        batch_id=batch.batch_id,
        metadata=dict(batch.metadata),
        seed=batch.seed,
        oligos=survivors,
    )

    assert len(mutated_batch.oligos) >= required
    assert len(mutated_batch.oligos) <= len(batch.oligos)

    mutated_info = dict(info)
    mutated_info["droplet_count"] = len(mutated_batch.oligos)
    encoded_stream = droplet_batch_to_bytes(mutated_batch)
    decoded, _ = FountainFEC().decode(encoded_stream, mutated_info)

    assert decoded == data
    assert drop_indices


@pytest.mark.slow
def test_channel_synthesis_constraint_violation(
    mock_coverage_distribution, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure channel processing rejects oligos violating synthesis constraints."""

    monkeypatch.setenv("GENECODER_SIM_SEED", "424242")

    fasta_path = tmp_path / "input.fasta"
    fasta_path.write_text(
        ">oligo1\n" + "A" * 48 + "\n>oligo2\n" + "CG" * 12 + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "output.fasta"

    constraints = {"min_length": 20, "max_length": 80, "max_homopolymer": 3, "gc_min": 0.25, "gc_max": 0.75}

    with pytest.raises(ValueError, match="violates synthesis constraints"):
        process_channel(
            str(fasta_path),
            str(output_path),
            [IlluminaChannel(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.0)],
            constraints,
            sub_prob=0.0,
            ins_prob=0.0,
            del_prob=0.0,
            config=ChannelConfig(coverage_distribution={4: 1.0}),
        )
