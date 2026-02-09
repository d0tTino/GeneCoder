from __future__ import annotations

"""Helpers for normalizing boolean-like values across GeneCoder surfaces."""


def parse_bool_like(value: object) -> bool | None:
    """Return a normalized bool for common JSON forms, else ``None``.

    Recognizes native booleans, numeric values, and common string literals.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        try:
            return float(value) != 0.0
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None
