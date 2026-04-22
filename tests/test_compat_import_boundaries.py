from __future__ import annotations

import ast
from pathlib import Path

COMPAT_ROOT = Path("src/genecoder/compat")

NON_FORWARDER_COMPAT_MODULES = {
    Path("src/genecoder/compat/legacy/cloud/worker.py"),
    Path("src/genecoder/compat/v1/pipeline_adapter.py"),
}


def _is_docstring_expr(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_warning_call(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        (
            isinstance(func, ast.Attribute)
            and func.attr == "warn"
            and isinstance(func.value, ast.Name)
            and func.value.id == "warnings"
        )
        or (isinstance(func, ast.Name) and func.id == "warn_with_telemetry")
    )


def _is_all_export_assignment(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assign):
        return all(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == "__all__"
    return False


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to("src").with_suffix("").parts)


def test_compat_modules_are_forwarders_only() -> None:
    violations: list[str] = []
    for path in COMPAT_ROOT.rglob("*.py"):
        if path in NON_FORWARDER_COMPAT_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if _is_docstring_expr(node):
                continue
            if _is_warning_call(node):
                continue
            if _is_all_export_assignment(node):
                continue
            violations.append(f"{_module_name(path)}:{node.__class__.__name__}")
    assert not violations, "\n".join(violations)


def test_runtime_does_not_depend_on_compat_module_logic() -> None:
    violations: list[str] = []
    for path in Path("src/genecoder").rglob("*.py"):
        if path.is_relative_to(COMPAT_ROOT):
            continue
        module = _module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module] if node.module else []
            else:
                continue
            if any(name and name.startswith("genecoder.compat") for name in imports):
                violations.append(f"{module} imports {imports}")
                break
    assert not violations, "\n".join(violations)
