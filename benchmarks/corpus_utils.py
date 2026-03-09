from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
CORPUS_PAYLOAD_PATH = CORPUS_DIR / "base_payload.txt"
PROFILE_MATRIX_PATH = CORPUS_DIR / "profiles.json"


def load_profile_matrix() -> dict[str, Any]:
    return json.loads(PROFILE_MATRIX_PATH.read_text(encoding="utf-8"))


def load_frozen_bytes(target_size: int) -> bytes:
    payload = CORPUS_PAYLOAD_PATH.read_bytes()
    if target_size <= len(payload):
        return payload[:target_size]
    repeats = (target_size // len(payload)) + 1
    return (payload * repeats)[:target_size]


def corpus_sha256() -> str:
    return hashlib.sha256(CORPUS_PAYLOAD_PATH.read_bytes()).hexdigest()


def substitute_dna_bases(sequence: str, probability: float, seed: int) -> str:
    if probability <= 0:
        return sequence
    rng = random.Random(seed)
    alphabet = ("A", "C", "G", "T")
    out: list[str] = []
    for base in sequence:
        if rng.random() < probability and base in alphabet:
            replacements = [candidate for candidate in alphabet if candidate != base]
            out.append(replacements[rng.randrange(len(replacements))])
        else:
            out.append(base)
    return "".join(out)
