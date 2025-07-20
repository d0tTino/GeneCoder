import types
import sys
import concurrent.futures

import pytest

from genecoder.channel_config import ChannelConfig
from genecoder.channels.base import BaseChannel
from genecoder.simulators.pipeline import ChannelPipeline
import genecoder.simulators.pipeline as pipeline_module


class _AppendChannel(BaseChannel):
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
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, *args, **kwargs):
        return _DummyFuture(fn(*args, **kwargs))


@pytest.mark.parametrize(
    "executor_attr, cfg_kwargs",
    [
        ("ThreadPoolExecutor", {"parallel": True, "workers": 2}),
        (
            "ProcessPoolExecutor",
            {"parallel": True, "workers": 2, "use_process_pool": True},
        ),
        ("MPIPoolExecutor", {"parallel": True, "workers": 2, "use_mpi": True}),
    ],
)
def test_channel_pipeline_with_mock_executor(monkeypatch, executor_attr, cfg_kwargs):
    calls: list[str] = []
    monkeypatch.setattr(pipeline_module.metrics, "increment", lambda key: calls.append(key))

    if executor_attr == "MPIPoolExecutor":
        mpimod = types.ModuleType("mpi4py")
        futures_mod = types.ModuleType("mpi4py.futures")
        futures_mod.MPIPoolExecutor = _DummyExecutor
        mpimod.futures = futures_mod
        monkeypatch.setitem(sys.modules, "mpi4py", mpimod)
        monkeypatch.setitem(sys.modules, "mpi4py.futures", futures_mod)
    else:
        monkeypatch.setattr(concurrent.futures, executor_attr, _DummyExecutor)

    pipeline = ChannelPipeline([_AppendChannel("A"), _AppendChannel("B")])
    expected = pipeline.simulate("X")
    calls.clear()

    cfg = ChannelConfig(**cfg_kwargs)
    result = pipeline.simulate("X", config=cfg)

    assert result == expected
    assert calls == ["oligos_simulated"]
