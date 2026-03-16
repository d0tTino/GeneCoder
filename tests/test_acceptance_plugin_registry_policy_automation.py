from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "docs" / "capabilities.yaml"


def _load_capabilities() -> dict:
    return yaml.safe_load(CAPABILITIES_PATH.read_text(encoding="utf-8"))


def test_validation_artifact_targets_dedicated_acceptance_module():
    data = _load_capabilities()
    capability = next(c for c in data["capabilities"] if c["id"] == "plugin_registry_policy_automation")

    assert capability["validation_artifacts"] == [
        {
            "type": "acceptance_test",
            "path": "tests/test_acceptance_plugin_registry_policy_automation.py",
        }
    ]


def test_suite_category_health_gate_criterion():
    data = _load_capabilities()
    phase_three_gate = next(g for g in data["phase_gates"] if g["gate"] == "Phase 3 -> Phase 4")
    suite_health_metric = next(
        m for m in phase_three_gate["measurable_checks"] if m["metric"] == "Suite category health"
    )

    assert suite_health_metric["tests_or_checks"] == [
        "pytest -q tests/test_acceptance_plugin_registry_policy_automation.py"
    ]


def test_phase_four_release_gate_readiness_conditions():
    data = _load_capabilities()
    phase_four_gate = next(g for g in data["phase_gates"] if g["gate"] == "Phase 4 release gate")
    checks = {m["metric"]: m for m in phase_four_gate["measurable_checks"]}

    expected_checks = {
        "Plugin policy compliance": [
            "pytest -q tests/test_acceptance_plugin_registry_policy_automation.py -k phase_four_release_gate_readiness_conditions",
            "pytest -q tests/test_plugin_supply_chain_policy.py tests/test_plugin_lifecycle_conformance.py tests/test_cli_plugin_registry.py",
        ],
    }

    assert set(checks) == set(expected_checks)
    for metric, commands in expected_checks.items():
        assert checks[metric]["tests_or_checks"] == commands
