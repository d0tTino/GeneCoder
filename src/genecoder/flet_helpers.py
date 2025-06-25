"""Helper utilities for the Flet GUI that do not depend on Flet itself.

These functions support the extensibility goals described in
`docs/DEVELOPMENT_VISION.md`.
"""

from __future__ import annotations


def parse_int_input(value: str | None, default: int, min_value: int = 1) -> int:
    """Parse ``value`` as an integer, enforcing a minimum.

    Parameters
    ----------
    value:
        Text from a GUI input field. ``None`` or an empty string results
        in ``default``.
    default:
        Value returned when parsing fails or ``value`` is empty/``None``.
    min_value:
        The minimum allowed integer value. Defaults to ``1``.

    Returns
    -------
    int
        The parsed integer if valid and >= ``min_value``; otherwise ``default``.
    """
    try:
        if value is None or value == "":
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if parsed < min_value:
        raise ValueError(f"Value must be >= {min_value}")

    return parsed
