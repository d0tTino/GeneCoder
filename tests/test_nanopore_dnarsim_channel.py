from genecoder.simulators.nanopore import NanoporeDNArSimChannel
import genecoder.simulators.nanopore as nanopore


def test_fallback_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    monkeypatch.setattr(nanopore.shutil, "which", lambda _: None)
    ch = NanoporeDNArSimChannel(error_rate=0.2)
    first = ch.simulate("ACGTACGTACGT")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    second = ch.simulate("ACGTACGTACGT")
    assert first == second == "ACGAGTACCGT"


def test_cli_invocation(monkeypatch):
    called = []
    monkeypatch.setattr(nanopore.shutil, "which", lambda _: "/usr/bin/dnarsim")
    monkeypatch.setattr(nanopore, "_parse_env_options", lambda _: [])

    def fake_run(cmd, seq):
        called.append((cmd, seq))
        return "ok"

    monkeypatch.setattr(nanopore, "_run_external", fake_run)
    ch = NanoporeDNArSimChannel(error_rate=0.1, profile="r9")
    result = ch.simulate("ACGT")
    assert result == "ok"
    assert called == [(["dnarsim", "-e", "0.1", "-p", "r9"], "ACGT")]

