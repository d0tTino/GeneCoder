from __future__ import annotations


from scripts.check_deprecated_references import APPROVED_REFERENCERS, DEPRECATED_MODULES, SEARCH_ROOTS, _extract_references


def test_no_new_deprecated_references_outside_approved_shims() -> None:
    violations: list[str] = []
    for root in SEARCH_ROOTS:
        for path in root.rglob("*.py"):
            if path in APPROVED_REFERENCERS:
                continue
            bad = sorted(name for name in _extract_references(path) if name in DEPRECATED_MODULES)
            if bad:
                violations.append(f"{path}: {bad}")

    assert not violations, "\n".join(violations)
