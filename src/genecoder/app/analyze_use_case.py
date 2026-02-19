from __future__ import annotations

from dataclasses import dataclass

from genecoder.constraint_fixer import fix_sequence
from genecoder.encoders import calculate_gc_content
from genecoder.formats import from_fasta
from genecoder.plotting import calculate_windowed_gc_content
from genecoder.synthesis import SynthesisConstraints
from genecoder.utils import get_max_homopolymer_length


@dataclass(frozen=True)
class AnalyzeRequest:
    fasta_data: str
    window_size: int = 50
    step: int = 10


@dataclass(frozen=True)
class AnalyzeResponse:
    header: str
    sequence: str
    length: int
    gc_content: float
    max_homopolymer: int
    min_window_gc: float
    max_window_gc: float
    avg_window_gc: float
    suggested_fix: str | None = None


class AnalyzeUseCase:
    def execute(self, request: AnalyzeRequest) -> AnalyzeResponse:
        parsed = from_fasta(request.fasta_data)
        if not parsed:
            raise ValueError("No valid FASTA records found")
        header, sequence = parsed[0]
        gc_content = calculate_gc_content(sequence)
        max_hp = get_max_homopolymer_length(sequence)
        _, gc_values = calculate_windowed_gc_content(sequence, request.window_size, request.step)
        avg_gc = sum(gc_values) / len(gc_values) if gc_values else 0.0

        suggested_fix: str | None = None
        constraints = SynthesisConstraints()
        if gc_content < 0.4 or gc_content > 0.6 or max_hp > constraints.max_homopolymer:
            suggested_fix = fix_sequence(
                sequence,
                target_gc_min=0.4,
                target_gc_max=0.6,
                max_homopolymer=constraints.max_homopolymer,
            )

        return AnalyzeResponse(
            header=header,
            sequence=sequence,
            length=len(sequence),
            gc_content=gc_content,
            max_homopolymer=max_hp,
            min_window_gc=min(gc_values) if gc_values else 0.0,
            max_window_gc=max(gc_values) if gc_values else 0.0,
            avg_window_gc=avg_gc,
            suggested_fix=suggested_fix,
        )
