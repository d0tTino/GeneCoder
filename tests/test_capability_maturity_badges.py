from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_capability_maturity_badges.py"
    spec = spec_from_file_location("render_capability_maturity_badges", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_partial_capabilities_report_ci_presence():
    module = _load_module()

    capabilities_data = {
        "capabilities": [
            {
                "id": "deterministic_reproducibility_governance",
                "status": "partial",
                "ci_status_checks": ["capability-deterministic-reproducibility"],
            }
        ]
    }
    workflow_data = {"jobs": {"capability-deterministic-reproducibility": {"runs-on": "ubuntu-latest"}}}

    rendered = module.render_markdown(capabilities_data, workflow_data)
    assert "`yes`" in rendered
    assert "in-progress" in rendered


def test_missing_ci_job_is_flagged_in_badge_table():
    module = _load_module()

    capabilities_data = {
        "capabilities": [
            {
                "id": "plugin_registry_policy_automation",
                "status": "partial",
                "ci_status_checks": ["capability-plugin-registry-policy"],
            }
        ]
    }
    workflow_data = {"jobs": {}}

    rendered = module.render_markdown(capabilities_data, workflow_data)
    assert "`no`" in rendered
    assert "in-progress-unchecked" in rendered
