import os
import sys
import types
from pathlib import Path

from tests.test_cli import run_cli_command


class _DummyExecutor:
    called = False

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        _DummyExecutor.called = True
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def map(self, fn, iterable):
        for item in iterable:
            yield fn(item)


def test_pipeline_cli_mpi(tmp_path: Path, monkeypatch) -> None:
    inp = tmp_path / "data.bin"
    inp.write_bytes(b"abc")
    outp = tmp_path / "out.bin"

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

    result = run_cli_command(
        [
            "pipeline",
            str(inp),
            str(outp),
            "--codec",
            "reverse",
            "--mpi-workers",
            "2",
        ],
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert _DummyExecutor.called
    assert outp.read_bytes() == b"abc"
