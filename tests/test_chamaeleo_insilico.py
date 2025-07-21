import genecoder.plugin_manager as plugins
from genecoder.simulators import SIMULATOR_REGISTRY
import pytest


def test_chamaeleo_insilico_roundtrip():
    pytest.importorskip("Chamaeleo")
    pytest.importorskip("iss")
    plugins.CODEC_REGISTRY.clear()
    SIMULATOR_REGISTRY.clear()
    plugins.load_builtin_plugins()

    assert 'chamaeleo_gc' in plugins.CODEC_REGISTRY
    assert 'insilicoseq' in SIMULATOR_REGISTRY

    encode = plugins.CODEC_REGISTRY['chamaeleo_gc']['encode']
    decode = plugins.CODEC_REGISTRY['chamaeleo_gc']['decode']
    simulator = SIMULATOR_REGISTRY['insilicoseq']

    data = b'hello world'
    dna = encode(data)
    dna_sim = simulator.simulate(dna)
    result = decode(dna_sim)
    assert result == data
