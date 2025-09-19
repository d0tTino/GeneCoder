import json
from pathlib import Path

from genecoder.html_report import generate_html_report
from tests.test_cli import run_cli_command


def _make_manifest(path: Path) -> Path:
    data = {
        "file": "test.bin",
        "encoding_parameters": {"method": "base4_direct"},
        "metrics": {
            "gc_content": 0.5,
            "gc_variance": 0.01,
            "max_homopolymer": 4,
            "ecc_success_rates": {"rs": 0.9},
            "substitutions": 7,
            "insertions": 2,
            "deletions": 3,
            "coverage": 42,
        },
    }
    path.write_text(json.dumps(data))
    return path


def test_generate_html_report(tmp_path: Path) -> None:
    manifest = _make_manifest(tmp_path / "m.json")
    html = generate_html_report(str(manifest))
    assert "50.00%" in html
    assert "GC Variance" in html
    assert "Max Homopolymer Length" in html
    assert "rs" in html
    assert "<h2>Error Metrics</h2>" in html
    assert "Substitutions:</strong> 7" in html
    assert "Insertions:</strong> 2" in html
    assert "Deletions:</strong> 3" in html
    assert "Coverage:</strong> 42" in html


def test_cli_html_report_stdout(tmp_path: Path) -> None:
    manifest = _make_manifest(tmp_path / "m.json")
    result = run_cli_command(["html-report", "--manifest", str(manifest)])
    assert result.returncode == 0
    assert "GeneCoder Summary Report" in result.stdout
    assert "50.00%" in result.stdout
    assert "GC Variance" in result.stdout
    assert "<h2>Error Metrics</h2>" in result.stdout
    assert "Substitutions:</strong> 7" in result.stdout
    assert "Insertions:</strong> 2" in result.stdout
    assert "Deletions:</strong> 3" in result.stdout
    assert "Coverage:</strong> 42" in result.stdout
