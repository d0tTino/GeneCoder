"""Generates plots and visualizations related to DNA encoding processes.

This module provides functions to prepare data and generate plots, such as
histograms for Huffman codeword lengths, using Matplotlib. The plots are
rendered to in-memory buffers for display in Flet or other GUI frameworks.
"""
import io
import collections
from typing import Dict, List  # For older Python; can be dict, list for 3.9+

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


# --- New functions for sequence analysis plotting ---

def calculate_windowed_gc_content(dna_sequence: str, window_size: int, step: int) -> tuple[list[int], list[float]]:
    """Calculates GC content for each sliding window along a DNA sequence.

    Only 'A', 'T', 'C', 'G' characters are considered for GC calculation
    within each window (for both numerator and effective window length).

    Args:
        dna_sequence: The DNA sequence string.
        window_size: The size of the sliding window.
        step: The step size to move the window.

    Returns:
        A tuple containing two lists:
            - window_starts: A list of 0-based start indices for each window.
            - gc_values: A list of corresponding GC content values (0.0 to 1.0).
                         Returns ([], []) if the sequence is shorter than window_size.

    Raises:
        ValueError: If `window_size` or `step` are not positive integers.
    """
    if not isinstance(window_size, int) or window_size <= 0:
        raise ValueError("window_size must be a positive integer.")
    if not isinstance(step, int) or step <= 0:
        raise ValueError("step must be a positive integer.")

    upper_sequence = dna_sequence.upper()
    seq_len = len(upper_sequence)
    window_starts: list[int] = []
    gc_values: list[float] = []

    if seq_len < window_size:
        return window_starts, gc_values

    for i in range(0, seq_len - window_size + 1, step):
        window = upper_sequence[i:i + window_size]
        
        gc_count = 0
        atcg_count = 0
        for base in window:
            if base == 'G' or base == 'C':
                gc_count += 1
                atcg_count += 1
            elif base == 'A' or base == 'T':
                atcg_count += 1
        
        if atcg_count == 0: # Window contains no ATCG characters
            gc_content = 0.0
        else:
            gc_content = gc_count / atcg_count
            
        window_starts.append(i)
        gc_values.append(gc_content)
        
    return window_starts, gc_values


def identify_homopolymer_regions(dna_sequence: str, min_len: int) -> list[tuple[int, int, str]]:
    """Identifies homopolymer regions of a minimum length in a DNA sequence.

    Args:
        dna_sequence: The DNA sequence string.
        min_len: The minimum length for a homopolymer region to be identified.
                 Must be 2 or greater.

    Returns:
        A list of tuples, where each tuple is (start_index, end_index, base_char).
        `end_index` is the index of the last base in the homopolymer.
        Returns an empty list if no such regions are found or if the sequence is too short.

    Raises:
        ValueError: If `min_len` is less than 2.
    """
    if not isinstance(min_len, int) or min_len < 2:
        raise ValueError("min_len must be an integer greater than or equal to 2.")

    regions: list[tuple[int, int, str]] = []
    seq_len = len(dna_sequence)
    if seq_len < min_len:
        return regions

    upper_sequence = dna_sequence.upper() # Process case-insensitively

    current_streak_char = ''
    current_streak_len = 0
    current_streak_start = -1

    for i, base in enumerate(upper_sequence):
        if base == current_streak_char:
            current_streak_len += 1
        else:
            # End of a streak (or start of sequence)
            if current_streak_len >= min_len:
                regions.append((current_streak_start, i - 1, current_streak_char))
            
            # Start new streak
            current_streak_char = base
            current_streak_len = 1
            current_streak_start = i

    # Check for a homopolymer at the end of the sequence
    if current_streak_len >= min_len:
        regions.append((current_streak_start, seq_len - 1, current_streak_char))
        
    return regions


def generate_sequence_analysis_plot(
    gc_windows_data: tuple[list[int], list[float]], 
    homopolymers: list[tuple[int, int, str]], 
    sequence_length: int
) -> io.BytesIO:
    """Generates a plot showing windowed GC content and homopolymer regions.

    Args:
        gc_windows_data: Tuple from `calculate_windowed_gc_content` 
                         (list of window starts, list of GC values).
        homopolymers: List of tuples from `identify_homopolymer_regions`
                      ((start_index, end_index, base_char)).
        sequence_length: The total length of the DNA sequence.

    Returns:
        io.BytesIO: A BytesIO buffer containing the PNG image data of the plot.
    """
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Plot GC content
    window_starts, gc_values = gc_windows_data
    if window_starts and gc_values:
        ax1.plot(window_starts, gc_values, label='Windowed GC Content', color='b', linestyle='-', marker='.')
        ax1.set_xlabel("Sequence Position (bp)")
        ax1.set_ylabel("GC Content", color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.set_ylim(0, 1.05) # GC content is between 0 and 1
    else:
        ax1.set_xlabel("Sequence Position (bp)")
        ax1.set_ylabel("GC Content", color='b')
        ax1.text(0.5, 0.6, "No GC content data to display.", 
                 horizontalalignment='center', verticalalignment='center', 
                 transform=ax1.transAxes, fontsize=10, color='gray')

    ax1.set_xlim(0, sequence_length)

    # Overlay homopolymer regions
    # We can use a secondary y-axis for visual separation if needed, but for axvspan it's not strictly necessary.
    # For simplicity, we'll plot on the same axis area.
    if homopolymers:
        # Define colors for homopolymers or use a generic one
        homopolymer_colors = {'A': 'lightcoral', 'T': 'lightgreen', 'C': 'lightskyblue', 'G': 'gold'}
        default_color = 'lightgrey'
        
        for start, end, base in homopolymers:
            color = homopolymer_colors.get(base.upper(), default_color)
            ax1.axvspan(start, end + 1, alpha=0.3, color=color, label=f'{base}-Homopolymer' if start == homopolymers[0][0] else None) 
            # The end+1 is because axvspan's xmax is exclusive for the highlighted region in some interpretations,
            # but visually it should cover the 'end' base. Let's test this.
            # Matplotlib axvspan: xmax is exclusive. So end + 1 is correct to include the end base.

        # Create a legend for homopolymers if needed, but it can get crowded.
        # A simpler approach is to just color them. For now, let's skip a complex legend for axvspan.
        # If a legend is desired, one would collect unique labels.
        # handles, labels = plt.gca().get_legend_handles_labels()
        # by_label = dict(zip(labels, handles))
        # plt.legend(by_label.values(), by_label.keys())

    ax1.set_title("Sequence GC Content and Homopolymer Analysis")
    fig.tight_layout() # otherwise the right y-label is slightly clipped

    buf = io.BytesIO()
    try:
        plt.savefig(buf, format='png')
        buf.seek(0)
    finally:
        plt.close(fig)

    return buf
