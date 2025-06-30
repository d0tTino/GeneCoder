"""Utilities for adding glossary tooltips to Flet controls."""

from __future__ import annotations

from pathlib import Path
import json
import logging
import re
from typing import Dict, List, cast

import flet as ft


_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "docs" / "glossary.json"


def load_glossary() -> Dict[str, str]:
    """Load glossary terms from the project's ``glossary.json`` file."""
    try:
        with open(_GLOSSARY_PATH, "r", encoding="utf-8") as f:
            return cast(Dict[str, str], json.load(f))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logging.warning("Could not load glossary file %s: %s", _GLOSSARY_PATH, exc)
        return {}


def wrap_glossary_terms(text: str, glossary: Dict[str, str]) -> ft.Row:
    """Wrap glossary terms in ``text`` with :class:`~flet.Tooltip` widgets."""
    if not glossary:
        return ft.Row([ft.Text(text)], spacing=0, wrap=True)

    # Build regex matching any glossary term, preferring longer terms first
    pattern = re.compile(
        "|".join(re.escape(t) for t in sorted(glossary, key=len, reverse=True))
    )

    controls: List[ft.Control] = []
    last = 0
    for match in pattern.finditer(text):
        if match.start() > last:
            controls.append(ft.Text(text[last : match.start()]))
        term = match.group(0)
        message = glossary.get(term, "")
        controls.append(ft.Text(term, tooltip=message))
        last = match.end()

    if last < len(text):
        controls.append(ft.Text(text[last:]))

    return ft.Row(controls, spacing=0, wrap=True)
