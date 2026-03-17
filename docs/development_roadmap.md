# Development Roadmap

This roadmap tracks KPI gates from the canonical strategy model.

<!-- strategy:roadmap:start -->
## KPI gates and evidence (generated)

> Source of truth: `docs/strategy_model.yaml`
> last_validated_commit: `94185d38d705181caa43ae5f31bb952131805687`

### Phase 1 -> Phase 2

| Metric | Threshold | Evidence |
| --- | --- | --- |
| Weekly usage (oligos_per_week) | >= 1,000 simulated oligos/week for 4 consecutive ISO weeks | `~/.genecoder/metrics.json`, `docs/metrics.md` |

### Phase 2 -> Phase 3

| Metric | Threshold | Evidence |
| --- | --- | --- |
| Deterministic reproducibility stability | 100% deterministic seed/profile checks for 2 consecutive weeks | `tests/test_simulator_seed_reproducibility.py`, `tests/test_illumina_coverage_quality.py`, `tests/test_nanopore_context_profile.py` |
| Throughput floor | >= 2.0 MB/s Base-4 encode throughput with BER observed at baseline 0.0 | `benchmarks/throughput.py`, `PYTHONPATH=src python benchmarks/throughput.py`, `docs/performance.md` |

### Phase 3 -> Phase 4

| Metric | Threshold | Evidence |
| --- | --- | --- |
| BER baseline quality | <= 0.01 BER on baseline profile/seed | `benchmarks/error_rate.py`, `PYTHONPATH=src python benchmarks/error_rate.py`, `docs/performance.md` |
| Suite category health | Green CI across CLI/API, pipeline/simulation, and plugins/security suites | `tests/test_cli*.py`, `tests/test_pipeline*.py`, `tests/test_plugin*.py` |

### Phase 4 release gate

| Metric | Threshold | Evidence |
| --- | --- | --- |
| Plugin policy compliance | 100% pass on plugin spec/security checks before publication | `tests/test_plugin_spec_validation.py`, `tests/test_plugin_security.py`, `configs/registry.yaml` |
<!-- strategy:roadmap:end -->
