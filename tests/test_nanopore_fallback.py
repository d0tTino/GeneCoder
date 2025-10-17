
import genecoder.simulators.nanopore as nanopore
import genecoder.simulators.nanopore_external as nanopore_external
from genecoder.simulators.nanopore import NanoporeDNArSimChannel


def test_fallback_output_length(monkeypatch) -> None:
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    monkeypatch.setattr(
        nanopore_external,
        "run_dnarsim_cli",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("run_dnarsim_cli called")
        ),
    )

    seq = "ACGT" * 10
    channel = NanoporeDNArSimChannel(error_rate=0.4)
    result = channel.simulate(seq)

    assert 0.5 * len(seq) <= len(result) <= 1.5 * len(seq)
