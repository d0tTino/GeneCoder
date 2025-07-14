import json
from pathlib import Path
from typing import Any, Iterable

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
    avg_bpn = sum(bpn_values) / len(bpn_values) if bpn_values else 0.0
    return {
        "files": total_files,
        "total_original_size": total_bytes,
        "total_dna_length": total_nt,
        "avg_bits_per_nt": avg_bpn,
    }
