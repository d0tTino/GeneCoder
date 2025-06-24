from __future__ import annotations

from html import escape
from typing import Iterable

from .app_helpers import EncodeResult, DecodeResult

__all__ = [
    "encode_to_markdown",
    "decode_to_markdown",
    "encode_to_html",
    "decode_to_html",
]


def _metric_lines(metrics: dict[str, float]) -> Iterable[str]:
    for key, value in metrics.items():
        yield f"- **{key}**: {value}"


def encode_to_markdown(result: EncodeResult) -> str:
    lines: list[str] = ["# Encoding Report", "", "## Metrics"]
    lines.extend(_metric_lines(result.metrics))
    if result.info_messages:
        lines.append("")
        lines.append("## Info Messages")
        lines.extend(f"- {m}" for m in result.info_messages)
    return "\n".join(lines)


def decode_to_markdown(result: DecodeResult) -> str:
    lines: list[str] = ["# Decoding Report", "", f"**Status:** {result.status_message}"]
    if result.fec_info:
        lines.append("")
        lines.append(f"**FEC Info:** {result.fec_info}")
    return "\n".join(lines)


def encode_to_html(result: EncodeResult) -> str:
    return _markdown_to_html(encode_to_markdown(result))


def decode_to_html(result: DecodeResult) -> str:
    return _markdown_to_html(decode_to_markdown(result))


def _markdown_to_html(markdown: str) -> str:
    html_lines: list[str] = []
    in_ul = False
    for line in markdown.splitlines():
        if line.startswith("# "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h1>{escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h2>{escape(line[3:].strip())}</h2>")
        elif line.startswith("- "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{escape(line[2:].strip())}</li>")
        elif line == "":
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<p>{escape(line)}</p>")
    if in_ul:
        html_lines.append("</ul>")
    return "\n".join(html_lines)
