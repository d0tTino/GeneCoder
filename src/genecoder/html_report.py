from __future__ import annotations

"""Simple HTML summary generation for manifest metrics."""

from html import escape
import json
from typing import Any

__all__ = ["generate_html_report"]


def _calc_decode_success(data: dict[str, Any]) -> float | None:
    rate = data.get("decode_success_rate")
    if isinstance(rate, (int, float)):
        return float(rate)
    ecc = data.get("ecc_success_rates")
    if isinstance(ecc, dict) and ecc:
        values = []
        for val in ecc.values():
            try:
                values.append(float(val))
            except Exception:
                pass
        if values:
            return sum(values) / len(values)
    return None


def generate_html_report(manifest_path: str) -> str:
    """Return HTML summary for the manifest at ``manifest_path``."""
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    metrics = data.get("metrics", data)
    html_lines: list[str] = ["<html>", "<body>", "<h1>GeneCoder Summary Report</h1>"]

    gc_content = metrics.get("gc_content")
    if isinstance(gc_content, (int, float)):
        html_lines.append(
            f"<p><strong>GC Content:</strong> {float(gc_content) * 100:.2f}%</p>"
        )

    max_hp: int | float | None = metrics.get("max_homopolymer")
    if not isinstance(max_hp, (int, float)):
        hp_runs = metrics.get("homopolymer_runs")
        if isinstance(hp_runs, list) and hp_runs:
            max_hp = len(hp_runs) - 1
    if isinstance(max_hp, (int, float)):
        html_lines.append(
            f"<p><strong>Max Homopolymer Length:</strong> {int(max_hp)}</p>"
        )

    ecc = metrics.get("ecc_success_rates")
    if isinstance(ecc, dict) and ecc:
        html_lines.append("<h2>ECC Success Rates</h2>")
        html_lines.append("<ul>")
        for name, val in ecc.items():
            try:
                value = float(val) * 100
                html_lines.append(
                    f"<li>{escape(str(name))}: {value:.2f}%</li>"
                )
            except Exception:
                pass
        html_lines.append("</ul>")

    decode_rate = _calc_decode_success(metrics)
    if decode_rate is not None:
        html_lines.append(
            f"<p><strong>Overall Decode Success:</strong> {decode_rate * 100:.2f}%</p>"
        )

    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)
