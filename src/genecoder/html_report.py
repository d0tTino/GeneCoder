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


def _format_numeric(value: int | float) -> str:
    """Return a user-friendly string for numeric values."""

    if isinstance(value, bool):  # bool is a subclass of int, handle explicitly
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def generate_html_report(manifest_path: str) -> str:
    """Return HTML summary for the manifest at ``manifest_path``."""
    with open(manifest_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    metrics = data.get("metrics", data)
    html_lines: list[str] = ["<html>", "<body>", "<h1>GeneCoder Summary Report</h1>"]

    gc_content = metrics.get("gc_content")
    if isinstance(gc_content, (int, float)):
        html_lines.append(
            f"<p><strong>GC Mean:</strong> {float(gc_content) * 100:.2f}%</p>"
        )
    gc_variance = metrics.get("gc_variance")
    if isinstance(gc_variance, (int, float)):
        html_lines.append(
            f"<p><strong>GC Variance:</strong> {float(gc_variance):.4f}</p>"
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

    error_metrics: list[tuple[str, str]] = [
        ("substitutions", "Substitutions"),
        ("insertions", "Insertions"),
        ("deletions", "Deletions"),
    ]
    error_lines: list[str] = []
    for key, label in error_metrics:
        value = metrics.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            error_lines.append(
                f"<li><strong>{label}:</strong> {_format_numeric(value)}</li>"
            )

    coverage = metrics.get("coverage")
    if isinstance(coverage, (int, float)) and not isinstance(coverage, bool):
        error_lines.append(
            f"<li><strong>Coverage:</strong> {_format_numeric(coverage)}</li>"
        )

    if error_lines:
        html_lines.append("<h2>Error Metrics</h2>")
        html_lines.append("<ul>")
        html_lines.extend(error_lines)
        html_lines.append("</ul>")

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
