from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "configs" / "schema" / "benchmark_competitor_matrix.schema.json"
DEFAULT_MATRIX_PATH = ROOT / "benchmarks" / "competitor_matrix.yaml"
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "benchmarks" / "competitor_report.md"
DEFAULT_CHART_PATH = ROOT / "artifacts" / "benchmarks" / "competitor_report.svg"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def validate_matrix(matrix: dict[str, Any], schema_path: Path = SCHEMA_PATH) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema = importlib.import_module("jsonschema")
    except ModuleNotFoundError:
        required = set(schema.get("required", []))
        missing = sorted(required - set(matrix))
        if missing:
            raise ValueError(f"Invalid competitor matrix: missing required keys {missing}")
        if not isinstance(matrix.get("scenarios"), list) or not matrix["scenarios"]:
            raise ValueError("Invalid competitor matrix: scenarios must be a non-empty list")
        return

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(matrix), key=lambda err: list(err.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in err.path) or '<root>'}: {err.message}"
            for err in errors
        )
        raise ValueError(f"Invalid competitor matrix: {details}")


def _load_json_if_present(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_result(source_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = payload.get("normalized_outputs", payload)
    if not isinstance(normalized, dict):
        raise ValueError(f"Result payload for {source_name} must be a mapping")
    normalized = dict(normalized)
    normalized.setdefault("tool", source_name)
    return normalized


def collect_results(matrix: dict[str, Any], results_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in matrix["scenarios"]:
        scenario_name = str(scenario["scenario"])
        gene_entry = _normalize_result("GeneCoder", scenario["normalized_outputs"])
        gene_entry["scenario"] = scenario_name
        gene_entry["source_type"] = "internal_reference"
        rows.append(gene_entry)

        for baseline in scenario.get("external_baselines", []):
            source_name = str(baseline["tool"])
            result_file = results_root / str(baseline["result_file"])
            if result_file.exists():
                payload = _load_json_if_present(result_file)
                source_type = "runtime_artifact"
            else:
                fixture_file = ROOT / str(baseline["fixture_file"])
                payload = _load_json_if_present(fixture_file)
                source_type = "fixture_baseline"
            normalized = _normalize_result(source_name, payload)
            normalized["scenario"] = scenario_name
            normalized["source_type"] = source_type
            rows.append(normalized)
    return rows


def _fmt_float(value: object, digits: int = 3) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}f}"
    return "n/a"


def render_markdown(matrix: dict[str, Any], rows: list[dict[str, Any]], chart_path: Path) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["scenario"]), []).append(row)

    lines = [
        "# External Benchmark Comparison Report",
        "",
        f"Matrix version: `{matrix['matrix_version']}`  ",
        f"Schema version: `{matrix['schema_version']}`",
        "",
        "This report compares GeneCoder reference runs with external baselines using normalized outputs.",
        "",
        f"![Throughput comparison chart]({chart_path.as_posix()})",
        "",
    ]

    for scenario in matrix["scenarios"]:
        name = str(scenario["scenario"])
        lines.extend(
            [
                f"## {name}",
                "",
                f"**Assumptions:** {scenario['assumptions']}",
                "",
                f"**Data source:** {scenario['data_source']}",
                "",
                f"**Reproducibility notes:** {scenario['reproducibility_notes']}",
                "",
                "| Tool | Source | Throughput MB/s | Decode Success | BER | Notes |",
                "| --- | --- | ---: | :---: | ---: | --- |",
            ]
        )
        for row in sorted(
            grouped.get(name, []), key=lambda item: (item["tool"] != "GeneCoder", item["tool"])
        ):
            lines.append(
                "| {tool} | {source} | {throughput} | {decode_success} | {ber} | {notes} |".format(
                    tool=row.get("tool", "unknown"),
                    source=row.get("source_type", "unknown"),
                    throughput=_fmt_float(row.get("throughput_mb_s")),
                    decode_success="yes" if bool(row.get("decode_success")) else "no",
                    ber=_fmt_float(row.get("bit_error_rate"), 6),
                    notes=str(row.get("notes", "")),
                )
            )
        lines.append("")
    return "\n".join(lines)


def render_svg(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width = 900
    row_height = 28
    left_pad = 280
    chart_width = 540
    max_tp = max((float(row.get("throughput_mb_s", 0.0)) for row in rows), default=1.0) or 1.0
    height = 80 + row_height * len(rows)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,sans-serif;font-size:12px}.gene{fill:#2563eb}.external{fill:#64748b}</style>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="20" y="30" font-size="20">GeneCoder vs external throughput</text>',
    ]
    y = 60
    for row in rows:
        tp = float(row.get("throughput_mb_s", 0.0))
        bar = 0 if tp <= 0 else int((tp / max_tp) * chart_width)
        css = "gene" if row.get("tool") == "GeneCoder" else "external"
        label = f"{row['scenario']} — {row['tool']} ({row.get('source_type', 'unknown')})"
        parts.append(f'<text x="20" y="{y + 14}">{label}</text>')
        parts.append(
            f'<rect x="{left_pad}" y="{y}" width="{bar}" height="16" class="{css}" rx="3"/>'
        )
        parts.append(f'<text x="{left_pad + bar + 8}" y="{y + 13}">{tp:.3f} MB/s</text>')
        y += row_height
    parts.append("</svg>")
    output_path.write_text("".join(parts), encoding="utf-8")


def generate_report(
    matrix_path: Path, results_root: Path, output_path: Path, chart_path: Path
) -> tuple[Path, Path]:
    matrix = load_yaml(matrix_path)
    validate_matrix(matrix)
    rows = collect_results(matrix, results_root)
    render_svg(rows, chart_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_markdown(matrix, rows, chart_path.relative_to(output_path.parent)),
        encoding="utf-8",
    )
    return output_path, chart_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate cross-tool benchmark comparison report")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--results-root", type=Path, default=ROOT / "artifacts" / "benchmarks")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--chart", type=Path, default=DEFAULT_CHART_PATH)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report_path, chart_path = generate_report(
        args.matrix, args.results_root, args.output, args.chart
    )
    print(json.dumps({"report": str(report_path), "chart": str(chart_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
