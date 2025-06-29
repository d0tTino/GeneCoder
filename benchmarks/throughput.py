import os
import time
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.huffman_coding import encode_huffman, decode_huffman
from genecoder.gc_constrained_encoder import encode_gc_balanced, decode_gc_balanced

DATA_SIZE = 1_000_000  # 1 MB


def _bench_base4() -> tuple[float, float]:
    data = os.urandom(DATA_SIZE)
    start = time.perf_counter()
    dna = encode_base4_direct(data)
    enc = time.perf_counter() - start
    start = time.perf_counter()
    decode_base4_direct(dna)
    dec = time.perf_counter() - start
    return enc, dec


def _bench_huffman() -> tuple[float, float]:
    data = os.urandom(DATA_SIZE)
    start = time.perf_counter()
    dna, table, padding = encode_huffman(data)
    enc = time.perf_counter() - start
    start = time.perf_counter()
    decode_huffman(dna, table, padding)
    dec = time.perf_counter() - start
    return enc, dec


def _bench_gc() -> tuple[float, float]:
    data = os.urandom(DATA_SIZE)
    start = time.perf_counter()
    dna = encode_gc_balanced(data, 0.45, 0.55, 3)
    enc = time.perf_counter() - start
    start = time.perf_counter()
    decode_gc_balanced(dna)
    dec = time.perf_counter() - start
    return enc, dec


def main() -> None:
    benches = {
        "Base-4": _bench_base4(),
        "Huffman": _bench_huffman(),
        "GC-balanced": _bench_gc(),
    }
    for name, (enc, dec) in benches.items():
        enc_rate = DATA_SIZE / (1024 * 1024) / enc
        dec_rate = DATA_SIZE / (1024 * 1024) / dec
        print(f"{name:10} encode: {enc_rate:.2f} MB/s  decode: {dec_rate:.2f} MB/s")


if __name__ == "__main__":
    main()
