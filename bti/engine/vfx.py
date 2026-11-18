"""Virtual-camera and overlay primitives (lifted from demo_runs/claude_code/lib/vfx.py).

Changes against the original: fonts come from a configurable map (`configure_fonts`, fed from style.json) and are cached;
the canvas size is a default only (every primitive takes explicit sizes); image loading is done by `ImageStore` in
`bti.engine.scene` (an LRU), `Img` itself is unchanged.  Everything renders at 1920x1080 and is resized down afterwards.

Original docstring:

All camera motion is sub-pixel: cv2.warpAffine with a float matrix + INTER_CUBIC from an area-averaged image pyramid
(level chosen so the warp scale stays within 0.7-1.4, i.e. never aliases, never zoompan).  Frames are BGR uint8.
"""
import math, os, sys, threading
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .guard import check_pixels, unlimited

W, H = 1920, 1080
cv2.setNumThreads(int(os.environ.get("CV_THREADS", "4")))

# ----------------------------------------------------------------------------- fonts
# Same behaviour as the benchmark: Windows faces first, then the macOS fallback (Futura for reg/bold), then PIL's default.
# `configure_fonts(style)` may override the macOS label face from style.json (fonts.stand_in_label_mac) and accepts an
# optional full map `fonts.map = {kind: [path, ...]}` (not present in style.json today).
_FONT_CANDIDATES = {
    "reg": [r"C:\Windows\Fonts\GOTHIC.TTF", "/System/Library/Fonts/Supplemental/Futura.ttc", "/System/Library/Fonts/Helvetica.ttc"],
    "bold": [r"C:\Windows\Fonts\GOTHICB.TTF", "/System/Library/Fonts/Supplemental/Futura.ttc", "/System/Library/Fonts/Helvetica.ttc"],
    "sans_bold": [r"C:\Windows\Fonts\arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "serif_it": [r"C:\Windows\Fonts\georgiai.ttf", r"C:\Windows\Fonts\timesi.ttf", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"],
}
_FONTS = {k: list(v) for k, v in _FONT_CANDIDATES.items()}
_FONT_CACHE = {}
_FONT_LOCK = threading.RLock()


def configure_fonts(style=None):
    """Apply the font section of style.json (idempotent)."""
    global _FONTS
    fonts = {k: list(v) for k, v in _FONT_CANDIDATES.items()}
    f = (style or {}).get("fonts", {}) or {}
    mac = (f.get("stand_in_label_mac") or {}).get("value") if isinstance(f.get("stand_in_label_mac"), dict) else f.get("stand_in_label_mac")
    if isinstance(mac, str) and mac.startswith("/"):
        for kind in ("reg", "bold"):
            fonts[kind] = [p for p in fonts[kind] if p.startswith("C:")] + [mac] + [p for p in fonts[kind] if not p.startswith("C:") and p != mac]
    m = f.get("map")
    if isinstance(m, dict):
        for kind, paths in m.items():
            if isinstance(paths, list):
                fonts[kind] = list(paths)
    with _FONT_LOCK:
        _FONTS = fonts
        _FONT_CACHE.clear()


# Bundled faces (the channel identity, family ID-*): EB Garamond Regular / Italic / Medium, static .ttf files with their licence in
# style/gae/fonts/. They load from that folder on every machine; a missing or unreadable file is an error that names the file and
# the folder, never a silent fallback to another face (the identity must not quietly change its typeface).
BUNDLED_FONTS = {"eb_regular": "EBGaramond-Regular.ttf", "eb_italic": "EBGaramond-Italic.ttf", "eb_medium": "EBGaramond-Medium.ttf"}


class BundledFontError(FileNotFoundError):
    """A bundled font file is missing or cannot be read."""


def bundled_font_dir():
    from . import registry as _registry          # late: the style root can be moved by BTI_STYLE_ROOT before the first use
    return _registry.STYLE_ROOT / "gae" / "fonts"


def bundled_font_path(kind):
    return bundled_font_dir() / BUNDLED_FONTS[kind]


