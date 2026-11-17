"""Virtual-camera and overlay primitives (lifted from demo_runs/claude_code/lib/vfx.py).

Changes against the original: fonts come from a configurable map (`configure_fonts`, fed from style.json) and are cached;
the canvas size is a default only (every primitive takes explicit sizes); image loading is done by `ImageStore` in
`bti.engine.scene` (an LRU), `Img` itself is unchanged.  Everything renders at 1920x1080 and is resized down afterwards.

Original docstring:

All camera motion is sub-pixel: cv2.warpAffine with a float matrix + INTER_CUBIC from an area-averaged image pyramid
(level chosen so the warp scale stays within 0.7-1.4, i.e. never aliases, never zoompan).  Frames are BGR uint8.
"""
import math, os, sys
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
    _FONTS = fonts
    _FONT_CACHE.clear()


def font_signature():
    """Stable text identifying the font choice; part of every text-layer cache key."""
    out = []
    for kind in sorted(_FONTS):
        first = next((p for p in _FONTS[kind] if os.path.exists(p)), "default")
        out.append(kind + "=" + os.path.basename(first))
    return ";".join(out)


def font(kind, size):
    key = (kind, int(size))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    res = None
    for p in _FONTS[kind]:
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


def backdrop(ow=W, oh=H):
    key = (ow, oh)
    if key not in _BD:
        yy, xx = np.mgrid[0:oh, 0:ow].astype(np.float32)
        r = np.sqrt(((xx - ow / 2) / (ow * .62)) ** 2 + ((yy - oh * .46) / (oh * .72)) ** 2)
        v = 30 - 24 * np.clip(r, 0, 1.15) ** 1.4          # centre ~#1e, edges ~#06
        v = np.clip(v, 5, 30)
        bgr = np.stack([v * 1.02, v * 0.99, v * 0.97], -1)  # faint warm-neutral
        rng = np.random.RandomState(7)
        bgr += rng.normal(0, 0.6, bgr.shape[:2])[:, :, None]  # grain kills 8-bit banding
        _BD[key] = np.clip(bgr, 0, 255).astype(np.float32)
    return _BD[key]


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
