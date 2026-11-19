"""Renders the MAP-01 examples (stills, timings, the preview clip and thumbnail) from a lab project it builds in a temporary folder.

    python tools/geo/render_map_examples.py stills OUTDIR            # 1280 px PNGs of the default example (both sea presets), the Oslo fjord, France and Venice to Constantinople
    python tools/geo/render_map_examples.py timing                   # milliseconds per frame at 1920 px, per example and per stage
    python tools/geo/render_map_examples.py preview                  # style/gae/previews/MAP-01.mp4 and .jpg (640 px, 15 fps, 8 s)

The examples are the ones the build contract asks for (docs/design/2026-11-18-explainer-components.md section 4): the default data is
Bruges to Lucca with Belgium; the others prove that the map is not a one-map trick: a regional view (the Oslo fjord, 400 km), a large country (France) and a long sea route (Venice to Constantinople, with `via` points in open water). Run it from the repository root with the engine's
Python (numpy, OpenCV, Pillow, ffmpeg on the PATH for `preview`).
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

EXAMPLES = {
    "default": {"start": 0.0, "params": {}, "times": [0.3, 1.4, 2.6, 4.2, 6.4, 7.6]},
    "sepia": {"start": 10.0, "params": {"sea": "sepia"}, "times": [0.3, 1.4, 2.6, 4.2, 6.4, 7.6]},
    "fjord": {"start": 20.0, "times": [0.4, 1.2, 2.5, 4.0, 5.5, 7.0], "params": {
        "places": [{"id": "oslo", "name": "Oslo", "lonlat": [10.7522, 59.9139], "at": 0.8, "label_side": "auto"},
                   {"id": "tonsberg", "name": "Tønsberg", "lonlat": [10.4076, 59.2675], "at": 2.0, "label_side": "auto"}],
        "route": [], "region_iso": [], "region_label": "", "view_start_width_km": 900, "view_end_mode": "manual", "view_end_center": "10.6, 59.6",
        "view_end_width_km": 400, "push_s": 5.0, "graticule_deg": 0.5}},
    "venice": {"start": 30.0, "times": [0.4, 1.5, 3.0, 4.5, 6.0, 8.0], "params": {
        "places": [{"id": "venice", "name": "Venice", "lonlat": [12.3155, 45.4408], "at": 0.8, "label_side": "auto"},
                   {"id": "istanbul", "name": "Constantinople", "lonlat": [28.9784, 41.0082], "at": 2.0, "label_side": "auto"}],
        "route": [{"from": "venice", "to": "istanbul", "via": "16.43, 42.56; 18.59, 40.40; 18.72, 39.47; 21.68, 36.49; 22.89, 35.96; 26.07, 36.26; 26.27, 36.97; 25.32, 38.42; 25.32, 39.38; 25.94, 39.94; 27.2, 40.4; 28.3, 40.8", "shape": "curve", "at": 2.4, "draw_s": 3.5, "head": "dot"}],
        "region_iso": [], "region_label": "", "view_start_width_km": 4200, "push_s": 6.0}},
    "france": {"start": 40.0, "times": [0.4, 1.6, 3.0, 4.5, 6.0, 7.5], "params": {
        "places": [{"id": "paris", "name": "Paris", "lonlat": [2.3522, 48.8566], "at": 0.8, "label_side": "auto"},
                   {"id": "lyon", "name": "Lyon", "lonlat": [4.8357, 45.764], "at": 2.0, "label_side": "auto"}],
        "route": [{"from": "paris", "to": "lyon", "via": "", "shape": "straight", "at": 2.6, "draw_s": 2.0, "head": "dot"}],
        "region_iso": ["FR"], "region_label": "France", "region_at": 0.4, "view_start_width_km": 2600, "view_end_mode": "manual", "view_end_center": "2.5, 46.5",
        "view_end_width_km": 1800, "push_s": 4.0}},
}


def build_lab(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    shots = [{"id": "s_" + k, "start": {"t": e["start"]}, "technique": "MAP-01", "intent": "context", "slots": {}, "params": e["params"], "transition_in": None,
              "overlays": [], "locked": False, "source": "agent", "note": "MAP-01 " + k} for k, e in EXAMPLES.items()]
    sb = {"schema": "bti.storyboard/1", "project": dest.name, "title": "MAP-01 examples", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
          "audio": None, "assets": {}, "shots": shots, "end": {"t": 10.0 * len(shots), "fade_s": 0}, "approvals": {"storyboard": None}}
    (dest / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    words = [{"w": "w%d" % i, "s": round(i * 0.5, 3), "e": round(i * 0.5 + 0.4, 3)} for i in range(100)]
    (dest / "timing.json").write_text(json.dumps({"duration": 10.0 * len(shots), "words": words, "beats": [], "chapters": []}), encoding="utf-8")
    return dest


def stills(out: Path) -> None:
    import cv2
    from bti.engine.api import open_project
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        p = open_project(build_lab(Path(tmp) / "maplab"))
        bad = [i for i in p.validate() if i["level"] == "error"]
        if bad:
            raise SystemExit("the examples do not validate: %s" % bad[:3])
        for name, e in EXAMPLES.items():
            for t in e["times"]:
                f = p.frame_at(e["start"] + t, 1280)
                cv2.imwrite(str(out / ("%s_%04.1f.png" % (name, t))), f)
                print(name, t, f.shape)


def timing() -> None:
    import numpy as np
    from bti.engine.api import open_project
    with tempfile.TemporaryDirectory() as tmp:
        p = open_project(build_lab(Path(tmp) / "maplab"))
        for name, e in EXAMPLES.items():
            ts = [e["start"] + 0.25 + k * (9.5 / 40) for k in range(40)]
            t0 = time.perf_counter()
            p.frame_at(ts[0], 1920)
            cold = (time.perf_counter() - t0) * 1000
            ms = []
            for t in ts[1:]:
                t0 = time.perf_counter()
                p.frame_at(t, 1920)
                ms.append((time.perf_counter() - t0) * 1000)
            r = p._scene().shots[[s["id"] for s in p._saved["shots"]].index("s_" + name)].base
            base = []
            for t in ts[1:21]:
                view = r.view_at(t - e["start"])
                k = r.scale_k(view)
                t0 = time.perf_counter()
                r.base.draw(view, k)
                base.append((time.perf_counter() - t0) * 1000)
            print("%-8s cold %.0f ms | warm 1920 px: median %.1f, mean %.1f, p90 %.1f, max %.1f ms | the map itself (land, sea, lines): median %.1f ms"
                  % (name, cold, statistics.median(ms), statistics.fmean(ms), float(np.percentile(ms, 90)), max(ms), statistics.median(base)))


def preview() -> None:
    import cv2
    from bti.engine.api import open_project
    dest = ROOT / "style" / "gae" / "previews"
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "maplab"
        d.mkdir()
        sb = {"schema": "bti.storyboard/1", "project": "maplab", "title": "MAP-01", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
              "audio": None, "assets": {}, "shots": [{"id": "s1", "start": {"t": 0.0}, "technique": "MAP-01", "intent": "context", "slots": {}, "params": {}, "transition_in": None,
                                                     "overlays": [], "locked": False, "source": "agent", "note": "MAP-01 preview"}], "end": {"t": 8.0, "fade_s": 0}, "approvals": {"storyboard": None}}
        (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
        (d / "timing.json").write_text(json.dumps({"duration": 8.0, "words": [], "beats": [], "chapters": []}), encoding="utf-8")
        p = open_project(d)
        p.render_range(0, 8, dest / "MAP-01.mp4", width=640, fps=15)
        cv2.imwrite(str(dest / "MAP-01.jpg"), p.frame_at(5.6, 480), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("wrote", dest / "MAP-01.mp4", dest / "MAP-01.jpg")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "stills" and len(sys.argv) > 2:
        stills(Path(sys.argv[2]))
    elif mode == "timing":
        timing()
    elif mode == "preview":
        preview()
    else:
        raise SystemExit(__doc__)
