"""Renders the examples of TIME-01, TREE-01 and STATE-01 (stills with contact sheets, timings, the preview clips and thumbnails) from a lab project
that it builds in a temporary folder.

    python tools/explain_base/render_examples.py stills OUTDIR [NAME ...]   # 1280 px PNGs at five moments of each example, one labelled contact sheet each
    python tools/explain_base/render_examples.py timing                      # milliseconds per frame at 1920 px
    python tools/explain_base/render_examples.py preview                     # style/gae/previews/{TIME-01,TREE-01,STATE-01}.mp4 and .jpg (640 px, 15 fps)

Examples: the default data of each technique (the approved mock-up's case: the Arnolfini Portrait) and a second set that stresses it (nine dated items with two
in one year; a tree of three generations with two marriages laid out automatically; two pictures of different pixel sizes with a moving camera). The picture
is the Arnolfini Portrait of `projects/technique_lab/media`; the second state is a copy made here (the mock-up's "infrared" filter: grey, contrast 1.45,
brightness 1.08; and a half-size sepia copy). Run it from the repository root with the engine's Python (numpy, OpenCV, Pillow; ffmpeg on the PATH for `preview`).
"""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PICTURE = "arn__arnolfini_commons.jpg"
CROP = (2650, 950, 1700, 956)                      # the mock-up's crop of the Arnolfini Portrait (x, y, w, h in source pixels)

MEDICI = {
    "nodes": [
        {"id": "cosimo", "name": "Cosimo de' Medici", "sub": "1389 to 1464", "at": 0.5, "strong": True},
        {"id": "contessina", "name": "Contessina de' Bardi", "sub": "about 1400 to 1473", "at": 1.0},
        {"id": "piero", "name": "Piero the Gouty", "sub": "1416 to 1469", "at": 2.0},
        {"id": "lucrezia", "name": "Lucrezia Tornabuoni", "sub": "1425 to 1482", "at": 2.5},
        {"id": "lorenzo", "name": "Lorenzo the Magnificent", "sub": "1449 to 1492", "at": 3.6, "strong": True},
        {"id": "giuliano", "name": "Giuliano", "sub": "1453 to 1478", "at": 4.0},
        {"id": "botticelli", "name": "Sandro Botticelli", "sub": "painter", "at": 5.3},
    ],
    "edges": [
        {"from": "cosimo", "to": "contessina", "kind": "marriage", "label": "married", "at": 1.3},
        {"from": "cosimo", "to": "piero", "kind": "descent", "at": 2.8},
        {"from": "contessina", "to": "piero", "kind": "descent", "at": 2.8},
        {"from": "piero", "to": "lucrezia", "kind": "marriage", "label": "married", "at": 3.0},
        {"from": "piero", "to": "lorenzo", "kind": "descent", "at": 4.2},
        {"from": "lucrezia", "to": "lorenzo", "kind": "descent", "at": 4.2},
        {"from": "piero", "to": "giuliano", "kind": "descent", "at": 4.4},
        {"from": "lorenzo", "to": "botticelli", "kind": "link", "label": "patron of", "at": 5.6},
    ],
}
NINE = [
    (1397, "Medici Bank founded", 0.8), (1429, "Cosimo takes over the bank", 1.6), (1434, "Cosimo returns from exile", 2.4), (1444, "Palazzo Medici begun", 3.2),
    (1464, "Cosimo dies", 4.0), (1469, "Lorenzo takes power", 4.8), (1478, "The Pazzi conspiracy", 5.6), (1492, "Lorenzo dies", 6.4), (1492, "Columbus reaches the Americas", 7.2)]

