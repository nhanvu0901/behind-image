"""MAP-01 (the atlas map), the `items` parameter type and the geography bundle: contract docs/design/2026-11-18-explainer-components.md
sections 3, 4 (MAP-01), 5 and 6. Pictures are measured, not looked at: land and sea pixels at known coordinates, marks and labels at
their times, the route's growth, label placement against the route, every param at its bounds."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import socket
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from bti.engine import geo
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine.api import open_project
from bti.engine.base import hex_to_bgr
from bti.engine.techniques import maps
from conftest import REPO

GEO = REPO / "style" / "gae" / "geo"
BRUGES, LUCCA = (3.2247, 51.2093), (10.5027, 43.8429)
STATIC = {"push_s": 0, "grain": 0, "vignette": 0, "graticule_deg": 0, "sea_names": False, "region_iso": [], "region_label": ""}


def spec():
    return R.load_bundle("gae").spec("MAP-01")


def words(n=80, step=0.5):
    return [{"w": "w%d" % i, "s": round(i * step, 3), "e": round(i * step + 0.4, 3)} for i in range(n)]


def make_project(tmp_path, params=None, start=0.0, end=10.0, name="maplab", shots=None):
    d = Path(tmp_path) / name
    d.mkdir(parents=True, exist_ok=True)
    shot = {"id": "m1", "start": {"t": start}, "technique": "MAP-01", "intent": "context", "slots": {}, "params": params or {}, "transition_in": None,
            "overlays": [], "locked": False, "source": "agent", "note": ""}
    sb = {"schema": "bti.storyboard/1", "project": name, "title": "map", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
          "audio": None, "assets": {}, "shots": shots or [shot], "end": {"t": end, "fade_s": 0}, "approvals": {"storyboard": None}}
    (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    (d / "timing.json").write_text(json.dumps({"duration": end + 5, "words": words(), "beats": [], "chapters": []}), encoding="utf-8")
    return open_project(d)


def errors(p, sb=None):
    return [i for i in p.validate(sb) if i["level"] == "error"]


def renderer(p):
    return p._scene().shots[0].base


def frame(p, t, width=1920):
    return p.frame_at(t, width)


def px(img, lon, lat, view):
    x, y = view.to_px(lon, lat)
    return img[int(round(float(y))), int(round(float(x)))].astype(int)


# ----------------------------------------------------------------------------- the geography bundle
def test_the_bundle_is_small_and_its_hashes_are_in_the_readme():
    man = json.loads((GEO / "manifest.json").read_text(encoding="utf-8"))
    readme = (GEO / "README.md").read_text(encoding="utf-8")
    total = 0
    for f in man["files"]:
        blob = (GEO / f["name"]).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == f["sha256"], f["name"]
        assert len(blob) == f["bytes"] and f["sha256"] in readme, f["name"]
        total += len(blob)
    for s in man["sources"]:
        assert s["sha256"] in readme and s["url"] in readme and s["version"], s["name"]
    assert total < 6_000_000
    assert sorted(f["name"] for f in man["files"]) == ["countries_50m.npz", "land_10m.npz", "land_50m.npz", "seas.json"]
    assert "public domain" in readme.lower() and "naturalearthdata.com/about/terms-of-use" in readme
    assert {p.name for p in GEO.iterdir()} == {"manifest.json", "README.md", "countries_50m.npz", "land_10m.npz", "land_50m.npz", "seas.json"}, "nothing else is bundled"


def test_the_bundle_loads_once_and_knows_its_countries_and_seas():
    land10, land50 = geo.land("10m"), geo.land("50m")
    assert land10.n > 5000 and land50.n > 1000 and land10 is geo.land("10m")
    assert len(land10.lon) > 400_000 and len(land50.lon) < len(land10.lon)
    codes = geo.iso_codes()
    assert {"BE", "FR", "IT", "NO", "TR", "GR", "US", "XK"} <= codes and len(codes) > 200 and all(len(c) == 2 and c.isupper() for c in codes)
    assert geo.country_name("be") == "Belgium"
    names = {s["name"]: s for s in geo.seas()}
    assert {"North Sea", "Bay of Biscay", "Mediterranean Sea", "Adriatic Sea"} <= set(names)
    assert (names["North Sea"]["lon"], names["North Sea"]["lat"]) == (3.0, 55.6)            # the positions of the approved mock-up
    assert all(-180 <= s["lon"] <= 180 and -85 <= s["lat"] <= 85 and s["extent_km"] > 0 for s in names.values())
    assert geo.level_for(1499) == "10m" and geo.level_for(1500) == "50m"


def test_a_coordinate_of_the_bundle_is_where_the_world_has_it():
    """Rings are stored delta coded and quantised: a known point must come out where it belongs (Paris is land, the middle of the Bay of Biscay is not)."""
    for res, tol in (("50m", 0.5), ("10m", 0.2)):
        lay = geo.land(res)
        lon, my = lay.lon, lay.my
        ext = lay.box
        assert math.degrees(ext[:, 0].min()) >= -180.01 and math.degrees(ext[:, 1].max()) <= 180.01
        assert -3.2 < ext[:, 2].min() < -3.0 and ext[:, 3].max() < 3.15      # Antarctica is held to the Mercator limit (-3.14), the Arctic stops at 83.6 N
    lay = geo.land("50m")
    mask = np.zeros((360, 720), np.uint8)
    for i in range(lay.n):
        lo, my = lay.ring(i)
        la = geo.inv_merc(my)
        pts = np.rint(np.stack([(np.degrees(lo) + 180) * 2, (85.05 - la) * 360 / 170.1], 1)).astype(np.int32)
        cv2.fillPoly(mask, [pts], 0 if lay.hole[i] else 255)
    at = lambda lon, lat: mask[int((85.05 - lat) * 360 / 170.1), int((lon + 180) * 2)] > 0
    assert at(2.35, 48.85) and at(-100, 40) and at(135, -25) and at(100, 60)          # Paris, Kansas, Australia, Siberia
    assert not at(-6.0, 45.5) and not at(-30, 30) and not at(170, 0) and not at(3.0, 55.6)  # Biscay, the Atlantic, the Pacific, the North Sea


# ----------------------------------------------------------------------------- projection and fit
def test_projection_is_web_mercator_with_a_width_in_km_at_the_centre():
    v = geo.View(6.86, 47.66, 3800)
    x, y = v.to_px(6.86, 47.66)
    assert (float(x), float(y)) == pytest.approx((960, 540))
    lon, lat = v.to_lonlat(0, 540)
    # 1920 px along the parallel of the centre are `width_km` of ground
    left, right = v.to_lonlat(0, 540)[0], v.to_lonlat(1920, 540)[0]
    assert math.radians(float(right - left)) * geo.EARTH_KM * math.cos(math.radians(47.66)) == pytest.approx(3800, rel=1e-6)
    for lo, la in ((3.2247, 51.2093), (-70.0, -33.0), (179.0, 80.0)):
        back = v.to_lonlat(*v.to_px(lo, la))
        assert (float(back[0]), float(back[1])) == pytest.approx((lo, la), abs=1e-9)
    assert float(geo.inv_merc(geo.merc(60.0))) == pytest.approx(60.0)
    assert float(geo.merc(90.0)) == pytest.approx(float(geo.merc(geo.LAT_LIMIT)))         # held to the Web Mercator limit
    # the scale is conformal: a metre east and a metre north are the same number of pixels (at the centre)
    s = v.s
    assert float(v.to_px(6.86, 47.66 + 0.001)[1]) - 540 == pytest.approx(-0.001 * math.pi / 180 * s / math.cos(math.radians(47.66)), rel=1e-3)


def test_fit_matches_the_worked_numbers_of_research_r10():
    """R10 part 3.2: Bruges and Lucca kept inside the middle 62 percent: centre 6.86 E 47.66 N, about 2,357 km wide, 1.23 km per pixel, Bruges at
    38.4 and 19.0 percent, Lucca at 61.6 and 81.0; at the start view (3,800 km, same centre) 42.8, 30.8 and 57.2, 69.2."""
    end = geo.fit([BRUGES, LUCCA], 19)
    assert (end.lon0, end.lat0) == pytest.approx((6.86, 47.66), abs=0.01)
    assert end.width_km == pytest.approx(2357, rel=0.01)         # exact fit: 2,348 km; R10's 2,357 km is the mock-up's rounded push factor 1.612
    assert end.km_per_px() == pytest.approx(1.23, abs=0.01)
    bx, by = (float(a) for a in end.to_px(*BRUGES))
    lx, ly = (float(a) for a in end.to_px(*LUCCA))
    assert (bx / 19.2, by / 10.8, lx / 19.2, ly / 10.8) == pytest.approx((38.4, 19.0, 61.6, 81.0), abs=0.1)
    start = geo.View(6.86, 47.66, 3800)
    sb, sl = start.to_px(*BRUGES), start.to_px(*LUCCA)
    assert (float(sb[0]) / 19.2, float(sb[1]) / 10.8, float(sl[0]) / 19.2, float(sl[1]) / 10.8) == pytest.approx((42.8, 30.8, 57.2, 69.2), abs=0.1)
    # the places fill exactly the middle (100 - 2 x margin) percent of the longer side, and never more
    for margin in (0, 10, 19, 30):
        v = geo.fit([BRUGES, LUCCA], margin)
        ys = [float(v.to_px(*q)[1]) / 10.8 for q in (BRUGES, LUCCA)]
        assert max(ys) - min(ys) == pytest.approx(100 - 2 * margin, abs=0.2)
    one = geo.fit([(10.78, 59.9)], 19)
    assert one.width_km == 600 and (one.lon0, one.lat0) == pytest.approx((10.78, 59.9))        # a single place: a default width
    far = geo.fit([(-179.0, -60.0), (179.0, 70.0)], 5)
    assert geo.MIN_WIDTH_KM <= far.width_km <= geo.MAX_WIDTH_KM


def test_the_push_is_eased_and_reaches_both_ends():
    a, b = geo.View(6.86, 47.66, 3800), geo.fit([BRUGES, LUCCA], 19)
    assert geo.ease_view(a, b, 0).width_km == pytest.approx(3800)
    assert geo.ease_view(a, b, 1).width_km == pytest.approx(b.width_km)
    mid = geo.ease_view(a, b, 0.5)
    assert b.s > mid.s > a.s and mid.s == pytest.approx((a.s + b.s) / 2)           # the zoom runs linearly in the eased progress, as the mock-up's scale()
    assert maps.ease_inout(0) == 0 and maps.ease_inout(1) == 1 and maps.ease_inout(0.5) == 0.5 and maps.ease_inout(0.25) < 0.25


# ----------------------------------------------------------------------------- the picture
@pytest.mark.parametrize("sea", ["blue_grey", "sepia"])
def test_land_and_sea_are_different_colours_in_both_presets(tmp_path, sea):
    """A point in France is land colour, a point in the Bay of Biscay is sea colour, and they differ by a clear margin (the owner's one correction)."""
    p = make_project(tmp_path, dict(STATIC, sea=sea, view_start_width_km=3800, view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=3800))
    f = frame(p, 0.5)
    v = renderer(p).view_at(0.5)
    pr = maps.PRESETS[sea]
    land = px(f, 2.5, 47.0, v)                       # inland France
    water = px(f, -6.0, 45.5, v)                     # the Bay of Biscay, far from every coast
    assert np.abs(land - np.array(hex_to_bgr(pr["land"]))).max() <= 3, land
    assert np.abs(water - np.array(hex_to_bgr(pr["sea"]))).max() <= 3, water
    assert np.linalg.norm(land - water) > 55
    lum = lambda c: 0.114 * c[0] + 0.587 * c[1] + 0.299 * c[2]
    assert abs(lum(land) - lum(water)) > 20
    near = px(f, -1.9, 46.0, v)                      # a little off the French coast: the sea is darker toward the coast
    assert np.linalg.norm(near - np.array(hex_to_bgr(pr["shade"]))) < np.linalg.norm(water - np.array(hex_to_bgr(pr["shade"])))


def test_narrow_views_use_the_fine_outlines_and_still_separate_land_from_sea(tmp_path):
    p = make_project(tmp_path, dict(STATIC, places=[{"id": "a", "name": "A", "lonlat": [-3.0, 49.0], "at": 50}], route=[], view_start_width_km=400,
                                    view_end_mode="manual", view_end_center="-3.0, 49.0", view_end_width_km=400))
    f = frame(p, 1.0)
    v = renderer(p).view_at(1.0)
    assert geo.level_for(v.width_km) == "10m"
    land, water = px(f, -2.5, 48.2, v), px(f, -3.5, 49.6, v)         # Brittany inland, the middle of the Channel
    pr = maps.PRESETS["blue_grey"]
    assert np.abs(land - np.array(hex_to_bgr(pr["land"]))).max() <= 3 and np.abs(water - np.array(hex_to_bgr(pr["sea"]))).max() <= 3


def test_places_and_labels_appear_at_their_times_and_not_before(tmp_path):
    p = make_project(tmp_path, dict(STATIC, route=[], view_start_width_km=3800, view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=3800))
    v = renderer(p).view_at(0)
    bx, by = (int(round(float(a))) for a in v.to_px(*BRUGES))
    lx, ly = (int(round(float(a))) for a in v.to_px(*LUCCA))
    box = lambda x, y: (slice(y - 60, y + 60), slice(x - 60, x + 200))
    base = frame(p, 0.5).astype(int)
    for t, (x, y), before in ((1.0, (bx, by), 0.95), (2.3, (lx, ly), 2.25)):
        pre, mid, post = (frame(p, tt).astype(int) for tt in (before, t + 0.15, t + 1.0))
        ring_only = (slice(y - 14, y + 14), slice(x - 14, x + 14))
        assert np.abs(pre[ring_only] - base[ring_only]).max() <= 1, "the mark is there before its time"
        assert np.abs(post[ring_only] - base[ring_only]).max() > 40, "the mark never appears"
        assert 0 < np.abs(mid[ring_only] - base[ring_only]).mean() < np.abs(post[ring_only] - base[ring_only]).mean(), "the mark fades in"
        label = (slice(y - 50, y + 50), slice(x + 20, x + 150))
        at_mark_end = frame(p, t + 0.2).astype(int)
        assert np.abs(at_mark_end[label] - base[label]).max() <= 2, "the label starts 0.2 s after the mark"
        assert np.abs(post[label] - base[label]).max() > 60, "the label never appears"
    assert np.abs(frame(p, 2.0).astype(int)[box(lx, ly)] - base[box(lx, ly)]).max() <= 1, "Lucca is not drawn at 2.0 s"


def test_a_place_can_land_on_a_word(tmp_path):
    """`at` may be a word anchor: the engine resolves it the way a camera key's `at` is resolved (word 6 starts at 3.0 s in the lab timing)."""
    word = {"w": 6, "off": 0.0, "text": "w6"}
    params = dict(STATIC, route=[], places=[{"id": "a", "name": "Alpha", "lonlat": [6.86, 47.66], "at": word}], view_start_width_km=3000,
                  view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=3000)
    p = make_project(tmp_path, params, start=1.0, end=12.0)
    assert errors(p) == []
    rs = p.resolve()
    assert rs["shots"][0]["params"]["places"][0]["at"]["_t"] == pytest.approx(3.0)       # the anchor carries its absolute time
    ring = (slice(540 - 14, 540 + 14), slice(960 - 14, 960 + 14))
    base = frame(p, 1.5).astype(int)
    assert np.abs(frame(p, 2.9).astype(int)[ring] - base[ring]).max() <= 1
    assert np.abs(frame(p, 3.6).astype(int)[ring] - base[ring]).max() > 40
    stale = copy.deepcopy(p.storyboard())
    stale["shots"][0]["params"]["places"][0]["at"] = {"w": 6, "off": 0.0, "text": "zzz"}
    assert [i["code"] for i in errors(p, stale)] == ["item_anchor_stale"]
    gone = copy.deepcopy(p.storyboard())
    gone["shots"][0]["params"]["places"][0]["at"] = {"w": 9999, "off": 0.0, "text": "x"}
    assert [i["code"] for i in errors(p, gone)] == ["item_anchor_invalid"]
    rel = copy.deepcopy(p.storyboard())
    rel["shots"][0]["params"]["places"][0]["at"] = {"rel": 0.5}
    assert errors(p, rel) == [] and p.resolve(rel)["shots"][0]["params"]["places"][0]["at"]["_t"] == pytest.approx(1.0 + 0.5 * 11.0)


def accent_like(img, r=70):
    acc = np.array(hex_to_bgr(maps.ACCENT))
    return (np.abs(img.astype(int) - acc).sum(2) < r)


def test_the_route_grows_with_time_and_its_head_sits_at_its_end(tmp_path):
    params = dict(STATIC, places=[{"id": "a", "name": "A", "lonlat": [3.2247, 51.2093], "at": 50}, {"id": "b", "name": "B", "lonlat": [10.5027, 43.8429], "at": 50}],
                  route=[{"from": "a", "to": "b", "via": "5.5, 48.8; 7.6, 46.0", "shape": "curve", "at": 2.0, "draw_s": 4.0, "head": "dot"}],
                  view_start_width_km=3800, view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=3800)
    p = make_project(tmp_path, params)
    r = renderer(p)
    v = r.view_at(0)
    route = r.routes[0]
    L = route["path"].length
    counts = [int(accent_like(frame(p, t)).sum()) for t in (1.9, 2.6, 3.4, 4.2, 5.0, 5.8, 6.0)]
    assert counts[0] == 0, "nothing before the route's time"
    assert all(b > a for a, b in zip(counts[:5], counts[1:6])), counts          # more of it drawn at every step
    assert counts[6] == pytest.approx(counts[5], rel=0.15)
    # at 4.0 s the route is half drawn: the head is on the path at half its length, and no dot is further on than the head's lead
    f = frame(p, 4.0)
    hx, hy = route["path"].at(0.5 * L)
    hpx, hpy = maps.px_of(v, float(hx), float(hy))
    assert np.abs(f[int(round(hpy)), int(round(hpx))].astype(int) - np.array(hex_to_bgr(maps.ACCENT))).max() < 30, "the head is on the path at half its length"
    acc = accent_like(f)
    ys, xs = np.nonzero(acc)
    d_world = []
    for x, y in zip(xs[::7], ys[::7]):                                           # distance along the path of the path point nearest to each accent pixel
        pts = route["path"].samples(v, 400)
        i = int(np.argmin(np.hypot(pts[:, 0] - x, pts[:, 1] - y)))
        d_world.append(i / 399.0)
    assert max(d_world) <= 0.5 + (maps.DOT_LEAD + maps.HEAD_R * 2) / (L * v.s) + 0.03, "dots beyond the head"
    assert min(d_world) < 0.05
    # the dots are anchored in map space: the same route in a pushed view has the same shape (its points keep their longitude and latitude)
    p2 = make_project(tmp_path, dict(params, view_end_width_km=2400, push_s=3.0), name="maplab2")
    r2 = renderer(p2)
    w0, w1 = r2.view_at(0), r2.view_at(3.0)
    assert w1.width_km == pytest.approx(2400) and r2.routes[0]["path"].length == pytest.approx(L)


def test_no_route_head_when_none_is_asked(tmp_path):
    params = dict(STATIC, places=[{"id": "a", "name": "A", "lonlat": [3.2, 51.2], "at": 50}, {"id": "b", "name": "B", "lonlat": [10.5, 43.8], "at": 50}],
                  route=[{"from": "a", "to": "b", "via": "", "shape": "straight", "at": 1.0, "draw_s": 2.0, "head": "none"}])
    p = make_project(tmp_path, params)
    with_head = make_project(tmp_path, dict(params, route=[dict(params["route"][0], head="dot")]), name="maplab_head")
    assert int(accent_like(frame(p, 2.0)).sum()) < int(accent_like(frame(with_head, 2.0)).sum())


def test_labels_keep_their_pixel_size_while_the_map_scales(tmp_path):
    """Marks and labels do not grow with the push: a place's label has the same size at the start and at the end view (only its position follows)."""
    params = dict(STATIC, route=[], places=[{"id": "a", "name": "Bruges", "lonlat": [3.2247, 51.2093], "at": 0.0, "label_side": "ne"}],
                  view_start_width_km=3800, view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=1900, push_s=6.0)
    p = make_project(tmp_path, params, end=12.0)
    r = renderer(p)
    a, b = r.view_at(1.0), r.view_at(7.0)
    assert b.s / a.s > 1.5
    la, lb = r.label_box(r.places[0], "ne", 100, 100), r.label_box(r.places[0], "ne", 100, 100)
    assert la == lb
    pt = r.name_patch["a"]
    assert pt.cap == pytest.approx(0.024 * 1080, rel=0.06)                      # cap height 2.4 percent of the frame height
    f1, f2 = frame(p, 1.0), frame(p, 7.0)
    def ink_height(f, view):
        x, y = (float(c) for c in view.to_px(*BRUGES))
        sub = f[int(y) - 60:int(y) - 2, int(x) + 14:int(x) + 160].astype(int)
        dark = (np.abs(sub - np.array(hex_to_bgr(maps.INK))).sum(2) < 90)
        rows = np.nonzero(dark.any(1))[0]
        return int(rows.max() - rows.min()) if rows.size else 0
    # a view that is zoomed 1.9 times does not make the word 1.9 times taller
    assert abs(ink_height(f1, a) - ink_height(f2, b)) <= 4 and ink_height(f1, a) > 15


def test_label_placement_avoids_the_route_and_the_other_labels_in_the_example(tmp_path):
    """The default example: Bruges to Lucca. Every label, where the engine put it, touches neither the route nor another mark or label in the start view,
    the middle of the push and the end view."""
    p = make_project(tmp_path)
    r = renderer(p)
    for e in (0.0, 0.5, 1.0):
        v = geo.ease_view(r.start, r.end, e)
        pts = r.routes[0]["path"].samples(v, 400)
        boxes = []
        for pl in r.places:
            x, y = maps.px_of(v, pl["lon_rad"], pl["my"])
            box = r.placed(pl, x, y)[2]
            assert not maps._box_near_points(box, pts, 4), (pl["id"], e)
            assert not any(maps._box_hits(box, o) for o in boxes)
            boxes.append(box)
        for (x, y), box in zip((maps.px_of(v, pl["lon_rad"], pl["my"]) for pl in r.places), boxes):
            for ox, oy in (maps.px_of(v, pl["lon_rad"], pl["my"]) for pl in r.places):
                if (ox, oy) != (x, y):
                    assert not maps._box_hits(box, (ox - 12, oy - 12, ox + 12, oy + 12))


def ink_pixels(img, box, margin):
    """Pixels of a frame without marks and labels that are ink under `box` grown by `margin`: the coastline (dark ink), the outline of a region (accent)."""
    x0, y0, x1, y1 = max(0, int(box[0] - margin)), max(0, int(box[1] - margin)), int(box[2] + margin), int(box[3] + margin)
    sub = img[y0:y1, x0:x1].astype(int)
    dark = np.abs(sub - np.array(hex_to_bgr(maps.INK))).sum(2) < 90
    accent = np.abs(sub - np.array(hex_to_bgr(maps.ACCENT))).sum(2) < 100
    return int(dark.sum() + accent.sum())


def test_a_place_label_has_no_ink_under_it_in_the_default_example(tmp_path):
    """Contract of fix round 1, point 1: no coastline stroke and no outline of the tinted country under the box of "Bruges" (and of "Lucca") at 1.4, 4.2 and 7.6 s.
    Measured on the pixels of the same frame drawn without marks and labels, apart from the engine's own placement."""
    p = make_project(tmp_path)
    clean = make_project(tmp_path, {"places": [dict(pl, at=1000) for pl in spec()["params"][0]["default"]]}, name="clean")   # same map, no mark, no label
    r = renderer(p)
    for t in (1.4, 4.2, 7.6):
        v = r.view_at(t)
        img = frame(clean, t)
        for pl in r.places:
            if t < pl["at"] + 0.5:
                continue
            x, y = maps.px_of(v, pl["lon_rad"], pl["my"])
            box = r.placed(pl, x, y)[2]
            assert ink_pixels(img, box, 2) == 0, (pl["id"], t, box)
            assert not r.off_frame(box)


def test_a_crowded_place_gets_its_label_farther_out_not_on_the_ink(tmp_path):
    """A mark on a coast with a country's outline beside it: none of the eight sides is clear, so the label is put farther out; it stays near its mark and clear of ink."""
    p = make_project(tmp_path)
    r = renderer(p)
    pl = r.places[0]                                                    # Bruges, on the coast of Belgium
    dx, dy = r.label_at["bruges"]
    pt = r.name_patch["bruges"]
    gap = r._gap_to_mark(pt, (dx, dy))
    assert gap > maps.LABEL_GAP / 100.0 * maps.H * 3, "the three nearest rings of the eight sides are all on ink"
    assert gap < 0.12 * maps.H, "and the label is still beside its mark"
    assert r.sides["bruges"] in ("n", "ne", "e", "se", "s", "sw", "w", "nw")
    open_sea = make_project(tmp_path, {"places": [{"id": "x", "name": "Open", "lonlat": [-20.0, 45.0], "at": 0.5}], "route": [], "region_iso": [], "region_label": "",
                                       "view_start_width_km": 1200, "view_end_mode": "manual", "view_end_center": "-20, 45", "view_end_width_km": 1200}, name="openlabel")
    ro = renderer(open_sea)
    assert ro.sides["x"] == "se" and ro.label_at["x"] == ro.side_offset(ro.places[0], "se"), "on open water the first side of the order is taken"


def test_the_region_name_goes_inside_a_big_country_and_outside_a_small_one(tmp_path):
    """Fix round 1, point 2. France is large: its name lies inside the outline with clearance. Belgium is small: its name lies beside it, on free ground. Either way it
    touches no outline, route, mark or label (measured in the start, the middle and the end view of the push)."""
    france = make_project(tmp_path, {"places": [{"id": "paris", "name": "Paris", "lonlat": [2.35, 48.86], "at": 0.5}, {"id": "lyon", "name": "Lyon", "lonlat": [4.84, 45.76], "at": 0.5}],
                                     "route": [{"from": "paris", "to": "lyon", "via": "", "shape": "straight", "at": 1.0, "draw_s": 2.0, "head": "dot"}], "region_iso": ["FR"],
                                     "region_label": "France", "view_start_width_km": 2600, "view_end_mode": "manual", "view_end_center": "2.5, 46.5", "view_end_width_km": 1800},
                          name="france")
    belgium = make_project(tmp_path, name="belgium")
    for p, inside in ((france, True), (belgium, False)):
        r = renderer(p)
        assert r.region_offset is not None
        views, fields = r.build_fields()
        for v, fd in zip(views, fields):
            box = r.region_box(v)
            assert not r.off_frame(box)
            assert not fd.ink_in(box, 4), "no coastline, water line or outline under the name"
            sub = fd.cut(fd.region_fill, box, 4)
            assert (sub.min() > 127) if inside else (sub.max() < 128), "inside the region" if inside else "outside it, on free ground"
            for rt in r.routes:
                assert not maps._box_near_points(box, rt["path"].samples(v, 400), 5)
            for pl in r.places:
                mx, my = maps.px_of(v, pl["lon_rad"], pl["my"])
                assert not maps._box_hits(box, (mx - 12, my - 12, mx + 12, my + 12), 3)
                assert not maps._box_hits(box, r.placed(pl, mx, my)[2], 3)


def test_a_label_side_that_is_given_is_kept_even_when_it_is_worse(tmp_path):
    params = {"places": [{"id": "bruges", "name": "Bruges", "lonlat": [3.2247, 51.2093], "at": 1.0, "label_side": "se"},
                         {"id": "lucca", "name": "Lucca", "lonlat": [10.5027, 43.8429], "at": 2.3, "label_side": "w"}]}
    assert renderer(make_project(tmp_path, params)).sides == {"bruges": "se", "lucca": "w"}


def test_the_region_is_tinted_and_named_from_its_time_on(tmp_path):
    p = make_project(tmp_path, dict(STATIC, region_iso=["BE"], region_label="Belgium", places=[{"id": "a", "name": "A", "lonlat": [6.0, 49.5], "at": 50}], route=[],
                                    view_start_width_km=3800, view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=3800))
    v = renderer(p).view_at(0)
    before, after = frame(p, 0.5).astype(int), frame(p, 2.0).astype(int)
    x, y = (int(round(float(a))) for a in v.to_px(4.6, 50.6))                      # inside Belgium
    assert np.abs(before[y - 3:y + 3, x - 3:x + 3] - after[y - 3:y + 3, x - 3:x + 3]).max() > 8
    acc = np.array(hex_to_bgr(maps.ACCENT))
    land = np.array(hex_to_bgr(maps.PRESETS["blue_grey"]["land"]))
    tinted = after[y - 3:y + 3, x - 3:x + 3].mean((0, 1))
    assert np.linalg.norm(tinted - acc) < np.linalg.norm(land - acc)                # moved toward the accent, by about a fifth
    ox, oy = (int(round(float(a))) for a in v.to_px(2.0, 48.0))                    # France, outside
    assert np.abs(before[oy, ox] - after[oy, ox]).max() <= 1


def test_sea_names_are_printed_only_inside_the_view_and_can_be_switched_off(tmp_path):
    base = dict(STATIC, route=[], view_start_width_km=3800, view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=3800)
    on = make_project(tmp_path, dict(base, sea_names=True), name="on")
    off = make_project(tmp_path, dict(base, sea_names=False), name="off")
    none = make_project(tmp_path, dict(base, sea_names=True, sea_names_max=0), name="none")
    a, b, c = frame(on, 0.3).astype(int), frame(off, 0.3).astype(int), frame(none, 0.3).astype(int)
    v = renderer(on).view_at(0.3)
    x, y = (int(round(float(q))) for q in v.to_px(-4.6, 45.3))                      # BAY OF BISCAY
    box = (slice(y - 14, y + 14), slice(x - 120, x + 120))
    assert np.abs(a[box] - b[box]).max() > 30, "the name is not printed"
    assert np.abs(c - b).max() == 0, "sea_names_max 0 prints none"
    assert np.abs(a - b).max() > 0
    x2, y2 = (int(round(float(q))) for q in v.to_px(3.0, 55.6))
    assert np.abs(a[y2 - 14:y2 + 14, x2 - 100:x2 + 100] - b[y2 - 14:y2 + 14, x2 - 100:x2 + 100]).max() > 30, "the North Sea is in the start view"
    narrow = make_project(tmp_path, dict(base, sea_names=True, view_start_width_km=300, view_end_width_km=300), name="narrow")
    assert np.abs(frame(narrow, 0.3).astype(int) - frame(make_project(tmp_path, dict(base, sea_names=False, view_start_width_km=300, view_end_width_km=300), name="narrow_off"), 0.3).astype(int)).max() == 0, "no sea name is in a view of the Loire"


def test_a_frame_is_a_pure_function_of_time_and_the_paper_does_not_flicker(tmp_path):
    p = make_project(tmp_path)
    ts = [7.7, 0.3, 3.1, 5.5, 3.1, 0.3]
    fr = {}
    for t in ts:
        f = frame(p, t)
        fr.setdefault(t, f)
        assert np.array_equal(f, fr[t]), t
    q = make_project(tmp_path, name="maplab_again")
    assert np.array_equal(frame(q, 3.1), fr[3.1]), "a new project draws the same frame"
    # grain and vignette are pinned to the screen: without a push the paper is identical from frame to frame wherever nothing else changes
    s = make_project(tmp_path, dict(STATIC, grain=1.0, vignette=1.0, route=[], places=[{"id": "a", "name": "A", "lonlat": [3, 50], "at": 50}], region_iso=[]), name="paper")
    a, b = frame(s, 1.0), frame(s, 4.0)
    assert np.array_equal(a, b)
    assert a.std(axis=(0, 1)).min() > 3                       # the grain is there
    corner, centre = a[:80, :80].mean(), a[500:580, 940:1020].mean()
    assert corner < centre                                    # and the vignette


def test_grain_is_seeded(tmp_path):
    a = make_project(tmp_path, dict(STATIC, grain=1.0, seed=4), name="g4")
    b = make_project(tmp_path, dict(STATIC, grain=1.0, seed=5), name="g5")
    c = make_project(tmp_path, dict(STATIC, grain=1.0, seed=4), name="g4b")
    fa, fb, fc = frame(a, 0.5), frame(b, 0.5), frame(c, 0.5)
    assert np.array_equal(fa, fc) and not np.array_equal(fa, fb)


def test_every_param_at_its_bounds_validates_and_draws(tmp_path):
    p = make_project(tmp_path)
    sb = p.storyboard()
    sp = spec()
    n = 0
    for pd in sp["params"]:
        cases = []
        if pd["type"] == "number":
            cases = [pd["min"], pd["max"], pd["default"]]
        elif pd["type"] == "enum":
            cases = list(pd["values"])
        elif pd["type"] == "bool":
            cases = [True, False]
        elif pd["type"] == "at":
            cases = [pd["min"], pd["max"], pd["default"], {"w": 6, "off": 0.0, "text": "w6"}]
        elif pd["type"] == "items":
            for fd in pd["fields"]:
                if fd["type"] in ("number", "at"):
                    for bound in (fd["min"], fd["max"]):
                        items = copy.deepcopy(pd["default"])
                        items[0][fd["name"]] = bound
                        cases.append(items)
                elif fd["type"] == "enum":
                    for v in fd["values"]:
                        items = copy.deepcopy(pd["default"])
                        items[0][fd["name"]] = v
                        cases.append(items)
            cases += [[], copy.deepcopy(pd["default"]) * (1 if pd["name"] == "route" else 1)]
            if pd["name"] == "places":
                cases = [c for c in cases if c] + [[dict(pd["default"][0], id="p%d" % i, name="P%d" % i, lonlat=[-170 + 30 * i, -80 + 12 * i]) for i in range(12)]]
        for v in cases:
            d = copy.deepcopy(sb)
            d["shots"][0]["params"][pd["name"]] = v
            e = errors(p, d)
            if pd["name"] == "places" and v and any(pl["id"] == "bruges" for pl in v) is False:
                e = [x for x in e if x["code"] != "map_route_unknown_place"]
            if pd["name"] == "route" and v == []:
                assert e == [], (pd["name"], v, e)
            if e:
                assert pd["name"] == "places" and all(x["code"] == "map_route_unknown_place" for x in e), (pd["name"], v, e)
                d["shots"][0]["params"]["route"] = []
            p.use_draft(d)
            try:
                for t in (0.2, 4.0, 9.0):
                    img = p.frame_at(t, 320)
                    assert img.shape == (180, 320, 3) and img.std() > 1
                n += 1
            finally:
                p.use_draft(None)
    assert n > 60
    for key, fd in ((k, f) for pd in sp["params"] if pd["type"] == "items" for f in pd["fields"] for k in [pd["name"]]):
        assert (fd["min"] is None) == (fd["max"] is None), (key, fd["name"])
    for pd in sp["params"]:
        if pd["type"] in ("number", "at"):
            assert pd["min"] is not None and pd["max"] is not None, pd["name"]


def test_no_network_is_used_while_a_map_is_drawn(tmp_path, monkeypatch):
    p = make_project(tmp_path, dict(region_iso=["BE", "NL"]))

    def forbid(*a, **k):
        raise AssertionError("a socket was opened while MAP-01 drew a frame")
    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)
    with geo._LOCK:
        geo._CACHE.clear()                                    # the bundle is read again from disk under the guard
    for t in (0.1, 3.0, 7.9):
        assert p.frame_at(t, 480).shape == (270, 480, 3)


