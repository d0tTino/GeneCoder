from genecoder.simulators.illumina_profile import IlluminaProfileChannel


def test_quality_profile_influences_errors(monkeypatch):
    monkeypatch.setenv("GENECODER_SIM_SEED", "1")
    channel = IlluminaProfileChannel(
        substitution_rate=0.0,
        insertion_rate=0.0,
        deletion_rate=0.0,
        read_length=4,
        quality_profile=[0, 40, 0, 40],
    )
    result = channel.simulate("ATCG")
    # Low quality positions should mutate
    assert result[0] != "A" and result[2] != "C"
    # High quality bases remain unchanged
    assert result[1] == "T" and result[3] == "G"
