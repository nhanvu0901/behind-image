"""TXT-01, TXT-02, STATIC-04/05/07, X-CARD-03/04, FOOT-01 against projects/lab_text (and the reel for the six that have a segment)."""
import copy
import sys
import time

import numpy as np
import pytest

from bti.engine import registry as R
from bti.engine.api import open_project
from bti.engine.techniques import _t3common as C
from conftest import REPO

IDS = ["TXT-01", "TXT-02", "STATIC-04", "STATIC-05", "STATIC-07", "X-CARD-03", "X-CARD-04", "FOOT-01"]
LAB = REPO / "projects" / "lab_text"
pytestmark = pytest.mark.skipif(not (LAB / "storyboard.json").exists(), reason="lab_text missing")


@pytest.fixture()
def lab():
    return open_project(LAB)


def psnr(a, b):
    m = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return 99.0 if m == 0 else 10 * np.log10(255 ** 2 / m)


def test_lab_validates_and_all_ids_available(lab):
    assert [i for i in lab.validate(lab.storyboard()) if i["level"] == "error"] == []
    for t in IDS:
        assert lab.bundle.available(t), t


@pytest.mark.parametrize("t", [1.0, 7.0, 14.0, 19.5, 25.0, 30.0, 36.0, 42.0, 49.0, 54.0, 60.0, 66.0])
def test_lab_frames_render_and_are_deterministic(lab, t):
    a = lab.frame_at(t, 480)
    b = open_project(LAB).frame_at(t, 480)
    assert a.shape == (270, 480, 3) and np.array_equal(a, b)


def test_default_params_validate_with_and_without_context(lab):
    ctx = {"asset": "A", "text": "Some text", "region": "MIRROR"}
    for tid in IDS:
        spec = lab.bundle.spec(tid)
        for c in ({}, ctx):
            p = lab.default_params(tid, c)
            assert [i for i in R.validate_params(spec, p, tid) if i["level"] == "error"] == [], tid


def test_registry_consistent():
    from bti.engine import techniques  # noqa: F401
    problems = R.check_registry(R.load_bundle("gae"))
    assert [x for x in problems if x.split(":")[0] in IDS] == []


def _draft(lab, idx, **upd):
    sb = copy.deepcopy(lab.storyboard())
    sb["shots"][idx]["params"].update(upd)
    lab.use_draft(sb)
    return sb


def test_empty_and_offcanvas_text_never_crash(lab):
    sb = copy.deepcopy(lab.storyboard())
    sb["shots"][0]["params"]["title"] = ""
    sb["shots"][1]["overlays"][0]["params"].update(lines=[], speed_px_s=1500)
    sb["shots"][2]["overlays"][0]["params"].update(quote="", attribution="x")
    sb["shots"][3]["overlays"][0]["params"].update(name="", role="")
    sb["shots"][4]["params"].update(labels=[], centers=[])
    sb["shots"][5]["params"]["credit_text"] = ""
    sb["shots"][6]["params"].update(text="", x_pct=-50, y_pct=95)
    lab.use_draft(sb)
    for t in (1.0, 7.0, 14.0, 19.5, 25.0, 30.0, 36.0):
        assert lab.frame_at(t, 320).shape == (180, 320, 3)


def test_scroll_direction_and_motion(lab):
    a, b = lab.frame_at(6.0, 480), lab.frame_at(7.0, 480)
    assert not np.array_equal(a, b)
    sb = copy.deepcopy(lab.storyboard())
    sb["shots"][1]["overlays"][0]["params"]["direction"] = "left_to_right"
    lab.use_draft(sb)
    assert not np.array_equal(lab.frame_at(7.0, 480), b)


def test_quote_wraps_to_width():
    lines = C.wrap("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda", "serif_it", 70, 1, 600)
    assert len(lines) > 2 and all(C.text_width(l, "serif_it", 70, 1) <= 600 or " " not in l for l in lines)
    assert C.wrap("", "reg", 40, 0, 500) == []


def test_white_card_variant_is_white_with_brown_text(lab):
    f = lab.frame_at(42.0, 640)
    assert f[0, 0].min() > 250 and (f.reshape(-1, 3).min(0) < 150).all()


def test_footage_source_time_behaviours(lab):
    # exercise through frames: hold = last frame repeats, loop returns to the start, slow keeps moving
    def frames(idx, key, val, ts):
        s = copy.deepcopy(lab.storyboard())
        s["shots"][idx]["params"][key] = val
        s["shots"][idx]["params"]["push_zoom"] = 1.0
        s["shots"][idx]["overlays"] = []
        s["shots"][idx]["params"]["label"] = ""
        s["shots"][idx]["params"]["source_text"] = ""
        lab.use_draft(s)
        return [lab.frame_at(t, 320).astype(int) for t in ts]
    h = frames(8, "end_behavior", "hold", (51.0, 51.8))             # clip is 3 s, in-point 0.2: past 3 s it holds
    assert np.array_equal(h[0], h[1])
    s_ = frames(8, "end_behavior", "slow", (51.0, 51.8))
    assert not np.array_equal(s_[0], s_[1])
    lp = frames(9, "end_behavior", "loop", (52.0, 52.0 + 3.0 / 1.5))   # one loop of the 3 s clip at speed 1.5
    assert np.abs(lp[0] - lp[1]).mean() < 2.0


def test_footage_push_changes_frame_and_contain_shows_ambient(lab):
    a = lab.frame_at(46.5, 320).astype(int)
    b = lab.frame_at(51.5, 320).astype(int)
    assert np.abs(a - b).mean() > 1
    f = lab.frame_at(54.0, 320)                       # vertical clip contained: side bands are not black but blurred ambient
    assert f[:, :20].max() > 5


def test_warm_still_is_fast(lab):
    for t in (1.0, 22.5, 34.5):
        lab.frame_at(t, 960)
        t0 = time.time()
        lab.frame_at(t, 960)
        assert time.time() - t0 < 0.5, t
    # the engine cost of a card is a copy + one blend


reel_dir = REPO / ".scratch" / "r1"


@pytest.mark.skipif(not (reel_dir / "build_reel.py").exists(), reason="reel copy missing")
def test_matches_the_reel_frames(lab):
    sys.path[:0] = [str(reel_dir), str(reel_dir / "lib")]
    try:
        import build_reel as br
        from bti.engine import vfx
        br.S()
        seg = {e["id"]: e for e in br.SEG}
        orig = br.view
        br.view = lambda img, cx, cy, z, w=br.W, h=br.H: br.compose_matte(img, cx, cy, z, w, h)   # engine bases sit on the designed matte
        for tid, off, x in (("TXT-01", 0.0, 1.0), ("TXT-01", 0.0, 3.0), ("TXT-02", 5.0, 2.0), ("TXT-02", 5.0, 5.0), ("STATIC-04", 11.0, 0.5),
                            ("STATIC-04", 11.0, 3.0), ("STATIC-05", 17.0, 1.2), ("STATIC-05", 17.0, 2.5), ("STATIC-07", 22.0, 1.0), ("STATIC-07", 22.0, 5.5)):
            ref = vfx.to_u8(seg[tid]["fn"](x, seg[tid]["dur"]))
            assert psnr(lab.frame_at(off + x, 1920), ref) >= 40, (tid, x)
    finally:
        br.view = orig
        del sys.path[:2]
