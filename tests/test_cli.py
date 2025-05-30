import pytest
import subprocess
import os
import shutil
import tempfile
from pathlib import Path

# Helper to get the root of the project
PROJECT_ROOT = Path(__file__).parent.parent

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def run_cli_command(command_args: list[str], env=None) -> subprocess.CompletedProcess:
    """Helper function to run CLI commands."""
    if env is None:
        env = os.environ.copy()
        # Ensure PYTHONPATH includes the project root so src.cli can be found
        env['PYTHONPATH'] = str(PROJECT_ROOT) + os.pathsep + env.get('PYTHONPATH', '')

    # Construct the command
    # Using python -m src.cli is generally more robust for module resolution
    full_command = [sys.executable, "-m", "src.cli"] + command_args
    
    return subprocess.run(
        full_command,
        capture_output=True,
        text=True,
        env=env,
        cwd=PROJECT_ROOT # Run from project root
    )

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
        assert f"method=base4_direct" in fasta_content
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

# Need to import sys for sys.executable in run_cli_command
import sys
