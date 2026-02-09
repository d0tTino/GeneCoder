# Roadmap Execution Plan

This document translates GeneCoder's product strategy into implementation-facing
milestones that can be staffed, validated, and tracked in the repository.
Use this alongside:

- [Product strategy](product_strategy.md)
- [Development vision](DEVELOPMENT_VISION.md)
- [Development roadmap KPI governance](development_roadmap.md)

## KPI tracking fields (apply to every milestone)

Record these fields in milestone notes, release checklists, or issue templates:

| KPI field | Definition | Suggested source |
| --- | --- | --- |
| `decode_success_profile_x` | Decode success rate under a named profile (for example `gold_miseq_v3` or `fountain_nanopore_r10`) across fixed-seed runs. | `tests/test_pipeline*.py`, pipeline manifests, benchmark outputs |
| `runtime_seconds_per_mb` | Median runtime per MB for encode/decode workloads under representative presets. | `benchmarks/throughput.py`, CI benchmark artifacts |
| `plugin_contrib_cadence_monthly` | Number of accepted plugin updates/additions per month that pass spec/security checks. | Plugin registry PRs, `tests/test_plugin_spec_validation.py`, `tests/test_plugin_security.py` |
| `reproducibility_pass_rate` | Percent of deterministic seed/profile checks passing in CI. | Reproducibility-focused tests and CI history |
| `dashboard_activation_rate` | Fraction of runs that emit dashboard/manifest artifacts and can be rendered without manual fixes. | CLI bundle outputs, dashboard smoke tests |

---

## Phase 1: MVP hardening

Focus: stabilize core encode → simulate → decode flow and improve confidence in
default profiles before broad expansion.

### Milestone 1.1: Deterministic pipeline reliability baseline

- **Repository modules:** `src/genecoder/cli`, `src/genecoder/pipeline`,
  `src/genecoder/simulators`
- **Scope:** Harden bundle presets and CLI orchestration so repeated runs with
  fixed seeds produce reproducible outputs and stable manifests.
- **Owner role:** Core pipeline maintainer
- **Acceptance criteria:**
  - Gold and Nanopore presets pass reproducibility checks across multiple
    consecutive CI runs.
  - Manifest schema fields required by downstream tooling are always present.
  - `decode_success_profile_x` meets target threshold agreed for MVP presets.
- **Validation artifact:**
  - `tests/test_pipeline*.py`
  - `tests/test_simulator_seed_reproducibility.py`
  - Example configs: `configs/gold.yaml`,
    `configs/fountain_nanopore_pipeline.yaml`
- **Risk/dependency notes:**
  - External simulator variance and optional dependencies can destabilize
    determinism.
  - Requires strict seed propagation and explicit profile pinning in configs.

### Milestone 1.2: CLI and manifest UX hardening

- **Repository modules:** `src/genecoder/cli`, `src/genecoder/reporting`,
  `src/genecoder/manifest`
- **Scope:** Improve CLI error clarity, manifest generation consistency, and
  quick artifact inspection workflows for first-time users.
- **Owner role:** CLI and DX maintainer
- **Acceptance criteria:**
  - All critical CLI paths provide actionable error messages with suggested
    remediation.
  - HTML/JSON manifest exports remain valid for every MVP preset.
  - `dashboard_activation_rate` for MVP examples reaches the agreed floor.
- **Validation artifact:**
  - `tests/test_cli*.py`
  - `tests/test_manifest*.py`
  - Example command path using `configs/pipeline_metrics.yaml`
- **Risk/dependency notes:**
  - Backward compatibility constraints for existing manifest consumers.
  - Documentation drift can reduce onboarding quality unless updated in lockstep.

---

## Phase 2: Feature expansion

Focus: broaden supported algorithms and analysis experiences while preserving
MVP reliability and performance budgets.

### Milestone 2.1: Simulator/profile breadth with performance guardrails

- **Repository modules:** `src/genecoder/simulators`,
  `src/genecoder/channel_profiles`, `src/genecoder/pipeline`
- **Scope:** Expand Illumina/Nanopore profile coverage and expose richer channel
  options without regressing runtime behavior.
