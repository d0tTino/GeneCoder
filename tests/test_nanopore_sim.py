import pytest

from genecoder import nanopore_sim

SIMULATORS = {
    "nanopore": "d2sim",
    "dnarsim": "dnarsim",
    "squigulator": "squigulator",
}


@pytest.mark.parametrize("simulator", SIMULATORS.keys())
def test_simulate_reads_runs_external(monkeypatch, simulator):
    cmd = SIMULATORS[simulator]
    which_called = []
    run_called = []

    def fake_which(name):
        which_called.append(name)
        return "/usr/bin/" + name

    def fake_run_external(command, seq):
        run_called.append((command, seq))
        return "external"

    monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run_external)

    result = nanopore_sim.simulate_reads("ACGT", simulator)
    assert result == "external"
    assert which_called == [cmd]
    assert run_called == [(cmd, "ACGT")]


@pytest.mark.parametrize("simulator", SIMULATORS.keys())
def test_simulate_reads_falls_back(monkeypatch, simulator):
    cmd = SIMULATORS[simulator]
    which_called: list[str] = []
    errors_called: list[tuple[str, float]] = []
    external_called: list[tuple[str, str]] = []

    def fake_which(name: str) -> None:
        which_called.append(name)
        return None

    def fake_errors(seq: str, rate: float) -> str:
        errors_called.append((seq, rate))
        return "fallback"

    def fake_external(command: str, seq: str) -> str:
        external_called.append((command, seq))
        return "should not be used"

    monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
    monkeypatch.setattr(nanopore_sim, "simulate_errors", fake_errors)
    monkeypatch.setattr(nanopore_sim, "_run_external", fake_external)

    result = nanopore_sim.simulate_reads("ACGT", simulator, error_rate=0.1)
    assert result == "fallback"
    assert which_called == [cmd]
    assert errors_called == [("ACGT", 0.1)]
    assert external_called == []


def test_simulate_reads_none(monkeypatch):
    call_count = []

    def fake_which(name: str) -> str:
        call_count.append(name)
        return "/usr/bin/" + name

    monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
    monkeypatch.setattr(nanopore_sim, "_run_external", lambda *_: "boom")

    result = nanopore_sim.simulate_reads("ACGT", "none")
    assert result == "ACGT"
    assert call_count == []
