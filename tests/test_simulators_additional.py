
from genecoder.simulators.illumina import IlluminaChannel, register as reg_illumina
from genecoder.simulators.adv_nanopore import AdvancedNanoporeChannel, register as reg_advnano


def test_register_channels():
    from genecoder.channels.base import BaseChannel
    registry: dict[str, BaseChannel] = {}
    reg_illumina(lambda n, ch: registry.setdefault(n, ch))
    reg_advnano(lambda n, ch: registry.setdefault(n, ch))
    assert "illumina" in registry and isinstance(registry["illumina"], BaseChannel)
    assert "adv_nanopore" in registry and isinstance(registry["adv_nanopore"], BaseChannel)


def test_illumina_simulator_deterministic(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    channel = IlluminaChannel(substitution_rate=0.5, insertion_rate=0.0, deletion_rate=0.0, read_length=4)
    out = channel.simulate("AAAA")
    assert out == "ACCT"


def test_adv_nanopore_homopolymer_bias(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "2")
    channel = AdvancedNanoporeChannel(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.5, read_length=6)
    result = channel.simulate("AAAAAA")
    # with high deletion rate and homopolymer bias we expect length < input
    assert len(result) < 6