def font_signature():
    """Stable text identifying the font choice; part of every text-layer cache key."""
    out = []
    with _FONT_LOCK:
        kinds = sorted(_FONTS)
        candidates = {k: list(_FONTS[k]) for k in kinds}
    for kind in kinds:
        first = next((p for p in candidates[kind] if os.path.exists(p)), "default")
        out.append(kind + "=" + os.path.basename(first))
    for kind in sorted(BUNDLED_FONTS):
        p = bundled_font_path(kind)
        out.append("%s=%s:%s" % (kind, p.name, p.stat().st_size if p.is_file() else "missing"))
    return ";".join(out)


def _bundled_font(kind, size):
    p = bundled_font_path(kind)
    if not p.is_file():
        raise BundledFontError("the bundled font %s is missing: expected the file %s (the EB Garamond files ship with the project in "
                               "style/gae/fonts/ and are never replaced by another face)" % (kind, p))
    try:
        return ImageFont.truetype(str(p), size)
    except OSError as e:
        raise BundledFontError("the bundled font file %s cannot be read (%s)" % (p, e)) from e


def cap_ratio(kind):
    """Cap height of the face as a fraction of its font size (px per px of size), measured on the glyph H of the real font."""
    key = ("cap_ratio", kind)
    with _FONT_LOCK:
        if key in _FONT_CACHE:
            return _FONT_CACHE[key]
    big = 2000
    top = font(kind, big).getbbox("H", anchor="ls")[1]
    r = -top / big
    with _FONT_LOCK:
        _FONT_CACHE[key] = r
    return r


def font(kind, size):
    key = (kind, int(size))
    with _FONT_LOCK:
        if key in _FONT_CACHE:
            return _FONT_CACHE[key]
        candidates = list(_FONTS.get(kind, []))
    if kind in BUNDLED_FONTS:
        res = _bundled_font(kind, int(size))
        with _FONT_LOCK:
            _FONT_CACHE[key] = res
        return res
    res = None
    for p in candidates:
        if os.path.exists(p):
            try:
                if p.endswith(".ttc") and "Futura" in p:
                    res = ImageFont.truetype(p, size, index=0 if kind == "reg" else 2)
                else:
                    res = ImageFont.truetype(p, size)
                break
            except Exception:
                continue
    if res is None:
        res = ImageFont.load_default()
    with _FONT_LOCK:
        _FONT_CACHE[key] = res
    return res


# ----------------------------------------------------------------------------- easing
def _clamp(p):
    return 0.0 if p < 0 else 1.0 if p > 1 else p


EASE = {
    "linear": lambda p: p,
    "in_quad": lambda p: p * p,
    "in_cubic": lambda p: p ** 3,
    "out_cubic": lambda p: 1 - (1 - p) ** 3,
    "out_quad": lambda p: 1 - (1 - p) ** 2,
    "inout_cubic": lambda p: 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2,
    "inout_sine": lambda p: -(math.cos(math.pi * p) - 1) / 2,
}


def ease(name, p):
    return EASE[name](_clamp(p))


def ramp(t, t0, dur, name="linear"):
    """0 -> 1 envelope starting at t0 lasting dur."""
    if dur <= 0:
        return 1.0 if t >= t0 else 0.0
    return ease(name, (t - t0) / dur)


def window(t, t0, t1, fin=0.1, fout=0.1):
    """0..1..0 envelope: fade in at t0, fade out ending at t1."""
    return min(ramp(t, t0, fin), 1 - ramp(t, t1 - fout, fout)) if t1 > t0 else 0.0


