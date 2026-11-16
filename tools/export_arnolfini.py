#!/usr/bin/env python3
"""Export the Arnolfini episode (demo_runs/claude_code/build_v2.py) to projects/arnolfini/{storyboard,timing}.json.

It runs the benchmark's own `build(T)` with instrumented shot builders, overlay classes and timeline, so every camera key,
overlay, phrase anchor and label comes from the real build logic rather than being re-typed.  Phrase times become word-index
anchors (`{"w", "off", "text"}`); constants like MIRROR become named regions of asset A; cards, context stills and the
"back to the painting" return become shots.

    python tools/export_arnolfini.py [--out projects/arnolfini] [--old demo_runs/claude_code]

Read-only on the old code (bytecode writing is disabled).  Needs ffmpeg for the audio stream copy.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]

# ----------------------------------------------------------------------------- benchmark pins
# The engine's defaults come from style.json / the registry (the measured channel look).  The benchmark build used slightly
# different literals; the exporter pins those explicitly in the storyboard so the new engine reproduces the old frames.
LABEL_PINS = {"strip_y_top_pct": 79.0, "strip_y_bottom_pct": 92.98, "right_fade_pct": 22, "fade_out_s": 0.12}
CARD_PINS = {"text_width_pct": 50, "text_fade_out_s": 0.1}
MAP_PINS = {"route_color": "#d22828"}

REGION_LABELS = {
    "MIRROR": "Mirror", "HANDS": "Joined hands", "DOG": "Dog", "RUG": "Carpet", "INSCR": "Latin inscription", "R1": "Roundel 1", "R2": "Roundel 2",
    "LIT": "Lit candle", "SNUF": "Snuffed-out candle", "ORANGE": "Single orange", "PATTENS": "Pattens", "BOOTS": "Boots", "LION": "Carved creature",
    "STM": "Saint Martha finial", "BRUSH": "Brush", "AMBER": "Amber beads", "HAT": "Straw hat", "TABARD": "Velvet tabard", "FURSLEEVE": "Fur sleeve",
    "BLUESL": "Blue underdress", "RUFFLES": "Ruffles", "BEDP": "Bed", "COSFACE": "Costanza's face", "GIOFACE": "Giovanni's face", "FULL": "Whole painting (centre)",
}
REGION_RADII = {"MIRROR": (440, 440), "HANDS": (360, 270), "INSCR": (420, 120), "DOG": (330, 330), "LION": (180, 180), "LIT": (215, 215), "SNUF": (215, 215),
                "R1": (82, 82), "R2": (82, 82), "ORANGE": (130, 130)}
ASSET_FILES = {"A": "arnolfini_commons.jpg", "V": "paele_commons.jpg"}
ASSET_META = {
    "A": ("The Arnolfini Portrait", "Jan van Eyck", "1434"),
    "V": ("Virgin and Child with Canon van der Paele", "Jan van Eyck", "1434"),
    "bruges": ("Grote Markt, Bruges", "Rijksmuseum (etching)", ""),
    "tomb": ("Tomb of Mary of Burgundy, Bruges", "Jacob Jonghelinck / Jan Borreman II", "late 15th century"),
}
INTENT_BY_TECH = {"CAM-01": "explore", "CAM-03": "establish", "CAM-04": "explore", "CAM-05": "point_at", "STATIC-01": "establish", "X-LAY-01": "context",
                  "LAY-01": "compare", "X-CARD-01": "structure", "X-CARD-02": "structure", "STATIC-06": "context", "DIA-07": "explain_mechanism"}
INTENT_BY_OVERLAY = {"HI-01": "isolate", "AN-01": "point_at", "X-ANN-01": "point_at", "X-ANN-02": "context", "STATIC-08": "point_at",
                     "X-ANN-03": "reveal", "AN-05": "quantify", "STATIC-09": "context"}


# ----------------------------------------------------------------------------- times that remember their word
class TF(float):
    """A float that remembers which word it was derived from (`anc` = word index) so it can be exported as an anchor."""

    def __new__(cls, v, anc=None):
        o = float.__new__(cls, v)
        o.anc = anc
        return o

    def __add__(self, o):
        return TF(float(self) + float(o), self.anc) if isinstance(o, (int, float)) and not isinstance(o, TF) else float(self) + float(o)

    __radd__ = __add__

    def __sub__(self, o):
        return TF(float(self) - float(o), self.anc) if isinstance(o, (int, float)) and not isinstance(o, TF) else float(self) - float(o)

    def __rsub__(self, o):
        return float(o) - float(self)


def load_old(old_dir: Path):
    sys.path.insert(0, str(old_dir / "lib"))
    sys.path.insert(0, str(old_dir))
    import importlib
    return importlib.import_module("build_v2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "projects" / "arnolfini"))
    ap.add_argument("--old", default=str(REPO / "demo_runs" / "claude_code"))
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()
    old, out = Path(a.old).resolve(), Path(a.out).resolve()
    B = load_old(old)
    timing2 = json.load(open(old / "v2" / "timing2.json"))

    # -- timing.json ------------------------------------------------------------------------------------------
    words, beats, chapters = [], [], []
    for b in timing2["beats"]:
        w0 = len(words)
        for w in b["words"]:
            words.append({"w": w["w"], "s": w["s"], "e": w["e"]})
        beats.append({"chapter": b["chapter"], "text": b["text"], "start": b["start"], "end": b["end"], "w0": w0, "w1": len(words)})
        if not chapters or chapters[-1]["name"] != b["chapter"]:
            chapters.append({"name": b["chapter"], "start": 0.0 if not chapters else b["start"], "end": b["end"]})
        else:
            chapters[-1]["end"] = b["end"]
    END = timing2["end"]
    timing = {"duration": END, "words": words, "beats": beats, "chapters": chapters}

    class TL2(B.TL):
        def __init__(self, path):
            super().__init__(path)
            self.words = [(B.norm(w["w"]), TF(w["s"], i), w["e"]) for i, w in enumerate(words)]

        def chapter_start(self, name):
            bt = next(b for b in beats if b["chapter"] == name)
            return TF(bt["start"], bt["w0"])

        def chapter_end(self, name):
            bt = [b for b in beats if b["chapter"] == name][-1]
            return TF(bt["end"], bt["w1"] - 1)

    def anchor(x):
        if isinstance(x, TF) and x.anc is not None:
            i = x.anc
            return {"w": i, "off": round(float(x) - words[i]["s"], 4), "text": words[i]["w"]}
        return {"t": round(float(x), 4)}

    # -- instrument the old module ---------------------------------------------------------------------------
    def rec_cls(cls, name):
        class R(cls):
            def __init__(self, *args, **kw):
                self.rec = (name, args, kw)
                super().__init__(*args, **kw)
        R.__name__ = "R" + name
        return R

    for n in ("Lbl", "Spot", "RingOv", "ScreenText", "DimOv", "Years"):
        setattr(B, n, rec_cls(getattr(B, n), n))
    orig_ps, orig_still = B.painting_shot, B.still_shot
    still_tags: list = []

    def ps(t0, t1, keys, overlays=(), key="A", desc="", ids=(), words="", params=None):
        d = orig_ps(t0, t1, keys, overlays, key, desc, ids, words, params)
        d["_rec"] = {"kind": "painting", "keys": list(keys), "overlays": list(overlays), "key": key, "ids": list(ids), "desc": desc,
                     "tag": still_tags.pop(0) if still_tags else None}
        return d

    def still(t0, t1, key, title, sub, *args, **kw):
        still_tags[:] = ["still", "back"]
        r = orig_still(t0, t1, key, title, sub, *args, **kw)
        still_tags.clear()
        for s in r:
            s["_rec"]["still"] = (key, title, sub)
        return r

    def wrap(name, f):
        def g(*args, **kw):
            d = f(*args, **kw)
            d["_rec"] = {"kind": name, "args": args, "kw": kw}
            return d
        return g

    B.painting_shot, B.still_shot = ps, still
    for n in ("card_shot", "title_card_shot", "map_shot", "dia_mirror_shot", "split_shot"):
        setattr(B, n, wrap(n, getattr(B, n)))

    T = TL2(str(old / "v2" / "timing2.json"))
    shots = B.make(T)

    # -- helpers ----------------------------------------------------------------------------------------------
    regions = {}
    for name in REGION_LABELS:
        v = getattr(B, name)
        regions[name] = {"x": v[0], "y": v[1]}
        if name in REGION_RADII:
            regions[name]["rx"], regions[name]["ry"] = REGION_RADII[name]
        regions[name]["label"] = REGION_LABELS[name]
    by_xy = {(r["x"], r["y"]): n for n, r in regions.items()}

    def point(pt, asset):
        pt = tuple(pt)
        if asset == "A" and pt in by_xy:
            return by_xy[pt]
        return [pt[0], pt[1]]

    def simplify(keys):
        """Ramer-Douglas-Peucker over densely sampled linear keys (the mirror drift track): same path, fewer keys."""
        if len(keys) <= 8 or any(k[4] != "linear" for k in keys[:-1]):
            return keys

        def dev(i, j, k):
            ti, tj, tk = keys[i][0], keys[j][0], keys[k][0]
            p = (tk - ti) / (tj - ti)
            cx = keys[i][1] + (keys[j][1] - keys[i][1]) * p
            cy = keys[i][2] + (keys[j][2] - keys[i][2]) * p
            lz = math.log(keys[i][3]) + (math.log(keys[j][3]) - math.log(keys[i][3])) * p
            z = keys[k][3]
            return max(abs(cx - keys[k][1]) * z, abs(cy - keys[k][2]) * z, abs(lz - math.log(z)) * 960)

        keep = {0, len(keys) - 1}

        def rec(i, j):
            if j - i < 2:
                return
            worst, wk = max((dev(i, j, k), k) for k in range(i + 1, j))
            if worst > 0.3:
                keep.add(wk)
                rec(i, wk)
                rec(wk, j)
        rec(0, len(keys) - 1)
        return [keys[i] for i in sorted(keep)]

    def cam_param(keys, t0, t1, name="shot"):
        dedup = []
        for k in keys:                                          # equal-time keys (a max() tie) are dropped when their values agree
            if dedup and abs(float(k[0]) - float(dedup[-1][0])) < 1e-9:
                if tuple(k[1:4]) != tuple(dedup[-1][1:4]):
                    raise SystemExit("conflicting camera keys at the same time in %s" % name)
                continue
            if dedup and float(k[0]) < float(dedup[-1][0]):         # out-of-order key: the benchmark's Cam never reaches it (closing shot's END key)
                print("note: dropping unreachable camera key at %.2f in %s" % (float(k[0]), name))
                continue
            dedup.append(tuple(k))
        keys = simplify(dedup)
        out = []
        for k in keys:
            t = k[0]
            if abs(float(t) - float(t0)) < 1e-9:
                at = {"rel": 0.0}
            elif abs(float(t) - float(t1)) < 1e-9:
                at = {"rel": 1.0}
            else:
                at = anchor(t)
            out.append({"at": at, "cx": k[1], "cy": k[2], "zoom": round(k[3], 6), "ease": k[4]})
        for x, y in zip(keys[:-1], keys[1:]):
            if float(y[0]) <= float(x[0]):
                raise SystemExit("camera keys not increasing in %s" % name)
        return out

    stats = {"clamped": 0, "start_before_shot": 0}

    def overlay_json(o, shot_t0, shot_t1, shot_asset, n):
        """-> list of overlay dicts for one old overlay object (Years gives several)."""
        nm, args, kw = o.rec
        res = []

        def add(tech, t0, t1, params, note=""):
            t0f, t1f = float(t0), float(t1)
            start = anchor(t0)
            if t0f < float(shot_t0) - 1e-9:                    # starts before the shot: pin to the shot start (spotlight: skip the ramp already elapsed)
                stats["start_before_shot"] += 1
                elapsed = float(shot_t0) - t0f
                if tech == "HI-01":
                    params["ramp_in"] = round(max(0.0, params["ramp_in"] - elapsed), 4)
                else:
                    raise SystemExit("overlay %s starts before its shot" % tech)
                t0f = float(shot_t0)
                start = anchor(shot_t0)
            if t1f > float(shot_t1) + 1e-9:
                stats["clamped"] += 1
                t1f = float(shot_t1)
            res.append({"id": "o%d" % (n + len(res) + 1), "technique": tech, "intent": INTENT_BY_OVERLAY[tech], "start": start, "dur": round(t1f - t0f, 4),
                        "params": params, "locked": False, "source": "import", "note": note})

        if nm == "Lbl":
            title, sub, t0 = args[0], args[1], args[2]
            dur = args[3] if len(args) > 3 else kw.get("dur", 3.2)
            p = dict(LABEL_PINS)
            if sub:
                add("X-ANN-02", t0, t0 + dur, {"title": title, "artist_year": sub, **p})
            else:
                add("X-ANN-01", t0, t0 + dur, {"text": title, **p})
        elif nm == "Spot":
            pt, rx, ry, t0, t1 = args[:5]
            floor, ri, ro = kw.get("floor", B.SPOT_FLOOR), kw.get("ramp_in", .5), kw.get("ramp_out", .5)
            add("HI-01", t0, t1, {"at": point(pt, shot_asset), "rx": rx, "ry": ry, "floor": floor, "ramp_in": ri, "ramp_out": ro})
        elif nm == "RingOv":
            pt, r, t0 = args[:3]
            hold, fade, draw = kw.get("hold", 2.0), kw.get("fade", .4), kw.get("draw", .5)
            add("AN-01", t0, t0 + draw + hold + fade, {"at": point(pt, shot_asset), "radius": r, "draw_s": draw, "hold_s": hold, "fade_s": fade})
        elif nm == "ScreenText":
            text, t0, t1 = args[:3]
            pt, size = kw.get("pt"), kw.get("size", 44)
            p = {"text": text, "size_px": size, "fade_in_s": kw.get("fin", .1), "fade_out_s": kw.get("fout", .15)}
            p["at" if pt is not None else "screen"] = point(pt, shot_asset) if pt is not None else list(kw["screen"])
            add("X-ANN-03" if size >= 40 else "STATIC-08", t0, t1, p)
        elif nm == "DimOv":
            t0, t1, zz = args
            add("AN-05", t0, t1, {"frame_zoom": round(zz, 8), "width_label": "60 cm", "height_label": "82 cm", "medium_caption": "OIL ON OAK PANEL"})
        elif nm == "Years":
            for s, sub, x, t0, t1 in args[0]:
                xp = round(x / 1920 * 100, 2)
                assert int(1920 * xp / 100) == int(x), (x, xp)
                add("STATIC-09", t0, t1, {"year": s, "sub": sub, "x_pct": xp})
        else:
            raise SystemExit("unknown overlay " + nm)
        return res

    def pick_intent(tech, overlays):
        techs = [o["technique"] for o in overlays]
        for t in ("AN-05", "HI-01", "AN-01"):
            if t in techs:
                return INTENT_BY_OVERLAY[t]
        if techs and tech.startswith("CAM"):
            return "point_at"
        return INTENT_BY_TECH[tech]

    # -- shots ------------------------------------------------------------------------------------------------
    assets_used = {}
    sb_shots = []
    for i, s in enumerate(shots):
        r = s["_rec"]
        t0, t1 = s["t0"], s["t1"]
        kind = r["kind"]
        sid = "s%04d" % (i + 1)
        shot = {"id": sid, "start": anchor(t0)}
        overlays = []
        if kind == "painting":
            key = r["key"]
            assets_used.setdefault(key, None)
            if r["tag"] == "still":
                tech = "X-LAY-01"
            elif r["tag"] == "back":
                tech = "STATIC-01"
            else:
                tech = next((x for x in r["ids"] if x.startswith("CAM-") and x != "CAM-02"), "STATIC-01")
            if tech == "X-LAY-01":
                assets_used[key] = r["still"][1:]
            for o in r["overlays"]:
                overlays += overlay_json(o, t0, t1, key, len(overlays))
            shot.update(technique=tech, slots={"image": {"asset": key}}, params={"camera": cam_param(r["keys"], t0, t1, sid)})
        elif kind == "card_shot":
            text = r["args"][2]
            tech = "X-CARD-01"
            shot.update(technique=tech, slots={}, params={"title": text, **CARD_PINS})
        elif kind == "title_card_shot":
            tech = "X-CARD-02"
            assets_used.setdefault("A", None)
            shot.update(technique=tech, slots={"background": {"asset": "A"}}, params={"title": "THE ARNOLFINI PORTRAIT", "artist": "JAN VAN EYCK", "year": "1434"})
        elif kind == "map_shot":
            tech = "STATIC-06"
            shot.update(technique=tech, slots={}, params={"draw_delay_s": round(float(r["args"][2]) - float(t0), 4), **MAP_PINS})
        elif kind == "dia_mirror_shot":
            tech = "DIA-07"
            shot.update(technique=tech, slots={}, params={})
        elif kind == "split_shot":
            tech = "LAY-01"
            t_slide, t_push = r["args"][2], r["args"][3]
            pw, ph = 900, 740
            zl, zv = 0.94 * ph / 6000, max(pw / 4169, ph / 3249)           # mirrors build_v2.split_shot
            fc = B.FULL
            camL = [(t0, fc[0], fc[1], zl, "linear"), (t_push, fc[0], fc[1], zl, "inout_cubic"), (t1, B.RUG[0], B.RUG[1], .30, "linear")]
            camR = [(t0, 4169 / 2, 3249 / 2, zv, "linear"), (t_push, 4169 / 2, 3249 / 2, zv, "inout_cubic"), (t1, 2085, 2780, .55, "linear")]
            assets_used.setdefault("A", None)
            assets_used.setdefault("V", None)
            shot.update(technique=tech, slots={"left": {"asset": "A"}, "right": {"asset": "V"}},
                        params={"camera_left": cam_param(camL, t0, t1, sid), "camera_right": cam_param(camR, t0, t1, sid),
                                "caption_left": "THE ARNOLFINI PORTRAIT", "caption_left_sub": "JAN VAN EYCK, 1434",
                                "caption_right": "VIRGIN AND CHILD WITH CANON VAN DER PAELE", "caption_right_sub": "JAN VAN EYCK, 1434",
                                "slide_delay_s": round(float(t_slide) - float(t0), 4)})
        else:
            raise SystemExit("unknown shot kind " + kind)
        shot["intent"] = pick_intent(tech, overlays)
        shot["transition_in"] = None
        shot["overlays"] = overlays
        shot.update(locked=False, source="import", note=s.get("effect", ""))
        sb_shots.append(shot)

    # -- assets -----------------------------------------------------------------------------------------------
    timeline = json.load(open(old / "timeline.json"))["sources"]
    ctxj = json.load(open(old / "assets" / "context" / "context_images.json"))
    (out / "media").mkdir(parents=True, exist_ok=True)
    assets = {}
    for key in sorted(assets_used, key=lambda k: (k not in ("A", "V"), k)):
        if key in ASSET_FILES:
            src = old / "assets" / "commons" / ASSET_FILES[key]
            fname = ASSET_FILES[key]
            cred = timeline["arnolfini_commons" if key == "A" else "paele_commons"]
            page = cred["url"]
            author, lic = cred["author"], cred["licence"]
        else:
            src = old / "assets" / "context" / (key + ".jpg")
            fname = key + ".jpg"
            c = ctxj[key]
            page, author, lic = c["page"], c.get("author", ""), c["licence"]
        shutil.copy2(src, out / "media" / fname)
        import cv2
        im = cv2.imread(str(out / "media" / fname), cv2.IMREAD_UNCHANGED)
        h, w = im.shape[:2]
        if key in ASSET_META:
            title, artist, year = ASSET_META[key]
        else:
            t_, sub = assets_used[key]
            title = t_
            artist, _, year = (sub or "").rpartition(", ")
            if not artist:
                artist, year = year, ""
        asset = {"file": "media/" + fname, "kind": "image", "title": title, "artist": artist, "year": year, "width": w, "height": h,
                 "credit": {"source": "commons", "source_url": page, "author": author or "unknown", "licence": "PD" if "ublic" in lic else lic, "licence_url": ""}}
        if key == "A":
            asset["regions"] = regions
        assets[key] = asset

    sb = {"schema": "bti.storyboard/1", "project": "arnolfini", "title": "The Arnolfini Portrait", "style": "gae",
          "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json", "audio": "audio/mix.m4a", "assets": assets,
          "shots": sb_shots, "end": {"t": END}, "approvals": {"storyboard": None}}
    out.mkdir(parents=True, exist_ok=True)
    (out / "storyboard.json").write_text(json.dumps(sb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    if not a.no_audio:
        (out / "audio").mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(old / "final_demo.mp4"), "-vn", "-map", "0:a:0", "-c:a", "copy", str(out / "audio" / "mix.m4a")], check=True)
    print("shots %d, overlays %d, assets %d, words %d" % (len(sb_shots), sum(len(s["overlays"]) for s in sb_shots), len(assets), len(words)))
    print("overlay end clamped to shot end: %d; overlay start pinned to shot start: %d" % (stats["clamped"], stats["start_before_shot"]))


if __name__ == "__main__":
    main()
