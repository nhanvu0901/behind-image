"""Fixtures of the identity tests: the real Arnolfini storyboard and timing of the draft tests (`tests/draft/fixtures/arnolfini_live`)
and a small FAKE identity block, so that the applier is tested on its own (no registry entries, no renderer needed)."""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

FIXTURE = REPO / "tests" / "draft" / "fixtures" / "arnolfini_live"

FAKE_STYLE = {
    "matte": {"painting_height_pct": {"value": 95.5, "source": "test"}},
    "identity": {
        "channel_name": "RAKING LIGHT",
        "default_style": "raking",
        "styles": {
            "raking": {"label_vi": "Vệt sáng quét", "open": "ID-OPEN-01", "label": "ID-LABEL-01", "brand": "ID-BRAND-01", "mark": "ID-MARK-01"},
            "dim": {"label_vi": "Tối lại, hiện tên", "open": "ID-OPEN-02", "brand": "ID-BRAND-02", "mark": "ID-MARK-02",
                    "mark_transition": {"technique": "TR-01", "dur": 0.75}},
        },
    },
}


@pytest.fixture()
def style():
    return copy.deepcopy(FAKE_STYLE)


@pytest.fixture()
def sb():
    return json.loads((FIXTURE / "storyboard.json").read_text(encoding="utf-8"))


@pytest.fixture()
def timing():
    return json.loads((FIXTURE / "timing.json").read_text(encoding="utf-8"))


@pytest.fixture()
def tm(timing):
    from bti.engine.timing import Timing
    return Timing({"duration": timing["duration"], "words": timing["words"]})
