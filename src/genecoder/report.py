from __future__ import annotations

from html import escape
from typing import Iterable, List, Dict, Mapping, Any
import io

from .plotting import plt, _MATPLOTLIB_AVAILABLE, _dummy_png

from .app_helpers import EncodeResult, DecodeResult
from .results.schema import RUN_SCHEMA_VERSION

__all__ = [
    "encode_to_markdown",
    "decode_to_markdown",
    "encode_to_html",
    "decode_to_html",
    "plot_fec_benchmark",
    "plot_fec_success",
]


def _metric_lines(metrics: dict[str, float]) -> Iterable[str]:
    for key, value in metrics.items():
        yield f"- **{key}**: {value}"


def _oligo_metric_lines(metrics: Mapping[str, Any]) -> list[str]:
    oligo = metrics.get("oligo_metrics") if isinstance(metrics, Mapping) else None
    if not isinstance(oligo, Mapping):
        return []

    lines: list[str] = []
    gc_vals = [float(v) for v in oligo.get("gc_percentages", []) if isinstance(v, (int, float))]
    hp_vals = [float(v) for v in oligo.get("max_homopolymers", []) if isinstance(v, (int, float))]
    dropout_flags = [flag for flag in oligo.get("dropout_flags", []) if isinstance(flag, bool)]
    ecc = oligo.get("ecc_success") if isinstance(oligo.get("ecc_success"), Mapping) else {}

    def summarize(values: list[float]) -> tuple[str, str, str]:
        if not values:
            return ("n/a", "n/a", "n/a")
        sorted_vals = sorted(values)
        mean_val = sum(values) / len(values)
        return (
            f"{sorted_vals[0]:.2f}",
            f"{mean_val:.2f}",
            f"{sorted_vals[-1]:.2f}",
        )

    if gc_vals:
        mn, mean, mx = summarize(gc_vals)
        lines.append(f"- **Per-oligo GC%**: min {mn}, mean {mean}, max {mx}")
    if hp_vals:
        mn, mean, mx = summarize(hp_vals)
        lines.append(f"- **Per-oligo homopolymer**: min {mn}, mean {mean}, max {mx}")
    if dropout_flags:
        total = len(dropout_flags)
        dropped = sum(1 for flag in dropout_flags if flag)
        lines.append(f"- **Dropouts**: {dropped}/{total} ({(dropped/total)*100:.2f}% )")
    if isinstance(ecc, Mapping) and ecc:
        lines.append("- **ECC Success Ratios:**")
        for name, values in ecc.items():
            if not isinstance(values, list):
                continue
            filtered = [float(v) for v in values if isinstance(v, (int, float))]
            if not filtered:
                continue
            _, mean_val, _ = sorted(filtered)[0], sum(filtered) / len(filtered), sorted(filtered)[-1]
            lines.append(f"  - {name}: {mean_val:.2%}")
    return lines


def encode_to_markdown(result: EncodeResult) -> str:
    lines: list[str] = ["# Encoding Report", "", f"**Schema Version:** {RUN_SCHEMA_VERSION}", "", "## Metrics"]
    lines.extend(_metric_lines(result.metrics))
    oligo_lines = _oligo_metric_lines(result.metrics)
    if oligo_lines:
        lines.append("")
        lines.append("## Per-oligo Metrics")
        lines.extend(oligo_lines)
    if result.info_messages:
        lines.append("")
        lines.append("## Info Messages")
        lines.extend(f"- {m}" for m in result.info_messages)
    return "\n".join(lines)


def decode_to_markdown(result: DecodeResult) -> str:
    lines: list[str] = ["# Decoding Report", "", f"**Schema Version:** {RUN_SCHEMA_VERSION}", f"**Status:** {result.status_message}"]
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


def plot_fec_benchmark(results: List[Dict[str, float | str]]) -> io.BytesIO:
    """Return a bar plot of encode/decode throughput for FEC benchmarks."""
    if not _MATPLOTLIB_AVAILABLE:
        return _dummy_png()

    names = [r.get("fec", "") for r in results]
    enc = [float(r.get("encode_mb_s", 0)) for r in results]
    dec = [float(r.get("decode_mb_s", 0)) for r in results]

    x = list(range(len(names)))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - width / 2 for i in x], enc, width, label="encode MB/s")
    ax.bar([i + width / 2 for i in x], dec, width, label="decode MB/s")
    ax.set_ylabel("MB/s")
    ax.set_title("FEC Benchmark")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    try:
        plt.savefig(buf, format="png")
        buf.seek(0)
    finally:
        plt.close(fig)
    return buf


def plot_fec_success(results: List[Dict[str, float | str]]) -> io.BytesIO:
    """Return a success-rate vs redundancy plot for FEC benchmarks."""
    if not _MATPLOTLIB_AVAILABLE:
        return _dummy_png()

    names = sorted({r.get("fec", "") for r in results})
    fig, ax = plt.subplots(figsize=(8, 5))
    for name in names:
        subset = [r for r in results if r.get("fec") == name and "redundancy" in r]
        if not subset:
            continue
        subset.sort(key=lambda d: float(d.get("redundancy_param", d.get("redundancy", 0))))
        xs = [float(r.get("redundancy_param", r.get("redundancy", 0))) for r in subset]
        ys = [1.0 - float(r.get("ber", 1.0)) for r in subset]
        ax.plot(xs, ys, marker="o", label=name)

    ax.set_xlabel("redundancy")
    ax.set_ylabel("success rate")
    ax.set_title("FEC Success Rate")
    ax.set_ylim(0, 1)
    ax.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    try:
        plt.savefig(buf, format="png")
        buf.seek(0)
    finally:
        plt.close(fig)
    return buf
