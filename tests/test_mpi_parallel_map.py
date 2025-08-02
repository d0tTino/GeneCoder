import sys
import types

from genecoder.parallel import parallel_map


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


def test_parallel_map_mpi(monkeypatch):
    mpimod = types.ModuleType("mpi4py")
    futures_mod = types.ModuleType("mpi4py.futures")
    futures_mod.MPIPoolExecutor = _DummyExecutor
    mpimod.futures = futures_mod
    monkeypatch.setitem(sys.modules, "mpi4py", mpimod)
    monkeypatch.setitem(sys.modules, "mpi4py.futures", futures_mod)

    _DummyExecutor.called = False
    result = parallel_map(lambda x: x + 1, [1, 2], workers=2, use_mpi=True)

    assert result == [2, 3]
    assert _DummyExecutor.called
