from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "docs" / "capabilities.yaml"


def _load_capabilities() -> dict:
    return yaml.safe_load(CAPABILITIES_PATH.read_text(encoding="utf-8"))


def _phase_gate(data: dict, gate_name: str) -> dict:
    return next(gate for gate in data["phase_gates"] if gate["gate"] == gate_name)


def test_validation_artifact_targets_dedicated_acceptance_module():
    data = _load_capabilities()
    capability = next(c for c in data["capabilities"] if c["id"] == "benchmark_depth_and_parity")

    assert capability["validation_artifacts"] == [
        {
            "type": "acceptance_test",
            "path": "tests/test_acceptance_benchmark_depth_and_parity.py",
        }
    ]


def test_throughput_gate_definition():
    data = _load_capabilities()
    phase_two_gate = _phase_gate(data, "Phase 2 -> Phase 3")
    throughput_metric = next(
        m for m in phase_two_gate["measurable_checks"] if m["metric"] == "Throughput median floor"
    )

    assert throughput_metric["tests_or_checks"] == [
        "PYTHONPATH=src python benchmarks/throughput.py",
        "pytest -q tests/test_acceptance_benchmark_depth_and_parity.py -k throughput_gate_definition",
    ]


def test_error_rate_gate_definition():
    data = _load_capabilities()
    phase_three_gate = _phase_gate(data, "Phase 3 -> Phase 4")
    ber_metric = next(
        m for m in phase_three_gate["measurable_checks"] if m["metric"] == "BER baseline quality"
    )

    assert ber_metric["tests_or_checks"] == [
        "PYTHONPATH=src python benchmarks/error_rate.py",
        "pytest -q tests/test_acceptance_benchmark_depth_and_parity.py -k error_rate_gate_definition",
    ]
