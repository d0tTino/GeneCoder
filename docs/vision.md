# Vision & Core Concept

GeneCoder aims to make DNA data storage experimentation practical and reproducible by combining encoding, channel simulation, and decoding workflows in one toolkit.

## Vision and Current State


> Phase, capability, and KPI gate definitions are canonically sourced from [`docs/strategy_model.yaml`](strategy_model.yaml).

<!-- strategy:vision:start -->
## Strategy-aligned phase and capability narrative (generated)

> Source of truth: `docs/strategy_model.yaml`
> last_validated_commit: `8d48bb07887d5f6589bbe941546d7867a260600a`

### Phase intent

- **Phase 1 — Foundation sustainment**: Keep MVP workflows reliable and reproducible. (Execution focus: Stabilize shipped bundles, manifests, and dashboard compatibility.)
- **Phase 2 — Robust encoding pipeline**: Expand profile/codec breadth while preserving determinism. (Execution focus: Increase simulator profile coverage without violating runtime budgets.)
- **Phase 3 — Simulation and analysis**: Scale benchmark quality and cross-suite confidence. (Execution focus: Enforce BER, throughput, and category-level CI guardrails.)
- **Phase 4 — Ecosystem and automation**: Harden plugin governance and operational automation. (Execution focus: Keep registry publication and execution policy checks continuously green.)

### Capability status snapshot

| Capability | Status | Phase | Owner modules |
| --- | --- | --- | --- |
| CLI bundle presets for end-to-end pipelines | `implemented` | 1 | `src/genecoder/cli/bundle.py`<br>`src/genecoder/pipeline.py` |
| Illumina simulation with profile-resolved errors | `implemented` | 1 | `src/genecoder/simulators/illumina/channel.py`<br>`src/genecoder/simulators/illumina/profiles.py` |
| Nanopore simulation with context-aware profile controls | `implemented` | 1 | `src/genecoder/simulators/nanopore.py`<br>`src/genecoder/simulators/nanopore_profiles.py` |
| Deterministic seed/profile reproducibility governance | `partial` | 2 | `src/genecoder/pipeline.py`<br>`src/genecoder/cli/cli.py` |
| Standardized benchmark depth and parity validation | `partial` | 3 | `benchmarks/throughput.py`<br>`benchmarks/error_rate.py` |
| Plugin registry policy/security automation | `partial` | 4 | `src/genecoder/plugin_manager.py`<br>`src/genecoder/plugin_runtime/registry.py` |
| Cloud worker remote execution | `deprecated` | 4 | `src/genecoder/compat/legacy/cloud/worker.py` |
<!-- strategy:vision:end -->

GeneCoder already ships an end-to-end simulation path for common DNA storage experiments. The current implementation includes:

- **Built-in sequencing simulators and presets** for **Illumina** and **Nanopore** workflows, including profile-driven runs in the bundled pipeline examples.
- A **storage decay stage** that can be chained after sequencing simulations in the preset bundles.
- End-to-end CLI presets in `configs/` (for example, the Gold, RS+Illumina, and Fountain+Nanopore pipelines) that exercise encode → simulate/decay → decode flows.

At the same time, the project still has fidelity work to do. The main gaps are not simulator availability, but:

- stronger profile calibration fidelity against wet-lab or public benchmark datasets,
- tighter reproducibility governance for cross-run benchmarking,
- and deeper parity validation versus external simulators under matched conditions.

### ECC and codec support status

GeneCoder currently documents and ships support for:

- **Reed–Solomon** and **Fountain** workflows in core presets/checklists,
- additional codec families through optional extras (for example Chamaeleo-backed schemes),
- and optional advanced integrations such as **LDPC**, **RaptorQ**, and AI-assisted **DNAformer/DeepDNA** components.

### Known limitations

Current limitations are primarily around validation depth and benchmarking rigor rather than missing baseline features:

- comparative validation datasets and benchmark depth are still limited,
- reproducibility governance across environments can be improved,
- and advanced profile-calibration workflows (including versioned calibration evidence) are still maturing.

## Recommended Features and Improvements (Near-Term)

### Completed/Available

The following items are already shipped and documented, so they are tracked as available capabilities rather than near-term feature gaps:

- **Reed–Solomon and Fountain presets/workflows** in bundled configs and checklists.
- **Profile selection support** for built-in Illumina/Nanopore simulator pathways.
- **Basic multi-stage pipeline chaining** (encode → simulate and/or decay → decode) in preset bundle flows.

### Near-Term Feature Work (Net-New Gaps)

#### 1) Simulator calibration hardening

Align profile fidelity work with `docs/channel_profiles.md` by adding a formal calibration track for existing profiles against reference datasets (public benchmarks or wet-lab-aligned snapshots).

**Acceptance criteria**

- Per-profile calibration reports are versioned and include baseline-versus-calibrated error summaries for substitution/indel/dropout metrics.
- At least one documented calibration recipe exists for Illumina and one for Nanopore profiles in `docs/channel_profiles.md`.
- Calibrated profiles demonstrate bounded error-rate deltas versus reference targets (for example, absolute deviation ≤ 10% on primary channel metrics across the validation corpus).

#### 2) Reproducibility and performance hardening

Close experiment-quality gaps by formalizing deterministic run controls and benchmark governance defined in `docs/reproducibility.md` and `docs/performance.md`.

**Acceptance criteria**

- Reproducibility checks confirm repeated seeded runs produce stable manifests/metrics within documented tolerance (or exact match where deterministic paths are expected).
- Performance baselines are published for key workflows, with CI or scheduled checks flagging regressions beyond agreed thresholds (for example, throughput slowdown > 10% or memory growth > 15%).
- `docs/reproducibility.md` and `docs/performance.md` each include a complete “how to run + how to interpret results” section for the tracked benchmarks.

#### 3) Plugin and security robustness

Harden extension safety and operator trust by tightening lifecycle guarantees already described in `docs/plugins.md` and `docs/security.md`.

**Acceptance criteria**

- Plugin validation paths cover signature verification/failure handling and provenance metadata checks for local and registry-driven installs.
- Security guidance includes explicit threat-model assumptions and operational hardening defaults for plugin execution contexts.
- Documentation completeness criteria are met: `docs/plugins.md` and `docs/security.md` contain end-to-end examples for secure plugin install, verification, and rollback/disable procedures.
