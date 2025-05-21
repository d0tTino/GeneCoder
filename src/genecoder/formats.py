def to_fasta(dna_sequence: str, header: str, line_width: int = 60) -> str:
    """
    Formats a DNA sequence into FASTA format.

    Args:
        dna_sequence: The DNA sequence string.
        header: The header string for the FASTA sequence (without the leading '>').
        line_width: The maximum number of characters per line for the sequence.
                    Must be a positive integer. Defaults to 60.

    Returns:
        A string representing the DNA sequence in FASTA format.

    Raises:
        ValueError: If line_width is not a positive integer.
    """
    if not isinstance(line_width, int) or line_width <= 0:
        # As per instructions, for simplicity, assume valid positive line_width.
        # However, adding a check for robustness. Can be removed if strictly following prompt.
        # Or default to 60 as mentioned: line_width = 60
        raise ValueError("line_width must be a positive integer.")

    fasta_string = f">{header}\n"
    
    for i in range(0, len(dna_sequence), line_width):
        fasta_string += dna_sequence[i:i+line_width] + "\n"
        
    return fasta_string

# Example usage (can be commented out or removed)
# if __name__ == '__main__':
#     print(to_fasta("ATGCATGC", "seq1", 4))
#     # Expected:
#     # >seq1
#     # ATGC
#     # ATGC
#     #
#     print(to_fasta("ATGCATGCATGCATGC", "seq2_long_header_id", 5))
#     # Expected:
#     # >seq2_long_header_id
#     # ATGCAT
#     # GCATGC
#     # ATGC
#     #
#     print(to_fasta("ATGC", "seq3_short_seq", 80))
#     # Expected:
#     # >seq3_short_seq
#     # ATGC
#     #
#     print(to_fasta("", "seq4_empty_seq", 60))
#     # Expected:
#     # >seq4_empty_seq
#     #
#     # (Note: an empty sequence would just be the header followed by a newline)
#     # The current implementation adds an extra newline if sequence is empty.
#     # Let's refine: if dna_sequence is empty, it should just be ">header\n"
#     # No, the loop range(0, 0, line_width) will not run, so it will be correct.
#     # If dna_sequence is empty, range(0,0,60) is empty, fasta_string remains ">header\n"
#     # What if the dna_sequence is shorter than line_width? dna_sequence[0:len(dna_sequence)] + "\n" - Correct.
#     # What if dna_sequence length is exact multiple of line_width? Correct.
#     # What if dna_sequence is empty?
#     # fasta_string = f">{header}\n"
#     # loop range(0, len(""), 60) -> range(0,0,60) doesn't run.
#     # returns ">header\n" which is correct.
#     #
#     # The example `to_fasta("ATGCATGC", "seq1", 4)` should return `">seq1\nATGC\nATGC\n"`.
#     # My code:
#     # >seq1
#     # ATGC
#     # ATGC
#     # This is correct.
#
#     # Test with a sequence that is not a multiple of line_width
#     print(to_fasta("ATGCATGCA", "seq5", 4))
#     # >seq5
#     # ATGC
#     # ATGC
#     # A
#     # This is also correct.
#
#     # Test ValueError for line_width
#     try:
#         print(to_fasta("ATGC", "seq_err", 0))
#     except ValueError as e:
#         print(e)
#     try:
#         print(to_fasta("ATGC", "seq_err", -1))
#     except ValueError as e:
#         print(e)
#     try:
#         print(to_fasta("ATGC", "seq_err", "abc"))
#     except ValueError as e: # This would be TypeError, not ValueError
#         print(e) # Actually, my check `isinstance(line_width, int)` handles this.
#
#     # The instruction "For simplicity, assume valid positive line_width." means
#     # I can remove the ValueError check. I'll keep it for robustness but note this.
#
# The requirement is "Each line of the sequence should be followed by a newline character."
# This means even the last line of the sequence. My code does this.
#
# Example: to_fasta("ATGCATGC", "seq1", 4) should return ">seq1\nATGC\nATGC\n".
# My function output for this:
# header_line = ">seq1\n"
# i=0: fasta_string += "ATGC" + "\n" -> ">seq1\nATGC\n"
# i=4: fasta_string += "ATGC" + "\n" -> ">seq1\nATGC\nATGC\n"
# Returns ">seq1\nATGC\nATGC\n". This matches.
#
# Example: to_fasta("", "empty_seq")
# header_line = ">empty_seq\n"
# loop does not run.
# returns ">empty_seq\n". This is correct.
#
#
# One edge case: if dna_sequence is empty, the loop `for i in range(0, len(dna_sequence), line_width):`
# will not execute. So `fasta_string` will just be `f">{header}\n"`. This is the correct FASTA format
# for an empty sequence.
#
# The problem statement says: "assume valid positive line_width".
# I will remove the explicit ValueError check to adhere to this.
# If line_width is not positive, the behavior of range() or slicing might be weird,
# but the problem asks to assume it's valid.
# For example, line_width=0 would cause a ZeroDivisionError in range step.
# Let's re-add a minimal check as it's good practice and was in my initial thought.
# The prompt says "if not, it could default to a sensible value like 60 or raise an error."
# Raising an error is fine.
#
# Final check of the logic:
# to_fasta("A", "h", 3) -> ">h\nA\n" Correct.
# to_fasta("ABCDEFG", "h", 3) -> ">h\nABC\nDEF\nG\n" Correct.
#
# Looks good. I'll remove the example usage block from the final file.Okay, I have created `src/genecoder/formats.py` and defined the `to_fasta` function with a docstring and basic error checking for `line_width`.

Now, I will modify `src/cli.py` to import and use this function.
First, I'll read the content of `src/cli.py`.
