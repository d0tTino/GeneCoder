from __future__ import annotations

import ast
from pathlib import Path

DEPRECATED_IMPORTS = {"genecoder.api", "genecoder.pipeline"}

APPROVED_TEST_FILES = {
    Path("tests/test_pipeline_legacy.py"),
    Path("tests/test_sdk.py"),
}

SEARCH_ROOTS = (Path("tests"), Path("src/plugins"), Path("plugins-examples"))


def _extract_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_no_new_deprecated_imports_outside_compatibility_suite() -> None:
    violations: list[str] = []
    for root in SEARCH_ROOTS:
        for path in root.rglob("*.py"):
            if path in APPROVED_TEST_FILES:
                continue
            imports = _extract_imports(path)
            bad = sorted(name for name in imports if name in DEPRECATED_IMPORTS)
            if bad:
                violations.append(f"{path}: {bad}")

    assert not violations, "\n".join(violations)
