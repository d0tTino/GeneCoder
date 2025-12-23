import pytest

from genecoder.constraint_fixer import fix_sequence
from genecoder.random_utils import reset_rng
from genecoder.encoders import encode_base4_direct, decode_base4_direct
from genecoder.simulators.illumina import IlluminaChannel

import genecoder.simulators.nanopore as nanopore
import genecoder.simulators.nanopore_external as nanopore_external


def _nanopore_profile() -> nanopore.NanoporeChannel:
    channel = nanopore.NanoporeChannel(profile="minion")
    channel.error_rate = 0.0
    channel.substitution_rate = 0.1
    channel.insertion_rate = 0.0
    channel.deletion_rate = 0.0
    channel.insertion_profile = {}
    channel.deletion_profile = {}
    channel.context_errors = {}
    channel.context_insertions = {}
    channel.context_deletions = {}
    return channel


def _noop_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    return None


def _nanopore_patch(monkeypatch: pytest.MonkeyPatch) -> None:

    def fallback(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("fallback")

    monkeypatch.setattr(nanopore_external, "run_dnarsim_cli", fallback)
    monkeypatch.setattr(nanopore, "run_dnarsim_cli", fallback)


@pytest.mark.parametrize(
    "channel_factory, patch",
    [
        (
            lambda: IlluminaChannel(
                profile="miseq",
                substitution_rate=0.1,
                insertion_rate=0.0,
                deletion_rate=0.0,
            ),
            _noop_patch,
        ),
        (lambda: _nanopore_profile(), _nanopore_patch),
    ],
)
def test_seeded_pipeline(monkeypatch: pytest.MonkeyPatch, channel_factory, patch) -> None:
    data = b"\x00" * 8
    patch(monkeypatch)

    def run() -> bytes:
        monkeypatch.setenv("GENECODER_SIM_SEED", "123")
        reset_rng()
        dna = encode_base4_direct(data)
        dna = fix_sequence(dna, target_gc_min=0.4, target_gc_max=0.6, max_homopolymer=3)
        channel = channel_factory()
        mutated = channel.simulate(dna)
        decoded, _ = decode_base4_direct(mutated)
        return decoded

    out1 = run()
    out2 = run()
    assert out1 == out2
