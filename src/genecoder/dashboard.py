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
    "homopolymer_runs": [],
    "ecc_success_rates": {},
    "decode_success_rate": None,
}


def _load_metrics(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
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
        st.line_chart(data["gc_distribution"])
    else:
        st.write("No GC distribution data.")

    gc_content = data.get("gc_content")
    if isinstance(gc_content, (int, float)):
        st.metric("Average GC Content", f"{float(gc_content):.2%}")

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

    decode_rate = data.get("decode_success_rate")
    if isinstance(decode_rate, (int, float)):
        st.metric("Decode Success", f"{float(decode_rate):.2%}")
    else:
        st.write("No decode success metric.")


def launch(results_path: str) -> None:
    """Start the Streamlit server for ``results_path``."""
    import streamlit.web.bootstrap as bootstrap

    bootstrap.run(Path(__file__).as_posix(), False, [results_path], {})


if __name__ == "__main__":  # pragma: no cover - manual invocation
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    launch(path)
