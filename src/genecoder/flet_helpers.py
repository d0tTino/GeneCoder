"""Helper utilities for the Flet GUI that do not depend on Flet itself."""

from __future__ import annotations


def parse_int_input(value: str | None, default: int, min_value: int = 1) -> int:
    """Parse ``value`` as an integer, enforcing a minimum.

    Parameters
    ----------
    value:
        Text from a GUI input field. ``None`` or an empty string results
        in ``default``.
    default:
        Value returned when parsing fails or the parsed value is less than
        ``min_value``.
    min_value:
        The minimum allowed integer value. Defaults to ``1``.

    Returns
    -------
    int
        The parsed integer if valid and >= ``min_value``; otherwise ``default``.
    """
    try:
        if value is not None and value != "":
            parsed = int(value)
        else:
            parsed = default
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= min_value else default
