"""Second-look tight bounding boxes for main-painting regions.

For every detail region on the main painting that is not yet tight, the program:
  1. Enlarges its rough box by 15% on each side, clamped to the painted surface (`content_box` if present, else the image frame).
  2. Crops directly from the full-resolution stored picture (never from the 1,568-px or 3,600-px downscaled work copies), scales
     so the long side is 1,024 px (up or down), and draws a labelled 100-px grid in the cut-out's own pixels.
  3. Checks the model's cut-out-pixel response (`tight`, `drop`, or one `wider` re-cut enlarged by 40%), converts cut-out pixels
     to stored-painting pixels in code (never trusting model arithmetic), and refuses boxes outside the cut-out, smaller than 8 px
     of the stored picture on either side, or covering the whole cut-out when the rough box was small.
  4. Renders clean cut-outs (no grid) with bright green tight rectangles tiled 6 to a check sheet, and accepts `tight: true`
     only for regions the model explicitly confirmed (`confirmed: true`) after seeing the check sheets.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from bti.media import contentbox as pcb

from . import images

TIGHTEN_SCHEMA = "bti.picks.tighten/1"
CUTOUT_LONG_SIDE = 1024
MARGIN_INITIAL = 0.15
MARGIN_WIDER = 0.40
GRID_STEP = 100
MIN_STORED_SIDE = 8
SMALL_ROUGH_SIDE_SHARE = 0.45       # rough box is considered small when both sides stay within 45% of the painted surface
FULL_CUTOUT_SHARE = 0.94            # covering >= 94% of both cut-out width and height counts as "as large as the cut-out on both sides"
CHECKS_PER_SHEET = 6
CHECK_COLS = 3
CHECK_TILE_MAX = 700
REGION_ACTIONS = ("tight", "drop", "wider")
STATE_FILE = "look/tighten_state.json"

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    str(Path(__file__).resolve().parents[3] / "style" / "gae" / "fonts" / "EBGaramond-Medium.ttf"),
)
_FONT_CACHE: dict[int, object] = {}


# ---------------------------------------------------------------------------------------------------------------- pure geometry & mapping
def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def surface_box(image_size: tuple[int, int] | list[int], content_box: Any = None) -> tuple[int, int, int, int]:
    """Painted surface bounds `(x0, y0, x1, y1)` in stored pixels: `content_box` (dict or 4-sequence) clamped to image frame when present, else full frame."""
    im_w, im_h = max(1, int(image_size[0])), max(1, int(image_size[1]))
    if isinstance(content_box, (list, tuple)) and len(content_box) == 4 and all(_finite(v) for v in content_box) and float(content_box[2]) > float(content_box[0]) and float(content_box[3]) > float(content_box[1]):
        cx0, cy0, cx1, cy1 = (float(v) for v in content_box)
    else:
        clean = pcb.clean(content_box)
        if clean is None:
            return 0, 0, im_w, im_h
        cx0, cy0, cx1, cy1 = clean
    x0 = max(0, min(im_w - 1, int(math.floor(cx0))))
    y0 = max(0, min(im_h - 1, int(math.floor(cy0))))
    x1 = max(x0 + 1, min(im_w, int(math.ceil(cx1))))
    y1 = max(y0 + 1, min(im_h, int(math.ceil(cy1))))
    return x0, y0, x1, y1


def region_to_rough_px(region: dict, image_size: tuple[int, int] | list[int], surface: tuple[int, int, int, int] | list[int] | None = None) -> list[int]:
    """Stored region `{x, y, rx?, ry?, rough?}` -> rough pixel box `[x0, y0, x1, y1]` clamped inside `surface`."""
    im_w, im_h = max(1, int(image_size[0])), max(1, int(image_size[1]))
    sx0, sy0, sx1, sy1 = tuple(surface) if surface is not None else (0, 0, im_w, im_h)
    if isinstance(region.get("rough"), (list, tuple)) and len(region["rough"]) == 4 and all(_finite(v) for v in region["rough"]):
        rx0, ry0, rx1, ry1 = (int(round(float(v))) for v in region["rough"])
    else:
        cx, cy = float(region["x"]), float(region["y"])
        rx_v = region.get("rx")
        ry_v = region.get("ry")
        if _finite(rx_v) and float(rx_v) > 0:
            rx = float(rx_v)
            ry = float(ry_v) if (_finite(ry_v) and float(ry_v) > 0) else rx
        else:
            rx = ry = float(max(40, int(round(0.08 * min(im_w, im_h)))))
        rx0, ry0 = int(round(cx - rx)), int(round(cy - ry))
        rx1, ry1 = int(round(cx + rx)), int(round(cy + ry))
    bx0 = max(sx0, min(sx1 - 1, rx0))
    by0 = max(sy0, min(sy1 - 1, ry0))
    bx1 = max(bx0 + 1, min(sx1, rx1))
    by1 = max(by0 + 1, min(sy1, ry1))
    return [bx0, by0, bx1, by1]


def cutout_geom(rough_px: tuple[int, int, int, int] | list[int], image_size: tuple[int, int] | list[int], content_box: Any = None, *,
                margin: float = MARGIN_INITIAL, long_side: int = CUTOUT_LONG_SIDE) -> dict:
    """Compute exact cut-out crop rectangle (enlarged by `margin`, clamped inside `surface_box`) and resize scale to `long_side`."""
    im_w, im_h = max(1, int(image_size[0])), max(1, int(image_size[1]))
    sx0, sy0, sx1, sy1 = surface_box((im_w, im_h), content_box)
    rb0 = max(sx0, min(sx1 - 1, int(round(rough_px[0]))))
    rb1 = max(sy0, min(sy1 - 1, int(round(rough_px[1]))))
    rb2 = max(rb0 + 1, min(sx1, int(round(rough_px[2]))))
    rb3 = max(rb1 + 1, min(sy1, int(round(rough_px[3]))))
    rw, rh = rb2 - rb0, rb3 - rb1
    px, py = int(margin * rw), int(margin * rh)
    x0 = max(sx0, rb0 - px)
    y0 = max(sy0, rb1 - py)
    x1 = min(sx1, rb2 + px)
    y1 = min(sy1, rb3 + py)
    cw_src = max(1, x1 - x0)
    ch_src = max(1, y1 - y0)
    scale = float(long_side) / float(max(cw_src, ch_src))
    cw = max(1, int(round(cw_src * scale)))
    ch = max(1, int(round(ch_src * scale)))
    return {
        "rough_px": [rb0, rb1, rb2, rb3],
        "crop_px": [x0, y0, x1, y1],
        "scale": scale,
        "cutout_size": [cw, ch],
        "surface_box": [sx0, sy0, sx1, sy1],
        "image_size": [im_w, im_h],
        "margin": float(margin),
    }


def cutout_to_stored(box_cutout: list[float] | tuple[float, ...], geom: dict) -> list[int]:
    """Map `[x0, y0, x1, y1]` in cut-out pixels -> stored-painting pixels `[sx0, sy0, sx1, sy1]` (clamped inside crop_px)."""
    x0, y0, x1, y1 = geom["crop_px"]
    k = float(geom["scale"])
    bx0, by0, bx1, by1 = (float(v) for v in box_cutout)
    sx0 = max(x0, min(x1 - 1, int(round(x0 + bx0 / k))))
    sy0 = max(y0, min(y1 - 1, int(round(y0 + by0 / k))))
    sx1 = max(sx0 + 1, min(x1, int(round(x0 + bx1 / k))))
    sy1 = max(sy0 + 1, min(y1, int(round(y0 + by1 / k))))
    return [sx0, sy0, sx1, sy1]


def stored_to_cutout(box_stored: list[float] | tuple[float, ...], geom: dict) -> list[float]:
    """Map stored-painting pixels `[sx0, sy0, sx1, sy1]` -> cut-out pixels `[bx0, by0, bx1, by1]`."""
    x0, y0, _, _ = geom["crop_px"]
    k = float(geom["scale"])
    sx0, sy0, sx1, sy1 = (float(v) for v in box_stored)
    return [round((sx0 - x0) * k, 1), round((sy0 - y0) * k, 1), round((sx1 - x0) * k, 1), round((sy1 - y0) * k, 1)]


def stored_box_to_region(stored_box: list[int] | tuple[int, ...]) -> dict:
    """Convert stored pixel bbox `[x0, y0, x1, y1]` to region dict `{"x", "y", "rx", "ry"}`."""
    sx0, sy0, sx1, sy1 = (int(v) for v in stored_box)
    return {
        "x": int(round((sx0 + sx1) / 2.0)),
        "y": int(round((sy0 + sy1) / 2.0)),
        "rx": max(1, int(round((sx1 - sx0) / 2.0))),
        "ry": max(1, int(round((sy1 - sy0) / 2.0))),
    }


# ---------------------------------------------------------------------------------------------------------------- image rendering
def _font(size: int):
    from PIL import ImageFont
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    chosen = None
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            try:
                chosen = ImageFont.truetype(p, size)
                break
            except OSError:
                continue
    if chosen is None:
        try:
            chosen = ImageFont.load_default(size=size)
        except TypeError:
            chosen = ImageFont.load_default()
    _FONT_CACHE[size] = chosen
    return chosen


def _open_rgb(src_path: Path):
    """Open the stored image at full resolution (up to 250M pixels), converted to RGB."""
    from PIL import Image
    prev = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = max(prev or 0, 250_000_000)
    try:
        with Image.open(src_path) as im:
            im.load()
            return im.convert("RGB")
    except Exception as e:
        raise images.ImageError("%s cannot be read as a picture" % Path(src_path).name) from e
    finally:
        Image.MAX_IMAGE_PIXELS = prev


def _crop_cutout_image(full_im, geom: dict):
    from PIL import Image
    x0, y0, x1, y1 = geom["crop_px"]
    cw, ch = geom["cutout_size"]
    sub = full_im.crop((x0, y0, x1, y1))
    return sub.resize((cw, ch), Image.LANCZOS)


def _draw_grid(im) -> None:
    """Draw thin dual-tone 100-px grid lines with dark-backed yellow numbers on top and left edges (readable on dark and light paint)."""
    from PIL import ImageDraw
    cw, ch = im.size
    d = ImageDraw.Draw(im, "RGBA")
    f = _font(17)

    def draw_label(bx: int, by: int, text: str) -> None:
        tb = d.textbbox((0, 0), text, font=f)
        tw, th = max(16, tb[2] - tb[0]), max(14, tb[3] - tb[1])
        bw, bh = tw + 10, th + 6
        px = max(0, min(cw - bw, bx))
        py = max(0, min(ch - bh, by))
        d.rectangle([px, py, px + bw, py + bh], fill=(0, 0, 0, 200))
        d.text((px + 5 - tb[0], py + 3 - tb[1]), text, font=f, fill=(255, 255, 0, 255))

    for gx in range(0, cw, GRID_STEP):
        if gx > 0:
            if gx - 1 >= 0:
                d.line([gx - 1, 0, gx - 1, ch], fill=(0, 0, 0, 80), width=1)
            d.line([gx, 0, gx, ch], fill=(255, 255, 0, 125), width=1)
        draw_label(gx + 2, 2, str(gx))

    for gy in range(GRID_STEP, ch, GRID_STEP):
        if gy - 1 >= 0:
            d.line([0, gy - 1, cw, gy - 1], fill=(0, 0, 0, 80), width=1)
        d.line([0, gy, cw, gy], fill=(255, 255, 0, 125), width=1)
        draw_label(2, gy + 2, str(gy))


def render_cutout(src_path: Path, geom: dict, dest: Path, *, with_grid: bool = True, full_im=None) -> tuple[int, int]:
    """Crop `geom["crop_px"]` from full-res `src_path`, scale to `geom["cutout_size"]`, optionally draw 100-px grid, save JPEG."""
    img = full_im if full_im is not None else _open_rgb(Path(src_path))
    cut = _crop_cutout_image(img, geom)
    if with_grid:
        _draw_grid(cut)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cut.convert("RGB").save(dest, format="JPEG", quality=92)
    return cut.size


def _fit_text(draw, text: str, fnt, max_w: int) -> str:
    if draw.textlength(text, font=fnt) <= max_w:
        return text
    s = str(text)
    while len(s) > 1 and draw.textlength(s + "…", font=fnt) > max_w:
        s = s[:-1]
    return s.rstrip() + "…"


def render_check_sheets(src_path: Path, items: list[dict], out_dir: Path, *, prefix: str = "check", full_im=None) -> list[Path]:
    """Draw every tight box on a clean cut-out (no grid) and tile them up to 6 per sheet into `out_dir`.

    `items`: [{"name", "geom", "box_cutout", "stored_box", "thing"?, "what"?}]. Returns written sheet Paths in order."""
    from PIL import Image, ImageDraw
    if not items:
        return []
    img = full_im if full_im is not None else _open_rgb(Path(src_path))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    f_head = _font(22)
    f_sub = _font(15)
    pad = 8
    header_h = 56
    tile_w = CHECK_TILE_MAX
    tile_h = CHECK_TILE_MAX
    paths: list[Path] = []
    for s_idx in range(0, len(items), CHECKS_PER_SHEET):
        chunk = items[s_idx:s_idx + CHECKS_PER_SHEET]
        cols = min(CHECK_COLS, len(chunk))
        rows = -(-len(chunk) // cols)
        sheet_w = cols * (tile_w + pad) + pad
        sheet_h = rows * (tile_h + header_h + pad) + pad
        sheet = Image.new("RGB", (sheet_w, sheet_h), (20, 20, 20))
        sg = ImageDraw.Draw(sheet)
        for k, it in enumerate(chunk):
            r, c = divmod(k, cols)
            ox = pad + c * (tile_w + pad)
            oy = pad + r * (tile_h + header_h + pad)
            cut = _crop_cutout_image(img, it["geom"])
            dr = ImageDraw.Draw(cut)
            b = [int(round(v)) for v in it["box_cutout"]]
            dr.rectangle(b, outline=(0, 0, 0), width=7)
            dr.rectangle(b, outline=(60, 255, 90), width=3)
            cut.thumbnail((tile_w, tile_h), Image.LANCZOS)
            sb = it["stored_box"]
            sw, sh = sb[2] - sb[0], sb[3] - sb[1]
            sg.rectangle([ox, oy, ox + tile_w - 1, oy + header_h - 1], fill=(0, 0, 0))
            sg.text((ox + 8, oy + 4), _fit_text(sg, "%s   %dx%d px" % (it["name"], sw, sh), f_head, tile_w - 16), font=f_head, fill=(255, 255, 255))
            desc = (it.get("thing") or it.get("what") or "").strip()
            sub = ("%s  [%d,%d,%d,%d]" % (desc, b[0], b[1], b[2], b[3])) if desc else ("box [%d,%d,%d,%d]" % (b[0], b[1], b[2], b[3]))
            sg.text((ox + 8, oy + 32), _fit_text(sg, sub, f_sub, tile_w - 16), font=f_sub, fill=(180, 235, 190))
            px = ox + (tile_w - cut.width) // 2
            py = oy + header_h + (tile_h - cut.height) // 2
            sheet.paste(cut, (px, py))
        dest = out_dir / ("%s_%d.jpg" % (prefix, len(paths) + 1))
        sheet.save(dest, format="JPEG", quality=90)
        paths.append(dest)
    return paths


# ---------------------------------------------------------------------------------------------------------------- box checks & state machine
def check_cutout_box(raw_box: Any, geom: dict, where: str) -> tuple[list[int] | None, list[int] | None, str | None]:
    """Validate `[x0, y0, x1, y1]` in cut-out pixels and map to stored painting pixels.
    Refuses outside cut-out, inverted/degenerate boxes, `< 8 px` of stored picture on either side, or full-cutout boxes when rough box was small."""
    cw, ch = int(geom["cutout_size"][0]), int(geom["cutout_size"][1])
    if not (isinstance(raw_box, (list, tuple)) and len(raw_box) == 4 and all(_finite(v) for v in raw_box)):
        return None, None, "%s: `box` must be four numbers [x0, y0, x1, y1] in the cut-out's own pixels (0..%d by 0..%d) [box_shape]" % (where, cw, ch)
    bx0, by0, bx1, by1 = (float(v) for v in raw_box)
    if bx0 < 0 or by0 < 0 or bx1 > cw or by1 > ch:
        return None, None, ("%s: box %s lies outside the cut-out (%d x %d px); keep x between 0 and %d and y between 0 and %d [box_outside_cutout]"
                           % (where, [round(v) for v in (bx0, by0, bx1, by1)], cw, ch, cw, ch))
    if bx1 <= bx0 or by1 <= by0:
        return None, None, "%s: box is empty or upside down (need x0 < x1 and y0 < y1) [box_inverted]" % where
    clean = [max(0, min(cw - 1, int(round(bx0)))), max(0, min(ch - 1, int(round(by0)))),
             min(cw, max(1, int(round(bx1)))), min(ch, max(1, int(round(by1))))]
    if clean[2] <= clean[0] or clean[3] <= clean[1]:
        return None, None, "%s: box rounds to zero width or height in cut-out pixels [box_too_small]" % where
    stored = cutout_to_stored(clean, geom)
    sw, sh = stored[2] - stored[0], stored[3] - stored[1]
    if sw < MIN_STORED_SIDE or sh < MIN_STORED_SIDE:
        return None, None, ("%s: mapped box (%dx%d stored px) is smaller than %d px of the stored picture on a side; tighten around a visible object [box_too_small]"
                           % (where, sw, sh, MIN_STORED_SIDE))
    rb0, rb1, rb2, rb3 = geom["rough_px"]
    sx0, sy0, sx1, sy1 = geom["surface_box"]
    rough_small = ((rb2 - rb0) <= SMALL_ROUGH_SIDE_SHARE * max(1, sx1 - sx0)
                   and (rb3 - rb1) <= SMALL_ROUGH_SIDE_SHARE * max(1, sy1 - sy0))
    if rough_small and (clean[2] - clean[0]) >= FULL_CUTOUT_SHARE * cw and (clean[3] - clean[1]) >= FULL_CUTOUT_SHARE * ch:
        return None, None, ("%s: box [%d,%d,%d,%d] covers almost the whole cut-out (%dx%d) for a small detail — measure the tight edges of the thing itself inside the cut-out, or answer `wider` / `drop` [box_too_loose]"
                           % (where, clean[0], clean[1], clean[2], clean[3], cw, ch))
    return clean, stored, None


def _load_state(ws_root: Path | None, state: dict | None) -> dict:
    if ws_root is not None:
        p = Path(ws_root) / STATE_FILE
        if p.is_file() and not p.is_symlink():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    d.setdefault("wider", {})
                    d.setdefault("checked", {})
                    d.setdefault("sheets", [])
                    return d
            except (OSError, ValueError):
                pass
    if isinstance(state, dict):
        state.setdefault("wider", {})
        state.setdefault("checked", {})
        state.setdefault("sheets", [])
        return state
    return {"wider": {}, "checked": {}, "sheets": []}


def _save_state(ws_root: Path | None, state: dict) -> None:
    if ws_root is None:
        return
    p = Path(ws_root) / STATE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _reason_check(raw: Any, where: str, *, required: bool) -> tuple[str | None, str | None]:
    from . import shapes
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            return None, "%s: `reason` must say in one short Vietnamese sentence why the box is here [reason_missing]" % where
        return "", None
    r = shapes._text(raw, 3, shapes.REASON_MAX * 2)
    if r is None:
        return None, "%s: `reason` must be a short Vietnamese sentence (3 to %d characters)" % (where, shapes.REASON_MAX)
    if not shapes._vietnamese(r):
        return None, "%s: `reason` must be written in Vietnamese, with its accents (the owner reads it); it says %r" % (where, r[:60])
    return shapes._short(r, shapes.REASON_MAX), None


def check_regions_response(raw_regions: Any, cutouts: dict[str, dict], *, ws_root: Path | None = None, state: dict | None = None,
                           allow_unconfirmed: bool = False, allow_thing: bool = False) -> tuple[dict[str, dict], list[str], list[str]]:
    """Validate second-look region entries (`tight` | `drop` | `wider`), trigger 40% wider re-cuts and 6-per-sheet check images as needed,
    and enforce check-sheet confirmation (`confirmed: true`) unless `allow_unconfirmed=True`."""
    from . import shapes
    errors: list[str] = []
    notes: list[str] = []
    out: dict[str, dict] = {}
    st = _load_state(ws_root, state)

    if not isinstance(raw_regions, list):
        return out, ["`regions` must be a list of {name, action, box?, thing?, confirmed?, reason}"], notes

    parsed: dict[str, dict] = {}
    need_wider: list[str] = []
    full_im = None

    def open_full():
        nonlocal full_im
        if full_im is not None:
            return full_im
        if ws_root is None:
            return None
        sample = next(iter(cutouts.values()), None)
        rel = sample.get("full_image") if sample else None
        if not rel:
            return None
        p = Path(ws_root) / rel
        if not p.is_file():
            return None
        full_im = _open_rgb(p)
        return full_im

    for k, r in enumerate(raw_regions):
        where = "regions[%d]" % k
        if not isinstance(r, dict) or not isinstance(r.get("name"), str):
            errors.append("%s must be an object with `name` and `action` (tight, drop or wider)" % where)
            continue
        name = r["name"]
        where = "regions[%d] (%s)" % (k, name)
        if name not in cutouts:
            errors.append("%s: there is no such region among those to tighten (%s)" % (where, ", ".join(cutouts) or "none"))
            continue
        if name in parsed:
            errors.append("%s: written twice" % where)
            continue
        action = r.get("action")
        if action not in REGION_ACTIONS:
            errors.append("%s: action must be one of %s" % (where, ", ".join(REGION_ACTIONS)))
            continue
        c = cutouts[name]
        reason, r_err = _reason_check(r.get("reason"), where, required=(action in ("drop", "wider")))
        if r_err:
            errors.append(r_err)
            continue
        thing_val = str(c.get("thing") or "")
        if (allow_thing or c.get("existing")) and r.get("thing") is not None and str(r.get("thing")).strip():
            ct, t_err = shapes.clean_thing(r.get("thing"), where, line_texts=c.get("line_texts"))
            if t_err:
                errors.append(t_err)
                continue
            thing_val = ct or thing_val

        if action == "drop":
            parsed[name] = {
                "action": "drop", "box": None, "stored_box": None, "rough_px": list(c["rough_px"]),
                "confirmed": False, "wider": name in st["wider"], "existing": bool(c.get("existing")),
                "thing": thing_val, "what": str(c.get("what") or ""), "reason": reason or "",
            }
            continue

        if action == "wider":
            if name in st["wider"]:
                wgeom = st["wider"][name]
                errors.append("%s: `wider` can only be asked once per region; look at look/d_%s_wider.jpg (%dx%d px) and answer `tight` or `drop` [wider_already_used]"
                              % (where, name, wgeom["cutout_size"][0], wgeom["cutout_size"][1]))
                continue
            wgeom = cutout_geom(c["rough_px"], c["image_size"], c["surface_box"], margin=MARGIN_WIDER)
            wdest = "look/d_%s_wider.jpg" % name
            if ws_root is not None:
                try:
                    im = open_full()
                    if im is not None:
                        render_cutout(Path(ws_root) / c["full_image"], wgeom, Path(ws_root) / wdest, with_grid=True, full_im=im)
                except images.ImageError:
                    pass
            st["wider"][name] = wgeom
            _save_state(ws_root, st)
            need_wider.append("%s -> %s (%dx%d px)" % (name, wdest, wgeom["cutout_size"][0], wgeom["cutout_size"][1]))
            parsed[name] = {
                "action": "wider", "box": None, "stored_box": None, "rough_px": list(c["rough_px"]),
                "confirmed": False, "wider": True, "existing": bool(c.get("existing")),
                "thing": thing_val, "what": str(c.get("what") or ""), "reason": reason or "",
            }
            continue

        # action == "tight"
        is_wider = name in st["wider"]
        geom = st["wider"][name] if is_wider else c
        clean_box, stored, b_err = check_cutout_box(r.get("box"), geom, where)
        if b_err:
            errors.append(b_err)
            continue
        if "confirmed" in r and not isinstance(r["confirmed"], bool):
            errors.append("%s: `confirmed` must be true or false" % where)
            continue
        parsed[name] = {
            "action": "tight",
            "box": clean_box,
            "stored_box": stored,
            "rough_px": list(c["rough_px"]),
            "confirmed": bool(r.get("confirmed") is True),
            "wider": is_wider,
            "existing": bool(c.get("existing")),
            "thing": thing_val,
            "what": str(c.get("what") or ""),
            "reason": reason or "",
            "_geom": geom,
            "_raw_confirmed": r.get("confirmed") is True,
        }

    left = [n for n in cutouts if n not in parsed and not any("(%s)" % n in e for e in errors)]
    if left and not errors:
        errors.append("these regions have no entry in `regions`: %s (say tight, drop or wider for each)" % ", ".join(left[:12]))
    elif left and not need_wider:
        errors.append("these regions have no entry in `regions`: %s" % ", ".join(left[:12]))

    if need_wider:
        errors.append("wrote wider (+40%%) gridded cut-out(s): %s. Open them and give a `tight` box (or `drop`) in the wider cut-out's pixels [wider_ready]"
                      % "; ".join(need_wider))

    if errors:
        return {}, errors, notes

    # No shape, geometry, missing or wider errors left: manage check sheets & one-time correction / confirmation.
    tight_names = [n for n in cutouts if parsed[n]["action"] == "tight"]
    if tight_names:
        unrendered = [n for n in tight_names if n not in st["checked"] or bool(st["checked"][n].get("wider")) != bool(parsed[n]["wider"])]
        if unrendered:
            # First time seeing check sheets (for current tight regions): draw green tight boxes on clean cut-outs, 6 per sheet.
            sheet_items = [{
                "name": n,
                "geom": parsed[n]["_geom"],
                "box_cutout": parsed[n]["box"],
                "stored_box": parsed[n]["stored_box"],
                "thing": parsed[n]["thing"],
                "what": parsed[n]["what"],
            } for n in tight_names]
            sheet_rels: list[str] = []
            if ws_root is not None:
                im = open_full()
                if im is not None:
                    written = render_check_sheets(Path(ws_root) / cutouts[tight_names[0]]["full_image"], sheet_items, Path(ws_root) / "look", prefix="check", full_im=im)
                    sheet_rels = ["look/" + p.name for p in written]
            if not sheet_rels:
                n_sheets = max(1, -(-len(sheet_items) // CHECKS_PER_SHEET))
                sheet_rels = ["look/check_%d.jpg" % i for i in range(1, n_sheets + 1)]
            for idx, n in enumerate(tight_names):
                st["checked"][n] = {
                    "box": list(parsed[n]["box"]),
                    "wider": bool(parsed[n]["wider"]),
                    "corrections": 0,
                    "sheet": sheet_rels[min(len(sheet_rels) - 1, idx // CHECKS_PER_SHEET)],
                }
            st["sheets"] = sheet_rels
            _save_state(ws_root, st)
            if allow_unconfirmed:
                for n in tight_names:
                    parsed[n]["confirmed"] = False
            else:
                errors.append("check sheets written (%s): open every check sheet, inspect each green tight box, then set `\"confirmed\": true` (or give a corrected box once with `\"confirmed\": true`, or `drop`) and run check again [check_sheet_ready]"
                              % ", ".join(sheet_rels))
                return {}, errors, notes
        else:
            # Check sheets already exist: enforce one-time correction & explicit `confirmed: true`.
            need_rerender = False
            for n in tight_names:
                rec = parsed[n]
                prev = st["checked"][n]
                same_box = (rec["box"] == prev["box"])
                if not same_box:
                    if int(prev.get("corrections") or 0) >= 1:
                        errors.append("regions (%s): a tight box can only be corrected once after seeing the check sheet (keep %s or `drop`) [correction_limit]"
                                      % (n, prev["box"]))
                        continue
                    prev["box"] = list(rec["box"])
                    prev["corrections"] = 1
                    need_rerender = True
                if not rec["_raw_confirmed"]:
                    if allow_unconfirmed:
                        rec["confirmed"] = False
                    else:
                        sheet_name = prev.get("sheet") or (st["sheets"][0] if st.get("sheets") else "look/check_1.jpg")
                        errors.append("regions (%s): open %s to verify the green tight box, then add `\"confirmed\": true` (or correct the box once, or `drop`) [unconfirmed]"
                                      % (n, sheet_name))
                else:
                    rec["confirmed"] = True
            if need_rerender and ws_root is not None:
                im = open_full()
                if im is not None:
                    sheet_items = [{
                        "name": n,
                        "geom": parsed[n]["_geom"],
                        "box_cutout": st["checked"][n]["box"],
                        "stored_box": cutout_to_stored(st["checked"][n]["box"], parsed[n]["_geom"]),
                        "thing": parsed[n]["thing"],
                        "what": parsed[n]["what"],
                    } for n in tight_names]
                    render_check_sheets(Path(ws_root) / cutouts[tight_names[0]]["full_image"], sheet_items, Path(ws_root) / "look", prefix="check", full_im=im)
            _save_state(ws_root, st)
            if errors:
                return {}, errors, notes

    for n, rec in parsed.items():
        rec.pop("_geom", None)
        rec.pop("_raw_confirmed", None)
        out[n] = rec
    return out, errors, notes


def check_tighten(obj: Any, tighten_ctx: dict, *, ws_root: Path | None = None, state: dict | None = None, allow_unconfirmed: bool = False):
    """Validate `out/tighten.json` for standalone `picks.tighten`."""
    from . import shapes
    rep = shapes.Report()
    err = rep.errors
    if not isinstance(obj, dict):
        err.append("out/tighten.json must be one JSON object with `regions`")
        return rep
    if obj.get("schema") not in (None, TIGHTEN_SCHEMA):
        err.append("schema must be %r (or left out)" % TIGHTEN_SCHEMA)
    cutouts = tighten_ctx.get("cutouts") or {}
    regs, r_errs, r_notes = check_regions_response(obj.get("regions", []), cutouts, ws_root=ws_root, state=state,
                                                   allow_unconfirmed=allow_unconfirmed, allow_thing=True)
    err.extend(r_errs)
    rep.notes.extend(r_notes)
    if not err:
        rep.value = {"schema": TIGHTEN_SCHEMA, "regions": regs}
    return rep
