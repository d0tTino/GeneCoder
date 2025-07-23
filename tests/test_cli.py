import argparse
import importlib
import io
import os
import sys
import tempfile
import contextlib
from pathlib import Path
import urllib.request
import pytest
from genecoder.utils import get_temp_dir
from src.genecoder.formats import to_fasta, from_fasta
from src.genecoder.cli.encode import reverse_complement, process_single_encode
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T

# Helper to get the root of the project
PROJECT_ROOT = Path(__file__).parent.parent

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory(dir=get_temp_dir()) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def small_fasta_file(temp_dir: Path) -> Path:
    """Create a simple FASTA file for CLI error simulation tests."""
    fasta_path = temp_dir / "input.fasta"
    fasta_path.write_text(to_fasta("ATGCATGC", "seq1"))
    return fasta_path

class _Result:
    def __init__(self, code: int, out: str, err: str) -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def run_cli_command(command_args: list[str], env=None) -> _Result:
    """Invoke CLI main with arguments and capture output."""

    if env is None:
        env = os.environ.copy()

    saved_env = os.environ.copy()
    saved_path = sys.path[:]
    os.environ.update(env)
    os.environ.setdefault("GENECODER_DISABLE_FIX", "1")

    import importlib as _importlib
    import genecoder.plugin_manager as _pm
    import genecoder.cli.plugin as _plugin_cli

    _pm._initialized = False
    _orig_urlopen = urllib.request.urlopen
    _orig_checksum = _pm.compute_checksum

    if "PYTHONPATH" in env:
        for path in env["PYTHONPATH"].split(os.pathsep):
            if path and path not in sys.path:
                sys.path.insert(0, path)
                sc = Path(path) / "sitecustomize.py"
                if sc.exists():
                    spec = importlib.util.spec_from_file_location("sitecustomize", sc)
                    assert spec and spec.loader
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

    from genecoder.cli.cli import main

    stdout = io.StringIO()
    stderr = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            main(command_args)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:  # pragma: no cover - CLI error path
        code = 1
        print(str(exc), file=stderr)
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
        sys.path[:] = saved_path
        _importlib.reload(_plugin_cli)
        urllib.request.urlopen = _orig_urlopen
        _pm.urllib.request.urlopen = _orig_urlopen
        _pm.compute_checksum = _orig_checksum

    return _Result(code, stdout.getvalue(), stderr.getvalue())

# --- Test Scenarios for Batch Encoding ---

def test_batch_encode_success(temp_dir: Path):
    """Test successful batch encoding with multiple input files."""
    input_dir = temp_dir / "input_encode"
    output_dir = temp_dir / "output_encode"
    input_dir.mkdir()
    output_dir.mkdir()

    file_contents = {
        "file1.txt": "Hello GeneCoder!",
        "file2.txt": "Batch processing test.",
        "file3.dat": "12345"
    }
    input_files = []
    for name, content in file_contents.items():
        p = input_dir / name
        p.write_text(content)
        input_files.append(str(p))

    cmd_args = ["encode", "--input-files"] + input_files + ["--output-dir", str(output_dir), "--method", "base4_direct"]
    result = run_cli_command(cmd_args)

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    assert result.returncode == 0, f"CLI command failed with error: {result.stderr}"

    for input_file_path in input_files:
        base_name = os.path.basename(input_file_path)
        expected_output_file = output_dir / (base_name + ".fasta")
        assert expected_output_file.exists(), f"Output file {expected_output_file} was not created."
        # Optionally check content
        fasta_content = expected_output_file.read_text()
        assert "method=base4_direct" in fasta_content
        assert f"input_file={base_name}" in fasta_content

def test_batch_encode_error_no_output_dir(temp_dir: Path):
    """Test batch encoding error when --output-dir is missing for multiple files."""
    input_dir = temp_dir / "input_err_encode"
    input_dir.mkdir()
    
    file1 = input_dir / "file1.txt"
    file1.write_text("test1")
    file2 = input_dir / "file2.txt"
    file2.write_text("test2")

    cmd_args = ["encode", "--input-files", str(file1), str(file2), "--method", "base4_direct"]
    result = run_cli_command(cmd_args)

    assert result.returncode != 0, "CLI command should have failed."
    assert "--output-dir is required" in result.stderr or "Error: --output-dir is required" in result.stderr

