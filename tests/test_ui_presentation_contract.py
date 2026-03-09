from __future__ import annotations

from genecoder.app.ui_dto import UIPresentationPayload
from genecoder import dashboard, dashboard_streamlit
import pytest

flet_handlers = pytest.importorskip("genecoder.flet_handlers")


def _sample_metrics() -> dict[str, object]:
    return {
        "constraint_violations": {"limits": {"gc_min": 0.45, "gc_max": 0.55, "max_homopolymer": 5}},
        "oligo_metrics": {
            "gc_percentages": [0.4, 0.5],
            "max_homopolymers": [4, 6],
            "dropout_flags": [0, 1],
            "ecc_success": {"rs": [1.0, 0.5]},
        },
    }


def test_flet_streamlit_dashboard_use_identical_presentation_payload() -> None:
    metrics = _sample_metrics()
    payload = UIPresentationPayload.from_metrics(metrics)

    assert dashboard._extract_oligo_records(metrics) == [dict(r) for r in payload.oligo_records]
    assert dashboard_streamlit._extract_oligo_records(metrics) == [dict(r) for r in payload.oligo_records]
    assert flet_handlers._constraint_limits_from_payload(metrics) == (
        payload.constraint_limits.gc_min,
        payload.constraint_limits.gc_max,
        payload.constraint_limits.max_homopolymer,
    )
    assert dashboard._constraint_limits(metrics) == (
        payload.constraint_limits.gc_min,
        payload.constraint_limits.gc_max,
        payload.constraint_limits.max_homopolymer,
    )
    assert dashboard_streamlit._constraint_limits(metrics) == (
        payload.constraint_limits.gc_min,
        payload.constraint_limits.gc_max,
        payload.constraint_limits.max_homopolymer,
    )
