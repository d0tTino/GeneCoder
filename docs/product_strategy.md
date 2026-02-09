# Product Strategy & Delivery Status

This document is the canonical status snapshot for what GeneCoder ships today versus what is still missing.

## Current Capabilities

### 1) Built-in sequencing + decay simulation

GeneCoder currently ships first-party simulation support for:

- **Illumina** channels via the `genecoder.simulators.illumina` package and the bundled Illumina-focused presets.
- **Nanopore** channels via built-in nanopore simulator modules and profile support.
- **Storage decay** via the built-in decay stage that can be chained with sequencing simulation in preset pipelines.

These paths are exercised by shipped bundle presets such as:

- `configs/gold.yaml` (MiSeq-style + decay)
- `configs/rs_illumina_pipeline.yaml` (Illumina profile + decay)
- `configs/fountain_nanopore_pipeline.yaml` (Nanopore profile + decay)

### 2) ECC and codec breadth (core + optional extras)

GeneCoder supports a broad codec/FEC surface area:

- **Core presets/checklists:** Reed–Solomon and Fountain workflows.
- **Built-in encoding options:** base5/base6 alphabet modes.
- **Optional extras:**
  - Chamaeleo-backed codecs: GC, Fountain, Goldman, Church, Grass, Blawat.
  - Advanced ECC integrations: LDPC, BCH, RaptorQ.
  - AI-assisted plugins: DNAformer and DeepDNA.

### 3) CLI bundles, dashboard, and reporting paths

Operational workflow paths already shipped:

- End-to-end pipeline orchestration via `genecli`/`genecoder`:
  - `bundle run` for a single preset
  - `bundle sweep` for side-by-side preset runs
- Metrics capture and manifest indexing via `--metrics-path`, `--manifest-index`, and `--emit-manifest-report`.
- Dashboard launch support with `--launch-dashboard`.
- HTML reporting path through `genecli html-report` for manifest summaries.

## Known Gaps

The primary missing capabilities are quality and scale hardening layers, not baseline feature coverage:

- **Model calibration quality:** stronger calibration and parity validation against wet-lab/public benchmark datasets.
- **Large-scale HPC orchestration:** robust multi-node scheduling/orchestration beyond current MPI-oriented integrations.
- **Economic cost modeling:** first-class synthesis/sequencing/storage cost models for scenario planning and tradeoff analysis.

_Last validated against codebase: 2026-02-09._
