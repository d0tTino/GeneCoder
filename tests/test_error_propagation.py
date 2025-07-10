import argparse
from pathlib import Path
import pytest

from genecoder.cli.analyze import process_single_analyze
from genecoder.cli.decode import process_single_decode
from genecoder.cli.channel import process_channel
from genecoder.formats import to_fasta


def _decode_args() -> argparse.Namespace:
    return argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule="gc_even_a_odd_t",
        alphabet="base4",
        stream=False,
        simulate_errors=0.0,
        simulator="none",
    )


def _analyze_args() -> argparse.Namespace:
    return argparse.Namespace(
        window_size=4,
        step=2,
        min_homopolymer=3,
        plot_dir=None,
    )


def _sim_args(input_file: Path, output_file: Path) -> argparse.Namespace:
    return argparse.Namespace(
        input_file=str(input_file),
        output_file=str(output_file),
        simulators=[],
        constraints={"min_length": 1, "max_length": 1000, "max_homopolymer": 4},
        sub_prob=0.1,
        ins_prob=0.0,
        del_prob=0.0,
        seed=None,
        parallel=False,
        threads=None,
        processes=None,
    )


def test_process_single_decode_unexpected_error(monkeypatch, tmp_path: Path) -> None:
    fasta_file = tmp_path / "x.fasta"
    fasta_file.write_text(to_fasta("ATGC", "seq1 method=base4_direct"))
    args = _decode_args()

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr("genecoder.cli.decode.run_decoding_pipeline", boom)
    with pytest.raises(RuntimeError):
        process_single_decode(str(fasta_file), str(tmp_path / "out.bin"), args)


def test_process_single_analyze_unexpected_error(monkeypatch, tmp_path: Path) -> None:
    fasta_file = tmp_path / "a.fasta"
    fasta_file.write_text(to_fasta("ATGC", "seq1"))
    args = _analyze_args()

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr("genecoder.cli.analyze.calculate_gc_content", boom)
    with pytest.raises(RuntimeError):
        process_single_analyze(str(fasta_file), args)


def test_handle_sim_errors_unexpected_error(monkeypatch, tmp_path: Path) -> None:
    inp = tmp_path / "i.fasta"
    inp.write_text(to_fasta("ATGC", "seq1"))
    out = tmp_path / "o.fasta"
    args = _sim_args(inp, out)

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr("genecoder.cli.channel.introduce_errors", boom)
    with pytest.raises(RuntimeError):
        process_channel(
            args.input_file,
            args.output_file,
            args.simulators,
            args.constraints,
            sub_prob=args.sub_prob,
            ins_prob=args.ins_prob,
            del_prob=args.del_prob,
            seed=args.seed,
        )
