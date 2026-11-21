"""ID-BRAND-03: the channel-name beat that also writes the video's title (docs/design/2026-11-18-identity-raking-light.md, section 4b).

Same manner as test_identity.py: real frames of a project whose picture is FLAT grey (brightness is then the light alone) or black (every
bright pixel is text), the state of the beat at the times that matter, the nominal timeline scaled on a shorter and a longer shot, the two
sweeps and what each of them writes, and a guard that ID-BRAND-01 (and the text lines of the other identity techniques) still draw exactly
the bytes they drew before ID-BRAND-03 existed.
Run on the Windows server in a snapshot (never on the Mac): tools/deploy/snapshot_test.sh introengine -- tests/engine/test_identity_brand_title.py -q
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from bti.engine import base, registry as R
from bti.engine.techniques import identity as ID
from bti.engine.vfx import Band
from conftest import REPO
from test_identity import CAM_FULL, GREY, H, W, at, gradient, make_lab, ov, renderer, shot

TID = "ID-BRAND-03"
TITLE = "The Saint Who Was Also an Advertisement"
SUB = "St. Eligius · Petrus Christus, 1449"
TITLE70 = "The Goldsmith, the Bride and the Mirror That Saw Everything Behind Her"
LINES = {"title": TITLE, "subtitle": SUB}
NOMINAL = 9.1                 # 0.5 + 1.6 + 2.4 + 1.6 + 3.0
NOMINAL_ALONE = 4.5           # 0.5 + 1.6 + 2.4
T_SWEEP2 = 4.5                # the second sweep starts here (nominal seconds) and ends at 6.1
CONTRACT_DEFAULTS = {
    "camera": None, "shadow": True, "text": "RAKING LIGHT", "title": "", "subtitle": "", "dim_s": 0.6, "floor": 0.12, "wake": 0.26,
    "sweep_delay_s": 0.5, "sweep_s": 1.6, "name_hold_s": 2.4, "title_sweep_s": 1.6, "title_hold_s": 3.0, "direction": "left_to_right",
    "band_width_pct": 16, "feather": 0.4, "angle_deg": 10, "warm": 0.14, "cap_pct": 8.0, "tracking_pct": 25, "y_pct": 36, "y_alone_pct": 42,
    "title_cap_pct": 4.6, "title_y_pct": 54, "sub_cap_pct": 2.2, "sub_tracking_pct": 14, "sub_y_pct": 62.5}
BRAND01_DEFAULTS = {   # ID-BRAND-01 as it was before ID-BRAND-03 existed: its params and its defaults must not change
    "camera": None, "shadow": True, "text": "RAKING LIGHT", "dim_s": 0.6, "floor": 0.12, "wake": 0.26, "sweep_delay_s": 0.6, "sweep_s": 2.4,
    "direction": "left_to_right", "band_width_pct": 16, "feather": 0.4, "angle_deg": 10, "warm": 0.14, "cap_pct": 8.0, "tracking_pct": 25,
    "y_pct": 42, "nominal_s": 5.0}


def lab(tmp_path, extra=None, length=NOMINAL, name="lab", level=GREY, **kw):
    """The beat alone as the first shot, a plain CAM-01 shot after it so that the beat lasts `length` seconds."""
    return make_lab(tmp_path, [shot(1, 0.0, TID, extra), shot(2, length, "CAM-01")], name=name, level=level, end=length + 10.0, **kw)


def nominal_of(params):
    """The nominal length the technique's own formula gives for a set of params (the registry's defaults under the given ones)."""
    p = R.merged_params(R.load_bundle("gae").spec(TID), params)
    n = p["sweep_delay_s"] + p["sweep_s"] + p["name_hold_s"]
    return n + (p["title_sweep_s"] + p["title_hold_s"] if (p["title"].strip() or p["subtitle"].strip()) else 0.0)


def ink(frame, y0=0.0, y1=1.0, thr=128):
    """Mask of the bright (text) pixels of a frame of a BLACK picture, rows from y0 to y1 (fractions of the height) only."""
    m = frame.max(axis=2) > thr
    out = np.zeros_like(m)
    out[int(y0 * H):int(y1 * H)] = m[int(y0 * H):int(y1 * H)]
    return out


def box(mask):
    ys, xs = np.nonzero(mask)
    assert xs.size, "no text drawn"
    return xs.min(), xs.max(), ys.min(), ys.max()


# ----------------------------------------------------------------------------- registry
def test_the_registry_lists_the_technique_with_complete_defaults():
    b = R.load_bundle("gae")
    from bti.engine import techniques  # noqa: F401
    assert R.check_registry(b) == []
    s = b.spec(TID)
    assert s and b.available(TID) and len(s["description"]) > 30 and len(s["usage_rule"]) > 30
    assert s["label_vi"] == "Tên kênh và tựa video: vệt sáng quét" and s["category"] == "card" and s["kind"] == "base" and s["intents"] == ["structure"]
    assert s["engine"]["impl"] == "bti.engine.techniques.identity.BrandTitle" and R.RENDERERS[TID] == (ID.BrandTitle, "base")
    assert s["slots"] == [{"name": "image", "type": "image", "required": True, "region": True}]
    assert s["timing"] == {"default_s": 9.1, "min_s": 1.5, "max_s": 30.0, "anchor": "shot_start"}
    assert {p["name"]: p["default"] for p in s["params"]} == CONTRACT_DEFAULTS and len(s["params"]) == len(CONTRACT_DEFAULTS)
    for p in s["params"]:
        if p["type"] == "number":
            assert p["min"] is not None and p["max"] is not None and p["min"] <= p["default"] <= p["max"] and p["unit"], p["name"]
        if p["type"] == "string":
            assert p["pattern"] and p["pattern_hint"], p["name"]
    assert (REPO / "style/gae" / s["preview"]["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / s["preview"]["thumb"]).stat().st_size > 1000
    assert [t["id"] for t in b.techniques].count(TID) == 1 and "Tên kênh và tựa video" in (REPO / "bti/editor/static/js/labels.js").read_text(encoding="utf-8")


def test_default_params_take_the_channel_name_from_the_style_and_the_camera_of_the_picture(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01")])
    d = p.default_params(TID, {"asset": "G"})
    assert d["text"] == "RAKING LIGHT" and d["title"] == "" and d["subtitle"] == ""
    assert [k["at"] for k in d["camera"]] == [{"rel": 0.0}, {"rel": 1.0}] and d["camera"][1]["zoom"] / d["camera"][0]["zoom"] == pytest.approx(1.03, rel=1e-3)
    assert p.default_params(TID, {})["camera"] is None
    spec = R.load_bundle("gae").spec(TID)
    assert [i for i in R.validate_params(spec, p.default_params(TID, {"asset": "G", "text": "T"}), TID) if i["level"] == "error"] == []
    assert [i for i in R.validate_params(spec, dict(d, **LINES), TID) if i["level"] == "error"] == []


def test_id_brand_01_is_as_it_was():
    b = R.load_bundle("gae")
    s = b.spec("ID-BRAND-01")
    assert {p["name"]: p["default"] for p in s["params"]} == BRAND01_DEFAULTS and s["timing"]["default_s"] == 5.0
    assert s["engine"]["impl"] == "bti.engine.techniques.identity.BrandRaking" and R.RENDERERS["ID-BRAND-01"][0] is ID.BrandRaking
    assert ID.BrandRaking.__mro__[1] is ID._BandBase and ID.BrandTitle.__mro__[1] is ID._BandBase


# ----------------------------------------------------------------------------- the timeline
def test_the_nominal_length_depends_on_whether_there_is_a_second_sweep(tmp_path):
    for name, extra, nominal in (("both", LINES, NOMINAL), ("title", {"title": TITLE}, NOMINAL), ("sub", {"subtitle": SUB}, NOMINAL), ("none", {}, NOMINAL_ALONE),
                                 ("blank", {"title": "  ", "subtitle": ""}, NOMINAL_ALONE),
                                 ("custom", dict(LINES, sweep_delay_s=1.0, sweep_s=2.0, name_hold_s=1.0, title_sweep_s=2.5, title_hold_s=0.5), 7.0),
                                 ("custom_alone", {"sweep_delay_s": 1.0, "sweep_s": 2.0, "name_hold_s": 1.0, "title_sweep_s": 2.5, "title_hold_s": 0.5}, 4.0)):
        p = lab(tmp_path, extra, name=name)
        assert renderer(p, 1.0).nominal == pytest.approx(nominal), name


def test_the_state_of_the_beat_at_the_times_that_matter(tmp_path):
    p = lab(tmp_path, LINES)
    r = renderer(p, 1.0)
    state = r.state
    dim = lambda tau: 1.0 - 0.88 * ID.ss01(tau, 0.0, 0.6)
    s = state(0.0)                                                               # starts on the picture, nothing written
    assert (s.q_name, s.q_title, s.q_light, s.ahead, s.behind) == (0.0, 0.0, 0.0, 1.0, 1.0)
    s = state(0.3)                                                               # dimming: halfway, smoothstep 0.5
    assert s.ahead == pytest.approx(dim(0.3)) == pytest.approx(0.56) and s.behind == pytest.approx(0.56) and s.q_name == 0.0
    s = state(0.55)                                                              # the first band has just entered its run-in
    assert 0.0 < s.q_name < 0.05 and s.q_title == 0.0 and s.ahead == pytest.approx(dim(0.55))
    s = state(1.3)                                                               # first sweep, halfway: ahead at the floor, behind at the wake
    assert s.q_name == pytest.approx(0.5) and s.q_light == pytest.approx(0.5) and s.q_title == 0.0 and (s.ahead, s.behind) == (pytest.approx(0.12), pytest.approx(0.26))
    s = state(2.11)                                                              # the first sweep ends
    assert s.q_name == 1.0 and s.q_light == 1.0 and s.q_title == 0.0
    for t in (2.5, 3.3, 4.49):                                                   # the name is written and nothing moves
        s = state(t)
        assert (s.q_name, s.q_title, s.q_light) == (1.0, 0.0, 1.0) and s.behind == pytest.approx(0.26), t
    s = state(4.4999)                                                            # the instant before the second band starts: still the first one's end state
    assert (s.q_name, s.q_title, s.q_light) == (1.0, 0.0, 1.0)
    s = state(4.5001)                                                            # the second band starts: the picture is at the wake on both sides
    assert s.q_name == 1.0 and s.q_title == pytest.approx(0.0001 / 1.6) and s.q_light == s.q_title and s.ahead == pytest.approx(0.26) == pytest.approx(s.behind)
    s = state(5.3)                                                               # second sweep, halfway
    assert s.q_name == 1.0 and s.q_title == pytest.approx(0.5) and s.q_light == pytest.approx(0.5) and s.ahead == pytest.approx(0.26) == pytest.approx(s.behind)
    s = state(6.11)                                                              # the second sweep ends
    assert s.q_title == 1.0 and s.q_light == 1.0
    for t in (6.5, 8.0, 9.099):                                                  # everything is held until the shot ends
        s = state(t)
        assert (s.q_name, s.q_title, s.q_light) == (1.0, 1.0, 1.0) and s.behind == pytest.approx(0.26), t
    assert state(12.0)[1:] == state(9.099)[1:]                                   # a longer shot holds the last state


def test_without_lines_there_is_no_second_sweep(tmp_path):
    p = lab(tmp_path, {}, length=12.0)
    s = renderer(p, 1.0).state
    assert s(4.4)[1:] == s(11.0)[1:] and s(4.4).q_title == 0.0 and s(4.6).q_light == 1.0 and s(6.0).behind == pytest.approx(0.26)
    f = lambda t: p.frame_at(t, W)
    assert np.array_equal(f(4.6), f(5.5)) and np.array_equal(f(5.5), f(11.0))     # nothing moves after the name is written
    assert np.allclose(at(f(5.5), 100, 100), 0.26 * GREY, atol=1.5) and np.allclose(at(f(5.5), 1800, 1000), 0.26 * GREY, atol=1.5)


def test_light_on_a_flat_picture_before_during_and_after_each_sweep(tmp_path):
    p = lab(tmp_path, LINES)
    f = lambda t: p.frame_at(t, W)
    plain = make_lab(tmp_path, [shot(1, 0.0, "CAM-01")], name="plain").frame_at(0.0, W)
    assert np.array_equal(f(0.0), plain)                                           # starts on the picture
    f06 = f(0.6)
    assert f06.min() == f06.max() and abs(float(f06[0, 0, 0]) - 0.12 * GREY) < 1.01   # dimmed to the floor, the band not yet on the canvas
    mid1 = f(1.3)                                                                  # first sweep, halfway, left to right: ahead = right, behind = left
    assert np.allclose(at(mid1, 1800, 1000), 0.12 * GREY, atol=1.5) and np.allclose(at(mid1, 100, 1000), 0.26 * GREY, atol=1.5)
    assert at(mid1, 879, 1000)[2] > GREY + 5                                       # inside the band: lifted above the picture, warm
    for t in (3.3, 4.4):                                                           # the hold after the name: the whole picture at the wake
        held = f(t)
        assert np.allclose(at(held, 100, 100), 0.26 * GREY, atol=1.5) and np.allclose(at(held, 1800, 1000), 0.26 * GREY, atol=1.5), t
    assert np.array_equal(f(4.4), f(4.5))                                          # the second band is still off the canvas: nothing changed
    mid2 = f(5.3)                                                                  # second sweep, halfway: the wake on BOTH sides, the band the only light
    assert np.allclose(at(mid2, 100, 1000), 0.26 * GREY, atol=1.5) and np.allclose(at(mid2, 1800, 1000), 0.26 * GREY, atol=1.5)
    assert np.allclose(at(mid2, 100, 300), 0.26 * GREY, atol=1.5) and at(mid2, 879, 1000)[2] > GREY + 5
    after = f(6.4)                                                                 # after the second band: back to the wake, held to the end
    assert np.allclose(at(after, 100, 1000), 0.26 * GREY, atol=1.5) and np.allclose(at(after, 1800, 1000), 0.26 * GREY, atol=1.5)
    assert np.array_equal(f(6.4), f(9.05)) and f(9.05).max() > 200                 # the text is on screen at the end


def test_a_shorter_and_a_longer_shot(tmp_path):
    for tag, extra, nominal in (("lines", LINES, NOMINAL), ("alone", {}, NOMINAL_ALONE)):
        short = lab(tmp_path, extra, length=nominal / 2, name="s" + tag)
        full = lab(tmp_path, extra, length=nominal, name="f" + tag)
        assert renderer(short, 0.5).k == 0.5 and renderer(full, 1.0).k == 1.0
        for frac in (0.08, 0.15, 0.31, 0.46, 0.55, 0.62, 0.8, 0.95):               # half the length: every time halves (both sweeps, both holds)
            assert np.array_equal(short.frame_at(frac * nominal / 2, W), full.frame_at(frac * nominal, W)), (tag, frac)
    three = lab(tmp_path, LINES, length=3.0, name="three")                         # a 3 s shot: both sweeps happen in it
    k = 3.0 / NOMINAL
    s = renderer(three, 0.5).state
    assert renderer(three, 0.5).k == pytest.approx(k) and s(2.99).q_title == 1.0 and 0.0 < s(2.0).q_title < 1.0 and s(1.3 * k).q_name == pytest.approx(0.5)
    long = lab(tmp_path, LINES, length=14.0, name="long")                          # a longer shot keeps the nominal times and holds the last state
    full = lab(tmp_path, LINES, name="full2")
    assert renderer(long, 1.0).k == 1.0
    for t in (0.4, 1.3, 3.0, 5.3, 8.0):
        assert np.array_equal(long.frame_at(t, W), full.frame_at(t, W)), t
    assert np.array_equal(long.frame_at(9.5, W), long.frame_at(13.9, W))


# ----------------------------------------------------------------------------- what is written, where, and when
def test_the_name_sits_at_36_percent_with_a_title_line_and_at_42_without(tmp_path):
    with_lines = lab(tmp_path, LINES, level=0, name="a")
    alone = lab(tmp_path, {}, level=0, name="b")
    x0, x1, y0, y1 = box(ink(with_lines.frame_at(3.3, W)))
    assert (y0 + y1) / 2 == pytest.approx(0.36 * H, abs=5) and (x0 + x1) / 2 == pytest.approx(W / 2, abs=3) and 0.08 * H - 3 <= y1 - y0 + 1 <= 0.08 * H * 1.15 + 3
    x0, x1, y0, y1 = box(ink(alone.frame_at(3.3, W)))
    assert (y0 + y1) / 2 == pytest.approx(0.42 * H, abs=5) and (x0 + x1) / 2 == pytest.approx(W / 2, abs=3)


def test_the_name_does_not_move_between_the_two_phases(tmp_path):
    p = lab(tmp_path, LINES, level=0)
    rows = slice(0, int(0.46 * H))                                                   # the rows of the name only (the title starts below 0.50)
    ref = p.frame_at(3.3, W)[rows].astype(int)
    m0 = ref.max(axis=2) > 128
    assert m0.sum() > 600
    cy0, cx0 = np.argwhere(m0).mean(0)
    for t in (4.6, 6.5, 9.0):                                                        # the band is off the canvas: the very same pixels
        assert np.array_equal(p.frame_at(t, W)[rows].astype(int), ref), t
    for t in (4.9, 5.0, 5.3, 5.8):                                                   # the second band is over the name: only its warm light (at most 36 on black) differs
        f = p.frame_at(t, W)[rows].astype(int)
        assert np.abs(f - ref).max() <= 37, t
        m = f.max(axis=2) > 128
        cy, cx = np.argwhere(m).mean(0)
        assert abs(cy - cy0) < 1.0 and abs(cx - cx0) < 1.0 and abs(int(m.sum()) - int(m0.sum())) < 0.03 * m0.sum(), t     # the same ink: same place (a move would be tens of px), same amount
    assert np.array_equal(p.frame_at(3.3, W), p.frame_at(4.4, W))                   # and nothing at all changes during the hold before the second sweep


def test_the_lines_sit_where_the_params_say_and_are_set_as_given(tmp_path):
    p = lab(tmp_path, {"title": "HHHH", "subtitle": "hhhh"}, level=0)                # capitals only: the rows are the cap height
    f = p.frame_at(9.0, W)
    x0, x1, y0, y1 = box(ink(f, 0.47, 0.59))
    assert (y0 + y1) / 2 == pytest.approx(0.54 * H, abs=3) and y1 - y0 + 1 == pytest.approx(0.046 * H, abs=3) and (x0 + x1) / 2 == pytest.approx(W / 2, abs=8)
    x0, x1, y0, y1 = box(ink(f, 0.59, 0.70))                                         # the small line is in capitals even when given in lower case
    assert (y0 + y1) / 2 == pytest.approx(0.625 * H, abs=3) and y1 - y0 + 1 == pytest.approx(0.022 * H, abs=2.5) and (x0 + x1) / 2 == pytest.approx(W / 2, abs=4)
    r = renderer(lab(tmp_path, {"title": "Written as Given", "subtitle": "st. eligius"}, name="given"), 1.0)
    same = lambda text, kind, cap, trk, y, kern: ID.ink_layer(r.ctx, text, kind, cap, trk, centre_pct=y, max_w_pct=ID.TITLE_MAX_W_PCT, shadow=True, kern=kern)
    assert r.title_layer is same("Written as Given", "eb_italic", 4.6, 0.0, 54.0, True) and r.title_layer is not same("WRITTEN AS GIVEN", "eb_italic", 4.6, 0.0, 54.0, True)
    assert r.sub_layer is same("ST. ELIGIUS", "eb_regular", 2.2, 14.0, 62.5, False)


def test_one_line_alone_is_written_at_its_own_place(tmp_path):
    both = lab(tmp_path, {"title": "HHHH", "subtitle": "HHHH"}, level=0, name="both").frame_at(9.0, W)
    only_t = lab(tmp_path, {"title": "HHHH"}, level=0, name="t").frame_at(9.0, W)
    only_s = lab(tmp_path, {"subtitle": "HHHH"}, level=0, name="s").frame_at(9.0, W)
    assert np.array_equal(ink(only_t, 0.47, 0.59), ink(both, 0.47, 0.59)) and not ink(only_t, 0.59, 0.70).any()
    assert np.array_equal(ink(only_s, 0.59, 0.70), ink(both, 0.59, 0.70)) and not ink(only_s, 0.47, 0.59).any()
    for f in (only_t, only_s):                                                      # the name did not move to make room, and the beat is still 9.1 s long
        assert np.array_equal(ink(f, 0.0, 0.46), ink(both, 0.0, 0.46))
    assert renderer(lab(tmp_path, {"title": "HHHH"}, name="t2"), 1.0).nominal == NOMINAL


@pytest.mark.parametrize("t_a, t_b", [(5.1, 5.3), (5.3, 5.5)])
def test_the_title_is_revealed_along_the_second_band(tmp_path, t_a, t_b):
    """The narrow band (4 % of the width) has a front, a middle and a wake over the text; the title (and the small line) is drawn only
    behind the band's front: a pixel of the title left of the band (it moves left to right) is written, one right of it is not."""
    p = lab(tmp_path, dict(LINES, band_width_pct=4), level=0)
    rowsel = np.zeros((H, W), bool)
    rowsel[int(0.47 * H):int(0.70 * H)] = True                                       # the rows of the title and the small line
    done = p.frame_at(9.0, W).max(axis=2).astype(int)
    band = Band(W, H, 4, 0.4, 10, "left_to_right")
    xs, ys = np.arange(W, dtype=np.float32) + 0.5, np.arange(H, dtype=np.float32) + 0.5
    counts = []
    for t in (t_a, t_b):
        s = band.s_grid((t - T_SWEEP2) / 1.6, xs, ys)
        mid = p.frame_at(t, W).max(axis=2).astype(int)
        ahead, behind = rowsel & (s > band.core / 2 + band.edge + 8), rowsel & (s < -band.half - 8)   # not yet reached / fully passed
        assert mid[ahead].max() == 0, "text (or its shadow) drawn ahead of the band"
        assert np.abs(mid - done)[behind].max() <= 2, "text behind the band is not fully written"
        assert ((done > 100) & ahead).any() and ((done > 100) & behind).any()          # the probe is meaningful: the text spans both sides
        counts.append(int(((mid > 100) & rowsel).sum()))
    assert 0 < counts[0] < counts[1] < int(((done > 100) & rowsel).sum())              # the writing only grows, and is not finished yet