def test_a_frame_costs_what_the_other_base_techniques_cost(tmp_path):
    """A guard against a slow path, not a benchmark (the milliseconds per frame are in docs/qa/FIX_map_build.md): a warm 1920 px frame under 0.6 s."""
    p = make_project(tmp_path)
    frame(p, 1.0)
    t0 = time.perf_counter()
    for t in (2.0, 4.0, 6.0, 7.0):
        frame(p, t)
    assert (time.perf_counter() - t0) / 4 < 0.6


def test_views_across_the_antimeridian_and_at_high_latitude_draw(tmp_path):
    fiji = make_project(tmp_path, dict(STATIC, places=[{"id": "a", "name": "Taveuni", "lonlat": [179.99, -16.85], "at": 0.2}], route=[], view_start_width_km=700,
                                      view_end_mode="manual", view_end_center="179.99, -16.85", view_end_width_km=700), name="fiji")
    f = frame(fiji, 1.0)
    v = renderer(fiji).view_at(1.0)
    pr = maps.PRESETS["blue_grey"]
    land, water = np.array(hex_to_bgr(pr["land"])), np.array(hex_to_bgr(pr["sea"]))
    x180 = int(round(float(v.to_px(180.0, -16.85)[0])))
    is_land = (np.abs(f.astype(int) - land).max(2) <= 4)
    assert is_land[:, :x180 - 40].sum() > 2000 and is_land[:, x180 + 40:].sum() > 500, "land on both sides of the antimeridian (Vanua Levu and the Lau group)"
    assert (np.abs(f.astype(int) - water).max(2) < 6).mean() > 0.1
    svalbard = make_project(tmp_path, dict(STATIC, places=[{"id": "a", "name": "Longyearbyen", "lonlat": [15.6, 78.2], "at": 0.2}], route=[], view_start_width_km=2000,
                                          view_end_mode="manual", view_end_center="15.6, 78.2", view_end_width_km=2000), name="svalbard")
    assert frame(svalbard, 1.0).std() > 5
    world = make_project(tmp_path, dict(STATIC, view_start_width_km=20000, view_end_mode="manual", view_end_width_km=20000, view_end_center="0, 0", route=[]), name="world")
    assert frame(world, 1.0).std() > 5


