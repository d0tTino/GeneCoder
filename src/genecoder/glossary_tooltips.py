"""Utilities for adding glossary tooltips to Flet controls."""

from __future__ import annotations

from pathlib import Path
import json
import logging
import re
from typing import Dict, List, cast

import flet as ft


_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "docs" / "glossary.json"
_GLOSSARY_MD_PATH = Path(__file__).resolve().parent.parent / "docs" / "glossary.md"


def load_glossary() -> Dict[str, str]:
    """Load glossary terms from the project's ``glossary.json`` file."""
    try:
        with open(_GLOSSARY_PATH, "r", encoding="utf-8") as f:
            return cast(Dict[str, str], json.load(f))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logging.warning("Could not load glossary file %s: %s", _GLOSSARY_PATH, exc)
        return {}


def load_glossary_full() -> Dict[str, str]:
    """Load full glossary definitions from ``glossary.md``."""
    terms: Dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    with open(_GLOSSARY_MD_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                if current:
                    terms[current] = " ".join(buffer).strip()
                current = line[3:].strip()
                buffer = []
            elif current:
                buffer.append(line.strip())
        if current:
            terms[current] = " ".join(buffer).strip()
    return terms


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


def glossary_modal_text(
    term: str,
    page: ft.Page,
    glossary: Dict[str, str],
    full_defs: Dict[str, str],
) -> ft.Text:
    """Return clickable text that opens a modal showing the term definition."""

    tooltip = glossary.get(term, "")
    full_text = full_defs.get(term, tooltip)
    dialog = ft.AlertDialog(title=ft.Text(term), content=ft.Text(full_text), modal=True)

    def _open_dialog(_: ft.ControlEvent) -> None:
        page.dialog = dialog
        dialog.open = True
        page.update()

    text_ctrl = ft.Text(
        term,
        tooltip=tooltip,
        style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
        color=ft.colors.BLUE_500,
    )
    text_ctrl.on_click = _open_dialog
    return text_ctrl
