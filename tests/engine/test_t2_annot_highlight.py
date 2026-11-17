"""Tests of the annotation / highlight / camera ports: CAM-02, CAM-06, HI-02, HI-03, X-HI-01, AN-02, AN-03, AN-04, AN-06, AN-07,
X-ANN-04, X-ANN-05 (modules annotations_extra, highlights_extra, camera_extra).

Unit tests run on the tiny fixture (a synthetic 800x1200 picture, masks built here).  The lab project `projects/lab_annot` (same content as the
benchmark reel segments) is validated, rendered, and compared with the reel when `.scratch/r1` is present."""
import json
import os
import sys

import cv2
import numpy as np
import pytest

from bti.engine import registry as R
from conftest import REPO, base_storyboard

IDS = ["CAM-02", "CAM-06", "HI-02", "HI-03", "X-HI-01", "AN-02", "AN-03", "AN-04", "AN-06", "AN-07", "X-ANN-04", "X-ANN-05"]
KINDS = {"CAM-02": "base", "CAM-06": "base", "HI-02": "base", "AN-07": "base"}
LAB = REPO / "projects" / "lab_annot"


# ----------------------------------------------------------------------------- helpers
def _mask(path, shape=(300, 200), boxes=(((60, 60), (140, 240)),)):
    m = np.zeros(shape, np.uint8)
    for (x0, y0), (x1, y1) in boxes:
        cv2.rectangle(m, (x0, y0), (x1, y1), 255, -1)
    cv2.imwrite(str(path), m)