- **Owner role:** Simulation systems maintainer
- **Acceptance criteria:**
  - New/updated profiles are documented and selectable from CLI/config.
  - `runtime_seconds_per_mb` remains within target envelope for baseline runs.
  - Profile-specific decode quality meets per-profile thresholds for
    `decode_success_profile_x`.
- **Validation artifact:**
  - `benchmarks/throughput.py`
  - `tests/test_illumina_coverage_quality.py`
  - `tests/test_nanopore_context_profile.py`
  - Example configs in `configs/illumina_profile.yaml` and bundle presets
- **Risk/dependency notes:**
  - Performance variance across CI runners may obscure regressions.
  - Optional third-party simulators introduce integration maintenance overhead.

### Milestone 2.2: Dashboard and API expansion for comparative analysis

- **Repository modules:** `src/genecoder/dashboard*`, `src/genecoder/web`,
  `src/genecoder/cli`
- **Scope:** Support side-by-side run comparison, richer KPI surfacing, and
  smoother dashboard launch paths from bundle workflows.
- **Owner role:** Visualization and web platform maintainer
- **Acceptance criteria:**
  - Dashboard/API can ingest multi-run manifest indexes and render key
    comparisons (error rates, coverage, throughput).
  - CLI sweep outputs are directly consumable without manual transformation.
  - KPI panels include at least decode success and runtime-per-MB views.
- **Validation artifact:**
  - Web/API test modules (`tests/test_web_api*.py`)
  - Dashboard smoke scenario based on generated manifest index
  - Example sweep command using multiple configs and shared metrics output
- **Risk/dependency notes:**
  - Frontend/backend schema coupling can break comparators during refactors.
  - Visualization debt may increase if metrics contracts are not versioned.

---

## Phase 3: Advanced ecosystem

Focus: scale community integrations, plugin interoperability, and automated
quality governance for a research-grade ecosystem.

### Milestone 3.1: Plugin ecosystem velocity with compliance automation

- **Repository modules:** `src/genecoder/plugins`, `src/genecoder/cli`,
  `plugins-examples/`, `configs/registry.yaml`
- **Scope:** Improve plugin contribution flow, enforce policy/security checks,
  and publish clear compatibility contracts for codec/FEC/simulator extensions.
- **Owner role:** Ecosystem and security maintainer
- **Acceptance criteria:**
  - Plugin validation gates are mandatory in CI for registry-bound updates.
  - `plugin_contrib_cadence_monthly` is tracked and reviewed in release cycles.
  - At least one exemplar plugin path exists per major extension class.
- **Validation artifact:**
  - `tests/test_plugin_spec_validation.py`
  - `tests/test_plugin_security.py`
  - Example registry entry updates in `configs/registry.yaml`
- **Risk/dependency notes:**
  - Supply-chain and provenance risks require strict verification practices.
  - Excessively rigid policy could reduce contributor throughput.

### Milestone 3.2: Cloud/distributed execution and reproducible research bundles

- **Repository modules:** `src/genecoder/cloud`, `src/genecoder/worker`,
  `src/genecoder/pipeline`, `src/genecoder/dashboard*`
- **Scope:** Enable scalable batch execution with reproducible manifests and KPI
  telemetry suitable for collaborative research programs.
- **Owner role:** Platform reliability maintainer
- **Acceptance criteria:**
  - Distributed runs produce equivalent manifests/metrics to local baselines
    within defined tolerance.
  - Cloud worker orchestration supports checkpointed reruns and artifact export.
  - Reproducibility and throughput KPI reports are available per execution batch.
- **Validation artifact:**
  - Cloud worker integration tests and example deployment configs
  - Benchmark scripts for batch throughput and recovery behavior
  - End-to-end bundle example that emits portable manifest archives
- **Risk/dependency notes:**
  - Infrastructure variability can erode reproducibility guarantees.
  - Cost controls and queue fairness become critical at larger workload scales.

---

## Operating cadence

- Review milestone KPI fields at least once per release cycle.
- Keep acceptance criteria tied to repository artifacts (tests, benchmarks,
  example configs) so progress is auditable.
- Update this document whenever module boundaries or extension contracts change.
