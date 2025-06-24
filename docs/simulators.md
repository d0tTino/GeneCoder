# Read Simulators

GeneCoder supports both built-in error models and adapters to external nanopore simulators.

## Built-in simulators

- **simple** — random substitution errors. Use `--simulate-errors` on the CLI or
  `--simulator simple`.
- **indel** — introduces insertions and deletions in addition to substitutions.
- **none** — disable simulation (the default).
- **nanopore** — alias for `d2sim`.

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

## Command-line usage

Apply simple substitutions with a chosen probability:

```bash
genecoder decode --simulate-errors 0.02 <other options>
```

Invoke an external simulator before decoding:

```bash
genecoder decode --simulator d2sim <other options>
```

Use `GENECODER_SIM_SEED=<seed>` to make runs reproducible.
