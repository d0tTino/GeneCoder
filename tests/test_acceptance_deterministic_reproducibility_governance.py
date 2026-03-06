from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "docs" / "capabilities.yaml"


def _load_capabilities() -> dict:
    return yaml.safe_load(CAPABILITIES_PATH.read_text(encoding="utf-8"))


def _partial_capability(data: dict, capability_id: str) -> dict:
    for capability in data["capabilities"]:
        if capability["id"] == capability_id:
            return capability
    raise AssertionError(f"Missing capability {capability_id!r}")


def test_validation_artifact_targets_dedicated_acceptance_module():
    data = _load_capabilities()
    capability = _partial_capability(data, "deterministic_reproducibility_governance")

    assert capability["validation_artifacts"] == [
        {
            "type": "acceptance_test",
            "path": "tests/test_acceptance_deterministic_reproducibility_governance.py",
        }
    ]


def test_phase_two_gate_reproducibility_criterion_uses_deterministic_command():
    data = _load_capabilities()
    phase_two_gate = next(g for g in data["phase_gates"] if g["gate"] == "Phase 2 -> Phase 3")
    reproducibility_metric = next(
        m for m in phase_two_gate["measurable_checks"] if m["metric"] == "Reproducibility pass rate"
    )

    assert reproducibility_metric["tests_or_checks"] == [
        "pytest -q tests/test_acceptance_deterministic_reproducibility_governance.py"
    ]
