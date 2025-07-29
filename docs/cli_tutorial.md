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

## Simulating channel errors

The `pipeline` command can apply a sequencing simulator between encoding and
decoding. Pass per-channel rates directly on the command line:

```bash
genecli pipeline input.bin output.bin --codec base4_direct --channel indel \
    --sub-rate 0.1 --ins-rate 0.02 --del-rate 0.05
```

The same parameters work with the `channel` command when applying simulators to
FASTA sequences:

```bash
genecli channel apply --input-file seq.fasta --output-file corrupted.fasta \
    --simulator indel --sub-rate 0.1 --ins-rate 0.02 --del-rate 0.05 --min-length 1
```