def test_a_narrow_view_smooths_the_coarse_outlines(tmp_path):
    """At 60 km wide the 1:10m outline has segments of tens of pixels: the corners are cut until they are about 6 px, and the ring is clipped to the canvas."""
    v = geo.View(10.78, 59.90, 60)
    rings = maps.BaseMap.project(geo.land("10m"), v, maps.PAD)
    assert rings and all(r[5] for r in rings)
    longest = max(len(r[1]) for r in rings)
    assert longest < 5000, "the huge ring is clipped before it is smoothed"
    seg = np.hypot(np.diff(rings[0][1]), np.diff(rings[0][2]))
    inside = (rings[0][1][:-1] > 0) & (rings[0][1][:-1] < 2000)
    assert np.median(seg[inside]) < 20
    wide = maps.BaseMap.project(geo.land("50m"), geo.View(6.86, 47.66, 3800), maps.PAD)
    assert wide and not any(r[5] for r in wide)


# ----------------------------------------------------------------------------- the items type
def items_param(**k):
    return dict({"name": "things", "type": "items", "default": [], "min": None, "max": None, "unit": None, "values": None, "measured": None, "min_items": 1, "max_items": 3,
                 "fields": [{"name": "name", "type": "string", "required": True, "default": None, "min": None, "max": None, "values": None, "pattern": ".{1,10}", "pattern_hint": "Gõ tên ngắn."},
                            {"name": "n", "type": "number", "required": False, "default": 2, "min": 0, "max": 9, "values": None},
                            {"name": "kind", "type": "enum", "required": False, "default": "a", "min": None, "max": None, "values": ["a", "b"]},
                            {"name": "on", "type": "bool", "required": False, "default": True, "min": None, "max": None, "values": None},
                            {"name": "pos", "type": "lonlat", "required": False, "default": [0, 0], "min": None, "max": None, "values": None},
                            {"name": "ref", "type": "ref", "required": False, "default": None, "min": None, "max": None, "values": None},
                            {"name": "at", "type": "at", "required": False, "default": 1.0, "min": 0, "max": 60, "values": None}]}, **k)


