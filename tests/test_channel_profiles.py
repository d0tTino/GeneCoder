from genecoder.simulators.pipeline import ChannelPipeline
from genecoder.channel_config import ChannelConfig
from genecoder.simulators.insilicoseq import InsilicoSeqChannel
from genecoder import dnarsim_adapter, nanopore_sim


def test_insilicoseq_profile(monkeypatch):
    calls = []
    import genecoder.simulators.insilicoseq as iss_mod
    monkeypatch.setattr(iss_mod, "_HAS_ISS", True)

    def fake_sim(seq, model="hiseq", n_reads=1, read_length=100):
        calls.append((seq, model, n_reads, read_length))
        return ["SIM"]

    monkeypatch.setattr(iss_mod, "simulate_read", fake_sim, raising=False)
    pipeline = ChannelPipeline([InsilicoSeqChannel(read_length=50)])
    cfg = ChannelConfig(illumina_profile="novaseq")
    result = pipeline.simulate("ACGTACGT", config=cfg)
    assert result == "SIM"
    assert calls == [("ACGTACGT", "novaseq", 1, 50)]


def test_dnarsim_profile(monkeypatch):
    run_called = []
    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda c: "/usr/bin/" + c)

    def fake_run(cmd, seq):
        run_called.append(cmd)
        return "OK"

    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run)
    pipeline = ChannelPipeline([dnarsim_adapter.DNArSimChannel(error_rate=0.1)])
    cfg = ChannelConfig(nanopore_profile="r9")
    result = pipeline.simulate("TTTT", config=cfg)
    assert result == "OK"
    assert run_called == [["dnarsim", "-e", "0.1", "-p", "r9"]]
