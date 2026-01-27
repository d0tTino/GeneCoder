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
import math
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
_DEFAULT_GC_MIN = 0.4
_DEFAULT_GC_MAX = 0.6
_DEFAULT_MAX_HOMOPOLYMER = 8

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


def _gc_percentages(dist: object) -> list[float]:
    """Return GC distribution values expressed as percentages."""

    if not isinstance(dist, list) or not dist:
        return []

    values: list[float] = []
    for value in dist:
        if isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            continue
        if not math.isfinite(numeric):  # pragma: no cover - defensive
            continue
        values.append(numeric)

    if not values:
        return []

    max_value = max(values)
    min_value = min(values)
    if max_value <= 1.0 and min_value >= 0.0:
        return [val * 100.0 for val in values]
    return values


def _gc_stats(dist: object) -> tuple[float | None, float | None, float | None]:
    """Return (min, mean, max) GC percentage from ``dist`` if possible."""

    values = _gc_percentages(dist)
    if not values:
        return (None, None, None)
    min_gc = min(values)
    mean_gc = sum(values) / len(values)
    max_gc = max(values)
    return float(min_gc), float(mean_gc), float(max_gc)


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


def _constraint_limits(data: dict[str, Any]) -> tuple[float, float, int]:
    gc_min = _DEFAULT_GC_MIN
    gc_max = _DEFAULT_GC_MAX
    max_hp = _DEFAULT_MAX_HOMOPOLYMER

    violations = data.get("constraint_violations")
    if isinstance(violations, dict):
        limits = violations.get("limits")
        if isinstance(limits, dict):
            gc_min_val = limits.get("gc_min")
            gc_max_val = limits.get("gc_max")
            max_hp_val = limits.get("max_homopolymer")
            if isinstance(gc_min_val, (int, float)) and not isinstance(gc_min_val, bool):
                gc_min = float(gc_min_val)
            if isinstance(gc_max_val, (int, float)) and not isinstance(gc_max_val, bool):
                gc_max = float(gc_max_val)
            if isinstance(max_hp_val, (int, float)) and not isinstance(max_hp_val, bool):
                max_hp = int(max_hp_val)
    return gc_min, gc_max, max_hp


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


def _plotting_status() -> tuple[bool, list[str]]:
    missing = []
    if pd is None:
        missing.append("pandas")
    if alt is None:
        missing.append("altair")
    return not missing, missing


