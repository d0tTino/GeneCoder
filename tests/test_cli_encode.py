import argparse
import contextlib
import importlib
import importlib.util
import io
import os
import sys
import urllib.request
from pathlib import Path

import pytest

from genecoder.cli.encode import process_single_encode
from genecoder.error_detection import PARITY_RULE_GC_EVEN_A_ODD_T
from genecoder.formats import SequenceBatch, from_fasta
from genecoder.reed_solomon_codec import _HAS_REEDSOLO


class _Result:
    def __init__(self, code: int, out: str, err: str) -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def run_cli_command(command_args: list[str], env: dict[str, str] | None = None) -> _Result:
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
        suppress_constraint_warnings=False,
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


def test_process_single_encode_sequence_batch_metadata(tmp_path: Path) -> None:
    input_file = tmp_path / "meta.bin"
    input_file.write_text("batch")
    output_file = tmp_path / "meta_out.fasta"
    args = _encode_args()
    args.seed = 123
    process_single_encode(str(input_file), str(output_file), args)

    batch = SequenceBatch.from_fasta(output_file.read_text())
    assert batch.batch_id == "meta"
    assert batch.seed == 123
    assert batch.metadata.get("method") == "base4_direct"
    assert batch.metadata.get("input_file") == "meta.bin"
    assert len(batch.oligos) == 1
    oligo = batch.oligos[0]
    assert oligo.metadata.get("batch_size") == "1"
    assert oligo.metadata.get("oligo_index") == "1"
    assert oligo.seed == 123
    assert "batch_id=" in oligo.header
    assert batch.primary_sequence() == from_fasta(output_file.read_text())[0][1]


def test_process_single_encode_windows_path_stream(tmp_path: Path) -> None:
    input_file = tmp_path / "C:\\path\\seq.bin"
    input_file.write_text("data")
    output_file = tmp_path / "out_stream.fasta"
    process_single_encode(str(input_file), str(output_file), _encode_args(stream=True))

    records = from_fasta(output_file.read_text())
    header = records[0][0]
    assert "input_file=seq.bin" in header
    assert "\\" not in header


def test_process_single_encode_applies_fix(tmp_path: Path) -> None:
    input_file = tmp_path / "data.bin"
    # Produce low GC content and long homopolymers
    input_file.write_bytes(b"\x00" * 8)
    output_file = tmp_path / "out_fix.fasta"
    os.environ.pop("GENECODER_DISABLE_FIX", None)
    args = _encode_args()
    process_single_encode(str(input_file), str(output_file), args)

    records = from_fasta(output_file.read_text())
    seq = records[0][1]
    from genecoder.encoders import calculate_gc_content
    from genecoder.utils import get_max_homopolymer_length

    gc_val = calculate_gc_content(seq)
    max_hp = get_max_homopolymer_length(seq)
    assert args.gc_min <= gc_val <= args.gc_max
    assert max_hp <= args.max_homopolymer


_HAS_PYFINITE = importlib.util.find_spec("pyfinite") is not None


@pytest.mark.parametrize(
    ("fec", "channel"),
    [
        pytest.param(
            "reed_solomon",
            "illumina",
            marks=pytest.mark.skipif(
                not _HAS_REEDSOLO, reason="reedsolo not installed"
            ),
        ),
        pytest.param(
            "fountain",
            "nanopore",
            marks=pytest.mark.skipif(
                not _HAS_PYFINITE, reason="pyfinite not installed"
            ),
        ),
    ],
)
def test_cli_encode_plugins(tmp_path: Path, fec: str, channel: str) -> None:
    input_file = tmp_path / "data.bin"
    input_file.write_bytes(b"abc")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    result = run_cli_command(
        [
            "encode",
            "--input-files",
            str(input_file),
            "--output-dir",
            str(output_dir),
            "--fec",
            fec,
            "--channel",
            channel,
        ]
    )
    assert result.returncode == 0, result.stderr
