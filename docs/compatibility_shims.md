# Compatibility Shim Matrix and Deprecation Schedule

The canonical runtime path is now **`SequenceBatch` + `channel_engine` stages**.
Core execution must route through `genecoder.core.run_canonical_pipeline` (encode → simulate → decode).

## Shim-only modules

| Module | Status | Replacement | Removal target |
| --- | --- | --- | --- |
| `genecoder.pipeline` | Shim-only | `genecoder.app.pipeline_runtime.run_pipeline` and `genecoder.core.run_canonical_pipeline` | v0.16.0 |
| `genecoder.api` | Shim-only | `genecoder.plugin_api` | v0.16.0 |
| `genecoder.channel_sim` | Shim-only | `genecoder.channel_engine`, `genecoder.simulators` | v0.15.0 |
| `genecoder.error_simulation` | Shim-only | `genecoder.channel_engine`, `genecoder.simulators` | v0.15.0 |
| `genecoder.compat.channel_sim` | Compatibility package | No direct replacement (legacy bridge only) | v0.15.0 |
| `genecoder.compat.error_simulation` | Compatibility package | No direct replacement (legacy bridge only) | v0.15.0 |

## Policy

- Core runtime modules (`genecoder.core`, `genecoder.app.*`, `genecoder.simulators.*`) must not import shim-only modules.
- Shim modules may re-export compatibility APIs for downstream users during the deprecation window.
- Removals are gated by release notes + migration callouts.

## First-party shim import audit

- `src/genecoder/cli/channel.py` now routes legacy indel compatibility through `channel_engine.legacy_adapter` and no longer imports `genecoder.error_simulation` directly.
- `src/genecoder/simulator_utils.py` now routes through `channel_engine.legacy_adapter` to keep first-party modules off shim-only imports.
- Remaining top-level shim modules (`genecoder.error_simulation`, `genecoder.channel_sim`) stay for external compatibility only and are scheduled for removal in **v0.15.0**.