EXAMPLES = {
    "time_default": {"id": "TIME-01", "dur": 8.0, "params": {}, "times": [0.5, 2.0, 3.8, 5.8, 7.2]},
    "time_nine": {"id": "TIME-01", "dur": 9.0, "times": [0.6, 2.7, 4.6, 6.6, 8.6], "params": {
        "items": [{"date": d, "label": t, "side": "auto", "at": a, "accent": i == 6} for i, (d, t, a) in enumerate(NINE)], "focus_s": 7.8}},
    "tree_default": {"id": "TREE-01", "dur": 8.0, "params": {}, "times": [0.9, 2.2, 3.6, 5.4, 7.2]},
    "tree_medici": {"id": "TREE-01", "dur": 8.0, "params": MEDICI, "times": [1.2, 2.6, 3.8, 5.0, 7.0]},
    "state_default": {"id": "STATE-01", "dur": 7.5, "slots": {"a": "colour", "b": "infrared"}, "times": [0.8, 2.0, 3.8, 5.5, 6.8],
                      "params": {"camera": [{"at": {"rel": 0}, "cx": CROP[0] + CROP[2] / 2, "cy": CROP[1] + CROP[3] / 2, "zoom": 1920 / CROP[2], "ease": "linear"},
                                            {"at": {"rel": 1}, "cx": CROP[0] + CROP[2] / 2, "cy": CROP[1] + CROP[3] / 2, "zoom": 1920 / CROP[2], "ease": "linear"}]}},
    "state_moving": {"id": "STATE-01", "dur": 9.0, "slots": {"a": "colour", "b": "sepia_half"}, "times": [0.8, 2.5, 4.2, 6.0, 8.2],
                     "params": {"first": "b", "label_a": "Photograph", "label_b": "Sepia copy at half size", "dissolve_s": 1.5, "holds": "1.5; 2.5; 2.0",
                                "camera": [{"at": {"rel": 0}, "cx": 2200, "cy": 1500, "zoom": 0.45, "ease": "inout_cubic"},
                                           {"at": {"rel": 0.6}, "cx": 2300, "cy": 1700, "zoom": 0.9, "ease": "inout_cubic"},
                                           {"at": {"rel": 1}, "cx": 2300, "cy": 1700, "zoom": 0.9, "ease": "linear"}]}},
}


def find_picture() -> Path:
    for base in (ROOT / "projects" / "technique_lab" / "media", ROOT.parent.parent / "projects" / "technique_lab" / "media"):
        if (base / PICTURE).is_file():
            return base / PICTURE
    raise SystemExit("the picture %s of projects/technique_lab/media was not found" % PICTURE)


