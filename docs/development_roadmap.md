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
| 2026-Q2 | Robust Encoding Pipeline (Phase 2) | Runtime throughput floor | `benchmarks/throughput.py` median encode throughput stays at or above 2.0 MB/s (Base-4) on the project benchmark runner | `docs/performance.md`, `benchmarks/throughput.py` | benchmark stdout artifact from `PYTHONPATH=src python benchmarks/throughput.py` |
| 2026-Q3 | Simulation & Analysis (Phase 3) | Benchmark quality under noise | `benchmarks/error_rate.py` BER at or below 0.01 on baseline profile with documented seed | `docs/performance.md`, `benchmarks/error_rate.py` | benchmark stdout artifact from `PYTHONPATH=src python benchmarks/error_rate.py` |
| 2026-Q3 | Simulation & Analysis (Phase 3) | Test coverage breadth (suite categories) | Stable green coverage across inferred categories: CLI/API (`tests/test_cli*.py`, `tests/test_web_api*.py`), pipeline/simulation (`tests/test_pipeline*.py`, `tests/test_simulator*.py`), plugins/security (`tests/test_plugin*.py`, `tests/test_security*.py`) | `tests/` suite taxonomy by filename prefixes | CI pytest summary grouped by selected markers/path globs |
| 2026-Q4 | Ecosystem & Automation (Phase 4) | Plugin policy compliance quality | 100% pass on plugin spec/security checks before registry publication | `tests/test_plugin_spec_validation.py`, `tests/test_plugin_security.py`, `docs/plugins.md` | CI pytest logs + registry validation output (`configs/registry.yaml` checks) |

## Phase transition criteria

1. **Foundation (Complete, KPI-sustained)**
   - **Entry criteria:** Baseline CLI/pipeline functionality and metrics capture
     are available (`genecli stats`, `/metrics`).
   - **Exit criteria:** Foundation usage KPI meets the `oligos_per_week`
     threshold for 4 consecutive ISO weeks.
   - **Evidence artifact:** `~/.genecoder/metrics.json` snapshots and dashboard
     extracts from `/metrics`.

2. **Phase 2: Robust Encoding Pipeline**
   - **Entry criteria:** Foundation exit criteria are met.
   - **Exit criteria:**
     - Reproducibility KPI: deterministic seed/profile regression checks hold at
       100% pass for two consecutive weeks.
     - Performance KPI: Base-4 encode throughput meets or exceeds 2.0 MB/s
       median on the benchmark runner.
   - **Evidence artifact:** reproducibility pytest logs + benchmark output from
     `benchmarks/throughput.py`.

3. **Phase 3: Simulation & Analysis**
   - **Entry criteria:** Phase 2 exit criteria are met.
   - **Exit criteria:**
     - Benchmark BER KPI reaches `<= 0.01` on baseline noisy decode runs.
     - Test coverage category KPI remains green across CLI/API,
       pipeline/simulation, and plugin/security suites.
   - **Evidence artifact:** `benchmarks/error_rate.py` outputs and CI pytest
     summaries for the category globs under `tests/`.

4. **Phase 4: Ecosystem & Automation**
   - **Entry criteria:** Phase 3 exit criteria are met.
   - **Exit criteria:** plugin publication and automation workflows satisfy
     100% policy/security KPI checks before release cut.
   - **Evidence artifact:** plugin/security pytest logs and registry validation
     records tied to `configs/registry.yaml`.

5. **Long-Term Vision (rolling KPI governance)**
   - Interactive dashboards to visualize storage simulations over time.
   - Cloud-friendly architecture for scaling large simulation batches.
   - Continued collaboration with the research community to expand features.
   - All long-term initiatives advance only when quarterly KPI baselines remain
     healthy (usage, reproducibility, performance, and quality).

### Long-term interoperability strategy

To make ecosystem growth concrete, external tools should integrate through the
existing plugin entry points and registry workflows rather than bespoke
adapters. The implementation anchors are:

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
6. **Documentation Updates**
   - Inline comments in `encoders.py` and `flet_app.py` now point to `docs/vision.md` ("Vision and Current State") for added context.

Refer to the [manifest format](manifest.md) for the current encoding metadata structure and the [plugin guide](plugins.md) for extension points that inform future roadmap items.
