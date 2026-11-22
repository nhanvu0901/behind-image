"""Fixtures of the draft tests: a small synthetic project (two chapters, six beats, two pictures) and a copy of the real arnolfini
project's files. Nothing here touches the real projects/ folder, the network or a model."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import make_synth_project  # noqa: E402


@pytest.fixture()
def proj(tmp_path):
    return make_synth_project(tmp_path / "projects" / "synth")


@pytest.fixture()
def proj_title_card(tmp_path):
    return make_synth_project(tmp_path / "projects" / "synthtitle", gap=7.0)


@pytest.fixture()
def arnolfini(tmp_path):
    """The real arnolfini storyboard, timing and pictures, copied to a temp folder, with picks built from its storyboard."""
    src = REPO / "projects" / "arnolfini"
    if not (src / "storyboard.json").is_file():
        pytest.skip("projects/arnolfini is not on this machine")
    dst = tmp_path / "projects" / "arnolfini"
    dst.mkdir(parents=True)
    shutil.copytree(src / "media", dst / "media")
    shutil.copyfile(src / "timing.json", dst / "timing.json")
    shutil.copyfile(src / "storyboard.json", dst / "storyboard.json")
    sb = json.loads((src / "storyboard.json").read_text(encoding="utf-8"))
    beats = {}
    tm = json.loads((src / "timing.json").read_text(encoding="utf-8"))
    for i, b in enumerate(tm["beats"], 1):
        beats["b%04d" % i] = {"items": [], "status": "todo"}
    (dst / "picks.json").write_text(json.dumps({"schema": "bti.picks/1", "main_asset": "A", "assets": sb["assets"], "beats": beats,
                                                 "approval": {"approved": True}}), encoding="utf-8")
    return dst


@pytest.fixture()
def box(tmp_path, monkeypatch):
    """The prompt box on typed operations, through the app, on a copy of the `tests/ops` fixture project (worker c2box)."""
    import box_helpers as BH
    b = BH.make_box(tmp_path, monkeypatch)
    yield b
    BH.cleanup(b)


@pytest.fixture(autouse=True)
def _fake_viewer_for_other_draft_tests(request, monkeypatch):
    """Existing edit tests exercise editing; replace its follow-up viewer with a clean fake.

    Dedicated viewer tests exercise the real orchestration with fake frames and
    providers. No draft test should render real frames or call a model.
    """
    if request.node.path.name == "test_viewer_review.py":
        return
    import json
    from bti.draft import review
    from bti.editor.common import compute_rev
    from bti.longjob import Part

    def fake_after(project_dir, model, turn_id):
        def run(ctx):
            from bti.draft.thread import load_thread
            turn = next((t for t in load_thread(project_dir) if t.get("id") == turn_id), None)
            if turn and turn.get("status") == "applied":
                sb = json.loads((project_dir / "storyboard.json").read_text(encoding="utf-8"))
                review.save_report(project_dir, {"revision": compute_rev(sb), "rounds": 0, "warnings": [], "history": []})
        return [Part(key="fake_viewer", title="Xem lại giả", run=run)]
    monkeypatch.setattr(review, "after_full_edit_parts", fake_after)
