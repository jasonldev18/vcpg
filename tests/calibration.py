"""Calibration loaders live in backend/audit/testsets.py; these names keep the tests short."""

from backend.audit.testsets import gate_sets, reviewer_cases, slide_bundles

STYLES = {
    "strong",
    "shallow",
    "wrong_but_confident",
    "off_topic",
    "partially_right",
    "copied_jargon",
}

__all__ = ["STYLES", "gate_sets", "reviewer_cases", "slide_bundles"]
