"""v2 long-form episode renderer. Shots are anchored to phrases of the narration (forced-alignment times in timing2.json).
No subtitles are burned in.

  build_v2.py still  <timing2.json> <out_dir> t1 t2 ...
  build_v2.py render <timing2.json> <out.mp4> --t0 S --t1 S [--size WxH --fps N]
  build_v2.py timeline <timing2.json> <shots.json>
"""
import json, os, sys, math, re, subprocess, time
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
from vfx import *

ASSET = os.path.join(HERE, "assets")
CTX = os.path.join(ASSET, "context")
ZW = 1920 / 4386          # painting width fills the frame
ZF = 0.172                # whole painting height = 95.5 % of frame
FULL = (2193, 3000)
MIRROR = (2220, 1790); HANDS = (2420, 2540); DOG = (2098, 5446); RUG = (2388, 4200)
INSCR = (2220, 1390)
R1 = (2474, 1690); R2 = (2466, 1870)
LIT = (1856, 420); SNUF = (2490, 500)
ORANGE = (470, 2704)
PATTENS = (250, 5300); BOOTS = (1200, 5150)
LION = (2553, 2300); STM = (2824, 1190); BRUSH = (2700, 1560)
AMBER = (1810, 1650); HAT = (1246, 1000); TABARD = (1266, 2666)
FURSLEEVE = (3500, 2700); BLUESL = (2900, 2330); RUFFLES = (3500, 4000)
BEDP = (3500, 1100); COSFACE = (3500, 1500); GIOFACE = (1233, 1300)
SPOT_FLOOR = 0.20

_IMG = {}


def IM(key):
    if key not in _IMG:
        path = {"A": "commons/arnolfini_commons.jpg", "V": "commons/paele_commons.jpg"}.get(key)
        p = os.path.join(ASSET, path) if path else os.path.join(CTX, key + ".jpg")
        _IMG[key] = Img(p, key)
    return _IMG[key]


# ----------------------------------------------------------------------------- timeline
def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


class TL:
    def __init__(self, path):
        d = json.load(open(path))
        self.d = d
        self.words = []
        for b in d["beats"]:
            for w in b["words"]:
                self.words.append((norm(w["w"]), w["s"], w["e"]))
        self.cards = d["cards"]
        self.end = d["end"]
        self.beats = d["beats"]

    def find(self, phrase, nth=0):
        p = [norm(x) for x in phrase.split()]
        hits = 0
        for i in range(len(self.words) - len(p) + 1):
            if all(self.words[i + k][0] == p[k] for k in range(len(p))):
                if hits == nth:
                    return i
                hits += 1
        raise KeyError(phrase)

    def at(self, phrase, nth=0, off=0.0, wi=0):
        return self.words[self.find(phrase, nth) + wi][1] + off

    def after(self, phrase, nth=0, off=0.0):
        i = self.find(phrase, nth) + len(phrase.split()) - 1
        return self.words[i][2] + off

    def chapter_start(self, name):
        for b in self.beats:
            if b["chapter"] == name:
                return b["start"]

    def chapter_end(self, name):
        e = None
        for b in self.beats:
            if b["chapter"] == name:
                e = b["end"]
        return e

    def card(self, text):
        for c in self.cards:
            if c["text"] == text:
                return c


# ----------------------------------------------------------------------------- overlays
def label_strip(title, sub=None):
    """channel detail label at the measured position (y 79-93 %), single line for the main painting, two lines for other works"""
    return TLC(("lab", title, sub), lambda: label_layer(title.upper(), sub.upper() if sub else None, y0=.79, h=151, x_text=.07))


_TLC = {}


def TLC(key, fn):
    if key not in _TLC:
        _TLC[key] = fn()
    return _TLC[key]


class Lbl:
    def __init__(self, title, sub, t0, dur=3.2):
        self.layer = label_strip(title, sub); self.t0 = t0; self.t1 = t0 + dur
        self.info = {"label": title + (" / " + sub if sub else ""), "t": round(t0, 2)}

    def __call__(self, f, t, cx, cy, z, img):
        return self.layer.apply(f, window(t, self.t0, self.t1, .1, .12))


class Spot:
    def __init__(self, pt, rx, ry, t0, t1, floor=SPOT_FLOOR, ramp_in=.5, ramp_out=.5):
        self.pt, self.rx, self.ry, self.t0, self.t1, self.floor, self.ri, self.ro = pt, rx, ry, t0, t1, floor, ramp_in, ramp_out
        self.info = {"spotlight": [list(pt), self.rx, self.ry], "t0": round(t0, 2), "t1": round(t1, 2), "floor": floor}

    def __call__(self, f, t, cx, cy, z, img):
        a = ramp(t, self.t0, self.ri, "inout_sine") * (1 - ramp(t, self.t1, self.ro, "inout_sine"))
        if a <= 0:
            return f
        pt = self.pt(t) if callable(self.pt) else self.pt
        sx, sy = img.to_screen(pt[0], pt[1], cx, cy, z)
        return spotlight(f, sx, sy, self.rx * z, self.ry * z, a, self.floor)


class RingOv:
    def __init__(self, pt, r_src, t0, hold=2.0, fade=.4, draw=.5):
        self.pt, self.r, self.t0, self.hold, self.fade, self.draw = pt, r_src, t0, hold, fade, draw
        self.info = {"ring": list(pt), "r_src": r_src, "t0": round(t0, 2), "draw_s": draw, "hold_s": hold, "fade_s": fade}

    def __call__(self, f, t, cx, cy, z, img):
        if t < self.t0:
            return f
        prog = ramp(t, self.t0, self.draw, "out_quad")
        al = .75 * (1 - ramp(t, self.t0 + self.draw + self.hold, self.fade))
        if al <= 0:
            return f
        x, y = img.to_screen(self.pt[0], self.pt[1], cx, cy, z)
        return ring(f, x, y, self.r * z, prog, al, max(6, 0.007 * W))


