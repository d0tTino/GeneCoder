from __future__ import annotations

import ast
from pathlib import Path

DEPRECATED_MODULES = {
    "genecoder.api",
    "genecoder.pipeline",
    "genecoder.compat.channel_cli",
    "genecoder.compat.channel_sim",
    "genecoder.compat.error_simulation",
    "genecoder.compat.legacy",
    "genecoder.compat.legacy.sequence_pipeline",
    "genecoder.compat.legacy.channel_adapter_exports",
    "genecoder.compat.legacy.cloud",
    "genecoder.compat.legacy.cloud.worker",
    "genecoder.compat.v1",
    "genecoder.compat.v1.api_adapter",
    "genecoder.compat.v1.pipeline_adapter",
}

APPROVED_REFERENCERS = {
    Path("src/genecoder/api.py"),
    Path("src/genecoder/pipeline.py"),
    Path("src/genecoder/channel_sim.py"),
    Path("src/genecoder/compat/__init__.py"),
    Path("src/genecoder/compat/channel_cli.py"),
    Path("src/genecoder/compat/channel_sim.py"),
    Path("src/genecoder/compat/error_simulation.py"),
    Path("src/genecoder/compat/legacy/__init__.py"),
    Path("src/genecoder/compat/legacy/channel_adapter_exports.py"),
    Path("src/genecoder/compat/legacy/sequence_pipeline.py"),
    Path("src/genecoder/compat/legacy/cloud/__init__.py"),
    Path("src/genecoder/compat/legacy/cloud/worker.py"),
    Path("src/genecoder/compat/v1/__init__.py"),
    Path("src/genecoder/compat/v1/api_adapter.py"),
    Path("src/genecoder/compat/v1/pipeline_adapter.py"),
    Path("tests/test_deprecated_import_boundaries.py"),
    Path("tests/test_compat_import_boundaries.py"),
    Path("tests/test_pipeline_legacy.py"),
    Path("tests/test_sdk.py"),
    Path("tests/test_architecture_boundaries.py"),
    Path("tests/test_cli_channel.py"),
    Path("tests/test_cloud_worker_offline.py"),
    Path("tests/test_deprecated_module_telemetry.py"),
    Path("tests/test_pipeline_kpi_bundle.py"),
    Path("tests/test_worker_metrics.py"),
    Path("tests/test_worker_security.py"),
    Path("plugins-examples/starter_plugin/starter_plugin/__init__.py"),
    Path("scripts/check_deprecated_references.py"),
}

SEARCH_ROOTS = (Path("src"), Path("tests"), Path("plugins-examples"), Path("scripts"))


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


def main() -> int:
    violations: list[str] = []
    for root in SEARCH_ROOTS:
        for path in root.rglob("*.py"):
            if path in APPROVED_REFERENCERS:
                continue
            bad = sorted(name for name in _extract_references(path) if name in DEPRECATED_MODULES)
            if bad:
                violations.append(f"{path}: {bad}")
    if violations:
        raise SystemExit("\n".join(violations))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
