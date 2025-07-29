
import genecoder.simulators.nanopore as nanopore
from genecoder.simulators.nanopore import NanoporeDNArSimChannel


def test_fallback_output_length(monkeypatch) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    monkeypatch.setattr(nanopore.shutil, "which", lambda _: None)
    # ensure external runner is not used
    monkeypatch.setattr(
        nanopore,
        "_run_external",
        lambda *_: (_ for _ in ()).throw(AssertionError("_run_external called")),
    )

    seq = "ACGT" * 10
    channel = NanoporeDNArSimChannel(error_rate=0.4)
    result = channel.simulate(seq)

    assert 0.5 * len(seq) <= len(result) <= 1.5 * len(seq)
