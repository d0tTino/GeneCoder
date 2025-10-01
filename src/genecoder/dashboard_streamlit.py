from __future__ import annotations

"""Minimal Streamlit dashboard for common simulation metrics.

The interface visualizes GC content, homopolymer runs, and ECC success rates
from one or more metrics files produced by the toolkit.  It also provides
summary plots showing GC percentage statistics and longest homopolymer runs
across multiple datasets.
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
    "substitutions": None,
    "insertions": None,
    "deletions": None,
    "coverage": None,
    "coverage_distribution": [],
    "oligo_metrics": {},
}

_ERROR_METRICS: tuple[tuple[str, str], ...] = (
    ("substitutions", "Substitutions"),
    ("insertions", "Insertions"),
    ("deletions", "Deletions"),
)


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


def _gc_stats(dist: object) -> tuple[float | None, float | None, float | None]:
    """Return (min, mean, max) GC percentage from ``dist`` if possible."""

    if isinstance(dist, list) and dist:
        try:
            total = float(sum(dist))
            if total <= 0:
                return (None, None, None)
            min_gc = next(i for i, v in enumerate(dist) if v)
            max_gc = len(dist) - 1 - next(
                i for i, v in enumerate(reversed(dist)) if v
            )
            mean_gc = sum(i * v for i, v in enumerate(dist)) / total
            return float(min_gc), float(mean_gc), float(max_gc)
        except Exception:  # pragma: no cover - defensive
            return (None, None, None)
    return (None, None, None)


def _longest_homopolymer(runs: object) -> float | None:
    """Return the longest homopolymer length from ``runs`` if possible."""

    if isinstance(runs, list) and runs:
        for idx, count in reversed(list(enumerate(runs, 1))):
            if count:
                return float(idx)
    return None


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _coverage_value(data: dict[str, Any]) -> float | None:
    coverage = _to_float(data.get("coverage"))
    if coverage is not None:
        return coverage
    distribution = data.get("coverage_distribution")
    if isinstance(distribution, list) and distribution:
        try:
            total = float(sum(float(v) for v in distribution))
            if total <= 0:
                return None
            mean = sum(idx * float(count) for idx, count in enumerate(distribution)) / total
            return float(mean)
        except Exception:  # pragma: no cover - defensive
            return None
    return None


def _extract_oligo_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    oligo = data.get("oligo_metrics")
    if not isinstance(oligo, dict):
        return []
    gc_vals = [
        float(v) for v in oligo.get("gc_percentages", []) if isinstance(v, (int, float))
    ]
    hp_vals = [
        float(v) for v in oligo.get("max_homopolymers", []) if isinstance(v, (int, float))
    ]
    dropout_flags = [
        bool(v) if isinstance(v, bool) else bool(int(v))
        for v in oligo.get("dropout_flags", [])
    ]
    ecc = oligo.get("ecc_success")
    ecc_map: dict[str, list[float]] = {}
    if isinstance(ecc, dict):
        for name, values in ecc.items():
            if isinstance(values, list):
                filtered = [
                    float(val)
                    for val in values
                    if isinstance(val, (int, float)) or isinstance(val, bool)
                ]
                if filtered:
                    ecc_map[str(name)] = [
                        float(val) if not isinstance(val, bool) else (1.0 if val else 0.0)
                        for val in filtered
                    ]

    max_len = max(
        [len(gc_vals), len(hp_vals), len(dropout_flags)]
        + [len(values) for values in ecc_map.values()] 
        if ecc_map
        else [len(gc_vals), len(hp_vals), len(dropout_flags)]
    )
    if max_len == 0:
        return []

    records: list[dict[str, Any]] = []
    for idx in range(max_len):
        record: dict[str, Any] = {"Index": idx + 1}
        if idx < len(gc_vals):
            record["GC%"] = gc_vals[idx]
        if idx < len(hp_vals):
            record["Max Homopolymer"] = hp_vals[idx]
        if idx < len(dropout_flags):
            record["Dropout"] = dropout_flags[idx]
        for name, values in ecc_map.items():
            if idx < len(values):
                record[f"ECC:{name}"] = values[idx]
        records.append(record)
    return records


def main(results_paths: Iterable[str] | str | None = None) -> None:  # pragma: no cover - UI logic
    """Render the dashboard from one or more metrics files."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to run the dashboard")

    paths = _iterable(results_paths) or sys.argv[1:]

    datasets: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = {**_DEF_METRICS, **_load_metrics(path)}
        datasets[str(path)] = data

    gc_rows: list[dict[str, float | str]] = []
    hp_rows: list[dict[str, float | str]] = []
    error_rows: list[dict[str, float | str]] = []
    coverage_rows: list[dict[str, float | str]] = []
    oligo_rows: list[dict[str, Any]] = []
    for name, data in datasets.items():
        label = Path(name).stem
        min_gc, mean_gc, max_gc = _gc_stats(data.get("gc_distribution"))
        if min_gc is not None and mean_gc is not None and max_gc is not None:
            gc_rows.extend(
                [
                    {"Run": label, "Metric": "min", "Value": min_gc},
                    {"Run": label, "Metric": "mean", "Value": mean_gc},
                    {"Run": label, "Metric": "max", "Value": max_gc},
                ]
            )
        longest = _longest_homopolymer(data.get("homopolymer_runs"))
        if longest is not None:
            hp_rows.append({"Run": label, "Value": longest})

        for metric_key, metric_label in _ERROR_METRICS:
            value = _to_float(data.get(metric_key))
            if value is not None:
                error_rows.append({"Run": label, "Metric": metric_label, "Value": value})

        coverage = _coverage_value(data)
        if coverage is not None:
            coverage_rows.append({"Run": label, "Metric": "Coverage", "Value": coverage})

        for record in _extract_oligo_records(data):
            record = {**record}
            record["Run"] = label
            oligo_rows.append(record)

    st.header("GC Summary (%)")
    if gc_rows:
        if alt and pd:
            df = pd.DataFrame(gc_rows)
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(x="Run:N", y="Value:Q", color="Metric:N")
            )
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            for metric in ("min", "mean", "max"):
                chart_data = {
                    row["Run"]: row["Value"]
                    for row in gc_rows
                    if row["Metric"] == metric
                }
                if chart_data:
                    st.bar_chart(chart_data)
    else:
        st.write("No GC summary data.")

    st.header("Per-oligo Distributions")
    if oligo_rows:
        if alt and pd:
            df = pd.DataFrame(oligo_rows)
            gc_chart = (
                alt.Chart(df.dropna(subset=["GC%"]))
                .mark_bar(opacity=0.7)
                .encode(
                    alt.X("GC%:Q", bin=alt.Bin(maxbins=20)),
                    y="count()",
                    color="Run:N",
                    tooltip=["Run", "count()"],
                )
                .properties(title="GC% Histogram")
            )
            hp_chart = (
                alt.Chart(df.dropna(subset=["Max Homopolymer"]))
                .mark_boxplot()
                .encode(x="Run:N", y="Max Homopolymer:Q", color="Run:N")
                .properties(title="Max Homopolymer Boxplot")
            )
            st.altair_chart(gc_chart, use_container_width=True)
            st.altair_chart(hp_chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            gc_hist: dict[str, list[float]] = {}
            hp_values: dict[str, list[float]] = {}
            for row in oligo_rows:
                run = row["Run"]
                gc_hist.setdefault(run, [])
                hp_values.setdefault(run, [])
                if "GC%" in row:
                    gc_hist[run].append(row["GC%"])
                if "Max Homopolymer" in row:
                    hp_values[run].append(row["Max Homopolymer"])
            for run, values in gc_hist.items():
                st.write(f"GC% for {run}: {[round(v, 3) for v in values]}")
            for run, values in hp_values.items():
                st.write(f"Homopolymer lengths for {run}: {values}")

        # Highlight out-of-bounds oligos (GC outside [0.4,0.6] or HP > 8)
        flagged = [
            row
            for row in oligo_rows
            if (
                ("GC%" in row and (row["GC%"] < 0.4 or row["GC%"] > 0.6))
                or ("Max Homopolymer" in row and row["Max Homopolymer"] > 8)
                or row.get("Dropout")
            )
        ]
        if flagged:
            st.subheader("Out-of-bounds oligos")
            st.table(flagged)
    else:
        st.write("No per-oligo metrics available.")

    st.header("Error Summary")
    if error_rows:
        if alt and pd:
            df = pd.DataFrame(error_rows)
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(x="Run:N", y="Value:Q", color="Metric:N")
            )
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            for _, metric_label in _ERROR_METRICS:
                chart_data = {
                    f"{row['Run']} ({row['Metric']})": row["Value"]
                    for row in error_rows
                    if row["Metric"] == metric_label
                }
                if chart_data:
                    st.bar_chart(chart_data)
    else:
        st.write("No error summary data.")

    st.header("Coverage Summary")
    if coverage_rows:
        if alt and pd:
            df = pd.DataFrame(coverage_rows)
            chart = alt.Chart(df).mark_bar().encode(x="Run:N", y="Value:Q")
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            chart_data = {
                f"{row['Run']} ({row['Metric']})": row["Value"] for row in coverage_rows
            }
            if chart_data:
                st.bar_chart(chart_data)
    else:
        st.write("No coverage summary data.")

    st.header("Longest Homopolymer Runs")
    if hp_rows:
        if alt and pd:
            df = pd.DataFrame(hp_rows)
            chart = alt.Chart(df).mark_bar().encode(x="Run:N", y="Value:Q")
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            st.bar_chart({row["Run"]: row["Value"] for row in hp_rows})
    else:
        st.write("No homopolymer summary data.")

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

        st.subheader("Coverage")
        coverage_value = _to_float(data.get("coverage"))
        coverage_shown = False
        if coverage_value is not None:
            coverage_shown = True
            if alt and pd:
                df = pd.DataFrame({"Run": [label], "Value": [coverage_value]})
                chart = alt.Chart(df).mark_bar().encode(x="Run:N", y="Value:Q")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.bar_chart({label: coverage_value})
        cov_dist = data.get("coverage_distribution")
        if isinstance(cov_dist, list) and cov_dist:
            coverage_shown = True
            if alt and pd:
                df = pd.DataFrame({"coverage": list(range(len(cov_dist))), "count": cov_dist})
                chart = alt.Chart(df).mark_bar().encode(x="coverage", y="count")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.bar_chart(cov_dist)
        if not coverage_shown:
            st.write("No coverage data.")


def launch(*results_paths: str) -> None:  # pragma: no cover - UI startup
    """Start the Streamlit server for ``results_paths``."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to launch the dashboard")

    import streamlit.web.bootstrap as bootstrap

    bootstrap.run(Path(__file__).as_posix(), False, list(results_paths), {})


if __name__ == "__main__":  # pragma: no cover - manual invocation
    launch(*sys.argv[1:])