def test_nothing_of_the_lines_is_written_before_the_second_band(tmp_path):
    p = lab(tmp_path, LINES, level=0)
    for t in (3.3, 4.4, 4.5, 4.6):
        assert not ink(p.frame_at(t, W), 0.47, 0.70, thr=60).any(), t
    assert ink(p.frame_at(6.3, W), 0.47, 0.70).any()


# ----------------------------------------------------------------------------- long lines
@pytest.mark.parametrize("title", [TITLE70, "W" * 70, "i" * 70, "The Goldsmith, the Bride and the Mirror " * 2 + "That Saw All"])
def test_a_long_title_is_made_smaller_and_stays_inside_the_frame(tmp_path, title):
    assert len(TITLE70) == 70
    p = lab(tmp_path, {"title": title.strip(), "subtitle": SUB}, level=0)
    f = p.frame_at(9.0, W)
    x0, x1, y0, y1 = box(ink(f, 0.47, 0.59, thr=100))
    assert x0 >= 0.07 * W and x1 <= 0.93 * W, (x0, x1)                                # margins of at least 7 % on each side: never cut, never run off
    assert (x0 + x1) / 2 == pytest.approx(W / 2, abs=10)                              # still centred
    assert y1 - y0 < 0.09 * H, "one line, not wrapped"
    if title == TITLE70:
        assert x1 - x0 > 0.70 * W                                                     # shrunk to fit, not shrunk beyond need
        short = renderer(lab(tmp_path, {"title": TITLE, "subtitle": SUB}, name="short"), 1.0).title_layer
        assert renderer(p, 1.0).title_layer.a.shape[0] < short.a.shape[0]             # the long one is set smaller than the short one
    sx0, sx1, _, _ = box(ink(f, 0.59, 0.70, thr=100))
    assert sx0 >= 0.07 * W and sx1 <= 0.93 * W


