
from genecoder.simulators.illumina import IlluminaChannel
from genecoder import nanopore_sim


def test_illumina_high_insertion(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    channel = IlluminaChannel(
        substitution_rate=0.0,
        insertion_rate=1.0,
        deletion_rate=0.0,
        read_length=4,
    )
    result = channel.simulate("ACGTACGT")
    assert len(result) == 8
    assert result[::2] == "ACGT"


def test_nanopore_high_error_rate(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "2")
    monkeypatch.setattr(nanopore_sim.shutil, "which", lambda _: None)
    result = nanopore_sim.simulate_d2sim("AAAA", error_rate=1.0)
    assert len(result) == 4
    assert set(result) <= {"A", "C", "G", "T"}
    assert "A" not in result
