# Migration Guide

## Canonical integration surface (supported API)

Starting in **v0.14.0**, GeneCoder supports external integrations only through:

- `genecoder.sdk` (stable external SDK requests/results and plugin contracts).
- `genecoder.app` (application-layer use-case contracts for runtime orchestration).

Deprecated facades (`genecoder.api`, `genecoder.pipeline`) now forward through versioned adapters in `genecoder.compat.v1` and do **not** add behavior beyond forwarding.

## Orchestration entrypoint migration

See [`docs/orchestration_migration.md`](orchestration_migration.md) for the authoritative mapping from deprecated orchestration imports (`genecoder.pipeline`, `genecoder.api`, and `SequencePipeline`) to canonical APIs.

## Explicit removal milestones

- **v0.15.0**: last release where `genecoder.api` and `genecoder.pipeline` remain available with deprecation warnings.
- **v0.16.0**: removal target for both deprecated facades; integrations must be on `genecoder.sdk` + `genecoder.app`.
- **v0.16.0**: first-party tests are canonical-import only except dedicated compatibility/deprecation tests.

## Channel attribute rename

The `Channel.error_rate` attribute has been renamed to `Channel.substitution_prob`.
Accessing or setting `error_rate` still works but raises a `DeprecationWarning` and
will be removed in a future release. Update any code that relies on `error_rate`
to use `substitution_prob` instead.

## Simulator ``SequenceBatch`` adoption

Simulators must return ``SequenceBatch`` objects from ``simulate``. When porting
an older plugin:

1. Wrap raw ``str`` inputs by calling ``SequenceBatch.build`` with a ``batch_id``
   and ``batch_seed``. The helper fills in deterministic oligo identifiers.
2. Clone the batch with ``genecoder.simulators.batch_utils.clone_batch`` before
   mutating to avoid rewriting the caller's data in place.
3. Record coverage and dropout metadata via ``RESULT_*`` constants and then
   invoke ``finalize_batch_statistics`` to generate aggregate metrics.
4. Reuse ``apply_legacy_simulator`` for simple passthrough simulators that do not
   yet understand batches; it automatically produces ``SequenceBatch`` outputs.


## Channel CLI legacy boundary

`genecoder.cli.channel` now resolves profiles and mutation behavior from `genecoder.simulators.*` modules and the typed channel option adapter in `genecoder.simulators.channel_cli_adapter`.

Legacy `channel_engine.legacy_adapter` usage is restricted to compatibility shims under `genecoder.compat.*` and deprecated top-level re-export modules. If you still use legacy flags such as `--indel-profile` with adapter-era aliases, the CLI emits migration warnings and maps them onto modern profile names (`illumina`, `nanopore`).
