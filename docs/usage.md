# Usage

## Command-Line Interface (CLI)

Run encoding or decoding with `src/cli.py`:

```bash
python src/cli.py <command> --input-files <path> [--output-file <path>] [--output-dir <dir>] --method <method_name> [--fec <fec_method>] [options]
```

See [WORKFLOWS.md](../WORKFLOWS.md) for a step-by-step overview.

## Graphical User Interface (GUI)

Launch the Flet application:

```bash
python src/flet_app.py
```

The GUI exposes encoding options, error correction choices and displays metrics and analysis plots.
