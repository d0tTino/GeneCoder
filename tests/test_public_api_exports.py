from __future__ import annotations

import importlib
import pkgutil

import genecoder


def _top_level_public_api_packages() -> list[str]:
    packages = [genecoder.__name__]
    for module_info in pkgutil.iter_modules(genecoder.__path__, prefix=f"{genecoder.__name__}."):
        if module_info.ispkg:
            packages.append(module_info.name)
    return sorted(packages)


def test_top_level_public_api_exports_are_unique() -> None:
    for package_name in _top_level_public_api_packages():
        module = importlib.import_module(package_name)
        exports = getattr(module, "__all__", None)
        if exports is None:
            continue
        assert len(exports) == len(set(exports)), package_name
