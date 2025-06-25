import pytest

from genecoder.simulators.illumina import IlluminaChannel
from genecoder.simulators.adv_nanopore import AdvancedNanoporeChannel
from genecoder.error_simulation import Channel as ErrorChannel


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize(
    "channel_cls,args,sequence",
    [
        (
            IlluminaChannel,
            dict(substitution_rate=0.5, insertion_rate=0.3, deletion_rate=0.2, read_length=6),
            "ACGTACGT",
        ),
        (
            AdvancedNanoporeChannel,
            dict(substitution_rate=0.5, insertion_rate=0.3, deletion_rate=0.2, read_length=6),
            "AAAAAA",
        ),
        (
            ErrorChannel,
            dict(substitution_prob=0.5, insertion_prob=0.3, deletion_prob=0.2),
            "ACGTACGT",
        ),
    ],
)
def test_reproducible_simulation(monkeypatch, channel_cls, args, sequence, seed):
    monkeypatch.setenv("GENECODER_SIM_SEED", str(seed))
    channel = channel_cls(**args)
    first = channel.simulate(sequence)
    monkeypatch.setenv("GENECODER_SIM_SEED", str(seed))
    channel = channel_cls(**args)
    second = channel.simulate(sequence)
    assert first == second