def test_the_longest_lines_the_registry_accepts_stay_inside_the_frame(tmp_path):
    p = lab(tmp_path, {"title": "Wm" * 60, "subtitle": "Wm" * 60}, level=0)
    f = p.frame_at(9.0, W)
    x0, x1, y0, y1 = box(ink(f, 0.45, 0.70, thr=60))
    assert x0 >= 0.05 * W and x1 <= 0.95 * W


# ----------------------------------------------------------------------------- the kerning of the title
def test_pair_kerning_is_read_from_the_font_and_only_used_when_asked(tmp_path):
    k = ID._kerning("eb_italic")
    assert k is not None and k.upem == 1000
    assert k.pair("W", "a") == -140 and k.pair("T", "y") == -60 and k.pair("T", "h") == 0 and k.pair("日", "a") == 0 and k.pair("W", "\u0001") == 0
    assert ID._kerning("eb_regular") is not None and ID._kerning("nonexistent_face") is None
    r = renderer(lab(tmp_path, {"title": "Was"}, name="k"), 1.0)
    on = ID.ink_layer(r.ctx, "Was Wa", "eb_italic", 4.6, 0.0, centre_pct=54.0, kern=True)
    off = ID.ink_layer(r.ctx, "Was Wa", "eb_italic", 4.6, 0.0, centre_pct=54.0)
    assert on.a.shape[1] < off.a.shape[1] - 10                                       # two "Wa" pairs: about 2 x 10 px closer at this size
    assert ID.ink_layer(r.ctx, "Was Wa", "eb_italic", 4.6, 0.0, centre_pct=54.0, kern=False) is off


