from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "docs" / "strategy_model.yaml"


def _load_capabilities() -> dict:
    return yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8"))


def test_deterministic_repro_validation_artifact_metadata() -> None:
    data = _load_capabilities()
    capability = next(c for c in data["feature_capabilities"] if c["id"] == "deterministic_reproducibility_governance")

    assert capability["validation_artifacts"] == [
        {
            "type": "acceptance_test",
            "path": "tests/test_acceptance_deterministic_reproducibility_governance.py",
        }
    ]


def test_deterministic_repro_phase_gate_metadata() -> None:
    data = _load_capabilities()
    phase_two_gate = next(g for g in data["phase_gates"] if g["gate"] == "Phase 2 -> Phase 3")
    reproducibility_metric = next(
        m for m in phase_two_gate["measurable_checks"] if m["metric"] == "Reproducibility pass rate"
    )

    assert reproducibility_metric["tests_or_checks"] == [
        "pytest -q tests/test_acceptance_deterministic_reproducibility_governance.py"
    ]


def test_plugin_policy_validation_artifact_metadata() -> None:
    data = _load_capabilities()
    capability = next(c for c in data["feature_capabilities"] if c["id"] == "plugin_registry_policy_automation")

    assert capability["validation_artifacts"] == [
        {
            "type": "acceptance_test",
            "path": "tests/test_acceptance_plugin_registry_policy_automation.py",
        }
    ]


def test_plugin_policy_phase_gate_metadata() -> None:
    data = _load_capabilities()
    phase_three_gate = next(g for g in data["phase_gates"] if g["gate"] == "Phase 3 -> Phase 4")
    suite_health_metric = next(
        m for m in phase_three_gate["measurable_checks"] if m["metric"] == "Suite category health"
    )

    assert suite_health_metric["tests_or_checks"] == [
        "pytest -q tests/test_acceptance_plugin_registry_policy_automation.py"
    ]


def test_plugin_policy_release_gate_metadata() -> None:
    data = _load_capabilities()
    phase_four_gate = next(g for g in data["phase_gates"] if g["gate"] == "Phase 4 release gate")
    checks = {m["metric"]: m for m in phase_four_gate["measurable_checks"]}

    assert checks["Plugin policy compliance"]["tests_or_checks"] == [
        "pytest -q tests/test_acceptance_plugin_registry_policy_automation.py -k phase_four_release_gate_readiness_conditions",
        "pytest -q tests/test_plugin_supply_chain_policy.py tests/test_plugin_lifecycle_conformance.py tests/test_cli_plugin_registry.py",
    ]
