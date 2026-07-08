from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    script_path = ROOT / "scripts" / "validate_capability_completion.py"
    spec = spec_from_file_location("validate_capability_completion", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _implemented_model(artifact_type: str, extra: dict | None = None) -> dict:
    artifact = {"type": artifact_type, "path": "artifacts/acceptance/report.json"}
    if extra:
        artifact.update(extra)
    return {
        "feature_capabilities": [
            {
                "id": "runtime_capability",
                "status": "implemented",
                "completion_criteria": [
                    {
                        "id": "runtime_report",
                        "artifacts": [artifact],
                    }
                ],
            }
        ]
    }


def test_runtime_report_artifact_passes_only_with_required_behavioral_evidence(tmp_path: Path) -> None:
    mod = _load_module()
    report_path = tmp_path / "acceptance" / "report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "suite": "deterministic_reproducibility_governance",
                "passed": True,
                "evidence": {"decoded_sha256_equal": True, "seed_provenance_equal": True},
            }
        ),
        encoding="utf-8",
    )

    model = _implemented_model(
        "runtime_report_json",
        {
            "suite": "deterministic_reproducibility_governance",
            "required_true": ["evidence.decoded_sha256_equal", "evidence.seed_provenance_equal"],
        },
    )

    assert mod.validate(model, tmp_path) == (True, [])


def test_runtime_report_artifact_fails_when_behavioral_evidence_is_false(tmp_path: Path) -> None:
    mod = _load_module()
    report_path = tmp_path / "acceptance" / "report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "suite": "deterministic_reproducibility_governance",
                "passed": True,
                "evidence": {"decoded_sha256_equal": True, "seed_provenance_equal": False},
            }
        ),
        encoding="utf-8",
    )

    model = _implemented_model(
        "runtime_report_json",
        {
            "suite": "deterministic_reproducibility_governance",
            "required_true": ["evidence.decoded_sha256_equal", "evidence.seed_provenance_equal"],
        },
    )

    passed, failures = mod.validate(model, tmp_path)
    assert passed is False
    assert "required field evidence.seed_provenance_equal is False" in failures[0]


def test_benchmark_gate_artifact_fails_without_executable_checks(tmp_path: Path) -> None:
    mod = _load_module()
    report_path = tmp_path / "acceptance" / "report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps({"benchmark": "throughput", "passed": True, "checks": []}),
        encoding="utf-8",
    )

    model = _implemented_model("benchmark_gate_json", {"benchmark": "throughput"})

    passed, failures = mod.validate(model, tmp_path)
    assert passed is False
    assert failures == ["runtime_capability::runtime_report: benchmark gate report has no checks"]


def test_benchmark_gate_artifact_fails_when_checks_are_only_skipped(tmp_path: Path) -> None:
    mod = _load_module()
    report_path = tmp_path / "acceptance" / "report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps({"benchmark": "throughput", "passed": True, "checks": ["base4: skipped"]}),
        encoding="utf-8",
    )

    model = _implemented_model("benchmark_gate_json", {"benchmark": "throughput"})

    passed, failures = mod.validate(model, tmp_path)
    assert passed is False
    assert failures == ["runtime_capability::runtime_report: benchmark gate report contains skipped checks"]


def test_strategy_model_promotes_only_capabilities_with_runtime_artifact_checks() -> None:
    model = yaml.safe_load((ROOT / "docs" / "strategy_model.yaml").read_text(encoding="utf-8"))
    capabilities = {item["id"]: item for item in model["feature_capabilities"]}

    expected_artifact_types = {
        "deterministic_reproducibility_governance": {"runtime_report_json"},
        "benchmark_depth_and_parity": {"benchmark_gate_json", "junit_xml"},
        "plugin_registry_policy_automation": {"plugin_policy_report_json"},
    }
    for capability_id, artifact_types in expected_artifact_types.items():
        capability = capabilities[capability_id]
        assert capability["status"] == "implemented"
        observed_types = {
            artifact["type"]
            for criterion in capability["completion_criteria"]
            for artifact in criterion["artifacts"]
        }
        assert artifact_types <= observed_types
