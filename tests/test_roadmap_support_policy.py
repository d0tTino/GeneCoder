from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_policy_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_roadmap_support_policy.py"
    spec = spec_from_file_location("check_roadmap_support_policy", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_model_flags_unsupported_paths() -> None:
    checker = _load_policy_module()

    model = {
        "support_policy": {
            "unsupported_module_prefixes": ["src/genecoder/cloud/"],
        },
        "feature_capabilities": [
            {"id": "cloud", "owner_modules": ["src/genecoder/cloud/worker.py"]},
            {"id": "local", "owner_modules": ["src/genecoder/pipeline.py"]},
        ],
        "kpi_gates": [
            {
                "gate": "Phase 4 release gate",
                "checks": [
                    {
                        "metric": "Legacy check",
                        "evidence": ["src/genecoder/cloud/worker.py", "tests/test_worker_security.py"],
                    }
                ],
            }
        ],
    }

    violations = checker._check_model(model)
    assert len(violations) == 2
    assert "feature_capabilities[cloud]" in violations[0]
    assert "kpi_gates[Phase 4 release gate -> Legacy check]" in violations[1]


def test_check_model_passes_without_unsupported_references() -> None:
    checker = _load_policy_module()

    model = {
        "support_policy": {
            "unsupported_module_prefixes": ["src/genecoder/cloud/"],
        },
        "feature_capabilities": [
            {"id": "local", "owner_modules": ["src/genecoder/pipeline.py"]},
        ],
        "kpi_gates": [
            {
                "gate": "Phase 1 -> Phase 2",
                "checks": [
                    {
                        "metric": "Weekly usage",
                        "evidence": ["docs/metrics.md"],
                    }
                ],
            }
        ],
    }

    assert checker._check_model(model) == []