# ----------------------------------------------------------------------------- purity, params
def test_a_frame_is_a_pure_function_of_time(tmp_path):
    p = lab(tmp_path, LINES, length=12.0)
    times = [8.0, 1.3, 5.3, 0.2, 4.55, 6.5, 3.3, 11.0]
    first = {t: p.frame_at(t, 640) for t in times}
    base.LAYERS.clear(); base.IMAGES.clear(); base.MISC.clear()
    for t in reversed(times):
        assert np.array_equal(p.frame_at(t, 640), first[t]), t


def test_every_param_at_min_and_max_draws(tmp_path):
    """Each number at its registry min and max (the others at their defaults, a title and a small line given), at four moments."""
    spec = R.load_bundle("gae").spec(TID)
    n = 0
    for pd in spec["params"]:
        values = [pd["min"], pd["max"]] if pd["type"] == "number" else (pd["values"] if pd["type"] == "enum" else ([False] if pd["type"] == "bool" else []))
        for v in values:
            extra = dict(LINES, **{pd["name"]: v})
            nominal = nominal_of(extra)
            p = make_lab(tmp_path, [shot(1, 0.0, TID, extra), shot(2, max(nominal, 1.5), "CAM-01")], name="p%d" % n, end=40.0)
            n += 1
            for frac in (0.1, 0.4, 0.7, 0.97):
                assert p.frame_at(frac * max(nominal, 1.5), 320).shape == (180, 320, 3), (pd["name"], v, frac)
    assert n >= 40


