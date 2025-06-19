"""Utilities for storing encoded DNA sequences in capsule files.

A capsule is a JSON document capturing the FASTA header, the sequence and
metadata describing the encoding process.  It allows GeneCoder to quickly
replay or inspect previous encodings.

The JSON structure follows this specification::

    {
        "version": 1,
        "header": "<fasta header>",
        "sequence": "<dna sequence>",
        "metadata": { ... },
        "created": "<ISO timestamp>"
    }
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
from typing import Any, Dict


@dataclass
class Capsule:
    """Represents the contents of a capsule."""

    header: str
    sequence: str
    metadata: Dict[str, Any]
    created: str
    version: int = 1


__all__ = ["Capsule", "write_capsule", "read_capsule"]


def write_capsule(sequence: str, header: str, metadata: Dict[str, Any], path: str) -> None:
    """Write ``sequence`` and ``metadata`` to ``path`` as a capsule."""
    capsule = Capsule(
        header=header,
        sequence=sequence,
        metadata=metadata,
        created=datetime.utcnow().isoformat(),
    )
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(capsule), f, indent=2)


def read_capsule(path: str) -> Capsule:
    """Load a capsule from ``path``."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid capsule file: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read capsule file: {path}") from exc
    return Capsule(**data)
