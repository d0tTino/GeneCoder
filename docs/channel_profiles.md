# Channel profiles at a glance

GeneCoder ships with built-in Illumina and Nanopore presets so you can match simulator settings to a given instrument without memorizing every flag. The tables below summarize the fallback defaults baked into the codebase and how to select them from the CLI.

## Illumina profiles

Named Illumina presets come from `ILLUMINA_PROFILES` and assume a consensus of single-pass reads (coverage depth = 1) unless overridden. Use them when you need low indel rates and platform-specific substitution tuning.

| Profile | Substitution rate | Insertion rate | Deletion rate | Coverage depth | When to use |
| --- | --- | --- | --- | --- | --- |
| `hiseq` | 5e-4 | 5e-5 | 5e-5 | 1 | Balanced accuracy for legacy HiSeq-style runs or general-purpose Illumina simulations. |
| `miseq` | 1e-3 | 1e-4 | 1e-4 | 1 | MiSeq V3-style experiments with slightly higher substitution noise. |
| `novaseq` | 3e-4 | 3e-5 | 3e-5 | 1 | NovaSeq S4‑like throughput with the lowest substitution rate among the presets. |
| `nova` | 3e-4 | 3e-5 | 3e-5 | 1 | Alias of NovaSeq defaults for compatibility with existing configs. |

Use a profile in `genecli` with the Illumina simulator:

```bash
genecli channel --simulator illumina --illumina-profile hiseq \
    --input-file encoded.fasta --output-file illumina_hiseq.fasta

# Increase coverage on top of the preset
genecli channel --simulator illumina --illumina-profile novaseq \
    --illumina-depth 5 --input-file encoded.fasta --output-file novaseq_depth5.fasta
```

## Nanopore profiles

The Nanopore channel falls back to `_FALLBACK_PROFILE_DATA` when YAML overrides are absent. Rates are higher and tuned for long-read indel patterns, with a default coverage of 30× for consensus calling.

| Profile | Substitution rate | Insertion rate | Deletion rate | Coverage | When to use |
| --- | --- | --- | --- | --- | --- |
| `minion` | 0.019 | 0.046 | 0.065 | 30 | Emulate portable MinION runs with elevated indels and a conservative 13% total error rate. |
| `promethion` | 0.015 | 0.02 | 0.045 | 30 | Larger PromethION flow cells with moderate indels and higher throughput assumptions. |
| `r10` | 0.01 | 0.015 | 0.025 | 30 | R10 chemistry with the lowest default indels among the presets; good for high-accuracy nanopore studies. |

Select a Nanopore profile from the CLI:

```bash
genecli channel --simulator nanopore --nanopore-profile minion \
    --input-file encoded.fasta --output-file minion_reads.fasta

# Override coverage while keeping the preset rates
genecli channel --simulator nanopore --nanopore-profile r10 --nanopore-coverage 60 \
    --input-file encoded.fasta --output-file r10_cov60.fasta
```

### What Nanopore presets record in manifests and dashboards

Nanopore presets also populate manifest summaries and dashboard panels. When you
run a profile such as `r10.4` (`genecli channel --nanopore-profile r10.4`), the
resulting `.manifest.json` captures:

* The GC guardrails in effect (`gc_min`/`gc_max`, defaulting to 45–55%).
* The enforced homopolymer cap (`max_homopolymer`, default 3).
* The preset coverage target for the selected profile (30× unless overridden).

View the same fields in the generated manifest HTML report (via
`genecli html-report`) or in the Streamlit dashboard (`genecli dashboard
<manifest>` or `--launch-dashboard` during bundle runs). Both UIs surface GC
range and homopolymer panels alongside coverage gauges for Nanopore runs. See
[`configs/nanopore.yml`](../configs/nanopore.yml) for the preset defaults that
back each profile.
