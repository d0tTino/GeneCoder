import json
from pathlib import Path
from typing import Any, Iterable


def _extract_violation_count(value: object) -> int:
    """Return an integer count from ``constraint_violations`` values."""

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dict):
        count_val = value.get("count")
        if isinstance(count_val, (int, float)):
            return int(count_val)
        violations = value.get("violations")
        if isinstance(violations, list):
            return len(violations)
        total = value.get("total") or value.get("violation_count")
        if isinstance(total, (int, float)):
            return int(total)
    if isinstance(value, list):
        return len(value)
    return 0

__all__ = ["parse_manifests", "aggregate_metrics"]


def parse_manifests(root: Path) -> Iterable[dict[str, Any]]:
    """Yield manifest dictionaries found under *root*.

    The function searches recursively for files ending with ``.manifest.json``
    and loads any valid JSON objects found.
    """
    for path in root.rglob("*.manifest.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            yield data


def aggregate_metrics(root: Path) -> dict[str, Any]:
    """Return aggregate metrics for all manifests under *root*."""
    total_files = 0
    total_bytes = 0
    total_nt = 0
    total_subs = 0
    total_ins = 0
    total_dels = 0
    total_cov = 0
    total_viol = 0
    bpn_values: list[float] = []
    for manifest in parse_manifests(root):
        total_files += 1
        metrics = manifest.get("metrics", {})
        if isinstance(metrics, dict):
            b = metrics.get("original_size")
            if isinstance(b, int):
                total_bytes += b
            n = metrics.get("dna_length")
            if isinstance(n, int):
                total_nt += n
            bpn = metrics.get("bits_per_nt")
            if isinstance(bpn, (int, float)):
                bpn_values.append(float(bpn))
            s = metrics.get("substitutions")
            if isinstance(s, int):
                total_subs += s
            i = metrics.get("insertions")
            if isinstance(i, int):
                total_ins += i
            d = metrics.get("deletions")
            if isinstance(d, int):
                total_dels += d
            cov = metrics.get("coverage")
            if isinstance(cov, int):
                total_cov += cov
            viol = metrics.get("constraint_violations")
            total_viol += _extract_violation_count(viol)
    avg_bpn = sum(bpn_values) / len(bpn_values) if bpn_values else 0.0
    return {
        "files": total_files,
        "total_original_size": total_bytes,
        "total_dna_length": total_nt,
        "avg_bits_per_nt": avg_bpn,
        "total_substitutions": total_subs,
        "total_insertions": total_ins,
        "total_deletions": total_dels,
        "total_coverage": total_cov,
        "total_constraint_violations": total_viol,
    }
