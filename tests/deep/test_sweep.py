"""Technique sweep: every one of the 78 registry techniques through the API, as the editing page uses it.
Defaults -> draft -> validate -> three stills across the span; plus a 3 s preview for 22 of them (all transitions and
cards included). Uses a copy of technique_lab as the reference configuration of each technique; the seven techniques of the channel
identity (`ID-*`) have no reference in technique_lab, so the fixture adds one for each to the COPY (never to the tracked project)."""
from __future__ import annotations

import pytest

import sweep
from conftest import put_sb, state, strip

PREVIEW_SAMPLE = {"X-TR-01", "X-TR-02", "TR-01", "TR-02", "TR-03", "TR-04", "X-CARD-01", "X-CARD-02", "X-CARD-03", "X-CARD-04",
                  "CAM-01", "CAM-05", "LAY-01", "LAY-03", "HI-01", "HI-02", "AN-01", "AN-06", "STATIC-01", "DIA-01",
                  "CMP-03", "SHORT-01"}
# problems that come from how the sweep samples, not from the product (see BUGS_backend.md, "Technique sweep")
BENIGN = ("required slots not filled",)
BENIGN_BY_ID = {"X-CARD-01": ("uniform/blank frame",),          # the card text leaves at 1.7 s, the rest of the shot is black
                "AN-01": ("overlay with default params changes nothing",)}   # the reference overlay's span is outside the camera
# the opening starts at 10 % brightness and its light only starts to travel at 17 % of its span: the sweep's first sample (12 %) is dark by design
# (std about 1.9 against the blank-frame limit of 2). Only that sample is let through; the other two must still be pictures.
FIRST_SAMPLE_DARK = {"ID-OPEN-01"}


def _identity_references(sb: dict) -> dict:
    """A reference configuration for each `ID-*` technique, after the last shot of the lab: four cards of 3 s (the two channel-name beats
    and the two chapter marks) and one 12 s host shot that carries the three overlays (the two openings and the label)."""
    sb = strip(sb)
    asset = "arn_A"
    t = float(sb["end"]["t"])
    for k, tid in enumerate(("ID-BRAND-01", "ID-BRAND-02", "ID-MARK-01", "ID-MARK-02")):
        sb["shots"].append({"id": "s9%03d" % k, "start": {"t": round(t, 3)}, "technique": tid, "slots": {"image": {"asset": asset}}, "params": {},
                            "intent": "structure", "transition_in": None, "overlays": [], "locked": False, "source": "import", "note": tid + " reference"})
        t += 3.0
    ov = [("ID-OPEN-01", 0.0, 9.0), ("ID-OPEN-02", 1.0, 5.0), ("ID-LABEL-01", 5.0, 4.5)]
    sb["shots"].append({"id": "s9100", "start": {"t": round(t, 3)}, "technique": "CAM-01", "slots": {"image": {"asset": asset}}, "params": {},
                        "intent": "explore", "transition_in": None, "locked": False, "source": "import", "note": "host of the identity overlays",
                        "overlays": [{"id": "o%d" % (n + 1), "technique": tid, "intent": "structure", "start": {"t": round(t + a, 3)}, "dur": d, "params": {},
                                      "slots": {}, "locked": False, "source": "import", "note": ""} for n, (tid, a, d) in enumerate(ov)]})
    sb["end"] = {"t": round(t + 12.0, 3), "fade_s": 0}
    return sb


@pytest.fixture(scope="module")
def lab_state(client, projects_root, data_root):
    import shutil
    from conftest import _clone
    _clone(projects_root / "technique_lab", projects_root / "sweep_lab")
    st = state(client, "sweep_lab")
    r = put_sb(client, "sweep_lab", _identity_references(st["storyboard"]), st["rev"])
    assert r.status_code == 200, r.text
    st = state(client, "sweep_lab")
    reg = client.get("/api/styles/gae").json()["techniques"]
    yield strip(st["storyboard"]), st["storyboard"], reg
    shutil.rmtree(projects_root / "sweep_lab", ignore_errors=True)


def test_registry_has_78_techniques(lab_state):
    reg = lab_state[2]
    assert len(reg) == len(_ids()) == 78                 # 71 of the channel's look and the seven `ID-*` of the identity
    assert {t["kind"] for t in reg} == {"base", "overlay", "transition", "card"}
    assert len([t for t in reg if t["id"].startswith("ID-")]) == 7


def test_the_lab_has_a_reference_for_every_technique(lab_state):
    """The sweep must draw all of them: a technique without a reference would be reported as a problem, never skipped."""
    sb, rs, reg = lab_state
    missing = []
    for tech in reg:
        try:
            sweep.locate(sb, tech)
        except LookupError:
            missing.append(tech["id"])
    assert missing == []


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
    allowed = BENIGN + BENIGN_BY_ID.get(tid, ())
    if tid in FIRST_SAMPLE_DARK:
        kind, i, j = sweep.locate(sb, tech)
        allowed += ("uniform/blank frame at t=%s " % sweep.sample_times(rs, kind, i, j)[0],)
    problems = [p for p in rec["problems"] if not any(p.startswith(b) for b in allowed)]
    if tid in ("STATIC-08", "X-ANN-03"):
        problems = [p for p in problems if "changes nothing" not in p]   # B-007 has its own test
    assert not problems, problems
    assert rec["errors"] == []
    assert all(v[1] <= sweep.WARM_LIMIT_MS for k, v in rec["timings_ms"].items() if k != "defaults"), rec["timings_ms"]
    if tid in PREVIEW_SAMPLE:
        pv = sweep.preview_one(client, tech, sb, rs, rec, pid="sweep_lab")
        assert "error" not in pv, pv
        assert abs(pv["duration"] - 3.0) < 0.05 and pv["frames"] == 45 or tid == "X-LAY-01", pv   # X-LAY-01: B-029
