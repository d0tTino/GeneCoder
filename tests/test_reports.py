import json
import base64
from pathlib import Path

from genecoder.app_helpers import EncodeResult, DecodeResult
from genecoder.report import encode_to_markdown, decode_to_html
from tests.test_cli import run_cli_command


def test_encode_markdown_report(tmp_path: Path) -> None:
    enc = EncodeResult(
        fasta=">seq\nACGT\n",
        encoded_dna="ACGT",
        metrics={"gc": 0.5},
        info_messages=["ok"],
    )
    md = encode_to_markdown(enc)
    assert "# Encoding Report" in md
    assert "gc" in md

    json_path = tmp_path / "enc.json"
    json_path.write_text(json.dumps(enc.__dict__))
    out_file = tmp_path / "report.md"
    result = run_cli_command([
        "report",
        "--input-json",
        str(json_path),
        "--type",
        "encode",
        "--output-file",
        str(out_file),
    ])
    assert result.returncode == 0
    assert out_file.read_text().startswith("# Encoding Report")


def test_decode_html_report(tmp_path: Path) -> None:
    dec = DecodeResult(decoded_bytes=b"abc", status_message="ok", fec_info="none")
    html = decode_to_html(dec)
    assert "Decoding Report" in html

    json_path = tmp_path / "dec.json"
    dec_dict = {
        "decoded_bytes": base64.b64encode(dec.decoded_bytes).decode(),
        "status_message": dec.status_message,
        "fec_info": dec.fec_info,
    }
    json_path.write_text(json.dumps(dec_dict))
    out_file = tmp_path / "report.html"
    result = run_cli_command([
        "report",
        "--input-json",
        str(json_path),
        "--type",
        "decode",
        "--format",
        "html",
        "--output-file",
        str(out_file),
    ])
    assert result.returncode == 0
    assert "<h1>Decoding Report</h1>" in out_file.read_text()
