"""The painted area of a picture: `content_box`, found by the program, kept in the asset, used by everything that frames the main painting.

A museum photograph of a panel is often taken on a black ground (the Met's goldsmith of Petrus Christus is 3469 x 4000 pixels, of which a band of about 100
pixels on every side is the black cloth behind the panel). The camera of the video must travel over the PAINTING, never over that cloth, so every picture
can carry its own box:

    "content_box": {"x0": 101, "y0": 99, "x1": 3370, "y1": 3902, "how": "found"}      pixels of the stored picture (the space of `width`, `height` and the regions)

`how` says where the box comes from: `found` (a uniform band along one or more edges was taken away), `whole` (no such band: the box is the whole picture),
`unsure` (the program was not sure and took the whole picture, `note` says why) or `set` (a person or an agent set it, `bti.ops` `set_content_box`).
A picture that carries no box is the whole picture, unless a consumer asks for the finding of the file (`box_of`, the same function); the program writes a box only
when it found something to take away (`found`) or was not sure (`unsure`), so that a document of a picture with no ground band stays as it was.

The finding (`find`), deterministic and careful, on a copy of the picture scaled to at most SCAN pixels on its long side:
  * a LINE (a row or a column, judged over what is left of the picture) is GROUND when it is uniform (the standard deviation of its grey values is at most
    SD_GROUND, SD_MID for a middle grey) and either dark (mean grey at most DARK_MEAN) or light (at least LIGHT_MEAN); a middle grey is ground only when at
    least three sides have it. Lines are taken away from each edge inward while they stay ground, in rounds, until nothing changes;
  * the painting begins at the first line that is not ground, and the box starts one scanned line further in (the line where the cloth meets the panel
    is half cloth), so a few pixels of the panel's own edge are left out and no pixel of the cloth is left in;
  * a band thinner than MIN_BAND of its side is not a band (a scanner's dark hairline) and is ignored;
  * the program says `unsure` and takes the whole picture when: a band is on one side only (it could be a dark part of the painting), a band is thicker
    than MAX_BAND of its side, the bands of different sides are not the same colour, or the box is under MIN_AREA of the picture. No band at all: `whole`.

The second half of the module is the geometry of a camera key against the box (`outside_share`, `fit_frame`, `whole_frame`): the check `frame_off_painting` of the engine and
the compiler's correction use the same two functions, so that what the compiler makes is what the check accepts.
"""
from __future__ import annotations

import math
from pathlib import Path

FIELDS = ("x0", "y0", "x1", "y1")
HOW = ("found", "whole", "unsure", "set")

SCAN = 640                  # the long side of the copy the finding looks at
MIN_BAND = 0.01             # a band under this share of its side is ignored
MAX_BAND = 0.30             # a band over this share of its side is not believed
MIN_AREA = 0.60             # a box under this share of the picture is not believed
DARK_MEAN = 32              # grey value (0..255) at most which a uniform line is dark ground
LIGHT_MEAN = 225            # ... at least which it is light ground
SD_GROUND = 3.0             # a dark or light line is uniform when its standard deviation is at most this
SD_MID = 2.0                # a middle grey line must be this uniform (and on three sides)
STEP_TOL = 8.0              # the mean grey of a ground line may move this much from the line before it ...
DRIFT_TOL = 30.0            # ... and this much from the outermost line of the band
COLOUR_TOL = 24.0           # a channel of a ground line may differ this much from the outermost line of the band
SAME_GROUND = 40.0          # the bands of two sides are the same ground when their colours differ by less than this in every channel
MIN_PX = 64                 # a box smaller than this on a side is not a box
MIN_SIDE_SHARE = 0.05       # `set_content_box`: a box is at least this share of the picture on each side
LUMA_MAX_PIXELS = 36_000_000   # a picture that is not a JPEG and has more pixels than this is not decoded

NOTES = {
    "one_side": "a dark or light band was found along one edge only: it could be a dark part of the painting, so the whole picture is used",
    "too_thick": "a band thicker than %d%% of its side was found: it is not believed, so the whole picture is used" % round(MAX_BAND * 100),
    "colours_differ": "the bands along the edges are not the same colour, so the whole picture is used",
    "too_small": "the painted area would be under %d%% of the picture, so the whole picture is used" % round(MIN_AREA * 100),
    "mid_tone": "a band of middle grey was found on fewer than three sides, so it is not taken for the ground",
}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ---------------------------------------------------------------------------------------------------------------- the record
def whole(w, h) -> tuple[int, int, int, int]:
    return (0, 0, int(round(w)), int(round(h)))