@pytest.mark.parametrize("value,code,words", [
    ("x", "param_not_items", ["list"]),
    ([], "param_item_count", ["at least 1"]),
    ([{"name": "a"}] * 4, "param_item_count", ["at most 3"]),
    (["x"], "item_not_object", ["item 1"]),
    ([{"name": "a"}, {"name": "b", "zz": 1}], "item_unknown_field", ["item 2 (b)", "'zz'"]),
    ([{"n": 3}], "item_field_missing", ["item 1", "'name'"]),
    ([{"name": None}], "item_field_missing", ["'name'"]),
    ([{"name": 5}], "item_field_bad_type", ["item 1", "'name'", "text"]),
    ([{"name": "x" * 11}], "item_field_bad_form", ["Gõ tên ngắn"]),
    ([{"name": "ok", "n": "x"}], "item_field_bad_type", ["item 1 (ok)", "'n'", "number"]),
    ([{"name": "ok", "n": -1}], "item_field_below_min", ["'n'", ">= 0"]),
    ([{"name": "ok", "n": 10}], "item_field_above_max", ["'n'", "<= 9"]),
    ([{"name": "ok", "n": float("nan")}], "item_field_bad_type", ["'n'"]),
    ([{"name": "ok", "kind": "c"}], "item_field_not_in_values", ["'kind'", "a, b"]),
    ([{"name": "ok", "on": "yes"}], "item_field_bad_type", ["'on'", "true or false"]),
    ([{"name": "ok", "pos": [1, 2, 3]}], "item_field_bad_lonlat", ["'pos'"]),
    ([{"name": "ok", "pos": ["a", 2]}], "item_field_bad_lonlat", ["'pos'"]),
    ([{"name": "ok", "pos": [181, 0]}], "item_field_bad_lonlat", ["longitude"]),
    ([{"name": "ok", "pos": [-181, 0]}], "item_field_bad_lonlat", ["longitude"]),
    ([{"name": "ok", "pos": [0, 85.1]}], "item_field_bad_lonlat", ["latitude"]),
    ([{"name": "ok", "pos": [0, -86]}], "item_field_bad_lonlat", ["latitude"]),
    ([{"name": "ok", "ref": 5}], "item_field_bad_type", ["'ref'"]),
    ([{"name": "ok", "ref": ["a", "b"]}], "item_field_bad_type", ["'ref'"]),
    ([{"name": "ok", "at": "soon"}], "item_field_bad_at", ["'at'"]),
    ([{"name": "ok", "at": {"x": 1}}], "item_field_bad_at", ["'at'"]),
    ([{"name": "ok", "at": {"w": -1}}], "item_field_bad_at", ["'at'"]),
    ([{"name": "ok", "at": {"rel": 2}}], "item_field_bad_at", ["'at'"]),
    ([{"name": "ok", "at": -1}], "item_field_below_min", ["'at'"]),
    ([{"name": "ok", "at": 61}], "item_field_above_max", ["'at'"]),
])
def test_items_validation_names_the_item_and_the_field(value, code, words):
    m = R.check_problem(items_param(), value)
    assert m is not None and m[0] == code, m
    for w in words:
        assert w in m[2], (w, m[2])
    if code.startswith("item_") and code not in ("item_not_object",):
        assert m[1]["index"] == (1 if "item 2" in m[2] else 0) or code == "item_field_missing"


