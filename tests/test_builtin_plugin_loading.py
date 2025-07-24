import pytest
import genecoder.plugins as plugins


def test_load_builtin_plugins_populates_registries() -> None:
    plugins.CODEC_REGISTRY.clear()
    plugins.FEC_REGISTRY.clear()
    plugins.SIMULATOR_REGISTRY.clear()

    plugins.load_plugins()

    assert {"reverse", "chamaeleo_gc"} <= set(plugins.CODEC_REGISTRY)
    assert {
        "reed_solomon",
        "ldpc",
        "fountain",
        "bch",
        "raptorq",
        "framed",
    } <= set(plugins.FEC_REGISTRY)

    sim_names = {
        "d2sim",
        "dnarsim",
        "squigulator",
        "desp",
        "insilicoseq",
        "nanopore",
        "none",
        "simple",
        "indel",
        "illumina",
        "illumina_d2sim",
        "illumina_insilicoseq",
        "nanopore_d2sim",
        "nanopore_desp",
    }
    assert sim_names <= set(plugins.SIMULATOR_REGISTRY)


def test_register_requires_subclass_via_alias() -> None:
    with pytest.raises(TypeError):
        plugins.register_codec("bad", object())
    with pytest.raises(TypeError):
        plugins.register_fec("bad", object())
    with pytest.raises(TypeError):
        plugins.register_simulator("bad", object())
