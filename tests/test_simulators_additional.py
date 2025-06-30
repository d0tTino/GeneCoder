
from genecoder.simulators.illumina import IlluminaChannel, register as reg_illumina
from genecoder.simulators.adv_nanopore import AdvancedNanoporeChannel, register as reg_advnano
from genecoder.simulators.replication import ReplicationSimulator, register as reg_replication
from genecoder.simulators.transcription import TranscriptionSimulator, register as reg_transcription
from genecoder.simulators.translation import TranslationSimulator, register as reg_translation
from genecoder.simulators import BaseSimulator


def test_register_channels():
    from genecoder.channels.base import BaseChannel
    registry: dict[str, BaseChannel] = {}
    reg_illumina(lambda n, ch: registry.setdefault(n, ch))
    reg_advnano(lambda n, ch: registry.setdefault(n, ch))
    reg_replication(lambda n, ch: registry.setdefault(n, ch))
    reg_transcription(lambda n, ch: registry.setdefault(n, ch))
    reg_translation(lambda n, ch: registry.setdefault(n, ch))
    assert "illumina" in registry and isinstance(registry["illumina"], BaseSimulator)
    assert "adv_nanopore" in registry and isinstance(registry["adv_nanopore"], BaseSimulator)
    assert "replication" in registry and isinstance(registry["replication"], BaseSimulator)
    assert "transcription" in registry and isinstance(registry["transcription"], BaseSimulator)
    assert "translation" in registry and isinstance(registry["translation"], BaseSimulator)
    assert all(isinstance(ch, BaseChannel) for ch in registry.values())


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


def test_transcription_converts_to_rna():
    channel = TranscriptionSimulator(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.0)
    assert channel.simulate("ATCG") == "AUCG"


def test_translation_produces_peptide():
    channel = TranslationSimulator(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.0)
    assert channel.simulate("AUGGCUUAA") == "MA"


def test_replication_identity(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "3")
    channel = ReplicationSimulator(substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.0)
    assert channel.simulate("GGCC") == "GGCC"
