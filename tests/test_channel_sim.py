import random

from genecoder.error_simulation import simulate_errors
from genecoder.simulators import simulate_reads
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.error_correction import encode_triple_repeat, decode_triple_repeat
from genecoder.error_simulation import register as register_error_sim
from genecoder.channel_config import ChannelConfig
from genecoder.simulators.pipeline import ChannelPipeline
import genecoder.dnarsim_adapter as dnarsim_adapter


def test_simulate_errors_deterministic():
    rng = random.Random(0)
    assert simulate_errors("AAAA", substitution_prob=1.0, rng=rng) == "CCTG"


def test_decode_recovery_with_triple_repeat(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    register_error_sim()
    data = b"hello"
    dna = encode_base4_direct(data)
    dna_tr = encode_triple_repeat(dna)
    corrupted = simulate_reads(dna_tr, "simple", error_rate=0.05)
    corrected, _, _ = decode_triple_repeat(corrupted)
    recovered, _ = decode_base4_direct(corrected)
    assert recovered == data


def test_pipeline_profile_application(monkeypatch):
    called_profiles: list[str | None] = []

    def fake_sim(seq: str, error_rate: float = 0.05, rng=None, profile: str | None = None) -> str:
        called_profiles.append(profile)
        return seq

    monkeypatch.setattr(dnarsim_adapter, "simulate_dnarsim", fake_sim)

    with_calls: list[str] = []

    def fake_with_profile(self, profile: str):
        with_calls.append(profile)
        self.profile = profile
        return self

    monkeypatch.setattr(dnarsim_adapter.DNArSimChannel, "with_profile", fake_with_profile)

    pipeline = ChannelPipeline([dnarsim_adapter.DNArSimChannel()])
    config = ChannelConfig(nanopore_profile="r9")
    pipeline.simulate("ACGT", config=config)

    assert with_calls == ["r9"]
    assert called_profiles == ["r9"]
