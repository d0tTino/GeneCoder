import sys
import types
from typing import Callable, Literal

import pytest

from genecoder.channel_config import ChannelConfig
from types import TracebackType

from genecoder.simulators.pipeline import ChannelPipeline
import genecoder.simulators.pipeline as pipeline_module


class _AppendChannel:
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def simulate(self, sequence: str) -> str:
        return sequence + self.suffix


class _DummyFuture:
    def __init__(self, result: str) -> None:
        self._result = result

    def result(self) -> str:
        return self._result


class _DummyExecutor:
    called = False

    def __enter__(self) -> "_DummyExecutor":
        _DummyExecutor.called = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        return False

    def submit(self, fn: Callable[..., str], *args: object, **kwargs: object) -> _DummyFuture:
        return _DummyFuture(fn(*args, **kwargs))


pytest.importorskip("mpi4py")


def test_mpi_pipeline_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(pipeline_module.metrics, "increment", lambda k: calls.append(k))

    mpimod = types.ModuleType("mpi4py")
    futures_mod = types.ModuleType("mpi4py.futures")
    futures_mod.MPIPoolExecutor = _DummyExecutor  # type: ignore[attr-defined]
    mpimod.futures = futures_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mpi4py", mpimod)
    monkeypatch.setitem(sys.modules, "mpi4py.futures", futures_mod)

    pipeline = ChannelPipeline([_AppendChannel("A"), _AppendChannel("B")])
    expected = pipeline.simulate("X")
    calls.clear()
    _DummyExecutor.called = False

    cfg = ChannelConfig(parallel=True, workers=2, use_mpi=True)
    result = pipeline.simulate("X", config=cfg)

    assert result == expected
    assert _DummyExecutor.called
    assert calls == ["oligos_simulated"]
