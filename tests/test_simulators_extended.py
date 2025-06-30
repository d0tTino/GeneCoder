from genecoder.simulators.replication import ReplicationSimulator
from genecoder.simulators.translation import TranslationSimulator


def test_replication_substitutions(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "42")
    channel = ReplicationSimulator(
        substitution_rate=1.0, insertion_rate=0.0, deletion_rate=0.0
    )
    assert channel.simulate("AAAA") == "CGTG"


def test_replication_insertions(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "0")
    channel = ReplicationSimulator(
        substitution_rate=0.0, insertion_rate=1.0, deletion_rate=0.0
    )
    assert channel.simulate("AT") == "ACTC"


def test_replication_deletions(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    channel = ReplicationSimulator(
        substitution_rate=0.0, insertion_rate=0.0, deletion_rate=0.5
    )
    assert channel.simulate("ATGC") == "T"


def test_translation_stops_at_mutated_stop_codon(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "2")
    channel = TranslationSimulator(
        substitution_rate=1.0, insertion_rate=0.0, deletion_rate=0.0
    )
    assert channel.simulate("AUGGCUUAA") == ""


def test_translation_respects_error_injection(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "0")
    channel = TranslationSimulator(
        substitution_rate=0.0, insertion_rate=1.0, deletion_rate=0.0
    )
    assert channel.simulate("AUGGCUUAA") == "TRAFLQ"

