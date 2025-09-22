"""Helpers for working with FASTA records and :class:`SequenceBatch` objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Mapping, MutableMapping, Sequence, Tuple
import logging


logger = logging.getLogger(__name__)

# The set of valid characters for FASTA sequence lines.
# Valid characters are the uppercase ASCII letters ``A``-``Z``, the digits
# ``0``-``9``, the gap characters ``-`` and ``*``, and the slash ``/``.
# Lowercase characters are considered invalid and will trigger a ``ValueError``.
FASTA_ALLOWED_CHARS: set[str] = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-*/")


@dataclass(slots=True)
class FastaRecord:
    """Represents a single FASTA record."""

    header: str
    sequence: str

    def as_tuple(self) -> tuple[str, str]:
        """Return ``(header, sequence)`` for compatibility with legacy helpers."""

        return self.header, self.sequence


@dataclass(slots=True)
class SequenceOligo:
    """A single oligo entry within a :class:`SequenceBatch`."""

    sequence: str
    header: str
    index: int
    oligo_id: str
    metadata: dict[str, str] = field(default_factory=dict)
    seed: int | None = None

    def to_record(self) -> FastaRecord:
        """Return the oligo as a :class:`FastaRecord`."""

        return FastaRecord(header=self.header, sequence=self.sequence)


@dataclass
class SequenceBatch:
    """A batch of related oligos accompanied by shared metadata."""

    batch_id: str
    metadata: dict[str, str] = field(default_factory=dict)
    seed: int | None = None
    oligos: list[SequenceOligo] = field(default_factory=list)
    legacy: bool = False

    def __post_init__(self) -> None:
        self.oligos.sort(key=lambda ol: ol.index)

    def add_oligo(self, oligo: SequenceOligo) -> None:
        """Append ``oligo`` and keep records ordered."""

        self.oligos.append(oligo)
        self.oligos.sort(key=lambda item: item.index)

    @property
    def total_length(self) -> int:
        """Return the total number of nucleotides across all oligos."""

        return sum(len(ol.sequence) for ol in self.oligos)

    def records(self) -> list[FastaRecord]:
        """Return the batch as a list of :class:`FastaRecord` objects."""

        return [ol.to_record() for ol in self.oligos]

    def to_fasta(self, line_width: int = 60) -> str:
        """Serialise the batch into FASTA text."""

        return format_fasta_records(self.records(), line_width=line_width)

    def combined_sequence(self) -> str:
        """Concatenate the sequences for all oligos in order."""

        return "".join(ol.sequence for ol in self.oligos)

    def primary_oligos(self) -> list[SequenceOligo]:
        """Return oligos that are not marked as mirrors."""

        return [
            ol for ol in self.oligos if ol.metadata.get("mirror", "").lower() != "rc"
        ]

    def primary_sequence(self) -> str:
        """Concatenate only the primary oligo sequences."""

        return "".join(ol.sequence for ol in self.primary_oligos())

    def first_header(self) -> str:
        """Return the header for the first primary oligo, if present."""

        primaries = self.primary_oligos()
        return primaries[0].header if primaries else (self.oligos[0].header if self.oligos else "")

    @classmethod
    def build(
        cls,
        records: Sequence[FastaRecord | tuple[str, str]],
        *,
        batch_id: str | None = None,
        batch_seed: int | None = None,
        max_oligo_length: int | None = None,
    ) -> "SequenceBatch":
        """Construct a batch from ``records``.

        The ``records`` iterable may contain :class:`FastaRecord` instances or
        ``(header, sequence)`` tuples. Each record can optionally be split into
        multiple oligos by providing ``max_oligo_length``. Metadata is preserved
        and augmented with ``batch_id``, ``batch_size`` and per-oligo identifiers.
        """

        items = [r if isinstance(r, FastaRecord) else FastaRecord(*r) for r in records]
        if not items:
            raise ValueError("records cannot be empty")

        base_meta = _metadata_from_header(items[0].header)
        derived_id = _sanitize_header_value(
            batch_id or base_meta.get("batch_id") or base_meta.get("input_file") or "batch"
        )
        batch = cls(batch_id=derived_id, metadata=dict(base_meta), seed=batch_seed)

        index = 0
        for record in items:
            rec_meta = _metadata_from_header(record.header)
            sequences = list(_split_sequence(record.sequence, max_oligo_length))
            if not sequences:
                sequences = [""]
            for chunk in sequences:
                index += 1
                metadata = dict(rec_meta)
                metadata["batch_id"] = derived_id
                metadata["oligo_index"] = str(index)
                metadata.setdefault("oligo_id", f"{derived_id}-{index:04d}")
                if batch_seed is not None:
                    metadata["batch_seed"] = str(batch_seed)
                    metadata.setdefault("oligo_seed", str(batch_seed + index - 1))
                header = _update_header_tokens(record.header, metadata)
                oligo_seed = metadata.get("oligo_seed")
                try:
                    oligo_seed_int = int(oligo_seed) if oligo_seed is not None else None
                except ValueError:
                    oligo_seed_int = None
                batch.add_oligo(
                    SequenceOligo(
                        sequence=chunk,
                        header=header,
                        index=index,
                        oligo_id=metadata["oligo_id"],
                        metadata=metadata,
                        seed=oligo_seed_int,
                    )
                )

        total = len(batch.oligos)
        batch.metadata["batch_id"] = derived_id
        batch.metadata["batch_size"] = str(total)
        if batch_seed is not None:
            batch.metadata["batch_seed"] = str(batch_seed)

        for oligo in batch.oligos:
            oligo.metadata["batch_size"] = str(total)
            oligo.header = _update_header_tokens(
                oligo.header,
                {"batch_size": str(total), "batch_id": derived_id}
                | ({"batch_seed": str(batch_seed)} if batch_seed is not None else {}),
            )

        return batch

    @classmethod
    def from_fasta(cls, fasta_content: str) -> "SequenceBatch":
        """Parse ``fasta_content`` into a :class:`SequenceBatch`.

        Legacy single-record FASTA files (without batch metadata) are wrapped into
        a batch with a deprecation warning.
        """

        records = parse_fasta_records(fasta_content)
        if not records:
            return cls(batch_id="", metadata={}, seed=None, oligos=[], legacy=False)

        first_meta = _metadata_from_header(records[0].header)
        has_batch = "batch_id" in first_meta and (
            "oligo_index" in first_meta or "oligo_id" in first_meta
        )

        if len(records) == 1 and not has_batch:
            logger.warning(
                "Legacy FASTA without SequenceBatch metadata detected; treating as a single-oligo batch."
            )
            batch_id = _sanitize_header_value(
                first_meta.get("input_file") or first_meta.get("name") or "legacy"
            )
            batch = cls.build(records, batch_id=batch_id)
            batch.legacy = True
            return batch

        batch_id = _sanitize_header_value(first_meta.get("batch_id") or "batch")
        batch_seed = first_meta.get("batch_seed")
        try:
            seed_int = int(batch_seed) if batch_seed is not None else None
        except ValueError:
            seed_int = None

        oligos: list[SequenceOligo] = []
        for idx, record in enumerate(records, start=1):
            meta = _metadata_from_header(record.header)
            index_str = meta.get("oligo_index") or meta.get("oligo_id")
            try:
                index = int(index_str) if index_str is not None else idx
            except ValueError:
                index = idx
            oligo_seed = meta.get("oligo_seed")
            try:
                seed_val = int(oligo_seed) if oligo_seed is not None else None
            except ValueError:
                seed_val = None
            oligo_id = meta.get("oligo_id") or f"{batch_id}-{index:04d}"
            oligos.append(
                SequenceOligo(
                    sequence=record.sequence,
                    header=record.header,
                    index=index,
                    oligo_id=oligo_id,
                    metadata=meta,
                    seed=seed_val,
                )
            )

        batch_meta = dict(first_meta)
        batch_meta["batch_id"] = batch_id
        batch_meta.setdefault("batch_size", str(len(oligos)))
        if seed_int is not None:
            batch_meta["batch_seed"] = str(seed_int)

        return cls(
            batch_id=batch_id,
            metadata=batch_meta,
            seed=seed_int,
            oligos=sorted(oligos, key=lambda ol: ol.index),
            legacy=False,
        )


def _split_sequence(sequence: str, max_length: int | None) -> Iterator[str]:
    """Yield ``sequence`` chunks of at most ``max_length`` nucleotides."""

    if max_length is None or max_length <= 0:
        yield sequence
        return
    for start in range(0, len(sequence), max_length):
        yield sequence[start : start + max_length]


def _sanitize_header_value(value: object) -> str:
    """Return ``value`` as a header-safe string without whitespace."""

    text = str(value).strip()
    if not text:
        return "0"
    for bad in "\r\n\t>":
        text = text.replace(bad, "_")
    return "_".join(part for part in text.split()) or "0"


def _tokenize_header(header: str) -> tuple[list[str], MutableMapping[str, int]]:
    tokens = header.strip().split()
    positions: MutableMapping[str, int] = {}
    for idx, token in enumerate(tokens):
        if "=" in token:
            key, _ = token.split("=", 1)
            positions[key] = idx
    return tokens, positions


def _update_header_tokens(header: str, updates: Mapping[str, object]) -> str:
    tokens, positions = _tokenize_header(header)
    for key, value in updates.items():
        if value is None:
            continue
        sanitized = _sanitize_header_value(value)
        token = f"{key}={sanitized}"
        if key in positions:
            tokens[positions[key]] = token
        else:
            positions[key] = len(tokens)
            tokens.append(token)
    return " ".join(tokens)


def _metadata_from_header(header: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for token in header.strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            metadata[key] = value
    return metadata

def to_fasta(dna_sequence: str, header: str, line_width: int = 60) -> str:
    """Formats a DNA sequence into a FASTA formatted string.

    Args:
        dna_sequence (str): The DNA sequence string (e.g., "ATGC...").
        header (str): The header string for the FASTA sequence, which will be
            prefixed with ">". Do not include ">" in this argument.
        line_width (int): The maximum number of characters per line for the
            sequence data. Defaults to 60. Must be a positive integer.
        
        The header is stripped of surrounding whitespace and validated to not
        contain newlines or the ``">"`` character. Non-printable characters are
        rejected.

    Returns:
        str: A string representing the DNA sequence in FASTA format.
             Each line of the sequence, including the last, is followed by a
             newline character. An empty sequence results in only the header
             line followed by a newline.

    Raises:
        ValueError: If ``line_width`` is not a positive integer or the header
        contains unsafe characters.
    """
    if not isinstance(line_width, int) or line_width <= 0:
        raise ValueError("line_width must be a positive integer.")

    sanitized_header = header.strip()
    if not sanitized_header or ">" in sanitized_header or any(c in sanitized_header for c in "\n\r"):
        raise ValueError("Invalid FASTA header")
    if not sanitized_header.isprintable():
        raise ValueError("Invalid FASTA header")

    fasta_string = f">{sanitized_header}\n"
    
    if not dna_sequence: # Handle empty sequence explicitly for clarity
        return fasta_string

    for i in range(0, len(dna_sequence), line_width):
        fasta_string += dna_sequence[i:i+line_width] + "\n"
        
    return fasta_string


def format_fasta_records(records: Sequence[FastaRecord], line_width: int = 60) -> str:
    """Return FASTA text for ``records``."""

    return "".join(
        to_fasta(record.sequence, record.header, line_width=line_width)
        for record in records
    )


def parse_fasta_records(fasta_content: str) -> List[FastaRecord]:
    """Parse ``fasta_content`` and return :class:`FastaRecord` objects.

    This function mirrors :func:`from_fasta` but preserves the headers exactly as
    they appear in the file.
    """

    records: List[FastaRecord] = []
    current_header: str | None = None
    current_sequence_parts: List[str] = []

    lines = fasta_content.splitlines()

    for line_number, line_text in enumerate(lines, start=1):
        stripped_line = line_text.strip()
        if not stripped_line:
            continue

        if stripped_line.startswith(">"):
            if current_header is not None:
                records.append(FastaRecord(current_header, "".join(current_sequence_parts)))
            current_header = stripped_line[1:].strip()
            current_sequence_parts = []
        elif current_header is not None:
            processed_sequence_line = "".join(stripped_line.split())
            if (
                any(ch.islower() for ch in processed_sequence_line)
                or not set(processed_sequence_line).issubset(FASTA_ALLOWED_CHARS)
            ):
                raise ValueError(f"Invalid characters on line {line_number}.")
            current_sequence_parts.append(processed_sequence_line)

    if current_header is not None:
        records.append(FastaRecord(current_header, "".join(current_sequence_parts)))

    return records


def from_fasta(fasta_content: str) -> List[Tuple[str, str]]:
    """Parse ``fasta_content`` and return ``(header, sequence)`` tuples."""

    return [record.as_tuple() for record in parse_fasta_records(fasta_content)]


def to_fastq(
    dna_sequence: str,
    header: str,
    qualities: Sequence[int] | str,
) -> str:
    """Formats a DNA sequence and qualities into FASTQ format."""
    sanitized_header = header.strip()
    if not sanitized_header or "@" in sanitized_header or any(c in sanitized_header for c in "\n\r"):
        raise ValueError("Invalid FASTQ header")
    if not sanitized_header.isprintable():
        raise ValueError("Invalid FASTQ header")

    if isinstance(qualities, str):
        qual_str = qualities
    else:
        if len(qualities) != len(dna_sequence):
            raise ValueError("Quality scores length must match sequence length")
        qual_str = "".join(chr(q + 33) for q in qualities)

    if len(qual_str) != len(dna_sequence):
        raise ValueError("Quality string length must match sequence length")

    return f"@{sanitized_header}\n{dna_sequence}\n+\n{qual_str}\n"


def from_fastq(fastq_content: str) -> List[Tuple[str, str, str]]:
    """Parses content in FASTQ format and extracts sequence records."""
    records: List[Tuple[str, str, str]] = []
    lines = [ln.strip() for ln in fastq_content.splitlines() if ln.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("@"):  # Skip non-record lines before first header
            i += 1
            continue
        if i + 3 >= len(lines):
            break
        header = line[1:].strip()
        seq = lines[i + 1].strip()
        plus = lines[i + 2].strip()
        qual = lines[i + 3].strip()
        if not plus.startswith("+"):
            raise ValueError("Invalid FASTQ record: missing '+' line")
        if len(seq) != len(qual):
            raise ValueError("Quality string length does not match sequence length")
        if any(ch.islower() for ch in seq) or not set(seq).issubset(FASTA_ALLOWED_CHARS):
            raise ValueError("Invalid characters in FASTQ sequence line")
        records.append((header, seq, qual))
        i += 4

    return records
