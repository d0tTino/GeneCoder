from __future__ import annotations

"""Minimal Streamlit dashboard for common simulation metrics.

The interface visualizes GC content, homopolymer runs, and ECC success rates
from one or more metrics files produced by the toolkit.
"""

from pathlib import Path
import json
import sys
from typing import Any, Iterable, IO, cast
from types import ModuleType

try:  # pragma: no cover - optional dependency
    import streamlit as _st
except Exception:  # pragma: no cover - gracefully degrade if missing
    _st = None
st = cast(ModuleType | None, _st)

try:  # pragma: no cover - optional plotting dependencies
    import pandas as _pd
    import altair as _alt
except Exception:  # pragma: no cover
    _pd = None
    _alt = None
pd = cast(Any, _pd)
alt = cast(Any, _alt)

_DEF_METRICS: dict[str, Any] = {
    "gc_distribution": [],
    "homopolymer_runs": [],
    "ecc_success_rates": {},
}


def _iterable(val: Iterable[str] | str | None) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _load_metrics(src: str | Path | IO[str]) -> dict[str, Any]:
    try:
        if hasattr(src, "read"):
            data = json.load(src)
        else:
            with open(src, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        if isinstance(data, dict):
            metrics = data.get("metrics")
            if isinstance(metrics, dict):
                return metrics
            return data
    except Exception:  # pragma: no cover - surfaced in UI
        pass
    return {}


def main(results_paths: Iterable[str] | str | None = None) -> None:  # pragma: no cover - UI logic
    """Render the dashboard from one or more metrics files."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to run the dashboard")

    paths = _iterable(results_paths) or sys.argv[1:]

    datasets: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = {**_DEF_METRICS, **_load_metrics(path)}
        datasets[path] = data

    for name, data in datasets.items():
        st.header(Path(name).name)

        gc = data.get("gc_distribution")
        st.subheader("GC Content (%)")
        if isinstance(gc, list) and gc:
            if alt and pd:
                df = pd.DataFrame({"gc": list(range(len(gc))), "count": gc})
                chart = alt.Chart(df).mark_bar().encode(x="gc", y="count")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover - basic fallback
                st.bar_chart(gc)
        else:
            st.write("No GC data.")

        hp = data.get("homopolymer_runs")
        st.subheader("Homopolymer Runs")
        if isinstance(hp, list) and hp:
            if alt and pd:
                df = pd.DataFrame({"length": list(range(len(hp))), "count": hp})
                chart = alt.Chart(df).mark_bar().encode(x="length", y="count")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.bar_chart(hp)
        else:
            st.write("No homopolymer data.")

        ecc = data.get("ecc_success_rates")
        st.subheader("ECC Success Rates")
        if isinstance(ecc, dict) and ecc:
            if alt and pd:
                df = pd.DataFrame({"method": list(ecc.keys()), "rate": list(ecc.values())})
                chart = alt.Chart(df).mark_bar().encode(x="method", y="rate")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.bar_chart(ecc)
        else:
            st.write("No ECC data.")


def launch(*results_paths: str) -> None:  # pragma: no cover - UI startup
    """Start the Streamlit server for ``results_paths``."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to launch the dashboard")

    import streamlit.web.bootstrap as bootstrap

    bootstrap.run(Path(__file__).as_posix(), False, list(results_paths), {})


if __name__ == "__main__":  # pragma: no cover - manual invocation
    launch(*sys.argv[1:])
