import argparse
from pathlib import Path

from genecoder.cli.encode import process_single_encode
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.formats import from_fasta


def _encode_args(stream: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
        alphabet="base4",
        stream=stream,
        chunk_size=1024,
        resume=False,
        key=None,
        encrypt=False,
        checksum=False,
        file_type=None,
        mirror=False,
        capsule=None,
        export_csv=None,
    )


def test_process_single_encode_windows_path(tmp_path: Path) -> None:
    input_file = tmp_path / "C:\\data\\file.txt"
    input_file.write_text("hi")
    output_file = tmp_path / "out.fasta"
    process_single_encode(str(input_file), str(output_file), _encode_args())

    records = from_fasta(output_file.read_text())
    header = records[0][0]
    assert "input_file=file.txt" in header
    assert "\\" not in header


def test_process_single_encode_windows_path_stream(tmp_path: Path) -> None:
    input_file = tmp_path / "C:\\path\\seq.bin"
    input_file.write_text("data")
    output_file = tmp_path / "out_stream.fasta"
    process_single_encode(str(input_file), str(output_file), _encode_args(stream=True))

    records = from_fasta(output_file.read_text())
    header = records[0][0]
    assert "input_file=seq.bin" in header
    assert "\\" not in header
