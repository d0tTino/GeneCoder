from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True)
class SynthesisCostAssumptions:
    usd_per_nt: float = 0.0


@dataclass(frozen=True)
class SequencingCostAssumptions:
    usd_per_read: float = 0.0


@dataclass(frozen=True)
class RedundancySettings:
    baseline_coverage: float = 1.0


@dataclass(frozen=True)
class CostModelInputs:
    synthesis: SynthesisCostAssumptions
    sequencing: SequencingCostAssumptions
    redundancy: RedundancySettings


@dataclass(frozen=True)
class CostOutputs:
    cost_per_recovered_bit: float
    reads_per_successful_decode: float
    redundancy_cost_ratio: float


def _as_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed


def parse_cost_model_inputs(raw: Mapping[str, Any] | None) -> CostModelInputs:
    payload = dict(raw or {})
    synthesis_raw = payload.get("synthesis")
    sequencing_raw = payload.get("sequencing")
    redundancy_raw = payload.get("redundancy")

    synthesis = dict(synthesis_raw) if isinstance(synthesis_raw, Mapping) else {}
    sequencing = dict(sequencing_raw) if isinstance(sequencing_raw, Mapping) else {}
    redundancy = dict(redundancy_raw) if isinstance(redundancy_raw, Mapping) else {}

    return CostModelInputs(
        synthesis=SynthesisCostAssumptions(
            usd_per_nt=max(0.0, _as_float(synthesis.get("usd_per_nt"), 0.0))
        ),
        sequencing=SequencingCostAssumptions(
            usd_per_read=max(0.0, _as_float(sequencing.get("usd_per_read"), 0.0))
        ),
        redundancy=RedundancySettings(
            baseline_coverage=max(1e-9, _as_float(redundancy.get("baseline_coverage"), 1.0))
        ),
    )


def compute_cost_outputs(
    *,
    inputs: CostModelInputs,
    total_nt: int,
    total_reads: int,
    recovered_bytes: int,
    decode_success_rate: float,
) -> CostOutputs:
    recovered_bits = max(0, int(recovered_bytes)) * 8
    success_rate = min(max(float(decode_success_rate), 0.0), 1.0)
    expected_successes = max(success_rate, 1e-9)

    synthesis_cost = max(0, int(total_nt)) * inputs.synthesis.usd_per_nt
    sequencing_cost = max(0, int(total_reads)) * inputs.sequencing.usd_per_read
    total_cost = synthesis_cost + sequencing_cost

    cost_per_recovered_bit = total_cost / max(recovered_bits, 1)
    reads_per_successful_decode = max(0, int(total_reads)) / expected_successes
    redundancy_cost_ratio = (max(0.0, float(total_reads)) / inputs.redundancy.baseline_coverage)

    return CostOutputs(
        cost_per_recovered_bit=cost_per_recovered_bit,
        reads_per_successful_decode=reads_per_successful_decode,
        redundancy_cost_ratio=redundancy_cost_ratio,
    )
