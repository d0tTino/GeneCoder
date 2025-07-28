import pytest

from genecoder import d2sim_adapter, desp_adapter, insilicoseq_adapter, nanopore_sim

ADAPTERS = {
    "d2sim": d2sim_adapter.simulate_d2sim,
    "desp": desp_adapter.simulate_desp,
    "insilicoseq": insilicoseq_adapter.simulate_insilicoseq,
}


@pytest.mark.parametrize("name", ADAPTERS.keys())
def test_simulate_adapters_use_run_external(monkeypatch, name):
    func = ADAPTERS[name]
    which_called = []
    run_called = []

    def fake_which(target: str) -> str:
        which_called.append(target)
        return "/usr/bin/" + target

    def fake_run(cmd, seq):
        run_called.append((cmd, seq))
        return f"{name}-result"

    monkeypatch.setattr(nanopore_sim.shutil, "which", fake_which)
    monkeypatch.setattr(nanopore_sim, "_run_external", fake_run)

    result = func("ACGT")
    assert result == f"{name}-result"
    assert which_called == [name]
    assert run_called == [([name, "-e", "0.05"], "ACGT")]

