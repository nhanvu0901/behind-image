"""The channel identity "Raking Light": the seven techniques ID-* of docs/design/2026-11-18-identity-raking-light.md (sections 3 and 4).

Most checks draw real frames of a project whose picture is FLAT grey (or black) and that fills the canvas, so that brightness is the
light alone: three zones (ahead of the band, inside it, behind it), the band's position, the text revealed only behind it, the
levels of the dim styles, the end state equal to the plain picture, time scaling, every param at its min and max.
Run on the Windows server in a snapshot (never on the Mac): tools/deploy/snapshot_test.sh idengine -- tests/engine/test_identity.py -q
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from bti.engine import base, registry as R, vfx
from bti.engine.api import open_project
from bti.engine.vfx import Band
from conftest import REPO, words

IDS = ["ID-OPEN-01", "ID-LABEL-01", "ID-OPEN-02", "ID-BRAND-01", "ID-BRAND-02", "ID-MARK-01", "ID-MARK-02"]
OVERLAYS = ["ID-OPEN-01", "ID-LABEL-01", "ID-OPEN-02"]
BASES = ["ID-BRAND-01", "ID-BRAND-02", "ID-MARK-01", "ID-MARK-02"]
NOMINAL = {"ID-OPEN-01": 9.0, "ID-LABEL-01": 4.5, "ID-OPEN-02": 5.0, "ID-BRAND-01": 5.0, "ID-BRAND-02": 4.0, "ID-MARK-01": 3.2, "ID-MARK-02": 3.0}
FONT_SHA256 = {   # EB Garamond, https://github.com/octaviopardo/EBGaramond12 at e608414f52e532b68e2182f96b4ce9db35335593, fonts/ttf/
    "EBGaramond-Regular.ttf": "9a976a3e4b61a1eef1db06d4ee8a9f4c547a6550be50f199fdea661de33b350a",
    "EBGaramond-Italic.ttf": "76fab0d73445f2e5c5b5c6cacdff47dc9f7cbad664efc10ed7f2c7ee832e5a29",
    "EBGaramond-Medium.ttf": "697f8839ef1c2abfe5bb99d90fe732b96065cf3e73a7c8ef4b6eaf2842df51a2",
    "OFL.txt": "6f9e3a1c51f617e7b110862426204ec7a56d8c6d2f731373b5de6b8d069099b6",
}
CAM_FULL = [{"at": {"rel": 0.0}, "cx": 960, "cy": 540, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 960, "cy": 540, "zoom": 1.0, "ease": "linear"}]
GREY = 128
W, H = 1920, 1080


# ----------------------------------------------------------------------------- a project with a flat picture that fills the canvas
def shot(i, start, tech, extra=None, overlays=None, transition=None, camera=CAM_FULL):
    return {"id": "s%d" % i, "start": {"t": start}, "technique": tech, "intent": "structure", "slots": {"image": {"asset": "G"}},
            "params": dict({"camera": camera}, **(extra or {})), "transition_in": transition, "overlays": overlays or [], "locked": False,
            "source": "agent", "note": ""}


def ov(i, tech, start, dur, params=None):
    return {"id": "o%d" % i, "technique": tech, "intent": "establish", "start": {"t": start}, "dur": dur, "params": params or {},
            "locked": False, "source": "agent", "note": ""}


def make_lab(root, shots, level=GREY, name="lab", end=40.0, image=None):
    d = Path(root) / name
    (d / "media").mkdir(parents=True)
    img = image if image is not None else np.full((H, W, 3), level, np.uint8)
    cv2.imwrite(str(d / "media" / "g.png"), img)
    asset = {"file": "media/g.png", "kind": "image", "title": "Grey Field", "artist": "Nobody", "year": "1999", "width": img.shape[1], "height": img.shape[0],
             "credit": {"source": "test", "source_url": "", "author": "x", "licence": "PD", "licence_url": ""}}
    (d / "timing.json").write_text(json.dumps({"duration": 60.0, "words": words(), "beats": [], "chapters": []}), encoding="utf-8")
    sb = {"schema": "bti.storyboard/1", "project": name, "title": name, "style": "gae", "canvas": {"w": W, "h": H, "fps": 30}, "timing": "timing.json",
          "audio": None, "assets": {"G": asset}, "shots": shots, "end": {"t": end, "fade_s": 0}, "approvals": {"storyboard": None}}
    (d / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    p = open_project(d)
    assert [i for i in p.validate() if i["level"] == "error"] == [], p.validate()
    return p


def at(f, x, y, r=6):
    return f[y - r:y + r, x - r:x + r].reshape(-1, 3).astype(np.float64).mean(0)


def renderer(p, t, overlay=None):
    """The renderer object of the shot at t (or of its overlay number `overlay`), to read its state."""
    c = p._scene().shot_at(t)
    return c.base if overlay is None else dict(c.overlays)[overlay]


# ----------------------------------------------------------------------------- registry and style block
def test_registry_entries_are_complete():
    b = R.load_bundle("gae")
    from bti.engine import techniques  # noqa: F401
    assert R.check_registry(b) == []
    for tid in IDS:
        s = b.spec(tid)
        assert s and b.available(tid) and s["label_vi"] and len(s["description"]) > 30, tid
        assert s["engine"]["impl"] == "bti.engine.techniques.identity." + R.RENDERERS[tid][0].__name__
        assert s["timing"]["min_s"] == 1.5 and s["timing"]["default_s"] == NOMINAL[tid], tid           # an element is never shorter than 1.5 s
        assert (R.RENDERERS[tid][1], bool(s["slots"])) == (("overlay", False) if tid in OVERLAYS else ("base", True)), tid
        for p in s["params"]:
            if p["type"] == "number":
                assert p["min"] is not None and p["max"] is not None and p["min"] <= p["default"] <= p["max"] and p["unit"], (tid, p["name"])
        names = {p["name"] for p in s["params"]}
        if tid in BASES:
            assert {"camera", "shadow"} <= names and s["slots"][0]["name"] == "image" and s["intents"] == ["structure"], tid
        assert (REPO / "style/gae" / s["preview"]["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / s["preview"]["thumb"]).stat().st_size > 1000, tid


def test_style_block_names_the_techniques_of_each_style():
    b = R.load_bundle("gae")
    idn = b.style["identity"]
    assert idn["channel_name"] == "RAKING LIGHT" and idn["default_style"] == "raking" and set(idn["styles"]) == {"raking", "dim"}
    assert b.spec(idn["styles"]["dim"]["mark_transition"]["technique"])["kind"] == "transition"
    assert idn["styles"]["dim"]["mark_transition"]["dur"] == 0.75 and idn["styles"]["raking"]["mark_transition"] is None
    used = []
    for name, st in idn["styles"].items():
        assert st["label_vi"]
        for role, kind in (("open", "overlay"), ("label", "overlay"), ("brand", "base"), ("mark", "base")):
            tid = st[role]
            if tid is None:
                assert role == "label" and name == "dim"                # the dim style has no separate label
                continue
            assert b.spec(tid)["kind"] == kind and b.available(tid), (name, role)
            used.append(tid)
            nom = st["nominal"][role]
            assert nom["dur_s"] == NOMINAL[tid] and nom.get("start_s", 0) >= 0, (name, role)
    assert sorted(used) == sorted(IDS)
    assert idn["styles"]["raking"]["nominal"]["label"]["start_s"] == 6.2 and idn["styles"]["dim"]["nominal"]["open"]["start_s"] == 7.0
    assert idn["min_element_s"] == 1.5


# ----------------------------------------------------------------------------- fonts
def test_fonts_load_from_the_bundle_and_are_the_pinned_files():
    fdir = REPO / "style/gae/fonts"
    for name, digest in FONT_SHA256.items():
        assert hashlib.sha256((fdir / name).read_bytes()).hexdigest() == digest, name
    assert "SIL OPEN FONT LICENSE" in (fdir / "OFL.txt").read_text(encoding="utf-8")
    for kind in ("eb_regular", "eb_italic", "eb_medium"):
        ft = vfx.font(kind, 43)
        assert ft.getname()[0].startswith("EB Garamond") and Path(ft.path) == fdir / vfx.BUNDLED_FONTS[kind], (kind, ft.getname())
        assert 0.64 < vfx.cap_ratio(kind) < 0.66, kind
    sig = vfx.font_signature()
    assert all(("%s=" % k) in sig and "missing" not in sig for k in ("eb_regular", "eb_italic", "eb_medium"))


def test_a_missing_bundled_font_is_an_error_never_a_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(vfx, "bundled_font_dir", lambda: tmp_path / "no-fonts")
    for kind in ("eb_regular", "eb_italic", "eb_medium"):
        with pytest.raises(FileNotFoundError) as e:
            vfx.font(kind, 61)
        assert vfx.BUNDLED_FONTS[kind] in str(e.value) and "style/gae/fonts" in str(e.value) and "no-fonts" in str(e.value)
        assert (kind, 61) not in vfx._FONT_CACHE                                 # nothing was cached in its place
    assert "eb_regular=EBGaramond-Regular.ttf:missing" in vfx.font_signature()
    monkeypatch.undo()
    assert vfx.font("eb_regular", 61).getname()[0] == "EB Garamond"


def test_a_damaged_font_file_names_the_file(tmp_path, monkeypatch):
    (tmp_path / "EBGaramond-Italic.ttf").write_bytes(b"not a font")
    monkeypatch.setattr(vfx, "bundled_font_dir", lambda: tmp_path)
    with pytest.raises(vfx.BundledFontError) as e:
        vfx.font("eb_italic", 62)
    assert "EBGaramond-Italic.ttf" in str(e.value)


# ----------------------------------------------------------------------------- the band primitive
def test_band_geometry_speed_direction_and_width():
    b = Band(W, H, 14, 0.4, 10, "right_to_left")
    a = math.radians(10)
    assert b.length == pytest.approx(W * math.cos(a) + H * math.sin(a))
    assert b.centre(0.5) == pytest.approx(0.0, abs=1e-6)
    assert b.centre(0.0) > 0 > b.centre(1.0)                                        # right to left
    assert abs(b.centre(0.0)) >= b.length / 2 + b.half and abs(b.centre(1.0)) >= b.length / 2 + b.half      # off the canvas at both ends
    assert b.centre(0.25) - b.centre(0.0) == pytest.approx(b.centre(0.5) - b.centre(0.25))               # constant speed
    ltr = Band(W, H, 14, 0.4, 10, "left_to_right")
    assert ltr.centre(0.0) < 0 < ltr.centre(1.0) and ltr.centre(0.3) == pytest.approx(-b.centre(0.3))
    s = np.linspace(-600, 600, 120001)
    inside = s[b.profile(s) >= 0.5]
    assert inside.max() - inside.min() == pytest.approx(0.14 * W, abs=0.5)           # band_width_pct is the width at half brightness
    assert b.profile(np.array([0.0]))[0] == 1.0 and b.profile(np.array([b.half + 1]))[0] == 0.0
    plateau = s[b.profile(s) >= 0.9999]
    assert plateau.max() - plateau.min() == pytest.approx(b.core, abs=2.0) and b.core == pytest.approx(0.6 * 0.14 * W)


def test_revealed_means_the_largest_value_the_band_had_so_far():
    """For a band moving one way at constant speed the closed form equals the running maximum of the mask over earlier times."""
    b = Band(W, H, 16, 0.4, 10, "left_to_right")
    xs, ys = np.array([100.5, 700.5, 960.5, 1500.5, 1800.5], np.float32), np.array([100.5, 540.5, 900.5], np.float32)
    seen = np.zeros((3, 5))
    for k, q in enumerate(np.linspace(0, 1, 401)):
        seen = np.maximum(seen, b.profile(b.s_grid(q, xs, ys)))
        if k in (0, 100, 200, 300, 400):
            assert np.allclose(b.reveal(b.s_grid(q, xs, ys)), seen, atol=2e-3), q
    assert np.all(b.reveal(b.s_grid(1.0, xs, ys)) == 1.0) and np.all(b.reveal(b.s_grid(0.0, xs, ys)) == 0.0)


# ----------------------------------------------------------------------------- ID-OPEN-01: band position, three zones, end state
def test_open_raking_levels_and_zones_on_a_flat_picture(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 9.0)])])
    f = lambda t: p.frame_at(t, W)
    assert f(0.2).max() == 0                                                         # black for the first 0.4 s
    f13 = f(1.3)                                                                     # picture at the floor, band not started
    assert f13.min() == f13.max() and abs(float(f13[0, 0, 0]) - 0.10 * GREY) < 1.01
    mid = f(4.5)                                                                     # halfway through the sweep: band at the centre
    ahead, inside, behind = at(mid, 300, 540), at(mid, 960, 540), at(mid, 1620, 540)    # right to left: ahead = left, behind = right
    assert np.allclose(ahead, 0.10 * GREY, atol=1.5) and np.allclose(behind, 0.45 * GREY, atol=1.5)
    tint = np.array([140, 205, 255]) / 255.0                                         # screen blend of the warm amber at 14 %
    assert np.allclose(inside, GREY * (1 - 0.14 * tint) + 255 * 0.14 * tint, atol=2.0)
    assert inside[2] > inside[1] > inside[0] > GREY                                  # warm: more red than green than blue, all above the picture
    rel = f(8.0)                                                                     # release: 0.5 s into the 1.5 s rise, smoothstep 0.259
    assert rel.min() == rel.max() and abs(float(rel[0, 0, 0]) - GREY * (0.45 + 0.55 * 0.2593)) < 1.5
    plain = make_lab(tmp_path, [shot(1, 0.0, "CAM-01")], name="plain").frame_at(10.0, W)
    for t in (9.0, 9.5, 11.0):                                                       # the end state equals the plain picture, exactly
        assert np.array_equal(f(t), plain), t
    assert np.abs(f(8.999).astype(int) - plain.astype(int)).max() <= 1


@pytest.mark.parametrize("t, expected_x", [(3.0, 1720.3), (4.5, 960.0), (6.0, 199.7)])
def test_open_raking_band_position_at_given_times(tmp_path, t, expected_x):
    """Right to left from 1.5 s to 7.5 s: 25 %, 50 %, 75 % of the travel. The expected x on the row y = 540 is worked out by hand:
    axis length 2078.4 px (1920 cos 10 + 1080 sin 10), band half-extent 188.2 px, run-in 13 % of the axis."""
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 9.0)])])
    row = p.frame_at(t, W)[540, :, 1].astype(float)
    xs = np.nonzero(row >= row.max() * 0.985)[0]                                   # the plateau of the band (100 % plus the tint)
    assert xs.size > 100 and abs((xs.min() + xs.max()) / 2 + 0.5 - expected_x) < 5, (xs.min(), xs.max())


def test_open_raking_band_edges_are_tilted_ten_degrees(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 9.0)])])
    f = p.frame_at(4.5, W)[:, :, 1].astype(float)
    def centre(y):
        xs = np.nonzero(f[y] >= f[y].max() * 0.985)[0]
        return (xs.min() + xs.max()) / 2
    dx = centre(980) - centre(100)
    assert dx == pytest.approx(-880 * math.tan(math.radians(10)), abs=4)              # a "/" : the top is further right than the bottom


def test_open_raking_direction_ltr_swaps_ahead_and_behind(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 9.0, {"direction": "left_to_right"})])])
    f = p.frame_at(4.5, W)
    assert np.allclose(at(f, 300, 540), 0.45 * GREY, atol=1.5) and np.allclose(at(f, 1620, 540), 0.10 * GREY, atol=1.5)


# ----------------------------------------------------------------------------- text revealed by the band (ID-MARK-01, ID-BRAND-01)
def ink_diff(a, b):
    return np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)


@pytest.mark.parametrize("tid, text_param, text, t_mid, t_done, t_hold", [("ID-MARK-01", "title", "5. The Mirror", 1.1, 2.4, 2.2),
                                                                           ("ID-BRAND-01", "text", "RAKING LIGHT", 1.8, 3.4, 3.1)])
def test_text_appears_only_behind_the_band_and_stays(tmp_path, tid, text_param, text, t_mid, t_done, t_hold):
    narrow = {"band_width_pct": 4}                                                        # narrower than the text, so that it has a front, a middle and a wake
    on = make_lab(tmp_path, [shot(1, 0.0, tid, dict(narrow, **{text_param: text}))], name="on")
    off = make_lab(tmp_path, [shot(1, 0.0, tid, dict(narrow, **{text_param: ""}))], name="off")      # the same light, no text: the difference is the text
    d = lambda t: ink_diff(on.frame_at(t, W), off.frame_at(t, W))
    done, hold = d(t_done), d(t_hold)
    assert (done > 100).sum() > 600 and np.array_equal(done, hold)                        # after the sweep the whole text is there and stays
    cols = np.nonzero((done > 100).any(axis=0))[0]
    q = (t_mid - (0.1 if tid == "ID-MARK-01" else 0.6)) / (2.0 if tid == "ID-MARK-01" else 2.4)
    band = Band(W, H, 4, 0.4, 10, "left_to_right")
    s = band.s_grid(q, np.arange(W, dtype=np.float32) + 0.5, np.arange(H, dtype=np.float32) + 0.5)
    mid = d(t_mid)
    ahead = s > band.core / 2 + band.edge + 8                                             # the mask has not reached these pixels yet
    behind = s < -band.half - 8                                                           # the band has fully passed these pixels
    assert mid[ahead].max() == 0, "text (or its shadow) drawn ahead of the band"
    assert np.abs(mid[behind & (done > 0)].astype(int) - done[behind & (done > 0)].astype(int)).max() <= 2
    assert (mid > 100).sum() > 0 and (mid > 100).sum() < (done > 100).sum()                # partly written at mid sweep
    assert behind[:, cols].any() and ahead[:, cols].any()                                 # the probe is meaningful: the text spans both sides
    counts = [int((d(t) > 100).sum()) for t in (t_mid - 0.5, t_mid, t_mid + 0.5, t_done)]
    assert counts == sorted(counts) and counts[0] < counts[-1]                            # the writing only grows


def test_mark_raking_text_leaves_and_the_picture_returns(tmp_path):
    on = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-01", {"title": "5. The Mirror"})], name="on")
    off = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-01", {"title": ""})], name="off")
    assert (ink_diff(on.frame_at(2.45, W), off.frame_at(2.45, W)) > 100).sum() > 600
    assert ink_diff(on.frame_at(2.7, W), off.frame_at(2.7, W)).max() > 0 and (ink_diff(on.frame_at(2.9, W), off.frame_at(2.9, W)) > 100).sum() == 0
    assert np.array_equal(on.frame_at(2.9, W), off.frame_at(2.9, W))                       # the text is gone after text_fade_out_s
    plain = make_lab(tmp_path, [shot(1, 0.0, "CAM-01")], name="plain").frame_at(1.0, W)
    assert np.abs(on.frame_at(3.199, W).astype(int) - plain.astype(int)).max() <= 1


def test_brand_raking_levels(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "ID-BRAND-01", {"text": "RAKING LIGHT"})])
    assert np.array_equal(p.frame_at(0.0, W), make_lab(tmp_path, [shot(1, 0.0, "CAM-01")], name="plain").frame_at(0.0, W))      # starts on the picture
    f06 = p.frame_at(0.6, W)
    assert abs(float(f06[0, 0, 0]) - 0.12 * GREY) < 1.01 and f06.min() == f06.max()
    mid = p.frame_at(1.8, W)                                                          # left to right, halfway: ahead = right, behind = left
    assert np.allclose(at(mid, 1700, 100), 0.12 * GREY, atol=1.5) and np.allclose(at(mid, 200, 100), 0.26 * GREY, atol=1.5)
    end = p.frame_at(4.0, W)                                                          # the sweep ended at 3.0 s: all behind, settled at 26 %
    assert np.allclose(at(end, 100, 100), 0.26 * GREY, atol=1.5) and np.allclose(at(end, 1800, 1000), 0.26 * GREY, atol=1.5)
    assert end.max() > 200                                                            # the name is on screen (text ink)


# ----------------------------------------------------------------------------- the dim styles
def test_dim_levels_of_the_opening_and_the_beat_and_the_mark(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-02", 0.0, 5.0, {"title": "", "sub": ""})]),
                            shot(2, 6.0, "ID-BRAND-02", {"text": ""}), shot(3, 10.0, "ID-MARK-02", {"title": ""})], end=14.0)
    lvl = lambda t: float(at(p.frame_at(t, W), 60, 60)[0])
    # ID-OPEN-02: dim to 45 % in 1.0 s, hold, back to 100 % over the last 1.0 s (smoothstep both ways)
    assert abs(lvl(0.0) - GREY) < 1
    assert abs(lvl(0.5) - GREY * (1 - 0.55 * 0.5)) < 1.2 and abs(lvl(1.0) - 0.45 * GREY) < 1.2 and abs(lvl(2.5) - 0.45 * GREY) < 1.2
    assert abs(lvl(4.5) - GREY * (1 - 0.55 * 0.5)) < 1.2 and abs(lvl(4.999) - GREY) < 1.2
    # ID-BRAND-02: dim to 25 % in 0.8 s and stay until the hard cut
    assert abs(lvl(6.0) - GREY) < 1 and abs(lvl(6.4) - GREY * (1 - 0.75 * 0.5)) < 1.2 and abs(lvl(6.8) - 0.25 * GREY) < 1.2 and abs(lvl(9.9) - 0.25 * GREY) < 1.2
    # ID-MARK-02: dim to 40 % in 0.6 s, from 2.4 s back to 100 % over 0.6 s
    assert abs(lvl(10.3) - GREY * (1 - 0.6 * 0.5)) < 1.2 and abs(lvl(10.6) - 0.40 * GREY) < 1.2 and abs(lvl(12.3) - 0.40 * GREY) < 1.2
    assert abs(lvl(12.7) - GREY * (1 - 0.6 * 0.5)) < 1.2 and abs(lvl(12.999) - GREY) < 1.2


def test_dim_text_fades_in_holds_and_fades_out(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-02", {"title": "5. The Mirror"})], level=0, end=10.0)       # black picture: all light is text
    q = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-02", {"title": "5. The Mirror"})], level=0, name="q", end=10.0)
    peak = lambda t: int(p.frame_at(t, W).max())
    assert peak(0.2) == 0 and peak(0.3) == 0                                          # text_in_delay_s 0.3
    assert 0 < peak(0.5) < peak(0.7) == peak(1.2) == peak(2.3) and peak(0.7) > 200      # fades in over 0.4 s, holds
    assert 0 < peak(2.6) < peak(2.3) and peak(2.81) == 0                              # fades out over 0.4 s from 2.4 s
    assert np.array_equal(p.frame_at(1.0, W), q.frame_at(1.0, W))


def test_open_dim_title_then_sub_line_in_the_right_places(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-02", 0.0, 5.0, {"title": "Hands", "sub": "Jan van Eyck · 1434"})])], level=0)
    ink = lambda t: p.frame_at(t, W).max(axis=2) > 90
    rows = lambda m: np.nonzero(m.any(axis=1))[0]
    assert not ink(0.1).any()
    title_only = rows(ink(0.65))
    assert title_only.size and 0.75 * H < title_only.mean() < 0.80 * H                     # the title is centred at 78 % of the height
    both = rows(ink(2.5))
    assert both.max() > title_only.max() + 20                                              # the small line (85.5 %) joins 0.4 s later
    sub = ink(2.5)[int(0.835 * H):int(0.88 * H)]
    cols = np.nonzero(sub.any(axis=0))[0]
    assert sub.any() and abs((cols.min() + cols.max()) / 2 - W / 2) < 6                    # centred
    assert not ink(5.0).any()                                                              # the overlay ends clean


# ----------------------------------------------------------------------------- text sizes and placement
@pytest.mark.parametrize("cap_pct", [3.0, 4.5, 7.0])
def test_cap_height_is_a_percentage_of_the_frame_height(tmp_path, cap_pct):
    p = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-02", {"title": "HHHH", "cap_pct": cap_pct, "y_pct": 40})], level=0, end=10.0)
    m = p.frame_at(1.2, W).max(axis=2) > 128
    ys, xs = np.nonzero(m)
    assert (ys.max() - ys.min() + 1) == pytest.approx(cap_pct / 100 * H, abs=2.5)       # the real cap height of EB Garamond (H), measured
    assert (ys.min() + ys.max()) / 2 == pytest.approx(0.40 * H, abs=2.5)                 # the middle of the capitals sits at y_pct
    assert (xs.min() + xs.max()) / 2 == pytest.approx(W / 2, abs=2.5)


def test_brand_text_is_capitals_tracked_and_centred(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "ID-BRAND-02", {"text": "raking light"})], level=0, end=10.0)
    m = p.frame_at(2.0, W).max(axis=2) > 128
    ys, xs = np.nonzero(m)
    assert 0.07 * H - 3 <= ys.max() - ys.min() + 1 <= 0.07 * H * 1.15 + 3                # capitals even for lower-case input (R, G and T reach a little beyond the cap height)
    assert (xs.min() + xs.max()) / 2 == pytest.approx(W / 2, abs=3) and (ys.min() + ys.max()) / 2 == pytest.approx(0.46 * H, abs=3)
    assert xs.max() - xs.min() > 0.25 * W                                                  # tracking +25 %: a wide line


def test_a_line_that_is_too_long_is_made_smaller_not_wrapped(tmp_path):
    title = "The Meeting of the Magi " * 4
    p = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-02", {"title": title.strip()})], level=0, end=10.0)
    m = p.frame_at(1.2, W).max(axis=2) > 128
    ys, xs = np.nonzero(m)
    assert xs.max() - xs.min() <= 0.88 * W + 6 and xs.max() - xs.min() > 0.7 * W
    assert ys.max() - ys.min() < 0.045 * H * 2                                             # one line: not twice the cap height


@pytest.mark.parametrize("text", ["", " ", "é" * 3, "Ệ ư ơ ă â đ", "x" * 120, "日本語"])
def test_odd_text_draws(tmp_path, text):
    p = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-02", {"title": text}), shot(2, 4.0, "ID-BRAND-01", {"text": text})], end=10.0)
    for t in (1.0, 2.8, 6.0):
        assert p.frame_at(t, 480).shape == (270, 480, 3)


def test_label_two_lines_bottom_left_without_a_strip(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-LABEL-01", 0.0, 4.5, {"title": "The Arnolfini Portrait", "artist_year": "Jan van Eyck, 1434"})])],
                 level=0, end=10.0)
    assert not p.frame_at(0.0, W).any()                                                    # fades in over 0.5 s
    f = p.frame_at(2.0, W)
    ys, xs = np.nonzero(f.max(axis=2) > 120)
    assert xs.min() == pytest.approx(0.04 * W, abs=12) and xs.max() < 0.5 * W              # left margin 4 % of the width, a short block
    assert 0.80 * H < ys.min() and ys.max() < 0.94 * H                                     # the block lies between about 84 % and 92 % of the height
    assert 0.0 < p.frame_at(0.25, W).max() < f.max() and p.frame_at(4.25, W).max() < f.max() and not p.frame_at(4.5, W).any()
    # no strip, box or flat ground: away from the letters the picture is untouched (black here), apart from the soft shadow's reach
    assert not f[: int(0.75 * H)].any() and not f[:, int(0.6 * W):].any()


# ----------------------------------------------------------------------------- time scaling
def test_a_shorter_element_scales_every_time(tmp_path):
    ov_short = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 4.5)])], name="a")
    ov_nom = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 9.0)])], name="b")
    ov_long = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 14.0)])], name="c")
    for frac in (0.1, 0.3, 0.5, 0.7, 0.95):                                              # half the length: every time halves
        assert np.array_equal(ov_short.frame_at(frac * 4.5, W), ov_nom.frame_at(frac * 9.0, W)), frac
    assert renderer(ov_short, 1.0, 0).k == 0.5 and renderer(ov_nom, 1.0, 0).k == 1.0 and renderer(ov_long, 1.0, 0).k == 1.0
    assert np.array_equal(ov_long.frame_at(4.5, W), ov_nom.frame_at(4.5, W))              # a longer overlay keeps the nominal times
    assert np.array_equal(ov_long.frame_at(9.5, W), ov_long.frame_at(13.5, W))            # and is plain after the release
    for tid, extra in (("ID-MARK-01", {"title": "5. The Mirror"}), ("ID-MARK-02", {"title": "5. The Mirror"}), ("ID-BRAND-01", {"text": "RAKING LIGHT"}),
                       ("ID-BRAND-02", {"text": "RAKING LIGHT"})):
        nom = NOMINAL[tid]
        short = make_lab(tmp_path, [shot(1, 0.0, tid, extra), shot(2, nom / 2, "CAM-01")], name="s" + tid)
        full = make_lab(tmp_path, [shot(1, 0.0, tid, extra), shot(2, nom, "CAM-01")], name="f" + tid)
        for frac in (0.15, 0.4, 0.6, 0.9):
            a, b = short.frame_at(frac * nom / 2, W), full.frame_at(frac * nom, W)
            if tid == "ID-BRAND-02" and frac > 0.8:
                continue                                                                  # the fade-out is anchored at the end of the shot, in both
            assert np.array_equal(a, b), (tid, frac)


def test_label_fades_scale_with_a_short_overlay(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-LABEL-01", 0.0, 2.25, {"title": "Title", "artist_year": "Artist, 1900"})])], level=0, end=10.0)
    r = renderer(p, 0.5, 0)
    assert r.k == 0.5 and r.envelope(0.125) == pytest.approx(0.5) and r.envelope(1.0) == pytest.approx(1.0) and r.envelope(2.125) == pytest.approx(0.5)


def test_branding_fade_out_is_anchored_at_the_end_of_the_shot(tmp_path):
    for length in (4.0, 6.0, 2.0):
        p = make_lab(tmp_path, [shot(1, 0.0, "ID-BRAND-02", {"text": "RAKING LIGHT"}), shot(2, length, "CAM-01")], level=0, name="b%g" % length)
        k = min(1.0, length / 4.0)
        peak = lambda t: int(p.frame_at(t, W).max())
        assert peak(length - 0.6 * k - 0.02) > 200 and 0 < peak(length - 0.3 * k) < peak(length - 0.6 * k - 0.02) and peak(length - 0.01) < 12


# ----------------------------------------------------------------------------- the picture is CAM-01's
def gradient(w=1500, h=1000):
    yy, xx = np.mgrid[0:h, 0:w]
    return np.stack([xx * 255 // w, yy * 255 // h, (xx + yy) * 255 // (w + h)], -1).astype(np.uint8)


@pytest.mark.parametrize("tid, neutral", [("ID-BRAND-01", {"text": "", "floor": 1.0, "wake": 1.0}), ("ID-BRAND-02", {"text": "", "dim": 1.0}),
                                          ("ID-MARK-01", {"title": "", "floor": 1.0, "wake": 1.0}), ("ID-MARK-02", {"title": "", "dim": 1.0})])
def test_base_techniques_draw_the_picture_exactly_as_cam01_does(tmp_path, tid, neutral):
    cam = [{"at": {"rel": 0.0}, "cx": 700, "cy": 480, "zoom": 0.9, "ease": "inout_sine"}, {"at": {"rel": 1.0}, "cx": 820, "cy": 520, "zoom": 1.1, "ease": "linear"}]
    img = gradient()
    a = make_lab(tmp_path, [shot(1, 0.0, tid, neutral, camera=cam)], image=img, name="a", end=8.0)
    b = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", camera=cam)], image=img, name="b", end=8.0)
    for t in (0.2, 1.7, 3.9):
        assert np.array_equal(a.frame_at(t, W), b.frame_at(t, W)), t
        va, vb = renderer(a, t).view(t), renderer(b, t).view(t)
        assert (va.cx, va.cy, va.z, va.asset_key) == (vb.cx, vb.cy, vb.z, vb.asset_key)


def test_an_overlay_can_sit_on_a_base_identity_technique(tmp_path):
    cam = [{"at": {"rel": 0.0}, "cx": 700, "cy": 480, "zoom": 0.9, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 700, "cy": 480, "zoom": 0.9, "ease": "linear"}]
    ring = {"id": "o9", "technique": "AN-01", "intent": "point_at", "start": {"t": 0.2}, "dur": 2.5, "params": {"at": [700, 480], "radius": 120}, "locked": False, "source": "agent", "note": ""}
    img = gradient()
    with_ring = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-02", {"title": ""}, overlays=[ring], camera=cam)], image=img, name="a", end=8.0)
    without = make_lab(tmp_path, [shot(1, 0.0, "ID-MARK-02", {"title": ""}, camera=cam)], image=img, name="b", end=8.0)
    assert not np.array_equal(with_ring.frame_at(1.8, W), without.frame_at(1.8, W))
    assert renderer(with_ring, 1.0).view(1.0) is not None


# ----------------------------------------------------------------------------- purity, params, defaults
def test_a_frame_is_a_pure_function_of_time(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, "ID-OPEN-01", 0.0, 9.0), ov(2, "ID-LABEL-01", 6.2, 2.0)]),
                            shot(2, 12.0, "ID-MARK-01", {"title": "5. The Mirror"}), shot(3, 16.0, "ID-BRAND-01", {"text": "RAKING LIGHT"})], end=24.0)
    times = [17.0, 3.1, 12.7, 6.9, 1.0, 14.0, 20.5]
    first = {t: p.frame_at(t, 640) for t in times}
    base.LAYERS.clear(); base.IMAGES.clear(); base.MISC.clear()
    for t in reversed(times):
        assert np.array_equal(p.frame_at(t, 640), first[t]), t


@pytest.mark.parametrize("tid", IDS)
def test_every_param_at_min_and_max_draws(tmp_path, tid):
    """Each number at its registry min and max (the others at their defaults), at three moments of the element; and the odd enum values."""
    spec = R.load_bundle("gae").spec(tid)
    nominal = NOMINAL[tid]
    extra = {"title": "5. The Mirror"} if "MARK" in tid else ({"text": "RAKING LIGHT"} if "BRAND" in tid else {})

    def build(params, name):
        if tid in OVERLAYS:
            return make_lab(tmp_path, [shot(1, 0.0, "CAM-01", overlays=[ov(1, tid, 0.0, nominal, params)])], name=name, end=20.0)
        return make_lab(tmp_path, [shot(1, 0.0, tid, dict(extra, **params)), shot(2, nominal, "CAM-01")], name=name, end=20.0)

    n = 0
    for pd in spec["params"]:
        values = [pd["min"], pd["max"]] if pd["type"] == "number" else (pd["values"] if pd["type"] == "enum" else [])
        for v in values:
            p = build({pd["name"]: v}, "p%d" % n)
            n += 1
            for t in (0.2 * nominal, 0.6 * nominal, 0.97 * nominal):
                assert p.frame_at(t, 320).shape == (180, 320, 3), (tid, pd["name"], v, t)
    assert n >= 4


def test_default_params_come_from_the_context_and_the_style(tmp_path):
    p = make_lab(tmp_path, [shot(1, 0.0, "CAM-01")])
    brand = p.default_params("ID-BRAND-01", {"asset": "G"})
    assert brand["text"] == "RAKING LIGHT" and [k["at"] for k in brand["camera"]] == [{"rel": 0.0}, {"rel": 1.0}]
    assert brand["camera"][1]["zoom"] / brand["camera"][0]["zoom"] == pytest.approx(1.03, rel=1e-3) and brand["camera"][0]["cx"] == 960
    assert p.default_params("ID-BRAND-02", {})["camera"] is None
    assert p.default_params("ID-MARK-01", {"title": "7. Hands"})["title"] == "7. Hands"
    lab = p.default_params("ID-LABEL-01", {"asset": "G"})
    assert lab["title"] == "Grey Field" and lab["artist_year"] == "Nobody, 1999"
    op = p.default_params("ID-OPEN-02", {"asset": "G"})
    assert op["title"] == "Grey Field" and op["sub"] == "Nobody · 1999"
    for tid in IDS:
        spec = R.load_bundle("gae").spec(tid)
        assert [i for i in R.validate_params(spec, p.default_params(tid, {"asset": "G", "text": "T"}), tid) if i["level"] == "error"] == [], tid


def test_the_sample_project_draws_every_technique(arnolfini, tmp_path):
    """The real picture (Arnolfini) with each technique: a frame draws, validate is clean."""
    sb = arnolfini.storyboard()
    first = sb["shots"][0]
    from identity_lab import append_identity_shots
    append_identity_shots(sb, first["slots"]["image"]["asset"], first["params"]["camera"])
    assert [i for i in arnolfini.validate(sb) if i["level"] == "error"] == []
    arnolfini.use_draft(sb)
    try:
        rs = arnolfini.resolve(sb)
        for s in rs["shots"][-6:]:
            assert arnolfini.frame_at(s["_t0"] + 0.5 * (s["_t1"] - s["_t0"]), 320).shape == (180, 320, 3), s["technique"]
    finally:
        arnolfini.use_draft(None)
