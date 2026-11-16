import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from bti.engine import registry as R  # noqa: E402
from bti.engine.api import open_project  # noqa: E402

LAB = REPO / "projects" / "lab_diagrams"
IDS = ["DIA-01", "DIA-02", "DIA-03", "DIA-04", "DIA-05", "DIA-06", "SHORT-01", "SHORT-02", "SHORT-03", "SHORT-04", "SHORT-05"]
pytestmark = pytest.mark.skipif(not (LAB / "storyboard.json").exists(), reason="lab_diagrams missing")


@pytest.fixture(scope="module")
def lab():
    p = open_project(LAB)
    return p, json.loads((LAB / "starts.json").read_text()) if (LAB / "starts.json").exists() else _starts(p)


def _starts(p):
    sb = json.loads((LAB / "storyboard.json").read_text())
    out = {}
    for s in sb["shots"]:
        tid = s["overlays"][0]["technique"] if s["overlays"] else s["technique"]
        out[tid] = s["start"]["t"]
    return out


def frame(lab, tid, u):
    p, st = lab
    return p.frame_at(st[tid] + u + 1e-4, 1920)


def test_lab_validates_and_all_ids_registered(lab):
    p, _ = lab
    assert not [i for i in p.validate() if i["level"] == "error"]
    b = p.bundle
    assert R.check_registry(b) == []
    for i in IDS:
        assert b.available(i), i


def test_default_params_valid_with_and_without_context(lab):
    p, _ = lab
    for tid in IDS:
        for ctx in ({}, {"asset": "A", "region": "MIRROR", "text": "A LABEL"}):
            d = p.default_params(tid, ctx)
            spec = p.bundle.spec(tid)
            assert not R.validate_params(spec, d, tid), (tid, ctx)


def test_frames_deterministic_and_nonblank(lab):
    for tid, u in [("DIA-01", 4.0), ("DIA-03", 4.0), ("DIA-04", 3.5), ("SHORT-01", 3.0), ("SHORT-05", 3.0)]:
        a, b = frame(lab, tid, u), frame(lab, tid, u)
        assert a.shape == (1080, 1920, 3)
        assert np.array_equal(a, b)
        assert a.std() > 3


def test_motion_changes_frames(lab):
    for tid, u0, u1 in [("DIA-01", 1.2, 3.0), ("DIA-02", 1.0, 3.5), ("DIA-03", 2.0, 4.0), ("DIA-04", 0.5, 3.0), ("DIA-05", 1.0, 4.5),
                        ("DIA-06", 1.0, 3.5), ("SHORT-01", 0.5, 1.9), ("SHORT-02", 1.0, 4.0), ("SHORT-03", 0.5, 2.5), ("SHORT-05", 0.1, 2.5)]:
        assert np.abs(frame(lab, tid, u0).astype(int) - frame(lab, tid, u1).astype(int)).mean() > 0.2, tid


def test_short02_has_no_edge_streaks(lab):
    f = frame(lab, "SHORT-02", 4.0)[:, 656:1264].astype(float)
    # rows in the lower empty part of the warped quad must be flat (constant fill), not vertical streaks of replicated pixels
    band = f[960:1040]
    assert band.std(axis=1).mean() < 6


def test_short04_text_inside_box(lab):
    a, b = frame(lab, "SHORT-04", 0.5).astype(int), frame(lab, "SHORT-04", 2.0).astype(int)
    diff = np.abs(a - b).sum(-1) > 30
    ys, xs = np.where(diff)
    assert ys.size > 50
    assert ys.min() >= 930 and ys.max() <= 1010 and xs.min() >= 686 and xs.max() <= 1234


def test_short_warm_still_is_fast(lab):
    for tid in ("SHORT-01", "SHORT-02", "SHORT-03", "SHORT-05"):
        frame(lab, tid, 1.0)
        t0 = time.time()
        frame(lab, tid, 2.2)
        assert time.time() - t0 < 0.15, tid


def test_dia03_layers_param_and_measure(lab):
    p, st = lab
    sb = p.storyboard()
    import copy
    d = copy.deepcopy(sb)
    for s in d["shots"]:
        if s["technique"] == "DIA-03":
            s["params"] = {"layers": ["TOP | #ff0000 | 100", "BOTTOM | #0000ff | 100"], "measure_text": "40 um", "ray_count": 2}
    p.use_draft(d)
    try:
        f = p.frame_at(st["DIA-03"] + 5.5, 1920)
        assert f.std() > 5
    finally:
        p.use_draft(None) if hasattr(p, "use_draft") else None


def test_reel_equivalence_when_reel_available(lab):
    reel = REPO / ".scratch" / "t4" / "reel_frames.py"
    if not (REPO / ".scratch" / "r1" / "build_reel.py").exists() or not reel.exists():
        pytest.skip("reel not available")
    sys.path.insert(0, str(REPO / ".scratch" / "t4"))
    from reel_frames import reel as reel_frame
    for tid, u in [("DIA-01", 3.0), ("DIA-03", 5.0), ("DIA-04", 3.0), ("DIA-06", 4.0), ("SHORT-03", 1.0)]:
        a, b = frame(lab, tid, u).astype(float), reel_frame(tid, u).astype(float)
        mse = ((a - b) ** 2).mean()
        assert mse == 0 or 10 * np.log10(255 ** 2 / mse) >= 40, tid
