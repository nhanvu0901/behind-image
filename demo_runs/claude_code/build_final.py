"""final_demo renderer: frame_at(t) driven by timing.json (exact beat starts + forced-alignment word times).

Usage:
  build_final.py still  <timing.json> <out_dir> t1 t2 ...        (PNG stills, any machine)
  build_final.py render <timing.json> <out.mp4> [--size WxH] [--fps N] [--t0 s --t1 s]   (server)
  build_final.py timeline <timing.json> <timeline_shots.json>
"""
import json, os, sys, math, subprocess, time
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
from vfx import *

ASSET = os.path.join(HERE, "assets")
ARN_PATH = os.path.join(ASSET, "commons", "arnolfini_commons.jpg")
VDP_PATH = os.path.join(ASSET, "commons", "paele_commons.jpg")

# source-pixel anchors in the 4386x6000 Arnolfini scan (measured on crops)
MIRROR = (2220, 1790)
ROUNDEL_R1 = (2474, 1690)   # Costanza's side (viewer's right), upper
ROUNDEL_R2 = (2466, 1870)   # Costanza's side, lower
HANDS = (2420, 2540)
DOG = (2098, 5446)
RUG_A = (2388, 4200)
FULL = (2193, 3000)         # centre of the full painting
Z_FULL = 0.172              # whole 6000 px painting = 1032 px (95.5 % of frame height)
Z_WIDTH = 1920 / 4386       # painting width fills the frame (full-bleed 16:9 crop)

shots_registry = []


class T:
    def __init__(self, path):
        d = json.load(open(path))
        self.b = d["beats"]
        self.title = d["title"]
        self.end = d["end"]
        self.d = d

    def s(self, beat):
        return self.b[beat]["start"]

    def e(self, beat):
        return self.b[beat]["end"]

    def w(self, beat, prefix):
        """start time of the first word in `beat` whose lowercase text starts with prefix"""
        for x in self.b[beat]["words"]:
            if x["w"].lower().strip(".,'\"").startswith(prefix.lower()):
                return x["s"]
        raise KeyError((beat, prefix))