def record(box, how: str, note: str | None = None) -> dict:
    """The `content_box` object of an asset: integer pixels, then `how` (and `note` when there is one)."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    out = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "how": how if how in HOW else "set"}
    if note:
        out["note"] = str(note)
    return out


def clean(raw, w=None, h=None):
    """The box of a stored `content_box` object as `(x0, y0, x1, y1)` floats, or None when it is missing or cannot be used: four finite numbers, x0 < x1,
    y0 < y1, a hair outside the picture is clamped to it (when its size `w` x `h` is known; a box that lies outside it is not a box)."""
    if not isinstance(raw, dict) or not all(_num(raw.get(k)) for k in FIELDS):
        return None
    x0, y0, x1, y1 = (float(raw[k]) for k in FIELDS)
    if _num(w) and _num(h) and w > 0 and h > 0:
        tol = max(2.0, 0.005 * max(w, h))
        if x0 < -tol or y0 < -tol or x1 > w + tol or y1 > h + tol:
            return None
        x0, y0, x1, y1 = max(0.0, x0), max(0.0, y0), min(float(w), x1), min(float(h), y1)
    return (x0, y0, x1, y1) if x1 - x0 >= 1 and y1 - y0 >= 1 else None


def box_problem(box, w, h) -> str | None:
    """Why `(x0, y0, x1, y1)` cannot be the painted area of a w x h picture (for `set_content_box`), or None."""
    if not _num(w) or not _num(h) or w <= 0 or h <= 0:
        return "the size of the picture is not known"
    x0, y0, x1, y1 = box
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return "the box must lie inside the picture (0..%d across, 0..%d down)" % (w, h)
    if not (x0 < x1 and y0 < y1):
        return "x0 must be less than x1 and y0 less than y1"
    if x1 - x0 < max(MIN_PX, MIN_SIDE_SHARE * w) or y1 - y0 < max(MIN_PX, MIN_SIDE_SHARE * h):
        return "the box is too small: at least %d%% of the picture across and down (and %d pixels)" % (round(MIN_SIDE_SHARE * 100), MIN_PX)
    return None


def scale_asset_box(asset: dict | None, kx: float, ky: float) -> None:
    """Scale the `content_box` of an asset IN PLACE when its picture changes size (the rule of the regions, `bti.media.assets.scale_regions`)."""
    cb = (asset or {}).get("content_box")
    if not isinstance(cb, dict):
        return
    for names, k in ((("x0", "x1"), kx), (("y0", "y1"), ky)):
        for n in names:
            if _num(cb.get(n)):
                cb[n] = int(round(cb[n] * k))


# ---------------------------------------------------------------------------------------------------------------- reading the picture
def _thumb(path: Path):
    """An RGB copy of the picture at `path`, at most SCAN pixels on its long side, as the engine draws it (EXIF turn applied); None when it cannot be read."""
    try:
        from PIL import Image, ImageOps
    except Exception:       # noqa: BLE001 - no imaging library: nothing can be found
        return None
    try:
        with Image.open(path) as im:
            if im.format != "JPEG" and im.size[0] * im.size[1] > LUMA_MAX_PIXELS:
                return None
            try:
                im.draft("RGB", (SCAN * 2, SCAN * 2))
            except Exception:       # noqa: BLE001 - a format with no draft mode
                pass
            im = ImageOps.exif_transpose(im).convert("RGB")
            rw, rh = im.size                           # a JPEG may have been decoded at 1/2, 1/4 or 1/8 (draft): only the ratios matter below
            side = max(rw, rh)
            k = SCAN / side if side > SCAN else 1.0
            small = im.resize((max(1, int(round(rw * k))), max(1, int(round(rh * k)))), Image.BOX) if k < 1.0 else im.copy()
            return small
    except Exception:       # noqa: BLE001 - damaged, too large, not an image: no finding
        return None


class _Scan:
    """The grey and colour bytes of the copy, and the statistics of a row or a column over a part of it."""

    def __init__(self, im):
        self.w, self.h = im.size
        self.g = im.convert("L").tobytes()
        r, g, b = im.split()
        self.c = (r.tobytes(), g.tobytes(), b.tobytes())

    def line(self, plane, side: str, k: int, a: int, b: int) -> bytes:
        """Row k (top/bottom) from column a to b, or column k (left/right) from row a to b."""
        w = self.w
        if side in ("top", "bottom"):
            return plane[k * w + a:k * w + b]
        return plane[a * w + k:(b - 1) * w + k + 1:w]

    def stat(self, side: str, k: int, a: int, b: int):
        v = self.line(self.g, side, k, a, b)
        n = len(v)
        if n == 0:
            return None
        s = sum(v)
        m = s / n
        sd = math.sqrt(max(0.0, sum(x * x for x in v) / n - m * m))
        cols = tuple(sum(self.line(p, side, k, a, b)) / n for p in self.c)
        return m, sd, cols


def _peel(sc: _Scan, side: str, ext: list, ref: tuple | None = None) -> tuple[int, tuple | None]:
    """How many lines from `side` inward are ground, judged over the part `ext` = [xa, ya, xb, yb] of the copy that is left. `ext` is not changed.
    `ref` is the `(grey, colours)` of the outermost line of the band this side already has (an earlier round): the lines that go on must be that colour, so that a
    flat part of the painting that is next to the band is not mistaken for more of it. -> (count, (grey, colours) of the outermost line or None)."""
    xa, ya, xb, yb = ext
    n = 0
    first = ref
    prev = ref[0] if ref else None
    if side in ("top", "bottom"):
        lines = range(ya, yb) if side == "top" else range(yb - 1, ya - 1, -1)
        span = (xa, xb)
    else:
        lines = range(xa, xb) if side == "left" else range(xb - 1, xa - 1, -1)
        span = (ya, yb)
    for k in lines:
        st = sc.stat(side, k, *span)
        if st is None:
            break
        m, sd, cols = st
        dark, light = m <= DARK_MEAN, m >= LIGHT_MEAN
        if sd > (SD_GROUND if (dark or light) else SD_MID):
            break
        if first is None:
            first = (m, cols)
        else:
            if abs(m - first[0]) > DRIFT_TOL or abs(m - prev) > STEP_TOL or any(abs(c - f) > COLOUR_TOL for c, f in zip(cols, first[1])):
                break
        prev = m
        n += 1
    return n, first


def _decide(sc: _Scan):
    """-> (extent of the painting in the copy [xa, ya, xb, yb], how, note). Pure arithmetic on what `_peel` says."""
    w, h = sc.w, sc.h
    ext = [0, 0, w, h]
    counts = {s: 0 for s in ("top", "bottom", "left", "right")}
    first: dict = {}
    for _ in range(4):
        moved = False
        for side in ("top", "bottom", "left", "right"):
            n, f = _peel(sc, side, ext, first.get(side))
            if n:
                counts[side] += n
                first.setdefault(side, f)
                moved = True
                if side == "top":
                    ext[1] += n
                elif side == "bottom":
                    ext[3] -= n
                elif side == "left":
                    ext[0] += n
                else:
                    ext[2] -= n
            if ext[2] - ext[0] < 4 or ext[3] - ext[1] < 4:
                return [0, 0, w, h], "whole", None          # the picture is all one colour: there is nothing to find
        if not moved:
            break
    dim = {"top": h, "bottom": h, "left": w, "right": w}
    sides = [s for s in counts if counts[s] >= max(2, MIN_BAND * dim[s])]
    if not sides:
        return [0, 0, w, h], "whole", None
    if any(counts[s] > MAX_BAND * dim[s] for s in sides):
        return [0, 0, w, h], "unsure", "too_thick"
    cols = [first[s][1] for s in sides]
    if any(abs(a - b) > SAME_GROUND for c1 in cols for c2 in cols for a, b in zip(c1, c2)):
        return [0, 0, w, h], "unsure", "colours_differ"
    mid = [s for s in sides if DARK_MEAN < first[s][0] < LIGHT_MEAN]
    if mid and len(sides) < 3:
        return [0, 0, w, h], "unsure", "mid_tone"
    if len(sides) == 1:
        return [0, 0, w, h], "unsure", "one_side"
    out = [0, 0, w, h]
    # the line where the cloth meets the panel is half cloth: the painting starts one line further in; a side with no real band keeps the edge
    out[1] = counts["top"] + 1 if "top" in sides else 0
    out[3] = h - counts["bottom"] - 1 if "bottom" in sides else h
    out[0] = counts["left"] + 1 if "left" in sides else 0
    out[2] = w - counts["right"] - 1 if "right" in sides else w
    if (out[2] - out[0]) * (out[3] - out[1]) < MIN_AREA * w * h:
        return [0, 0, w, h], "unsure", "too_small"
    return out, "found", None


# ---------------------------------------------------------------------------------------------------------------- the finding
_CACHE: dict = {}                # (path, mtime_ns, bytes) -> the record or None; the finding of a file is the same until the file changes
_CACHE_MAX = 256


def find(path, width=None, height=None) -> dict | None:
    """The `content_box` record of the picture file at `path` (pixels of the picture as the engine draws it), or None when the file cannot be read as a picture.
    `width` and `height`, when given (the asset's own record), are the size the box is made for: a file of another size gives None (the record is stale).
    Deterministic; remembered per (path, mtime, size)."""
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p), st.st_mtime_ns, st.st_size)
    if key in _CACHE:
        rec = _CACHE[key]
    else:
        rec = None
        im = _thumb(p)
        if im is not None:
            from .imageinfo import drawn_size
            fw, fh = drawn_size(p)
            if fw and fh:
                sc = _Scan(im)
                ext, how, note = _decide(sc)
                kx, ky = fw / sc.w, fh / sc.h
                if how == "found":
                    box = (ext[0] * kx, ext[1] * ky, ext[2] * kx, ext[3] * ky)
                    box = (box[0], box[1], min(float(fw), box[2]), min(float(fh), box[3]))
                else:
                    box = whole(fw, fh)
                rec = record(box, how, note)
                rec["_size"] = (fw, fh)
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = rec
    if rec is None:
        return None
    if _num(width) and _num(height) and rec["_size"] != (int(width), int(height)):
        return None
    return {k: v for k, v in rec.items() if k != "_size"}


def _file_of(project_dir, asset) -> Path | None:
    from .assets import _inside
    if project_dir is None or not isinstance(asset, dict) or asset.get("kind") not in (None, "image"):
        return None
    return _inside(Path(project_dir), asset.get("file"))


def box_of(asset, project_dir=None):
    """The painted area of an asset as `(x0, y0, x1, y1)` floats in pixels of its picture: its stored `content_box` when it has a usable one, else (when
    `project_dir` is given and the file reads) the program's finding, else None. The whole picture comes back as the whole-picture box, never as None."""
    if not isinstance(asset, dict) or asset.get("kind") not in (None, "image"):
        return None
    w, h = asset.get("width"), asset.get("height")
    got = clean(asset.get("content_box"), w, h)
    if got is not None:
        return got
    f = _file_of(project_dir, asset)
    if f is None:
        return None
    rec = find(f, w if _num(w) and w > 0 else None, h if _num(h) and h > 0 else None)
    return clean(rec, w, h) if rec else None


def ensure(asset, project_dir) -> bool:
    """Give an image asset that has no usable `content_box` the program's finding of its file, IN PLACE. -> True when the asset changed. A video, a missing or
    unreadable file, or a picture that already has a usable box is left alone, and so is a picture in which the program found nothing to take away (`whole`):
    no box is the whole picture, so a document of a picture with no ground band stays exactly as it was."""
    if not isinstance(asset, dict) or asset.get("kind") not in (None, "image"):
        return False
    w, h = asset.get("width"), asset.get("height")
    if clean(asset.get("content_box"), w, h) is not None:
        return False
    f = _file_of(project_dir, asset)
    if f is None:
        return False
    rec = find(f, w if _num(w) and w > 0 else None, h if _num(h) and h > 0 else None)
    if rec is None or rec["how"] == "whole":
        return False
    asset["content_box"] = rec
    return True


# ---------------------------------------------------------------------------------------------------------------- regions inside the box
def clamp_region(region: dict, box) -> dict | None:
    """The region `{x, y, rx, ry}` (a centre and two radii, pixels) cut to the box: its bounding rectangle is intersected with `box`, and the centre and the
    radii are those of the part that is left. None when under half of the region's own area lies inside the box (it was drawn on the cloth), or when the
    region is a point outside the box. A region with no radius (a point) is kept when it is inside. Other fields (`label`) are kept."""
    if not (isinstance(region, dict) and _num(region.get("x")) and _num(region.get("y"))):
        return None
    x0, y0, x1, y1 = box
    x, y = float(region["x"]), float(region["y"])
    rx = float(region["rx"]) if _num(region.get("rx")) and region["rx"] > 0 else 0.0
    ry = float(region["ry"]) if _num(region.get("ry")) and region["ry"] > 0 else rx
    if rx <= 0:
        return dict(region) if x0 <= x <= x1 and y0 <= y <= y1 else None
    ax0, ax1, ay0, ay1 = max(x - rx, x0), min(x + rx, x1), max(y - ry, y0), min(y + ry, y1)
    if ax1 <= ax0 or ay1 <= ay0 or (ax1 - ax0) * (ay1 - ay0) < 0.5 * (2 * rx) * (2 * ry):
        return None
    out = dict(region)
    if all(isinstance(region.get(k), int) and not isinstance(region.get(k), bool) for k in ("x", "y", "rx")):
        i0, i1, j0, j1 = math.ceil(ax0 - 1e-9), math.floor(ax1 + 1e-9), math.ceil(ay0 - 1e-9), math.floor(ay1 + 1e-9)       # whole pixels, never past the box
        rxi, ryi = max(1, (i1 - i0) // 2), max(1, (j1 - j0) // 2)
        out["x"], out["y"], out["rx"], out["ry"] = i0 + rxi, j0 + ryi, rxi, ryi
        return out
    out["x"], out["y"] = (ax0 + ax1) / 2, (ay0 + ay1) / 2
    out["rx"], out["ry"] = max(1.0, (ax1 - ax0) / 2), max(1.0, (ay1 - ay0) / 2)
    return out


# ---------------------------------------------------------------------------------------------------------------- the camera inside the box
CANVAS_W, CANVAS_H = 1920.0, 1080.0      # the engine's frame (bti.engine.limits)
OFF_LIMIT = 0.01                         # a frame shows too much of what is outside the box when more than this share of it does
WHOLE_SLACK = 0.01                       # a frame "holds the whole box" when it holds it up to this share of the box's own size on each side
MATTE_RATIO = 1.25                       # along an axis where the frame is this many times the box or more, the painting stands in the matte by design: bars at both sides are not a fault


def frame_rect(cx: float, cy: float, zoom: float) -> tuple[float, float, float, float]:
    """The part of the picture a camera key shows: `(x0, y0, x1, y1)` in picture pixels (the frame is 1920 x 1080 screen pixels, `zoom` screen pixels per picture pixel)."""
    vw, vh = CANVAS_W / zoom, CANVAS_H / zoom
    return cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2


def holds_whole(box, cx: float, cy: float, zoom: float) -> bool:
    """Does the frame of this camera key hold the whole box (up to WHOLE_SLACK)? Such a frame is a pull-back, the whole painting on screen with the matte round it
    by design (the opening shot, a chapter mark): whatever is outside the box in it is not a fault."""
    x0, y0, x1, y1 = box
    fx0, fy0, fx1, fy1 = frame_rect(cx, cy, zoom)
    sx, sy = WHOLE_SLACK * (x1 - x0), WHOLE_SLACK * (y1 - y0)
    return fx0 <= x0 + sx and fx1 >= x1 - sx and fy0 <= y0 + sy and fy1 >= y1 - sy


def _judged_axes(box, cx: float, cy: float, zoom: float) -> tuple[bool, bool]:
    """Which axes of a frame are judged. An axis is NOT when the frame is MATTE_RATIO times the box or more along it AND holds the box along it (up to WHOLE_SLACK):
    the painting is narrow, or short, in a wide frame and stands in the matte at both sides, which is the look and not a fault. Every other axis is judged: a frame
    that is a window onto the painting there, or hugs its width with a band of ground at each side, or is so far off that it cuts the painting at one side."""
    x0, y0, x1, y1 = box
    fx0, fy0, fx1, fy1 = frame_rect(cx, cy, zoom)
    sx, sy = WHOLE_SLACK * (x1 - x0), WHOLE_SLACK * (y1 - y0)
    matte_x = fx1 - fx0 >= MATTE_RATIO * (x1 - x0) and fx0 <= x0 + sx and fx1 >= x1 - sx
    matte_y = fy1 - fy0 >= MATTE_RATIO * (y1 - y0) and fy0 <= y0 + sy and fy1 >= y1 - sy
    return not matte_x, not matte_y


def outside_share(box, cx: float, cy: float, zoom: float) -> float:
    """The share (0..1) of the frame of this camera key that lies outside the box, counted along the judged axes only (see `_judged_axes`), and 0 for a frame that
    holds the whole box (`holds_whole`). What a viewer sees there is a band of the photograph's black ground, or of the matte, at a side of a frame that is
    otherwise the painting: the camera went past the edge of the painting, or nearly fills the width of a painting that has a ground band."""
    if not (zoom > 0 and all(_num(v) for v in (cx, cy, zoom))):
        return 0.0
    if holds_whole(box, cx, cy, zoom):
        return 0.0
    x0, y0, x1, y1 = box
    fx0, fy0, fx1, fy1 = frame_rect(cx, cy, zoom)
    jx, jy = _judged_axes(box, cx, cy, zoom)
    ox = max(0.0, x0 - fx0) + max(0.0, fx1 - x1) if jx else 0.0
    oy = max(0.0, y0 - fy0) + max(0.0, fy1 - y1) if jy else 0.0
    ox, oy = min(ox, fx1 - fx0), min(oy, fy1 - fy0)
    return max(0.0, 1.0 - (1.0 - ox / (fx1 - fx0)) * (1.0 - oy / (fy1 - fy0)))


def fit_frame(box, cx: float, cy: float, zoom: float) -> tuple[float, float, float]:
    """The camera key `(cx, cy, zoom)` as it must be to show nothing outside the box, changing as little as possible: a key that already shows at most OFF_LIMIT
    of its frame outside the box (`outside_share`), or holds the whole box, is returned as it is. Otherwise the zoom is raised only as far as the frame needs to
    fit the box along the judged axes (`1920 / box width` and `1080 / box height`, rounded up at the fifth decimal) and the centre is moved, along those axes, to the
    nearest point from which the frame lies inside the box (a centre is rounded to hundredths, towards the inside). Raising the zoom or moving the centre can change
    which axes are judged, so this is repeated until the key is right (at most four times; it always is, the zoom of the box's own fit is the end of the road)."""
    if outside_share(box, cx, cy, zoom) <= OFF_LIMIT:
        return cx, cy, zoom
    x0, y0, x1, y1 = box

    def inside(c: float, lo: float, hi: float) -> float:
        lo2, hi2 = math.ceil(lo * 100 - 1e-9) / 100, math.floor(hi * 100 + 1e-9) / 100
        if lo2 > hi2:                                      # the room is under a hundredth of a pixel: the middle
            return round((lo + hi) / 2, 2)
        return min(max(round(c, 2), lo2), hi2)

    z = zoom
    for _ in range(4):
        jx, jy = _judged_axes(box, cx, cy, z)
        need = math.ceil(max([CANVAS_W / (x1 - x0)] * jx + [CANVAS_H / (y1 - y0)] * jy + [z]) * 1e5 - 1e-9) / 1e5
        z = max(z, need)
        jx, jy = _judged_axes(box, cx, cy, z)
        hw, hh = CANVAS_W / z / 2, CANVAS_H / z / 2
        if jx:
            cx = inside(cx, x0 + hw, x1 - hw)
        if jy:
            cy = inside(cy, y0 + hh, y1 - hh)
        if outside_share(box, cx, cy, z) <= OFF_LIMIT:
            break
    else:                                                  # never reached for a box with a size; the last word is the box's own fit, centred
        z = math.ceil(max(CANVAS_W / (x1 - x0), CANVAS_H / (y1 - y0), z) * 1e5 - 1e-9) / 1e5
        cx, cy = inside(cx, x0 + CANVAS_W / z / 2, x1 - CANVAS_W / z / 2), inside(cy, y0 + CANVAS_H / z / 2, y1 - CANVAS_H / z / 2)
    return cx, cy, z


def whole_frame(box, fit_pct: float, canvas_w: float = CANVAS_W, canvas_h: float = CANVAS_H) -> tuple[float, float, float, float]:
    """The camera that shows the whole box as the matte shots show a painting (the box fills `fit_pct` of the frame, in the direction that is tighter), centred on
    the box: `(cx, cy, zoom, zoom at which the box exactly touches the frame)`."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    z = min(fit_pct / 100.0 * canvas_h / bh, fit_pct / 100.0 * canvas_w / bw)
    return (x0 + x1) / 2, (y0 + y1) / 2, z, min(canvas_h / bh, canvas_w / bw)
