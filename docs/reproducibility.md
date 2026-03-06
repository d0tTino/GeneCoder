# Reproducibility Guide

Deterministic experiments make it easier to compare codecs, simulators and
pipelines across machines. This guide captures the minimum runtime requirements
for GeneCoder and the knobs you can tune to make channel simulations repeatable.

## Supported Python Versions

GeneCoder targets **Python 3.11 or newer**. The CLI and bundled plugins are
actively tested on CPython 3.11 and 3.12. Earlier versions are unsupported and
will miss typing improvements relied on by the codebase. Install the toolchain
through [Poetry](https://python-poetry.org/) or your preferred virtual
environment manager, but ensure that the interpreter is at least version 3.11.

## Recommended Operating Systems and Hardware

While GeneCoder runs on Linux, macOS and Windows (via WSL2 or the native
installers), the following setups provide the smoothest experience when running
full pipelines:

- **Linux**: Ubuntu 22.04 LTS or Fedora 39 on a 64-bit system.
- **macOS**: Ventura 13 or Sonoma 14 on Apple Silicon or Intel hardware.
- **Windows**: Windows 11 with WSL2 enabled and an Ubuntu 22.04 distribution.

Regardless of platform, plan for:

- **CPU**: 4 physical cores (or better) to parallelize encode and channel steps.
- **Memory**: 16&nbsp;GB RAM to accommodate simultaneous simulator and decoder
  workloads.
- **Storage**: 10&nbsp;GB of free SSD space for Poetry environments, simulator
  caches and manifest artifacts.

These specs match the footprint observed when enabling the optional GUI, web and
FEC extras listed in the quick start section of the README. Lightweight encode
and decode runs will work on smaller systems, but the margin above prevents
unexpected slowdowns or swapping when running multi-oligo experiments.

## Seeding the Simulation RNG

GeneCoder centralizes all pseudo-random number generation through the
`GENECODER_SIM_SEED` environment variable. Export it before invoking any CLI
command to lock in deterministic noise sequences:

```bash
export GENECODER_SIM_SEED=12345
```

The CLI also exposes `--seed` wherever randomness is involved. Passing
`--seed 12345` automatically sets the same environment variable for the duration
of the command, so you can either export it globally or set it per invocation:

```bash
genecli pipeline input.txt decoded.txt --channel illumina --illumina-profile miseq --seed 12345
```

Any sub-process launched by the CLI (including bundled simulators) inherits the
seed, ensuring reproducible dropout patterns, coverage distributions and quality
score sampling.

## Pinning Illumina Profiles

Illumina simulations expose named profiles that adjust quality scores, read
lengths and dropout behaviour. To reproduce specific lab presets, explicitly
select the desired profile in your CLI commands or bundle configuration.

### CLI invocations

```bash
# MiSeq-style short reads
GENECODER_SIM_SEED=12345 genecli pipeline \
  examples/pipeline_demo_input.txt decoded_miseq.txt \
  --channel illumina --illumina-profile miseq

# NovaSeq high-throughput profile
GENECODER_SIM_SEED=12345 genecli pipeline \
  examples/pipeline_demo_input.txt decoded_novaseq.txt \
  --channel illumina --illumina-profile novaseq
```

### Bundle and pipeline configurations

Add the profile under the `simulate` stage so the bundle executor chooses the
same preset each run:

```yaml
simulate:
  simulators:
    - illumina
  pipeline:
    illumina_profile: miseq_v3
```

Switch `illumina_profile` to `hiseq_high_coverage`, `novaseq_s4`, or any other
registered profile to lock in different quality curves. When combined with a
fixed `GENECODER_SIM_SEED`, MiSeq V3 and NovaSeq S4 simulations yield identical
error statistics across repeated runs, which is ideal for regression testing and
benchmarking new codecs.

## Validating sequencing profile error rates

Both the Nanopore and Illumina simulators now expose helper hooks that emit
aggregate substitution/insertion/deletion counts for a deterministic run. The
pytest suite drives these hooks to ensure the bundled configuration files stay
in sync with the observed behaviour:

- `tests/test_nanopore_context_profile.py` calls
  `genecoder.simulators.nanopore_batch.observe_error_rates` for each profile in
  `configs/nanopore.yml` and fails if the measured error rates drift beyond the
  documented tolerances.
- `tests/test_illumina_coverage_quality.py` uses
  `IlluminaChannel.observe_error_rates` together with the presets defined in
  `src/genecoder/simulators/illumina/profiles.py` to guarantee the short-read
  channel matches its specification.

When new empirical data arrives you only need to update the profile files and
adjust the tolerances in the corresponding tests. Use the helper functions to
measure the new rates (optionally seeding `GENECODER_SIM_SEED` for repeatable
experiments) and tighten the assertions once the numbers stabilise. This keeps
future regression runs honest and provides a lightweight checklist for
contributors submitting improved sequencing statistics.


## Reproducible two-tier testing

The CI pipeline runs tests in two deterministic tiers:

1. **Core tier**: `pytest -m core --test-tier=core`
   - Targets the minimal dependency profile.
   - Must complete with **zero skipped tests**.
2. **Optional integration tier**: `pytest -m integration_optional --test-tier=integration`
   - Covers optional dependencies and external executables.
   - Skips are allowed when dependencies are unavailable.
   - A dependency availability report is generated via
     `python scripts/report_optional_test_dependencies.py`.

To reproduce CI behavior locally, run:

```bash
# Core (minimal)
python -m pip install -e . pytest pytest-xdist pytest-cov
pytest -m core --test-tier=core --junitxml=artifacts/core-junit.xml -q

# Optional integrations
poetry install --with gui,web,dev   --extras ldpc --extras fountain --extras bch   --extras raptorq --extras deepdna --extras chamaeleo   --no-interaction --no-root
python scripts/report_optional_test_dependencies.py
poetry run pytest -m integration_optional --test-tier=integration -rs -q
```

Keeping these commands and dependency profiles pinned in automation makes test
outcomes easier to compare across machines and over time.
