import sys
import types
import pytest

from genecoder.channel_config import ChannelConfig
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

    def add_done_callback(self, fn):
        fn(self)


class _DummyExecutor:
    called = False

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        """Accept arbitrary args like a real executor."""
        pass

    def __enter__(self) -> "_DummyExecutor":
        _DummyExecutor.called = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> bool:
        return False

    def submit(self, fn, *args, **kwargs):
        return _DummyFuture(fn(*args, **kwargs))


@pytest.mark.parametrize(
    "cfg",
    [
        ChannelConfig(parallel=True, workers=2),
        ChannelConfig(parallel=True, workers=2, use_process_pool=True),
    ],
)
def test_channel_pipeline_parallel(
    monkeypatch: pytest.MonkeyPatch, cfg: ChannelConfig
) -> None:
    if cfg.use_process_pool and sys.platform.startswith("win"):
        pytest.skip("ProcessPoolExecutor not supported on Windows for this test")

    calls: list[str] = []
    monkeypatch.setattr(pipeline_module.metrics, "increment", lambda k: calls.append(k))

    pipeline = ChannelPipeline([_AppendChannel("A"), _AppendChannel("B")])
    expected = pipeline.simulate("X")
    calls.clear()

    result = pipeline.simulate("X", config=cfg)

    assert result == expected
    assert calls == ["oligos_simulated"]


def test_channel_pipeline_mpi(monkeypatch: pytest.MonkeyPatch) -> None:
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
