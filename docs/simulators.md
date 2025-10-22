# Read Simulators

GeneCoder supports both built-in error models and adapters to external nanopore simulators.

## Built-in simulators

- **simple** — random substitutions. Use `genecli channel --sub-prob`
  (and optionally `--ins-prob`/`--del-prob`) or `--simulator simple`.
- **indel** — introduces insertions and deletions in addition to substitutions.
- **none** — disable simulation (the default).
- **illumina** — simple Illumina read errors. Customize rates with
  `--illumina-sub-rate`, `--illumina-ins-rate` and `--illumina-del-rate`. Depth
  and the base-quality distribution can be adjusted using `--illumina-depth`,
  `--illumina-quality` and `--illumina-context`.
- **nanopore** — alias for `d2sim`. Customize rates with `--nanopore-sub-rate`,
  `--nanopore-ins-rate` and `--nanopore-del-rate`.

### Nanopore fallback profiles

GeneCoder ships Nanopore presets that mirror `d2sim` profiles so decoding
pipelines continue to work even when the external binary is unavailable. The
fallback draws its defaults from:

- `configs/nanopore.yml` – substitution/indel/coverage values for profiles such
  as `minion`, `promethion` and `r10`.
- `configs/nanopore_context.yaml` – context-aware insertion/deletion tables used
  when the external simulator cannot provide them.

Both files are optional; if they are missing the embedded presets bundled with
GeneCoder are used instead. Custom profiles or context overrides can be supplied
with `--profile`, `--nanopore-profile`, `--nanopore-context` or the YAML
configuration helpers. When the `d2sim` or `desp` executables are unavailable,
the CLI falls back to these presets to mutate reads before continuing with the
decode pipeline.

Example YAML:

```yaml
simulators:
  - name: nanopore_d2sim
    substitution_rate: 0.05
    insertion_rate: 0.01
    deletion_rate: 0.02
```

`GENECODER_SIM_SEED` can be set to an integer to reproduce the randomness used
by these simulators.

## External tools

Additional simulators can be used if the corresponding commands are available on
your `PATH`:

- **d2sim** — [D2Sim](https://github.com/kurimsw/d2sim). Clone the repository,
  build the binary (typically with `make`) and ensure the `d2sim` executable is
  on your `PATH`.
- **dnarsim** — [DNArSim](https://github.com/Purdue-ScottLab/DNArSim). Follow the
  project instructions to compile the tool and add `dnarsim` to your `PATH`.
- **squigulator** — [Squigulator](https://github.com/hasindu2008/squigulator).
    Download a release or build from source so that the `squigulator` command is
    available.
- **desp** — [DeSP](https://github.com/atcg/deSP) nanopore simulator. Install
  the `desp` binary and ensure it is on your `PATH` to activate the adapter.

GeneCoder automatically falls back to the internal error model when an external
simulator is missing or fails.

### DeSP adapter

The optional DeSP integration is registered under both `desp` and
`nanopore_desp`. Provide the binary via your `PATH` or a virtual environment and
install any dependencies recommended by the
[DeSP project](https://github.com/atcg/deSP). Once installed you can invoke it
from the CLI or YAML pipelines:

```bash
genecli decode --simulator desp --desp-options "--model r10" <other options>
genecli channel --simulator nanopore_desp --profile promethion <other options>
```

Use `--desp-options` or set `GENECODER_DESP_OPTIONS` to forward additional
flags to the `desp` binary. Arguments are validated for safety before being
passed through. If the executable exits with an error or is not present the
channel automatically reverts to the built-in Nanopore fallback described
above, so decode commands succeed with deterministic settings even without the
external dependency.

### Installation tips

Most simulators require compilation. A typical workflow is:

```bash
git clone <repo-url>
cd <project>
make
sudo make install  # or copy the binary to a directory on your PATH
```

Verify the installation by running the command directly:

```bash
d2sim --help
```

Once the binary is accessible, GeneCoder can invoke it via the `--simulator`
option or `simulate_reads()` API.

### Installing `d2sim`

```bash
git clone https://github.com/kurimsw/d2sim.git
cd d2sim
make
sudo make install  # or copy the binary to a directory on your PATH
```

### Installing `DNArSim`

```bash
git clone https://github.com/Purdue-ScottLab/DNArSim.git
cd DNArSim
make
sudo make install
```

### Installing `squigulator`

```bash
git clone https://github.com/hasindu2008/squigulator.git
cd squigulator
make
sudo make install
```

## IlluminaInSilicoSeqChannel

`IlluminaInSilicoSeqChannel` wraps the optional
[InSilicoSeq](https://github.com/HadrienG/InSilicoSeq) Illumina simulator. It
invokes the `insilicoseq` CLI when present and falls back to the built-in
Illumina model otherwise.

### Command-line options

```bash
genecli decode --simulator illumina_insilicoseq --profile hiseq <other options>
genecli decode --simulator illumina_insilicoseq --insilicoseq-options "--num_reads 1000" <other options>
```

Profiles such as `miseq` and `hiseq` map to the corresponding InSilicoSeq
presets. Additional flags can be supplied with `--insilicoseq-options`.

### Sample quality-profile file

Illumina simulators accept per-base quality distributions via JSON or YAML. A
sample configuration is provided in `configs/illumina_profile.yaml`:

```yaml
simulators:
  - name: insilicoseq
    read_length: 150
pipeline:
  illumina_profile: hiseq
  illumina_depth: 1
  illumina_quality_distribution: null
```

## Command-line usage

Apply substitutions and indels with chosen probabilities using the ``channel`` command:

```bash
genecli channel --input-file input.fasta --output-file corrupted.fasta \
    --sub-prob 0.02 --ins-prob 0.01 --del-prob 0.01
genecli decode corrupted.fasta --output-file decoded.bin <other options>
```

Invoke a sequencing simulator before decoding:

```bash
genecli decode --simulator illumina <other options>
genecli decode --simulator nanopore <other options>
```

Invoke an external simulator before decoding:

```bash
genecli decode --simulator d2sim <other options>
```

Provide additional parameters to ``d2sim`` using ``--d2sim-options``:

```bash
genecli decode --simulator d2sim --d2sim-options "--seed 42" <other options>
```

Provide extra flags to ``dnarsim`` or ``squigulator`` in the same way:

```bash
genecli decode --simulator dnarsim --dnarsim-options "<opts>" <other options>
genecli decode --simulator squigulator --squigulator-options "<opts>" <other options>
genecli decode --simulator desp --desp-options "<opts>" <other options>
```

Use `GENECODER_SIM_SEED=<seed>` to make runs reproducible.
Set `GENECODER_D2SIM_OPTIONS`, `GENECODER_DNARSIM_OPTIONS`,
`GENECODER_SQUIGULATOR_OPTIONS` or `GENECODER_DESP_OPTIONS` to forward extra
flags to the respective simulator automatically. The same options can be
specified on the command line with ``--d2sim-options``, ``--dnarsim-options``,
``--squigulator-options`` and ``--desp-options``.
