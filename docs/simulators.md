# Read Simulators

GeneCoder supports both built-in error models and adapters to external nanopore simulators.

## Built-in simulators

- **simple** — random substitutions. Use `genecli channel --sub-prob`
  (and optionally `--ins-prob`/`--del-prob`) or `--simulator simple`.
- **indel** — introduces insertions and deletions in addition to substitutions.
- **none** — disable simulation (the default).
- **illumina** — simple Illumina read errors. Customize rates with
  `--illumina-sub-rate`, `--illumina-ins-rate` and `--illumina-del-rate`. Depth
  and quality can be adjusted using `--illumina-depth`, `--illumina-quality` and
  `--illumina-context`.
- **nanopore** — alias for `d2sim`. Customize rates with `--nanopore-sub-rate`,
  `--nanopore-ins-rate` and `--nanopore-del-rate`.

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

GeneCoder automatically falls back to the internal error model when an external
simulator is missing or fails.

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
```

Use `GENECODER_SIM_SEED=<seed>` to make runs reproducible.
Set `GENECODER_D2SIM_OPTIONS`, `GENECODER_DNARSIM_OPTIONS` or
`GENECODER_SQUIGULATOR_OPTIONS` to forward extra flags to the respective
simulator automatically. The same options can be specified on the command line
with ``--d2sim-options``, ``--dnarsim-options`` and ``--squigulator-options``.
