from __future__ import annotations

"""Streamlit dashboard for simulation metrics.

This module can render one or more metrics files. When multiple files are
provided, GC distributions are overlaid and ECC success rates are shown
side-by-side for easier comparison between datasets.
"""

import json
import sys
import math
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
    "oligo_metrics": {},
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


def _split_error_metric(val: object) -> tuple[float | None, list[int]]:
    """Return a rate and histogram tuple for error metric values."""

    rate: float | None = None
    hist: list[int] = []
    if isinstance(val, (int, float)):
        rate = float(val)
    else:
        hist = _calc_error_hist(val)
    return rate, hist


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

    base_lengths = [len(gc_vals), len(hp_vals), len(dropout_flags)]
    extra_lengths = [len(values) for values in ecc_map.values()]
    max_len = max(base_lengths + extra_lengths) if base_lengths or extra_lengths else 0
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


def _parse_constraint_violations(value: object) -> dict[str, Any]:
    """Return a normalized summary for ``constraint_violations`` values.

    The metric may be expressed as an integer count, a mapping with nested
    structures or an iterable of individual violation records.  The returned
    dictionary always contains ``count`` (int), ``sequence_ids`` (list[str]) and
    ``type_counts`` (dict[str, int]).  Unknown formats fall back to empty
    collections.
    """

    sequences: list[str] = []
    type_counts: Counter[str] = Counter()
    explicit_count: int | None = None

    def add_sequence(seq: object) -> None:
        if seq is None:
            return
        text = str(seq)
        if not text:
            return
        if text not in sequences:
            sequences.append(text)

    def add_type(name: object, count: object = 1) -> None:
        if name is None:
            return
        label = str(name)
        if not label:
            return
        try:
            amount = int(count)
        except Exception:
            amount = 1
        if amount <= 0:
            return
        type_counts[label] += amount

    def parse_collection(collection: object) -> None:
        nonlocal explicit_count
        if isinstance(collection, dict):
            for key, val in collection.items():
                if key in {"count", "total", "violation_count"}:
                    if isinstance(val, (int, float)):
                        cur = int(val)
                        explicit_count = max(explicit_count or 0, cur)
                    continue
                if key in {"sequence_ids", "sequences", "ids"}:
                    if isinstance(val, list):
                        for item in val:
                            add_sequence(item)
                    elif isinstance(val, str):
                        add_sequence(val)
                    continue
                if key in {"violations", "details", "entries"}:
                    parse_collection(val)
                    continue
                if isinstance(val, dict):
                    if key in {"type_counts", "counts", "violations_by_type"}:
                        for sub_key, sub_val in val.items():
                            if isinstance(sub_val, (int, float)):
                                add_type(sub_key, int(sub_val))
                            elif isinstance(sub_val, list):
                                add_type(sub_key, len(sub_val))
                                for item in sub_val:
                                    parse_item(item)
                            else:
                                add_type(sub_key)
                        continue
                    parse_collection(val)
                    continue
                if isinstance(val, (int, float)):
                    add_type(key, int(val))
                elif isinstance(val, list):
                    add_type(key, len(val))
                    for item in val:
                        parse_item(item)
                else:
                    add_type(key)
        elif isinstance(collection, list):
            for item in collection:
                parse_item(item)
        elif isinstance(collection, tuple):
            parse_collection(list(collection))
        elif isinstance(collection, str):
            add_type(collection)

    def parse_item(item: object) -> None:
        nonlocal explicit_count
        if isinstance(item, dict):
            seq = (
                item.get("sequence_id")
                or item.get("sequence")
                or item.get("id")
                or item.get("name")
            )
            add_sequence(seq)
            if "count" in item and isinstance(item["count"], (int, float)):
                cur = int(item["count"])
                explicit_count = max(explicit_count or 0, cur)
            type_hint = item.get("type") or item.get("constraint")
            if type_hint:
                add_type(type_hint, item.get("count", 1))
            nested = item.get("violations") or item.get("details") or item.get("issues")
            if nested is not None:
                parse_collection(nested)
        elif isinstance(item, (list, tuple)) and item:
            add_sequence(item[0])
            if len(item) > 1:
                add_type(item[1])
        elif isinstance(item, str):
            # When only the sequence identifier is provided.
            add_sequence(item)
        elif isinstance(item, (int, float)):
            explicit_count = max(explicit_count or 0, int(item))

    if isinstance(value, (int, float)):
        explicit_count = int(value)
    elif isinstance(value, dict):
        parse_collection(value)
    elif isinstance(value, list):
        for entry in value:
            parse_item(entry)
        explicit_count = explicit_count or len(value)
    elif value is None:
        pass
    else:
        # Attempt to coerce other iterables.
        try:
            for entry in value:  # type: ignore[assignment]
                parse_item(entry)
        except Exception:
            pass

    total_types = sum(type_counts.values())
    count = explicit_count if explicit_count is not None else 0
    if count == 0:
        if sequences:
            count = len(sequences)
        elif total_types:
            count = total_types

    return {
        "count": count,
        "sequence_ids": sequences,
        "type_counts": dict(type_counts),
    }


