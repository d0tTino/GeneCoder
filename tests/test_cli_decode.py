import argparse
import base64
import os
import pytest

from pathlib import Path
from tests.test_cli import run_cli_command

from genecoder.cli.options import build_encoding_options, build_decoding_options
from genecoder.cli import run_encoding_pipeline, run_decoding_pipeline
from genecoder.encoders import encode_base4_direct
from genecoder.formats import SequenceBatch, to_fasta
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder import plugins


def _sample_dna(data: bytes) -> tuple[str, str]:
    plugins.load_plugins()
    enc_args = argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
    )
    enc_opts = build_encoding_options(enc_args)
    dna, header, *_ = run_encoding_pipeline(data, enc_opts, "in.bin")
    return dna, header


def _decoding_opts():
    plugins.load_plugins()
    dec_args = argparse.Namespace(
        method="base4_direct",
        check_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
    )
    dec_opts = build_decoding_options(dec_args)
    return dec_opts


def test_run_decoding_invalid_fec_info_base64() -> None:
    dna, header = _sample_dna(b"abc")
    header += " fec=reed_solomon fec_info=abc"
    dec_opts = _decoding_opts()
    with pytest.raises(ValueError, match="Invalid 'fec_info'"):
        run_decoding_pipeline(dna, header, dec_opts, "in.bin")


def test_run_decoding_invalid_fec_info_json() -> None:
    dna, header = _sample_dna(b"abc")
    bad_json = base64.b64encode(b"not json").decode()
    header += f" fec=reed_solomon fec_info={bad_json}"
    dec_opts = _decoding_opts()
    with pytest.raises(ValueError, match="Invalid 'fec_info'"):
        run_decoding_pipeline(dna, header, dec_opts, "in.bin")


def test_cli_decode_duplicate_output_names(tmp_path: Path) -> None:
    dna1 = encode_base4_direct(b"one")
    dna2 = encode_base4_direct(b"two")
    header = "method=base4_direct input_file=dup.bin"
    f1 = tmp_path / "a.fasta"
    f1.write_text(to_fasta(dna1, header))
    f2 = tmp_path / "b.fasta"
    f2.write_text(to_fasta(dna2, header))

    res = run_cli_command(
        [
            "decode",
            "--input-files",
            str(f1),
            str(f2),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--auto-ext",
        ]
    )
    assert res.returncode == 0, res.stderr

    out1 = tmp_path / "dup.bin"
    out2 = tmp_path / "dup_1.bin"
    assert out1.read_bytes() == b"one"
    assert out2.read_bytes() == b"two"


def test_cli_decode_sequence_batch_round_trip(tmp_path: Path) -> None:
    input_file = tmp_path / "payload.bin"
    input_file.write_bytes(b"hello world")
    encoded_dir = tmp_path / "encoded"
    encoded_dir.mkdir()

    enc_res = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_file),
            "--output-dir",
            str(encoded_dir),
            "--method",
            "base4_direct",
            "--seed",
            "7",
        ]
    )
    assert enc_res.returncode == 0, enc_res.stderr
    fasta_path = encoded_dir / "payload.bin.fasta"
    batch = SequenceBatch.from_fasta(fasta_path.read_text())

    sequence = batch.primary_sequence()
    split = len(sequence) // 2 or len(sequence)
    records = [
        (batch.first_header(), sequence[:split]),
        (batch.first_header(), sequence[split:]),
    ]
    split_batch = SequenceBatch.build(
        records,
        batch_id=batch.batch_id,
        batch_seed=batch.seed,
    )
    split_path = tmp_path / "payload_split.fasta"
    split_path.write_text(split_batch.to_fasta(line_width=80))

    decoded_dir = tmp_path / "decoded"
    decoded_dir.mkdir()
    dec_res = run_cli_command(
        [
            "decode",
            "--input-files",
            str(split_path),
            "--output-dir",
            str(decoded_dir),
            "--method",
            "base4_direct",
        ]
    )
    assert dec_res.returncode == 0, dec_res.stderr
    outputs = list(decoded_dir.glob("*"))
    assert len(outputs) == 1
    assert outputs[0].read_bytes() == input_file.read_bytes()


@pytest.mark.parametrize("sim_name", ["d2sim", "dnarsim", "squigulator", "desp"])
def test_cli_decode_missing_simulator(tmp_path: Path, sim_name: str) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    input_file = tmp_path / "in.txt"
    input_file.write_text("missing test")

    enc_res = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--fec",
            "triple_repeat",
        ],
        env=env,
    )
    assert enc_res.returncode == 0, enc_res.stderr
    fasta_file = tmp_path / "in.txt.fasta"
    assert fasta_file.exists()

    dec_res = run_cli_command(
        [
            "decode",
            "--input-files",
            str(fasta_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--simulator",
            sim_name,
        ],
        env=env,
    )
    assert dec_res.returncode == 0, dec_res.stderr
    out_file = tmp_path / "in.txt_decoded.bin"
    assert out_file.exists()
    assert out_file.read_text().startswith("missing")


@pytest.mark.parametrize("sim_name", ["d2sim", "dnarsim", "squigulator", "desp"])
def test_cli_decode_simulator_failure(tmp_path: Path, sim_name: str) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / sim_name
    script.write_text("#!/bin/sh\nexit 1\n")
    script.chmod(0o755)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    input_file = tmp_path / "in.txt"
    input_file.write_text("failure test")

    enc_res = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--fec",
            "triple_repeat",
        ],
        env=env,
    )
    assert enc_res.returncode == 0, enc_res.stderr
    fasta_file = tmp_path / "in.txt.fasta"
    assert fasta_file.exists()

    dec_res = run_cli_command(
        [
            "decode",
            "--input-files",
            str(fasta_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--simulator",
            sim_name,
        ],
        env=env,
    )
    assert dec_res.returncode == 0, dec_res.stderr
    out_file = tmp_path / "in.txt_decoded.bin"
    assert out_file.exists()
    assert out_file.read_text().startswith("failure")


def test_cli_decode_simulator_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    input_file = tmp_path / "in.txt"
    input_file.write_text("profile test")

    enc_res = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--fec",
            "triple_repeat",
        ],
        env=env,
    )
    assert enc_res.returncode == 0, enc_res.stderr
    fasta_file = tmp_path / "in.txt.fasta"
    assert fasta_file.exists()

    called: list[str] = []

    import genecoder.simulators.illumina as illumina

    monkeypatch.setattr(illumina.IlluminaChannel, "simulate", lambda self, seq: seq)

    def fake_with_profile(self: illumina.IlluminaChannel, profile: str):
        called.append(profile)
        return self

    monkeypatch.setattr(illumina.IlluminaChannel, "with_profile", fake_with_profile)

    dec_res = run_cli_command(
        [
            "decode",
            "--input-files",
            str(fasta_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--simulator",
            "illumina",
            "--profile",
            "miseq",
        ],
        env=env,
    )
    assert dec_res.returncode == 0, dec_res.stderr
    out_file = tmp_path / "in.txt_decoded.bin"
    assert out_file.exists()
    assert out_file.read_text() == "profile test"
    assert called == ["miseq"]
