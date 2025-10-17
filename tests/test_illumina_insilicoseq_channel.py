
from genecoder.simulators.illumina import IlluminaInSilicoSeqChannel
import genecoder.simulators.illumina.cli as illumina_cli
import genecoder.random_utils as random_utils


def test_fallback_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    monkeypatch.setattr(illumina_cli.shutil, "which", lambda _: None)
    random_utils._RNG = None
    channel = IlluminaInSilicoSeqChannel(error_rate=0.2)
    first = channel.simulate("ACGTACGTACGT")
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    random_utils._RNG = None
    second = channel.simulate("ACGTACGTACGT")
    assert first == second == "ACATATGTACGT"


def test_cli_invocation(monkeypatch):
    called = []
    monkeypatch.setattr(illumina_cli.shutil, "which", lambda _: "/usr/bin/insilicoseq")
    monkeypatch.setattr(illumina_cli, "_parse_env_options", lambda _: [])
    def fake_run(cmd, seq):
        called.append((cmd, seq))
        return "ok"
    monkeypatch.setattr(illumina_cli, "_run_external", fake_run)
    ch = IlluminaInSilicoSeqChannel(error_rate=0.1)
    result = ch.simulate("ACGT")
    assert result == "ok"
    assert called == [(["insilicoseq", "-e", "0.1"], "ACGT")]

