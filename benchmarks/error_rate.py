import os
import time

from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.error_simulation import introduce_errors

DATA_SIZE = 1_000_000  # 1 MB
SUBSTITUTION_PROB = 0.01  # 1% substitutions


def bit_error_rate(original: bytes, recovered: bytes) -> float:
    """Return the bit error rate between two byte strings."""
    total_bits = len(original) * 8
    min_len = min(len(original), len(recovered))
    errors = 0
    for o, r in zip(original[:min_len], recovered[:min_len]):
        errors += (o ^ r).bit_count()
    if len(recovered) < len(original):
        errors += (len(original) - len(recovered)) * 8
    return errors / total_bits if total_bits else 0.0


def main() -> None:
    data = os.urandom(DATA_SIZE)

    start = time.perf_counter()
    dna = encode_base4_direct(data)
    enc_time = time.perf_counter() - start

    corrupted = introduce_errors(dna, substitution_prob=SUBSTITUTION_PROB)

    start = time.perf_counter()
    decoded, _ = decode_base4_direct(corrupted)
    dec_time = time.perf_counter() - start

    ber = bit_error_rate(data, decoded)

    enc_rate = DATA_SIZE / (1024 * 1024) / enc_time
    dec_rate = DATA_SIZE / (1024 * 1024) / dec_time
    print(
        f"encode: {enc_rate:.2f} MB/s  decode: {dec_rate:.2f} MB/s  BER: {ber:.6f}"
    )


if __name__ == "__main__":
    main()