def main(results_paths: Iterable[str] | str | None = None) -> None:  # pragma: no cover - UI logic
    """Render the dashboard from one or more metrics files."""

    if st is None:  # pragma: no cover - requires streamlit
        raise RuntimeError("streamlit is required to run the dashboard")

    paths = _iterable(results_paths) or sys.argv[1:]

    datasets: dict[str, dict[str, Any]] = {}
    oligo_rows: list[dict[str, Any]] = []
    for path in paths:
        data = {**_DEF_METRICS, **_load_metrics(path)}
        for key in ("substitutions", "insertions", "deletions"):
            rate, hist = _split_error_metric(data.get(key))
            data[key] = rate
            data[f"{key}_histogram"] = hist
        data["constraint_violation_summary"] = _parse_constraint_violations(
            data.get("constraint_violations")
        )
        if data:
            label = Path(path).stem
            datasets[label] = data
            for record in _extract_oligo_records(data):
                new_record = {**record}
                new_record["Run"] = label
                oligo_rows.append(new_record)

    sidebar = getattr(st, "sidebar", st)
    file_uploader: Callable[..., Iterable[Any]] = getattr(
        sidebar, "file_uploader", lambda *a, **k: []
    )
    uploaded = file_uploader("Add metrics files", type="json", accept_multiple_files=True)
    for up in uploaded or []:
        data = {**_DEF_METRICS, **_load_metrics(up)}
        for key in ("substitutions", "insertions", "deletions"):
            rate, hist = _split_error_metric(data.get(key))
            data[key] = rate
            data[f"{key}_histogram"] = hist
        data["constraint_violation_summary"] = _parse_constraint_violations(
            data.get("constraint_violations")
        )
        label = Path(up.name).stem
        datasets[label] = data
        for record in _extract_oligo_records(data):
            new_record = {**record}
            new_record["Run"] = label
            oligo_rows.append(new_record)

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
            dist = _gc_percentages(datasets[name].get("gc_distribution"))
            if dist:
                for idx, val in enumerate(dist, 1):
                    rows.append({"Window": idx, "GC%": val, "Dataset": name})
        if rows:
            df = pd.DataFrame(rows)
            gc_chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(x="Window:Q", y="GC%:Q", color="Dataset:N")
            )
            st.altair_chart(gc_chart, use_container_width=True)
        else:
            st.write("No GC distribution data.")
    else:
        if len(selected) == 1:
            dist = _gc_percentages(datasets[selected[0]].get("gc_distribution"))
            if dist:
                st.bar_chart({f"Window {idx}": val for idx, val in enumerate(dist, 1)})
            else:
                st.write("No GC distribution data.")
        else:
            st.write("Install pandas and altair for multi-file GC charts.")

    st.header("Per-oligo Distributions")
    if oligo_rows:
        relevant = [row for row in oligo_rows if row.get("Run") in selected]
        if relevant:
            if alt and pd and hasattr(st, "altair_chart"):
                df = pd.DataFrame(relevant)
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
            else:
                for row in relevant:
                    st.write(row)

            flagged = [
                row
                for row in relevant
                if (
                    ("GC%" in row and (row["GC%"] < 0.4 or row["GC%"] > 0.6))
                    or ("Max Homopolymer" in row and row["Max Homopolymer"] > 8)
                    or row.get("Dropout")
                )
            ]
            if flagged:
                st.subheader("Out-of-bounds oligos")
                if pd:
                    st.dataframe(pd.DataFrame(flagged))
                else:
                    st.write(flagged)
        else:
            st.write("No per-oligo metrics for selected datasets.")
    else:
        st.write("No per-oligo metrics available.")

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
                hist_vals = datasets[name].get(key)
                if isinstance(hist_vals, list) and hist_vals:
                    for i, val in enumerate(hist_vals):
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
                hist_vals = datasets[selected[0]].get(key)
                if isinstance(hist_vals, list) and hist_vals:
                    st.bar_chart(hist_vals)
                else:
                    st.write(f"No {label.lower()} histogram data.")
            else:
                st.write("Install pandas and altair for multi-file error histograms.")

    st.header("Constraint Violation Types")
    violation_rows: list[dict[str, Any]] = []
    for name in selected:
        summary = datasets[name].get("constraint_violation_summary")
        type_counts = {}
        if isinstance(summary, dict):
            type_counts = summary.get("type_counts", {}) or {}
        if isinstance(type_counts, dict) and type_counts:
            for vio_type, count in type_counts.items():
                try:
                    violation_rows.append(
                        {"Violation": str(vio_type), "Count": float(count), "Dataset": name}
                    )
                except Exception:
                    pass
    if violation_rows:
        if alt and pd and hasattr(st, "altair_chart"):
            df = pd.DataFrame(violation_rows)
            chart = (
                alt.Chart(df)
                .mark_bar(opacity=0.5)
                .encode(x="Violation:N", y="Count:Q", color="Dataset:N")
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            if len(selected) == 1:
                summary = datasets[selected[0]].get("constraint_violation_summary")
                type_counts = {}
                if isinstance(summary, dict):
                    maybe_counts = summary.get("type_counts", {})
                    if isinstance(maybe_counts, dict):
                        type_counts = maybe_counts
                if isinstance(type_counts, dict) and type_counts:
                    st.bar_chart(type_counts)
                else:
                    st.write("No constraint violation type data.")
            else:
                st.write("Install pandas and altair for multi-file constraint violation charts.")
    else:
        st.write("No constraint violation type data.")

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
        summary = data.get("constraint_violation_summary")
        count = 0
        sequences: list[str] = []
        type_counts: dict[str, int] = {}
        if isinstance(summary, dict):
            try:
                count = int(summary.get("count", 0))
            except Exception:
                count = 0
            seq_ids = summary.get("sequence_ids", [])
            if isinstance(seq_ids, list):
                sequences = [str(item) for item in seq_ids if str(item)]
            counts = summary.get("type_counts", {})
            if isinstance(counts, dict):
                cleaned: dict[str, int] = {}
                for key, val in counts.items():
                    try:
                        cleaned[str(key)] = int(val)
                    except Exception:
                        try:
                            cleaned[str(key)] = int(float(val))
                        except Exception:
                            continue
                type_counts = {k: v for k, v in cleaned.items() if v}
        original_value = data.get("constraint_violations")
        has_data = not (
            original_value is None and not sequences and not type_counts and count == 0
        )
        if has_data:
            st.metric("Constraint Violations", f"{count}")
            if sequences:
                st.write("Offending sequence IDs:", ", ".join(sequences))
            if not type_counts and count:
                st.bar_chart({"Violations": count})
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
