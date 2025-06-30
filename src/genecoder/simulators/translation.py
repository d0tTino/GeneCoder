"""mRNA translation simulator stub."""
from __future__ import annotations

from typing import Callable, Sequence

from .base import BaseSimulator
from ..random_utils import make_rng
from ..error_simulation import introduce_errors
from ..channels.base import BaseChannel

__all__ = ["TranslationSimulator", "register"]


class TranslationSimulator(BaseSimulator):
    """Simplified translation model converting RNA to amino acids."""

    CODON_TABLE: dict[str, str] = {
        # Phenylalanine
        "UUU": "F",
        "UUC": "F",
        # Leucine
        "UUA": "L",
        "UUG": "L",
        "CUU": "L",
        "CUC": "L",
        "CUA": "L",
        "CUG": "L",
        # Isoleucine / Methionine
        "AUU": "I",
        "AUC": "I",
        "AUA": "I",
        "AUG": "M",
        # Valine
        "GUU": "V",
        "GUC": "V",
        "GUA": "V",
        "GUG": "V",
        # Serine
        "UCU": "S",
        "UCC": "S",
        "UCA": "S",
        "UCG": "S",
        "AGU": "S",
        "AGC": "S",
        # Proline
        "CCU": "P",
        "CCC": "P",
        "CCA": "P",
        "CCG": "P",
        # Threonine
        "ACU": "T",
        "ACC": "T",
        "ACA": "T",
        "ACG": "T",
        # Alanine
        "GCU": "A",
        "GCC": "A",
        "GCA": "A",
        "GCG": "A",
        # Tyrosine
        "UAU": "Y",
        "UAC": "Y",
        # Histidine
        "CAU": "H",
        "CAC": "H",
        # Glutamine
        "CAA": "Q",
        "CAG": "Q",
        # Asparagine
        "AAU": "N",
        "AAC": "N",
        # Lysine
        "AAA": "K",
        "AAG": "K",
        # Aspartic Acid
        "GAU": "D",
        "GAC": "D",
        # Glutamic Acid
        "GAA": "E",
        "GAG": "E",
        # Cysteine
        "UGU": "C",
        "UGC": "C",
        # Tryptophan
        "UGG": "W",
        # Arginine
        "CGU": "R",
        "CGC": "R",
        "CGA": "R",
        "CGG": "R",
        "AGA": "R",
        "AGG": "R",
        # Glycine
        "GGU": "G",
        "GGC": "G",
        "GGA": "G",
        "GGG": "G",
        # Stop codons
        "UAA": "*",
        "UAG": "*",
        "UGA": "*",
    }

    def __init__(
        self,
        substitution_rate: float = 1e-4,
        insertion_rate: float = 1e-5,
        deletion_rate: float = 1e-5,
        coverage: int = 1,
        quality_profile: Sequence[float] | None = None,
    ) -> None:
        super().__init__(
            substitution_rate=substitution_rate,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            coverage=coverage,
            read_length=0,
            quality_profile=quality_profile,
        )

    def simulate(self, sequence: str) -> str:
        """Return the translated peptide from ``sequence``."""
        dna = sequence.replace("U", "T")
        rng = make_rng()
        mutated = introduce_errors(
            dna,
            substitution_prob=self.substitution_rate,
            insertion_prob=self.insertion_rate,
            deletion_prob=self.deletion_rate,
            rng=rng,
        )
        rna = mutated.replace("T", "U")
        peptide: list[str] = []
        for i in range(0, len(rna) - 2, 3):
            codon = rna[i : i + 3]
            if len(codon) < 3:
                break
            aa = self.CODON_TABLE.get(codon)
            if not aa:
                continue
            if aa == "*":
                break
            peptide.append(aa)
        return "".join(peptide)


def register(register_simulator: Callable[[str, BaseChannel], None]) -> None:
    register_simulator("translation", TranslationSimulator())
