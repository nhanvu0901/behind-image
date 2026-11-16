"""Technique sweep: every one of the 71 registry techniques through the API, as the editing page uses it.
Defaults -> draft -> validate -> three stills across the span; plus a 3 s preview for 22 of them (all transitions and
cards included). Uses a copy of technique_lab as the reference configuration of each technique."""
from __future__ import annotations

import pytest

import sweep
from conftest import state, strip

PREVIEW_SAMPLE = {"X-TR-01", "X-TR-02", "TR-01", "TR-02", "TR-03", "TR-04", "X-CARD-01", "X-CARD-02", "X-CARD-03", "X-CARD-04",
                  "CAM-01", "CAM-05", "LAY-01", "LAY-03", "HI-01", "HI-02", "AN-01", "AN-06", "STATIC-01", "DIA-01",
                  "CMP-03", "SHORT-01"}
# problems that come from how the sweep samples, not from the product (see BUGS_backend.md, "Technique sweep")
BENIGN = ("required slots not filled",)
BENIGN_BY_ID = {"X-CARD-01": ("uniform/blank frame",),          # the card text leaves at 1.7 s, the rest of the shot is black
                "AN-01": ("overlay with default params changes nothing",)}   # the reference overlay's span is outside the camera


@pytest.fixture(scope="module")
def lab_state(client, projects_root, data_root):
    import shutil
    from conftest import _clone
    _clone(projects_root / "technique_lab", projects_root / "sweep_lab")
    st = state(client, "sweep_lab")
    reg = client.get("/api/styles/gae").json()["techniques"]
    yield strip(st["storyboard"]), st["storyboard"], reg
    shutil.rmtree(projects_root / "sweep_lab", ignore_errors=True)


def test_registry_has_71_techniques(lab_state):
    reg = lab_state[2]
    assert len(reg) == 71
    assert {t["kind"] for t in reg} == {"base", "overlay", "transition", "card"}


def _ids():
    import json
    from pathlib import Path
    reg = json.loads((Path(__file__).resolve().parents[2] / "style" / "gae" / "techniques.json").read_text())
    return [t["id"] for t in (reg["techniques"] if isinstance(reg, dict) else reg)]


@pytest.mark.parametrize("tid", _ids())
def test_technique(client, lab_state, tid):
    sb, rs, reg = lab_state
    tech = next(t for t in reg if t["id"] == tid)
    rec = sweep.sweep_one(client, tech, sb, rs, pid="sweep_lab")
    problems = [p for p in rec["problems"] if not any(p.startswith(b) for b in BENIGN + BENIGN_BY_ID.get(tid, ()))]
    if tid in ("STATIC-08", "X-ANN-03"):
        problems = [p for p in problems if "changes nothing" not in p]   # B-007 has its own test
    assert not problems, problems
    assert rec["errors"] == []
    assert all(v[1] <= 300 for k, v in rec["timings_ms"].items() if k != "defaults"), rec["timings_ms"]
    if tid in PREVIEW_SAMPLE:
        pv = sweep.preview_one(client, tech, sb, rs, rec, pid="sweep_lab")
        assert "error" not in pv, pv
        assert abs(pv["duration"] - 3.0) < 0.05 and pv["frames"] == 45 or tid == "X-LAY-01", pv   # X-LAY-01: B-029
