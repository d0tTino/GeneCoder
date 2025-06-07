import io
from collections import Counter
import pytest

from genecoder.plotting import (
    prepare_huffman_codeword_length_data,
    generate_codeword_length_histogram,
    prepare_nucleotide_frequency_data,
    generate_nucleotide_frequency_plot,
    calculate_windowed_gc_content,
    identify_homopolymer_regions,
    generate_sequence_analysis_plot,
)


def test_prepare_huffman_data_empty_table():
    assert prepare_huffman_codeword_length_data({}) == Counter()


def test_prepare_huffman_data_simple_table():
    table = {65: "0", 66: "10", 67: "110"}
    expected = Counter({1: 1, 2: 1, 3: 1})
    assert prepare_huffman_codeword_length_data(table) == expected


def test_generate_histogram_empty_data():
    buf = generate_codeword_length_histogram(Counter())
    assert isinstance(buf, io.BytesIO)
    assert len(buf.getvalue()) > 0
    assert buf.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    buf.close()


def test_generate_histogram_simple_data():
    counts = Counter({3: 5, 4: 2})
    buf = generate_codeword_length_histogram(counts)
    assert isinstance(buf, io.BytesIO)
    assert len(buf.getvalue()) > 0
    assert buf.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    buf.close()


def test_prepare_nucleotide_data_empty_sequence():
    expected = Counter({"A": 0, "T": 0, "C": 0, "G": 0})
    assert prepare_nucleotide_frequency_data("") == expected


def test_prepare_nucleotide_data_simple_sequence():
    dna = "AATTCG"
    expected = Counter({"A": 2, "T": 2, "C": 1, "G": 1})
    assert prepare_nucleotide_frequency_data(dna) == expected


def test_prepare_nucleotide_data_with_invalid_chars():
    dna = "AATXTCGY"
    expected = Counter({"A": 2, "T": 2, "C": 1, "G": 1})
    assert prepare_nucleotide_frequency_data(dna) == expected


def test_prepare_nucleotide_data_only_some_nts():
    dna = "AAAA"
    expected = Counter({"A": 4, "T": 0, "C": 0, "G": 0})
    assert prepare_nucleotide_frequency_data(dna) == expected


def test_generate_frequency_plot_empty_data():
    buf = generate_nucleotide_frequency_plot(Counter({"A": 0, "T": 0, "C": 0, "G": 0}))
    assert isinstance(buf, io.BytesIO)
    assert len(buf.getvalue()) > 0
    assert buf.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    buf.close()

    buf_empty_counter = generate_nucleotide_frequency_plot(Counter())
    assert isinstance(buf_empty_counter, io.BytesIO)
    assert len(buf_empty_counter.getvalue()) > 0
    assert buf_empty_counter.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    buf_empty_counter.close()


def test_generate_frequency_plot_simple_data():
    counts = Counter({"A": 10, "T": 5, "C": 5, "G": 10})
    buf = generate_nucleotide_frequency_plot(counts)
    assert isinstance(buf, io.BytesIO)
    assert len(buf.getvalue()) > 0
    assert buf.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    buf.close()


def test_calculate_windowed_gc_empty_sequence():
    starts, gcs = calculate_windowed_gc_content("", window_size=5, step=1)
    assert starts == []
    assert gcs == []


def test_calculate_windowed_gc_sequence_shorter_than_window():
    starts, gcs = calculate_windowed_gc_content("ATGC", window_size=5, step=1)
    assert starts == []
    assert gcs == []


def test_calculate_windowed_gc_invalid_params():
    with pytest.raises(ValueError):
        calculate_windowed_gc_content("ATGC", window_size=0, step=1)
    with pytest.raises(ValueError):
        calculate_windowed_gc_content("ATGC", window_size=5, step=0)
    with pytest.raises(ValueError):
        calculate_windowed_gc_content("ATGC", window_size=-1, step=1)
    with pytest.raises(ValueError):
        calculate_windowed_gc_content("ATGC", window_size=5, step=-1)


def test_calculate_windowed_gc_single_window():
    starts, gcs = calculate_windowed_gc_content("ATGCATGC", window_size=8, step=1)
    assert starts == [0]
    assert gcs == [pytest.approx(0.5)]


def test_calculate_windowed_gc_multiple_windows():
    dna = "AAAAAGGGGGCCCCCTTTTT"
    starts, gcs = calculate_windowed_gc_content(dna, window_size=5, step=5)
    assert starts == [0, 5, 10, 15]
    assert gcs == [pytest.approx(0.0), pytest.approx(1.0), pytest.approx(1.0), pytest.approx(0.0)]


