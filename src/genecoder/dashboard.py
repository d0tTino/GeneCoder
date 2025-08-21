from __future__ import annotations

"""Streamlit dashboard for simulation metrics.

This module can render one or more metrics files. When multiple files are
provided, GC distributions are overlaid and ECC success rates are shown
side-by-side for easier comparison between datasets.
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import IO, Any, Iterable, Callable, cast
from types import ModuleType

try:  # pragma: no cover - optional dependency for tests
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
    "gc_content": None,
    "gc_variance": None,
    "max_homopolymer": None,
    "homopolymer_runs": [],
    "ecc_success_rates": {},
    "decode_success_rate": None,
    "substitutions": None,
    "insertions": None,
    "deletions": None,
    "substitutions_histogram": [],
    "insertions_histogram": [],
    "deletions_histogram": [],
    "coverage": None,
    "coverage_distribution": [],
    "constraint_violations": None,
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


def _load_metrics(src: str | Path | IO[str]) -> dict[str, Any]:
    """Load metrics from ``src`` which may be a path or file-like object."""

    try:
        if hasattr(src, "read"):
            data = json.load(src)
            name = getattr(src, "name", "uploaded")
        else:
            name = str(src)
            with open(src, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        if isinstance(data, dict):
            metrics = data.get("metrics")
            if isinstance(metrics, dict):
                return metrics
            return data
    except Exception as exc:  # pragma: no cover - surfaced in UI
        if st:  # pragma: no cover - only used in dashboard
            st.error(f"Failed to load {name}: {exc}")
        else:
            print(f"Failed to load {name}: {exc}")
    return {}


def _iterable(val: Iterable[str] | str | None) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _calc_error_hist(val: object) -> list[int]:
    """Return a histogram list from ``val`` if possible.

    ``val`` may be a list of counts or a mapping of count->frequency.
    The returned list uses the count as the index and the frequency as the
    value, filling any missing bins with zeros.
    """
    if isinstance(val, dict):
        counts: dict[int, int] = {}
        for k, v in val.items():
            try:
                counts[int(k)] = int(v)
            except Exception:
                pass
    elif isinstance(val, list):
        counts = Counter()
        for item in val:
            try:
                counts[int(item)] += 1
            except Exception:
                pass
    else:
        return []
    if not counts:
        return []
    max_bin = max(counts)
    return [counts.get(i, 0) for i in range(max_bin + 1)]


def main(results_paths: Iterable[str] | str | None = None) -> None:  # pragma: no cover - UI logic
    """Render the dashboard from one or more metrics files."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to run the dashboard")

    paths = _iterable(results_paths) or sys.argv[1:]

    datasets: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = {**_DEF_METRICS, **_load_metrics(path)}
        for key in ("substitutions", "insertions", "deletions"):
            val = data.get(key)
            rate: float | None = None
            hist: list[int] = []
            if isinstance(val, (int, float)):
                rate = float(val)
            else:
                hist = _calc_error_hist(val)
            data[key] = rate
            data[f"{key}_histogram"] = hist
        if data:
            datasets[Path(path).stem] = data

    sidebar = getattr(st, "sidebar", st)
    file_uploader: Callable[..., Iterable[Any]] = getattr(
        sidebar, "file_uploader", lambda *a, **k: []
    )
    uploaded = file_uploader("Add metrics files", type="json", accept_multiple_files=True)
    for up in uploaded or []:
        data = {**_DEF_METRICS, **_load_metrics(up)}
        for key in ("substitutions", "insertions", "deletions"):
            val = data.get(key)
            rate: float | None = None
            hist: list[int] = []
            if isinstance(val, (int, float)):
                rate = float(val)
            else:
                hist = _calc_error_hist(val)
            data[key] = rate
            data[f"{key}_histogram"] = hist
        datasets[Path(up.name).stem] = data

    st.title("GeneCoder Dashboard")
    if not datasets:
        st.write("No results files provided.")
        return

    names = list(datasets.keys())
    multiselect = getattr(sidebar, "multiselect", lambda *a, **k: names)
    selected = multiselect("Datasets", names, default=names)
    if not selected:
        st.write("No datasets selected.")
        return

    st.header("GC Distribution")
    if alt and pd and hasattr(st, "altair_chart"):
        rows: list[dict[str, Any]] = []
        for name in selected:
            dist = datasets[name].get("gc_distribution")
            if isinstance(dist, list) and dist:
                for i, val in enumerate(dist):
                    rows.append({"Bin": i, "Count": val, "Dataset": name})
        if rows:
            df = pd.DataFrame(rows)
            gc_chart = (
                alt.Chart(df)
                .mark_bar(opacity=0.5)
                .encode(x="Bin:Q", y="Count:Q", color="Dataset:N")
            )
            st.altair_chart(gc_chart, use_container_width=True)
        else:
            st.write("No GC distribution data.")
    else:
        if len(selected) == 1 and datasets[selected[0]]["gc_distribution"]:
            st.bar_chart(datasets[selected[0]]["gc_distribution"])
        else:
            st.write("Install pandas and altair for multi-file GC charts.")

    st.header("ECC Success Rates")
    ecc_rows: list[dict[str, Any]] = []
    for name in selected:
        ecc = datasets[name].get("ecc_success_rates")
        if isinstance(ecc, dict) and ecc:
            for k, v in ecc.items():
                try:
                    ecc_rows.append({"ECC": k, "Dataset": name, "Rate": float(v)})
                except Exception:
                    pass
    if ecc_rows:
        if pd and len({r["Dataset"] for r in ecc_rows}) > 1:
            df = pd.DataFrame(ecc_rows).pivot(index="ECC", columns="Dataset", values="Rate")
            st.bar_chart(df)
        else:
            ecc_chart: dict[str, float] = {}
            for row in ecc_rows:
                if row["Dataset"] in selected:
                    ecc_chart[row["ECC"]] = row["Rate"]
            if ecc_chart:
                st.bar_chart(ecc_chart)
            else:
                st.write("No ECC success rate data.")
    else:
        st.write("No ECC success rate data.")

    st.header("Homopolymer Run Distribution")
    if alt and pd and hasattr(st, "altair_chart"):
        hp_rows: list[dict[str, Any]] = []
        for name in selected:
            runs = datasets[name].get("homopolymer_runs")
            if isinstance(runs, list) and runs:
                for i, val in enumerate(runs, 1):
                    hp_rows.append({"Run Length": i, "Count": val, "Dataset": name})
        if hp_rows:
            df = pd.DataFrame(hp_rows)
            chart = (
                alt.Chart(df)
                .mark_bar(opacity=0.5)
                .encode(x="Run Length:Q", y="Count:Q", color="Dataset:N")
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.write("No homopolymer run data.")
    else:
        if len(selected) == 1 and datasets[selected[0]]["homopolymer_runs"]:
            st.bar_chart(datasets[selected[0]]["homopolymer_runs"])
        else:
            st.write("Install pandas and altair for multi-file homopolymer charts.")

    st.header("Error Rates")
    subheader = getattr(st, "subheader", getattr(st, "header", lambda *a, **k: None))
    for label, key in [
        ("Substitution Rate", "substitutions"),
        ("Insertion Rate", "insertions"),
        ("Deletion Rate", "deletions"),
    ]:
        rate_rows: list[dict[str, Any]] = []
        for name in selected:
            val = datasets[name].get(key)
            if isinstance(val, (int, float)):
                rate_rows.append({"Dataset": name, "Rate": float(val)})
        subheader(label)
        if rate_rows:
            if pd and len({r["Dataset"] for r in rate_rows}) > 1:
                df = pd.DataFrame(rate_rows).set_index("Dataset")
                st.bar_chart(df)
            else:
                st.bar_chart({r["Dataset"]: r["Rate"] for r in rate_rows})
        else:
            st.write(f"No {label.lower()} data.")

    st.header("Error Histograms")
    err_labels = ["Substitutions", "Insertions", "Deletions"]
    select_err = getattr(sidebar, "multiselect", lambda *a, **k: err_labels)
    enabled_errs = select_err("Error Types", err_labels, default=err_labels)
    for label, key in [
        ("Substitutions", "substitutions_histogram"),
        ("Insertions", "insertions_histogram"),
        ("Deletions", "deletions_histogram"),
    ]:
        if label not in enabled_errs:
            continue
        subheader(f"{label} Histogram")
        if alt and pd and hasattr(st, "altair_chart"):
            hist_rows: list[dict[str, Any]] = []
            for name in selected:
                hist = datasets[name].get(key)
                if isinstance(hist, list) and hist:
                    for i, val in enumerate(hist):
                        hist_rows.append({"Errors": i, "Count": val, "Dataset": name})
            if hist_rows:
                df = pd.DataFrame(hist_rows)
                chart = (
                    alt.Chart(df)
                    .mark_bar(opacity=0.5)
                    .encode(x="Errors:Q", y="Count:Q", color="Dataset:N")
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.write(f"No {label.lower()} histogram data.")
        else:
            if len(selected) == 1:
                hist = datasets[selected[0]].get(key)
                if isinstance(hist, list) and hist:
                    st.bar_chart(hist)
                else:
                    st.write(f"No {label.lower()} histogram data.")
            else:
                st.write("Install pandas and altair for multi-file error histograms.")

    for name in selected:
        data = datasets[name]
        section = getattr(st, "subheader", getattr(st, "header", lambda *a, **k: None))
        section(name)

        gc_content = data.get("gc_content")
        gc_variance = data.get("gc_variance")
        columns = getattr(st, "columns", lambda n: [st] * n)
        cols = columns(2)
        if isinstance(gc_content, (int, float)):
            cols[0].metric("GC Mean", f"{float(gc_content):.2%}")
        if isinstance(gc_variance, (int, float)):
            cols[1].metric("GC Variance", f"{float(gc_variance):.4f}")

        max_hp = data.get("max_homopolymer")
        if isinstance(max_hp, (int, float)):
            st.metric("Max Homopolymer Length", f"{int(max_hp)}")

        decode_rate = _calc_decode_success(data)
        if decode_rate is not None:
            st.metric("Decode Success", f"{decode_rate:.2%}")
        else:
            st.write("No decode success metric.")


        subheader("Read Coverage")
        cov_dist = data.get("coverage_distribution")
        if isinstance(cov_dist, list) and cov_dist:
            st.bar_chart(cov_dist)
        else:
            coverage = data.get("coverage")
            if isinstance(coverage, int):
                st.bar_chart({"Coverage": coverage})
            else:
                st.write("No coverage data.")

        subheader("Constraint Violations")
        violations = data.get("constraint_violations")
        if isinstance(violations, int):
            st.bar_chart({"Violations": violations})
        else:
            st.write("No constraint violation data.")


def launch(*results_paths: str) -> None:  # pragma: no cover - UI startup
    """Start the Streamlit server for ``results_paths``."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to launch the dashboard")

    import streamlit.web.bootstrap as bootstrap

    bootstrap.run(Path(__file__).as_posix(), False, list(results_paths), {})


if __name__ == "__main__":  # pragma: no cover - manual invocation
    launch(*sys.argv[1:])