# ----------------------------------------------------------------------------- source images
class Img:
    """Full-resolution source with an area-averaged pyramid."""

    def __init__(self, path_or_arr, name=""):
        a = cv2.imread(path_or_arr, cv2.IMREAD_COLOR) if isinstance(path_or_arr, str) else path_or_arr
        assert a is not None, path_or_arr
        self.name = name or str(path_or_arr)
        self.levels = [a]
        while min(self.levels[-1].shape[:2]) // 2 >= 256:
            p = self.levels[-1]
            with unlimited():                      # sized by the source file, not by the storyboard
                self.levels.append(cv2.resize(p, (p.shape[1] // 2, p.shape[0] // 2), interpolation=cv2.INTER_AREA))
        self.h, self.w = a.shape[:2]

    def rect(self, cx, cy, zoom, ow=W, oh=H):
        """Where the source rectangle lands on the canvas: (x0, y0, x1, y1) in canvas px."""
        return (ow / 2 + (0 - cx) * zoom, oh / 2 + (0 - cy) * zoom, ow / 2 + (self.w - cx) * zoom, oh / 2 + (self.h - cy) * zoom)

    def view(self, cx, cy, zoom, ow=W, oh=H, bg=None, region=None):
        """Render the source into an ow x oh canvas. (cx,cy)=source point at canvas centre, zoom=out px per source px.
        Returns (frame BGR, alpha float32 ow x oh x1).  Outside the source, frame is `bg` (or 0) and alpha 0."""
        check_pixels(ow, oh, "view")
        k = int(round(math.log2(1.0 / zoom))) if zoom < 1 else 0
        k = max(0, min(k, len(self.levels) - 1))
        s = zoom * (2 ** k)
        lv = self.levels[k]
        sx = (cx / 2 ** k)
        sy = (cy / 2 ** k)
        M = np.array([[s, 0, ow / 2 - s * sx], [0, s, oh / 2 - s * sy]], np.float64)
        out = cv2.warpAffine(lv, M, (ow, oh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        # analytic anti-aliased alpha of the source rectangle
        x0 = ow / 2 + (0 - cx) * zoom
        x1 = ow / 2 + (self.w - cx) * zoom
        y0 = oh / 2 + (0 - cy) * zoom
        y1 = oh / 2 + (self.h - cy) * zoom
        rx0, ry0, rx1, ry1 = region if region is not None else (0, 0, ow, oh)     # alpha only over `region` (x0, y0, x1, y1) when given
        xs = np.arange(rx0, rx1, dtype=np.float32) + .5
        ys = np.arange(ry0, ry1, dtype=np.float32) + .5
        ax = np.clip(np.minimum(xs - x0, x1 - xs), 0, 1)
        ay = np.clip(np.minimum(ys - y0, y1 - ys), 0, 1)
        alpha = (ay[:, None] * ax[None, :])[:, :, None].astype(np.float32)
        return out, alpha, (x0, y0, x1, y1)

    def to_screen(self, px, py, cx, cy, zoom, ow=W, oh=H):
        return ow / 2 + (px - cx) * zoom, oh / 2 + (py - cy) * zoom


# ----------------------------------------------------------------------------- backdrop (designed near-black gallery matte)
_BD = {}
_BD_LOCK = threading.RLock()


def backdrop(ow=W, oh=H):
    key = (ow, oh)
    with _BD_LOCK:
        if key in _BD:
            return _BD[key]
    yy, xx = np.mgrid[0:oh, 0:ow].astype(np.float32)
    r = np.sqrt(((xx - ow / 2) / (ow * .62)) ** 2 + ((yy - oh * .46) / (oh * .72)) ** 2)
    v = 30 - 24 * np.clip(r, 0, 1.15) ** 1.4          # centre ~#1e, edges ~#06
    v = np.clip(v, 5, 30)
    bgr = np.stack([v * 1.02, v * 0.99, v * 0.97], -1)  # faint warm-neutral
    rng = np.random.RandomState(7)
    bgr += rng.normal(0, 0.6, bgr.shape[:2])[:, :, None]  # grain kills 8-bit banding
    res = np.clip(bgr, 0, 255).astype(np.float32)
    with _BD_LOCK:
        _BD[key] = res
    return res


def compose_matte(img, cx, cy, zoom, ow=W, oh=H, shadow=True):
    """Painting over designed backdrop with soft drop shadow. Returns float32 BGR frame."""
    x0, y0, x1, y1 = img.rect(cx, cy, zoom, ow, oh)
    ix0, ix1 = max(0, int(math.floor(x0)) - 1), min(ow, int(math.ceil(x1)) + 1)
    iy0, iy1 = max(0, int(math.floor(y0)) - 1), min(oh, int(math.ceil(y1)) + 1)
    out, alpha, _ = img.view(cx, cy, zoom, ow, oh, region=(ix0, iy0, max(ix1, ix0), max(iy1, iy0)))   # alpha only where it can be non-zero
    bd = backdrop(ow, oh)                     # shared, never modified: a copy is made below only when it is blended into
    covers = x0 <= 0 and y0 <= 0 and x1 >= ow and y1 >= oh
    if covers:
        return out.astype(np.float32)
    if shadow:
        sh = np.zeros((oh // 4, ow // 4), np.float32)
        d = max(6, 14 * zoom / 0.17) / 4
        cv2.rectangle(sh, (int((x0 + 10) / 4), int((y0 + 22) / 4)), (int((x1 + 10) / 4), int((y1 + 22) / 4)), 1.0, -1)
        sh = cv2.GaussianBlur(sh, (0, 0), max(3.0, 11 * min(zoom, .6) / .17 / 4 * .5 + 3))
        sh *= -.75                            # 1 - .75*sh on the small array (resize is linear, so it commutes)
        sh += 1
        sh = cv2.resize(sh, (ow, oh), interpolation=cv2.INTER_LINEAR)[:, :, None]
        bd = bd * sh                          # a new array (this is the copy)
    else:
        bd = bd.copy()
    # bd*(1-a) + out*a == bd + (out-bd)*a. Outside the painting's rectangle a is exactly 0 (the frame is the backdrop), so only
    # the rectangle (grown by a pixel) is blended; in place, no full-frame temporaries.
    if ix1 > ix0 and iy1 > iy0:
        sl = (slice(iy0, iy1), slice(ix0, ix1))
        reg = out[sl].astype(np.float32)
        reg -= bd[sl]
        reg *= alpha
        reg += bd[sl]
        bd[sl] = reg
    return bd


# ----------------------------------------------------------------------------- camera paths
class Cam:
    """Keyframed camera: keys = [(t, cx, cy, zoom, ease_to_next)]. Zoom interpolates in log space."""

    def __init__(self, keys):
        self.k = keys

    def at(self, t):
        k = self.k
        if t <= k[0][0]:
            return k[0][1:4]
        for a, b in zip(k[:-1], k[1:]):
            if t <= b[0]:
                p = ease(a[4], (t - a[0]) / (b[0] - a[0]))
                cx = a[1] + (b[1] - a[1]) * p
                cy = a[2] + (b[2] - a[2]) * p
                z = math.exp(math.log(a[3]) + (math.log(b[3]) - math.log(a[3])) * p)
                return cx, cy, z
        return k[-1][1:4]


# ----------------------------------------------------------------------------- overlay layers (pre-rendered RGBA, alpha-blended with an envelope)
class Layer:
    def __init__(self, rgba, x0=0, y0=0):
        a = np.asarray(rgba)
        self.x0, self.y0 = x0, y0
        self.rgb = a[:, :, :3][:, :, ::-1].astype(np.float32)  # to BGR
        self.a = (a[:, :, 3:4].astype(np.float32) / 255.0)

    def apply(self, frame, env=1.0, dx=0, dy=0):
        if env <= 0.001:
            return frame
        h, w = self.a.shape[:2]
        x0, y0 = self.x0 + int(dx), self.y0 + int(dy)
        fx0, fy0 = max(x0, 0), max(y0, 0)
        fx1, fy1 = min(x0 + w, frame.shape[1]), min(y0 + h, frame.shape[0])
        if fx1 <= fx0 or fy1 <= fy0:
            return frame
        sl = (slice(fy0 - y0, fy1 - y0), slice(fx0 - x0, fx1 - x0))
        a = self.a[sl] * env
        reg = frame[fy0:fy1, fx0:fx1]
        frame[fy0:fy1, fx0:fx1] = reg * (1 - a) + self.rgb[sl] * a
        return frame


def _tracked(draw, xy, text, fnt, fill, tracking=0, anchor="la"):
    """Text with letter tracking (px). anchor 'la' or 'ma' (centre)."""
    x, y = xy
    widths = [draw.textlength(c, font=fnt) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    if anchor[0] == "m":
        x -= total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill)
        x += w + tracking


def label_layer(title, sub=None, y0=.70, h=140, x_text=.07, w=W, hh=H, opacity=0.80, fade_frac=0.22, size=58, sub_size=32, pad=16, gap=78):
    """Channel-style detail label: dark translucent strip, white caps title, smaller 2nd line (artist, year).
    (opacity/fade_frac/size/sub_size/pad/gap are new keyword arguments; their defaults reproduce the benchmark.)"""
    Y0 = int(y0 * hh)
    if h < 1 or w < 1:
        return Layer(np.zeros((1, 1, 4), np.uint8), 0, 0)      # a strip whose bottom edge is above its top edge: nothing to draw
    a = np.full((h, w), opacity * 255, np.float32)
    fade = int(w * fade_frac)
    if fade > 0:
        a[:, w - fade:] *= np.linspace(1, 0, fade)[None, :]       # right end of the strip fades out (as in the reference)
    strip = np.zeros((h, w, 4), np.uint8)
    strip[:, :, 3] = a.astype(np.uint8)
    strip[:, :, :3] = 8
    im = Image.fromarray(strip, "RGBA")
    d = ImageDraw.Draw(im)
    ft = font("reg", size)
    _tracked(d, (int(x_text * w), pad), title, ft, (255, 255, 255, 255), tracking=2)
    if sub:
        _tracked(d, (int(x_text * w), pad + gap), sub, font("reg", sub_size), (205, 205, 205, 255), tracking=1)
    return Layer(np.array(im), 0, Y0)


def text_layer(text, cx, cy, size=90, kind="reg", tracking=6, color=(255, 255, 255), sub=None, subsize=30, w=W, h=H, shadow=True):
    """Centred text (and optional sub line) on a transparent full-frame layer, cropped to its bbox."""
    check_pixels(w, h, "text layer")
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ft = font(kind, size)
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        _tracked(sd, (cx, cy - size // 2), text, ft, (0, 0, 0, 170), tracking, "ma")
        if sub:
            _tracked(sd, (cx, cy + size // 2 + 6), sub, font("reg", subsize), (0, 0, 0, 170), 2, "ma")
        sh = sh.filter(ImageFilter.GaussianBlur(9))
        im.alpha_composite(sh)
        d = ImageDraw.Draw(im)
    _tracked(d, (cx, cy - size // 2), text, ft, color + (255,), tracking, "ma")
    if sub:
        _tracked(d, (cx, cy + size // 2 + 6), sub, font("reg", subsize), (225, 225, 225, 255), 2, "ma")
    arr = np.array(im)
    ys, xs = np.where(arr[:, :, 3] > 0)
    if ys.size == 0:
        return Layer(np.zeros((1, 1, 4), np.uint8), 0, 0)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return Layer(arr[y0:y1, x0:x1], x0, y0)


# ----------------------------------------------------------------------------- effects on frames
def spotlight(frame, sx, sy, rx, ry, a, floor=0.35, feather=0.55):
    """Dim everything outside a feathered ellipse at screen (sx,sy) to `floor` brightness; a in 0..1 is the ramp."""
    if a <= 0.001:
        return frame
    h, w = frame.shape[:2]
    q = 4
    yy, xx = np.mgrid[0:h // q, 0:w // q].astype(np.float32)
    d = np.sqrt(((xx * q - sx) / max(rx, 1)) ** 2 + ((yy * q - sy) / max(ry, 1)) ** 2)
    m = np.clip((d - (1 - feather * .5)) / feather, 0, 1)       # 0 inside, 1 outside (smooth edge)
    m = m * m * (3 - 2 * m)
    m = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)[:, :, None]
    gain = 1 - (1 - floor) * m * a
    return frame * gain


def smoothstep(u):
    """0 -> 1 smooth step of `u` (a number or an array), clamped to 0..1."""
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


class Band:
    """A soft-edged strip of light that travels across the canvas (the channel identity, family ID-*).

    The strip has straight edges tilted `angle_deg` from the vertical (a "/" for a positive angle) and moves along the axis that is
    perpendicular to them, in one direction at constant speed. Its profile along the axis is a plateau (`core`) with smoothstep
    shoulders (`edge`): `width_pct` is the width of the strip at half brightness (core + edge), `feather` the part of that width that
    each shoulder takes (0.05 sharp .. 1 no plateau). `s` is the signed distance in px of a pixel from the strip's centre line along
    the direction of travel: s > 0 is AHEAD of the strip (not yet reached), s < 0 BEHIND it (already passed).

    Everything is a pure function of the progress `q` (0 = the strip is just off the canvas where it enters, 1 = just off the canvas
    where it leaves, with a run-in margin so that a strip is never visible at q = 0 or q = 1). Masks are computed on a grid reduced by
    `qres` and enlarged bilinearly (as `spotlight` does); the reveal mask of a text box is computed the same way on that box only."""

    RUN_IN = 0.13           # extra travel before and after the canvas, as a fraction of the axis length (the mock-up's -22 % .. 122 %)

    def __init__(self, w, h, width_pct, feather, angle_deg, direction="left_to_right"):
        a = math.radians(float(angle_deg))
        self.w, self.h = int(w), int(h)
        self.ca, self.sa = math.cos(a), math.sin(a)
        self.length = abs(self.w * self.ca) + abs(self.h * self.sa)             # axis length over the canvas (corner to corner)
        width = max(float(width_pct) / 100.0 * self.w, 1.0)
        self.edge = max(width * min(max(float(feather), 0.0), 1.0), 1e-3)         # one shoulder
        self.core = max(width - self.edge, 0.0)                                  # the plateau
        self.half = self.core / 2.0 + self.edge                                  # centre line to where the strip ends
        pad = self.half + self.RUN_IN * self.length
        self.span = (-(self.length / 2.0 + pad), self.length / 2.0 + pad)        # centre-line positions at q = 0 and q = 1 (left to right)
        self.sign = -1.0 if direction == "right_to_left" else 1.0

    def centre(self, q):
        """Axis position (px from the canvas centre, positive to the right and down-right) of the strip's centre line."""
        q = min(max(float(q), 0.0), 1.0)
        a, b = self.span
        return a + q * (b - a) if self.sign > 0 else b - q * (b - a)

    def s_grid(self, q, xs, ys):
        """Signed distance ahead (px) for pixel-centre coordinates `xs` (1-D, width) and `ys` (1-D, height): shape (len(ys), len(xs))."""
        u = (xs[None, :] - self.w / 2.0) * self.ca + (ys[:, None] - self.h / 2.0) * self.sa
        return (u - self.centre(q)) * self.sign

    def profile(self, s):
        """Strip brightness weight 0..1 at signed distance s."""
        return 1.0 - smoothstep((np.abs(s) - self.core / 2.0) / self.edge)

    def reveal(self, s):
        """Largest value the strip's profile has had so far at a pixel with signed distance s (1 once the centre line has passed)."""
        return 1.0 - smoothstep((s - self.core / 2.0) / self.edge)

    def reveal_box(self, q, x0, y0, x1, y1, qres=4):
        """Reveal values (float32, y1-y0 by x1-x0) for the canvas pixels x0..x1, y0..y1: computed on a grid reduced by `qres` and enlarged
        bilinearly (the profile's shoulders are many pixels wide), so a text box costs a fraction of a millisecond."""
        bw, bh = x1 - x0, y1 - y0
        gw, gh = max(2, -(-bw // qres)), max(2, -(-bh // qres))
        xs = x0 + (np.arange(gw, dtype=np.float32) + 0.5) * (bw / gw)
        ys = y0 + (np.arange(gh, dtype=np.float32) + 0.5) * (bh / gh)
        m = self.reveal(self.s_grid(q, xs, ys)).astype(np.float32)
        return cv2.resize(m, (bw, bh), interpolation=cv2.INTER_LINEAR)

    def light(self, frame, q, ahead, wake, warm=0.0, qres=4):
        """Multiply `frame` (float32 BGR, IN PLACE) by the strip's light: `ahead` of it, 1 inside it, `wake` behind it, plus a warm tint
        (`warm` is the screen-blend opacity of an amber (255, 205, 140) at full strength inside the strip). Returns the frame.

        The gain is a low-resolution map enlarged bilinearly (as `spotlight` does) and only the columns where it is not constant are
        touched with it (about a third of the frame); the rest is one scalar multiply. The tint is folded into the same pass:
        f * (g * (1 - a t)) + 255 * a * t per channel (a = warm * strip weight, t = the tint)."""
        if ahead >= 1.0 and wake >= 1.0:
            return frame
        if q <= 0.0:
            return gain_in_place(frame, ahead)
        if q >= 1.0:
            return gain_in_place(frame, wake)
        h, w = frame.shape[:2]
        if w % qres or h % qres:
            qres = 1
        gh, gw = h // qres, w // qres
        xs = (np.arange(gw, dtype=np.float32) + 0.5) * qres
        ys = (np.arange(gh, dtype=np.float32) + 0.5) * qres
        s = self.s_grid(q, xs, ys)
        b = self.profile(s)
        r = smoothstep(-s / self.half)
        g = ahead + (wake - ahead) * r
        g = (g + (1.0 - g) * b).astype(np.float32)
        varying = (b.max(axis=0) > 1e-4) | ((r.max(axis=0) - r.min(axis=0)) > 1e-4)
        cols = np.nonzero(varying)[0]
        if not cols.size:                                           # the strip is wholly off the canvas: one level for all of it
            return gain_in_place(frame, float(g[0, 0]))
        j0, j1 = max(0, int(cols[0]) - 2), min(gw, int(cols[-1]) + 3)
        x0, x1 = j0 * qres, j1 * qres
        if x0 > 0:
            gain_in_place(frame[:, :x0], float(g[0, 0]))                   # columns that are entirely ahead of the strip (or entirely behind)
        if x1 < w:
            gain_in_place(frame[:, x1:], float(g[0, gw - 1]))
        reg = frame[:, x0:x1]
        gz = g[:, j0:j1]
        if warm > 0:
            a = (b[:, j0:j1] * warm)[:, :, None]
            gain = cv2.resize((gz[:, :, None] * (1.0 - a * _WARM_BGR)).astype(np.float32), (x1 - x0, h), interpolation=cv2.INTER_LINEAR)
            lift = cv2.resize(((255.0 * a) * _WARM_BGR).astype(np.float32), (x1 - x0, h), interpolation=cv2.INTER_LINEAR)
            reg[...] = cv2.multiply(reg, gain)
            reg += lift
        else:
            gain = cv2.resize(gz, (x1 - x0, h), interpolation=cv2.INTER_LINEAR)
            reg[...] = cv2.multiply(reg, cv2.merge([gain, gain, gain]))
        return frame


def gain_in_place(frame, k):
    """frame *= k in place (a view of a frame is fine); returns it."""
    if k != 1.0:
        np.multiply(frame, np.float32(k), out=frame)
    return frame


_WARM_BGR = np.array([140.0, 205.0, 255.0], np.float32) / 255.0


def composite_layer_masked(frame, layer, mask_fn=None, env=1.0):
    """Draw `layer` on `frame` (IN PLACE, like `Layer.apply`) with the opacity `env` times a per-pixel mask: `mask_fn(x0, y0, x1, y1)`
    returns the mask (0..1, float32, shape y1-y0 by x1-x0) of the canvas box that the layer covers (clipped to the frame); None means
    no mask. Only the columns where the mask is not zero are touched. Used for text that is revealed by a moving band."""
    if env <= 0.001:
        return frame
    lh, lw = layer.a.shape[:2]
    x0, y0 = layer.x0, layer.y0
    fx0, fy0 = max(x0, 0), max(y0, 0)
    fx1, fy1 = min(x0 + lw, frame.shape[1]), min(y0 + lh, frame.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return frame
    a = layer.a[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    rgb = layer.rgb[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    if mask_fn is not None:
        m = mask_fn(fx0, fy0, fx1, fy1)
        cols = np.nonzero(m.max(axis=0) > 0.001)[0]
        if not cols.size:
            return frame
        c0, c1 = int(cols[0]), int(cols[-1]) + 1
        a, rgb, fx0, fx1 = a[:, c0:c1] * (m[:, c0:c1, None] * env), rgb[:, c0:c1], fx0 + c0, fx0 + c1
    else:
        a = a * env
    reg = frame[fy0:fy1, fx0:fx1]
    reg -= (reg - rgb) * a                                   # reg * (1 - a) + rgb * a
    return frame


def ring(frame, sx, sy, r, prog, alpha=0.75, thick=13, color=(205, 205, 205)):
    """Light-grey ring drawn on over prog 0..1 (arc sweep from top, clockwise)."""
    if prog <= 0 or alpha <= 0:
        return frame
    pad = int(r + thick + 4)
    x0, y0 = int(sx - pad), int(sy - pad)
    x1, y1 = x0 + 2 * pad, y0 + 2 * pad
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x1, frame.shape[1]), min(y1, frame.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return frame
    S = 2
    m = np.zeros(((y1 - y0) * S, (x1 - x0) * S), np.uint8)
    cv2.ellipse(m, (int(pad * S + (sx - int(sx)) * S), int(pad * S + (sy - int(sy)) * S)), (int(r * S), int(r * S)), -90, 0, 360 * min(prog, 1.0), 255, int(thick * S), cv2.LINE_AA)
    m = cv2.resize(m, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA).astype(np.float32)[:, :, None] / 255 * alpha
    m = m[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    frame[fy0:fy1, fx0:fx1] = frame[fy0:fy1, fx0:fx1] * (1 - m) + np.array(color, np.float32) * m
    return frame


def blend(a, b, p):
    return a * (1 - p) + b * p


def put(frame, x, y, img, alpha=None):
    """Draw `img` (h, w, 3) on `frame` with its top-left corner at (x, y), clipped to the canvas: the part that lies outside is
    dropped, a box that lies completely outside draws nothing. `alpha` (0..1) blends instead of replacing. Slice assignment with a
    box that leaves the canvas fails (or wraps around when x or y is negative), so every layout draws through this."""
    x, y = int(x), int(y)
    h, w = img.shape[:2]
    fx0, fy0 = max(x, 0), max(y, 0)
    fx1, fy1 = min(x + w, frame.shape[1]), min(y + h, frame.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return frame
    part = img[fy0 - y:fy1 - y, fx0 - x:fx1 - x]
    if alpha is None:
        frame[fy0:fy1, fx0:fx1] = part
    else:
        frame[fy0:fy1, fx0:fx1] = frame[fy0:fy1, fx0:fx1] * (1 - alpha) + part * alpha
    return frame


def to_u8(f):
    return np.clip(f, 0, 255).astype(np.uint8)


def blurred_bg(img_bgr, ow=W, oh=H, sigma=38, dark=.38, center=(0.5, 0.40)):
    """16:9 blurred-artwork background from any image (cover-crop, heavy blur, darkened)."""
    h, w = img_bgr.shape[:2]
    sc = max(ow / w, oh / h)
    big = cv2.resize(img_bgr, (int(w * sc) + 1, int(h * sc) + 1), interpolation=cv2.INTER_AREA)
    x0 = int((big.shape[1] - ow) * center[0])
    y0 = int((big.shape[0] - oh) * center[1])
    crop = big[y0:y0 + oh, x0:x0 + ow]
    bl = cv2.GaussianBlur(crop, (0, 0), sigma).astype(np.float32) * dark
    yy, xx = np.mgrid[0:oh, 0:ow].astype(np.float32)
    vig = 1 - .55 * np.clip(np.sqrt(((xx - ow / 2) / (ow * .7)) ** 2 + ((yy - oh / 2) / (oh * .7)) ** 2), 0, 1) ** 2
    return bl * vig[:, :, None]


def hline(frame, cx, y, w, th=2, alpha=.8):
    x0, x1 = int(cx - w / 2), int(cx + w / 2)
    frame[int(y):int(y) + th, x0:x1] = frame[int(y):int(y) + th, x0:x1] * (1 - alpha) + 255 * alpha
    return frame
