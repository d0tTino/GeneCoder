"""Check that dependency attributions stay in sync with pyproject.toml.

Update notes:
- When adding, removing, or renaming dependencies in pyproject.toml, update the
  NOTICE (or THIRD_PARTY.md) file so the new dependency appears in the
  attribution list.
- If a dependency is an extra that is intentionally not bundled (for example,
  an optional runtime that users install themselves), add it to
  NON_BUNDLED_EXTRAS_ALLOWLIST below with a short comment explaining why.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"
ATTRIBUTION_FILES = [Path("NOTICE"), Path("THIRD_PARTY.md")]

# Dependencies that are intentionally excluded from attribution because they
# are non-bundled extras. Keep this list small and documented.
NON_BUNDLED_EXTRAS_ALLOWLIST = {
    "torch",  # Optional deep learning runtime installed separately by users.
}


def _normalize_name(name: str) -> str:
    return re.sub(r"[_.-]+", "-", name).lower()


def _load_pyproject_dependencies() -> set[str]:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    poetry = data.get("tool", {}).get("poetry", {})

    dependencies: set[str] = set()

    for name in poetry.get("dependencies", {}).keys():
        if name == "python":
            continue
        dependencies.add(_normalize_name(name))

    for group in poetry.get("group", {}).values():
        for name in group.get("dependencies", {}).keys():
            dependencies.add(_normalize_name(name))

    for extra_deps in poetry.get("extras", {}).values():
        for name in extra_deps:
            dependencies.add(_normalize_name(name))

    return dependencies


def _load_attribution_text() -> str:
    contents: list[str] = []
    for path in ATTRIBUTION_FILES:
        if path.exists():
            contents.append(path.read_text(encoding="utf-8"))
    return "\n".join(contents)


def _attribution_mentions(name: str, attribution_text: str) -> bool:
    normalized_text = _normalize_name(attribution_text)
    pattern = rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def test_dependencies_have_attributions() -> None:
    dependencies = _load_pyproject_dependencies()
    attribution_text = _load_attribution_text()

    assert attribution_text.strip(), (
        "Expected NOTICE or THIRD_PARTY.md to exist and contain attributions."
    )

    missing = sorted(
        dep
        for dep in dependencies
        if dep not in NON_BUNDLED_EXTRAS_ALLOWLIST
        and not _attribution_mentions(dep, attribution_text)
    )

    assert not missing, (
        "Missing dependency attributions in NOTICE/THIRD_PARTY.md: "
        + ", ".join(missing)
    )
