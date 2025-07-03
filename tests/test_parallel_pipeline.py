from genecoder.channel_sim import Channel
from genecoder.simulators.pipeline import ChannelPipeline


def test_parallel_pipeline_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    pipeline = ChannelPipeline([Channel(0.1), Channel(0.2)])
    seq = "ACGTACGTACGT"
    serial = pipeline.simulate(seq)
    threads = pipeline.simulate(seq, parallel=True, workers=2)
    processes = pipeline.simulate(seq, parallel=True, workers=2, use_process_pool=True)
    assert serial == threads == processes
