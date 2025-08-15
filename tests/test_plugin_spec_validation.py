"""Tests for plugin specification sanitization.

Safe specifications are limited to simple package names composed of letters,
digits, underscores, periods, or dashes (``^[A-Za-z0-9_.-]+$``) or to HTTP,
HTTPS, or file URLs containing only standard URL-safe characters.
"""

import pytest

from genecoder.plugin_manager import _validate_spec


@pytest.mark.parametrize(
    "spec",
    [
        "package name",
        "package\tname",
        "package\nname",
    ],
)
def test_validate_spec_rejects_whitespace(spec: str) -> None:
    """Whitespace should render a plugin spec unsafe."""
    with pytest.raises(ValueError):
        _validate_spec(spec)


@pytest.mark.parametrize(
    "spec",
    [
        "package;",
        "package&",
        "package|",
        "package$",
        "package<",
        "package>",
    ],
)
def test_validate_spec_rejects_shell_metacharacters(spec: str) -> None:
    """Shell metacharacters should render a plugin spec unsafe."""
    with pytest.raises(ValueError):
        _validate_spec(spec)


@pytest.mark.parametrize(
    "spec",
    [
        "../package",
        "..\\package",
        "package/../evil",
    ],
)
def test_validate_spec_rejects_path_traversal(spec: str) -> None:
    """Path traversal attempts should be rejected."""
    with pytest.raises(ValueError):
        _validate_spec(spec)
