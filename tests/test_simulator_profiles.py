from genecoder.simulators.illumina import IlluminaChannel, ILLUMINA_PROFILES
from genecoder.simulators.nanopore import NanoporeChannel, NANOPORE_PROFILES


def test_illumina_profiles() -> None:
    for name, params in ILLUMINA_PROFILES.items():
        ch = IlluminaChannel(**params)
        for key, value in params.items():
            assert getattr(ch, key) == value


def test_nanopore_profiles() -> None:
    for name, params in NANOPORE_PROFILES.items():
        ch = NanoporeChannel(**params)
        for key, value in params.items():
            assert getattr(ch, key) == value

