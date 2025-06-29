# Performance Benchmarks

GeneCoder includes a small benchmark script measuring encoding and decoding throughput.
Run the benchmark from the repository root:

```bash
PYTHONPATH=src python benchmarks/throughput.py
```

Sample output on a GitHub Codespace instance:

```
Base-4     encode: 2.6 MB/s  decode: 1.5 MB/s
Huffman    encode: 1.3 MB/s  decode: 0.6 MB/s
GC-balanced encode: 0.7 MB/s  decode: 1.1 MB/s
```

These numbers were produced using 1&nbsp;MB random inputs and will vary by hardware.
