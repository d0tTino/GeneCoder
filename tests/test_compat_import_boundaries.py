from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path("src/genecoder")

DEPRECATED_COMPAT_FACADES = {
    "genecoder.compat",
    "genecoder.compat.v1",
    "genecoder.compat.channel_sim",
    "genecoder.compat.error_simulation",
}

ALLOWED_IMPORTERS = {
    "genecoder.channel_sim",
    "genecoder.error_simulation",
    "genecoder.pipeline",
    "genecoder.api",
    "genecoder.simulators.channel_cli_adapter",
    "genecoder.cli.channel",
    "genecoder.app.pipeline_runtime",
    "genecoder.compat.v1.pipeline_adapter",
    "genecoder.compat.v1.api_adapter",
}


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to("src").with_suffix("").parts)


def _resolve_from(module: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    parts = module.split(".")
    anchor = parts[:-node.level]
    if node.module:
        anchor.extend(node.module.split("."))
    return ".".join(anchor) if anchor else None


def _imports_for(path: Path) -> set[str]:
    module = _module_name(path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_from(module, node)
            if resolved:
                imports.add(resolved)
    return imports


def test_only_boundary_modules_import_compatibility_facades() -> None:
    violations: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        module = _module_name(path)
        imports = _imports_for(path)
        bad = sorted(i for i in imports if i in DEPRECATED_COMPAT_FACADES)
        if bad and module not in ALLOWED_IMPORTERS and not module.startswith("genecoder.compat"):
            violations.append(f"{module} imports {bad}")
    assert not violations, "\n".join(violations)
