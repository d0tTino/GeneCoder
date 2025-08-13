import pytest

from genecoder.simulators import SIMULATOR_REGISTRY, simulate_reads
from genecoder.simulators.illumina import IlluminaChannel, register as illumina_register


def test_illumina_registered_and_deterministic(monkeypatch):
    assert "illumina" in SIMULATOR_REGISTRY
    seq = "A" * 50
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    first = simulate_reads(seq, "illumina")
    monkeypatch.setenv("GENECODER_SIM_SEED", "123")
    second = simulate_reads(seq, "illumina")
    assert first == second
    assert isinstance(first, str)


def test_simulate_reads_profile_validation(monkeypatch):
    illumina_register()
    called: list[str] = []

    orig = IlluminaChannel.with_profile

    def fake_with_profile(self: IlluminaChannel, profile: str):
        called.append(profile)
        return orig(self, profile)

    monkeypatch.setattr(IlluminaChannel, "with_profile", fake_with_profile)

    simulate_reads("ACGT", "illumina", profile="miseq")
    assert called == ["miseq"]

    with pytest.raises(ValueError, match="Unknown Illumina profile"):
        simulate_reads("ACGT", "illumina", profile="unknown")

