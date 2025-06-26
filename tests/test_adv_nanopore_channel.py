from genecoder.simulators.adv_nanopore import AdvancedNanoporeChannel


def test_adv_nanopore_deterministic(monkeypatch):
    monkeypatch.setenv('GENECODER_SIM_SEED', '1')
    channel = AdvancedNanoporeChannel(
        substitution_rate=0.5,
        insertion_rate=0.0,
        deletion_rate=0.0,
        read_length=10,
    )
    result = channel.simulate('ACGTACGTAC')
    assert result == 'ATTAAAGAAC'


def test_adv_nanopore_indel_variation(monkeypatch):
    monkeypatch.setenv('GENECODER_SIM_SEED', '2')
    channel = AdvancedNanoporeChannel(
        substitution_rate=0.0,
        insertion_rate=0.2,
        deletion_rate=0.2,
        read_length=10,
    )
    result = channel.simulate('AAAAAAAAAA')
    assert len(result) != 10

