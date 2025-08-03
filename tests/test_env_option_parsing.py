import pytest

from genecoder.simulator_utils import _parse_env_options


def test_valid_options(monkeypatch):
    """Ensure valid flags and arguments parse correctly."""
    env_value = "--alpha beta --gamma=delta path/to/file:1"
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", env_value)
    assert _parse_env_options("d2sim") == [
        "--alpha",
        "beta",
        "--gamma=delta",
        "path/to/file:1",
    ]


def test_invalid_flag(monkeypatch):
    """Invalid flag patterns should raise ``ValueError``."""
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", "---badflag")
    with pytest.raises(ValueError):
        _parse_env_options("d2sim")


def test_invalid_argument(monkeypatch):
    """Arguments failing the regex are rejected."""
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", "foo=bar")
    with pytest.raises(ValueError):
        _parse_env_options("d2sim")


@pytest.mark.parametrize("env_value", ["--foo bar$", "foo;bar"])
def test_unsafe_characters(monkeypatch, env_value):
    """Unsafe characters trigger ``ValueError`` before regex checks."""
    monkeypatch.setenv("GENECODER_D2SIM_OPTIONS", env_value)
    with pytest.raises(ValueError):
        _parse_env_options("d2sim")
