# GeneCoder Workflows

This document outlines the high level steps for encoding and decoding data with GeneCoder. Both the command line interface (CLI) and the Flet based graphical interface share the same processing pipeline under the hood.

## Encoding a File to DNA

### CLI
1. `genecoder.cli` reads the input file.
2. If `--fec hamming_7_4` is selected, `genecoder.hamming_codec.encode_data_with_hamming` adds binary level FEC.
3. The chosen encoder from `genecoder.encoders` or `genecoder.huffman_coding` converts the bytes to DNA:
   - `encode_base4_direct`
   - `encode_huffman`
   - `encode_gc_balanced`
4. Optional parity bits are applied via `genecoder.error_detection` when using base‑4 or Huffman.
5. Optional Triple‑Repeat FEC is applied with `genecoder.error_correction.encode_triple_repeat`.
6. `genecoder.formats.to_fasta` creates the FASTA record which is written to disk.

### Flet GUI
1. `src/flet_app.py` loads the selected file asynchronously when *Encode* is clicked.
2. The same encoding functions (`encode_base4_direct`, `encode_huffman`, `encode_gc_balanced`) are executed.
3. Triple‑Repeat FEC, if enabled, is applied using `encode_triple_repeat`.
4. The output FASTA string is displayed and can be saved from the interface.
5. Metrics and plots are produced using helpers in `genecoder.plotting`.

### Encoding Flow (text diagram)
```
Input File
  ↓
[Optional] Hamming FEC → encode_data_with_hamming
  ↓
Encoding Method → encode_base4_direct | encode_huffman | encode_gc_balanced
  ↓
[Optional] Parity via error_detection
  ↓
[Optional] Triple‑Repeat FEC → encode_triple_repeat
  ↓
FASTA formatting → to_fasta
  ↓
Encoded FASTA file
```

## Decoding DNA back to a File

### CLI
1. `genecoder.cli` reads the FASTA file and parses it with `genecoder.formats.from_fasta`.
2. If `fec=triple_repeat` is indicated, `genecoder.error_correction.decode_triple_repeat` is invoked.
3. The primary decoding function is chosen based on the header:
   - `decode_base4_direct`
   - `decode_huffman`
   - `decode_gc_balanced`
4. Parity checks occur through `genecoder.error_detection` when applicable.
5. If the header contains `fec=hamming_7_4`, `genecoder.hamming_codec.decode_data_with_hamming` restores the original bytes.
6. The resulting data is written to the specified output file.

### Flet GUI
1. When *Decode* is clicked in `src/flet_app.py`, the selected FASTA file is parsed by `from_fasta`.
2. Triple‑Repeat FEC and then the main decoding method are applied using the same modules as in the CLI.
3. Decoded bytes can be saved from the interface.

### Decoding Flow (text diagram)
```
FASTA file
  ↓
Parse records → from_fasta
  ↓
[Optional] Triple‑Repeat decode → decode_triple_repeat
  ↓
Primary decode → decode_base4_direct | decode_huffman | decode_gc_balanced
  ↓
[Optional] Parity checking
  ↓
[Optional] Hamming decode → decode_data_with_hamming
  ↓
Output file
```

Both interfaces rely primarily on modules under `genecoder/`:
- `encoders.py` and `gc_constrained_encoder.py`
- `huffman_coding.py`
- `error_detection.py`
- `error_correction.py`
- `hamming_codec.py`
- `formats.py`
- `plotting.py` (GUI metrics)

These modules contain the core logic used by `genecoder.cli` and `src/flet_app.py`.

## Continuous Integration and Merge Queue

Pull requests are merged using GitHub's **merge queue**. When a PR enters the
queue, GitHub creates a temporary merge commit that must pass all required
status checks before the branch is merged. The `python-ci` workflow is the
required check for this repository, so the queued merge commit must succeed in
that workflow to reach the front of the queue. If the checks fail, the PR is
removed from the queue and will need to be re-queued after fixes are pushed.

Contributors do not need to take any manual steps beyond opening the pull
request. The merge queue will handle running `python-ci` automatically and will
merge the branch once all checks pass.

### `changes` Job

The workflow begins with a **`changes`** job that uses
`dorny/paths-filter` to check whether source files were modified. It looks at
`src/`, `tests/`, configuration files, workflow definitions and the `scripts/`
directory. If no files in those paths changed, the heavy test matrix is
skipped.

### `check-comments` Job

The `python-ci` workflow contains a **`check-comments`** job that runs
`scripts/only_comments_changed.py` to detect pull requests that exclusively
touch comments, docstrings or documentation files. When the script outputs
`only_comments=true`, the workflow skips the `lint` and `build` jobs entirely so
the full test matrix does not run. This short‑circuits CI for
documentation‑only updates and significantly reduces build time.

Code style checks are handled in a dedicated **`lint`** job that runs
`pre-commit` with Python 3.11. The `build` matrix depends on this job so
linting only executes once per change.


## Automatic Merging for Comment-Only Changes

A separate workflow (`automerge-comments.yml`) listens to pull request events. It
also runs `scripts/only_comments_changed.py` to verify that the diff only
contains comments, docstrings or documentation files. When `only_comments=true`
is reported, the workflow calls
`peter-evans/enable-pull-request-automerge@v2` to enable auto-merge. As a
result, pull requests containing only documentation or comment updates merge
automatically once the standard checks succeed.

