from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path("src/genecoder")

LEGACY_MODULES = {
    "genecoder.pipeline",
    "genecoder.api",
    "genecoder.channel_sim",
}

APPROVED_LEGACY_IMPORTERS = {
    "genecoder.pipeline",
    "genecoder.api",
    "genecoder.channel_sim",
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


def _all_imports() -> dict[str, set[str]]:
    data: dict[str, set[str]] = {}
    for path in SRC_ROOT.rglob("*.py"):
        data[_module_name(path)] = _imports_for(path)
    return data


def _is_interface_module(module: str) -> bool:
    return module.startswith(("genecoder.cli", "genecoder.dashboard", "genecoder.sdk"))


def _is_domain_module(module: str) -> bool:
    return module.startswith(("genecoder.coding", "genecoder.constraints", "genecoder.simulators"))


def _is_application_module(module: str) -> bool:
    return module.startswith("genecoder.app")


def _is_infrastructure_module(module: str) -> bool:
    return module.startswith("genecoder.plugin_runtime") or module.endswith("_adapter")


def test_interfaces_do_not_import_legacy_modules() -> None:
    violations: list[str] = []
    for module, imports in _all_imports().items():
        if not _is_interface_module(module):
            continue
        if module in APPROVED_LEGACY_IMPORTERS:
            continue
        bad = sorted(i for i in imports if i in LEGACY_MODULES)
        if bad:
            violations.append(f"{module} imports {bad}")
    assert not violations, "\n".join(violations)


def test_only_compat_adapters_can_import_legacy_modules() -> None:
    violations: list[str] = []
    for module, imports in _all_imports().items():
        bad = sorted(i for i in imports if i in LEGACY_MODULES)
        if not bad:
            continue
        if module not in APPROVED_LEGACY_IMPORTERS:
            violations.append(f"{module} imports {bad}")
    assert not violations, "\n".join(violations)


def test_layer_dependencies_follow_direction() -> None:
    violations: list[str] = []
    for module, imports in _all_imports().items():
        if _is_domain_module(module):
            for imported in imports:
                if _is_interface_module(imported) or _is_application_module(imported):
                    violations.append(f"domain module {module} depends on {imported}")
        if _is_application_module(module):
            for imported in imports:
                if _is_interface_module(imported):
                    violations.append(f"application module {module} depends on {imported}")
        if _is_infrastructure_module(module):
            for imported in imports:
                if _is_interface_module(imported):
                    violations.append(f"infrastructure module {module} depends on {imported}")
    assert not violations, "\n".join(violations)
