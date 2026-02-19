from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from genecoder.core import metrics as gather_metrics
from genecoder.formats import SequenceBatch

from .schema import RUN_SCHEMA_VERSION, translate_manifest


@dataclass(slots=True)
class EncodeStageEvent:
    codec: str
    fec: str | None
    input_path: str
    original_data: bytes
    encoded_batch: SequenceBatch
    fec_info: Mapping[str, Any] | None
    encoding_parameters: dict[str, Any]


@dataclass(slots=True)
class SimulateStageEvent:
    channel: str | None
    channel_parameters: dict[str, Any]
    mutated_batch: SequenceBatch
    substitutions: int
    insertions: int
    deletions: int
    coverage: int | None


@dataclass(slots=True)
class DecodeStageEvent:
    output_path: str
    decoded_data: bytes
    constraints: Any = None


@dataclass(slots=True)
class RunArtifactCollector:
    run_id: str
    input_config: dict[str, Any]
    reproducibility: dict[str, Any] = field(default_factory=dict)
    _encode: EncodeStageEvent | None = None
    _simulate: SimulateStageEvent | None = None
    _decode: DecodeStageEvent | None = None

    def record_encode(self, event: EncodeStageEvent) -> None:
        self._encode = event

    def record_simulate(self, event: SimulateStageEvent) -> None:
        self._simulate = event

    def record_decode(self, event: DecodeStageEvent) -> None:
        self._decode = event

    def emit(self) -> dict[str, Any]:
        if self._encode is None or self._simulate is None or self._decode is None:
            raise ValueError("Collector requires encode/simulate/decode events")

        stack_metrics = (
            dict(self._encode.fec_info).get("coding_stack")
            if isinstance(self._encode.fec_info, Mapping)
            else None
        )

        metrics = gather_metrics(
            self._simulate.mutated_batch,
            self._encode.original_data,
            self._decode.decoded_data,
            self._encode.fec,
            self._simulate.substitutions,
            self._simulate.insertions,
            self._simulate.deletions,
            self._simulate.coverage,
            constraints=self._decode.constraints,
            stack_metrics=stack_metrics,
        )

        manifest_payload = {
            "file": Path(self._encode.input_path).name,
            "encoding_parameters": dict(self._encode.encoding_parameters),
            "metrics": metrics,
        }
        canonical = translate_manifest(manifest_payload)
        canonical["schema_version"] = RUN_SCHEMA_VERSION
        canonical["run_id"] = self.run_id
        canonical["input_config"] = dict(self.input_config)
        canonical["stage_outputs"] = {
            "encode": {
                "batch_id": self._encode.encoded_batch.batch_id,
                "oligos": len(self._encode.encoded_batch.oligos),
            },
            "simulate": {
                "batch_id": self._simulate.mutated_batch.batch_id,
                "oligos": len(self._simulate.mutated_batch.oligos),
            },
            "decode": {
                "output_path": self._decode.output_path,
                "decoded_size": len(self._decode.decoded_data),
            },
        }
        canonical["coding_stack"] = metrics.get("coding_stack", {})
        canonical["constraint_outcomes"] = metrics.get("constraint_violations", {})
        canonical["decode_results"] = {
            "decode_success_rate": metrics.get("decode_success_rate"),
            "ecc_success_rates": metrics.get("ecc_success_rates", {}),
        }
        canonical["reproducibility"] = dict(self.reproducibility)
        return canonical