def test_calculate_windowed_gc_skip_bases():
    starts, gcs = calculate_windowed_gc_content("ATGCATGCATGC", window_size=4, step=3)
    assert starts == [0, 3, 6]
    assert gcs == [pytest.approx(0.5), pytest.approx(0.5), pytest.approx(0.5)]

    starts, gcs = calculate_windowed_gc_content("ATGCATGC", window_size=5, step=2)
    assert starts == [0, 2]
    assert gcs == [pytest.approx(0.4), pytest.approx(0.6)]


def test_calculate_windowed_gc_with_non_atcg_chars():
    starts, gcs = calculate_windowed_gc_content("AAANNGGG", window_size=4, step=1)
    assert starts == [0, 1, 2, 3, 4]
    assert gcs == [pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.5), pytest.approx(1.0), pytest.approx(1.0)]


def test_identify_homopolymers_empty_sequence():
    assert identify_homopolymer_regions("", min_len=3) == []


def test_identify_homopolymers_invalid_min_len():
    with pytest.raises(ValueError):
        identify_homopolymer_regions("ATGC", min_len=0)
    with pytest.raises(ValueError):
        identify_homopolymer_regions("ATGC", min_len=1)
    assert identify_homopolymer_regions("AA", min_len=2) is not None


def test_identify_homopolymers_no_regions_found():
    assert identify_homopolymer_regions("AGCTAGCT", min_len=3) == []
    assert identify_homopolymer_regions("AAGGTTCC", min_len=3) == []


def test_identify_homopolymers_single_region():
    assert identify_homopolymer_regions("AAATGCC", min_len=3) == [(0, 2, "A")]
    assert identify_homopolymer_regions("TGCCCATT", min_len=3) == [(2, 4, "C")]


def test_identify_homopolymers_multiple_distinct_regions():
    assert identify_homopolymer_regions("AAATTTTGGCC", min_len=3) == [(0, 2, "A"), (3, 6, "T")]
    assert identify_homopolymer_regions("GGGGGAAACCCC", min_len=3) == [(0, 4, "G"), (5, 7, "A"), (8, 11, "C")]


def test_identify_homopolymers_at_ends_and_middle():
    assert identify_homopolymer_regions("AAAAGCT", min_len=3) == [(0, 3, "A")]
    assert identify_homopolymer_regions("AGTTTTGCT", min_len=3) == [(2, 5, "T")]
    assert identify_homopolymer_regions("AGCTGGGG", min_len=3) == [(4, 7, "G")]
    assert identify_homopolymer_regions("AAAAGCTTTTCGGGGG", min_len=4) == [(0, 3, "A"), (6, 9, "T"), (11, 15, "G")]


def test_identify_homopolymers_adjacent_and_overlapping_like():
    assert identify_homopolymer_regions("AAAAAAPPP", min_len=3) == [(0, 5, "A"), (6, 8, "P")]
    assert identify_homopolymer_regions("AAABBAAA", min_len=3) == [(0, 2, "A"), (5, 7, "A")]


def test_identify_homopolymers_mixed_case():
    assert identify_homopolymer_regions("aaAAAttT", min_len=3) == [(0, 4, "A"), (5, 7, "T")]
    assert identify_homopolymer_regions("aaAAAttT", min_len=2) == [(0, 4, "A"), (5, 7, "T")]


def test_identify_homopolymers_with_non_dna_chars():
    assert identify_homopolymer_regions("AAANNTTTT", min_len=3) == [(0, 2, "A"), (5, 8, "T")]
    assert identify_homopolymer_regions("GGXXAAA", min_len=2) == [(0, 1, "G"), (2, 3, "X"), (4, 6, "A")]
    assert identify_homopolymer_regions("CCC YYYY Z", min_len=3) == [(0, 2, "C"), (4, 7, "Y")]


def test_generate_sequence_analysis_plot_basic():
    gc_data = ([0, 2, 4], [0.5, 0.0, 1.0])
    homos = [(1, 3, "A")]
    buf = generate_sequence_analysis_plot(gc_data, homos, sequence_length=6)
    assert isinstance(buf, io.BytesIO)
    assert buf.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    buf.close()


def test_generate_sequence_analysis_plot_empty():
    buf = generate_sequence_analysis_plot(([], []), [], sequence_length=0)
    assert isinstance(buf, io.BytesIO)
    assert buf.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    buf.close()
