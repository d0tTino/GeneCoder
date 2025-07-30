import json
import os
from pathlib import Path

import pytest

from tests.test_cli import run_cli_command


@pytest.mark.parametrize("sim,seed", [("illumina", "9"), ("nanopore", "6")])
def test_encode_decode_roundtrip(tmp_path: Path, sim: str, seed: str) -> None:
    env = os.environ.copy()
    src_path = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = seed

    input_file = tmp_path / "msg.txt"
    input_file.write_text("hi")

    enc = run_cli_command(
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
    assert enc.returncode == 0, enc.stderr

    manifest = tmp_path / "msg.txt.manifest.json"
    assert manifest.exists()
    metrics = json.loads(manifest.read_text()).get("metrics", {})
    for key in ["original_size", "dna_length", "compression_ratio", "bits_per_nt"]:
        assert key in metrics

    fasta_file = tmp_path / "msg.txt.fasta"
    dec = run_cli_command(
        [
            "decode",
            "--input-files",
            str(fasta_file),
            "--output-dir",
            str(tmp_path),
            "--method",
            "base4_direct",
            "--simulator",
            sim,
        ],
        env=env,
    )
    assert dec.returncode == 0, dec.stderr

    output_file = tmp_path / "msg.txt_decoded.bin"
    assert output_file.exists()
    assert output_file.read_text() == "hi"