class ScreenText:
    """plain white text (no strip) attached to a source point (recap labels) or fixed on screen"""
    def __init__(self, text, t0, t1, pt=None, screen=None, size=44, fin=.1, fout=.15):
        self.layer = TLC(("st", text, size), lambda: text_layer(text, W // 2, H // 2, size, "reg", 3, shadow=True))
        self.t0, self.t1, self.pt, self.screen, self.fin, self.fout = t0, t1, pt, screen, fin, fout
        self.info = {"text": text, "t0": round(t0, 2)}

    def __call__(self, f, t, cx, cy, z, img):
        e = window(t, self.t0, self.t1, self.fin, self.fout)
        if e <= 0:
            return f
        if self.pt is not None:
            x, y = img.to_screen(self.pt[0], self.pt[1], cx, cy, z)
        else:
            x, y = self.screen
        return self.layer.apply(f, e, x - W // 2, y - H // 2)


class DimOv:
    """AN-05 dimension annotation: 60 / 82 cm lines and OIL ON OAK PANEL, pops within 0.2 s"""
    def __init__(self, t0, t1, zz):
        self.t0, self.t1, self.zz = t0, t1, zz
        self.info = {"annotation": "AN-05 82 cm x 60 cm, OIL ON OAK PANEL", "t0": round(t0, 2), "t1": round(t1, 2)}
        xh, yh = 2193 * zz, 3000 * zz
        self.x0, self.x1, self.y0, self.y1 = W / 2 - xh, W / 2 + xh, H / 2 - yh, H / 2 + yh
        self.L60 = TLC("d60", lambda: text_layer("60 cm", W // 2, int(self.y0 - 62), 46, "sans_bold", 1))
        self.L82 = TLC("d82", lambda: text_layer("82 cm", int(self.x0 - 150), H // 2, 46, "sans_bold", 1))
        self.LOIL = TLC("doil", lambda: text_layer("OIL ON OAK PANEL", int(self.x1 + 330), int(self.y0 + 60), 44, "sans_bold", 1))

    def __call__(self, f, t, cx, cy, z, img):
        e = ramp(t, self.t0, .2) * (1 - ramp(t, self.t1, .2))
        if e <= 0:
            return f
        ov = np.zeros((H, W), np.uint8)
        c = 255
        cv2.line(ov, (int(self.x0), int(self.y0 - 24)), (int(self.x1), int(self.y0 - 24)), c, 4, cv2.LINE_AA)
        cv2.line(ov, (int(self.x0 - 40), int(self.y0)), (int(self.x0 - 40), int(self.y1)), c, 4, cv2.LINE_AA)
        for a, b in (((self.x0, self.y0 - 38), (self.x0, self.y0 - 10)), ((self.x1, self.y0 - 38), (self.x1, self.y0 - 10)),
                     ((self.x0 - 54, self.y0), (self.x0 - 26, self.y0)), ((self.x0 - 54, self.y1), (self.x0 - 26, self.y1))):
            cv2.line(ov, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), c, 4, cv2.LINE_AA)
        a = (ov.astype(np.float32) / 255 * e)[:, :, None]
        f = f * (1 - a) + 255 * a
        for L in (self.L60, self.L82, self.LOIL):
            L.apply(f, e)
        return f


class Years:
    def __init__(self, items):
        self.items = [(TLC(("yr", s, x), lambda s=s, x=x, sub=sub: text_layer(s, x, int(H * .46), 120, "reg", 10, sub=sub, subsize=30)), t0, t1) for s, sub, x, t0, t1 in items]
        self.info = {"years": [(i[0], round(i[2], 2)) for i in items]}

    def __call__(self, f, t, cx, cy, z, img):
        for L, t0, t1 in self.items:
            L.apply(f, window(t, t0, t1, .2, .25))
        return f


# ----------------------------------------------------------------------------- shot builders
def img_fit(key, k=0.94):
    im = IM(key)
    return k * H / im.h


def painting_shot(t0, t1, keys, overlays=(), key="A", desc="", ids=(), words="", params=None):
    cam = Cam(keys)
    ovs = list(overlays)

    def fn(t):
        cx, cy, z = cam.at(t)
        img = IM(key)
        f = compose_matte(img, cx, cy, z)
        for o in ovs:
            f = o(f, t, cx, cy, z, img)
        return f
    meta = dict(effect=desc, ids=list(ids), image=key, params=dict(params or {}, overlays=[o.info for o in ovs if hasattr(o, "info")]), words=words)
    return dict(t0=t0, t1=t1, fn=fn, **meta)


def still_shot(t0, t1, key, title, sub, push=1.06, center=None, z0=None, desc="context still (two-line label)", words="", ids=("STATIC-02", "TR-04"), cam_keys=None, overlays=(), hold=4.0):
    """context still held `hold` s (reference: stills in a sequence are held 4.0 s); the rest of the narration span returns to the painting on the matte"""
    im = IM(key)
    base = img_fit(key)
    c = center or (im.w / 2, im.h / 2)
    tend = t1 if (hold is None or cam_keys is not None or t1 - t0 <= hold + 2.0) else t0 + hold
    keys = cam_keys or [(t0, c[0], c[1], z0 or base, "linear"), (tend, c[0], c[1], (z0 or base) * push, "linear")]
    lb = Lbl(title, sub, t0 + .6, dur=min(3.2, max(2.5, tend - t0 - .8)))
    out = [painting_shot(t0, tend, keys, [lb] + list(overlays), key=key, desc=desc, ids=ids, words=words, params={"hold_s": round(tend - t0, 2)})]
    if tend < t1 - 1e-6:
        out.append(painting_shot(tend, t1, [(tend, FULL[0], FULL[1], ZF * .97, "linear"), (t1, FULL[0], FULL[1], ZF * 1.04, "linear")], [], desc="back to the painting after the still", ids=["STATIC-01"], words=words))
    return out


def card_shot(t0, t1, text):
    L = TLC(("card", text), lambda: _card_layer(text))

    def fn(t):
        f = np.zeros((H, W, 3), np.float32)
        e = window(t, t0 + .2, t0 + 1.7, .1, .1)
        return L.apply(f, e)
    return dict(t0=t0, t1=t1, fn=fn, effect="chapter card", ids=["TXT-01"], image="", params={"text": text, "bg": "black", "pop": "0.1 s at +0.2 s, leaves at +1.7 s", "y": "88 %"}, words="")


def _card_layer(text):
    size = 70
    d = ImageDraw.Draw(Image.new("L", (10, 10)))
    while True:
        ft = font("reg", size)
        w = sum(d.textlength(c, font=ft) for c in text) + 9 * (len(text) - 1)
        if w <= 0.50 * W or size < 30:
            break
        size -= 2
    return text_layer(text, W // 2, int(H * .88), size, "reg", 9, shadow=False)


def title_card_shot(t0, t1, bgimg):
    bg = TLC("tc_bg", lambda: blurred_bg(cv2.imread(os.path.join(ASSET, "commons", "arnolfini_commons.jpg"), cv2.IMREAD_REDUCED_COLOR_4), sigma=30, dark=.42))
    l1 = TLC("tc1", lambda: text_layer("THE ARNOLFINI PORTRAIT", W // 2, int(H * .455), 78, "reg", 11))
    l2 = TLC("tc2", lambda: text_layer("JAN VAN EYCK", W // 2, int(H * .585), 38, "reg", 10))
    l3 = TLC("tc3", lambda: text_layer("1434", W // 2, int(H * .65), 34, "reg", 10))

    def fn(t):
        e = ramp(t, t0, .35, "out_quad")
        f = bg.copy()
        l1.apply(f, e); hline(f, W // 2, int(H * .535), 200, 2, .75 * e); l2.apply(f, e); l3.apply(f, e)
        return f
    return dict(t0=t0, t1=t1, fn=fn, effect="title card (blurred artwork)", ids=["TXT-01"], image="arnolfini_commons (blurred)", params={"blur_sigma": 30, "fade_in_s": .35}, words="")


def map_shot(t0, t1, tdraw):
    def fn(t):
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
        a, b = (520, 330), (1360, 790); ctrl = (860, 220)
        pts = np.array([[(1 - u) ** 2 * a[0] + 2 * (1 - u) * u * ctrl[0] + u * u * b[0], (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * ctrl[1] + u * u * b[1]] for u in np.linspace(0, 1, 120)])
        p = ramp(t, tdraw, 2.4, "inout_sine"); n = int(len(pts) * p)
        for i in range(0, n - 1, 2):
            cv2.line(f, tuple(pts[i].astype(int)), tuple(pts[min(i + 1, n - 1)].astype(int)), (40, 40, 210), 7, cv2.LINE_AA)
        for k, (c, name) in enumerate(((a, "BRUGES"), (b, "LUCCA"))):
            cv2.circle(f, c, 22, (255, 255, 255), 4, cv2.LINE_AA)
            TLC(("mp", name), lambda name=name, c=c: text_layer(name, c[0], c[1] - 60, 38, "reg", 4)).apply(f, ramp(t, t0 + .5 + 1.5 * k, .3))
        if n > 30:
            e = pts[n - 1]; v = pts[n - 1] - pts[n - 6]; v /= np.linalg.norm(v) + 1e-6; l = np.array([-v[1], v[0]])
            cv2.fillConvexPoly(f, np.array([e + v * 26, e - v * 18 + l * 18, e - v * 18 - l * 18], np.int32), (40, 40, 210), cv2.LINE_AA)
        return f
    return dict(t0=t0, t1=t1, fn=fn, effect="route map (procedural stand-in)", ids=["AN-04", "STATIC-06"], image="procedural map (stand-in)", params={"route_draw_s": 2.4}, words="")


def dia_mirror_shot(t0, t1):
    def fn(t):
        f = np.zeros((H, W, 3), np.float32) + 10
        c = (1300, 540); p = ramp(t, t0 + .5, 2.6, "inout_sine")
        cv2.ellipse(f, (c[0] + 330, c[1]), (330, 330), 0, 150, 210, (230, 230, 230), 8, cv2.LINE_AA)
        cv2.arrowedLine(f, (330, 780), (330, 380), (60, 190, 255), 8, cv2.LINE_AA, 0, .12)
        for y in (380, 540, 700):
            q0 = (330, y); hit = (int(c[0] - (330 - math.sqrt(max(330 ** 2 - (y - c[1]) ** 2, 1)))), y)
            e1 = (int(q0[0] + (hit[0] - q0[0]) * min(p * 2, 1)), y)
            cv2.line(f, q0, e1, (255, 255, 255), 3, cv2.LINE_AA)
            if p > .5:
                k = (p - .5) * 2; cv2.line(f, hit, (int(hit[0] - 600 * k), int(y + (y - c[1]) * .7 * k)), (40, 190, 255), 3, cv2.LINE_AA)
        TLC("dm", lambda: text_layer("CONVEX MIRROR: WIDE VIEW, SMALL IMAGE", W // 2, 960, 34, "reg", 4)).apply(f, ramp(t, t0 + 1.0, .4))
        return f
    return dict(t0=t0, t1=t1, fn=fn, effect="convex mirror optical diagram (stand-in)", ids=["DIA-07"], image="procedural diagram", params={}, words="")


def split_shot(t0, t1, t_slide, t_push):
    pw, ph, py = 900, 740, 36
    xl, xr = 50, 970
    capL = TLC("spL", lambda: text_layer("THE ARNOLFINI PORTRAIT", xl + pw // 2, py + ph + 52, 30, "reg", 2, sub="JAN VAN EYCK, 1434", subsize=26))
    capR = TLC("spR", lambda: text_layer("VIRGIN AND CHILD WITH CANON VAN DER PAELE", xr + pw // 2, py + ph + 52, 30, "reg", 2, sub="JAN VAN EYCK, 1434", subsize=26))
    zl = 0.94 * ph / 6000; zv = max(pw / 4169, ph / 3249)
    camL = Cam([(t0, FULL[0], FULL[1], zl, "linear"), (t_push, FULL[0], FULL[1], zl, "inout_cubic"), (t1, RUG[0], RUG[1], .30, "linear")])
    camR = Cam([(t0, 4169 / 2, 3249 / 2, zv, "linear"), (t_push, 4169 / 2, 3249 / 2, zv, "inout_cubic"), (t1, 2085, 2780, .55, "linear")])

    def fn(t):
        f = backdrop(W, H).copy()
        cx, cy, z = camL.at(t)
        f[py:py + ph, xl:xl + pw] = compose_matte(IM("A"), cx, cy, z, pw, ph)
        sl = ease("out_cubic", (t - t_slide - .05) / .85)
        x = int(round(W + 10 - (W + 10 - xr) * sl))
        cx, cy, z = camR.at(t)
        right = IM("V").view(cx, cy, z, pw, ph)[0].astype(np.float32)
        x0, x1 = max(x, 0), min(x + pw, W)
        if x1 > x0:
            f[py:py + ph, x0:x1] = right[:, x0 - x:x1 - x]
        capL.apply(f, ramp(t, t_slide, .2)); capR.apply(f, ramp(t, t_slide + .75, .25))
        return f
    return dict(t0=t0, t1=t1, fn=fn, effect="split-screen comparison, slide-in, synchronous push-ins", ids=["LAY-01", "TR-02", "CAM-05"], image="arnolfini_commons + paele_commons",
                params={"slide_s": .85, "push_L": "0.1097->0.30", "push_R": "%.3f->0.55" % zv}, words="")


# ----------------------------------------------------------------------------- the storyboard
def build(T):
    S = []
    add = lambda x: S.extend(x if isinstance(x, list) else [x])
    tt = T.at
    END = T.end
    first = T.beats[0]["start"]
    # ---------------- cold open
    tpb = tt("But look at what is actually") - 1.0
    z_end = ZF * 0.97
    tdim0 = max(tpb + 18.0, tt("It is small"))
    t_mirror = tt("Notice the mirror")
    add(painting_shot(0, tpb, [(0, 2193, 1750, ZW * 1.0, "linear"), (tpb, 2193, 1750, ZW * 1.14, "linear")], [], desc="cold open: slow push-in on couple", ids=["CAM-01"], words="Most people ... look at what is", params={"push": "1.14x, linear"}))
    add(painting_shot(tpb, tdim0, [(tpb, 2193, 1750, ZW * 1.14, "out_quad"), (tpb + 18.0, FULL[0], FULL[1], z_end, "linear"), (tdim0, FULL[0], FULL[1], z_end, "linear")], [],
                      desc="opening pull-back 3.0x over 18 s ease-out_quad", ids=["CAM-03", "STATIC-01"], words="But look at what is ... finished the Arnolfini Portrait", params={"from_z": ZW * 1.14, "to_z": z_end, "ratio": round(ZW * 1.14 / z_end, 2), "dur_s": 18, "ease": "out_cubic"}))
    zz = z_end * 0.88
    t82 = max(tdim0 + .5, tt("eighty-two") - .3)
    add(painting_shot(tdim0, t_mirror, [(tdim0, FULL[0], FULL[1], zz, "linear"), (t_mirror, FULL[0], FULL[1], zz * 1.03, "linear")], [DimOv(t82, t82 + 4.5, zz)],
                      desc="dimension annotation (AN-05) on the matte painting", ids=["AN-05", "STATIC-01"], words="It is small ... eighty-two centimetres tall and sixty wide", params={"hold_s": 4.5}))
    t_lat = tt("and the Latin words")
    t_wit = tt("A painter does not usually")
    add(painting_shot(t_mirror, t_wit, [(t_mirror, 2220, 1650, .72, "inout_cubic"), (t_lat, 2220, 1620, .86, "inout_cubic"), (t_wit, INSCR[0], INSCR[1] + 40, 1.25, "linear")],
                      [Spot(MIRROR, 440, 440, tt("Notice the mirror", wi=2) - .12, t_lat - .2), Spot(INSCR, 420, 120, tt("and the Latin words", wi=2) - .12, t_wit, ramp_in=.5, ramp_out=.4), Lbl("Latin inscription", None, tt("and the Latin words", wi=2))],
                      desc="push to mirror then inscription with spotlights", ids=["CAM-05", "HI-01"], words="Notice the mirror ... the Latin words", params={"floor": SPOT_FLOOR}))
    t3 = tt("Over the next few minutes")
    add(painting_shot(t_wit, t3, [(t_wit, INSCR[0], INSCR[1] + 40, 1.25, "inout_sine"), (t3, MIRROR[0], MIRROR[1], 1.0, "linear")], [], desc="slow drift from the inscription to the mirror", ids=["CAM-05"], words="A painter does not usually sign ... what exactly was he witnessing"))
    tc0 = T.card("__title__")
    ta_, tb_ = tt("what the documents and historians"), tt("and how all of that might be read")
    add(painting_shot(t3, ta_, [(t3, FULL[0], FULL[1], ZF * .9, "linear"), (ta_, FULL[0], FULL[1], ZF * .95, "linear")], [], desc="hold on matte: what we can see", ids=["STATIC-01"], words="Over the next few minutes ... what we can see with our own eyes"))
    add(painting_shot(ta_, tb_, [(ta_, HANDS[0], HANDS[1], .55, "linear"), (tb_, HANDS[0], HANDS[1], .65, "linear")], [], desc="hard cut to the joined hands: what the documents say", ids=["TR-04", "CAM-05"], words="what the documents and historians actually tell us"))
    add(painting_shot(tb_, tc0["t0"], [(tb_, MIRROR[0], MIRROR[1], .8, "linear"), (tc0["t0"], MIRROR[0], MIRROR[1], .9, "linear")], [], desc="hard cut to the mirror: how it might be read", ids=["TR-04", "CAM-05"], words="and how all of that might be read, bearing in mind that no painting has ever held only one meaning"))
    add(title_card_shot(tc0["t0"], tc0["t1"], None))
    # ---------------- chapter 1: merchant city
    c = T.card("THE MERCHANT CITY"); add(card_shot(c["t0"], c["t1"], c["text"]))
    cs = T.chapter_start("THE MERCHANT CITY"); t_inter = tt("Bruges was an international crossroads"); t_luc = tt("One of those families came from Lucca")
    add(still_shot(cs, t_inter, "bruges", "Grote Markt, Bruges", "Etching, Rijksmuseum", push=1.12, hold=None, desc="Bruges still (two-line label)", words="To understand the couple ... Flanders"))
    add(map_shot(t_inter, tt("As the merchants got richer"), t_luc))
    t_m3 = tt("As the merchants got richer"); t_j = tt("Jan van Eyck was a trailblazer")
    add(painting_shot(t_m3, t_j, [(t_m3, FULL[0], FULL[1], ZF * .95, "linear"), (t_j, FULL[0], FULL[1], ZF * 1.04, "linear")], [], desc="back to the painting", ids=["STATIC-01"], words="As the merchants got richer"))
    t_gh = tt("where in 1432"); t_yet = tt("yet he kept accepting"); t_so = tt("So a portrait by Van Eyck")
    add(still_shot(t_j, t_gh, "blue_cap", "Man in a Blue Chaperon", "Jan van Eyck, c.1430", push=1.05, words="Jan van Eyck was a trailblazer ..."))
    g = IM("ghent"); gz = img_fit("ghent")
    add(still_shot(t_gh, t_yet, "ghent", "Ghent Altarpiece", "Jan van Eyck, 1432", cam_keys=[(t_gh, g.w / 2, g.h / 2, gz, "linear"), (t_gh + 1.5, g.w / 2, g.h / 2, gz, "inout_cubic"), (t_yet, g.w * 0.60, g.h * 0.45, gz * 2.4, "linear")], desc="Ghent still with zoom-and-shift (CAM-05)", ids=["CAM-05", "STATIC-02"], words="where in 1432 he finished the enormous Ghent Altarpiece"))
    add(still_shot(t_yet, t_so, "turban", "Man in a Red Turban", "Jan van Eyck, 1433", push=1.06, words="yet he kept accepting private clients"))
    add(painting_shot(t_so, T.chapter_end("THE MERCHANT CITY") + .25, [(t_so, FULL[0], FULL[1], ZF * 1.0, "linear"), (T.chapter_end("THE MERCHANT CITY") + .25, FULL[0], FULL[1], ZF * 1.08, "linear")], [], desc="status symbol: painting on matte", ids=["STATIC-01"], words="So a portrait by Van Eyck was far more than a likeness"))
    # ---------------- chapter 2: arnolfinis
    c = T.card("THE ARNOLFINIS"); add(card_shot(c["t0"], c["t1"], c["text"]))
    cs = T.chapter_start("THE ARNOLFINIS"); t_dead = tt("The marriage produced no recorded children")
    add(painting_shot(cs, t_dead, [(cs, FULL[0], FULL[1], ZF * .95, "linear"), (t_dead, FULL[0], FULL[1], ZF * 1.05, "linear")],
                      [ScreenText("GIOVANNI DI NICOLAO ARNOLFINI (?)", tt("Giovanni di Nicolao"), tt("Giovanni di Nicolao") + 3.6, pt=GIOFACE, size=34), ScreenText("COSTANZA TRENTA (?)", tt("Costanza Trenta"), tt("Costanza Trenta") + 3.4, pt=COSFACE, size=34)],
                      desc="name labels near the figures", ids=["STATIC-08", "STATIC-01"], words="Who bought this one ... Costanza Trenta"))
    t_hon = tt("We should be honest"); t_sep = tt("and Van Eyck painted a separate portrait"); t_prob = tt("The names are probable")
    add(painting_shot(t_dead, t_hon, [(t_dead, FULL[0], FULL[1], ZF * 1.0, "linear"), (t_hon, FULL[0], FULL[1], ZF * 1.04, "linear")],
                      [Years([("1433", "COSTANZA DIES", int(W * .17), tt("dead by 1433", wi=2) - .1, tt("a full year before") + 1.0), ("1434", "PANEL FINISHED", int(W * .83), tt("finished this panel"), tt("finished this panel") + 3.0)])],
                      desc="year captions on matte", ids=["STATIC-09", "STATIC-01"], words="Costanza was dead by 1433 ... finished this panel"))
    add(painting_shot(t_hon, t_sep, [(t_hon, FULL[0], FULL[1], ZF * 1.0, "linear"), (t_sep, FULL[0], FULL[1], ZF * 1.05, "linear")], [], desc="matte hold, honest limits", ids=["STATIC-01"], words="We should be honest about the limits"))
    t_cert = tt("What is certain")
    add(still_shot(t_sep, t_cert, "giovanni_berlin", "Man in a Red Chaperon", "Jan van Eyck, c.1438", push=1.07, words="a separate portrait of a man from this family, now in Berlin; the names are probable, not proven"))
    t_many = tt("For many years the picture"); t_fig = tt("with the figures in the mirror")
    t_pu = min(t_cert + 11.0, t_fig - 3.0)
    add(painting_shot(t_cert, t_pu, [(t_cert, 2300, 4650, .50, "linear"), (t_pu, 2300, 3300, .50, "linear")], [], desc="pan up the painting (CAM-04)", ids=["CAM-04"], words="What is certain is how unusual the picture is", params={"pan": "legs to waist, linear, 11 s"}))
    add(painting_shot(t_pu, t_fig, [(t_pu, GIOFACE[0] + 600, GIOFACE[1] + 400, .62, "linear"), (t_fig, GIOFACE[0] + 600, GIOFACE[1] + 460, .70, "linear")], [], desc="hard cut to the faces (TR-04)", ids=["TR-04", "CAM-05"], words="two people who were neither royalty nor nobility, in their own home"))
    t_but = tt("But without any evidence")
    add(painting_shot(t_fig, t_but, [(t_fig, 2193, 1700, ZW * .9, "inout_cubic"), (t_but, MIRROR[0], MIRROR[1], 1.0, "inout_cubic")], [Spot(MIRROR, 430, 430, tt("with the figures in the mirror", wi=4) - .12, t_but)], desc="mirror spotlight: witnesses", ids=["HI-01", "CAM-05"], words="with the figures in the mirror acting as witnesses"))
    t_dog = tt("Look down at the dog"); t_tomb = tt("Yet on late medieval tombs")
    add(painting_shot(t_but, t_dog, [(t_but, FULL[0], FULL[1], ZF * 1.0, "linear"), (t_dog, FULL[0], FULL[1], ZF * 1.06, "linear")], [], desc="memorial painting for Costanza: matte", ids=["STATIC-01"], words="But without any evidence ... more convincing of the two"))
    add(painting_shot(t_dog, t_tomb, [(t_dog, DOG[0], DOG[1] - 260, .62, "inout_cubic"), (t_tomb, DOG[0], DOG[1] - 80, .95, "linear")], [RingOv(DOG, 330, tt("Look down at the dog", wi=4) - .05), Lbl("Dog at her feet", None, tt("Look down at the dog", wi=4))], desc="dog detail with circle (AN-01) and label", ids=["CAM-05", "AN-01", "STATIC-02"], words="Look down at the dog at her feet"))
    t_port = tt("Portraits of the dead")
    tomb = IM("tomb"); tz = img_fit("tomb")
    add(still_shot(t_tomb, t_port, "tomb", "Tomb of Mary of Burgundy, Bruges", "Late 15th century", cam_keys=[(t_tomb, tomb.w / 2, tomb.h / 2, tz * 1.0, "linear"), (t_tomb + 2.0, tomb.w / 2, tomb.h / 2, tz * 1.0, "inout_cubic"), (t_port, 4300, 1050, tz * 2.6, "linear")], desc="tomb still with push to the dog (CAM-05)", ids=["CAM-05", "STATIC-02"], words="Yet on late medieval tombs, sculptors often placed a dog by a woman's feet"))
    t_what = tt("Whatever else it does")
    add(painting_shot(t_port, t_what, [(t_port, COSFACE[0], COSFACE[1] + 250, .90, "inout_sine"), (t_what, COSFACE[0], COSFACE[1] + 300, 1.0, "linear")], [], desc="push on Costanza's face: portraits of the dead", ids=["CAM-05"], words="Portraits of the dead were not unusual either"))
    t_end2 = T.chapter_end("THE ARNOLFINIS") + .25
    add(painting_shot(t_what, t_end2, [(t_what, COSFACE[0], COSFACE[1] + 300, 1.0, "inout_cubic"), (t_end2, FULL[0], FULL[1], ZF, "linear")], [], desc="pull-back to the matte", ids=["CAM-03"], words="Whatever else it does, this double portrait ..."))
    # ---------------- chapter 3: fashions and fabrics
    c = T.card("FASHIONS AND FABRICS"); add(card_shot(c["t0"], c["t1"], c["text"]))
    cs = T.chapter_start("FASHIONS AND FABRICS"); t_col = tt("The colour alone"); t_lin = tt("Now look at the lining"); t_bl = tt("Notice how carefully she handles blue")
    add(still_shot(cs, cs + 4.0, "rogier", "Portrait of a Woman", "Rogier van der Weyden, c.1435", push=1.05, words="Clothes shape identity, then as now"))
    add(painting_shot(cs + 4.0, t_col, [(cs + 4.0, FULL[0], FULL[1], ZF * .95, "in_quad"), (cs + 8.9, 2300, 3100, ZW * .98, "linear"), (t_col, 2900, 3500, .62, "inout_cubic")], [Lbl("Green wool gown", None, tt("that green dress", wi=1))],
                      desc="matte to fill-width 1.59x/4.9 s ease-in (as ref), then push to the dress with label", ids=["CAM-01", "CAM-05", "STATIC-02"], words="and here every thread is a statement ... that green dress", params={"ratio": round(ZW * .98 / (ZF * .95), 2), "dur_s": 4.9}))
    add(painting_shot(t_col, t_lin, [(t_col, 2900, 3500, .62, "linear"), (t_lin, 2900, 4650, .56, "linear")], [], desc="long pan down the dress (CAM-04)", ids=["CAM-04"], words="The colour alone is an announcement", params={"pan": "linear, ~180 px/s ref"}))
    add(painting_shot(t_lin, t_bl, [(t_lin, FURSLEEVE[0], FURSLEEVE[1] + 100, .85, "inout_cubic"), (t_bl, FURSLEEVE[0], FURSLEEVE[1] + 160, .95, "linear")], [Lbl("Miniver lining", None, tt("Now look at the lining", wi=4))], desc="fur lining crop with label", ids=["CAM-05", "STATIC-02"], words="Now look at the lining ... two thousand"))
    t_gio = tt("Giovanni is dressed with the same care"); t_straw = tt("his hat is straw"); t_vel = tt("and his velvet tabard"); t_boots = tt("His boots are")
    add(painting_shot(t_bl, t_gio, [(t_bl, BLUESL[0], BLUESL[1], .9, "linear"), (t_gio, BLUESL[0] - 50, BLUESL[1] + 30, 1.0, "linear")], [Lbl("Blue underdress", None, tt("of blue underdress", wi=2))], desc="blue underdress with label", ids=["CAM-05", "STATIC-02"], words="Notice how carefully she handles blue"))
    add(painting_shot(t_gio, t_straw, [(t_gio, 1250, 2200, .36, "linear"), (t_straw, 1250, 2000, .42, "linear")], [], desc="Giovanni dressed with the same care", ids=["CAM-05", "TR-04"], words="Giovanni is dressed with the same care. His clothes are plum and black"))
    add(painting_shot(t_straw, t_vel, [(t_straw, HAT[0], HAT[1] + 80, .78, "linear"), (t_vel, HAT[0], HAT[1] + 100, .86, "linear")], [Lbl("Straw hat", None, tt("his hat is straw", wi=3))], desc="hat crop with label (hard cut)", ids=["TR-04", "STATIC-02"], words="his hat is straw, woven in tiny plaits"))
    add(painting_shot(t_vel, t_boots, [(t_vel, TABARD[0], TABARD[1] - 500, .62, "linear"), (t_boots, TABARD[0], TABARD[1] - 350, .70, "linear")], [Lbl("Silk velvet tabard", None, tt("and his velvet tabard", wi=2))], desc="tabard crop with label (hard cut)", ids=["TR-04", "STATIC-02"], words="and his velvet tabard ... pine martens from Russia"))
    t_over = tt("And in the lower left corner"); t_disc = tt("An abandoned pair of shoes")
    add(painting_shot(t_boots, t_over, [(t_boots, BOOTS[0], BOOTS[1], .62, "linear"), (t_over, BOOTS[0] - 120, BOOTS[1] + 60, .72, "linear")], [], desc="boots crop", ids=["CAM-05", "TR-04"], words="His boots are such supple leather"))
    add(painting_shot(t_over, t_disc, [(t_over, 1010, PATTENS[1] + 80, .95, "linear"), (t_disc, 1010, PATTENS[1] + 150, 1.05, "linear")], [Spot((PATTENS[0] + 60, PATTENS[1] + 120), 480, 300, tt("called pattens", wi=1) - .12, t_disc + 2.0), Lbl("Pattens", None, tt("called pattens", wi=1))], desc="pattens with spotlight (HI-01) and label", ids=["HI-01", "STATIC-02"], words="the pointed overshoes called pattens"))
    t_end3 = T.chapter_end("FASHIONS AND FABRICS") + .25
    add(painting_shot(t_disc, t_end3, [(t_disc, 1010, PATTENS[1] + 150, 1.05, "inout_cubic"), (t_end3, 2193, 4800, ZW, "linear")], [], desc="discarded shoes, a real room", ids=["CAM-03"], words="An abandoned pair of shoes ... a real day"))
    # ---------------- chapter 4: the room
    c = T.card("THE ROOM"); add(card_shot(c["t0"], c["t1"], c["text"]))
    cs = T.chapter_start("THE ROOM"); t_bed = tt("Look at the bed behind the couple"); t_set = tt("Further back is a bench")
    add(painting_shot(cs, t_bed, [(cs, FULL[0], FULL[1], ZF * 1.0, "linear"), (t_bed, FULL[0], FULL[1], ZF * 1.1, "linear")], [], desc="the room: matte", ids=["STATIC-01"], words="The room will strike us as strange"))
    t_mv = tt("and the mirror shows two visitors")
    add(painting_shot(t_bed, t_mv, [(t_bed, 3300, 2600, .50, "linear"), (t_mv, 3350, 1500, .50, "linear")], [Lbl("Bed", None, tt("Look at the bed behind the couple", wi=3))], desc="pan up the bed (CAM-04) with label", ids=["CAM-04", "STATIC-02"], words="Look at the bed behind the couple"))
    add(painting_shot(t_mv, t_mv + 4.0, [(t_mv, MIRROR[0], MIRROR[1], .9, "linear"), (t_mv + 4.0, MIRROR[0], MIRROR[1], 1.0, "linear")], [Spot(MIRROR, 430, 430, tt("and the mirror shows two visitors", wi=2) - .12, t_mv + 3.8)], desc="mirror cut-in with spotlight: two visitors (HI-01, TR-04)", ids=["HI-01", "TR-04"], words="and the mirror shows two visitors being welcomed in"))
    add(painting_shot(t_mv + 4.0, t_set, [(t_mv + 4.0, 3400, 1300, .55, "linear"), (t_set, 3400, 800, .55, "linear")], [], desc="back to the bed: a reception room", ids=["TR-04", "CAM-04"], words="So this is a reception room ... purely to impress"))
    t_ch = tt("Beside it stands a tall-backed chair"); t_mons = tt("the carved monsters")
    add(painting_shot(t_set, t_ch, [(t_set, LION[0], LION[1], .85, "inout_cubic"), (t_ch, LION[0], LION[1] - 30, .98, "linear")], [Lbl("Settle", None, tt("Further back is a bench called a settle", wi=7)), RingOv(LION, 180, tt("the carved monsters", wi=2) - .05)], desc="settle with circle on the carved creature (AN-01)", ids=["CAM-05", "AN-01", "STATIC-02"], words="Further back is a bench called a settle"))
    t_floor = tt("Now look at the floor"); t_brush = tt("and the brush hanging nearby")
    add(painting_shot(t_ch, t_floor, [(t_ch, STM[0] - 60, STM[1] + 150, .72, "linear"), (t_floor, STM[0] - 60, STM[1] + 250, .8, "linear")], [Lbl("Saint Martha", None, tt("That could be Saint Martha", wi=4)), RingOv((BRUSH[0], BRUSH[1] + 20), 190, tt("and the brush hanging nearby", wi=2) - .05)], desc="chair and brush with circle", ids=["CAM-05", "AN-01", "STATIC-02"], words="a tall-backed chair, topped by a woman riding a dragon"))
    t_set2 = tt("Set it beside the carpet")
    add(painting_shot(t_floor, t_set2, [(t_floor, RUG[0], RUG[1] - 300, .55, "inout_cubic"), (t_set2, RUG[0], RUG[1] - 100, .95, "linear")], [Lbl("Oriental carpet", None, tt("this oriental carpet", wi=1))], desc="rug crop push with label", ids=["CAM-05", "STATIC-02"], words="Now look at the floor ... oriental carpet"))
    t_same = tt("The same patient looking"); t_amb = tt("Beside the mirror hangs")
    add(split_shot(t_set2, t_amb, t_set2 + .1, t_same))
    t_fin = tt("Finally, let your eye drift")
    add(painting_shot(t_amb, t_fin, [(t_amb, AMBER[0] + 180, AMBER[1], .85, "inout_cubic"), (t_fin, AMBER[0] + 150, AMBER[1] + 60, 1.1, "linear")], [Lbl("Amber prayer beads", None, tt("of amber prayer beads", wi=1))], desc="amber beads crop with label", ids=["CAM-05", "STATIC-02"], words="Beside the mirror hangs a string of amber prayer beads"))
    t_stud = tt("Study the single orange"); t_end4 = T.chapter_end("THE ROOM") + .25
    add(painting_shot(t_fin, t_stud, [(t_fin, 1070, 1100, .9, "linear"), (t_stud - .8, 1070, 2880, .9, "inout_cubic"), (t_stud, 1070, 2900, .9, "linear")], [Lbl("Oranges", None, tt("the oranges on the sill", wi=1)), RingOv((430, 3200), 190, tt("the oranges on the sill", wi=1) - .05, hold=3.0)], desc="window pan down to the oranges (CAM-04)", ids=["CAM-04", "STATIC-02"], words="Finally, let your eye drift to the window"))
    add(painting_shot(t_stud, t_end4, [(t_stud, 1070, 2900, .9, "linear"), (t_end4, 900, 2900, 1.5, "out_cubic")], [RingOv(ORANGE, 130, tt("Study the single orange", wi=3) - .05, hold=3.4)], desc="circle on the single orange (AN-01)", ids=["AN-01", "CAM-05"], words="Study the single orange ... still life"))
    # ---------------- chapter 5: the mirror
    c = T.card("THE MIRROR"); add(card_shot(c["t0"], c["t1"], c["text"]))
    cs = T.chapter_start("THE MIRROR"); t_pull = tt("The mirror pulls the whole room together")
    z0 = 0.42; z1 = z0 * 3.57
    t_mi_end = tt("In the fifteenth century")
    t_dia = tt("and they were usually convex"); t_wide = tt("But a mirror so wide")
    cam_m = [(cs, 2193, 1750, z0, "inout_cubic"), (cs + 11.0, MIRROR[0], MIRROR[1], z1, "linear"), (t_mi_end + 20, MIRROR[0] + 30, MIRROR[1] + 20, z1 * 1.15, "linear")]
    # full mirror drift track used by several shots
    cam_drift = Cam(cam_m)
    def mkcam(ta, tb):
        n = max(2, int((tb - ta) / 0.25) + 1)
        ts_ = [ta + (tb - ta) * i / (n - 1) for i in range(n)]
        return [(t_, *cam_drift.at(t_), "linear") for t_ in ts_]
    add(painting_shot(cs, t_dia, mkcam(cs, t_dia), [Spot(MIRROR, 440, 440, tt("The mirror pulls the whole room together", wi=1) - .12, t_dia, ramp_in=.5, ramp_out=.5)], desc="mirror push 3.57x/11 s ease-in-out then drift; spotlight floor 0.20", ids=["CAM-05", "HI-01"], words="And now to the most intriguing object ... glass mirrors were high technology", params={"ratio": 3.57, "dur_s": 11}))
    t_ref = tt("Look closely at the reflection")
    add(still_shot(t_dia, t_dia + 4.0, "matsys", "The Moneylender and his Wife", "Quentin Massys, 1514", push=1.08, words="usually convex (a later convex mirror)"))
    add(dia_mirror_shot(t_dia + 4.0, t_ref))
    t_pur = tt("Mirrors were also used in art")
    add(painting_shot(t_ref, t_pur, [(t_ref, *cam_drift.at(t_ref), "inout_cubic"), (t_ref + 4.0, 2210, 1795, 2.7, "linear"), (t_pur, 2210, 1795, 2.9, "linear")], [Lbl("Reflection", None, tt("Look closely at the reflection", wi=4))], desc="push into the reflection with label", ids=["CAM-05", "STATIC-02"], words="Look closely at the reflection", params={"zoom": "to 2.7"}))
    t_fr = tt("Now notice the frame"); t_pos = tt("Their positions matter")
    add(painting_shot(t_pur, t_fr, [(t_pur, 2210, 1795, 2.9, "inout_cubic"), (t_fr, MIRROR[0], MIRROR[1], 1.45, "linear")], [], desc="pull out of reflection: purity", ids=["CAM-03"], words="Mirrors were also used in art to suggest purity"))
    t_rnd = tt("Ten tiny roundels"); t_every = tt("Every episode that comes after")
    add(painting_shot(t_fr, t_pos, [(t_fr, MIRROR[0], MIRROR[1], 1.45, "linear"), (t_pos, MIRROR[0] + 20, MIRROR[1], 1.2, "linear")], [Lbl("Passion roundels", None, tt("Ten tiny roundels", wi=2)), RingOv(R1, 82, tt("Ten tiny roundels", wi=2) - .05, hold=2.6), RingOv(R2, 82, tt("Ten tiny roundels", wi=2) - .05, hold=2.6)],
                      desc="frame crop with two circles on roundels (AN-01)", ids=["AN-01", "STATIC-02"], words="Now notice the frame. Ten tiny roundels"))
    t_chan = tt("And one more detail")
    add(painting_shot(t_pos, t_chan, [(t_pos, MIRROR[0] + 30, MIRROR[1], 1.2, "linear"), (t_chan, MIRROR[0] + 140, MIRROR[1], 1.1, "linear")], [Spot((MIRROR[0] + 215, MIRROR[1]), 250, 420, tt("is placed beside Costanza", wi=3) - .12, t_chan - .1)], desc="spotlight on Costanza's half of the ring (HI-01)", ids=["HI-01", "CAM-05"], words="Their positions matter. Every episode ... beside Costanza"))
    t_lit = tt("one candle is lit"); t_snuf = tt("another has been snuffed out"); t_some = tt("Some read the flame"); t_end5 = T.chapter_end("THE MIRROR") + .25
    add(painting_shot(t_chan, t_end5, [(t_chan, 2150, 700, .62, "linear"), (t_lit - .3, 2150, 700, .62, "inout_cubic"), (t_lit + 3.0, 2160, 600, .62 * 1.49, "out_cubic"), (t_end5, 2400, 560, .62 * 1.6, "linear")],
                      [Lbl("Chandelier", None, tt("from the chandelier above", wi=2)), RingOv(LIT, 215, tt("one candle is lit", wi=1) - .05, hold=3.0), RingOv(SNUF, 215, tt("another has been snuffed out", wi=3) - .05, hold=3.0)], desc="chandelier: circles on the lit and the snuffed-out candle (AN-01), push then drift", ids=["AN-01", "CAM-05", "STATIC-02"], words="And one more detail ... one candle is lit and another has been snuffed out"))
    # ---------------- chapter 6: the alchemist
    c = T.card("THE ALCHEMIST"); add(card_shot(c["t0"], c["t1"], c["text"]))
    cs = T.chapter_start("THE ALCHEMIST"); t_dogc = tt("starting with the dog by her skirt"); t_sc = tt("then the small scenes"); t_chk = tt("and the chance that he is wearing"); t_yet = tt("Yet the strongest hint")
    add(painting_shot(cs, t_dogc, [(cs, FULL[0], FULL[1], ZF * 1.0, "linear"), (t_dogc, FULL[0], FULL[1], ZF * 1.08, "linear")], [], desc="one single meaning would be reckless: matte", ids=["STATIC-01"], words="Saying that a painting has one single meaning would be reckless"))
    add(painting_shot(t_dogc, t_sc, [(t_dogc, DOG[0], DOG[1] - 120, .75, "linear"), (t_sc, DOG[0], DOG[1] - 90, .85, "linear")], [], desc="clue: the dog (hard cut)", ids=["TR-04", "CAM-05"], words="starting with the dog by her skirt"))
    add(painting_shot(t_sc, t_chk, [(t_sc, MIRROR[0] + 140, MIRROR[1], 1.2, "linear"), (t_chk, MIRROR[0] + 150, MIRROR[1], 1.28, "linear")], [Spot((MIRROR[0] + 215, MIRROR[1]), 250, 420, tt("then the small scenes", wi=3) - .12, t_chk - .1)], desc="clue: roundels on her side", ids=["TR-04", "HI-01"], words="then the small scenes on her half of the frame"))
    add(painting_shot(t_chk, t_yet, [(t_chk, TABARD[0], TABARD[1] - 500, .62, "linear"), (t_yet, TABARD[0], TABARD[1] - 400, .68, "linear")], [], desc="clue: dark clothes (hard cut)", ids=["TR-04", "CAM-05"], words="and the chance that he is wearing mourning clothes"))
    t_look = tt("Look at the joined hands"); t_then = tt("Then again, the same gesture")
    add(painting_shot(t_yet, t_then, [(t_yet, 2300, 2400, .5, "linear"), (t_look, HANDS[0], HANDS[1], .8, "inout_cubic"), (t_then, HANDS[0], HANDS[1], .95, "linear")], [Spot(HANDS, 360, 270, tt("Look at the joined hands", wi=3) - .12, t_then + 4.0), Lbl("Joined hands", None, tt("Look at the joined hands", wi=3))],
                      desc="push to the joined hands with spotlight (HI-01), floor 0.20", ids=["CAM-05", "HI-01", "STATIC-02"], words="Yet the strongest hint is the way Giovanni takes her hand"))
    t_real = tt("The real marvel"); t_alc = tt("His contemporaries called him an alchemist")
    add(painting_shot(t_then, t_real, [(t_then, HANDS[0], HANDS[1], .95, "linear"), (t_real, HANDS[0], HANDS[1], 1.0, "linear")], [Spot(HANDS, 360, 270, t_then - 1.0, t_real - .2)], desc="hands: both readings at once", ids=["HI-01"], words="Then again, the same gesture has been read as a wedding vow"))
    add(painting_shot(t_real, t_alc, [(t_real, MIRROR[0] - 100, MIRROR[1], .7, "inout_cubic"), (t_alc, MIRROR[0], MIRROR[1], 2.2, "linear")], [], desc="step into the mirrored world: push (CAM-05)", ids=["CAM-05"], words="The real marvel is how Van Eyck handles space"))
    t_knew = tt("He knew that some pigments")
    add(still_shot(t_alc, t_knew, "turban", "Man in a Red Turban", "Jan van Eyck, 1433", push=1.06, words="His contemporaries called him an alchemist"))
    t_his = tt("His reach extended"); t_thumb = tt("and there is even a thumbprint")
    t_glow = tt("which gives it a glow")
    add(painting_shot(t_knew, t_glow, [(t_knew, COSFACE[0], COSFACE[1] + 100, 1.2, "linear"), (t_glow, COSFACE[0] - 100, COSFACE[1] + 150, 1.35, "linear")], [], desc="glaze crop on Costanza's veil and face: thin layers", ids=["CAM-05"], words="He knew that some pigments turn almost transparent in oil"))
    add(painting_shot(t_glow, t_thumb, [(t_glow, 3000, 3300, .7, "linear"), (t_thumb, 3000, 3500, .78, "linear")], [], desc="hard cut: the smooth surface of the dress (TR-04)", ids=["TR-04", "CAM-05"], words="which gives it a glow, and a surface so smooth that it looks untouched"))
    t_dur = tt("Albrecht Durer"); t_vel = tt("to Velazquez")
    add(painting_shot(t_thumb, t_his, [(t_thumb, DOG[0], DOG[1] - 60, .9, "linear"), (t_his, DOG[0], DOG[1] - 40, 1.0, "linear")], [], desc="close on the dog's shadow (thumbprint)", ids=["CAM-05"], words="and there is even a thumbprint close to the dog's shadow"))
    add(painting_shot(t_his, t_dur, [(t_his, FULL[0], FULL[1], ZF, "linear"), (t_dur, FULL[0], FULL[1], ZF * 1.05, "linear")], [], desc="his reach: matte", ids=["STATIC-01"], words="His reach extended far past the Low Countries"))
    add(still_shot(t_dur, t_vel, "durer", "Self-Portrait", "Albrecht Dürer, 1500", push=1.06, words="Albrecht Durer, whose self-portrait of 1500 shares that direct gaze"))
    mn = IM("meninas")
    add(still_shot(t_vel, tt("and on to the Pre-Raphaelites"), "meninas", "Las Meninas", "Diego Velázquez, 1656", cam_keys=[(t_vel, mn.w / 2, mn.h / 2, img_fit("meninas"), "linear"), (t_vel + 1.5, mn.w / 2, mn.h / 2, img_fit("meninas"), "inout_cubic"), (tt("and on to the Pre-Raphaelites"), mn.w * .42, mn.h * .575, img_fit("meninas") * 3.2, "linear")], desc="Las Meninas with push to its mirror (CAM-05)", ids=["CAM-05", "STATIC-02"], words="Velazquez, whose Las Meninas has its own mirror at the back"))
    # ---------------- closing
    ccs = T.chapter_start("CLOSING"); t_so2 = tt("So let us return")
    base = T.find("the dog the roundels the candle the dark clothes")
    wd = T.words
    t_dog3, t_rnd3, t_can, t_dark = wd[base + 1][1], wd[base + 3][1], wd[base + 5][1], wd[base + 7][1]
    t_pull_start = ccs - 0.2; t_pull_end = t_pull_start + 40.0
    pos = {"CANDLE": LIT, "ROUNDELS": (R1[0] + 300, R1[1]), "MOURNING DRESS": (TABARD[0] - 700, TABARD[1] - 600), "DOG": (DOG[0] + 600, DOG[1])}
    recaps = [ScreenText("DOG", t_dog3 + 0.0, t_dog3 + 6.5, pt=pos["DOG"], size=46), ScreenText("ROUNDELS", t_rnd3, t_rnd3 + 6.0, pt=pos["ROUNDELS"], size=46), ScreenText("CANDLE", t_can, t_can + 5.5, pt=pos["CANDLE"], size=46), ScreenText("MOURNING DRESS?", t_dark, t_dark + 5.0, pt=pos["MOURNING DRESS"], size=46)]
    close_cam = [(ccs - 0.3, HANDS[0], HANDS[1], 1.0, "out_quad"), (t_pull_end, FULL[0], FULL[1], 1.0 / 5.8, "linear")]
    t_h = END - 3.8
    add(painting_shot(ccs - 0.3, END, close_cam + [(END, FULL[0], FULL[1], 1.0 / 5.8, "linear")], recaps, desc="closing: recap labels (plain text, no strip) and 5.8x/40 s ease-out pull-out", ids=["CAM-03", "STATIC-01", "STATIC-08"], words="So let us return ... so that we would know", params={"ratio": 5.8, "dur_s": 40, "ease": "out_quad"}))
    # fix: alchemist last shot must end at closing start
    return sorted(S, key=lambda s: s["t0"])


def contiguous(shots, end):
    """make shots contiguous: each shot ends where the next starts (hard cuts)"""
    out = []
    for i, s in enumerate(shots):
        s = dict(s)
        s["t1"] = shots[i + 1]["t0"] if i + 1 < len(shots) else end
        out.append(s)
    return out


def make(T):
    shots = contiguous(build(T), T.end)
    shots[0]["t0"] = 0.0
    for a in shots:
        if a["t1"] <= a["t0"] + 0.2:
            raise ValueError("bad shot duration %s %.2f-%.2f" % (a.get("effect"), a["t0"], a["t1"]))
    return shots


def frame_fn(T):
    shots = make(T)
    starts = [s["t0"] for s in shots]
    import bisect

    def frame_at(t):
        i = max(0, bisect.bisect_right(starts, t + 1e-6) - 1)
        f = shots[i]["fn"](t)
        fade = 1 - ramp(t, T.end - 1.6, 1.6, "inout_sine")
        if fade < 1:
            f = f * fade
        return to_u8(f)
    return frame_at, shots


def main():
    mode, tpath = sys.argv[1], sys.argv[2]
    T = TL(tpath)
    fa, shots = frame_fn(T)
    if mode == "still":
        os.makedirs(sys.argv[3], exist_ok=True)
        for t in sys.argv[4:]:
            cv2.imwrite(os.path.join(sys.argv[3], "t%07.2f.png" % float(t)), fa(float(t)))
    elif mode == "timeline":
        json.dump([{k: v for k, v in s.items() if k != "fn"} for s in shots], open(sys.argv[3], "w"), indent=1, default=str)
    elif mode == "render":
        outp = sys.argv[3]; size, fps, t0, t1 = (W, H), 30.0, 0.0, T.end
        a = sys.argv[4:]
        for i, x in enumerate(a):
            if x == "--size": size = tuple(int(v) for v in a[i + 1].split("x"))
            if x == "--fps": fps = float(a[i + 1])
            if x == "--t0": t0 = float(a[i + 1])
            if x == "--t1": t1 = float(a[i + 1])
        crf = "15" if size == (W, H) else "27"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % size, "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", crf,
                              "-pix_fmt", "yuv420p", "-g", "60", "-threads", "4", outp], stdin=subprocess.PIPE)
        i0 = int(round(t0 * fps)); i1 = int(round(t1 * fps)); ts = time.time()
        for i in range(i0, i1):
            fr = fa(i / fps)
            if size != (W, H):
                fr = cv2.resize(fr, size, interpolation=cv2.INTER_AREA)
            p.stdin.write(fr.tobytes())
            if (i - i0) % 150 == 0:
                print("frame %d/%d  %.1fs elapsed" % (i - i0, i1 - i0, time.time() - ts), flush=True)
        p.stdin.close(); p.wait()
        print("RENDER_DONE %d frames %.1fs" % (i1 - i0, time.time() - ts), flush=True)


if __name__ == "__main__":
    main()
