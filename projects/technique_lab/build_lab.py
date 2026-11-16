#!/usr/bin/env python3
"""Build projects/technique_lab/: one ~6 s shot per registry technique (registry order), cloned from the real exemplars in
projects/arnolfini and projects/lab_*. Times are rewritten to absolute seconds on the new timeline; media are hard-linked (or copied).

    .venv-engine/bin/python projects/technique_lab/build_lab.py
"""
import copy, json, os, shutil, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.dont_write_bytecode = True
from bti.engine.api import open_project  # noqa: E402
from bti.engine import registry as R, storyboard as SB  # noqa: E402

OUT = Path(__file__).resolve().parent
SOURCES = [("arn", "arnolfini"), ("annot", "lab_annot"), ("diag", "lab_diagrams"), ("lay", "lab_layouts"), ("text", "lab_text")]
SLOT_DUR = 6.0

bundle = R.load_bundle("gae")
projs = {tag: open_project(REPO / "projects" / d) for tag, d in SOURCES}
resolved = {tag: p.resolve() for tag, p in projs.items()}

# exemplars: technique id -> (tag, shot index, overlay index | None, 'shot'|'overlay'|'transition')
ex = {}
for tag, _ in SOURCES:
    for si, s in enumerate(resolved[tag]["shots"]):
        d = s["_t1"] - s["_t0"]
        for kind, tid, oi in [("shot", s["technique"], None)] + [("overlay", o["technique"], j) for j, o in enumerate(s["overlays"])] + \
                ([("transition", s["transition_in"]["technique"], None)] if s.get("transition_in") else []):
            better = tid not in ex or (ex[tid][0] != "arn" and tag == "arn") or (ex[tid][0] == tag and abs(d - SLOT_DUR) < ex[tid][4])
            if better and not (tid in ex and ex[tid][0] == "arn" and tag != "arn"):
                ex[tid] = (tag, si, oi, kind, abs(d - SLOT_DUR))

assets, shots, start = {}, [], 0.0
media = OUT / "media"


def import_asset(tag, key):
    src = resolved[tag]["assets"][key]
    nk = "%s_%s" % (tag, key)
    if nk not in assets:
        a = copy.deepcopy(src)
        base = os.path.basename(a["file"])
        target = media / ("%s__%s" % (tag, base))
        sp = (REPO / "projects" / dict(SOURCES)[tag] / a["file"]).resolve()
        if not target.exists():
            try:
                os.link(sp, target)
            except OSError:
                shutil.copy2(sp, target)
        a["file"] = "media/" + target.name
        if a.get("aligned_to"):
            a["aligned_to"] = "%s_%s" % (tag, a["aligned_to"])
        assets[nk] = a
    return nk


def clone(tag, shot, new0, keep_ov, scale, tech_name):
    s0 = shot["_t0"]

    def conv(o):
        if isinstance(o, dict):
            if "_t" in o and any(k in o for k in ("t", "w", "rel")):
                return {"rel": o["rel"]} if "rel" in o else {"t": round(new0 + (o["_t"] - s0) * scale, 4)}
            r = {k: conv(v) for k, v in o.items() if not k.startswith("_")}
            if isinstance(o.get("asset"), str) and o["asset"] in resolved[tag]["assets"]:      # slot reference (shot or overlay slots)
                r["asset"] = import_asset(tag, o["asset"])
            return r
        if isinstance(o, list):
            return [conv(v) for v in o]
        return o
    n = conv({k: v for k, v in shot.items() if k not in ("overlays",)})
    n["overlays"] = []
    for j, o in enumerate(shot["overlays"]):
        if keep_ov == j:
            c = conv(o)
            if "dur" in c:
                c["dur"] = round(c["dur"] * scale, 4)
            n["overlays"].append(c)
    n["start"] = {"t": round(new0, 4)}
    n.update(locked=False, source="import", note=tech_name)
    return n


missing = []
for t in bundle.techniques:
    tid = t["id"]
    name = "%s %s" % (tid, t["name"])
    if tid not in ex:
        if t["kind"] in ("transition", "overlay") and "STATIC-01" in ex:     # generic: a held painting shot carrying the technique
            tag, si, _, _, _ = ex["STATIC-01"]
            sh = resolved[tag]["shots"][si]
            d = sh["_t1"] - sh["_t0"]
            dur = d if 3.0 <= d <= 9.0 else SLOT_DUR
            n = clone(tag, sh, start, None, dur / d, name)
            n["id"] = "s%04d" % (len(shots) + 1)
            ctx = {"asset": "%s_A" % tag if False else {"key": "arn_A", "w": 4386, "h": 6000, "title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434", "regions": {}}}
            params = projs["arn"].default_params(tid, {"asset": "A", "region": "MIRROR"})
            if t["kind"] == "transition":
                n["transition_in"] = {"technique": tid, "dur": 0.0 if t["timing"]["default_s"] in (0, None) or tid in ("TR-04", "X-TR-01") else 1.0, "params": params}
            else:
                n["transition_in"] = None
                n["overlays"] = [{"id": "o1", "technique": tid, "intent": t["intents"][0], "start": {"t": round(start + 1.0, 4)}, "dur": round(dur - 2.0, 4),
                                  "params": params, "locked": False, "source": "import", "note": ""}]
            shots.append(n)
            start += dur
            continue
        missing.append(tid)
        continue
    tag, si, oi, kind, _ = ex[tid]
    shot = resolved[tag]["shots"][si]
    d = shot["_t1"] - shot["_t0"]
    dur = d if 3.0 <= d <= 9.0 else SLOT_DUR
    n = clone(tag, shot, start, oi, dur / d, name)
    n["id"] = "s%04d" % (len(shots) + 1)
    if kind == "transition":
        pass                                   # keeps its transition_in, no overlays
    elif kind == "shot":
        n["overlays"] = []
        n["transition_in"] = None
    else:
        n["transition_in"] = None
        n["overlays"][0]["id"] = "o1"
    if kind != "transition":
        n["transition_in"] = None if kind != "transition" else n.get("transition_in")
    shots.append(n)
    start += dur

if missing:
    print("NO EXEMPLAR for:", missing)

sb = {"schema": "bti.storyboard/1", "project": "technique_lab", "title": "Technique lab: every technique once", "style": "gae",
      "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json", "audio": None, "assets": assets, "shots": shots,
      "end": {"t": round(start, 4), "fade_s": 0}, "approvals": {"storyboard": None}}
shutil.copy2(REPO / "projects" / "arnolfini" / "timing.json", OUT / "timing.json")
(OUT / "storyboard.json").write_text(json.dumps(sb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("shots %d, assets %d, total %.1f s" % (len(shots), len(assets), start))
