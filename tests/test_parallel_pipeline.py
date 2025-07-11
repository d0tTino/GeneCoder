from genecoder.channel_sim import Channel
from genecoder.channel_config import ChannelConfig
from genecoder.simulators.pipeline import ChannelPipeline


def test_parallel_pipeline_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    pipeline = ChannelPipeline([Channel(0.1), Channel(0.2)])
    seq = "ACGTACGTACGT"
    serial = pipeline.simulate(seq)
    cfg_threads = ChannelConfig(parallel=True, workers=2)
    threads = pipeline.simulate(seq, config=cfg_threads)
    cfg_proc = ChannelConfig(parallel=True, workers=2, use_process_pool=True)
    processes = pipeline.simulate(seq, config=cfg_proc)
    assert serial == threads == processes