@pytest.fixture()
def lab(tiny, tiny_project):
    """(project, helper): a single 10 s shot of CAM-05 over picture A, masks M1..M3 (quarter size, aligned to A), overlays added by the helper."""
    _mask(tiny / "media" / "m1.png", boxes=(((20, 40), (90, 150)),))
    _mask(tiny / "media" / "m2.png", boxes=(((110, 40), (180, 150)),))
    _mask(tiny / "media" / "m3.png", boxes=(((50, 190), (150, 280)),))
    _mask(tiny / "media" / "mall.png", boxes=(((20, 40), (180, 150)),))
    cv2.imwrite(str(tiny / "media" / "map.png"), np.dstack([np.full((540, 960), v, np.uint8) for v in (90, 140, 190)]))

    def make(overlays=(), tech="CAM-05", params=None, slots=None, camera=True):
        sb = base_storyboard()
        for k, f in (("M1", "m1.png"), ("M2", "m2.png"), ("M3", "m3.png"), ("MALL", "mall.png")):
            sb["assets"][k] = {"file": "media/" + f, "kind": "mask", "aligned_to": "A", "width": 200, "height": 300}
        sb["assets"]["MAP"] = {"file": "media/map.png", "kind": "image", "width": 960, "height": 540}
        s = sb["shots"][0]
        s["technique"], s["overlays"] = tech, []
        s["slots"] = slots or {"image": {"asset": "A"}}
        s["params"] = params if params is not None else ({"camera": [{"at": {"rel": 0.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"},
                                                                    {"at": {"rel": 1.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"}]} if camera else {})
        sb["shots"] = [s]
        sb["end"] = {"t": 10.0}
        for i, (tid, start, dur, p, sl) in enumerate(overlays):
            s["overlays"].append({"id": "o%d" % i, "technique": tid, "intent": "point_at", "start": {"t": start}, "dur": dur, "params": p,
                                  "slots": {k: {"asset": v} for k, v in (sl or {}).items()}, "locked": False, "source": "human", "note": ""})
        errs = [i for i in tiny_project.validate(sb) if i["level"] == "error"]
        assert errs == [], errs
        tiny_project.use_draft(sb)
        return tiny_project
    return make


def frame(p, t, w=960):
    return p.frame_at(t, w).astype(np.float32)


def bright(f, thr=235):
    return int((f.min(axis=2) > thr).sum())


def drawn(p, t, base_t=0.2):
    """pixels that are white now but were not white in the frame at base_t (annotation strokes; the fixture picture has a white disc of its own)."""
    f, b = frame(p, t), frame(p, base_t)
    return int(((f.min(axis=2) > 235) & (b.min(axis=2) <= 235)).sum())


# ----------------------------------------------------------------------------- registry and defaults
def test_all_twelve_are_available_with_the_right_kinds(arnolfini):
    b = arnolfini.bundle
    for tid in IDS:
        assert b.available(tid), tid
        assert R.RENDERERS[tid][1] == b.spec(tid)["kind"] == KINDS.get(tid, "overlay"), tid
        eng = b.spec(tid)["engine"]
        assert eng["impl"].startswith("bti.engine.techniques.") and eng["reason"] is None
    assert [p for p in R.check_registry(b) if any(p.startswith(i + ":") for i in IDS)] == []


def test_registry_params_use_allowed_types_and_have_previews(arnolfini):
    ok = {"number", "enum", "bool", "string", "text", "color", "point", "box", "camera", "asset", "points", "lines"}
    for tid in IDS:
        spec = arnolfini.bundle.spec(tid)
        assert {p["type"] for p in spec["params"]} <= ok, tid
        assert spec["preview"] and spec["preview"]["clip"] == "previews/%s.mp4" % tid, tid
        assert (REPO / "style" / "gae" / spec["preview"]["clip"]).exists() and (REPO / "style" / "gae" / spec["preview"]["thumb"]).exists(), tid


def test_default_params_validate_with_and_without_context(arnolfini):
    for tid in IDS:
        spec = arnolfini.bundle.spec(tid)
        for ctx in ({}, {"asset": "A", "region": "MIRROR", "text": "A LABEL"}):
            params = arnolfini.default_params(tid, ctx)
            errs = [i for i in R.validate_params(spec, params, tid) if not (not ctx and "required parameter" in i["message"])]
            assert errs == [], (tid, errs)
    p = arnolfini.default_params("X-HI-01", {"asset": "A", "region": "MIRROR"})
    assert p["at"] == "MIRROR" and p["rx"] == 440 and p["surround_floor"] == 0.2
    p = arnolfini.default_params("AN-03", {"asset": "A"})
    assert p["vanishing_point"][0] == pytest.approx(4386 / 2) and len(p["origins"]) == 9
    p = arnolfini.default_params("CAM-06", {"asset": "A"})
    assert p["label_text"] == "The Arnolfini Portrait" and p["label_sub"] == "Jan van Eyck, 1434" and p["strip_y_top_pct"] == 79.4
    assert arnolfini.default_params("CAM-02", {"asset": "A"})["fg_camera"][1]["zoom"] / arnolfini.default_params("CAM-02", {"asset": "A"})["fg_camera"][0]["zoom"] == pytest.approx(1.3, rel=1e-3)


# ----------------------------------------------------------------------------- unit behaviour
def test_an02_draws_progressively_then_leaves_no_trace(lab):
    p = lab([("AN-02", 1.0, 6.0, {"draw_s": 3.0, "dim_base": 1.0, "fade_s": 0.5}, {"mask": "MALL"})])
    base = frame(p, 0.5)
    n1, n2, n3 = drawn(p, 2.5, 0.5), drawn(p, 4.0, 0.5), drawn(p, 5.5, 0.5)
    assert 0 < n1 < n2 <= n3 + 5 and n3 > 0                          # more of the outline each time, then stable
    assert np.array_equal(frame(p, 7.1), frame(p, 7.4))               # after the end nothing is drawn
    assert np.abs(frame(p, 7.2) - base).max() < 40                    # (same camera; only noise-free matte)
    assert np.array_equal(frame(p, 7.0), frame(p, 7.0))


def test_an02_from_points_and_closed_flag(lab):
    pts = [[200, 300], [600, 300], [600, 900], [200, 900]]
    p = lab([("AN-02", 0.5, 8.0, {"points": pts, "closed": True, "draw_s": 1.0, "dim_base": 1.0, "fade_s": 0.5}, None)])
    full = drawn(p, 3.0)
    assert full > 600
    p = lab([("AN-02", 0.5, 8.0, {"points": pts, "closed": False, "draw_s": 1.0, "dim_base": 1.0, "fade_s": 0.5}, None)])
    assert drawn(p, 3.0) < full - 200                                 # the open polyline lacks its last side


def test_an02_dims_base_and_restores(lab):
    p = lab([("AN-02", 1.0, 6.0, {"dim_base": 0.5, "dim_ramp_s": 0.2, "draw_s": 1.0, "fade_s": 0.5}, {"mask": "M1"})])
    a, b, c = frame(p, 0.5), frame(p, 3.0), frame(p, 7.2)
    far = (slice(300, 340), slice(20, 60))                            # a patch away from the outline
    assert b[far].mean() < 0.6 * a[far].mean() and np.allclose(a[far], c[far], atol=1)


def test_an03_rays_converge_on_the_vanishing_point(lab):
    p = lab([("AN-03", 0.5, 8.0, {"vanishing_point": [400, 500], "stagger_s": 0.2, "each_draw_s": 0.3, "dim_base": 1.0, "fade_s": 0.5, "ray_count": 4}, None)])
    n = [drawn(p, t) for t in (0.4, 0.8, 1.6, 4.0)]
    assert n[0] == 0 and n[0] < n[1] < n[2] <= n[3]
    f = frame(p, 4.0)
    cx, cy = 480, 270 + (500 - 600) * 0.7 / 2                        # vp on screen at width 960
    assert bright(f[int(cy) - 6:int(cy) + 6, int(cx) - 6:int(cx) + 6]) > 20


def test_xhi01_dim_hold_restore(lab):
    params = {"at": [400, 500], "rx": 150, "ry": 120, "shape": "ellipse", "ramp_in_s": 0.5, "ramp_out_s": 0.5, "surround_floor": 0.2}
    p = lab([("X-HI-01", 1.0, 5.0, params, None)])
    base = frame(p, 0.5)
    mid, late = frame(p, 3.0), frame(p, 6.2)
    c = (slice(235, 245), slice(475, 485))                           # inside the bright region
    out = (slice(20, 60), slice(100, 160))                           # far outside
    assert np.allclose(mid[c], base[c], atol=2) and mid[out].mean() < 0.3 * base[out].mean()
    assert 0.3 * base[out].mean() < frame(p, 1.25)[out].mean() < base[out].mean()          # mid-ramp
    assert np.array_equal(late, base) and np.array_equal(frame(p, 6.0), base)               # restore ends at the overlay end
    # explicit hold: restore starts ramp_in + hold after the start
    p = lab([("X-HI-01", 1.0, 8.0, dict(params, hold_s=1.0), None)])
    assert frame(p, 2.4)[out].mean() < 0.3 * base[out].mean() and np.allclose(frame(p, 3.2), base, atol=1)


def test_xhi01_rect_differs_from_ellipse_in_the_corners(lab):
    kw = {"at": [400, 500], "rx": 200, "ry": 200, "ramp_in_s": 0.2}
    p = lab([("X-HI-01", 0.5, 8.0, dict(kw, shape="ellipse"), None)])
    e = frame(p, 4.0)
    p = lab([("X-HI-01", 0.5, 8.0, dict(kw, shape="rect"), None)])
    r = frame(p, 4.0)
    corner = (slice(270 - 85 - 12, 270 - 85 + 12), slice(480 + 85 - 12, 480 + 85 + 12))        # near the box corner at screen scale 0.35
    assert r[corner].mean() > e[corner].mean() * 1.15


def test_hi03_keeps_colour_only_inside_the_mask(lab):
    p = lab([("HI-03", 1.0, 8.0, {"desaturate_ramp_s": 0.5}, {"mask": "MALL"})])
    base, after = frame(p, 0.5), frame(p, 3.0)
    sat = lambda f: (f.max(2) - f.min(2))
    inside = (slice(190, 215), slice(430, 450))                      # screen point of source (600, 540..) inside the mask box
    # mask box in source px: x 80-720, y 160-600 (quarter masks x4); at zoom 0.7 centred (400,600): screen = 480 + (x-400)*.35 , 270 + (y-600)*.35
    sy, sx = int(270 + (400 - 600) * 0.35), int(480 + (400 - 400) * 0.35)
    inside = (slice(sy - 8, sy + 8), slice(sx - 8, sx + 8))
    outside = (slice(400, 440), slice(120, 180))
    assert np.allclose(after[inside], base[inside], atol=1.5)
    assert sat(after[outside]).mean() < 0.02 * max(sat(base[outside]).mean(), 1)
    assert after[outside].mean() < base[outside].mean()
    # restore
    p = lab([("HI-03", 1.0, 5.0, {"desaturate_ramp_s": 0.5, "restore_s": 1.0}, {"mask": "MALL"})])
    assert np.allclose(frame(p, 6.0), base, atol=1.5)


def test_xann04_outlines_one_after_another_and_clear(lab):
    slots = {"mask_1": "M1", "mask_2": "M2", "mask_3": "M3"}
    p = lab([("X-ANN-04", 1.0, 8.0, {"group_count": 3, "per_group_draw_s": 1.0, "gap_s": 0.5, "hold_s": 0.5, "fade_s": 0.5, "dim_base": 1.0}, slots)])
    n = [drawn(p, t) for t in (0.5, 1.8, 3.3, 4.8, 8.6)]
    assert n[0] == 0 and 0 < n[1] < n[2] < n[3]
    after = frame(p, 9.5)
    assert drawn(p, 9.0) == 0 and np.array_equal(after, frame(lab([]), 9.5))          # all gone: the painting stays
    # clear mode: only one outline at a time
    p = lab([("X-ANN-04", 1.0, 8.0, {"group_count": 3, "per_group_draw_s": 1.0, "gap_s": 1.5, "hold_s": 0.5, "fade_s": 0.5, "after_hold": "clear", "dim_base": 1.0}, slots)])
    one, after_one = drawn(p, 2.0), drawn(p, 3.8)
    assert one > 0 and after_one < one * 0.3
    # group_count limits the groups
    p = lab([("X-ANN-04", 1.0, 8.0, {"group_count": 1, "per_group_draw_s": 1.0, "dim_base": 1.0}, slots)])
    assert 0 < drawn(p, 7.0) < n[3]


def test_xann04_points_groups(lab):
    sq = lambda x, y: [[x, y], [x + 200, y], [x + 200, y + 300], [x, y + 300]]
    p = lab([("X-ANN-04", 1.0, 6.0, {"points_1": sq(100, 100), "points_2": sq(500, 300), "per_group_draw_s": 0.5, "gap_s": 0.1, "group_count": 2, "dim_base": 1.0}, None)])
    assert drawn(p, 3.0) > 300


def test_map_annotations_draw_on_the_chosen_background(lab):
    kw = {"places": [[300, 150], [700, 400]], "labels": ["A", "B"], "control": [500, 100]}
    p = lab([("AN-04", 0.0, 8.0, dict(kw, background="image"), {"map": "MAP"})])
    f = frame(p, 5.0)
    assert abs(f[5, 5, 0] - 90) < 4 and abs(f[5, 5, 2] - 190) < 4                                   # the map image is the backdrop
    red = (f[:, :, 2] > 150) & (f[:, :, 1] < 80)
    assert red.sum() > 150
    p = lab([("AN-04", 0.0, 8.0, dict(kw, background="procedural"), None)])
    g = frame(p, 5.0)
    assert abs(g[5, 5].mean() - 150) < 30 and not np.allclose(f, g)
    p = lab([("AN-04", 0.0, 8.0, {"places": [[300, 400], [600, 1000]], "background": "base", "control": [500, 600]}, None)])
    h = frame(p, 5.0)
    assert ((h[:, :, 2] > 150) & (h[:, :, 1] < 80)).sum() > 100                                      # drawn over the picture
    p = lab([("AN-04", 0.0, 8.0, dict(kw, background="image"), None)])          # image mode without the `map` slot draws the procedural map
    assert np.array_equal(frame(p, 5.0), g)                                     # (it used to raise; validate must never accept what cannot be drawn)


def test_map_route_follows_the_camera_in_base_mode(lab):
    ov = [("AN-04", 0.0, 9.0, {"places": [[300, 400], [600, 1000]], "background": "base", "control": [500, 600]}, None)]
    p1 = lab(ov)
    a = frame(p1, 6.0)
    p2 = lab(ov, params={"camera": [{"at": {"rel": 0.0}, "cx": 300, "cy": 500, "zoom": 0.7, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 300, "cy": 500, "zoom": 0.7, "ease": "linear"}]})
    b = frame(p2, 6.0)
    ya, yb = np.where((a[:, :, 2] > 150) & (a[:, :, 1] < 80))[1], np.where((b[:, :, 2] > 150) & (b[:, :, 1] < 80))[1]
    assert ya.size and yb.size and abs(ya.mean() - yb.mean()) > 20            # the annotation moved with the picture


def test_xann05_markers_appear_one_by_one(lab):
    pts = [[200, 150], [400, 200], [600, 300], [800, 150]]
    p = lab([("X-ANN-05", 1.0, 8.0, {"points": pts, "stagger_s": 1.0, "start_delay_s": 0.0, "pop_s": 0.2, "pulse": False, "outline_px": 0, "radius_px": 12}, None)])

    def n_dots(t):
        m = ((frame(p, t, 1920)[:, :, 2] > 170) & (frame(p, t, 1920)[:, :, 1] < 70)).astype(np.uint8)
        return cv2.connectedComponents(m)[0] - 1
    assert [n_dots(t) for t in (0.5, 1.5, 2.5, 3.5, 4.5, 9.3)] == [0, 1, 2, 3, 4, 0]
    p = lab([("X-ANN-05", 1.0, 8.0, {"points": pts, "marker_count": 2, "stagger_s": 1.0, "start_delay_s": 0.0, "pop_s": 0.2, "pulse": False, "outline_px": 0, "radius_px": 12}, None)])
    assert n_dots(5.5) == 2


def test_an06_grid_and_region(lab):
    p = lab([("AN-06", 1.0, 8.0, {"grid_draw_s": 1.0, "region_delay_s": 1.5, "region_fade_s": 0.5, "dim_base": 1.0, "dim_ramp_s": 0.0, "fade_s": 0.5}, None)])
    base = frame(p, 0.5)
    g1, g2 = frame(p, 1.5), frame(p, 4.0)
    col = lambda f, x: f[:, x].min(axis=1)                              # a vertical grid line at x = 960/3 = 320 is white
    assert bright(g1[:, 318:322]) > 200 and bright(g1[:, 318:322]) <= bright(g2[:, 318:322]) + 5
    tri = g2[270, 480]                                                 # inside the triangle (frame fractions .5, .5)
    assert tri[2] > base[270, 480][2] and tri[0] < base[270, 480][0] + 1                         # warm tint: more red than blue
    assert np.allclose(g2[1, 5], base[1, 5], atol=1.5) or g2[1, 5].mean() > 100                  # outside the triangle only the grid changes (no global darkening)
    out = frame(p, 2.6)[500:520, 10:40]
    assert np.allclose(out, base[500:520, 10:40], atol=1.5)
    p = lab([("AN-06", 1.0, 8.0, {"shape": "circle", "shape_points": [[0.5, 0.5], [0.8, 0.5]], "grid_draw_s": 0.1, "region_delay_s": 0.0, "region_fade_s": 0.1, "dim_base": 1.0}, None)])
    c = frame(p, 4.0)
    assert c[270, 480, 2] > base[270, 480, 2] and np.allclose(c[270 + 100, 480 + 440], base[270 + 100, 480 + 440], atol=2.5)


def test_an07_dot_field_resolves_into_the_picture(lab):
    ref = frame(lab([], tech="CAM-05"), 9.95)
    p = lab([], tech="AN-07", params={"dots_end": 3000, "camera": [{"at": {"rel": 0.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"},
                                                                  {"at": {"rel": 1.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"}]})
    early, mid, end = frame(p, 0.3), frame(p, 4.0), frame(p, 9.95)
    assert early.mean() > 150                                           # paper white with a few big dots
    assert np.abs(mid - frame(p, 4.0)).max() == 0                       # seeded: bit identical
    assert np.abs(end - ref).mean() < 3              # resolved into the picture
    assert abs(early.mean() - end.mean()) > 20 and mid.std() > 5


def test_cam06_label_pops_in_after_the_delay_and_leaves(tiny, tiny_project, lab):
    p = lab([], tech="CAM-06", params={"label_text": "Hello", "label_sub": "World", "label_delay_s": 2.0, "label_pop_s": 0.1, "label_hold_s": 3.0, "label_fade_out_s": 0.2})
    before, during, after = frame(p, 1.9), frame(p, 3.5), frame(p, 5.4)
    assert np.array_equal(before, after)
    strip = (slice(int(0.72 * 540), int(0.95 * 540)), slice(30, 300))
    assert bright(during[strip], 235) > 80 and bright(before[strip], 235) == 0


def test_cam02_layers_move_relatively(tiny, tiny_project, lab):
    _mask(tiny / "media" / "m1.png", boxes=(((60, 60), (140, 240)),))
    cv2.imwrite(str(tiny / "media" / "bg.png"), np.dstack([np.tile(np.linspace(0, 255, 800, dtype=np.uint8), (1200, 1)) for _ in range(3)]))
    sb = base_storyboard()
    sb["assets"]["BG"] = {"file": "media/bg.png", "kind": "image", "width": 800, "height": 1200}
    sb["assets"]["M1"] = {"file": "media/m1.png", "kind": "mask", "aligned_to": "A", "width": 200, "height": 300}
    s = sb["shots"][0]
    s["technique"], s["overlays"] = "CAM-02", []
    s["slots"] = {"foreground": {"asset": "A"}, "background": {"asset": "BG"}, "mask": {"asset": "M1"}}
    key = lambda r, cx, z: {"at": {"rel": r}, "cx": cx, "cy": 600, "zoom": z, "ease": "linear"}
    s["params"] = {"fg_camera": [key(0.0, 400, 0.9), key(1.0, 400, 1.3)], "bg_camera": [key(0.0, 400, 0.9), key(1.0, 400, 0.95)], "zoom_interp": "linear"}
    sb["shots"], sb["end"] = [s], {"t": 10.0}
    assert [i for i in tiny_project.validate(sb) if i["level"] == "error"] == []
    tiny_project.use_draft(sb)
    a, b = frame(tiny_project, 0.0), frame(tiny_project, 9.9)
    bgcol = lambda f: f[100, 5:40].mean()
    assert abs(bgcol(a) - bgcol(b)) < 40                                 # background hardly moves
    ca, cb = (a[:, :, 0] != a[:, :, 1]), (b[:, :, 0] != b[:, :, 1])
    assert not np.array_equal(a, b) and np.abs(a - b)[270 - 20:270 + 20, 480 - 20:480 + 20].mean() > 5   # the cut-out changes scale
    # without explicit tracks: width-fit push by fg_zoom / bg_zoom
    s["params"] = {"fg_zoom": 1.5, "bg_zoom": 1.0}
    tiny_project.use_draft(dict(sb, shots=[s]))
    assert frame(tiny_project, 0.0).shape == (540, 960, 3) and not np.array_equal(frame(tiny_project, 0.0), frame(tiny_project, 9.9))


def test_hi02_groups_reveal_in_order_with_a_slide(tiny, tiny_project):
    _mask(tiny / "media" / "l.png", boxes=(((20, 60), (90, 240)),))
    _mask(tiny / "media" / "r.png", boxes=(((110, 60), (180, 240)),))
    plate = np.full((1200, 800, 3), 60, np.uint8)
    cv2.imwrite(str(tiny / "media" / "plate.png"), plate)
    sb = base_storyboard()
    sb["assets"]["PL"] = {"file": "media/plate.png", "kind": "image", "width": 800, "height": 1200}
    for k, f in (("L", "l.png"), ("R", "r.png")):
        sb["assets"][k] = {"file": "media/" + f, "kind": "mask", "aligned_to": "A", "width": 200, "height": 300}
    s = sb["shots"][0]
    s["technique"], s["overlays"] = "HI-02", []
    s["slots"] = {"room_plate": {"asset": "PL"}, "figure_groups": {"asset": "A"}, "mask_1": {"asset": "L"}, "mask_2": {"asset": "R"}}
    s["params"] = {"camera": [{"at": {"rel": 0.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"}],
                   "first_group_delay_s": 1.0, "group_stagger_s": 2.0, "group_fade_s": 0.5, "group_slide_s": 1.0, "slide_px": 400, "plate_dim": 1.0}
    sb["shots"], sb["end"] = [s], {"t": 10.0}
    assert [i for i in tiny_project.validate(sb) if i["level"] == "error"] == []
    tiny_project.use_draft(sb)
    F = lambda t: frame(tiny_project, t)
    left, right = (slice(200, 300), slice(380, 480)), (slice(200, 300), slice(525, 590))   # screen patches over the two groups at width 960
    plate_only = F(0.5)
    assert np.allclose(F(0.9), plate_only)                                  # nothing before the first group
    assert np.abs(F(4.0)[left] - plate_only[left]).mean() > 8 and np.abs(F(2.5)[right] - plate_only[right]).mean() < 1   # group 1 in, group 2 not yet
    assert np.abs(F(6.0)[right] - plate_only[right]).mean() > 8
    mid = F(1.6)                                                            # group 1 mid-slide: displaced to the left of its final place
    assert np.abs(mid[left] - F(4.0)[left]).mean() > 3


# ----------------------------------------------------------------------------- the lab project
@pytest.mark.skipif(not (LAB / "storyboard.json").exists(), reason="lab project not present")
def test_lab_project_validates_and_every_shot_renders_fast_and_deterministically():
    from bti.engine.api import open_project
    import time
    p = open_project(LAB)
    assert [i for i in p.validate() if i["level"] == "error"] == []
    sb = p.resolve()
    used = {s["technique"] for s in sb["shots"]} | {o["technique"] for s in sb["shots"] for o in s["overlays"]}
    assert set(IDS) <= used
    slow = []
    for s in sb["shots"]:
        t = s["_t0"] + 0.62 * (s["_t1"] - s["_t0"])
        f1 = p.frame_at(t, 960)
        t0 = time.time()
        f2 = p.frame_at(t, 960)
        dt = time.time() - t0
        assert np.array_equal(f1, f2), s["id"]
        if dt > 0.15:
            slow.append((s["id"], round(dt, 3)))
    assert slow == [], slow


# ----------------------------------------------------------------------------- equivalence with the benchmark reel
REEL = REPO / ".scratch" / "r1"


@pytest.fixture(scope="module")
def reel():
    if not (REEL / "build_reel.py").exists() or not (LAB / "storyboard.json").exists():
        pytest.skip("reel copy or lab project not present")
    cwd = os.getcwd()
    sys.path.insert(0, str(REEL)); sys.path.insert(0, str(REEL / "lib"))
    os.chdir(REEL)
    try:
        import build_reel as B
        B.S()
    finally:
        os.chdir(cwd)
    B.view = B.matte                           # the engine puts pictures on the designed matte, the reel drew them on black
    return B


CASES = [("CAM-02", "cam02", 3.0), ("CAM-06", "cam06", 4.0), ("HI-02", "hi02", 3.0), ("HI-03", "hi03", 3.0), ("AN-02", "an02", 1.5),
         ("AN-03", "an03", 3.0), ("AN-04", "an04", 3.5), ("AN-07", "an07", 4.5), ("AN-07", "an07", 6.2)]


@pytest.mark.parametrize("tid,shot,t", CASES)
def test_matches_the_reel_segment(reel, tid, shot, t):
    from bti.engine.api import open_project
    p = open_project(LAB)
    t0 = next(s["_t0"] for s in p.resolve()["shots"] if s["id"] == shot)
    e = next(x for x in reel.SEG if x["id"] == tid)
    ref = np.clip(e["fn"](t, e["dur"]), 0, 255).astype(np.uint8)
    ours = p.frame_at(t0 + t, 1920)
    mse = np.mean((ref.astype(np.float64) - ours.astype(np.float64)) ** 2)
    psnr = 99 if mse == 0 else 10 * np.log10(255 ** 2 / mse)
    assert psnr >= 40, (tid, t, psnr)
