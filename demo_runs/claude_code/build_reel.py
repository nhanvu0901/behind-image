"""technique_reel renderer: one 4-8 s segment per EFFECTS_CATALOG record (ordered by ID), corner label on each.

Usage:
  build_reel.py still  <out_dir> ID[:t] ...          PNG stills (any machine)
  build_reel.py render <out.mp4> [--fps N --size WxH --only ID,ID]   (server)
  build_reel.py timeline <out.json>
"""
import json, os, sys, math, subprocess, time
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
from vfx import *

ASSET = os.path.join(HERE, "assets")
rng = np.random.RandomState(11)
FULL = (2193, 3000); Z_FULL = 0.172; Z_W = 1920 / 4386
MIRROR = (2220, 1790); HANDS = (2420, 2540); DOG = (2098, 5446); RUG = (2388, 4200)
R1 = (2474, 1690); R2 = (2466, 1870)

_S = {}


def S():
    if _S:
        return _S
    _S["A"] = Img(os.path.join(ASSET, "commons", "arnolfini_commons.jpg"), "arnolfini")
    _S["V"] = Img(os.path.join(ASSET, "commons", "paele_commons.jpg"), "paele")
    a2 = cv2.imread(os.path.join(ASSET, "commons", "arnolfini_commons.jpg"), cv2.IMREAD_REDUCED_COLOR_2)
    m2 = cv2.imread(os.path.join(ASSET, "masks", "couple.png"), 0)
    m2 = cv2.resize(m2, (a2.shape[1], a2.shape[0]), interpolation=cv2.INTER_LINEAR)
    _S["mask_small"] = cv2.imread(os.path.join(ASSET, "masks", "couple.png"), 0)
    _S["cut_rgb"] = Img(a2, "cut_rgb")
    _S["cut_m"] = Img(cv2.cvtColor(m2, cv2.COLOR_GRAY2BGR), "cut_mask")
    # stand-in empty-room plate: couple inpainted at 1/8 scale, softened, resized up
    sm = cv2.imread(os.path.join(ASSET, "commons", "arnolfini_commons.jpg"), cv2.IMREAD_REDUCED_COLOR_8)
    sm = cv2.resize(sm, (sm.shape[1] // 2, sm.shape[0] // 2), interpolation=cv2.INTER_AREA)
    mk = cv2.resize(_S["mask_small"], (sm.shape[1], sm.shape[0]))
    mk = cv2.dilate((mk > 60).astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
    pl = cv2.inpaint(sm, mk, 7, cv2.INPAINT_NS)
    pl = cv2.GaussianBlur(pl, (0, 0), 3.0)
    pl = (pl.astype(np.float32) * .85 + 12).clip(0, 255).astype(np.uint8)
    _S["plate"] = Img(cv2.resize(pl, (4386, 6000), interpolation=cv2.INTER_CUBIC), "plate_standin")
    _S["pdf"] = {k: cv2.imread(os.path.join(ASSET, "pdf_images", v)) for k, v in dict(
        dog="p25_x862.jpeg", pattens="p26_x864.jpeg", paele="p29_x872.jpeg", mirror="p30_x874.jpeg", hands="p31_x876.jpeg",
        orange="p32_x878.jpeg", full="p35_x883.jpeg").items()}
    _S["pdf_full"] = Img(_S["pdf"]["full"], "pdf_full")
    return _S


_T = {}


def TL(key, fn):
    if key not in _T:
        _T[key] = fn()
    return _T[key]


def U(f):
    return np.clip(f, 0, 255).astype(np.float32)


def view(img, cx, cy, z, w=W, h=H):
    return img.view(cx, cy, z, w, h)[0].astype(np.float32)


def matte(img, cx, cy, z, w=W, h=H):
    return compose_matte(img, cx, cy, z, w, h)


def cview(img, cx, cy, z, w=W, h=H):
    """view of a half-resolution cut-out image using full-resolution coordinates"""
    return img.view(cx / 2, cy / 2, z * 2, w, h)[0]


def paste(f, p, x, y):
    h, w = p.shape[:2]
    f[y:y + h, x:x + w] = p
    return f


def gray(f):
    g = cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    return np.stack([g, g, g], -1)


def txt(f, text, cx, cy, size=60, alpha=1.0, **kw):
    key = ("t", text, cx, cy, size, tuple(sorted(kw.items())))
    L = TL(key, lambda: text_layer(text, cx, cy, size, **kw))
    return L.apply(f, alpha)


def chip(f, text):
    L = TL(("chip", text), lambda: _chip(text))
    return L.apply(f, 1.0)


def _chip(text):
    ft = font("reg", 27)
    w = int(ImageDraw.Draw(Image.new("L", (10, 10))).textlength(text, font=ft)) + 36
    im = Image.new("RGBA", (w, 46), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 45), 8, fill=(0, 0, 0, 165))
    d.text((18, 6), text, font=ft, fill=(255, 255, 255, 255))
    return Layer(np.array(im), 28, 24)


def vpanel(content, pw=608, ph=1080):
    """9:16 content shown in 16:9 canvas: blurred ambient fill + centred panel with soft shadow."""
    bg = cv2.GaussianBlur(cv2.resize(content, (W, int(W * ph / pw)), interpolation=cv2.INTER_AREA), (0, 0), 38)
    y0 = (bg.shape[0] - H) // 2
    f = bg[y0:y0 + H] * 0.42
    x0 = (W - pw) // 2
    sh = np.zeros((H, W), np.float32); sh[10:H, x0 - 6:x0 + pw + 6] = 1
    sh = cv2.GaussianBlur(sh, (0, 0), 18)[:, :, None]
    f = f * (1 - .5 * sh)
    f[:, x0:x0 + pw] = content
    return f


SEG = []


def seg(id_, name, dur, ids=None):
    def deco(fn):
        SEG.append(dict(id=id_, name=name, dur=dur, fn=fn))
        return fn
    return deco


def lab(id_, name):
    return "%s %s" % (id_, name)


# =============================================================== CAMERA
@seg("CAM-01", "Push-in", 6.0)
def cam01(t, d):
    s = S(); z = 0.52 * (1.142 ** ease("linear", t / d * 0.97 + 0.03 * ease("in_quad", t / d)))
    return matte(s["A"], 2300, 3050, z)


@seg("CAM-02", "Layered relative motion", 6.0)
def cam02(t, d):
    s = S(); p = ease("inout_sine", t / d)
    bg = view(s["plate"], FULL[0], 2900, Z_W * (1.0 + 0.06 * p))
    z = Z_W * (1.0 + 0.30 * p)
    fg = cview(s["cut_rgb"], FULL[0] + 60 * p, 3000 + 380 * p, z)
    m = cview(s["cut_m"], FULL[0] + 60 * p, 3000 + 380 * p, z)[:, :, :1].astype(np.float32) / 255.0
    return bg * (1 - m) + fg.astype(np.float32) * m


@seg("CAM-03", "Pull-back", 7.0)
def cam03(t, d):
    s = S(); p = ease("in_quad", t / d)
    z = math.exp(math.log(0.62) + (math.log(0.62 / 1.31) - math.log(0.62)) * p * 0 + math.log(1 / 1.31) * p)
    z = 0.62 * (1 / 1.31) ** p
    z2 = z * (1 - ease("in_cubic", max(0, t / d - .6) / .4) * 0.0)
    cx = 2220 + (FULL[0] - 2220) * p * .5
    cy = 1900 + (2600 - 1900) * p
    return matte(s["A"], cx, cy, z2)


@seg("CAM-04", "Pan up", 6.0)
def cam04(t, d):
    s = S()
    cy = 1500 - (t / d) * (0.166 * 1080 / .90) * (6.0 / 9.4)
    return matte(s["A"], 1500, cy + 120, 0.90)


@seg("CAM-05", "Zoom and shift", 6.0)
def cam05(t, d):
    s = S(); p = t / d
    z = 0.44 * (1.51 ** (p * 6.0 / 9.4 * 1.0 + 0.0))
    z = 0.44 * (1.30 ** p)
    return matte(s["A"], 2193 + 240 * p, 2000 + 350 * p, z)


@seg("CAM-06", "Hold + label reveal", 6.0)
def cam06(t, d):
    s = S(); f = matte(s["A"], FULL[0], FULL[1], Z_FULL)
    L = TL("l06", lambda: label_layer("The Arnolfini Portrait", "Jan van Eyck, 1434"))
    return L.apply(f, window(t, 2.0, 5.2, .08, .1))


# =============================================================== TRANSITIONS
@seg("TR-01", "Dissolve", 5.0)
def tr01(t, d):
    s = S()
    a = matte(s["A"], FULL[0], FULL[1], Z_FULL * (1 + .02 * t / d))
    b = view(s["V"], 2085, 1624, 1920 / 4169)
    return blend(a, b, ease("linear", (t - 2.0) / 1.0))


@seg("TR-02", "Slide in / out", 5.5)
def tr02(t, d):
    s = S(); f = backdrop(W, H).copy()
    pw, ph, py = 900, 740, 170
    f[py:py + ph, 50:50 + pw] = matte(s["A"], FULL[0], FULL[1], .94 * ph / 6000, pw, ph)
    sl = ease("out_cubic", (t - 1.0) / .8) - ease("in_cubic", (t - 4.0) / .8)
    x = int(round(W + 10 - (W + 10 - 970) * sl))
    right = view(s["V"], 2085, 1624, max(pw / 4169, ph / 3249), pw, ph)
    x0, x1 = max(x, 0), min(x + pw, W)
    if x1 > x0:
        f[py:py + ph, x0:x1] = right[:, x0 - x:x1 - x]
    return f


@seg("TR-03", "Panel opening", 6.0)
def tr03(t, d):
    s = S()
    f = backdrop(W, H).copy()
    inner = view(s["V"], 2085, 1624, 0.30, 1200, 900)
    f[90:990, 360:1560] = inner * (0.5 + 0.5 * ease("inout_sine", (t - 1.0) / 3.0))
    th = math.radians(84 * ease("inout_cubic", (t - 1.0) / 3.2))
    big = s["A"].levels[2]    # 1/4-scale Arnolfini, split into two shutters
    bw = big.shape[1]
    halves = [cv2.resize(big[:, :bw // 2], (600, 900), interpolation=cv2.INTER_AREA), cv2.resize(big[:, bw // 2:], (600, 900), interpolation=cv2.INTER_AREA)]
    w_ = 600 * math.cos(th); q = 450 * (1 - (1 - .22 * math.sin(th)))
    quads = [np.float32([[360, 90], [360 + w_, 90 + q], [360 + w_, 990 - q], [360, 990]]),
             np.float32([[1560 - w_, 90 + q], [1560, 90], [1560, 990], [1560 - w_, 990 - q]])]
    src = np.float32([[0, 0], [599, 0], [599, 899], [0, 899]])
    for img, dst in zip(halves, quads):
        M = cv2.getPerspectiveTransform(src, dst)
        wr = cv2.warpPerspective(img, M, (W, H), flags=cv2.INTER_LINEAR)
        mk = cv2.warpPerspective(np.full((900, 600), 255, np.uint8), M, (W, H), flags=cv2.INTER_LINEAR)[:, :, None].astype(np.float32) / 255
        f = f * (1 - mk) + wr.astype(np.float32) * mk
    return f


@seg("TR-04", "Hard cut: full to crop", 5.0)
def tr04(t, d):
    s = S()
    if t < 2.4:
        return matte(s["A"], FULL[0], FULL[1], Z_FULL * (1 + .03 * t / 2.4))
    return matte(s["A"], 2420, 2480, .75 * (1 + .03 * (t - 2.4)))


# =============================================================== LAYOUT
def two_panels(s, t, left_fn, right_fn, capL, capR):
    f = backdrop(W, H).copy()
    pw, ph, py = 900, 740, 36
    f[py:py + ph, 50:50 + pw] = left_fn(t, pw, ph)
    f[py:py + ph, 970:970 + pw] = right_fn(t, pw, ph)
    txt(f, capL[0], 50 + pw // 2, py + ph + 52, 30, 1, tracking=2, sub=capL[1], subsize=26)
    txt(f, capR[0], 970 + pw // 2, py + ph + 52, 30, 1, tracking=2, sub=capR[1], subsize=26)
    return f


@seg("LAY-01", "Two panels", 5.0)
def lay01(t, d):
    s = S()
    return two_panels(s, t, lambda t, w, h: matte(s["A"], FULL[0], FULL[1], .94 * h / 6000 * (1 + .04 * t / d), w, h),
                      lambda t, w, h: view(s["V"], 2085, 1624, max(w / 4169, h / 3249) * (1 + .05 * t / d), w, h),
                      ("THE ARNOLFINI PORTRAIT", "Jan van Eyck, 1434"), ("VIRGIN AND CHILD WITH CANON VAN DER PAELE", "Jan van Eyck, 1434"))


@seg("LAY-02", "Four-tile grid", 5.5)
def lay02(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 10
    tw, th = 930, 520
    crops = [(MIRROR, .55), (HANDS, .60), (DOG, .62), ((2193, 880), .40)]
    pos = [(20, 15), (970, 15), (20, 545), (970, 545)]
    for i, ((c, z), (x, y)) in enumerate(zip(crops, pos)):
        a = ramp(t, .3 * i, .4)
        tile = view(s["A"], c[0], c[1], z * (1 + .06 * t / d), tw, th)
        f[y:y + th, x:x + tw] = f[y:y + th, x:x + tw] * (1 - a) + tile * a
    p = ramp(t, 1.8, 1.2, "inout_sine")
    for a, b in (((485, 275), (1435, 275)), ((485, 275), (485, 805)), ((1435, 275), (1435, 805)), ((485, 805), (1435, 805))):
        q = (int(a[0] + (b[0] - a[0]) * p), int(a[1] + (b[1] - a[1]) * p))
        cv2.line(f, a, q, (245, 245, 245), 3, cv2.LINE_AA)
    return f


@seg("LAY-03", "Five-column comparison", 5.0)
def lay03(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 8
    base = s["A"].levels[2]
    cols = 5; cw = 360; gap = 24; x0 = (W - cols * cw - (cols - 1) * gap) // 2
    pdf = cv2.resize(s["pdf"]["full"], (base.shape[1], base.shape[0]))
    for i in range(cols):
        im = base if i != 1 else pdf
        img = im.astype(np.float32)
        if i == 2:
            img = gray(img)
        if i == 3:
            g = gray(img)[:, :, 0]; img = np.stack([g * .62, g * .78, g * 1.0], -1)
        if i == 4:
            img = np.clip((img - 110) * 1.8 + 110, 0, 255)
        c = cv2.resize(img, (cw, 1000), interpolation=cv2.INTER_AREA)
        a = ramp(t, .25 * i, .35)
        x = x0 + i * (cw + gap)
        f[40:1040, x:x + cw] = f[40:1040, x:x + cw] * (1 - a) + c * a
    return f


@seg("LAY-04", "Inset window", 5.5)
def lay04(t, d):
    s = S()
    f = matte(s["A"], 2800, 3900, .62 * (1 + .05 * t / d))
    w_, h_ = 560, 315
    ins = view(s["V"], 2085, 2760, .30 * (1 + .35 * t / d), w_, h_)
    a = ramp(t, 1.0, .4)
    x, y = W - w_ - 70, 60
    cv2.rectangle(f, (x - 4, y - 4), (x + w_ + 4, y + h_ + 4), (240, 240, 240), 4)
    f[y:y + h_, x:x + w_] = f[y:y + h_, x:x + w_] * (1 - a) + ins * a
    return f


def _bgs(s):
    return [lambda: view(s["V"], 2085, 1624, 1920 / 4169),
            lambda: view(s["A"], 2220, 1790, .9),
            lambda: np.full((H, W, 3), (40, 40, 150), np.float32) * np.linspace(.6, 1.2, W)[None, :, None],
            lambda: view(s["A"], 2300, 4400, .5)]


@seg("LAY-05", "Subject held, background changes", 6.0)
def lay05(t, d):
    s = S(); n = 4; seg_t = d / n
    i = min(int(t // seg_t), n - 1); j = (i + 1) % n
    p = ease("inout_sine", (t - i * seg_t - seg_t * .6) / (seg_t * .4)) if i < n - 1 else 0
    bgs = _bgs(s)
    bg = blend(bgs[i]() * .55, bgs[j]() * .55, p) if i < n - 1 else bgs[i]() * .55
    z = 0.172 * 1.07
    fg = cview(s["cut_rgb"], FULL[0], 3000, z).astype(np.float32)
    m = cview(s["cut_m"], FULL[0], 3000, z)[:, :, :1].astype(np.float32) / 255
    return bg * (1 - m) + fg * m


@seg("LAY-06", "Translucent vertical strips", 5.5)
def lay06(t, d):
    s = S(); f = backdrop(W, H).copy()
    base = view(s["A"], FULL[0], 2200, Z_W * 0.75)
    f = f * 0.4 + base * 0.6
    for i in range(6):
        w_ = 260
        x = int(((i * 330 + 120 * math.sin(t * .9 + i)) % (W - w_)))
        c = (2000 + 400 * i, 1200 + 700 * i)
        strip = view(s["A"], c[0], c[1], .50 * (1 + .1 * math.sin(t + i)), w_, H)
        a = .72 * ramp(t, .15 * i, .5)
        f[:, x:x + w_] = f[:, x:x + w_] * (1 - a) + strip * a
    return f


@seg("LAY-07", "Grid with translucent overlay object", 5.5)
def lay07(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 10
    for k, (c, z) in enumerate([(HANDS, .6), (DOG, .6), ((2193, 880), .42), (RUG, .55)]):
        x, y = (k % 2) * 960, (k // 2) * 540
        f[y:y + 540, x:x + 960] = view(s["A"], c[0], c[1], z, 960, 540)
    ov = view(s["A"], MIRROR[0], MIRROR[1], 1.55 + .1 * math.sin(t))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    m = np.clip(1 - (np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2) - 360) / 40, 0, 1)[:, :, None] * .55 * ramp(t, 1.0, .6)
    return f * (1 - m) + ov * m


@seg("LAY-08", "Repeated symmetric motif", 5.0)
def lay08(t, d):
    s = S(); z = .75 * (1 + .06 * math.sin(t))
    tile = view(s["A"], MIRROR[0], MIRROR[1] + 20, z, 480, 540)
    top = np.concatenate([tile, tile[:, ::-1]], 1)
    rowA = np.concatenate([top, top[:, ::-1]], 1)
    f = np.concatenate([rowA, rowA[::-1]], 0)
    return cv2.resize(f, (W, H))


# =============================================================== HIGHLIGHT
@seg("HI-01", "Spotlight", 6.0)
def hi01(t, d):
    s = S(); cz = .55 + .06 * t / d
    f = matte(s["A"], 2300, 2300, cz)
    sx, sy = s["A"].to_screen(HANDS[0], HANDS[1], 2300, 2300, cz)
    return spotlight(f, sx, sy, 380 * cz + 60, 280 * cz + 60, ramp(t, 1.5, .5, "inout_sine"))


@seg("HI-02", "Hiding figures then group reveal", 7.0)
def hi02(t, d):
    s = S(); z = Z_W * .78
    cy = 2700
    bg = view(s["plate"], FULL[0], cy, z) * .9
    out = bg
    for k, (xs, ys, t0) in enumerate([(-1, 0, 1.4), (1, 0, 2.6)]):
        p = ease("out_cubic", (t - t0) / 1.4); a = ramp(t, t0, 1.0)
        shift = xs * (1 - p) * 900
        fg = cview(s["cut_rgb"], FULL[0], cy, z).astype(np.float32)
        m = cview(s["cut_m"], FULL[0], cy, z)[:, :, :1].astype(np.float32) / 255
        cols = np.arange(W)[None, :, None]
        sel = (cols < W / 2 + 120) if k == 0 else (cols >= W / 2 - 120)
        mm = m * sel
        M = np.float32([[1, 0, shift], [0, 1, 0]])
        fg2 = cv2.warpAffine(fg, M, (W, H)); mm2 = cv2.warpAffine(mm[:, :, 0], M, (W, H))[:, :, None]
        out = out * (1 - mm2 * a) + fg2 * mm2 * a
    return out


@seg("HI-03", "Colour kept on subject, rest grey", 5.5)
def hi03(t, d):
    s = S(); z = Z_W * .8
    f = view(s["A"], FULL[0], 2900, z)
    m = cview(s["cut_m"], FULL[0], 2900, z)[:, :, :1].astype(np.float32) / 255
    a = ramp(t, 1.0, 1.0, "inout_sine")
    g = blend(f, gray(f) * .75, a)
    return g * (1 - m) + f * m


# =============================================================== ANNOTATION
@seg("AN-01", "Circle draw", 5.5)
def an01(t, d):
    s = S(); z = .85; c = (2190, 2300)
    f = matte(s["A"], c[0], c[1], z)
    for k, (p, r) in enumerate(((HANDS, 230), ((1130, 1980), 190))):
        x, y = s["A"].to_screen(p[0], p[1], c[0], c[1], z)
        t0 = 1.0 + .5 * k
        f = ring(f, x, y, r * z, ramp(t, t0, .5, "out_quad"), .75 * window(t, t0, 4.6, .05, .4), 13)
    return f


@seg("AN-02", "Object outline", 6.0)
def an02(t, d):
    s = S(); z = Z_W * .8
    f = view(s["A"], FULL[0], 2900, z) * .85
    m = s["mask_small"]
    cs, _ = cv2.findContours((m > 128).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cs = sorted(cs, key=lambda c: -len(c))[:2]
    ov = np.zeros((H, W), np.uint8)
    p = ramp(t, 1.0, 3.0, "inout_sine")
    for c in cs:
        pts = c[:, 0, :].astype(np.float32) * (4386 / m.shape[1])
        sc = np.stack([W / 2 + (pts[:, 0] - FULL[0]) * z, H / 2 + (pts[:, 1] - 2900) * z], 1)
        n = int(len(sc) * p)
        if n > 2:
            cv2.polylines(ov, [sc[:n].astype(np.int32)], False, 255, 6, cv2.LINE_AA)
    a = (ov.astype(np.float32) / 255)[:, :, None]
    return f * (1 - a) + 255 * a


@seg("AN-03", "Perspective rays", 6.0)
def an03(t, d):
    s = S(); z = Z_W * .8
    f = view(s["A"], FULL[0], 2900, z) * .8
    vp = (W / 2 + (2193 - FULL[0]) * z + 40, H / 2 + (2350 - 2900) * z)
    src_pts = [(0, H * .98), (W * .12, H), (W * .3, H), (W * .62, H), (W * .83, H), (W * .98, H * .9), (0, H * .6), (W, H * .55), (W * .98, H * .12)]
    ov = np.zeros((H, W), np.uint8)
    for i, p in enumerate(src_pts):
        pr = ramp(t, .6 + .35 * i, .45, "out_quad")
        q = (int(p[0] + (vp[0] - p[0]) * pr), int(p[1] + (vp[1] - p[1]) * pr))
        cv2.line(ov, (int(p[0]), int(p[1])), q, 255, 4, cv2.LINE_AA)
    a = (ov.astype(np.float32) / 255)[:, :, None] * .9
    return f * (1 - a) + 255 * a


def _map(t, route=True):
    f = np.zeros((H, W, 3), np.float32) + (150, 150, 150)
    r = np.random.RandomState(5)
    for _ in range(22):
        c = (int(r.randint(0, W)), int(r.randint(0, H)))
        cv2.ellipse(f, c, (int(r.randint(160, 420)), int(r.randint(80, 220))), int(r.randint(0, 180)), 0, 360, (172, 170, 168), -1, cv2.LINE_AA)
    f = cv2.GaussianBlur(f, (0, 0), 4)
    for gx in range(0, W, 160):
        cv2.line(f, (gx, 0), (gx, H), (140, 140, 140), 1)
    for gy in range(0, H, 160):
        cv2.line(f, (0, gy), (W, gy), (140, 140, 140), 1)
    a, b = (520, 330), (1360, 790)
    ctrl = (860, 220)
    pts = np.array([[(1 - u) ** 2 * a[0] + 2 * (1 - u) * u * ctrl[0] + u * u * b[0], (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * ctrl[1] + u * u * b[1]] for u in np.linspace(0, 1, 120)])
    p = ramp(t, 1.4, 2.4, "inout_sine")
    n = int(len(pts) * p)
    if route and n > 2:
        for i in range(0, n - 1, 2):
            cv2.line(f, tuple(pts[i].astype(int)), tuple(pts[min(i + 1, n - 1)].astype(int)), (40, 40, 210), 7, cv2.LINE_AA)
    for k, (c, name) in enumerate(((a, "BRUGES"), (b, "LUCCA"))):
        cv2.circle(f, c, 22, (255, 255, 255), 4, cv2.LINE_AA)
        txt(f, name, c[0], c[1] - 60, 36, ramp(t, .4 + 1.2 * k, .3), tracking=4)
    return f, pts, n


@seg("AN-04", "Map circle and arrow (stand-in map)", 6.0)
def an04(t, d):
    f, pts, n = _map(t)
    if n > 30:
        e = pts[n - 1]; v = pts[n - 1] - pts[n - 6]; v /= np.linalg.norm(v) + 1e-6
        l = np.array([-v[1], v[0]])
        tri = np.array([e + v * 26, e - v * 18 + l * 18, e - v * 18 - l * 18], np.int32)
        cv2.fillConvexPoly(f, tri, (40, 40, 210), cv2.LINE_AA)
    return f


@seg("AN-05", "Dimension ruler", 6.0)
def an05(t, d):
    zz = Z_FULL * .84
    s = S(); f = matte(s["A"], FULL[0], FULL[1], zz)
    x0 = W / 2 - 2193 * zz; x1 = W / 2 + 2193 * zz; y0 = H / 2 - 3000 * zz; y1 = H / 2 + 3000 * zz
    p = ramp(t, 1.0, .25)
    c = (255, 255, 255)
    def ln(a, b):
        cv2.line(f, (int(a[0]), int(a[1])), (int(a[0] + (b[0] - a[0]) * p), int(a[1] + (b[1] - a[1]) * p)), c, 4, cv2.LINE_AA)
    ln((x0, y0 - 24), (x1, y0 - 24)); ln((x0 - 40, y0), (x0 - 40, y1))
    for (a, b) in (((x0, y0 - 38), (x0, y0 - 10)), ((x1, y0 - 38), (x1, y0 - 10)), ((x0 - 54, y0), (x0 - 26, y0)), ((x0 - 54, y1), (x0 - 26, y1))):
        if p > .9:
            cv2.line(f, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), c, 4, cv2.LINE_AA)
    txt(f, "60 cm", int(W / 2), int(y0 - 58), 46, p, kind="sans_bold", tracking=1)
    txt(f, "82 cm", int(x0 - 150), int(H / 2), 46, p, kind="sans_bold", tracking=1)
    txt(f, "OIL ON OAK PANEL", int(x1 + 330), int(y0 + 60), 44, p, kind="sans_bold", tracking=1)
    return f


@seg("AN-06", "Grid and geometric regions", 6.0)
def an06(t, d):
    s = S(); z = Z_W * .8
    f = view(s["A"], FULL[0], 2900, z) * .85
    ov = np.zeros((H, W, 3), np.float32)
    p = ramp(t, .8, 1.2)
    for k in (1, 2):
        cv2.line(f, (int(W * k / 3), 0), (int(W * k / 3), int(H * p)), (255, 255, 255), 2, cv2.LINE_AA)
        cv2.line(f, (0, int(H * k / 3)), (int(W * p), int(H * k / 3)), (255, 255, 255), 2, cv2.LINE_AA)
    tri = np.array([[W * .5, H * .06], [W * .26, H * .96], [W * .76, H * .96]], np.int32)
    cv2.fillConvexPoly(ov, tri, (60, 160, 255))
    a = .28 * ramp(t, 2.2, .8)
    return f * (1 - a) + ov * a + 0 * f


@seg("AN-07", "Dot field densifying", 6.5)
def an07(t, d):
    s = S(); base = view(s["A"], FULL[0], 2900, Z_W * .8)
    r = np.random.RandomState(2)
    n_final = 9000
    f = np.zeros((H, W, 3), np.float32) + 245
    p = ease("inout_sine", t / (d * .8))
    n = int(60 + (n_final - 60) * p ** 1.5)
    rad = max(3.0, 70 * (1 - p) ** 1.6 + 3)
    xs = r.randint(0, W, n_final); ys = r.randint(0, H, n_final)
    ov = f.copy()
    for i in range(n):
        c = np.clip(base[ys[i], xs[i]] * 1.8 + 12, 0, 255)
        cv2.circle(ov, (int(xs[i]), int(ys[i])), int(rad), (float(c[0]), float(c[1]), float(c[2])), -1, cv2.LINE_AA)
    mix = ramp(t, d * .78, d * .2)
    return blend(ov, base, mix)


# =============================================================== TYPOGRAPHY
@seg("TXT-01", "Chapter title card", 4.5)
def txt01(t, d):
    s = S(); bg = TL("bgmirror", lambda: blurred_bg(cv2.imread(os.path.join(ASSET, "pdf_images", "p30_x874.jpeg")), sigma=34, dark=.45))
    f = bg.copy()
    return txt(f, "THE MIRROR", W // 2, int(H * .5), 84, ramp(t, .4, .5), tracking=14)


@seg("TXT-02", "Sliding italic text", 5.5)
def txt02(t, d):
    s = S(); f = view(s["A"], FULL[0], 2300, Z_W * .85) * .55
    for i, line in enumerate(["“Every detail has a story…”", "“Richly worked, quietly staged…”", "“A room built to impress…”"]):
        x = W * 1.6 - (t - .3 * i) * 520 - i * 160
        f = txt(f, line, int(x), int(H * (.3 + .2 * i)), 76, 1.0, kind="serif_it", tracking=1)
    return f


# =============================================================== STATIC
@seg("STATIC-01", "Black matte (designed gallery matte)", 4.5)
def st01(t, d):
    return matte(S()["A"], FULL[0], FULL[1], Z_FULL * (1 + .015 * t / d))


@seg("STATIC-02", "Source label", 5.0)
def st02(t, d):
    s = S(); f = view(s["A"], 2193, 2300, Z_W * .9)
    L = TL("src", lambda: _srclabel())
    return L.apply(f, ramp(t, 1.0, .3))


def _srclabel():
    im = Image.new("RGBA", (900, 36), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((0, 2), "Jan van Eyck, The Arnolfini Portrait, 1434", font=font("reg", 24), fill=(255, 255, 255, 235))
    return Layer(np.array(im), 36, H - 62)


@seg("STATIC-04", "Quote over image", 5.5)
def st04(t, d):
    s = S(); f = view(s["A"], 2193, 4200, Z_W * .75) * .38
    return txt(f, "“A memorial, not a wedding record.”", W // 2, H // 2, 70, ramp(t, 1.0, .6), kind="serif_it", tracking=1)


@seg("STATIC-05", "Interviewee name tag (placeholder)", 5.0)
def st05(t, d):
    s = S(); f = view(s["A"], 1233, 1266, .75)
    L = TL("tag", lambda: label_layer("Speaker Name", "Curator, Example Museum (placeholder)", y0=.76, h=140))
    return L.apply(f, window(t, 1.0, 4.4, .1, .1))


@seg("STATIC-06", "Map with route", 5.5)
def st06(t, d):
    return _map(t)[0]


@seg("STATIC-07", "Multi-cell circular diagram", 6.0)
def st07(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 12
    c = (W // 2, H // 2); R = 470
    crops = [(DOG, .8, "DOG"), (MIRROR, .8, "MIRROR"), ((1500, 2100), .7, "HAND"), ((2200, 800), .8, "CHANDELIER"), ((4300, 4900), .8, "FUR"), ((2388, 4200), .8, "RUG")]
    for i, (cc, z, name) in enumerate(crops):
        a = ramp(t, .3 + .35 * i, .4)
        ang0 = math.radians(60 * i - 90); ang1 = math.radians(60 * (i + 1) - 90)
        ov = view(s["A"], cc[0], cc[1], z)
        mk = np.zeros((H, W), np.uint8)
        pts = [c] + [(int(c[0] + R * math.cos(x)), int(c[1] + R * math.sin(x))) for x in np.linspace(ang0, ang1, 24)]
        cv2.fillConvexPoly(mk, np.array(pts, np.int32), 255, cv2.LINE_AA)
        m = (cv2.erode(mk, np.ones((5, 5), np.uint8)).astype(np.float32) / 255)[:, :, None] * a
        f = f * (1 - m) + ov * m
        mid = (ang0 + ang1) / 2
        f = txt(f, name, int(c[0] + (R + 130) * math.cos(mid)), int(c[1] + (R + 70) * math.sin(mid)), 34, a, tracking=5)
    cv2.circle(f, c, R, (255, 255, 255), 3, cv2.LINE_AA)
    return f


@seg("STATIC-08", "Name labels on figures", 5.5)
def st08(t, d):
    s = S(); z = Z_W * .78
    f = view(s["A"], FULL[0], 2300, z)
    for k, (nm, p, off) in enumerate((("GIOVANNI DI NICOLAO ARNOLFINI (?)", (1233, 1300), (60, -330)), ("COSTANZA TRENTA (?)", (3500, 1500), (-30, -300)))):
        a = ramp(t, 1.0 + .8 * k, .4)
        x, y = s["A"].to_screen(p[0], p[1], FULL[0], 2300, z)
        tx, ty = x + off[0], y + off[1]
        tx = min(max(tx, 420), W - 420); ty = 110 + 80 * k
        cv2.line(f, (int(tx), int(ty + 26)), (int(x), int(y)), (255, 255, 255), 2, cv2.LINE_AA)
        f = txt(f, nm, int(tx), int(ty), 32, a, tracking=3)
    return f


@seg("STATIC-09", "Year centred over image", 4.5)
def st09(t, d):
    s = S(); bg = TL("bgyear", lambda: blurred_bg(cv2.imread(os.path.join(ASSET, "commons", "arnolfini_commons.jpg"), cv2.IMREAD_REDUCED_COLOR_4), sigma=26, dark=.5, center=(.5, .55)))
    return txt(bg.copy(), "1434", W // 2, H // 2, 190, ramp(t, .5, .5), tracking=16)


# =============================================================== DIAGRAMS
@seg("DIA-01", "Grid + projecting rays (room perspective)", 6.5)
def dia01(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 8
    gl = view(s["A"], MIRROR[0] - 300, MIRROR[1] + 300, .5, 900, 900)
    f[90:990, 60:960] = gl
    for k in range(7):
        x = 60 + k * 150; cv2.line(f, (x, 90), (x, 990), (255, 255, 255), 1, cv2.LINE_AA)
        y = 90 + k * 150; cv2.line(f, (60, y), (960, y), (255, 255, 255), 1, cv2.LINE_AA)
    for k, ch in enumerate("ABCDEF"):
        f = txt(f, ch, 60 + k * 150 + 75, 70, 28, 1, tracking=0)
    # right: oblique ray diagram
    ox, oy = 1020, 900
    cv2.line(f, (ox, oy), (1860, oy), (255, 255, 255), 2, cv2.LINE_AA)
    cv2.line(f, (ox, oy), (ox, 200), (255, 255, 255), 2, cv2.LINE_AA)
    p = ramp(t, 1.0, 3.5, "inout_sine")
    for i in range(7):
        ex = ox + 120 + i * 105
        e = (1840, 230 + i * 105)
        q = (int(ox + (e[0] - ox) * p), int(300 + (e[1] - 300) * p))
        cv2.line(f, (ox, 300), q, (60, 190, 255), 3, cv2.LINE_AA)
    return f


@seg("DIA-02", "Two views of one object (stand-in)", 6.0)
def dia02(t, d):
    s = S(); a = view(s["A"], MIRROR[0], MIRROR[1], .9, 900, 900)
    p = ease("inout_cubic", (t - 1.5) / 2.5)
    sh = .62 * p + 1e-3
    src = np.float32([[0, 0], [899, 0], [899, 899], [0, 899]])
    dst = np.float32([[0, 450 * (1 - sh) * .5], [899 * (1 - .55 * p), 450 * (1 - sh)], [899 * (1 - .55 * p), 899 - 450 * (1 - sh)], [0, 899 - 450 * (1 - sh) * .5]])
    M = cv2.getPerspectiveTransform(src, dst)
    b = cv2.warpPerspective(a, M, (900, 900), flags=cv2.INTER_LINEAR)
    f = backdrop(W, H).copy()
    f[90:990, 60:960] = a
    f[90:990, 960:1860] = b * 1.0 + backdrop(900, 900) * (b.sum(-1, keepdims=True) == 0)
    f = txt(f, "FRONTAL", 510, 1040, 28, 1, tracking=5)
    f = txt(f, "OBLIQUE", 1410, 1040, 28, p, tracking=5)
    return f


@seg("DIA-03", "Cross-section and light rays (schematic)", 6.5)
def dia03(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 14
    layers = [("OAK PANEL", (60, 90, 120), 200), ("CHALK GROUND", (230, 230, 235), 70), ("IMPRIMATURA", (120, 150, 170), 60), ("PAINT LAYERS", (40, 120, 40), 160), ("VARNISH", (90, 190, 220), 50)]
    y = 380; ys = []
    for nm, c, h_ in layers:
        a = ramp(t, .3 * len(ys), .4)
        cv2.rectangle(f, (200, y), (1720, y + h_), tuple(float(v) * a + 14 * (1 - a) for v in c), -1)
        f = txt(f, nm, 960, y + h_ // 2 + 6, 28, a, tracking=5, color=(0, 0, 0) if c[0] > 200 else (255, 255, 255), shadow=False)
        ys.append(y); y += h_
    top = ys[-1]
    for i in range(3):
        p = ramp(t, 2.2 + .6 * i, 1.0)
        x0 = 520 + i * 360
        pts = [(x0, 120), (x0 + 100, 520 + 0), (x0 + 200, 120)]
        q1 = (int(x0 + (x0 + 100 - x0) * min(p * 2, 1)), int(120 + (700 - 120) * min(p * 2, 1)))
        cv2.line(f, (x0, 120), q1, (40, 190, 255), 6, cv2.LINE_AA)
        if p > .5:
            q = (int(x0 + 100 + 100 * (p - .5) * 2), int(700 - 580 * (p - .5) * 2))
            cv2.line(f, (x0 + 100, 700), q, (40, 190, 255), 6, cv2.LINE_AA)
    return f


@seg("DIA-04", "Figure and separated pieces", 6.0)
def dia04(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 6
    p = ease("inout_cubic", (t - 1.0) / 2.0)
    z = Z_W * .45
    fg = cview(s["cut_rgb"], FULL[0], 3000, Z_FULL * .86).astype(np.float32)
    m = cview(s["cut_m"], FULL[0], 3000, Z_FULL * .86)[:, :, :1].astype(np.float32) / 255
    f = f * (1 - m) + fg * m
    for img, c, zz, pos in ((s["A"], DOG, .5, (1450, 620)), (s["A"], MIRROR, .45, (1450, 80)), (s["A"], (2200, 820), .55, (180, 80))):
        tw = 380
        piece = view(img, c[0], c[1], zz, tw, tw)
        yy, xx = np.mgrid[0:tw, 0:tw].astype(np.float32)
        circ = (np.sqrt((xx - tw / 2) ** 2 + (yy - tw / 2) ** 2) < tw / 2 - 2).astype(np.float32)[:, :, None]
        x = int(W / 2 + (pos[0] - W / 2) * p); y = int(H / 2 + (pos[1] - H / 2) * p)
        reg = f[y:y + tw, x:x + tw]
        f[y:y + tw, x:x + tw] = reg * (1 - circ * p) + piece * circ * p
    return f


@seg("DIA-05", "Silhouette process", 6.0)
def dia05(t, d):
    s = S(); z = Z_W * .8
    base = view(s["A"], FULL[0], 2900, z)
    m = cview(s["cut_m"], FULL[0], 2900, z)[:, :, :1].astype(np.float32) / 255
    sil = np.zeros_like(base) + 12
    sil = sil * (1 - m) + np.array([60, 190, 255], np.float32) * m
    e = cv2.Canny((m[:, :, 0] * 255).astype(np.uint8), 50, 150)
    e = cv2.dilate(e, np.ones((3, 3), np.uint8)).astype(np.float32)[:, :, None] / 255
    outl = np.zeros_like(base) + 12; outl = outl * (1 - e) + 255 * e
    a = ramp(t, 1.5, 1.0); b = ramp(t, 3.2, 1.2)
    return blend(blend(sil, outl, a), base, b)


@seg("DIA-06", "Room model + UV-style image (simulated)", 6.5)
def dia06(t, d):
    s = S(); f = backdrop(W, H).copy()
    # simple isometric room diagram, left
    ox, oy = 480, 560
    p = ramp(t, .4, 1.4)
    floor = np.array([[ox, oy + 120], [ox + 330, oy - 40], [ox + 0, oy - 200], [ox - 330, oy - 40]], np.float32)
    cv2.polylines(f, [floor.astype(np.int32)], True, (230, 230, 230), 3, cv2.LINE_AA)
    for a_, b_ in zip(floor, floor):
        pass
    wall = np.array([floor[2], floor[3], floor[3] + (0, -330), floor[2] + (0, -330)], np.int32)
    wall2 = np.array([floor[2], floor[1], floor[1] + (0, -330), floor[2] + (0, -330)], np.int32)
    cv2.polylines(f, [wall, wall2], True, (230, 230, 230), 3, cv2.LINE_AA)
    cv2.rectangle(f, (ox - 70, oy - 440), (ox + 20, oy - 290), (60, 190, 255), -1)
    f = txt(f, "ROOM MODEL", ox, oy + 230, 30, p, tracking=5)
    # simulated UV: false colour of crop, right
    c = view(s["A"], MIRROR[0], MIRROR[1], .8, 900, 760)
    g = gray(c)[:, :, 0].astype(np.uint8)
    fc = cv2.applyColorMap(cv2.equalizeHist(g), cv2.COLORMAP_BONE if False else cv2.COLORMAP_OCEAN).astype(np.float32)
    uv = blend(c, fc, ramp(t, 2.0, 1.0))
    f[140:900, 940:1840] = uv
    f = txt(f, "SIMULATED UV-STYLE VIEW", 1390, 950, 30, ramp(t, 2.2, .5), tracking=5)
    return f


@seg("DIA-07", "Optical diagram (convex mirror)", 6.0)
def dia07(t, d):
    s = S(); f = np.zeros((H, W, 3), np.float32) + 10
    c = (1300, 540)
    p = ramp(t, .6, 3.0, "inout_sine")
    # convex mirror arc
    cv2.ellipse(f, (c[0] + 330, c[1]), (330, 330), 0, 150, 210, (230, 230, 230), 8, cv2.LINE_AA)
    # object (arrow) left
    cv2.arrowedLine(f, (330, 780), (330, 380), (60, 190, 255), 8, cv2.LINE_AA, 0, .12)
    for i, y in enumerate((380, 540, 700)):
        q0 = (330, y); hit = (int(c[0] - (330 - math.sqrt(max(330 ** 2 - (y - c[1]) ** 2, 1)))), y)
        e1 = (int(q0[0] + (hit[0] - q0[0]) * min(p * 2, 1)), y)
        cv2.line(f, q0, e1, (255, 255, 255), 3, cv2.LINE_AA)
        if p > .5:
            k = (p - .5) * 2
            ex = int(hit[0] - 600 * k); ey = int(y + (y - c[1]) * .35 * k * 2)
            cv2.line(f, hit, (ex, ey), (40, 190, 255), 3, cv2.LINE_AA)
    f = txt(f, "CONVEX MIRROR: WIDE VIEW, SMALL IMAGE", W // 2, 960, 34, ramp(t, 1.2, .5), tracking=4)
    return f


# =============================================================== COMPARISON
@seg("CMP-01", "Grey and colour side by side", 5.0)
def cmp01(t, d):
    s = S(); f = backdrop(W, H).copy()
    a = view(s["A"], 1233, 1300, .75, 930, 800)
    f[140:940, 20:950] = gray(a)
    f[140:940, 970:1900] = blend(gray(a), a, ramp(t, 1.0, .8))
    f = txt(f, "GREYSCALE", 485, 1000, 30, 1, tracking=6)
    return txt(f, "COLOUR", 1435, 1000, 30, 1, tracking=6)


@seg("CMP-02", "Stages vs finished (simulated stages)", 6.0)
def cmp02(t, d):
    s = S(); f = backdrop(W, H).copy()
    c = view(s["A"], MIRROR[0], MIRROR[1], .9, 600, 600)
    stages = [cv2.GaussianBlur(gray(c), (0, 0), 14) * .9, cv2.GaussianBlur(c, (0, 0), 5), c]
    for i in range(2):
        pass
    for i, im in enumerate(stages[:3]):
        a = ramp(t, .5 + .9 * i, .5)
        f[40 + i * 340:40 + i * 340 + 320, 80:80 + 320] = f[40 + i * 340:40 + i * 340 + 320, 80:80 + 320] * (1 - a) + cv2.resize(im, (320, 320)) * a
    fin = view(s["A"], MIRROR[0], MIRROR[1], 1.45, 1000, 1000)[40:1040 - 40]
    f[40:1040, 520:1520] = view(s["A"], MIRROR[0], MIRROR[1], 1.45, 1000, 1000)
    return f


@seg("CMP-03", "White / sepia / colour versions", 5.5)
def cmp03(t, d):
    s = S(); f = backdrop(W, H).copy()
    a = view(s["A"], 2300, 2300, .5, 610, 900)
    g = gray(a)[:, :, 0]
    versions = [np.stack([g, g, g], -1) * 1.0 + 60, np.stack([g * .55, g * .75, g * 1.0], -1), a]
    for i, im in enumerate(versions):
        al = ramp(t, .3 + .6 * i, .5)
        x = 60 + i * 620
        f[90:990, x:x + 610] = f[90:990, x:x + 610] * (1 - al) + np.clip(im, 0, 255) * al
    return f


@seg("CMP-04", "Colour blocks beside detail", 5.5)
def cmp04(t, d):
    s = S(); f = backdrop(W, H).copy()
    a = view(s["A"], 2300, 3300, .6, 900, 900)
    f[90:990, 40:940] = a
    nb = int(8 + 24 * ramp(t, .8, 2.0))
    small = cv2.resize(a, (nb, nb), interpolation=cv2.INTER_AREA)
    mosaic = cv2.resize(small, (900, 900), interpolation=cv2.INTER_NEAREST)
    f[90:990, 980:1880] = mosaic
    return f


@seg("CMP-05", "Two colour states (print vs scan)", 6.0)
def cmp05(t, d):
    s = S(); z = Z_W * .8
    a = view(s["A"], FULL[0], 2900, z)
    pdf = s["pdf_full"]
    b = view(pdf, pdf.w / 2, pdf.h * .48, 1920 / pdf.w * .95 * (4386 / 4386))
    b = view(pdf, pdf.w / 2, pdf.h * 2900 / 6000, z * 4386 / pdf.w)
    x = int(W * (.1 + .8 * ease("inout_sine", (t - 1.0) / 3.5)))
    f = a.copy(); f[:, :x] = b[:, :x]
    cv2.line(f, (x, 0), (x, H), (255, 255, 255), 3, cv2.LINE_AA)
    return f


# =============================================================== FOOTAGE (stand-in)
@seg("FOOT-01", "Material cards and palette (stand-in)", 6.0)
def foot01(t, d):
    s = S(); f = backdrop(W, H).copy()
    items = [("GREEN WOOL", (2300, 3900), (40, 120, 40)), ("SQUIRREL FUR", (3000, 3700), (190, 200, 205)), ("BLUE DRESS", (3350, 2640), (170, 110, 50)), ("RED BED", (3900, 1300), (40, 40, 150))]
    for i, (nm, c, col) in enumerate(items):
        a = ramp(t, .4 + .7 * i, .5)
        x = 80 + i * 460 + int((1 - ease("out_cubic", (t - .4 - .7 * i) / .8)) * 300)
        x = min(x, W - 420)
        tile = view(s["A"], c[0], c[1], .8, 420, 520)
        f[170:690, x:x + 420] = f[170:690, x:x + 420] * (1 - a) + tile * a
        sw = np.zeros((120, 420, 3), np.float32) + col
        f[720:840, x:x + 420] = f[720:840, x:x + 420] * (1 - a) + sw * a
        f = txt(f, nm, x + 210, 890, 28, a, tracking=4)
    return f


# =============================================================== SHORTS (vertical 9:16 panel in 16:9)
@seg("SHORT-01", "Three horizontal strips (vertical)", 6.0)
def sh01(t, d):
    s = S(); c = np.zeros((1080, 608, 3), np.float32)
    srcs = [(MIRROR, .62), (HANDS, .62), (DOG, .62)]
    for i, (cc, z) in enumerate(srcs):
        sh = int(t / 2.0)
        cc2, z2 = srcs[(i + sh) % 3]
        a = ease("inout_sine", (t % 2.0 - 1.4) / .6)
        n2 = srcs[(i + sh + 1) % 3]
        v = blend(view(s["A"], cc2[0], cc2[1], z2 * (1 + .04 * t), 608, 356), view(s["A"], n2[0][0], n2[0][1], n2[1], 608, 356), a)
        c[i * 362:i * 362 + 356] = v
    return vpanel(c)


@seg("SHORT-02", "Changing view (vertical)", 6.0)
def sh02(t, d):
    s = S(); a = view(s["A"], MIRROR[0], MIRROR[1], .6, 608, 1080)
    p = ease("inout_cubic", (t - 1.5) / 3.0)
    src = np.float32([[0, 0], [607, 0], [607, 1079], [0, 1079]])
    k = .5 * p
    dst = np.float32([[0, 540 * k], [607 * (1 - .45 * k), 540 * k * 1.8], [607 * (1 - .45 * k), 1079 - 540 * k * 1.8], [0, 1079 - 540 * k]])
    M = cv2.getPerspectiveTransform(src, dst)
    b = cv2.warpPerspective(a, M, (608, 1080), borderMode=cv2.BORDER_REPLICATE)
    return vpanel(b)


@seg("SHORT-03", "Large type changes (vertical)", 6.0)
def sh03(t, d):
    s = S(); c = view(s["A"], 2193, 2300, .62, 608, 1080) * .5
    words = ["LOOK", "CLOSER", "1434"]
    i = min(int(t // 2), 2)
    f0 = vpanel(c)
    a = min(1, (t % 2) / .2) * (1 - ease("linear", ((t % 2) - 1.75) / .25))
    return txt(f0, words[i], W // 2, H // 2, 130, a, kind="bold", tracking=6)


@seg("SHORT-04", "Yellow label box (vertical)", 5.5)
def sh04(t, d):
    s = S(); c = view(s["A"], 1233, 1500, .62, 608, 1080)
    cv2.rectangle(c, (30, 930), (578, 1010), (30, 205, 245), -1)
    p = vpanel(c)
    p = txt(p, "DETAIL LABEL", W // 2, 935, 36, ramp(t, 1.0, .3), tracking=3, color=(20, 20, 20), shadow=False)
    return p


@seg("SHORT-05", "Colour wheel from palette (vertical)", 6.0)
def sh05(t, d):
    s = S(); c = np.zeros((1080, 608, 3), np.float32) + 14
    base = s["A"].levels[3]
    px = cv2.resize(base, (64, 64), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
    km = cv2.kmeans(px, 8, None, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 20, .5), 3, cv2.KMEANS_PP_CENTERS)[2]
    cc = (304, 540)
    for i in range(8):
        a = ramp(t, .3 * i, .4)
        cv2.ellipse(c, cc, (250, 250), 0, 45 * i - 90, 45 * i - 90 + 45 * a, tuple(float(v) for v in km[i]), -1, cv2.LINE_AA)
    cv2.circle(c, cc, 100, (14, 14, 14), -1)
    return vpanel(c)


ORDER = [x["id"] for x in SEG]


def corner_frame(entry, t):
    f = entry["fn"](t, entry["dur"])
    f = chip(np.asarray(f, np.float32).copy(), lab(entry["id"], entry["name"]))
    return to_u8(f)


def main():
    mode = sys.argv[1]
    S()
    if mode == "still":
        out = sys.argv[2]; os.makedirs(out, exist_ok=True)
        for a in sys.argv[3:]:
            i, _, tt = a.partition(":")
            e = next(x for x in SEG if x["id"] == i)
            tt = float(tt) if tt else e["dur"] * .6
            cv2.imwrite(os.path.join(out, "%s_%.1f.png" % (i, tt)), corner_frame(e, tt))
    elif mode == "timeline":
        t = 0; rows = []
        for e in SEG:
            rows.append(dict(id=e["id"], name=e["name"], t0=round(t, 2), t1=round(t + e["dur"], 2))); t += e["dur"]
        json.dump(rows, open(sys.argv[2], "w"), indent=1)
    elif mode == "render":
        outp = sys.argv[2]; fps = 30.0; size = (W, H); only = None
        a = sys.argv[3:]
        for i, x in enumerate(a):
            if x == "--fps": fps = float(a[i + 1])
            if x == "--size": size = tuple(int(v) for v in a[i + 1].split("x"))
            if x == "--only": only = a[i + 1].split(",")
        crf = "15" if size == (W, H) else "27"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % size, "-r", str(fps), "-i", "-",
                              "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p", "-threads", "4", outp], stdin=subprocess.PIPE)
        ts = time.time(); tot = 0; tcur = 0.0; rows = []
        for e in SEG:
            if only and e["id"] not in only:
                continue
            n = int(round(e["dur"] * fps)); t1 = time.time()
            for i in range(n):
                fr = corner_frame(e, i / fps)
                if size != (W, H):
                    fr = cv2.resize(fr, size, interpolation=cv2.INTER_AREA)
                p.stdin.write(fr.tobytes())
            rows.append(dict(id=e["id"], name=e["name"], t0=round(tcur, 2), t1=round(tcur + e["dur"], 2), render_s=round(time.time() - t1, 1)))
            tcur += e["dur"]; tot += n
            print("%s done  total %d frames  %.0fs" % (e["id"], tot, time.time() - ts), flush=True)
        p.stdin.close(); p.wait()
        json.dump(rows, open(os.path.splitext(outp)[0] + "_segments.json", "w"), indent=1)
        print("RENDER_DONE %d frames %.1fs" % (tot, time.time() - ts), flush=True)


if __name__ == "__main__":
    main()
