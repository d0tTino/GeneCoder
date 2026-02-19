from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genecoder.manifest import generate_manifest
from genecoder.pipeline import run_pipeline


@dataclass(frozen=True)
class RunPipelineRequest:
    codec: str
    input_path: str
    output_path: str
    fec: str | None = None
    channel: str | None = None


@dataclass(frozen=True)
class RunPipelineResponse:
    decoded: bytes
    metrics: dict[str, Any]
    fec_info: dict[str, Any] | None
    metrics_path: str
    manifest_path: str


class RunPipelineUseCase:
    def execute(self, request: RunPipelineRequest) -> RunPipelineResponse:
        decoded, metrics, fec_info = run_pipeline(
            codec=request.codec,
            fec_backend=request.fec,
            channel=request.channel,
            input_path=request.input_path,
            output_path=request.output_path,
        )
        artifact = {
            "input_config": {
                "codec": request.codec,
                "fec": request.fec,
                "channel": request.channel,
            },
            "outcome": {
                "metrics": metrics,
                "fec_info": fec_info,
            },
            "metrics": metrics,
        }
        metrics_path = Path(str(request.output_path) + ".json")
        metrics_path.write_text(__import__("json").dumps(artifact, indent=2), encoding="utf-8")

        manifest = generate_manifest(
            request.input_path,
            {"method": request.codec, "fec": request.fec, "channel": request.channel},
            metrics,
        )
        manifest_path = metrics_path.with_suffix(".manifest.json")
        manifest_path.write_text(__import__("json").dumps(manifest, indent=2), encoding="utf-8")
        return RunPipelineResponse(
            decoded=decoded,
            metrics=metrics,
            fec_info=dict(fec_info) if isinstance(fec_info, dict) else None,
            metrics_path=str(metrics_path),
            manifest_path=str(manifest_path),
        )
