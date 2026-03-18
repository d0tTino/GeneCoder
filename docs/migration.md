# Migration Guide

## Canonical integration surface (supported API)

Starting in **v0.14.0**, GeneCoder supports external integrations only through:

- `genecoder.sdk` for stable request/result contracts and plugin interfaces.
- `genecoder.app` for application-layer use cases and orchestration contracts.

Deprecated facades (`genecoder.api`, `genecoder.pipeline`, and `genecoder.compat.*`) remain compatibility-only bridges. They forward to canonical implementations, emit `DeprecationWarning`, and now record usage telemetry so release planning can confirm when removals are safe.

## Migration priorities

1. **Move orchestration calls to `genecoder.app`.** Replace `genecoder.pipeline` and any `SequencePipeline` compatibility imports with `RunPipelineUseCase`, `RunPipelineRequest`, and related dataclasses from `genecoder.app`.
2. **Move plugin contracts and automation to `genecoder.sdk`.** Replace `genecoder.api` imports with `genecoder.sdk.plugins`, and use `genecoder.sdk.run_experiment` / `ExperimentRequest` for supported external workflows.
3. **Eliminate direct `genecoder.compat.*` dependencies.** Compatibility packages are temporary shims only; new production code must not depend on them.

## Versioned removal schedule

| Release | Status | Concrete milestone | Required consumer action |
| --- | --- | --- | --- |
| **v0.14.x** | Current migration window | Canonical `genecoder.app` and `genecoder.sdk` interfaces are the only supported first-class APIs. Deprecated facades are warning-only compatibility bridges. | Start replacing imports in all maintained integrations and update tests to exercise canonical entrypoints. |
| **v0.15.0** | Compatibility freeze | No new feature logic or new references to deprecated modules are allowed outside approved shims/tests. CI blocks new deprecated references and telemetry counts remaining usage. | Finish code migration away from `genecoder.api`, `genecoder.pipeline`, and `genecoder.compat.channel_sim` / `error_simulation`. |
| **v0.16.0** | Planned removal | Remove `genecoder.api`, `genecoder.pipeline`, `genecoder.compat.v1.api_adapter`, and `genecoder.compat.v1.pipeline_adapter`. Root-package exports remain canonical-only. | All orchestration and plugin imports must already be on `genecoder.app` / `genecoder.sdk`. |
| **v0.17.0** | Compatibility package cleanup | Remove `genecoder.compat.channel_cli`, `genecoder.compat.legacy.sequence_pipeline`, and test-only `genecoder.compat.legacy.cloud.*` shims unless telemetry-backed exception is documented in release notes. | Remove any remaining `genecoder.compat.*` imports from downstream maintenance branches. |
| **v0.18.0** | Final cleanup gate | Remove any residual deprecated top-level compatibility re-export stubs that exist only for patch-level grace periods. | Downstream consumers must be fully canonical-interface only. |

## Canonical replacement map

| Deprecated path | Canonical replacement | Notes |
| --- | --- | --- |
| `genecoder.pipeline` | `genecoder.app.RunPipelineUseCase` and `genecoder.app.RunPipelineRequest` | Use `genecoder.app` for orchestration, artifact policy, and typed request modeling. |
| `genecoder.api` | `genecoder.sdk.plugins` | Plugin interfaces are part of the supported SDK contract. |
| `genecoder.compat.v1.pipeline_adapter` | `genecoder.app` | Versioned adapter is only a temporary forwarder. |
| `genecoder.compat.v1.api_adapter` | `genecoder.sdk.plugins` | Versioned adapter is only a temporary forwarder. |
| `genecoder.compat.legacy.sequence_pipeline` | `genecoder.app.sequence_pipeline` only as a temporary stepping stone, then `genecoder.app.RunPipelineUseCase` | Prefer migrating directly to `RunPipelineUseCase`. |
| `genecoder.compat.channel_cli` | `genecoder.core` profile helpers | Use modern channel profile helpers. |
| `genecoder.compat.channel_sim` / `genecoder.compat.error_simulation` | `genecoder.channel_engine` internals only where explicitly needed, otherwise canonical app/sdk workflows | Do not add new external usage. |

## Orchestration entrypoint migration

See [`docs/orchestration_migration.md`](orchestration_migration.md) for the authoritative mapping from deprecated orchestration imports to canonical APIs.

## Channel attribute rename

The `Channel.error_rate` attribute has been renamed to `Channel.substitution_prob`. Accessing or setting `error_rate` still works but raises a `DeprecationWarning` and will be removed in a future release. Update any code that relies on `error_rate` to use `substitution_prob` instead.

## Simulator `SequenceBatch` adoption

Simulators must return `SequenceBatch` objects from `simulate`. When porting an older plugin:

1. Wrap raw `str` inputs by calling `SequenceBatch.build` with a `batch_id` and `batch_seed`.
2. Clone the batch with `genecoder.simulators.batch_utils.clone_batch` before mutating it in place.
3. Record coverage and dropout metadata via `RESULT_*` constants and invoke `finalize_batch_statistics` to generate aggregate metrics.
4. Reuse `apply_legacy_simulator` for simple passthrough simulators that do not yet understand batches.

## Channel CLI legacy boundary

`genecoder.cli.channel` now resolves profiles and mutation behavior from `genecoder.simulators.*` modules and the typed channel option adapter in `genecoder.simulators.channel_cli_adapter`. Legacy `channel_engine.legacy_adapter` usage is restricted to compatibility shims under `genecoder.compat.*` and deprecated top-level re-export modules. If you still use legacy flags such as `--indel-profile` with adapter-era aliases, the CLI emits migration warnings and maps them onto modern profile names (`illumina`, `nanopore`).
