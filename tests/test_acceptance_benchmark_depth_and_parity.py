from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "docs" / "capabilities.yaml"
MATRIX_PATH = ROOT / "configs" / "benchmark_matrix.yaml"
MUTATION_KEYS = ("substitution_prob", "insertion_prob", "deletion_prob", "dropout_prob")


def _load_capabilities() -> dict:
    return yaml.safe_load(CAPABILITIES_PATH.read_text(encoding="utf-8"))


def _phase_gate(data: dict, gate_name: str) -> dict:
    return next(gate for gate in data["phase_gates"] if gate["gate"] == gate_name)


def test_validation_artifact_targets_dedicated_acceptance_module() -> None:
    data = _load_capabilities()
    capability = next(c for c in data["capabilities"] if c["id"] == "benchmark_depth_and_parity")

    assert capability["validation_artifacts"] == [
        {
            "type": "acceptance_test",
            "path": "tests/test_acceptance_benchmark_depth_and_parity.py",
        }
    ]


def test_throughput_gate_definition() -> None:
    data = _load_capabilities()
    phase_two_gate = _phase_gate(data, "Phase 2 -> Phase 3")
    throughput_metric = next(
        m for m in phase_two_gate["measurable_checks"] if m["metric"] == "Throughput median floor"
    )

    assert throughput_metric["tests_or_checks"] == [
        "PYTHONPATH=src python benchmarks/throughput.py",
        "pytest -q tests/test_acceptance_benchmark_depth_and_parity.py -k throughput_gate_definition",
    ]


def test_error_rate_gate_definition() -> None:
    data = _load_capabilities()
    phase_three_gate = _phase_gate(data, "Phase 3 -> Phase 4")
    ber_metric = next(
        m for m in phase_three_gate["measurable_checks"] if m["metric"] == "BER baseline quality"
    )

    assert ber_metric["tests_or_checks"] == [
        "PYTHONPATH=src python benchmarks/error_rate.py",
        "pytest -q tests/test_acceptance_benchmark_depth_and_parity.py -k error_rate_gate_definition",
    ]


def test_benchmark_matrix_completeness() -> None:
    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    expected = {
        (codec, simulator, profile, payload_size)
        for codec, simulator, profile, payload_size in itertools.product(
            matrix["axes"]["codec"],
            matrix["axes"]["simulator"],
            matrix["axes"]["profile"],
            matrix["axes"]["payload_size"],
        )
    }
    observed = {
        (
            scenario["codec"],
            scenario["simulator"],
            scenario["profile"],
            int(scenario["payload_size"]),
        )
        for scenario in matrix["scenarios"]
    }
    assert observed == expected


def _run_benchmark(benchmark: str) -> dict:
    proc = subprocess.run(
        [sys.executable, f"benchmarks/{benchmark}.py", "--format", "json"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_deterministic_benchmark_schema() -> None:
    first = _run_benchmark("throughput")
    second = _run_benchmark("throughput")

    assert first["schema_version"] == "1.0.0"
    assert first["matrix_version"]
    assert first["corpus_sha256"] == second["corpus_sha256"]
    assert [r["profile"] for r in first["results"]] == [r["profile"] for r in second["results"]]

    expected_keys = {
        "profile",
        "codec",
        "simulator",
        "profile_descriptor",
        "payload_size",
        "seed",
        "substitution_prob",
        "insertion_prob",
        "deletion_prob",
        "dropout_prob",
        "throughput",
        "BER",
        "decode_success",
        "runtime_per_mb",
        "encode_mb_s",
        "decode_mb_s",
    }
    assert first["results"]
    for result in first["results"]:
        assert set(result.keys()) == expected_keys


def test_noisy_scenarios_inject_measurable_noise() -> None:
    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    noisy_scenarios = [scenario for scenario in matrix["scenarios"] if scenario["profile"] == "noisy"]

    assert noisy_scenarios
    for scenario in noisy_scenarios:
        mutation_sum = sum(float(scenario.get(key, 0.0)) for key in MUTATION_KEYS)
        assert mutation_sum > 0.0

    payload = _run_benchmark("error_rate")
    substitution_noisy = [
        result
        for result in payload["results"]
        if result["profile_descriptor"] == "noisy" and result["simulator"] == "substitution"
    ]
    assert substitution_noisy
    assert all(result["BER"] > 0.0 for result in substitution_noisy)



def test_noisy_scenarios_require_non_zero_mutation_parameters() -> None:
    from benchmarks.harness import _validated_scenarios

    matrix = {
        "profiles": {"noisy": {"substitution_prob": 0.0}},
        "scenarios": [
            {
                "codec": "base4",
                "simulator": "substitution",
                "profile": "noisy",
                "payload_size": 65536,
                "seed": 7331,
                "substitution_prob": 0.0,
                "insertion_prob": 0.0,
                "deletion_prob": 0.0,
                "dropout_prob": 0.0,
            }
        ],
    }

    with pytest.raises(ValueError, match="profile=noisy requires at least one non-zero mutation parameter"):
        _validated_scenarios(matrix)

def test_gate_enforcement() -> None:
    payload = {
        "benchmark": "throughput",
        "schema_version": "1.0.0",
        "matrix_version": "1.0.0",
        "results": [
            {
                "profile": "base4_identity_clean_256kb_seed1337",
                "throughput": 0.1,
                "BER": 0.5,
                "decode_success": False,
                "runtime_per_mb": 99.0,
            }
        ],
    }
    temp_dir = ROOT / "build" / "tmp_acceptance"
    temp_dir.mkdir(parents=True, exist_ok=True)
    artifact = temp_dir / "bad-throughput.json"
    report = temp_dir / "bad-throughput-gate.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_benchmark_gates.py",
            "--benchmark",
            "throughput",
            "--artifact-json",
            str(artifact),
            "--output-json",
            str(report),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    parsed_report = json.loads(report.read_text(encoding="utf-8"))
    assert parsed_report["passed"] is False
