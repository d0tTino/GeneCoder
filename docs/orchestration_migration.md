# Orchestration Migration Map

## Authoritative orchestration entrypoint

The single supported orchestration entrypoint is:

- `genecoder.app.RunPipelineUseCase`

Canonical runtime execution is modeled by:

- `genecoder.core.CanonicalRuntimeResult`

`RunPipelineUseCase` is the transport-agnostic boundary for CLI, SDK, and UI integrations.
Compatibility facades remain available only during deprecation windows.

## Legacy import migration map

| Legacy import | Status | Canonical replacement |
| --- | --- | --- |
| `genecoder.pipeline` | Deprecated facade | `genecoder.app.RunPipelineUseCase` (primary), `genecoder.core.run_canonical_pipeline` (internal runtime) |
| `genecoder.api` | Deprecated facade | `genecoder.sdk.plugins` |
| `genecoder.app.pipeline_runtime.SequencePipeline` | Deprecated compatibility adapter | `genecoder.app.RunPipelineUseCase` |
| `SequencePipeline` (from `genecoder` package root) | Deprecated compatibility adapter | `genecoder.app.RunPipelineUseCase` |

## Boundary policy

- New orchestration features **must not** be added in `genecoder.compat.*`.
- Deprecated module updates are limited to forwarding, warning text, or removal work.
- CI tests enforce that new modules do not import deprecated facades outside approved boundary files.
