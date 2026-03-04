# Compatibility Shim Matrix and Deprecation Schedule

The canonical runtime path is now **`SequenceBatch` + `channel_engine` stages**.
Core execution must route through `genecoder.core.run_canonical_pipeline` (encode → simulate → decode).

The only supported external integration surface is `genecoder.sdk` + `genecoder.app`.
Legacy imports are routed through versioned adapters under `genecoder.compat.v1`.

## Shim-only modules

| Module | Status | Replacement | Removal target |
| --- | --- | --- | --- |
| `genecoder.pipeline` | Shim-only via `genecoder.compat.v1.pipeline_adapter` | `genecoder.app.pipeline_runtime.run_pipeline` and `genecoder.core.run_canonical_pipeline` | v0.16.0 |
| `genecoder.api` | Shim-only via `genecoder.compat.v1.api_adapter` | `genecoder.sdk.plugins` | v0.16.0 |
| `genecoder.channel_sim` | Shim-only | `genecoder.channel_engine`, `genecoder.simulators` | v0.15.0 |
| `genecoder.error_simulation` | Shim-only | `genecoder.channel_engine`, `genecoder.simulators` | v0.15.0 |
| `genecoder.compat.channel_sim` | Compatibility package | No direct replacement (legacy bridge only) | v0.15.0 |
| `genecoder.compat.error_simulation` | Compatibility package | No direct replacement (legacy bridge only) | v0.15.0 |

## Policy

- Core runtime modules (`genecoder.core`, `genecoder.app.*`, `genecoder.simulators.*`) must not import shim-only modules.
- Shim modules may re-export compatibility APIs for downstream users during the deprecation window.
- Removals are gated by release notes + migration callouts.
- CI enforces no new `genecoder.api` / `genecoder.pipeline` imports outside approved compatibility tests.


- `genecoder.channel_engine.legacy_adapter` is now treated as a compatibility-only implementation detail and must not be imported from interface packages (`genecoder.cli`, `genecoder.sdk`, `genecoder.dashboard`).
