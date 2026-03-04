from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from genecoder import plugins
from genecoder.html_report import generate_html_report
from genecoder.manifest import generate_manifest
from genecoder.results.schema import compare_runs, load_run_schema, canonical_metrics_view
from genecoder.simulators.profile_resolver import available_profiles

from .pipeline_use_case import RunPipelineRequest, RunPipelineResponse, RunPipelineUseCase


@dataclass(frozen=True)
class ArtifactExportRequest:
    run_data: Mapping[str, Any]
    output_dir: str
    run_id: str


class UIService:
    """Headless application service contract for UI adapters."""

    def __init__(self, pipeline_use_case: RunPipelineUseCase | None = None) -> None:
        self._pipeline_use_case = pipeline_use_case or RunPipelineUseCase()

    def run_pipeline(self, request: RunPipelineRequest) -> RunPipelineResponse:
        return self._pipeline_use_case.execute(request)

    def load_artifact(self, artifact: str | Path | Mapping[str, Any]) -> dict[str, Any]:
        run_schema = load_run_schema(artifact)
        run_schema["dashboard_metrics"] = canonical_metrics_view(run_schema)
        return run_schema

    def compare_artifacts(
        self,
        baseline: str | Path | Mapping[str, Any],
        candidate: str | Path | Mapping[str, Any],
        *others: str | Path | Mapping[str, Any],
    ) -> dict[str, Any]:
        base = self.load_artifact(baseline)
        cand = self.load_artifact(candidate)
        rest = [self.load_artifact(item) for item in others]
        return compare_runs(base, cand, *rest)

    def list_plugins(self) -> dict[str, Any]:
        return {"plugins": plugins.PLUGIN_CATALOG}

    def list_profiles(self) -> dict[str, Any]:
        return {
            "aliases": [
                {"alias": alias, "family": family, "profile": profile}
                for alias, (family, profile) in sorted(available_profiles().items())
            ]
        }

    def export_artifacts(self, request: ArtifactExportRequest) -> dict[str, str]:
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        metrics_path = output_dir / f"{request.run_id}.metrics.json"
        metrics_path.write_text(json.dumps(dict(request.run_data), indent=2), encoding="utf-8")

        dashboard_metrics = canonical_metrics_view(request.run_data)
        manifest = generate_manifest(
            request.run_id,
            {"method": request.run_data.get("profiles", {}).get("encoding", "unknown")},
            dashboard_metrics,
        )
        manifest_path = output_dir / f"{request.run_id}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        report_path = output_dir / f"{request.run_id}.report.html"
        report_path.write_text(generate_html_report(str(manifest_path)), encoding="utf-8")

        index_path = output_dir / "manifest_index.json"
        entries: list[dict[str, str]] = []
        if index_path.exists():
            try:
                raw_entries = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(raw_entries, list):
                    entries = [dict(item) for item in raw_entries if isinstance(item, Mapping)]
            except (ValueError, json.JSONDecodeError):
                entries = []
        entries.append(
            {
                "run_id": request.run_id,
                "metrics_json": str(metrics_path),
                "manifest_json": str(manifest_path),
                "report_html": str(report_path),
            }
        )
        index_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

        return {
            "metrics_json": str(metrics_path),
            "manifest_json": str(manifest_path),
            "report_html": str(report_path),
            "manifest_index": str(index_path),
        }
