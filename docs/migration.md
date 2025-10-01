# Migration Guide

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
