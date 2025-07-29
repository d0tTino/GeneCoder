import os
import sys
import types
from pathlib import Path

from tests.test_cli import run_cli_command
from tests.test_cli_channel import create_fasta


class _DummyFuture:
    def __init__(self, result: str) -> None:
        self._result = result

    def result(self) -> str:
        return self._result


class _DummyExecutor:
    called = False

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        _DummyExecutor.called = True
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, *args, **kwargs):
        return _DummyFuture(fn(*args, **kwargs))


def test_channel_cli_mpi(tmp_path: Path, monkeypatch) -> None:
    input_fasta = tmp_path / "in.fasta"
    create_fasta(input_fasta)
    output_fasta = tmp_path / "out.fasta"
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(
        f"""input: {input_fasta}\noutput: {output_fasta}\nsimulators:\n  - simple\n  - simple\nsynthesis:\n  min_length: 1\npipeline:\n  parallel: true\n  workers: 2\n  use_mpi: true\n"""
    )

    mpimod = types.ModuleType("mpi4py")
    futures_mod = types.ModuleType("mpi4py.futures")
    futures_mod.MPIPoolExecutor = _DummyExecutor
    mpimod.futures = futures_mod
    monkeypatch.setitem(sys.modules, "mpi4py", mpimod)
    monkeypatch.setitem(sys.modules, "mpi4py.futures", futures_mod)

    env = os.environ.copy()
    from pathlib import Path as _Path
    src_path = _Path(__file__).resolve().parent.parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENECODER_SIM_SEED"] = "1"

    result = run_cli_command(["channel", "run", str(cfg)], env=env)

    assert result.returncode == 0, result.stderr
    assert _DummyExecutor.called
    assert output_fasta.exists()
