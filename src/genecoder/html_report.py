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


def _summarize(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return (float("nan"),) * 3
    sorted_vals = sorted(values)
    mean_val = sum(values) / len(values)
    return sorted_vals[0], mean_val, sorted_vals[-1]


def _render_oligo_section(metrics: dict[str, Any], html_lines: list[str]) -> None:
    oligo = metrics.get("oligo_metrics")
    if not isinstance(oligo, dict):
        return
    gc_vals = [float(v) for v in oligo.get("gc_percentages", []) if isinstance(v, (int, float))]
    hp_vals = [float(v) for v in oligo.get("max_homopolymers", []) if isinstance(v, (int, float))]
    dropout_flags = [flag for flag in oligo.get("dropout_flags", []) if isinstance(flag, bool)]
    ecc = oligo.get("ecc_success")

    if not (gc_vals or hp_vals or dropout_flags or ecc):
        return

    html_lines.append("<h2>Per-oligo Metrics</h2>")
    html_lines.append("<ul>")
    if gc_vals:
        min_gc, mean_gc, max_gc = _summarize(gc_vals)
        html_lines.append(
            "<li><strong>GC%:</strong> min {0:.2%}, mean {1:.2%}, max {2:.2%}</li>".format(
                min_gc, mean_gc, max_gc
            )
        )
    if hp_vals:
        min_hp, mean_hp, max_hp = _summarize(hp_vals)
        html_lines.append(
            "<li><strong>Max Homopolymer:</strong> min {0:.0f}, mean {1:.1f}, max {2:.0f}</li>".format(
                min_hp,
                mean_hp,
                max_hp,
            )
        )
    if dropout_flags:
        total = len(dropout_flags)
        dropped = sum(1 for flag in dropout_flags if flag)
        html_lines.append(
            f"<li><strong>Dropouts:</strong> {dropped} of {total} oligos ({(dropped / total) * 100:.2f}%)</li>"
        )
    if isinstance(ecc, dict) and ecc:
        html_lines.append("<li><strong>ECC Success:</strong><ul>")
        for name, values in ecc.items():
            if not isinstance(values, list):
                continue
            filtered = [float(v) for v in values if isinstance(v, (int, float))]
            if not filtered:
                continue
            _, mean_val, _ = _summarize(filtered)
            html_lines.append(
                f"<li>{escape(str(name))}: mean {(mean_val * 100):.2f}%</li>"
            )
        html_lines.append("</ul></li>")
    html_lines.append("</ul>")


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

    error_metrics: list[tuple[str, str, str]] = [
        ("substitutions", "substitution_rate", "Substitutions"),
        ("insertions", "insertion_rate", "Insertions"),
        ("deletions", "deletion_rate", "Deletions"),
    ]
    error_lines: list[str] = []
    for count_key, rate_key, label in error_metrics:
        count_value = metrics.get(count_key)
        rate_value = metrics.get(rate_key)
        line_parts: list[str] = []
        if isinstance(count_value, (int, float)) and not isinstance(count_value, bool):
            line_parts.append(f"count {_format_numeric(count_value)}")
        if isinstance(rate_value, (int, float)) and not isinstance(rate_value, bool):
            line_parts.append(f"rate {float(rate_value):.4%}")
        if line_parts:
            error_lines.append(
                f"<li><strong>{label}:</strong> {'; '.join(line_parts)}</li>"
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

    _render_oligo_section(metrics, html_lines)

    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)
