# CLI Tutorial

This tutorial walks through basic command-line usage of GeneCoder.

## Encoding a file

```bash
pip install genecoder[cli]

genecoder encode --input-files example.txt --output-file example.fasta --method base4_direct
```

## Decoding a file

```bash
genecoder decode --input-files example.fasta --output-file decoded.txt --method base4_direct
```

See `genecoder --help` for all available options.
