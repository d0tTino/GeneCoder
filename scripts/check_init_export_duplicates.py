from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "genecoder"


def _literal_exports(node: ast.AST, names: dict[str, object]) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        exports: list[str] = []
        for elt in node.elts:
            exports.extend(_literal_exports(elt, names))
        return exports
    if isinstance(node, ast.Name):
        value = names.get(node.id)
        if isinstance(value, str):
            return [value]
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            named_exports: list[str] = []
            for item in value:
                if not isinstance(item, str):
                    raise ValueError(f"Unsupported non-string export via name {node.id!r}")
                named_exports.append(item)
            return named_exports
        raise ValueError(f"Unsupported export reference {node.id!r}")
    if isinstance(node, ast.Starred):
        return _literal_exports(node.value, names)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in {"sorted", "list", "tuple", "set"} and len(node.args) == 1:
            values = _literal_exports(node.args[0], names)
            if node.func.id == "sorted":
                return sorted(values)
            if node.func.id == "set":
                return list(dict.fromkeys(values))
            return values
        raise ValueError("Unsupported callable used in __all__")
    raise ValueError(f"Unsupported __all__ element: {ast.dump(node, include_attributes=False)}")


def _assigned_names(tree: ast.Module) -> dict[str, object]:
    names: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            names[target.id] = ast.literal_eval(node.value)
        except Exception:
            continue
    return names


def _load_exports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = _assigned_names(tree)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        return _literal_exports(node.value, names)
    return []


def find_duplicate_exports() -> list[str]:
    failures: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("__init__.py")):
        exports = _load_exports(path)
        duplicates = sorted({name for name in exports if exports.count(name) > 1})
        if duplicates:
            rel_path = path.relative_to(ROOT)
            failures.append(f"{rel_path}: duplicate exports {', '.join(duplicates)}")
    return failures


def main() -> int:
    failures = find_duplicate_exports()
    if failures:
        print("Duplicate __all__ entries found in package exports:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
