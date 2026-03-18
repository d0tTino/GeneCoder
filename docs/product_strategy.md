<!-- GENERATED FILE: derived from docs/strategy_model.yaml; edit docs/strategy_model.yaml and rerun `python scripts/generate_strategy_artifacts.py --write`. -->

# Product Strategy

This document includes generated strategy metadata. Update `docs/strategy_model.yaml` and re-render generated sections instead of editing the generated block directly.

<!-- strategy:product:start -->
## Strategy model snapshot (generated)

> Source of truth: `docs/strategy_model.yaml`
> last_validated_commit: `f62498d40dd487eca4eff0cd1f41a42cc056eaed`

### Phase definitions

| Phase | Name | Objective | Execution focus |
| --- | --- | --- | --- |
| 1 | Foundation sustainment | Keep MVP workflows reliable and reproducible. | Stabilize shipped bundles, manifests, and dashboard compatibility. |
| 2 | Robust encoding pipeline | Expand profile/codec breadth while preserving determinism. | Increase simulator profile coverage without violating runtime budgets. |
| 3 | Simulation and analysis | Scale benchmark quality and cross-suite confidence. | Enforce BER, throughput, and category-level CI guardrails. |
| 4 | Ecosystem and automation | Harden plugin governance and operational automation. | Keep registry publication and execution policy checks continuously green. |

### Feature capability statuses

| Capability | Status | Phase | Owner modules |
| --- | --- | --- | --- |
| CLI bundle presets for end-to-end pipelines | `implemented` | 1 | `src/genecoder/cli/bundle.py`<br>`src/genecoder/pipeline.py` |
| Illumina simulation with profile-resolved errors | `implemented` | 1 | `src/genecoder/simulators/illumina/channel.py`<br>`src/genecoder/simulators/illumina/profiles.py` |
| Nanopore simulation with context-aware profile controls | `implemented` | 1 | `src/genecoder/simulators/nanopore.py`<br>`src/genecoder/simulators/nanopore_profiles.py` |
| Deterministic seed/profile reproducibility governance | `partial` | 2 | `src/genecoder/pipeline.py`<br>`src/genecoder/cli/cli.py` |
| Standardized benchmark depth and parity validation | `partial` | 3 | `benchmarks/throughput.py`<br>`benchmarks/error_rate.py` |
| Plugin registry policy/security automation | `partial` | 4 | `src/genecoder/plugin_manager.py`<br>`src/genecoder/plugin_runtime/registry.py` |
| Cloud worker remote execution | `deprecated` | 4 | `src/genecoder/compat/legacy/cloud/worker.py` |

### Deployment posture flags

| Flag | Value |
| --- | --- |
| `cloud_enabled` | `False` |
| `cloud_worker_enabled` | `False` |
| `local_execution_only` | `True` |
<!-- strategy:product:end -->
