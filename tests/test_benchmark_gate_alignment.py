from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_benchmark_gate_alignment.py"
    spec = spec_from_file_location("check_benchmark_gate_alignment", script_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fixtures(tmp_path: Path, throughput_threshold: str = ">= throughput floor with BER parity"):
    (tmp_path / "configs").mkdir(parents=True)
    (tmp_path / "docs").mkdir(parents=True)

    (tmp_path / "configs" / "benchmark_thresholds.json").write_text(
        """{
  "throughput": {
    "gate": "Phase 2 -> Phase 3",
    "metric": "Throughput median floor",
    "benchmark_command": "PYTHONPATH=src python benchmarks/throughput.py",
    "baseline_snapshot": {"base4_clean_256kb": {"throughput": 1.8, "BER": 0.0, "decode_success": true, "runtime_per_mb": 1.1}},
    "tolerance_gates": {"throughput_regression_pct": 0.1, "ber_absolute_delta": 0.001, "runtime_per_mb_regression_pct": 0.2, "require_decode_success": true}
  },
  "error_rate": {
    "gate": "Phase 3 -> Phase 4",
    "metric": "BER baseline quality",
    "benchmark_command": "PYTHONPATH=src python benchmarks/error_rate.py",
    "baseline_snapshot": {"base4_noisy_256kb": {"throughput": 1.5, "BER": 0.01, "decode_success": false, "runtime_per_mb": 1.2}},
    "tolerance_gates": {"throughput_regression_pct": 0.1, "ber_absolute_delta": 0.002, "runtime_per_mb_regression_pct": 0.2, "require_decode_success": false}
  }
}
""",
        encoding="utf-8",
    )

    (tmp_path / "docs" / "capabilities.yaml").write_text(
        f"""
phase_gates:
  - gate: "Phase 2 -> Phase 3"
    measurable_checks:
      - metric: Throughput median floor
        threshold: "{throughput_threshold}"
        tests_or_checks:
          - PYTHONPATH=src python benchmarks/throughput.py
        evidence_artifacts:
          - benchmark stdout artifact
          - benchmark gate JSON artifact
  - gate: "Phase 3 -> Phase 4"
    measurable_checks:
      - metric: BER baseline quality
        threshold: "<= BER tolerance on reproducible corpus"
        tests_or_checks:
          - PYTHONPATH=src python benchmarks/error_rate.py
        evidence_artifacts:
          - benchmark stdout artifact
          - benchmark gate JSON artifact
""",
        encoding="utf-8",
    )

    (tmp_path / "docs" / "development_roadmap.md").write_text(
        "\n".join(
            [
                "Throughput threshold: throughput with BER parity",
                "BER threshold: BER tolerance",
                "PYTHONPATH=src python benchmarks/throughput.py",
                "PYTHONPATH=src python benchmarks/error_rate.py",
            ]
        ),
        encoding="utf-8",
    )


def test_benchmark_alignment_check_passes(tmp_path):
    mod = _load_module()
    _write_fixtures(tmp_path)

    mod.THRESHOLDS_PATH = tmp_path / "configs" / "benchmark_thresholds.json"
    mod.CAPABILITIES_PATH = tmp_path / "docs" / "capabilities.yaml"
    mod.ROADMAP_PATH = tmp_path / "docs" / "development_roadmap.md"

    assert mod.main() == 0


def test_benchmark_alignment_check_fails_for_threshold_mismatch(tmp_path):
    mod = _load_module()
    _write_fixtures(tmp_path, throughput_threshold=">= latency only")

    mod.THRESHOLDS_PATH = tmp_path / "configs" / "benchmark_thresholds.json"
    mod.CAPABILITIES_PATH = tmp_path / "docs" / "capabilities.yaml"
    mod.ROADMAP_PATH = tmp_path / "docs" / "development_roadmap.md"

    assert mod.main() == 1