def test_batch_encode_single_file_with_output_dir(temp_dir: Path):
    """Test batch encoding with a single file and --output-dir."""
    input_dir = temp_dir / "input_single_encode"
    output_dir = temp_dir / "output_single_encode"
    input_dir.mkdir()
    output_dir.mkdir()

    file1 = input_dir / "file1.txt"
    file1.write_text("single file test")
    
    cmd_args = ["encode", "--input-files", str(file1), "--output-dir", str(output_dir), "--method", "base4_direct"]
    result = run_cli_command(cmd_args)

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    assert result.returncode == 0, f"CLI command failed with error: {result.stderr}"
    
    expected_output_file = output_dir / ("file1.txt.fasta")
    assert expected_output_file.exists(), f"Output file {expected_output_file} was not created."


def test_gc_balanced_params_in_header_default_and_custom(temp_dir: Path):
    """Verify gc_balanced CLI parameters are parsed and appear in FASTA headers."""
    input_dir = temp_dir / "input_gc"
    output_dir = temp_dir / "output_gc"
    input_dir.mkdir()
    output_dir.mkdir()

    # File for default parameters
    default_file = input_dir / "default.txt"
    # Use data that reliably meets GC constraints with and without inversion
    default_file.write_bytes(b"\xdc\x05b\xa4$J5\xcf3\xbfJJa\xab} ")

    cmd_default = [
        "encode",
        "--input-files",
        str(default_file),
        "--output-dir",
        str(output_dir),
        "--method",
        "gc_balanced",
    ]
    result_default = run_cli_command(cmd_default)
    assert result_default.returncode == 0, f"Default encode failed: {result_default.stderr}"
    default_out = output_dir / "default.txt.fasta"
    assert default_out.exists()
    header_default = default_out.read_text().splitlines()[0]
    assert "gc_min=0.45" in header_default
    assert "gc_max=0.55" in header_default
    assert "max_homopolymer=3" in header_default

    # File for custom parameters
    custom_file = input_dir / "custom.txt"
    custom_file.write_bytes(b"\xdc\x05b\xa4$J5\xcf3\xbfJJa\xab} ")

    cmd_custom = [
        "encode",
        "--input-files",
        str(custom_file),
        "--output-dir",
        str(output_dir),
        "--method",
        "gc_balanced",
        "--gc-min",
        "0.4",
        "--gc-max",
        "0.6",
        "--max-homopolymer",
        "4",
    ]
    result_custom = run_cli_command(cmd_custom)
    assert result_custom.returncode == 0, f"Custom encode failed: {result_custom.stderr}"
    custom_out = output_dir / "custom.txt.fasta"
    assert custom_out.exists()
    header_custom = custom_out.read_text().splitlines()[0]
    assert "gc_min=0.4" in header_custom
    assert "gc_max=0.6" in header_custom
    assert "max_homopolymer=4" in header_custom


