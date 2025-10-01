# Migration Guide

## Channel attribute rename

The `Channel.error_rate` attribute has been renamed to `Channel.substitution_prob`.
Accessing or setting `error_rate` still works but raises a `DeprecationWarning` and
will be removed in a future release. Update any code that relies on `error_rate`
to use `substitution_prob` instead.

## Migrating to the multi-oligo pipeline

GeneCoder 0.18 promotes the multi-oligo encode → channel → decode flow. Earlier releases operated on single FASTA records, so existing automation may need small adjustments:

- **Encoding** – the new streaming mode (`--stream` with `--chunk-size`) writes a `SequenceBatch` containing many oligos plus a manifest. Leave streaming disabled to retain the previous single-record output. The CLI still honours legacy options such as `--auto-ext` and `--capsule`.
- **Channel simulation** – `genecli channel run` now expects the streamed FASTA with batch metadata. Legacy single-record files continue to work because `SequenceBatch.from_fasta` wraps them automatically, marking the batch as `legacy`. To keep scripts quiet, pass `--suppress-constraint-warnings` (or set `GENECODER_DISABLE_CONSTRAINT_WARNINGS=1`) just like before. The YAML loader also keeps the historical `constraints` key as an alias for `synthesis` so older configs do not need to change.
- **Dropout controls** – the pipeline uses the new compatibility flags `--dropout-rate`, `--coverage-distribution` and `--synthesis-loss` on `genecli channel` (and the matching YAML fields) to emulate the single-sequence error rate tunables. Supply the same values you used previously to reproduce older simulations, then tighten them gradually to explore multi-oligo loss scenarios.
- **Decoding** – `genecli decode` accepts both legacy FASTA and new multi-oligo batches. No flags are required, but you can continue to rely on familiar arguments such as `--output-dir` and `--file-type` to mirror older automation.

Finally, rebuild the documentation (`mkdocs serve`) to confirm your guides and READMEs reference the updated flow before shipping your migration notes.
