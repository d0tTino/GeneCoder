import pytest
from genecoder.channel_sim import Channel
from genecoder.simulators.pipeline import ChannelPipeline

pytest.importorskip("mpi4py")
import shutil

if shutil.which("mpiexec") is None:
    pytest.skip("mpiexec not available", allow_module_level=True)


def test_mpi_pipeline_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    pipeline = ChannelPipeline([Channel(0.1), Channel(0.2)])
    seq = "ACGTACGTACGT"
    serial = pipeline.simulate(seq)
    mpi_result = pipeline.simulate(
        seq,
        parallel=True,
        workers=2,
        use_mpi=True,
    )
    assert serial == mpi_result