def make_media(dest: Path) -> dict:
    """The colour picture, an infrared-like copy of it and a half-size sepia copy; returns the assets of the storyboard."""
    import cv2
    import numpy as np
    media = dest / "media"
    media.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(find_picture()), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    cv2.imwrite(str(media / "colour.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    g = np.clip(((g - 0.5) * 1.45 + 0.5) * 1.08, 0, 1)
    cv2.imwrite(str(media / "infrared.jpg"), cv2.cvtColor((g * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    half = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA).astype(np.float32)
    gray = half.mean(axis=2, keepdims=True) / 255.0
    sepia = np.clip(gray * np.array([0.62, 0.80, 1.05], np.float32) * 255.0 * 1.1, 0, 255).astype(np.uint8)
    cv2.imwrite(str(media / "sepia_half.jpg"), sepia, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cr = {"source": "test", "source_url": "", "author": "Jan van Eyck", "licence": "PD", "licence_url": ""}
    return {"colour": {"file": "media/colour.jpg", "kind": "image", "title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434", "width": w, "height": h, "credit": cr},
            "infrared": {"file": "media/infrared.jpg", "kind": "image", "title": "Infrared (made for the example)", "width": w, "height": h, "credit": cr},
            "sepia_half": {"file": "media/sepia_half.jpg", "kind": "image", "title": "Sepia copy at half size", "width": w // 2, "height": h // 2, "credit": cr}}


def build_lab(dest: Path, names: list, with_media: bool = True) -> tuple:
    """A lab project with one shot per example (10 s apart); returns (path, {name: start})."""
    dest.mkdir(parents=True, exist_ok=True)
    assets = make_media(dest) if with_media else {}
    shots, starts, t = [], {}, 0.0
    for name in names:
        e = EXAMPLES[name]
        starts[name] = t
        shots.append({"id": "s_" + name, "start": {"t": t}, "technique": e["id"], "intent": "context", "slots": {k: {"asset": v} for k, v in (e.get("slots") or {}).items()},
                      "params": e["params"], "transition_in": None, "overlays": [], "locked": False, "source": "agent", "note": "%s %s" % (e["id"], name)})
        t += e["dur"] + 2.0
    sb = {"schema": "bti.storyboard/1", "project": dest.name, "title": "explain_base examples", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
          "audio": None, "assets": assets, "shots": shots, "end": {"t": t, "fade_s": 0}, "approvals": {"storyboard": None}}
    (dest / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    words = [{"w": "w%d" % i, "s": round(i * 0.5, 3), "e": round(i * 0.5 + 0.4, 3)} for i in range(int(t * 2) + 2)]
    (dest / "timing.json").write_text(json.dumps({"duration": t, "words": words, "beats": [], "chapters": []}), encoding="utf-8")
    return dest, starts


def sheet(frames: list, title: str, times: list):
    """A contact sheet: the frames in rows of three, each labelled with its time, the title on top."""
    import cv2
    import numpy as np
    cw, ch = 640, 360
    cols = 3
    rows = (len(frames) + cols - 1) // cols
    out = np.full((rows * (ch + 28) + 34, cols * cw + (cols + 1) * 6, 3), 24, np.uint8)
    cv2.putText(out, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (230, 230, 230), 1, cv2.LINE_AA)
    for k, (f, t) in enumerate(zip(frames, times)):
        r, c = divmod(k, cols)
        x, y = 6 + c * (cw + 6), 34 + r * (ch + 28)
        out[y + 24:y + 24 + ch, x:x + cw] = cv2.resize(f, (cw, ch), interpolation=cv2.INTER_AREA)
        cv2.putText(out, "t = %.1f s" % t, (x, y + 17), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    return out


def stills(out: Path, names: list) -> None:
    import cv2
    from bti.engine.api import open_project
    names = names or list(EXAMPLES)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        lab, starts = build_lab(Path(tmp) / "explainlab", names)
        p = open_project(lab)
        bad = [i for i in p.validate() if i["level"] == "error"]
        if bad:
            raise SystemExit("the examples do not validate: %s" % bad[:3])
        for name in names:
            e = EXAMPLES[name]
            frames = []
            for t in e["times"]:
                f = p.frame_at(starts[name] + t, 1280)
                cv2.imwrite(str(out / ("%s_%04.1f.png" % (name, t))), f)
                frames.append(f)
                print(name, t, f.shape)
            cv2.imwrite(str(out / ("sheet_%s.png" % name)), sheet(frames, "%s  %s" % (e["id"], name), e["times"]))


def timing() -> None:
    import numpy as np
    from bti.engine.api import open_project
    with tempfile.TemporaryDirectory() as tmp:
        lab, starts = build_lab(Path(tmp) / "explainlab", list(EXAMPLES))
        p = open_project(lab)
        for name, e in EXAMPLES.items():
            ts = [starts[name] + 0.2 + k * ((e["dur"] - 0.4) / 40) for k in range(40)]
            t0 = time.perf_counter()
            p.frame_at(ts[0], 1920)
            cold = (time.perf_counter() - t0) * 1000
            ms = []
            for t in ts[1:]:
                t0 = time.perf_counter()
                p.frame_at(t, 1920)
                ms.append((time.perf_counter() - t0) * 1000)
            print("%-14s cold %.0f ms | warm 1920 px: median %.1f, mean %.1f, p90 %.1f, max %.1f ms" % (name, cold, statistics.median(ms), statistics.fmean(ms), float(np.percentile(ms, 90)), max(ms)))


def preview() -> None:
    import cv2
    from bti.engine.api import open_project
    dest = ROOT / "style" / "gae" / "previews"
    for tid, name, thumb_t in (("TIME-01", "time_default", 7.0), ("TREE-01", "tree_default", 7.0), ("STATE-01", "state_default", 3.2)):
        with tempfile.TemporaryDirectory() as tmp:
            lab, starts = build_lab(Path(tmp) / "explainlab", [name])
            p = open_project(lab)
            p.render_range(0, EXAMPLES[name]["dur"], dest / (tid + ".mp4"), width=640, fps=15)
            cv2.imwrite(str(dest / (tid + ".jpg")), p.frame_at(thumb_t, 480), [cv2.IMWRITE_JPEG_QUALITY, 88])
            print("wrote", dest / (tid + ".mp4"), dest / (tid + ".jpg"))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "stills" and len(sys.argv) > 2:
        stills(Path(sys.argv[2]), sys.argv[3:])
    elif mode == "timing":
        timing()
    elif mode == "preview":
        preview()
    else:
        raise SystemExit(__doc__)
