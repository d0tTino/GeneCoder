"""Minimal YAML compatibility layer for environments without PyYAML.

This module provides ``safe_load`` and ``safe_dump`` helpers that handle the
subset of YAML used by GeneCoder configuration files. It supports nested
mapping/list structures and scalar coercion, and falls back to JSON parsing when
appropriate.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable, Iterator, List, Tuple


class YAMLError(Exception):
    """Fallback YAML error used when PyYAML is unavailable."""


_TRUE_VALUES = {"true", "yes", "on"}
_FALSE_VALUES = {"false", "no", "off"}
_NULL_VALUES = {"null", "none", "~"}


@dataclass(frozen=True)
class _Line:
    indent: int
    content: str


def _iter_lines(text: str) -> Iterator[_Line]:
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue
        indent = len(raw) - len(stripped)
        yield _Line(indent, stripped)


def _strip_inline_comment(value: str) -> str:
    if "#" not in value:
        return value
    in_quotes = False
    quote_char = ""
    for idx, char in enumerate(value):
        if char in {"'", '"'}:
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif quote_char == char:
                in_quotes = False
        if char == "#" and not in_quotes:
            return value[:idx].rstrip()
    return value


def _coerce_scalar(value: str) -> object:
    cleaned = _strip_inline_comment(value).strip()
    if not cleaned:
        return ""
    if cleaned.startswith("[") and not cleaned.endswith("]"):
        raise YAMLError("Invalid YAML: unmatched '['")
    if cleaned.startswith("{") and not cleaned.endswith("}"):
        raise YAMLError("Invalid YAML: unmatched '{'")
    lower = cleaned.lower()
    if lower in _NULL_VALUES:
        return None
    if lower in _TRUE_VALUES:
        return True
    if lower in _FALSE_VALUES:
        return False
    if cleaned.startswith(("'", '"')) and cleaned.endswith(("'", '"')) and len(cleaned) >= 2:
        return cleaned[1:-1]
    try:
        if cleaned.startswith("0x"):
            return int(cleaned, 16)
        if cleaned.startswith("0o"):
            return int(cleaned, 8)
        if cleaned.startswith("0b"):
            return int(cleaned, 2)
    except ValueError:
        pass
    try:
        if any(ch in cleaned for ch in ".eE"):
            return float(cleaned)
        return int(cleaned, 10)
    except ValueError:
        return cleaned


def _is_list_item(content: str) -> bool:
    return content == "-" or content.startswith("- ")


def _parse_block(lines: List[_Line], start: int, indent: int) -> Tuple[object, int]:
    if start >= len(lines):
        return {}, start
    if lines[start].indent < indent:
        return {}, start

    is_list = _is_list_item(lines[start].content)
    if is_list:
        items: List[object] = []
        index = start
        while index < len(lines):
            line = lines[index]
            if line.indent < indent or not _is_list_item(line.content):
                break
            if line.indent > indent:
                break
            item_content = line.content[1:].strip()
            if not item_content:
                item, index = _parse_block(lines, index + 1, indent + 2)
                items.append(item)
                continue
            if ":" in item_content:
                key, _, remainder = item_content.partition(":")
                key = key.strip()
                remainder = remainder.strip()
                item_map: dict[str, object] = {}
                if remainder:
                    item_map[key] = _coerce_scalar(remainder)
                    index += 1
                    if index < len(lines) and lines[index].indent > indent:
                        extra, next_index = _parse_block(lines, index, indent + 2)
                        if isinstance(extra, dict):
                            item_map.update(extra)
                        index = next_index
                    items.append(item_map)
                else:
                    nested, next_index = _parse_block(lines, index + 1, indent + 2)
                    item_map[key] = nested
                    items.append(item_map)
                    index = next_index
            else:
                items.append(_coerce_scalar(item_content))
                index += 1
        return items, index

    mapping: dict[str, object] = {}
    index = start
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            break
        key, sep, remainder = line.content.partition(":")
        if not sep:
            index += 1
            continue
        key = key.strip()
        remainder = remainder.strip()
        if remainder:
            mapping[key] = _coerce_scalar(remainder)
            index += 1
            continue
        nested, next_index = _parse_block(lines, index + 1, indent + 2)
        mapping[key] = nested
        index = next_index
    return mapping, index


def _has_unbalanced_brackets(text: str) -> bool:
    stack: list[str] = []
    in_quotes = False
    quote_char = ""
    for char in text:
        if char in {"'", '"'}:
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif quote_char == char:
                in_quotes = False
        if in_quotes:
            continue
        if char in {"[", "{"}:
            stack.append(char)
        elif char in {"]", "}"}:
            if not stack:
                return True
            opener = stack.pop()
            if (opener == "[" and char != "]") or (opener == "{" and char != "}"):
                return True
    return bool(stack)


def safe_load(stream: object) -> object:
    if hasattr(stream, "read"):
        text = stream.read()
    else:
        text = str(stream)
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    if _has_unbalanced_brackets(text):
        raise YAMLError("Invalid YAML: unbalanced brackets")
    lines = list(_iter_lines(text))
    if not lines:
        return {}
    parsed, _ = _parse_block(lines, 0, lines[0].indent)
    return parsed


def _dump_mapping(mapping: dict[str, object], indent: int, lines: List[str]) -> None:
    pad = " " * indent
    for key, value in mapping.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            _dump_mapping(value, indent + 2, lines)
        elif isinstance(value, list):
            lines.append(f"{pad}{key}:")
            _dump_list(value, indent + 2, lines)
        else:
            lines.append(f"{pad}{key}: {_format_scalar(value)}")


def _dump_list(items: Iterable[object], indent: int, lines: List[str]) -> None:
    pad = " " * indent
    for item in items:
        if isinstance(item, dict):
            lines.append(f"{pad}-")
            _dump_mapping(item, indent + 2, lines)
        elif isinstance(item, list):
            lines.append(f"{pad}-")
            _dump_list(item, indent + 2, lines)
        else:
            lines.append(f"{pad}- {_format_scalar(item)}")


def _format_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text or any(ch.isspace() for ch in text) or text.startswith(("#", "-", ":")):
        return json.dumps(text)
    return text


def safe_dump(
    data: object,
    stream: object | None = None,
    sort_keys: bool = True,
) -> str | None:
    if isinstance(stream, bool):
        sort_keys = stream
        stream = None
    if isinstance(data, dict):
        items = dict(sorted(data.items())) if sort_keys else data
        lines: List[str] = []
        _dump_mapping(items, 0, lines)
        output = "\n".join(lines) + ("\n" if lines else "")
    elif isinstance(data, list):
        lines = []
        _dump_list(data, 0, lines)
        output = "\n".join(lines) + ("\n" if lines else "")
    else:
        output = f"{_format_scalar(data)}\n"
    if stream is not None and hasattr(stream, "write"):
        stream.write(output)
        return None
    return output
