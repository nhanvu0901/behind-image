"""Quality scorecard, contact sheets, and render record (design 2026-11-27 section 6)."""
from __future__ import annotations

from .build import is_stale, load_record, load_scorecard, make_for_project, scorecard_dir
from .metrics import SCHEMA, compute_metrics
from .record import RECORD_SCHEMA, build_record
from .render import record_md, scorecard_md
from .sheets import render_sheets, shot_sample_time
from .targets import DEFAULT_TARGETS, load_targets

__all__ = [
    "DEFAULT_TARGETS",
    "RECORD_SCHEMA",
    "SCHEMA",
    "build_record",
    "compute_metrics",
    "is_stale",
    "load_record",
    "load_scorecard",
    "load_targets",
    "make_for_project",
    "record_md",
    "render_sheets",
    "scorecard_dir",
    "scorecard_md",
    "shot_sample_time",
]
