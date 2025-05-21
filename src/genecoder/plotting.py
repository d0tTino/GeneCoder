"""Generates plots and visualizations related to DNA encoding processes.

This module provides functions to prepare data and generate plots, such as
histograms for Huffman codeword lengths, using Matplotlib. The plots are
rendered to in-memory buffers for display in Flet or other GUI frameworks.
"""
import io
import collections
from typing import Dict, List, Tuple # For older Python; can be dict, list, tuple for 3.9+

import matplotlib
matplotlib.use('Agg') # Set Matplotlib backend to Agg for headless environments
import matplotlib.pyplot as plt


def prepare_huffman_codeword_length_data(huffman_table: Dict[int, str]) -> collections.Counter:
    """Prepares data for a Huffman codeword length histogram.

    Calculates the length of each codeword in the provided Huffman table and
    counts the occurrences of each distinct length.

    Args:
        huffman_table (Dict[int, str]): A dictionary mapping byte values (int)
            to their Huffman codes (binary strings).

    Returns:
        collections.Counter: A Counter object where keys are codeword lengths (int)
        and values are the number of codewords (frequency) of that length.
        Returns an empty Counter if the input table is empty.
    """
    if not huffman_table:
        return collections.Counter()

    codeword_lengths: List[int] = [len(code) for code in huffman_table.values()]
    length_counts = collections.Counter(codeword_lengths)
    return length_counts


def generate_codeword_length_histogram(length_counts: collections.Counter) -> io.BytesIO:
    """Generates a histogram of Huffman codeword lengths as a PNG image in a BytesIO buffer.

    Args:
        length_counts (collections.Counter): A Counter object where keys are
            codeword lengths (int) and values are their frequencies.

    Returns:
        io.BytesIO: A BytesIO buffer containing the PNG image data of the
        generated histogram. If `length_counts` is empty, it returns a
        BytesIO buffer containing a plot with a "No data to display" message.
    """
    fig, ax = plt.subplots(figsize=(8, 6)) # Adjust figsize as needed

    if not length_counts:
        ax.text(0.5, 0.5, "No data to display for histogram.", 
                horizontalalignment='center', verticalalignment='center', 
                transform=ax.transAxes, fontsize=12, color='gray')
        ax.set_xlabel("Codeword Length (bits)")
        ax.set_ylabel("Frequency (Number of Codewords)")
        ax.set_title("Huffman Codeword Length Distribution")
    else:
        sorted_lengths = sorted(length_counts.keys())
        counts = [length_counts[length] for length in sorted_lengths]

        ax.bar(sorted_lengths, counts, width=0.8, align='center', color='skyblue')
        ax.set_xlabel("Codeword Length (bits)")
        ax.set_ylabel("Frequency (Number of Codewords)")
        ax.set_title("Huffman Codeword Length Distribution")
        
        # Set x-ticks: if there are many unique lengths, this might become crowded.
        # A common strategy is to show all if less than a threshold, or a subset otherwise.
        if len(sorted_lengths) <= 20: # Threshold for showing all ticks
            ax.set_xticks(sorted_lengths)
        else:
            # For many lengths, matplotlib's default ticker might be better,
            # or a custom ticker can be implemented (e.g., MaxNLocator).
            # For now, let default behavior handle it if too many.
            pass 
        
        # Ensure y-axis ticks are integers if counts are always integers
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))


    plt.tight_layout()  # Adjust layout to prevent labels from being cut off

    buf = io.BytesIO()
    try:
        plt.savefig(buf, format='png')
        buf.seek(0) # Rewind the buffer to the beginning
    finally:
        plt.close(fig) # Close the figure to free up memory

    return buf


def prepare_nucleotide_frequency_data(dna_sequence: str) -> collections.Counter:
    """Prepares data for a nucleotide frequency plot.

    Counts occurrences of 'A', 'T', 'C', 'G' in the DNA sequence.
    Other characters are ignored. Ensures all four standard nucleotides
    are present in the output Counter, with a count of 0 if not found.

    Args:
        dna_sequence (str): The DNA sequence string.

    Returns:
        collections.Counter: A Counter mapping each nucleotide ('A', 'T', 'C', 'G')
        to its frequency.
    """
    # Initialize with all standard nucleotides to ensure they are in the output
    nucleotide_counts = collections.Counter({'A': 0, 'T': 0, 'C': 0, 'G': 0})
    
    # Count only the valid nucleotides from the sequence
    valid_nucleotide_counts = collections.Counter(
        nt for nt in dna_sequence if nt in {'A', 'T', 'C', 'G'}
    )
    nucleotide_counts.update(valid_nucleotide_counts) # Add counts from sequence
    
    return nucleotide_counts


def generate_nucleotide_frequency_plot(nucleotide_counts: collections.Counter) -> io.BytesIO:
    """Generates a bar plot of nucleotide frequencies as a PNG image in a BytesIO buffer.

    Args:
        nucleotide_counts (collections.Counter): A Counter mapping nucleotides
            ('A', 'T', 'C', 'G') to their frequencies.

    Returns:
        io.BytesIO: A BytesIO buffer containing the PNG image data of the
        generated bar plot. If all counts are zero, it returns a plot
        with a "No nucleotide data to display." message.
    """
    fig, ax = plt.subplots(figsize=(6, 5)) # Adjust figsize as needed

    nucleotides_for_plot = ['A', 'T', 'C', 'G']
    counts = [nucleotide_counts.get(nt, 0) for nt in nucleotides_for_plot]

    if all(c == 0 for c in counts) and not any(nucleotide_counts.values()): # Check if effectively empty
        ax.text(0.5, 0.5, "No nucleotide data to display.", 
                horizontalalignment='center', verticalalignment='center', 
                transform=ax.transAxes, fontsize=12, color='gray')
    else:
        ax.bar(nucleotides_for_plot, counts, color=['cornflowerblue', 'lightgreen', 'sandybrown', 'lightcoral'])
    
    ax.set_xlabel("Nucleotide")
    ax.set_ylabel("Frequency (Count)")
    ax.set_title("Nucleotide Frequency Distribution")
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True)) # Ensure y-axis has integer ticks

    plt.tight_layout()

    buf = io.BytesIO()
    try:
        plt.savefig(buf, format='png')
        buf.seek(0)
    finally:
        plt.close(fig)

    return buf
