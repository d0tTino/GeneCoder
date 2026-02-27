from genecoder.runtime import make_run_context


def test_run_context_uses_env_fallback(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "101")
    ctx = make_run_context()
    assert ctx.global_seed == 101
    assert ctx.simulate_seed == 103
    assert ctx.seed_source == "env_fallback"


def test_run_context_explicit_seed_precedence(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "101")
    ctx = make_run_context(global_seed=7, simulate_seed=9)
    assert ctx.global_seed == 7
    assert ctx.simulate_seed == 9
    assert ctx.seed_source == "explicit"
