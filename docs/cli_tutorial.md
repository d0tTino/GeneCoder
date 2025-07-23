# CLI Tutorial

This tutorial walks through basic command-line usage of GeneCoder.

## Encoding a file

```bash
pip install genecoder[cli]

genecli encode --input-files example.txt --output-file example.fasta --method base4_direct
```

## Decoding a file

```bash
genecli decode --input-files example.fasta --output-file decoded.txt --method base4_direct
```

See `genecli --help` for all available options.

## Running a bundle

Bundle YAML files describe an encode/decode workflow. A simple example:

```yaml
encode:
  input_files: [message.txt]
  method: base4_direct
decode:
  method: base4_direct
```

Execute the bundle:

```bash
genecli bundle run bundle.yaml --cache-dir runs/
```

Results are written to `runs/<hash>/<timestamp>/` and skipped when the same
configuration is executed again.
