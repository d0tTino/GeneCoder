import pytest

ft = pytest.importorskip("flet")

from genecoder.glossary_tooltips import wrap_glossary_terms


def test_wrap_glossary_terms_basic():
    glossary = {"GC content": "desc", "Homopolymer": "info"}
    row = wrap_glossary_terms(
        "Check GC content and Homopolymer issues", glossary
    )
    assert isinstance(row, ft.Row)
    tips = [getattr(c, "tooltip", None) for c in row.controls]
    assert [t for t in tips if t] == ["desc", "info"]


def test_wrap_glossary_terms_no_match():
    glossary = {"GC content": "desc"}
    row = wrap_glossary_terms("No terms here", glossary)
    assert isinstance(row, ft.Row)
    assert len(row.controls) == 1
    assert isinstance(row.controls[0], ft.Text)
