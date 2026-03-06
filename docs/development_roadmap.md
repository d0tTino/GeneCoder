# Development Roadmap

> last_validated_commit: `4eb89f0cde3b7d75fcaf8311634be19ec56b90f0`

## Phase 1 -> Phase 2

| Metric | Threshold | Evidence |
| --- | --- | --- |
| Weekly usage (oligos_per_week) | >= 1,000 simulated oligos/week for 4 consecutive ISO weeks | run-scoped artifacts under output directories (for example `<run>/metrics.json`, `<run>/metrics.kpi.json`), `docs/metrics.md` |

## Phase 2 -> Phase 3

| Metric | Threshold | Evidence |
| --- | --- | --- |
| Deterministic reproducibility stability | 100% deterministic seed/profile checks for 2 consecutive weeks | `tests/test_simulator_seed_reproducibility.py`, `tests/test_illumina_coverage_quality.py`, `tests/test_nanopore_context_profile.py` |
| Throughput floor | >= 2.0 MB/s Base-4 encode throughput | `PYTHONPATH=src python benchmarks/throughput.py`, run artifact `artifacts/benchmarks/throughput.kpi.json`, gate report `artifacts/benchmarks/throughput-gate.json`, `docs/performance.md` |

## Phase 3 -> Phase 4

| Metric | Threshold | Evidence |
| --- | --- | --- |
| BER baseline quality | <= 0.01 BER on baseline profile/seed | `PYTHONPATH=src python benchmarks/error_rate.py`, run artifact `artifacts/benchmarks/error_rate.kpi.json`, gate report `artifacts/benchmarks/error_rate-gate.json`, `docs/performance.md` |
| Suite category health | Green CI across CLI/API, pipeline/simulation, and plugins/security suites | `tests/test_cli*.py`, `tests/test_pipeline*.py`, `tests/test_plugin*.py` |

## Phase 4 release gate

| Metric | Threshold | Evidence |
| --- | --- | --- |
| Plugin policy compliance | 100% pass on plugin spec/security checks before publication | `tests/test_plugin_spec_validation.py`, `tests/test_plugin_security.py`, `configs/registry.yaml` |