@pytest.mark.parametrize("title, sub", [("", ""), (" ", " "), ("é" * 3, "é"), ("Ệ ư ơ ă â đ", "Đối"), ("x" * 120, "y" * 120), ("日本語", "日本"),
                                         ("Wa Wa Wa", "T. T. T.")])
def test_odd_text_draws(tmp_path, title, sub):
    p = make_lab(tmp_path, [shot(1, 0.0, TID, {"title": title, "subtitle": sub}), shot(2, 4.0, TID, {"title": title, "subtitle": sub, "shadow": False}, camera=CAM_FULL),
                            shot(3, 14.0, "CAM-01")], end=20.0)
    for t in (1.0, 2.8, 5.5, 8.0, 12.0):
        assert p.frame_at(t, 480).shape == (270, 480, 3)


# ----------------------------------------------------------------------------- the older identity techniques draw what they drew before
GOLDEN = {
    "brand01@0": "92f60c7aef06ebdd66ff0176f9b4f40960a4497eeffd48361b0674d3f6922ebc",
    "brand01@0.3": "a4064fb999c5023fc34eaaf99285e840bc5b4937e163867f47fa4f896e6297e5",
    "brand01@0.9": "c7864da9bec5037acf1c0b4bb2bf7334c87fc5c16dc479185091e2146d3de2f2",
    "brand01@1.8": "f74271adbda98bef7a235ad2fafb9926c48473f0ef5050a58501cca4a6c56fa0",
    "brand01@2.7": "f89df799fa571cf1794bb49a356773762afa084c883446eedf4b2f044f463cc3",
    "brand01@3.3": "96b51619c9e730747ef021d47de1c923d626b63c4a630b592ee76173b8f1a4cc",
    "brand01@4.9": "62fdbf2dc49be9ccdc532251d67856bb174964e69a76e6680589363738b93e2c",
    "brand01_rtl@1.7": "615e37f75f53c56682cbadb84a465e64071c7e3b65cd060a8c2968abcb8af107",
    "brand01_rtl@4.2": "e8246ca4f0fbdb4f8264ba37da1ce86b7ee1edb6f6c2914ebfd0f93e3e25b46a",
    "mark01@0.8": "801e6303247d82dc4d1b09a1c162cf1067ce9e3b64994acff68c40a6c6656370",
    "mark01@1.5": "40127522a65b917f7db2eef7b1a4c0a68c6b7f731ea3c11c153a56439310d5f6",
    "mark01@2.2": "ffb7018633f6bf0fa4a516236e4b9ffee9f67e37714188c0a22f442889e8e12c",
    "mark01@3": "9dcc163cf53ff3c606cc7ab84256f5bb38970ba1807b9e09f96c3fd43bdfa027",
    "label01@0.7": "b815733a32981d0c52bc916a9085f78e00ce1f3dab07ed9fe3d8b4984e2c48c3",
    "label01@2": "e37bc84afc74966dc5fd4406b1c56f8649a6c664803c034763b9d5279570ae9e",
    "label01@4.8": "31792fba069fd12790bbcada2d0fd82935d51e4350f4a6dcd315402ab44273b4",
    "open02@1.2": "87bfa2c6a2b6a97e9567df21bf1a041a4f927286209bf421ea07d7abed9ac22c",
    "open02@3": "dda69ceebfc1bfa947d1f0efad227ac7a4ec8f55d68d0622bdd2ec8face0ebec",
    "open02@5.2": "adac7ae4dae26dd912536a0dccd65671955ac3a8ea7683a20ac01bf81720a55c",
}


