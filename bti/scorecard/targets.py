"""Quality targets read from the style's `quality` block (`style/<id>/style.json`)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLE_RE = re.compile(r"[a-z0-9_-]{1,32}")

DEFAULT_TARGETS: dict[str, float | int] = {
    "small_painting_max_share": 0.06,
    "small_painting_cover_threshold": 0.70,
    "marks_per_min_max": 3.0,
    "mark_max_height_pct": 0.30,
    "marks_on_person_max": 0,
    "strip_sub_repeats_max": 0,
    "strip_on_thing_max": 0,
    "borrowed_min_s": 3.0,
    "borrowed_max_gap_s": 120.0,
    "short_shot_min_s": 2.5,
    "short_shots_max": 0,
    "region_repeat_max": 4,
    "subject_not_shown_max": 0,
    "unfilled_identity_max": 0,
    "identity_fill_min_cover": 0.95,
    "loudness_target_lufs": -15.0,
    "loudness_tolerance_lu": 1.5,
    "pause_under_speech_min_db": 6.0,
    "pause_under_speech_max_db": 22.0,
}


def _unwrap(v: Any) -> Any:
    if isinstance(v, dict) and "value" in v:
        return v["value"]
    return v


def load_targets(style_id: str = "gae", style_root: Path | None = None) -> dict[str, float | int]:
    """Load the `quality` block from `style/<style_id>/style.json`, falling back to `DEFAULT_TARGETS`."""
    out: dict[str, float | int] = dict(DEFAULT_TARGETS)
    sid = style_id if isinstance(style_id, str) and STYLE_RE.fullmatch(style_id) else "gae"
    root = Path(style_root) if style_root is not None else (REPO_ROOT / "style")
    path = root / sid / "style.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    compose = doc.get("compose", {}) if isinstance(doc, dict) else {}
    if isinstance(compose, dict) and isinstance(compose.get("marks_per_min_max"), (int, float)):
        out["marks_per_min_max"] = float(compose["marks_per_min_max"])
    block = doc.get("quality") if isinstance(doc, dict) else None
    if not isinstance(block, dict):
        return out
    for k, default in DEFAULT_TARGETS.items():
        if k not in block or (k == "marks_per_min_max" and "marks_per_min_max" in compose):
            continue
        raw = _unwrap(block[k])
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            out[k] = int(raw) if isinstance(default, int) and isinstance(raw, int) else float(raw)
    return out