@pytest.mark.parametrize("value", [
    [{"name": "a"}], [{"name": "a", "n": 0, "kind": "b", "on": False, "pos": [180, 85], "ref": "MIRROR", "at": 60}],
    [{"name": "a", "pos": [-180, -85], "ref": [10, 20], "at": {"t": 3.5}}], [{"name": "a", "at": {"w": 4, "off": -0.2, "text": "x"}}],
    [{"name": "a", "at": {"rel": 0.25}}], [{"name": "a"}, {"name": "b"}, {"name": "c"}],
])
def test_items_that_are_fine_pass(value):
    assert R.check_problem(items_param(), value) is None


def test_item_defaults_fill_the_missing_fields_and_one_line_text():
    d = items_param()
    out = R.fill_items(d, [{"name": "a\nb"}, "junk", {"name": "c", "n": 7, "kind": None}])
    assert out == [{"name": "a b", "n": 2, "kind": "a", "on": True, "pos": [0, 0], "at": 1.0}, {"name": "c", "n": 7, "kind": "a", "on": True, "pos": [0, 0], "at": 1.0}]
    out[0]["pos"].append(9)
    assert d["fields"][4]["default"] == [0, 0], "defaults are copied, never shared"
    sp = spec()
    merged = R.merged_params(sp, {"route": [{"from": "a", "to": "b"}]})
    assert merged["route"] == [{"from": "a", "to": "b", "via": "", "shape": "curve", "at": 2.6, "draw_s": 3.0, "head": "dot"}]
    assert merged["places"] == sp["params"][0]["default"] and merged["places"] is not sp["params"][0]["default"]
    assert R.at_seconds(1.5, 9) == 1.5 and R.at_seconds({"_t": 12.0}, 9) == 3.0 and R.at_seconds({"w": 3}, 9, 7.0) == 7.0 and R.at_seconds("x", 0, 2.0) == 2.0
    assert R.items_at_fields(sp) == [("places", ["at"]), ("route", ["at"])]
    assert R.item_label({"name": "Lucca", "id": "l"}) == "Lucca" and R.item_label({"id": "l"}) == "l" and R.item_label({}) == "" and R.item_label("x") == ""


