# Development Roadmap

Roadmap execution now gates phase transitions on measurable KPI thresholds,
instead of feature checklists alone. Features remain important, but they are now
considered complete only when usage, quality, and reproducibility KPIs are at or
above their phase targets.

## KPI table (quarterly targets and existing data sources)

| Quarter | Phase | KPI | Target threshold | Data source already in repo | Evidence artifact |
| --- | --- | --- | --- | --- | --- |
| 2026-Q1 | Foundation sustainment (Phase 1) | Weekly usage (`oligos_per_week`) | At least 1,000 simulated oligos/week for 4 consecutive ISO weeks | `docs/metrics.md` metric definition + `genecli stats`/`/metrics` output | `~/.genecoder/metrics.json` |
| 2026-Q2 | Robust Encoding Pipeline (Phase 2) | Pipeline reproducibility pass rate | 100% pass for deterministic seed/profile checks in CI for two consecutive weeks | `docs/reproducibility.md`, `tests/test_simulator_seed_reproducibility.py`, `tests/test_illumina_coverage_quality.py`, `tests/test_nanopore_context_profile.py` | CI pytest logs for reproducibility suites |
| 2026-Q2 | Robust Encoding Pipeline (Phase 2) | Runtime throughput floor | `benchmarks/throughput.py` median encode throughput stays at or above 2.0 MB/s (Base-4) on the project benchmark runner | `docs/performance.md`, `benchmarks/throughput.py` | benchmark stdout/JSON artifacts from `PYTHONPATH=src python benchmarks/throughput.py` |
| 2026-Q3 | Simulation & Analysis (Phase 3) | Benchmark quality under noise | `benchmarks/error_rate.py` BER at or below 0.01 on baseline profile with documented seed | `docs/performance.md`, `benchmarks/error_rate.py` | benchmark stdout/JSON artifacts from `PYTHONPATH=src python benchmarks/error_rate.py` |
| 2026-Q3 | Simulation & Analysis (Phase 3) | Test coverage breadth (suite categories) | Stable green coverage across inferred categories: CLI/API (`tests/test_cli*.py`, `tests/test_web_api*.py`), pipeline/simulation (`tests/test_pipeline*.py`, `tests/test_simulator*.py`), plugins/security (`tests/test_plugin*.py`, `tests/test_security*.py`) | `tests/` suite taxonomy by filename prefixes | CI pytest summary grouped by selected markers/path globs |
| 2026-Q4 | Ecosystem & Automation (Phase 4) | Plugin policy compliance quality | 100% pass on plugin spec/security checks before registry publication | `tests/test_plugin_spec_validation.py`, `tests/test_plugin_security.py`, `docs/plugins.md` | CI pytest logs + registry validation output (`configs/registry.yaml` checks) |

## KPI-driven phase transition model

> **Source of truth for phase gates:** This document is the canonical
> definition of phase numbering, phase names, KPI thresholds, and gate evidence.
> Any other roadmap/strategy document must align to this framework.
> Capability status metadata that strategy/vision docs must reflect is maintained in `docs/capabilities.yaml` and checked in CI via `scripts/check_capability_docs_sync.py`.

Roadmap phases advance only when KPI thresholds, validation checks, and evidence
artifacts all satisfy the quarter/phase definitions in the table above.

For operational details behind each KPI, use:

- [`docs/metrics.md`](metrics.md) for usage counters, `oligos_per_week`, and
  `genecli stats`/`/metrics` evidence handling.
- [`docs/reproducibility.md`](reproducibility.md) for deterministic seed/profile
  controls and reproducibility test suites.
- [`docs/performance.md`](performance.md) for throughput and BER benchmark
  scripts (`benchmarks/throughput.py`, `benchmarks/error_rate.py`) and CI gate
  implementation details (`scripts/evaluate_benchmark_gates.py`,
  `configs/benchmark_thresholds.json`, workflow benchmark artifacts).

### Phase 1 → Phase 2 (Foundation sustainment to Robust Encoding Pipeline)

- **Entry criteria**
  - Baseline CLI and pipeline paths are shipping with metrics capture enabled.
  - Usage telemetry is persisted in `~/.genecoder/metrics.json` (or configured
    equivalent) and exposed via `genecli stats` and `/metrics`.
- **Exit criteria (must all pass)**
  - `oligos_per_week` remains at or above 1,000 simulated oligos/week for 4
    consecutive ISO weeks.
- **Required evidence artifacts**
  - Metrics snapshots (`~/.genecoder/metrics.json`) showing weekly aggregates.
  - `/metrics` and/or `genecli stats` extracts captured with release evidence.

### Phase 2 → Phase 3 (Robust Encoding Pipeline to Simulation & Analysis)

- **Entry criteria**
  - Phase 1 usage KPI is sustained and evidence is archived.
- **Exit criteria (must all pass)**
  - Reproducibility suites maintain 100% pass for deterministic seed/profile
    checks across two consecutive weeks in CI.
  - Base-4 encode throughput median is at or above 2.0 MB/s on the benchmark
    runner.
