from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BOUNDARY_MANIFEST = Path("configs/compat_boundary.yaml")
MATRIX_PATH = Path("docs/legacy_deprecation_matrix.md")


@dataclass(frozen=True)
class LegacyModuleBoundary:
    module: str
    sunset_version: str
    allowed_referencers: set[Path]


def _load_boundary_manifest(path: Path = BOUNDARY_MANIFEST) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


_MANIFEST = _load_boundary_manifest()
DEPRECATED_MODULES = set(_MANIFEST["legacy_modules"])
SEARCH_ROOTS = tuple(Path(root) for root in _MANIFEST.get("search_roots", ["src", "tests"]))
APPROVED_REFERENCERS = {
    Path(referencer)
    for module_data in _MANIFEST["legacy_modules"].values()
    for referencer in module_data.get("allowed_referencers", [])
}


def _extract_import_references(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    references: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            references.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            references.add(node.module)
    return references


def _extract_references(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    references: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            references.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            references.add(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            for module_name in DEPRECATED_MODULES:
                if module_name in node.value:
                    references.add(module_name)
    return references


def _parse_version(raw: str) -> tuple[int, ...]:
    return tuple(int(token) for token in raw.strip().lstrip("vV").split("."))


def _all_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.exists():
            files.extend(root.rglob("*.py"))
    return files


def _scan_reference_maps() -> tuple[dict[str, set[Path]], dict[str, set[Path]]]:
    all_refs: dict[str, set[Path]] = {module: set() for module in DEPRECATED_MODULES}
    import_refs: dict[str, set[Path]] = {module: set() for module in DEPRECATED_MODULES}

    for path in _all_python_files():
        references = _extract_references(path)
        for module in references.intersection(DEPRECATED_MODULES):
            all_refs[module].add(path)

        imports = _extract_import_references(path)
        for module in imports.intersection(DEPRECATED_MODULES):
            import_refs[module].add(path)

    return all_refs, import_refs


def _boundary_violations(all_references: dict[str, set[Path]]) -> list[str]:
    violations: list[str] = []
    for module, paths in sorted(all_references.items()):
        allowed = {
            Path(value)
            for value in _MANIFEST["legacy_modules"][module].get("allowed_referencers", [])
        }
        for path in sorted(paths):
            if path not in allowed:
                violations.append(f"{path}: ['{module}']")
    return violations


def _reduction_violations(import_references: dict[str, set[Path]], release: str) -> list[str]:
    violations: list[str] = []
    current = _parse_version(release)
    total_imports = sum(len(paths) for paths in import_references.values())

    targets = _MANIFEST.get("reduction_targets", {})
    for target_release, target in sorted(targets.items(), key=lambda item: _parse_version(item[0])):
        if _parse_version(target_release) > current:
            continue
        max_total = target.get("max_import_references")
        if isinstance(max_total, int) and total_imports > max_total:
            violations.append(
                f"release {release}: total deprecated import references {total_imports} exceeds target {max_total} ({target_release})"
            )
        module_caps = target.get("module_max_import_references", {})
        for module, limit in sorted(module_caps.items()):
            count = len(import_references.get(module, set()))
            if count > int(limit):
                violations.append(
                    f"release {release}: {module} import references {count} exceeds target {limit} ({target_release})"
                )
    return violations


def _render_matrix(import_references: dict[str, set[Path]], release: str) -> str:
    targets = _MANIFEST.get("reduction_targets", {})
    current = _parse_version(release)
    applicable_target_release = None
    for candidate in sorted(targets, key=_parse_version):
        if _parse_version(candidate) <= current:
            applicable_target_release = candidate
    target_modules = (targets.get(applicable_target_release) or {}).get("module_max_import_references", {})

    lines = [
        "# Legacy Module Deprecation Matrix",
        "",
        f"Generated by `scripts/check_deprecated_references.py --release {release} --write-matrix`.",
        "",
        "| Legacy module | Sunset version | Import references (current) | Import cap (current target) | Allowed referencers | Status |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]

    for module in sorted(DEPRECATED_MODULES):
        module_data = _MANIFEST["legacy_modules"][module]
        count = len(import_references.get(module, set()))
        cap = target_modules.get(module, "—")
        allowed_count = len(module_data.get("allowed_referencers", []))
        status = "within boundary"
        if isinstance(cap, int) and count > cap:
            status = "target exceeded"
        lines.append(
            f"| `{module}` | `{module_data['sunset_version']}` | {count} | {cap} | {allowed_count} | {status} |"
        )

    lines.extend(
        [
            "",
            "## Reduction targets",
            "",
            "| Release | Max total import references |",
            "| --- | ---: |",
        ]
    )
    for target_release, target in sorted(targets.items(), key=lambda item: _parse_version(item[0])):
        lines.append(f"| `{target_release}` | {target.get('max_import_references', '—')} |")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", default="v0.17.0")
    parser.add_argument("--write-matrix", action="store_true")
    args = parser.parse_args(argv)

    all_refs, import_refs = _scan_reference_maps()
    violations = _boundary_violations(all_refs)
    violations.extend(_reduction_violations(import_refs, args.release))

    if args.write_matrix:
        MATRIX_PATH.write_text(_render_matrix(import_refs, args.release), encoding="utf-8")

    if violations:
        raise SystemExit("\n".join(violations))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
