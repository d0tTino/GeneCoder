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



def test_canonical_simple_indel_modules_exist() -> None:
    simple = importlib.import_module("genecoder.simulators.simple")
    indel = importlib.import_module("genecoder.simulators.indel")

    assert hasattr(simple, "register")
    assert hasattr(indel, "register")


def test_canonical_simulator_modules_are_not_deprecated_shims() -> None:
    deprecated_prefixes = ("genecoder.compat",)
    deprecated_exact = {"genecoder.error_simulation", "genecoder.channel_sim"}

    for module_name in ("genecoder.simulators.simple", "genecoder.simulators.indel"):
        module = importlib.import_module(module_name)
        assert module.__name__ == module_name
        assert module.__name__ not in deprecated_exact
        assert not module.__name__.startswith(deprecated_prefixes)