- **Required evidence artifacts**
  - CI logs for deterministic reproducibility suites (seed/profile checks).
  - Benchmark stdout and gate JSON artifacts from
    `PYTHONPATH=src python benchmarks/throughput.py`.

### Phase 3 → Phase 4 (Simulation & Analysis to Ecosystem & Automation)

- **Entry criteria**
  - Phase 2 reproducibility and throughput KPIs are both green.
- **Exit criteria (must all pass)**
  - Baseline BER from `benchmarks/error_rate.py` is at or below 0.01 using the
    documented seed/profile setup.
  - CI remains green across test-suite categories: CLI/API,
    pipeline/simulation, and plugins/security.
- **Required evidence artifacts**
  - Benchmark stdout and gate JSON artifacts from
    `PYTHONPATH=src python benchmarks/error_rate.py`.
  - CI summaries for category-level suite health across the defined pytest
    globs.

### Phase 4 release gate (Ecosystem & Automation)

- **Entry criteria**
  - Phase 3 BER and suite-health KPIs are both met.
- **Exit criteria (must all pass)**
  - Plugin policy/spec/security checks remain at 100% pass before any registry
    publication or release cut.
- **Required evidence artifacts**
  - CI logs for `tests/test_plugin_spec_validation.py` and
    `tests/test_plugin_security.py`.
  - Registry validation outputs tied to `configs/registry.yaml`.

### Continuous governance beyond Phase 4

Long-term workstreams (dashboards, cloud scaling, research integrations, and
new feature delivery) are governed by the same KPI model: no initiative
graduates from planning to rollout unless the active quarter's entry/exit KPI
criteria and evidence artifacts are complete.

### Long-term interoperability strategy

To make ecosystem growth concrete, external tools should integrate through the
existing plugin entry points and registry workflows rather than bespoke,
one-off pathways.

#### Available now (implemented interoperability hooks)

- Adapter-backed optional integrations for D2Sim, DeSP, and DNArSim already
  exist in `src/genecoder/d2sim_adapter.py`,
  `src/genecoder/desp_adapter.py`, and `src/genecoder/dnarsim_adapter.py`.
- Shared plugin/registry hooks are already operational in
  `src/genecoder/plugin_manager.py`, including simulator registration and
  entry-point loading paths used by built-in and external plugins.
- The current plugin workflow for authoring/registering extensions is already
  documented in [`docs/plugins.md`](plugins.md).

#### Future deep integrations (exploratory and phase-gated)

- Production hardening for external adapters/plugins (reliability, rollout,
  and failure-handling maturity) beyond current fallback-capable operation.
- Broader benchmark validation across standardized datasets/runners before
  external integrations are treated as release-gate evidence.
- Tightened policy/security governance for registry publication and supply-chain
  controls as part of Phase 4 automation criteria.

The implementation anchors for moving from available hooks to release-grade
interoperability are:

- [`docs/plugins.md`](plugins.md) for entry point groups, `register_*` hooks,
  and runtime loading rules.
- [`configs/registry.yaml`](../configs/registry.yaml) for registry schema fields
  (`name`, `version`, `spec`, `license`, `checksum`/`signature`) and trusted
  distribution patterns.
- [`plugins-examples/`](../plugins-examples/) for working package layouts,
  `pyproject.toml` entry point declarations, and minimal registration modules.

The roadmap supports three primary integration archetypes:

1. **External simulator wrapper plugin**
   - **Entry points:** `genecoder.simulators` and optional
     `genecoder.channels`.
   - **Input contract:** sequence payloads plus simulator/channel parameters
     provided from CLI/config profiles.
   - **Output contract:** deterministic simulation artifacts (mutated reads,
     per-read error metrics, and optional summary JSON compatible with pipeline
     reporting).
2. **Codec/FEC plugin**
   - **Entry points:** `genecoder.codecs` or `genecoder.fec`.
   - **Input contract:** binary/text payload bytes and plugin-specific coding
     parameters.
   - **Output contract:** encode/decode methods that round-trip payloads,
     expose parity/redundancy metadata, and return errors compatible with core
     validation paths.
3. **Visualizer plugin**
   - **Entry points:** `genecoder.visualizers`.
   - **Input contract:** standardized metrics/report structures produced by core
     pipeline commands.
   - **Output contract:** serializable figures or dashboard-ready artifacts that
     can be embedded in CLI/web reports without altering core data models.

#### External plugin compliance checklist

- Declare complete plugin metadata in packaging and registry records (name,
  version, entry point target, SPDX license identifier).
- Use an allowlisted license for registry distribution (see
  `docs/plugins.md` for accepted SPDX values).
- Include integrity material in registry entries: checksum is mandatory, and
  signature verification is required when registry policy enables signed
  artifacts.
- Follow safe package/URL constraints from the registry validation workflow
  before publication.
- Provide at least one runnable example under `plugins-examples/` (or equivalent
  structure) so maintainers can validate the entry point contract quickly.
Refer to the [manifest format](manifest.md) for the current encoding metadata structure and the [plugin guide](plugins.md) for extension points that inform future roadmap items.
