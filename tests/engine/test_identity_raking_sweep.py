"""ID-BRAND-04: the raking light sweep ident (variants A, B, C).

Tests registration, non-interference with existing style defaults, frame rendering across variants and painting layouts
(textured, flat, portrait, landscape, top/middle/bottom regions), relief modulation vs relief=0, return to plain picture
at end, and purity as a function of time.
"""
from __future__ import annotations

import numpy as np
import pytest

from bti.engine import base, registry as R
from bti.engine.techniques import identity as ID
from test_identity import CAM_FULL, H, W, make_lab, renderer, shot

TID = "ID-BRAND-04"
VARIANTS = ("A", "B", "C")


def _textured_painting(w=1200, h=1600):
    """Synthetic oil-painting-like texture with impasto ridges and tonal variation (no external file)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    pat = (
        115.0
        + 38.0 * np.sin(xx / 19.0 + 0.4 * np.cos(yy / 17.0))
        + 26.0 * np.cos(yy / 13.0 - 0.3 * np.sin(xx / 23.0))
        + 14.0 * np.sin((xx + yy) / 7.5)
    )
    bgr = np.stack([pat * 0.85, pat * 0.96, pat * 1.05], axis=-1)
    return np.clip(bgr, 15, 240).astype(np.uint8)


def _make_lab_regions(tmp_path, shots, regions, *, image, name, end):
    p = make_lab(tmp_path, shots, image=image, name=name, end=end)
    sb = p.storyboard()
    sb["assets"]["G"]["regions"] = regions
    for s in sb["shots"]:
        if s["technique"] == TID and s["params"].get("_pending_region"):
            s["params"]["region"] = s["params"].pop("_pending_region")
    p.save(sb)
    assert [i for i in p.validate() if i["level"] == "error"] == []
    return p


@pytest.mark.parametrize("variant", VARIANTS)
def test_variants_render_start_middle_rest_and_end(tmp_path, variant):
    img = _textured_painting()
    cam = [{"at": {"rel": 0.0}, "cx": 600, "cy": 800, "zoom": 0.62, "ease": "linear"},
           {"at": {"rel": 1.0}, "cx": 600, "cy": 800, "zoom": 0.66, "ease": "linear"}]
    p = _make_lab_regions(
        tmp_path,
        [shot(1, 0.0, TID, {"variant": variant, "_pending_region": "DETAIL", "title": "A Question About the Surface", "subtitle": "Untitled Study · Painter, 1650"}, camera=cam),
         shot(2, 8.0, "CAM-01", camera=cam)],
        {"DETAIL": {"x": 620, "y": 720, "rx": 120, "ry": 110}},
        image=img, name=f"tex_{variant}", end=12.0,
    )

    for t in (0.6, 2.0, 5.2, 7.99):
        fr = p.frame_at(t, 640)
        assert fr.shape == (360, 640, 3) and fr.dtype == np.uint8

    # End state returns cleanly to the plain CAM-01 painting (same shot timing so camera matches).
    plain = make_lab(tmp_path, [shot(1, 0.0, "CAM-01", camera=cam), shot(2, 8.0, "CAM-01", camera=cam)], image=img, name=f"plain_{variant}", end=12.0)
    assert np.array_equal(p.frame_at(7.999, 640), plain.frame_at(7.999, 640))


@pytest.mark.parametrize("variant", VARIANTS)
def test_relief_modulates_textured_surface_during_grazing_light(tmp_path, variant):
    img = _textured_painting()
    cam = [{"at": {"rel": 0.0}, "cx": 600, "cy": 800, "zoom": 0.65, "ease": "linear"},
           {"at": {"rel": 1.0}, "cx": 600, "cy": 800, "zoom": 0.65, "ease": "linear"}]
    common = {"variant": variant, "_pending_region": "DETAIL", "title": "Surface Study", "subtitle": "Work · Artist, 1500"}
    regs = {"DETAIL": {"x": 600, "y": 760, "rx": 130, "ry": 120}}
    p_rel = _make_lab_regions(tmp_path, [shot(1, 0.0, TID, dict(common, relief=1.2), camera=cam)], regs, image=img, name=f"rel_{variant}", end=9.0)
    p_off = _make_lab_regions(tmp_path, [shot(1, 0.0, TID, dict(common, relief=0.0), camera=cam)], regs, image=img, name=f"off_{variant}", end=9.0)

    t_probe = {"A": 2.2, "B": 1.6, "C": 1.2}[variant]
    a = p_rel.frame_at(t_probe, 640).astype(np.int16)
    b = p_off.frame_at(t_probe, 640).astype(np.int16)
    assert np.abs(a - b).mean() > 0.5, f"variant {variant} showed negligible relief modulation"


@pytest.mark.parametrize("variant", VARIANTS)
def test_flat_image_and_landscape_region_positions_render_cleanly(tmp_path, variant):
    flat = make_lab(tmp_path, [shot(1, 0.0, TID, {"variant": variant, "title": "Title", "subtitle": "Sub"})], name=f"flat_{variant}", end=9.0)
    assert flat.frame_at(2.0, 480).shape == (270, 480, 3)

    land = _textured_painting(1920, 1080)
    for tag, ry in (("top", 160), ("bottom", 860)):
        p = _make_lab_regions(
            tmp_path,
            [shot(1, 0.0, TID, {"variant": variant, "_pending_region": "R", "title": "Landscape Check", "subtitle": "Canvas · Artist, 1700"}, camera=CAM_FULL)],
            {"R": {"x": 960, "y": ry, "rx": 160, "ry": 110}},
            image=land, name=f"{variant}_{tag}", end=9.0,
        )
        assert p.frame_at(5.0, 640).shape == (360, 640, 3)


def test_pure_function_of_time_and_defaults_and_style_unchanged(tmp_path):
    b = R.load_bundle("gae")
    from bti.engine import techniques  # noqa: F401

    assert R.check_registry(b) == []
    spec = b.spec(TID)
    assert spec and b.available(TID)
    assert spec["offered"] is False and spec["hidden_reason"]["code"] == "program"
    assert R.RENDERERS[TID] == (ID.BrandRakingSweep, "base")

    # Default raking style now points to ID-BRAND-04 variant B, keeping earlier ID-BRAND-01 and ID-BRAND-03.
    idn = b.style["identity"]
    assert idn["default_style"] == "raking"
    assert idn["styles"]["raking"]["brand"] == TID
    assert idn["styles"]["raking"]["brand_params"] == {"variant": "B"}
    assert idn["styles"]["raking"]["earlier"] == {"brand": ["ID-BRAND-01", "ID-BRAND-03"]}
    assert idn["styles"]["dim"]["brand"] == "ID-BRAND-02"
    assert spec["timing"]["default_s"] == 9.1 and spec["timing"]["min_s"] == 1.5
    assert next(p for p in spec["params"] if p["name"] == "variant")["default"] == "B"

    p = make_lab(tmp_path, [shot(1, 0.0, TID, {"variant": "B", "title": "Purity", "subtitle": "Work · Artist, 1600"})], end=9.1)
    assert [i for i in R.validate_params(spec, p.default_params(TID, {"asset": "G"}), TID) if i["level"] == "error"] == []
    assert [i for i in R.validate_params(spec, p.default_params(TID, {}), TID) if i["level"] == "error"] == []

    times = [0.7, 2.1, 5.4, 7.6]
    first = {t: p.frame_at(t, 480) for t in times}
    base.LAYERS.clear()
    base.IMAGES.clear()
    base.MISC.clear()
    for t in reversed(times):
        assert np.array_equal(p.frame_at(t, 480), first[t]), t


@pytest.mark.parametrize("shape_tag,w,h,region,reg_box", [
    ("tall", 800, 1600, "SPOT", {"x": 400, "y": 320, "rx": 90, "ry": 90, "tight": True}),
    ("wide", 1920, 800, "SPOT", {"x": 960, "y": 620, "rx": 130, "ry": 90, "tight": True}),
    ("square", 1200, 1200, None, None),
    ("upper_spot", 1000, 1400, "SPOT", {"x": 500, "y": 430, "rx": 40, "ry": 40, "tight": True}),
])
def test_texts_clear_of_rest_region_across_painting_shapes(tmp_path, shape_tag, w, h, region, reg_box):
    """Rest-time channel name (dimmed), title, and subtitle stay visible and clear of the lit region and each other."""
    from bti.engine.techniques.camera import fit_zoom
    img = np.full((h, w, 3), 90, np.uint8)
    img[h // 3:2 * h // 3, w // 3:2 * w // 3] = (125, 118, 108)
    z0 = min(round(fit_zoom(h), 5), round(0.96 * 1920 / w, 5))
    cam = [{"at": {"rel": 0.0}, "cx": w / 2, "cy": h / 2, "zoom": z0, "ease": "linear"},
           {"at": {"rel": 1.0}, "cx": w / 2, "cy": h / 2, "zoom": round(z0 * 1.03, 5), "ease": "linear"}]
    p = _make_lab_regions(
        tmp_path,
        [shot(1, 0.0, TID, {"variant": "B", "_pending_region": region, "title": "Shape Check", "subtitle": "Work · Artist, 1500"}, camera=cam)],
        ({region: reg_box} if region and reg_box else {}),
        image=img, name=f"shape_{shape_tag}", end=9.1,
    )
    rend = p._scene().shots[0].base
    assert rend.fade_name_at_rest is False
    r_top, r_bot = rend.rest_box_pct
    ys = [rend.name_y_pct, rend.title_y_pct, rend.sub_y_pct]
    for label, y_pct in (("name", rend.name_y_pct), ("title", rend.title_y_pct), ("sub", rend.sub_y_pct)):
        assert y_pct < r_top or y_pct > r_bot, (shape_tag, label, y_pct, r_top, r_bot)
        assert 5.0 <= y_pct <= 95.0, (shape_tag, label, y_pct)
    for a, b in ((ys[0], ys[1]), (ys[0], ys[2]), (ys[1], ys[2])):
        assert abs(a - b) >= 6.5, (shape_tag, ys)
    rest = p.frame_at(6.2, 640)
    assert rest.shape == (360, 640, 3)
    # Channel name (`RAKING LIGHT`) must still have bright dimmed ink at rest near `name_y_pct`.
    ny = int(round(rend.name_y_pct / 100.0 * 360))
    band = rest[max(0, ny - 14):min(360, ny + 14), :, :]
    assert int(band.max()) >= 140, (shape_tag, rend.name_y_pct, int(band.max()))


def test_bright_painting_text_remains_legible_with_halo(tmp_path):
    """On a bright (240/255) canvas even with high wake, the two-tier glyph shadow gives clear dark relief around text."""
    bright = np.full((900, 1400, 3), 240, np.uint8)
    p = make_lab(tmp_path, [shot(1, 0.0, TID, {"variant": "B", "wake": 0.85, "title": "Light Study", "subtitle": "White Ground · Painter, 1800"})],
                 image=bright, end=9.1)
    frame = p.frame_at(6.2, 960)
    # Near the title band (title_y_pct ~ 70%), shadow halo must pull pixels darker than bright background while ink stays bright.
    y_band = slice(int(540 * 0.62), int(540 * 0.85))
    band = frame[y_band, :, :]
    assert int(band.min()) < 165 and int(band.max()) >= 230


def test_variant_b_light_stays_on_painted_surface_and_matte_margins_stay_dark(tmp_path):
    """When a narrow upright painting is shown with black matte margins, Move 1 never illuminates the matte outside the painting."""
    img = _textured_painting(800, 1600)
    z = 0.955 * 1080.0 / 1600.0
    cam = [{"at": {"rel": 0.0}, "cx": 400.0, "cy": 800.0, "zoom": z, "ease": "linear"},
           {"at": {"rel": 1.0}, "cx": 400.0, "cy": 800.0, "zoom": z, "ease": "linear"}]
    p = _make_lab_regions(
        tmp_path,
        [shot(1, 0.0, TID, {"variant": "B", "_pending_region": "R", "text": "", "title": "Margin Check", "subtitle": "Work · Artist, 1500"}, camera=cam)],
        {"R": {"x": 400, "y": 800, "rx": 30, "ry": 30}},
        image=img, name="matte_check", end=9.1,
    )
    # At 960x540, painting occupies x in [345, 615] -> left margin x < 310, right margin x > 650.
    for t in (0.6, 1.5, 2.7):
        fr = p.frame_at(t, 960)
        left_margin = fr[:, :300, :]
        right_margin = fr[:, 660:, :]
        assert int(left_margin.max()) <= 8, (t, int(left_margin.max()))
        assert int(right_margin.max()) <= 8, (t, int(right_margin.max()))
    # With channel name enabled too, pixels outside the name/title rows stay dark in the margins.
    p_txt = _make_lab_regions(
        tmp_path,
        [shot(1, 0.0, TID, {"variant": "B", "_pending_region": "R", "title": "Margin Check", "subtitle": "Work · Artist, 1500"}, camera=cam)],
        {"R": {"x": 400, "y": 800, "rx": 30, "ry": 30}},
        image=img, name="matte_check_txt", end=9.1,
    )
    f_start = p_txt.frame_at(1.0, 960)
    assert int(f_start[200:320, :300, :].max()) <= 8 and int(f_start[200:320, 660:, :].max()) <= 8
    # Inside the painting at Move 1 start (t=1.0), the left edge of the painted surface itself is lit.
    assert int(f_start[100:260, 355:440, :].max()) >= 75


@pytest.mark.parametrize("variant", VARIANTS)
def test_tiny_rest_region_enforces_phone_readable_spot_floor(tmp_path, variant):
    """A tiny region (rx=5, ry=5) still produces a phone-readable lit spot (>= 9% of frame height radius) at rest."""
    img = np.full((1600, 1200, 3), 170, np.uint8)
    cam = [{"at": {"rel": 0.0}, "cx": 600.0, "cy": 800.0, "zoom": 1.6, "ease": "linear"},
           {"at": {"rel": 1.0}, "cx": 600.0, "cy": 800.0, "zoom": 1.6, "ease": "linear"}]
    p = _make_lab_regions(
        tmp_path,
        [shot(1, 0.0, TID, {"variant": variant, "_pending_region": "TINY", "title": "Tiny Spot", "subtitle": "Work · Artist, 1500"}, camera=cam)],
        {"TINY": {"x": 600, "y": 800, "rx": 5, "ry": 5}},
        image=img, name=f"tiny_{variant}", end=9.1,
    )
    fr = p.frame_at(9.1 * 0.68, 960).astype(np.float32)
    lum = fr.mean(axis=2)
    cy_px = 540 // 2
    cx_px = 960 // 2
    col_profile = lum[:, cx_px - 3:cx_px + 4].mean(axis=1)
    # Exclude text bands by checking contiguous half-peak span around the spot centre.
    peak = col_profile[cy_px - 30:cy_px + 30].max()
    bg = col_profile[0:20].mean()
    half_lvl = bg + 0.5 * (peak - bg)
    above = np.where(col_profile[cy_px - 120:cy_px + 120] >= half_lvl)[0]
    radius_px = (above[-1] - above[0]) / 2.0
    assert radius_px / 540.0 >= 0.09, (variant, radius_px, radius_px / 540.0)