class Scene:
    def __init__(self):
        self.A = Img(ARN_PATH, "arnolfini")
        self.V = Img(VDP_PATH, "paele")
        self.bgcard = blurred_bg(cv2.imread(ARN_PATH, cv2.IMREAD_REDUCED_COLOR_4), sigma=30, dark=.42)
        self.l_title = text_layer("THE ARNOLFINI PORTRAIT", W // 2, int(H * .455), 78, "reg", 11)
        self.l_artist = text_layer("JAN VAN EYCK", W // 2, int(H * .585), 38, "reg", 10)
        self.l_year = text_layer("1434", W // 2, int(H * .65), 34, "reg", 10)


def make_shots(S, T):
    A, V = S.A, S.V
    shots = []

    def add(t0, t1, effect, ids, image, params, words, fn):
        shots.append(dict(t0=t0, t1=t1, effect=effect, ids=ids, image=image, params=params, words=words, fn=fn))

    # ---------------------------------------------------------------- S0 hook: couple detail -> pull-back to full painting
    t_title0 = T.title[0]
    cam0 = Cam([(0, 2193, 1500, 1.00 * Z_WIDTH, "inout_sine"),
                (T.e("B1a") - .6, 2193, 2150, 1.08 * Z_WIDTH, "out_cubic"),
                (t_title0 - .35, FULL[0], FULL[1], Z_FULL, "linear")])

    def f0(t):
        cx, cy, z = cam0.at(t)
        return compose_matte(A, cx, cy, z)
    add(0, t_title0, "slow drift across couple + decelerating pull-back to matte", ["CAM-03", "CAM-05", "STATIC-01"], "arnolfini_commons",
        {"drift": "z 0.4378->0.4728 over %.1fs" % (T.e("B1a") - .6), "pull_back": "0.4728->0.172 (2.75x) %.1fs ease out_cubic" % (t_title0 - .35 - (T.e("B1a") - .6)),
         "ref": "opening pull-back 3.0x/17.9s out"}, "Most people ... Look closer", f0)

    # ---------------------------------------------------------------- S1 title card
    def f1(t):
        e = ramp(t, T.title[0], .35, "out_quad")
        f = S.bgcard.copy()
        S.l_title.apply(f, e)
        hline(f, W // 2, int(H * .535), 200, 2, .75 * e)
        S.l_artist.apply(f, e)
        S.l_year.apply(f, e)
        return f
    add(T.title[0], T.title[1], "title card", ["TXT-01"], "arnolfini_commons (blurred)", {"blur_sigma": 30, "text_fade": 0.35}, "", f1)

    # ---------------------------------------------------------------- S2 dress and fur
    a0, a1, b0, b1 = T.s("B2a"), T.e("B2a"), T.s("B2b"), T.e("B2b")
    cam2 = Cam([(a0, FULL[0], FULL[1], Z_FULL, "inout_cubic"),
                (a1 + .3, 2300, 3600, .50, "linear"),
                (b1 + .25, 2300, 4650, .48, "linear")])
    L1 = label_layer("Green wool gown", "Jan van Eyck, 1434")
    L2 = label_layer("Squirrel-fur lining", "Jan van Eyck, 1434")
    l1t0 = a0 + 2.3

    def f2(t):
        cx, cy, z = cam2.at(t)
        f = compose_matte(A, cx, cy, z)
        L1.apply(f, window(t, l1t0, min(l1t0 + 3.2, b0 - .05), .08, .1))
        L2.apply(f, window(t, b0 + .35, b1 + .1, .08, .1))
        return f
    add(a0, b1 + .25, "matte zoom-in to full-bleed then pan down dress", ["CAM-01", "CAM-04", "CAM-06", "STATIC-02"], "arnolfini_commons",
        {"zoom": "0.172->0.50 (2.9x) ease inout_cubic", "pan": "cy 3600->4650 linear (%.0f px/s screen)" % ((4650 - 3600) * .49 / (b1 + .25 - a1 - .3)),
         "label": ["Green wool gown @%.2f" % l1t0, "Squirrel-fur lining @%.2f" % (b0 + .35)], "ref": "matte zoom-in 1.59x/4.9s ease-in; dress pan ~180 px/s"}, "Her green gown / The fur lining", f2)

    # ---------------------------------------------------------------- S3 dog (hard cut-in)
    c0, c1 = T.s("B2c"), T.e("B2c")
    cam3 = Cam([(c0, DOG[0], DOG[1] - 130, .90, "out_cubic"), (c1 + .3, DOG[0], DOG[1] - 70, 1.04, "linear")])
    L3 = label_layer("Dog at her feet", "Jan van Eyck, 1434")

    def f3(t):
        cx, cy, z = cam3.at(t)
        f = compose_matte(A, cx, cy, z)
        L3.apply(f, window(t, c0 + .4, c1 - .1, .08, .1))
        return f
    add(c0, c1 + .3, "hard cut-in to detail + slow push", ["TR-04", "CAM-01", "STATIC-08"], "arnolfini_commons", {"zoom": "0.90->1.04 out_cubic"}, "The dog at her feet", f3)

    # ---------------------------------------------------------------- S4 1433 / 1434 on matte
    d0, d1 = T.s("B2d"), T.e("B2d")
    cam4 = Cam([(d0, FULL[0], FULL[1], Z_FULL, "linear"), (d1 + .3, FULL[0], FULL[1], Z_FULL * 1.06, "linear")])
    L33 = text_layer("1433", int(W * .17), int(H * .46), 120, "reg", 10, sub="COSTANZA DIES", subsize=30)
    L34 = text_layer("1434", int(W * .83), int(H * .46), 120, "reg", 10, sub="PORTRAIT FINISHED", subsize=30)
    t33, t34 = T.w("B2d", "1433"), T.w("B2d", "finished")

    def f4(t):
        cx, cy, z = cam4.at(t)
        f = compose_matte(A, cx, cy, z)
        L33.apply(f, window(t, t33, d1 + .3, .2, .2))
        L34.apply(f, window(t, t34, d1 + .3, .2, .2))
        return f
    add(d0, d1 + .3, "hard cut to matte, year captions", ["STATIC-09", "STATIC-01"], "arnolfini_commons", {"text": "1433 @%.2f, 1434 @%.2f" % (t33, t34)}, "died in 1433 / finished", f4)

    # ---------------------------------------------------------------- S5 mirror: spotlight, rings, spotlight on Costanza's side
    m0, m1 = T.s("B3a"), T.e("B3a")
    r0, r1 = T.s("B3b"), T.e("B3b")
    s0, s1 = T.s("B3c"), T.e("B3c")
    cam5 = Cam([(m0, 2193, 1750, Z_WIDTH, "inout_cubic"),
                (m1 + .1, MIRROR[0], MIRROR[1], 1.12, "inout_sine"),
                (r1 + .1, MIRROR[0] + 20, MIRROR[1], 1.30, "inout_sine"),
                (s1 + .3, MIRROR[0] + 120, MIRROR[1], 1.28, "linear")])
    tmir = T.w("B3a", "mirror")
    trnd = T.w("B3b", "roundels")
    L5 = label_layer("Passion roundels", "Jan van Eyck, 1434")

    def f5(t):
        cx, cy, z = cam5.at(t)
        f = compose_matte(A, cx, cy, z)
        sc = lambda p: A.to_screen(p[0], p[1], cx, cy, z)
        # spotlight 1: whole mirror, on from the word "mirror", released early in B3b
        a1_ = ramp(t, tmir, .5, "inout_sine") * (1 - ramp(t, r0 + .25, .4, "inout_sine"))
        sx, sy = sc(MIRROR)
        f = spotlight(f, sx, sy, 420 * z, 420 * z, a1_)
        # rings on two roundels on Costanza's side
        pr = ramp(t, trnd + .1, .5, "out_quad")
        ra = window(t, trnd + .1, r1 + .35, .05, .4)
        for p in (ROUNDEL_R1, ROUNDEL_R2):
            x, y = sc(p)
            f = ring(f, x, y, 78 * z, pr, .75 * ra, max(5, 9 * z))
        # spotlight 2: right half of the ring (Costanza's side) from B3c start
        a2_ = ramp(t, s0, .5, "inout_sine") * (1 - ramp(t, s1 + .05, .3))
        sx, sy = sc((MIRROR[0] + 215, MIRROR[1]))
        f = spotlight(f, sx, sy, 230 * z, 400 * z, a2_)
        L5.apply(f, window(t, r0 + .15, r1 - .1, .08, .1))
        return f
    add(m0, s1 + .3, "push-in to mirror + spotlight x2 + two circles", ["HI-01", "CAM-05", "AN-01", "STATIC-02"], "arnolfini_commons",
        {"zoom": "0.4378->1.12->1.30 (3.0x) inout", "spotlight": "floor 0.35, ramp 0.5s @'mirror' %.2f and @B3c %.2f" % (tmir, s0),
         "rings": "r=78 src px, 0.5s draw @'roundels' %.2f, fade 0.4s" % (trnd + .1)}, "The convex mirror / Ten tiny roundels / Every scene", f5)

    # ---------------------------------------------------------------- S6 split-screen comparison with slide-in
    p0, p1 = T.s("B4a"), T.e("B4b")
    pw, ph, py = 900, 740, 36
    xl, xr = 50, 970
    rug_t0 = T.s("B4b")
    camL = Cam([(p0, FULL[0], FULL[1], 0.94 * ph / 6000, "linear"), (rug_t0, FULL[0], FULL[1], 0.94 * ph / 6000, "inout_cubic"),
                (p1 + .3, RUG_A[0], RUG_A[1], .30, "linear")])
    zv = max(pw / 4169, ph / 3249)
    camR = Cam([(p0, 4169 / 2, 3249 / 2, zv, "linear"), (rug_t0, 4169 / 2, 3249 / 2, zv, "inout_cubic"), (p1 + .3, 2085, 2780, .55, "linear")])
    capL = label_layer("The Arnolfini Portrait", "Jan van Eyck, 1434", y0=.70, h=140)
    # captions beneath panels (small, no strip): two layers
    capL = text_layer("THE ARNOLFINI PORTRAIT", xl + pw // 2, py + ph + 52, 30, "reg", 2, sub="Jan van Eyck, 1434", subsize=26)
    capR = text_layer("VIRGIN AND CHILD WITH CANON VAN DER PAELE", xr + pw // 2, py + ph + 52, 30, "reg", 2, sub="Jan van Eyck, 1434", subsize=26)
    tcmp = T.s("B4a")

    def f6(t):
        f = backdrop(W, H).copy()
        cx, cy, z = camL.at(t)
        left = compose_matte(A, cx, cy, z, pw, ph)
        f[py:py + ph, xl:xl + pw] = left
        slide = ease("out_cubic", (t - tcmp - .08) / .85)
        x = int(round(W + 10 - (W + 10 - xr) * slide))
        cx, cy, z = camR.at(t)
        right, _, _ = V.view(cx, cy, z, pw, ph)
        x0 = max(x, 0); x1 = min(x + pw, W)
        if x1 > x0:
            f[py:py + ph, x0:x1] = right[:, x0 - x:x1 - x]
        capL.apply(f, ramp(t, tcmp, .2))
        capR.apply(f, ramp(t, tcmp + .75, .25))
        return f
    add(p0, p1 + .3, "two-panel split-screen, slide-in of 2nd panel, synchronous push-ins on rugs", ["LAY-01", "TR-02", "CAM-05", "STATIC-02"],
        "arnolfini_commons + paele_commons", {"slide": "0.85s out_cubic from right edge @'Compare' %.2f" % tcmp, "push": "L 0.1097->0.30, R %.3f->0.55" % zv}, "Compare it / The same mastery", f6)

    # ---------------------------------------------------------------- S7 hands spotlight, then closing pull-back
    h0, h1 = T.s("B4c"), T.e("B4c")
    g0, g1 = T.s("B4d"), T.e("B4d")
    n0, n1 = T.s("B5a"), T.e("B5b")
    camH = Cam([(h0, FULL[0], FULL[1], Z_FULL, "inout_cubic"),
                (h1 + .1, HANDS[0], HANDS[1], .50, "linear"),
                (g1 + .1, HANDS[0], HANDS[1], .95, "inout_sine"),
                (n1 - .6, FULL[0], FULL[1], Z_FULL, "out_cubic")])
    thold = T.w("B4d", "holds")
    end = T.end
    L7 = label_layer("Joined hands", "Jan van Eyck, 1434")

    def f7(t):
        cx, cy, z = camH.at(t)
        f = compose_matte(A, cx, cy, z)
        a = ramp(t, thold, .5, "inout_sine") * (1 - ramp(t, n0, .5, "inout_sine"))
        sx, sy = A.to_screen(HANDS[0], HANDS[1], cx, cy, z)
        f = spotlight(f, sx, sy, 330 * z + 40, 260 * z + 40, a)
        L7.apply(f, window(t, g0 + .2, thold + 2.7, .08, .1))
        fade = 1 - ramp(t, end - .9, .9, "inout_sine")
        return f * fade
    add(h0, end, "push to hands + spotlight, then long pull-back to matte, fade out", ["HI-01", "CAM-05", "CAM-03", "STATIC-01"], "arnolfini_commons",
        {"spotlight": "floor 0.35 ramp 0.5s @'holds' %.2f, release @B5a %.2f" % (thold, n0), "pull_back": "0.95->0.172 (5.5x) %.1fs out_cubic" % (n1 - .6 - g1 - .1),
         "ref": "closing pull-out 5.8x/40s ease-out"}, "But the clue / Giovanni holds / Pull back / memorial", f7)
    return shots


def frame_fn(S, T):
    shots = make_shots(S, T)
    shots_registry[:] = shots
    starts = [s["t0"] for s in shots]

    def frame_at(t):
        i = max(j for j, s0 in enumerate(starts) if s0 <= t + 1e-9) if t >= 0 else 0
        return to_u8(shots[i]["fn"](t))
    return frame_at


def main():
    mode, tpath = sys.argv[1], sys.argv[2]
    Tm = T(tpath)
    S = Scene()
    fa = frame_fn(S, Tm)
    if mode == "still":
        out = sys.argv[3]
        os.makedirs(out, exist_ok=True)
        for t in sys.argv[4:]:
            cv2.imwrite(os.path.join(out, "t%07.2f.png" % float(t)), fa(float(t)))
    elif mode == "timeline":
        json.dump([{k: v for k, v in s.items() if k != "fn"} for s in shots_registry], open(sys.argv[3], "w"), indent=1)
    elif mode == "render":
        outp = sys.argv[3]
        size, fps, t0, t1 = (W, H), 30.0, 0.0, Tm.end
        a = sys.argv[4:]
        for i, x in enumerate(a):
            if x == "--size":
                size = tuple(int(v) for v in a[i + 1].split("x"))
            if x == "--fps":
                fps = float(a[i + 1])
            if x == "--t0":
                t0 = float(a[i + 1])
            if x == "--t1":
                t1 = float(a[i + 1])
        crf = "14" if size == (W, H) else "26"
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % size, "-r", str(fps), "-i", "-",
               "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p", "-threads", "4", outp]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        n = int(round((t1 - t0) * fps))
        ts = time.time()
        for i in range(n):
            t = t0 + i / fps
            fr = fa(t)
            if size != (W, H):
                fr = cv2.resize(fr, size, interpolation=cv2.INTER_AREA)
            p.stdin.write(fr.tobytes())
            if i % 60 == 0:
                print("frame %d/%d  %.1fs elapsed" % (i, n, time.time() - ts), flush=True)
        p.stdin.close()
        p.wait()
        print("RENDER_DONE %d frames %.1fs" % (n, time.time() - ts), flush=True)


if __name__ == "__main__":
    main()
