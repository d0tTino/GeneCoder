from __future__ import annotations

"""Streamlit dashboard for simulation metrics."""

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st


_DEF_METRICS: dict[str, Any] = {
    "gc_distribution": [],
    "gc_content": None,
    "max_homopolymer": None,
    "homopolymer_runs": [],
    "ecc_success_rates": {},
    "decode_success_rate": None,
}


def _calc_decode_success(data: dict[str, Any]) -> float | None:
    """Return overall decode success rate from ``data``.

    Falls back to averaging ``ecc_success_rates`` when ``decode_success_rate``
    is missing.
    """
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


def _load_metrics(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            metrics = data.get("metrics")
            if isinstance(metrics, dict):
                return metrics
            return data
    except Exception as exc:  # pragma: no cover - I/O errors are surfaced in UI
        st.error(f"Failed to load {path}: {exc}")
    return {}


def main(results_path: str | None = None) -> None:
    """Render the dashboard from ``results_path``."""
    if results_path is None and len(sys.argv) > 1:
        results_path = sys.argv[1]

    st.title("GeneCoder Dashboard")
    if not results_path:
        st.write("No results file provided.")
        return

    data = {**_DEF_METRICS, **_load_metrics(results_path)}

    st.header("GC Distribution")
    if data["gc_distribution"]:
        st.bar_chart(data["gc_distribution"])
    else:
        st.write("No GC distribution data.")

    gc_content = data.get("gc_content")
    if isinstance(gc_content, (int, float)):
        st.metric("Average GC Content", f"{float(gc_content):.2%}")

    max_hp = data.get("max_homopolymer")
    if isinstance(max_hp, (int, float)):
        st.metric("Max Homopolymer Length", f"{int(max_hp)}")

    st.header("Homopolymer Runs")
    if data["homopolymer_runs"]:
        st.bar_chart(data["homopolymer_runs"])
    else:
        st.write("No homopolymer data.")

    st.header("ECC Success Rates")
    ecc = data["ecc_success_rates"]
    if isinstance(ecc, dict) and ecc:
        st.bar_chart({k: float(v) for k, v in ecc.items()})
    else:
        st.write("No ECC success rate data.")

    decode_rate = _calc_decode_success(data)
    if decode_rate is not None:
        st.metric("Decode Success", f"{decode_rate:.2%}")
    else:
        st.write("No decode success metric.")


def launch(results_path: str) -> None:
    """Start the Streamlit server for ``results_path``."""
    import streamlit.web.bootstrap as bootstrap

    bootstrap.run(Path(__file__).as_posix(), False, [results_path], {})


if __name__ == "__main__":  # pragma: no cover - manual invocation
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    launch(path)
