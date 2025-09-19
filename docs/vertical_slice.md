# Vertical Slice Walkthrough

This guide demonstrates a minimal end-to-end run of GeneCoder. A convenient
PowerShell script is provided for Windows users to run the demo automatically.

## Prerequisites

- **Python 3.11+**
- GeneCoder uses **Poetry** for dependency management.
- Ensure `pip` is up to date before installing dependencies:
  `python -m pip install --upgrade pip`

## Environment Setup

```bash
git clone https://github.com/d0tTino/GeneCoder.git
cd GeneCoder
extras on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_vertical_slice.ps1
```

If PowerShell blocks the script, run the following once from an elevated
prompt to allow local scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Ensure you have the **Terminal** or PowerShell 7 installed so that `poetry`
and `python` are available on your `PATH`.

The script prints the GeneCoder version, runs the test suite, launches the Flet
GUI and finally starts the FastAPI server. The last lines of output should
include:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Open that address in your browser to confirm the server is reachable.

### Automated Shell Script

For Linux, macOS and other Unix-like systems a portable shell version of the
demo script is provided:

```bash
bash scripts/vertical_slice.sh
```

It performs the same actions as the Windows script: upgrading ``pip``,
installing optional extras, running the smoke tests, launching the Flet GUI and
then starting the FastAPI server.

## CLI Smoke Test

Ensure the command line interface is available and the test suite passes. On
Windows this is run from PowerShell just like on Linux:

```bash
genecli --version
poetry run pytest -q
```

## Bundle Workflow

An example configuration file at `configs/vertical_slice_demo.yaml` demonstrates
using a simulator and Hamming FEC. The `pipeline` section selects the built-in
`hiseq` profile for the Illumina simulator. Run the bundle with:

```bash
genecli bundle run configs/vertical_slice_demo.yaml --cache-dir runs
```

For a pipeline run that records usage statistics see
`configs/pipeline_metrics.yaml`.

The `scripts/vertical_slice.sh` helper executes the same command automatically
as part of the demo.

## Channel Configuration

A unified configuration describing sequencing simulators and synthesis
constraints is provided at `configs/channel_demo.yaml`. Another example at
`configs/dnarsim_profile.yaml` selects the `r9` Nanopore profile. Apply the
channel step using:

```bash
genecli channel run configs/channel_demo.yaml
```

The `configs/decay_demo.yaml` file demonstrates storage degradation using
the new decay channel. The pipeline first applies the Illumina simulator
before running the decay stage:
```yaml
input: encoded/message.fasta
output: decay_output.fasta

simulators:
  - illumina

decay:
  half_life: 1000   # days
  variation: 0.1

pipeline:
  illumina_profile: hiseq
```

The ``half_life`` value indicates the time required for half the DNA to
degrade while ``variation`` adds randomness across sequences. This results in
deletion errors that emulate gradual decay during storage.

Run the pipeline with:

```bash
genecli channel run configs/decay_demo.yaml
```


## Encode Example

Run a single encode step with error correction and channel simulation:

```bash
genecli encode input.bin output.fasta --codec chamaeleo_gc --fec reed_solomon --channel illumina
```

This creates `output.fasta.manifest.json` containing encoding metrics.

### Review the Metrics Outputs

The manifest captures all of the quality measurements from the encode run.
Use these commands to inspect substitution, insertion, deletion and coverage
results in different formats so you can confirm the channel behaviour.

1. **Inspect the raw JSON.** The manifest stores error counts under the
   `metrics` key. Filter them with `jq` (or your preferred JSON viewer):

   ```bash
   jq '.metrics | {substitutions, insertions, deletions, coverage, coverage_distribution}' \
       output.fasta.manifest.json
   ```

   A value of `2` under `substitutions` means two base substitutions were
   introduced across the simulated reads. `coverage` reports the average read
   depth returned by the simulator, while `coverage_distribution` (when
   present) lists how many sequences were observed at each depth bucket.

2. **Generate a standalone HTML summary.** Build a static report that can be
   shared with collaborators:

   ```bash
   genecli html-report --manifest output.fasta.manifest.json --output-file reports/vertical-slice.html
   ```

   Open `reports/vertical-slice.html` in a browser to review the GC, homopolymer
   and ECC sections, keeping the JSON snippet handy for the exact error counts.

3. **Launch the interactive dashboard.** The Streamlit view provides charts for
   the error metrics and coverage distribution:

   ```bash
   genecli dashboard output.fasta.manifest.json
   ```

   The **Error Rates** cards list the substitution, insertion and deletion
   counts. Expand the **Error Histograms** multiselect in the sidebar to view
   per-read distributions. The **Read Coverage** chart visualises the
   `coverage_distribution` array, defaulting to the single `coverage` value when
   no histogram is available.

## Launch the GUI

```bash
python -m genecoder.flet_app
```

## Start the FastAPI Server

```bash
poetry run uvicorn web.main:app --reload
```

Open <http://localhost:8000> in your browser to view the landing page.

## Dashboard

The server includes a small dashboard for quick sequence analysis. Navigate to
`http://localhost:8000/dashboard` and paste a DNA sequence to view GC content,
homopolymer metrics and heatmap plots. The GUI also provides an "Open Web
Dashboard" button under the Analysis tab which launches the same page in your
default browser.

Metrics from the encode example above can also be inspected locally:

```bash
genecli dashboard output.fasta.manifest.json
```

## Streaming Encode and Resume

Large files can be encoded and decoded in streaming mode to reduce memory usage.
Each streaming run writes a `<output>.stream.manifest` file containing chunk offsets
and SHA-256 hashes. Specify a chunk size in bytes and pass `--resume` to
continue a partial run. Previously completed chunks are verified against the
manifest before processing resumes:

```bash
# initial encode
genecli encode --input-files big.bin --output-file big.fasta \
  --stream --chunk-size 1048576

# resume if interrupted
genecli encode --input-files big.bin --output-file big.fasta \
  --stream --chunk-size 1048576 --resume

# decoding with resume support
genecli decode --input-files big.fasta --output-file big.bin \
  --stream --chunk-size 1048576 --resume
```

Using `--mirror` on the `encode` command automatically launches the helix
viewer displaying the sequence and its reverse complement:

```bash
genecli encode --input-files hello.txt --output-file hello.fasta --mirror
```

This document condenses the key steps from the installation and usage guides into a quick demo.

Contributors may prefer to run these commands inside the provided
**devcontainer** for a ready-to-use environment.
