from genecoder.simulators import SIMULATOR_REGISTRY, simulate_reads
from genecoder.simulators.illumina import register as illumina_register


def test_illumina_profile_alias_matches_canonical(monkeypatch) -> None:
    SIMULATOR_REGISTRY.clear()
    illumina_register()
    assert "illumina" in SIMULATOR_REGISTRY
    assert "illumina_builtin" in SIMULATOR_REGISTRY

    sequence = "ACGT" * 25
    monkeypatch.setenv("GENECODER_SIM_SEED", "2024")
    legacy = simulate_reads(sequence, "illumina_builtin", profile="hiseq")
    monkeypatch.setenv("GENECODER_SIM_SEED", "2024")
    canonical = simulate_reads(sequence, "illumina", profile="hiseq")
    assert legacy == canonical