def golden_frames(root):
    """SHA-256 of frames of ID-BRAND-01, ID-MARK-01 (tracked and plain text), ID-LABEL-01 and ID-OPEN-02 (italic and regular sentences) on a
    gradient picture with a moving camera, at 960 px. The values in GOLDEN were made with the code as it was before ID-BRAND-03 and the
    `kern` option of the text layers were added (git HEAD de426d3). If a library of the server changes how text is rasterised and the
    pictures still look right, make them again with `python -c "import test_identity_brand_title as t; print(t.golden_frames(...))"`."""
    cam = [{"at": {"rel": 0.0}, "cx": 700, "cy": 480, "zoom": 0.9, "ease": "inout_sine"}, {"at": {"rel": 1.0}, "cx": 820, "cy": 520, "zoom": 1.1, "ease": "linear"}]
    img = gradient()
    out = {}

    def grab(tag, p, times):
        for t in times:
            out["%s@%g" % (tag, t)] = hashlib.sha256(p.frame_at(t, 960).tobytes()).hexdigest()

    grab("brand01", make_lab(root, [shot(1, 0.0, "ID-BRAND-01", {"text": "RAKING LIGHT"}, camera=cam)], image=img, name="g1", end=8.0), (0.0, 0.3, 0.9, 1.8, 2.7, 3.3, 4.9))
    grab("brand01_rtl", make_lab(root, [shot(1, 0.0, "ID-BRAND-01", {"text": "Light and Shadow", "direction": "right_to_left", "shadow": False, "y_pct": 55}, camera=cam)],
                                 image=img, name="g2", end=8.0), (1.7, 4.2))
    grab("mark01", make_lab(root, [shot(1, 0.0, "ID-MARK-01", {"title": "5. The Mirror"}, camera=cam)], image=img, name="g3", end=8.0), (0.8, 1.5, 2.2, 3.0))
    grab("label01", make_lab(root, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-LABEL-01", 0.5, 4.5, {"title": "The Arnolfini Portrait", "artist_year": "Jan van Eyck, 1434", "title_cap_pct": 3.0, "second_cap_pct": 2.3})],
                                         camera=cam)], image=img, name="g4", end=8.0), (0.7, 2.0, 4.8))
    grab("open02", make_lab(root, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-02", 0.5, 5.0, {"title": "Hands", "sub": "Jan van Eyck · 1434"})], camera=cam)],
                            image=img, name="g5", end=8.0), (1.2, 3.0, 5.2))
    return out


def test_the_older_identity_techniques_draw_the_same_bytes_as_before(tmp_path):
    got = golden_frames(tmp_path)
    assert GOLDEN, "GOLDEN is empty"
    assert got == GOLDEN, [k for k in GOLDEN if got.get(k) != GOLDEN[k]]