def test_encode_mirror(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("flet")
    input_file = tmp_path / "msg.txt"
    input_file.write_text("mirror")
    output_file = tmp_path / "seq.fasta"

    calls: list[tuple[str, str | None]] = []

    def fake_show(seq: str, *, seq2: str | None = None, **_: object) -> None:
        calls.append((seq, seq2))

    monkeypatch.setattr("genecoder.helix_view.show_helix_ui", fake_show)

    args = argparse.Namespace(
        method="base4_direct",
        add_parity=False,
        k_value=7,
        parity_rule=PARITY_RULE_GC_EVEN_A_ODD_T,
        fec=None,
        gc_min=0.45,
        gc_max=0.55,
        max_homopolymer=3,
        alphabet="base4",
        stream=False,
        capsule=None,
        export_csv=None,
        mirror=True,
    )

    process_single_encode(str(input_file), str(output_file), args)

    records = from_fasta(output_file.read_text())
    assert len(records) == 2
    assert records[1][1] == reverse_complement(records[0][1])
    assert "mirror=rc" in records[1][0]
    assert len(calls) == 1

# --- Test Scenarios for Batch Decoding ---

def create_dummy_fasta_file(file_path: Path, content: str, method: str = "base4_direct", input_filename: str = "dummy.txt"):
    """Helper to create a dummy FASTA file for decoding tests."""
    # This is a simplified FASTA creation, assuming base4_direct for simplicity
    # A more robust way would be to call the encoder itself.
    from src.genecoder.encoders import encode_base4_direct
    from src.genecoder.formats import to_fasta
    
    encoded_dna = encode_base4_direct(content.encode('utf-8'))
    header = f"method={method} input_file={input_filename}"
    fasta_content = to_fasta(encoded_dna, header)
    file_path.write_text(fasta_content)

def test_batch_decode_success(temp_dir: Path):
    """Test successful batch decoding with multiple input FASTA files."""
    input_dir = temp_dir / "input_decode_fasta"
    output_dir = temp_dir / "output_decode"
    input_dir.mkdir()
    output_dir.mkdir()

    fasta_files_info = {
        "seq1.fasta": ("test content 1", "file1.txt"),
        "seq2.fa": ("another sequence", "file2.txt"),
        "seq3.fasta": ("12345", "file3.dat")
    }
    input_fasta_paths = []
    for name, (content, original_name) in fasta_files_info.items():
        p = input_dir / name
        create_dummy_fasta_file(p, content, input_filename=original_name)
        input_fasta_paths.append(str(p))

    cmd_args = ["decode", "--input-files"] + input_fasta_paths + ["--output-dir", str(output_dir), "--method", "base4_direct"]
    result = run_cli_command(cmd_args)

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    assert result.returncode == 0, f"CLI command failed with error: {result.stderr}"

    for input_fasta_path_str in input_fasta_paths:
        input_fasta_path = Path(input_fasta_path_str)
        base_name_no_ext, _ = os.path.splitext(input_fasta_path.name)
        expected_output_file = output_dir / (base_name_no_ext + "_decoded.bin")
        assert expected_output_file.exists(), f"Output file {expected_output_file} was not created."
        
        # Verify content for one file
        if input_fasta_path.name == "seq1.fasta":
            decoded_content = expected_output_file.read_text()
            assert decoded_content == "test content 1"

def test_batch_decode_error_no_output_dir(temp_dir: Path):
    """Test batch decoding error when --output-dir is missing for multiple files."""
    input_dir = temp_dir / "input_err_decode"
    input_dir.mkdir()
    
    file1_fasta = input_dir / "file1.fasta"
    create_dummy_fasta_file(file1_fasta, "test1")
    file2_fasta = input_dir / "file2.fasta"
    create_dummy_fasta_file(file2_fasta, "test2")

    cmd_args = ["decode", "--input-files", str(file1_fasta), str(file2_fasta), "--method", "base4_direct"]
    result = run_cli_command(cmd_args)

    assert result.returncode != 0, "CLI command should have failed."
    assert "--output-dir is required" in result.stderr or "Error: --output-dir is required" in result.stderr

def test_batch_decode_single_file_with_output_dir(temp_dir: Path):
    """Test batch decoding with a single file and --output-dir."""
    input_dir = temp_dir / "input_single_decode"
    output_dir = temp_dir / "output_single_decode"
    input_dir.mkdir()
    output_dir.mkdir()

    file1_fasta = input_dir / "file1.fasta"
    create_dummy_fasta_file(file1_fasta, "single decode test")
    
    cmd_args = ["decode", "--input-files", str(file1_fasta), "--output-dir", str(output_dir), "--method", "base4_direct"]
    result = run_cli_command(cmd_args)

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    assert result.returncode == 0, f"CLI command failed with error: {result.stderr}"
    
    expected_output_file = output_dir / ("file1_decoded.bin")
    assert expected_output_file.exists(), f"Output file {expected_output_file} was not created."
    assert expected_output_file.read_text() == "single decode test"


def test_decode_method_mismatch(temp_dir: Path):
    """Decoding should fail if --method does not match FASTA header."""
    input_dir = temp_dir / "input_method_mismatch"
    output_dir = temp_dir / "output_method_mismatch"
    input_dir.mkdir()
    output_dir.mkdir()

    fasta_file = input_dir / "file1.fasta"
    # Create FASTA with method base4_direct
    create_dummy_fasta_file(fasta_file, "mismatch test", method="base4_direct")

    cmd_args = [
        "decode",
        "--input-files",
        str(fasta_file),
        "--output-dir",
        str(output_dir),
        "--method",
        "huffman",
    ]
    result = run_cli_command(cmd_args)

    assert result.returncode != 0, "CLI decode should fail on method mismatch"
    assert "FASTA header specifies method" in result.stdout


def create_simple_fasta(file_path: Path, seq: str, header: str = "seq1"):
    from src.genecoder.formats import to_fasta
    file_path.write_text(to_fasta(seq, header))


def test_analyze_single_file(temp_dir: Path):
    fasta_file = temp_dir / "test.fasta"
    create_simple_fasta(fasta_file, "ATGCATGC")

    cmd_args = [
        "analyze",
        "--input-files",
        str(fasta_file),
        "--window-size",
        "4",
        "--step",
        "4",
        "--min-homopolymer",
        "2",
    ]
    result = run_cli_command(cmd_args)

    assert result.returncode == 0
    assert "GC content: 50.00%" in result.stdout
    assert "Max homopolymer length: 1" in result.stdout


def test_analyze_multiple_files(temp_dir: Path):
    f1 = temp_dir / "s1.fasta"
    f2 = temp_dir / "s2.fasta"
    create_simple_fasta(f1, "AAAAACCCC")
    create_simple_fasta(f2, "GGGGTTTT")

    cmd_args = ["analyze", "--input-files", str(f1), str(f2)]
    result = run_cli_command(cmd_args)

    assert result.returncode == 0
    # Should produce analysis for both files
    assert result.stdout.count("Sequence length:") == 2


def test_analyze_suggest_fix(temp_dir: Path):
    fasta_file = temp_dir / "bad.fasta"
    create_simple_fasta(fasta_file, "AAAAAA")

    result = run_cli_command(["analyze", "--input-files", str(fasta_file)])

    assert result.returncode == 0
    assert "Suggested fix" in result.stdout


def test_channel_command_probabilities(temp_dir: Path, small_fasta_file: Path) -> None:
    """CLI channel with probabilities should output a corrupted FASTA file."""
    out_file = temp_dir / "corrupted.fasta"
    cmd_args = [
        "channel",
        "apply",
        "--input-file",
        str(small_fasta_file),
        "--output-file",
        str(out_file),
        "--sub-prob",
        "0.5",
        "--seed",
        "1",
        "--min-length",
        "1",
    ]
    result = run_cli_command(cmd_args)
    assert result.returncode == 0, f"channel failed: {result.stderr}"
    assert out_file.exists()

    original_seq = from_fasta(small_fasta_file.read_text())[0][1]
    new_seq = from_fasta(out_file.read_text())[0][1]
    assert new_seq != original_seq


def test_channel_missing_input(temp_dir: Path) -> None:
    out_file = temp_dir / "corrupted.fasta"
    cmd_args = [
        "channel",
        "apply",
        "--input-file",
        str(temp_dir / "nofile.fasta"),
        "--output-file",
        str(out_file),
        "--sub-prob",
        "0.1",
        "--min-length",
        "1",
    ]
    result = run_cli_command(cmd_args)
    assert result.returncode != 0
    assert "not found" in result.stderr.lower()


def test_channel_unknown_simulator(temp_dir: Path, small_fasta_file: Path) -> None:
    out_file = temp_dir / "corrupt.fasta"
    cmd_args = [
        "channel",
        "apply",
        "--input-file",
        str(small_fasta_file),
        "--output-file",
        str(out_file),
        "--simulator",
        "bogus",
        "--min-length",
        "1",
    ]
    result = run_cli_command(cmd_args)
    assert result.returncode != 0
    assert "unknown simulator" in result.stderr.lower()


def test_invalid_fec_none_choice(temp_dir: Path):
    """Passing '--fec None' should result in an argparse error."""
    input_file = temp_dir / "invalid.txt"
    input_file.write_text("invalid fec")

    cmd_args = [
        "encode",
        "--input-files",
        str(input_file),
        "--output-dir",
        str(temp_dir),
        "--method",
        "base4_direct",
        "--fec",
        "None",
    ]
    result = run_cli_command(cmd_args)
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_encode_invalid_chunk_size(temp_dir: Path, chunk_size: int) -> None:
    """Streaming encode should fail for non-positive chunk sizes."""
    input_file = temp_dir / "in.txt"
    input_file.write_text("data")
    output_file = temp_dir / "out.fasta"

    cmd_args = [
        "encode",
        "--input-files",
        str(input_file),
        "--output-file",
        str(output_file),
        "--method",
        "base4_direct",
        "--stream",
        "--chunk-size",
        str(chunk_size),
    ]
    result = run_cli_command(cmd_args)
    assert result.returncode != 0
    assert "chunk-size" in result.stderr.lower()


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_decode_invalid_chunk_size(temp_dir: Path, chunk_size: int) -> None:
    """Streaming decode should fail for non-positive chunk sizes."""
    fasta_file = temp_dir / "seq.fasta"
    create_dummy_fasta_file(fasta_file, "hello")
    output_file = temp_dir / "out.bin"

    cmd_args = [
        "decode",
        "--input-files",
        str(fasta_file),
        "--output-file",
        str(output_file),
        "--method",
        "base4_direct",
        "--stream",
        "--chunk-size",
        str(chunk_size),
    ]
    result = run_cli_command(cmd_args)
    assert result.returncode != 0
    assert "chunk-size" in result.stderr.lower()


def test_to_fasta_invalid_header_newline():
    with pytest.raises(ValueError):
        to_fasta("ATGC", "bad\nheader")


def test_to_fasta_invalid_header_gt():
    with pytest.raises(ValueError):
        to_fasta("ATGC", "bad>header")

