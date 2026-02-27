# Legacy Module Deprecation Matrix

This matrix tracks legacy modules, their replacement paths, and the release
phase/KPI evidence required before removal.

## Module mapping and removal governance

| Legacy module | Replacement path | Status | Removal phase (roadmap) | KPI/release evidence required before removal |
| --- | --- | --- | --- | --- |
| `genecoder.pipeline` | `genecoder.app.pipeline_runtime` + `genecoder.app.pipeline_use_case` | Compatibility shim only | Phase 2 completion gate | `decode_success_profile_x >= 0.95` and `reproducibility_pass_rate >= 0.99` across CI pipeline tests and release checklist artifacts. |
| `genecoder.api` | `genecoder.plugin_api` | Compatibility shim only | Phase 2 completion gate | No direct production imports outside approved adapters plus plugin interface tests green in release branch. |
| `genecoder.channel_sim` | `genecoder.compat.channel_sim` (shim) + `genecoder.channel_engine` | Compatibility shim only | v0.15.0 removal window | Channel-equivalence tests green and runtime budget (`runtime_seconds_per_mb`) within roadmap threshold. |
| `genecoder.error_simulation` | `genecoder.compat.error_simulation` (shim) + `genecoder.channel_engine` | Compatibility shim only | v0.15.0 removal window | Channel profile parity tests, reproducibility checks, and benchmark trend evidence attached to release decision. |
| `genecoder.simulation_engine.legacy_adapter` | `genecoder.simulation_engine.executors` and profile-driven execution | Migration in progress | Phase 3 hardening gate | Executor path coverage in CI and reproducibility KPI pass-rate maintained for rolling window. |

## Approved compatibility adapters

Only compatibility adapters may import marked legacy modules:

- `genecoder.pipeline`
- `genecoder.api`
- `genecoder.channel_sim`
- `genecoder.error_simulation`

CI architecture checks fail if additional modules import these paths.

## Governance policy

Legacy removals are release-governed and require both:

1. A roadmap phase transition checkpoint documented in release notes.
2. KPI evidence from `docs/roadmap_execution.md` gate metrics attached to the
   release checklist.

Ad hoc deletions without roadmap/KPI evidence are out of policy.