def test_the_registry_entry_is_complete_and_the_default_data_is_the_example():
    sp = spec()
    assert sp["kind"] == "base" and sp["engine"]["available"] and sp["label_vi"] and sp["description"] and sp["usage_rule"]
    for word in ("STATIC-06", "AN-04", "X-ANN-05", "replaces"):
        assert word in sp["usage_rule"]
    assert sp["timing"] == {"default_s": 8.0, "min_s": 3.0, "max_s": 30.0, "anchor": "word"}
    names = [x["name"] for x in sp["params"]]
    for need in ("places", "route", "region_iso", "region_label", "region_at", "region_fill_s", "view_start_width_km", "view_start_center", "view_end_mode",
                 "view_end_margin_pct", "view_end_center", "view_end_width_km", "push_s", "sea", "sea_names", "graticule_deg", "grain", "vignette"):
        assert need in names, need
    d = {x["name"]: x["default"] for x in sp["params"]}
    assert [pl["id"] for pl in d["places"]] == ["bruges", "lucca"] and d["places"][0]["lonlat"] == [3.2247, 51.2093] and d["places"][1]["lonlat"] == [10.5027, 43.8429]
    assert d["region_iso"] == ["BE"] and d["sea"] == "blue_grey" and d["view_start_width_km"] == 3800 and d["view_end_mode"] == "fit" and d["view_end_margin_pct"] == 19
    assert d["places"][0]["at"] == 1.0 and d["places"][1]["at"] == 2.3 and d["route"][0]["at"] == 2.6 and d["route"][0]["draw_s"] == 3.0 and d["push_s"] == 6.0
    assert all(R.check_problem(x, x["default"]) is None for x in sp["params"])
    assert (REPO / "style/gae" / sp["preview"]["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / sp["preview"]["thumb"]).stat().st_size > 1000
    assert open_project is not None


def test_the_rules_between_params(tmp_path):
    p = make_project(tmp_path)
    sb = p.storyboard()

    def codes(**params):
        d = copy.deepcopy(sb)
        d["shots"][0]["params"].update(params)
        return [(i["code"], i["path"]) for i in errors(p, d)]
    assert codes() == []
    assert codes(places=[]) == [("param_item_count", "shots[0].params.places")]
    assert codes(places=[{"id": "x", "name": "X", "lonlat": [0, 0]}]) == [("map_route_unknown_place", "shots[0].params.route")] * 2, "the default route still names Bruges and Lucca"
    assert codes(places=[{"id": "x", "name": "X", "lonlat": [0, 0]}], route=[]) == []
    assert codes(places=[{"id": "x", "name": "X", "lonlat": [0, 0]}] * 2, route=[]) == [("map_duplicate_place", "shots[0].params.places")]
    assert codes(route=[{"from": "bruges", "to": "nowhere"}]) == [("map_route_unknown_place", "shots[0].params.route")]
    assert codes(route=[{"from": "bruges", "to": "lucca", "via": "1, 2; x"}]) == [("item_field_bad_form", "shots[0].params.route")]
    assert codes(route=[{"from": "bruges", "to": "lucca", "via": "1, 200"}]) == [("map_bad_via", "shots[0].params.route")]
    assert codes(route=[{"from": "bruges", "to": "lucca", "via": "; ".join("1, 2" for _ in range(13))}]) == [("map_bad_via", "shots[0].params.route")]
    assert codes(route=[{"from": "bruges", "to": "lucca", "via": "1, 2;"}]) == []
    assert codes(view_start_center="a") == [("param_bad_form", "shots[0].params.view_start_center")]
    assert codes(view_start_center="1, 2; 3, 4") == [("param_bad_form", "shots[0].params.view_start_center")] or codes(view_start_center="1, 2; 3, 4") == [("map_bad_center", "shots[0].params.view_start_center")]
    assert codes(view_end_center="190, 10") == [("map_bad_center", "shots[0].params.view_end_center")]
    assert codes(view_end_center="10, 86") == [("map_bad_center", "shots[0].params.view_end_center")]
    assert codes(view_end_center="10, 40", view_end_mode="manual") == []
    assert codes(view_end_width_km=49) == [("param_below_min", "shots[0].params.view_end_width_km")]
    assert codes(view_end_width_km=20001) == [("param_above_max", "shots[0].params.view_end_width_km")]
    assert codes(view_start_width_km=49) == [("param_below_min", "shots[0].params.view_start_width_km")]
    assert codes(region_iso=["XX"]) == [("map_unknown_iso", "shots[0].params.region_iso")]
    assert codes(region_iso=["be", "Fr"]) == []
    assert codes(region_iso=["Belgium"]) == [("param_bad_form", "shots[0].params.region_iso")]
    assert codes(sea="green") == [("param_not_in_values", "shots[0].params.sea")]
    assert codes(places=[{"id": "x", "name": "X", "lonlat": [0, 99]}], route=[]) == [("item_field_bad_lonlat", "shots[0].params.places")]
    bad = errors(p, {**copy.deepcopy(sb), "shots": [{**sb["shots"][0], "params": {"places": [{"id": "x", "name": "Y", "lonlat": [0, 99]}], "route": []}}]})
    assert "item 1 (Y)" in bad[0]["message"] and "'lonlat'" in bad[0]["message"] and bad[0]["args"]["index"] == 0 and bad[0]["args"]["field"] == "lonlat"


def test_an_element_shorter_than_its_minimum_is_an_error_for_the_new_families(tmp_path):
    short = make_project(tmp_path, {}, start=0.0, end=2.0)
    e = [i for i in errors(short) if i["code"] == "element_too_short"]
    assert len(e) == 1 and e[0]["args"]["technique"] == "MAP-01" and e[0]["args"]["min"] == 3.0 and e[0]["args"]["got"] == pytest.approx(2.0)
    ok = make_project(tmp_path, {}, start=0.0, end=3.0, name="okmap")
    assert errors(ok) == []
    assert SB._element_floor({"id": "ID-OPEN-01", "timing": {"min_s": 1.5}}) == 1.5
    for fam in ("MAP", "KEY", "TIME", "NUM", "TREE", "STATE", "DOC"):
        assert SB._element_floor({"id": fam + "-01", "timing": {"min_s": 2.0}}) == 2.0, fam
    assert SB._element_floor({"id": "STATIC-06", "timing": {"min_s": 3.0}}) is None, "the older map is not held to it"
    assert SB._element_floor({"id": "MAP-01", "timing": {"min_s": None}}) is None


def test_the_draw_check_and_the_defaults_of_the_technique_pass(tmp_path):
    p = make_project(tmp_path)
    assert p.draw_check() == []
    d = p.default_params("MAP-01", {})
    assert d == {x["name"]: x["default"] for x in spec()["params"]}
    sb = p.storyboard()
    sb["shots"][0]["params"] = d
    assert errors(p, sb) == []
    d["places"][0]["name"] = "changed"
    assert p.default_params("MAP-01", {})["places"][0]["name"] == "Bruges", "defaults are copied on every call"


def test_a_place_name_with_a_line_break_draws(tmp_path):
    p = make_project(tmp_path, dict(places=[{"id": "a", "name": "Great\nPlace", "lonlat": [6, 47], "at": 0.1}], route=[], region_iso=[]))
    assert errors(p) == []
    assert frame(p, 3.0, 320).shape == (180, 320, 3)


def test_validate_accepts_only_what_the_map_can_draw(tmp_path):
    """The rule of the registry (R2B-012) for MAP-01, run here because the full sweep is a slow test: every odd value of every param (wrong but well typed, extreme,
    empty, degenerate) is either refused by `validate` or drawn. A value that validate accepts and the engine cannot draw is a hole in the registry."""
    from test_validate_draw_sweep import odd_values
    p = make_project(tmp_path)
    sb = p.storyboard()
    sp = spec()
    holes, drawn = [], 0
    for pd in sp["params"]:
        for v in odd_values(pd, pd["default"], [], None):
            d = copy.deepcopy(sb)
            d["shots"][0]["params"][pd["name"]] = v
            if pd["name"] == "places":
                d["shots"][0]["params"]["route"] = []
            if errors(p, d):
                continue
            p.use_draft(d)
            try:
                p.frame_at(5.0, 160)
                drawn += 1
            except Exception as e:      # noqa: BLE001
                holes.append((pd["name"], str(v)[:60], "%s: %s" % (type(e).__name__, str(e)[:100])))
            finally:
                p.use_draft(None)
    assert not holes, holes[:6]
    assert drawn > 60


# ----------------------------------------------------------------------------- fix round 1
def test_a_sea_name_lies_wholly_on_water_with_clearance(tmp_path):
    """Fix round 1, point 3: whatever sea name is printed, in any frame of the push, no pixel of land lies within 8 px of its text, and it is inside the frame. The names
    of the default example are looked at in the start, the middle and the end view, and at the times of the stills."""
    p = make_project(tmp_path)
    r = renderer(p)
    names = set()
    for t in (0.3, 1.4, 2.6, 4.2, 6.4, 7.6):
        v = r.view_at(t)
        _img, land = r.base.draw(v, r.scale_k(v))
        for nm, _x, _y, box in r.visible_sea_names(v):
            names.add(nm["name"])
            x0, y0, x1, y1 = int(box[0]) - 8, int(box[1]) - 8, int(box[2]) + 8, int(box[3]) + 8
            assert land[max(0, y0):y1, max(0, x0):x1].max() == 0, (nm["name"], t)
    assert {"North Sea", "Bay of Biscay"} <= names, names
    assert "Mediterranean Sea" not in names, "the Mediterranean has no water wide enough for its name at the start view: it is left out, not laid across Sardinia"


def test_a_sea_name_is_left_out_when_the_sea_has_no_room_for_it(tmp_path):
    """The Adriatic is long and narrow: in a view of 2,000 km its name does not fit on water, so it is not printed (it is not laid across the coast)."""
    p = make_project(tmp_path, dict(STATIC, sea_names=True, route=[], places=[{"id": "a", "name": "A", "lonlat": [15.0, 43.0], "at": 50}], view_start_width_km=2000,
                                    view_end_mode="manual", view_end_center="15, 43", view_end_width_km=2000))
    r = renderer(p)
    v = r.view_at(1.0)
    assert "Adriatic Sea" not in [nm["name"] for nm, *_ in r.visible_sea_names(v)]
    _img, land = r.base.draw(v, r.scale_k(v))
    for nm, _x, _y, box in r.visible_sea_names(v):
        assert land[max(0, int(box[1]) - 8):int(box[3]) + 8, max(0, int(box[0]) - 8):int(box[2]) + 8].max() == 0, nm["name"]


def test_a_sea_name_is_placed_inside_its_own_sea():
    from bti.engine.techniques.maps import _in_sea
    import numpy as np
    seas = {s["name"]: s for s in geo.seas()}

    def inside(name, lon, lat):
        return _in_sea([np.array(r, np.float32).reshape(-1, 1, 2) / 10.0 for r in seas[name]["poly"]], lon, lat)
    assert inside("Mediterranean Sea", 5.0, 40.6) and inside("Bay of Biscay", -5.7, 45.7) and inside("North Sea", 3.0, 55.6) and inside("Adriatic Sea", 15.0, 43.2)
    assert not inside("Mediterranean Sea", -7.2, 45.1), "the Bay of Biscay is not the Mediterranean"
    assert not inside("North Sea", 3.0, 45.0) and not inside("Bay of Biscay", 15.0, 43.2)
    assert all(s["poly"] for s in seas.values() if s["rank"] <= 3), "every sea of rank 3 and up has an outline"


# ---- the type `at`
def test_a_param_of_type_at_takes_seconds_or_a_word_and_is_held_to_its_bounds():
    p = {"name": "t", "type": "at", "default": 1.0, "min": 0, "max": 60, "unit": "s", "values": None, "measured": None}
    for ok in (0, 1.5, 60, {"t": 3.0}, {"w": 4, "off": -0.2, "text": "x"}, {"w": 0}, {"rel": 0.5}):
        assert R.check_problem(p, ok) is None, ok
    for bad, code in (("soon", "param_bad_at"), (True, "param_bad_at"), ([1], "param_bad_at"), ({"x": 1}, "param_bad_at"), ({"w": -1}, "param_bad_at"), ({"w": 1.5}, "param_bad_at"),
                      ({"rel": 2}, "param_bad_at"), ({"t": "x"}, "param_bad_at"), (-0.1, "param_below_min"), (61, "param_above_max"), (float("nan"), "param_bad_at")):
        m = R.check_problem(p, bad)
        assert m is not None and m[0] == code, (bad, m)
    assert R.check_problem(p, None)[0] == "param_null", "like every other type: null is refused when the param has a default"
    assert R.at_params({"params": [p, {"name": "n", "type": "number"}]}) == ["t"]


def test_region_at_takes_a_word_and_the_tint_comes_on_that_word(tmp_path):
    """The region of the default example appears at `region_at`: in seconds, or on a word of the narration (word 6 starts at 3.0 s in the lab timing). It is resolved and checked
    the way a camera key's `at` is."""
    word = {"w": 6, "off": 0.0, "text": "w6"}
    base = dict(STATIC, region_iso=["BE"], region_label="", route=[], places=[{"id": "a", "name": "A", "lonlat": [6.0, 49.5], "at": 50}], view_start_width_km=3800,
                view_end_mode="manual", view_end_center="6.86, 47.66", view_end_width_km=3800)
    p = make_project(tmp_path, dict(base, region_at=word, region_fill_s=0.5), end=12.0)
    assert errors(p) == []
    assert p.resolve()["shots"][0]["params"]["region_at"]["_t"] == pytest.approx(3.0)
    v = renderer(p).view_at(0)
    x, y = (int(round(float(a))) for a in v.to_px(4.6, 50.6))                      # inside Belgium
    before, during, after = (frame(p, t).astype(int)[y - 3:y + 3, x - 3:x + 3] for t in (2.9, 3.25, 4.0))
    assert np.abs(before - frame(p, 0.5).astype(int)[y - 3:y + 3, x - 3:x + 3]).max() <= 1, "nothing before the word"
    assert 0 < np.abs(during - before).mean() < np.abs(after - before).mean()
    seconds = make_project(tmp_path, dict(base, region_at=3.0, region_fill_s=0.5), end=12.0, name="seconds")
    assert np.array_equal(frame(seconds, 4.0), frame(p, 4.0)), "a word and its time in seconds draw the same frame"
    stale = copy.deepcopy(p.storyboard())
    stale["shots"][0]["params"]["region_at"] = {"w": 6, "off": 0.0, "text": "zzz"}
    assert [(i["code"], i["path"]) for i in errors(p, stale)] == [("stale_anchor", "shots[0].params.region_at")]
    gone = copy.deepcopy(p.storyboard())
    gone["shots"][0]["params"]["region_at"] = {"w": 9999, "off": 0.0, "text": "x"}
    assert [i["code"] for i in errors(p, gone)] == ["anchor_invalid"]
    for bad, code in (("soon", "param_bad_at"), (-1, "param_below_min"), (601, "param_above_max")):
        d = copy.deepcopy(p.storyboard())
        d["shots"][0]["params"]["region_at"] = bad
        assert [i["code"] for i in errors(p, d)] == [code], bad


# ---- narrow views
def test_a_view_narrower_than_300_km_is_a_warning_not_an_error(tmp_path):
    """Fix round 1, point 5(a): Natural Earth has no detail closer than that. The warning `map_view_coarse` names the param; the storyboard still validates and saves."""
    p = make_project(tmp_path)
    sb = p.storyboard()

    def warns(**params):
        d = copy.deepcopy(sb)
        d["shots"][0]["params"].update(params)
        assert errors(p, d) == []
        # fixdraft: this fixture's map is its first shot (second 0), which the viewer check `explainer_early` flags; it is not what this test is about
        return [(i["code"], i["path"].split(".")[-1]) for i in p.validate(d) if i["level"] == "warn" and i["code"] != "explainer_early"]
    assert warns() == []
    assert warns(view_start_width_km=299) == [("map_view_coarse", "view_start_width_km")]
    assert warns(view_start_width_km=300) == []
    assert warns(view_end_mode="manual", view_end_width_km=120, view_end_center="10, 59") == [("map_view_coarse", "view_end_width_km")]
    assert warns(view_end_mode="manual", view_end_width_km=400) == []
    one_street = dict(places=[{"id": "a", "name": "A", "lonlat": [10.78, 59.90], "at": 1.0}, {"id": "b", "name": "B", "lonlat": [10.80, 59.91], "at": 2.0}], route=[], region_iso=[], region_label="")
    assert warns(**one_street) == [("map_view_coarse", "view_end_mode")], "two places a kilometre apart: the fitted view is far narrower than 300 km"
    assert warns(places=[one_street["places"][0]], route=[], region_iso=[], region_label="") == [], "one place: the fitted view has a default width of 600 km"
    both = warns(view_start_width_km=100, view_end_mode="manual", view_end_width_km=100, view_end_center="10, 59")
    assert [c for c, _ in both] == ["map_view_coarse", "map_view_coarse"]
    msg = [i for i in p.validate({**sb, "shots": [{**sb["shots"][0], "params": {"view_start_width_km": 100}}]}) if i["code"] == "map_view_coarse"][0]
    assert msg["level"] == "warn" and msg["args"]["width_km"] == 100 and msg["args"]["param"] == "view_start_width_km"
    p.save({**sb, "shots": [{**sb["shots"][0], "params": {"view_start_width_km": 100}}]})                      # a warning does not refuse a save


def test_the_usage_rule_says_what_the_map_is_for_and_how_to_draw_a_sea_route():
    rule = spec()["usage_rule"]
    for phrase in ("country, a region or a journey", "300 km", "street-map picture from the picks", "spot inside a city", "STATIC-06", "AN-04", "X-ANN-05",
                   "`via` points in open water", "drawn across land"):
        assert phrase in rule, phrase


def test_strokes_and_the_shade_never_get_heavier_than_in_the_default_end_view(tmp_path):
    """Fix round 1, point 5(c): the widths that live in map space scale with the zoom since the start view, held to the zoom of the default example's end view
    (3,800 to 2,348 km: 1.617), however far the push goes; the hairlines are the same in px at every zoom."""
    default = renderer(make_project(tmp_path))
    k_end = default.scale_k(default.end)
    assert k_end == pytest.approx(maps.K_MAX, abs=0.001) and k_end <= maps.K_MAX + 1e-12
    far = make_project(tmp_path, dict(STATIC, places=[{"id": "a", "name": "A", "lonlat": [10.78, 59.9], "at": 50}], route=[], view_start_width_km=20000, view_end_mode="manual",
                                      view_end_center="10.78, 59.9", view_end_width_km=60, push_s=4.0), name="far")
    rf = renderer(far)
    ks = [rf.scale_k(rf.view_at(t)) for t in (0.0, 1.0, 2.0, 3.0, 4.0, 9.0)]
    assert max(ks) <= k_end + 1e-12 and ks[-1] == maps.K_MAX and ks[0] == pytest.approx(1.0)
    lut_end, lut_far = maps.profile_lut(default.pr, k_end), maps.profile_lut(default.pr, rf.scale_k(rf.view_at(9.0)))
    assert np.array_equal(lut_end, lut_far), "the shade and the water lines are the same as in the default end view"
    assert maps.COAST_PX == 3 and maps.REGION_LINE_PX == 3 and maps.GRAT_PX == 2


def test_the_venice_example_route_stays_on_water():
    """Fix round 1, point 6: the sea route of the Venice to Constantinople example has its `via` points in open water: from the Adriatic to the Aegean the dotted line is
    on sea at the start view and at the end view (the Dardanelles are narrower than a pixel of the data, so the last stretch is left out)."""
    import tempfile
    from tools.geo.render_map_examples import EXAMPLES, build_lab
    with tempfile.TemporaryDirectory() as tmp:
        p = open_project(build_lab(Path(tmp) / "maplab"))
        r = p._scene().shots[[s["id"] for s in p._saved["shots"]].index("s_venice")].base
        path = r.routes[0]["path"]
        assert len(EXAMPLES["venice"]["params"]["route"][0]["via"].split(";")) >= 8, "the route is bent through open water"
        checked = 0
        for v in r.sample_views():
            fd = r.base.field(v, r.scale_k(v))
            pts = path.samples(v, 1200)
            lon = np.degrees(path.at(np.linspace(0, path.length, 1200))[0])
            for (x, y), lo in zip(pts, lon):
                if lo > 25.9 or (lo < 13.0 and y < pts[0][1] + 30) or not (0 <= x < maps.W and 0 <= y < maps.H):
                    continue
                checked += 1
                assert fd.land[int(y), int(x)] < 128, (round(float(lo), 2), round(float(x)), round(float(y)))
        assert checked > 2000