def main(results_paths: Iterable[str] | str | None = None) -> None:  # pragma: no cover - UI logic
    """Render the dashboard from one or more metrics files."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to run the dashboard")

    paths = _iterable(results_paths) or sys.argv[1:]

    datasets: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = {**_DEF_METRICS, **_load_metrics(path)}
        datasets[str(path)] = data

    can_plot, missing_plot_deps = _plotting_status()
    if not can_plot:
        deps = ", ".join(missing_plot_deps)
        st.error(
            "Plotting dependencies missing: "
            f"{deps}. Install with `pip install 'GeneCoder[dashboard]'` "
            "or `poetry install --extras dashboard` to enable charts."
        )

    gc_rows: list[dict[str, float | str]] = []
    hp_rows: list[dict[str, float | str]] = []
    error_rows: list[dict[str, float | str]] = []
    coverage_rows: list[dict[str, float | str]] = []
    oligo_rows: list[dict[str, Any]] = []
    limits_by_run: dict[str, tuple[float, float, int]] = {}
    for name, data in datasets.items():
        label = Path(name).stem
        limits_by_run[label] = _constraint_limits(data)
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
        if can_plot:
            df = pd.DataFrame(gc_rows)
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(x="Run:N", y="Value:Q", color="Metric:N")
            )
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            st.table(gc_rows)
    else:
        st.write("No GC summary data.")

    st.header("Per-oligo Distributions")
    if oligo_rows:
        if can_plot:
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
            st.table(oligo_rows)

        def is_flagged(row: dict[str, Any]) -> bool:
            gc_min, gc_max, max_hp = limits_by_run.get(
                row.get("Run", ""),
                (_DEFAULT_GC_MIN, _DEFAULT_GC_MAX, _DEFAULT_MAX_HOMOPOLYMER),
            )
            if "GC%" in row and (row["GC%"] < gc_min or row["GC%"] > gc_max):
                return True
            if "Max Homopolymer" in row and row["Max Homopolymer"] > max_hp:
                return True
            return bool(row.get("Dropout"))

        flagged = [row for row in oligo_rows if is_flagged(row)]
        if flagged:
            st.subheader("Out-of-bounds oligos")
            st.table(flagged)
    else:
        st.write("No per-oligo metrics available.")

    st.header("Error Summary")
    if error_rows:
        if can_plot:
            df = pd.DataFrame(error_rows)
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(x="Run:N", y="Value:Q", color="Metric:N")
            )
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            st.table(error_rows)
    else:
        st.write("No error summary data.")

    st.header("Coverage Summary")
    if coverage_rows:
        if can_plot:
            df = pd.DataFrame(coverage_rows)
            chart = alt.Chart(df).mark_bar().encode(x="Run:N", y="Value:Q")
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            st.table(coverage_rows)
    else:
        st.write("No coverage summary data.")

    st.header("Longest Homopolymer Runs")
    if hp_rows:
        if can_plot:
            df = pd.DataFrame(hp_rows)
            chart = alt.Chart(df).mark_bar().encode(x="Run:N", y="Value:Q")
            st.altair_chart(chart, use_container_width=True)
        else:  # pragma: no cover - basic fallback
            st.table(hp_rows)
    else:
        st.write("No homopolymer summary data.")

    for name, data in datasets.items():
        st.header(Path(name).name)

        gc = _gc_percentages(data.get("gc_distribution"))
        st.subheader("GC Content (%)")
        if gc:
            if can_plot:
                df = pd.DataFrame(
                    {
                        "Window": list(range(1, len(gc) + 1)),
                        "GC%": gc,
                    }
                )
                chart = (
                    alt.Chart(df)
                    .mark_line(point=True)
                    .encode(x="Window:Q", y="GC%:Q")
                )
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover - basic fallback
                st.table(
                    [{"Window": idx, "GC%": val} for idx, val in enumerate(gc, 1)]
                )
        else:
            st.write("No GC data.")

        hp = data.get("homopolymer_runs")
        st.subheader("Homopolymer Runs")
        if isinstance(hp, list) and hp:
            if can_plot:
                df = pd.DataFrame({"length": list(range(len(hp))), "count": hp})
                chart = alt.Chart(df).mark_bar().encode(x="length", y="count")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.table(
                    [
                        {"Length": idx, "Count": count}
                        for idx, count in enumerate(hp)
                    ]
                )
        else:
            st.write("No homopolymer data.")

        ecc = data.get("ecc_success_rates")
        st.subheader("ECC Success Rates")
        if isinstance(ecc, dict) and ecc:
            if can_plot:
                df = pd.DataFrame(
                    {"method": list(ecc.keys()), "rate": list(ecc.values())}
                )
                chart = alt.Chart(df).mark_bar().encode(x="method", y="rate")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.table(
                    [{"Method": method, "Rate": rate} for method, rate in ecc.items()]
                )
        else:
            st.write("No ECC data.")

        st.subheader("Coverage")
        coverage_value = _to_float(data.get("coverage"))
        coverage_shown = False
        if coverage_value is not None:
            coverage_shown = True
            if can_plot:
                df = pd.DataFrame({"Run": [label], "Value": [coverage_value]})
                chart = alt.Chart(df).mark_bar().encode(x="Run:N", y="Value:Q")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.table([{"Run": label, "Coverage": coverage_value}])
        cov_dist = data.get("coverage_distribution")
        if isinstance(cov_dist, list) and cov_dist:
            coverage_shown = True
            if can_plot:
                df = pd.DataFrame(
                    {"coverage": list(range(len(cov_dist))), "count": cov_dist}
                )
                chart = alt.Chart(df).mark_bar().encode(x="coverage", y="count")
                st.altair_chart(chart, use_container_width=True)
            else:  # pragma: no cover
                st.table(
                    [
                        {"Coverage": idx, "Count": count}
                        for idx, count in enumerate(cov_dist)
                    ]
                )
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
