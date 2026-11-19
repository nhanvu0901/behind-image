"""Renders the KEY-01, NUM-01 and DOC-01 examples (stills with contact sheets, timings, the preview clips and thumbnails) from a lab project it builds in a
temporary folder on the Arnolfini Portrait of `projects/technique_lab` (the picture and the regions the default data of the three techniques is written for).

    python tools/explain/render_examples.py stills OUTDIR      # 1280 px PNGs of every example at its moments, plus one contact sheet per example (times written on it)
    python tools/explain/render_examples.py timing             # milliseconds per frame at 1920 px of the default examples
    python tools/explain/render_examples.py leaders            # for the eight-label example: where every label sits, its distance to its detail, the threshold of `leader` auto
    python tools/explain/render_examples.py preview            # style/gae/previews/KEY-01, NUM-01, DOC-01 (.mp4 640 px 15 fps 7 s, .jpg 480 px)

Run it from the repository root with the engine's Python (numpy, OpenCV, Pillow; ffmpeg on the PATH for `preview`). `--projects DIR` says where `technique_lab` is
(default: `projects/` of the repository).
"""
from __future__ import annotations

import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STILL_W = 1280
DUR = 7.0


def cam(cx0, cy0, z0, cx1=None, cy1=None, z1=None, ease="linear", t_end=None):
    """Two camera keys: (cx0, cy0, z0) at the start, (cx1, cy1, z1) at `t_end` seconds (or at the end of the shot)."""
    cx1, cy1, z1 = cx0 if cx1 is None else cx1, cy0 if cy1 is None else cy1, z0 if z1 is None else z1
    return [{"at": {"rel": 0.0}, "cx": cx0, "cy": cy0, "zoom": z0, "ease": ease}, {"at": {"t": t_end} if t_end is not None else {"rel": 1.0}, "cx": cx1, "cy": cy1, "zoom": z1, "ease": "linear"}]


def lb(text, ref, side, at, style="italic"):
    return {"text": text, "ref": ref, "side": side, "at": at, "style": style}


def rw(label, value, units, count, at):
    return {"label": label, "value": value, "units": units, "count": count, "at": at}


# name -> (technique, params, camera, moments, base technique). Empty params are the default data of the technique (the mock-up's example).
EXAMPLES = {
    "key_default": ("KEY-01", {}, cam(2220, 1410, 0.5), [0.5, 1.2, 2.9, 4.8, 6.7], "CAM-05"),
    "key_crowd": ("KEY-01", {"labels": [lb("Convex mirror", "MIRROR", "auto", 0.5), lb("Latin inscription", "INSCR", "auto", 1.0), lb("First roundel", "R1", "auto", 1.5),
                                         lb("Second roundel", "R2", "auto", 2.0), lb("Amber beads", "AMBER", "auto", 2.5), lb("A brush", "BRUSH", "auto", 3.0),
                                         lb("Saint Martha finial", "STM", "auto", 3.5), lb("Carved creature", "LION", "auto", 4.0)]},
                  cam(2300, 1650, 0.45, 2450, 1850, 0.72), [0.9, 2.2, 3.6, 4.6, 6.0], "CAM-05"),
    "num_default": ("NUM-01", {}, cam(3218, 2987, 0.822), [0.6, 1.5, 3.4, 4.9, 6.7], "CAM-05"),
    "num_four": ("NUM-01", {"rows": [rw("A farm labourer's year", "20", "florins", 10, 0.6), rw("A master mason's year", "60", "florins", 30, 1.6),
                                     rw("A court painter's year", "130", "florins", 40, 2.6), rw("This panel, as a price", "1,000", "florins", 60, 3.6)],
                            "caption": "each dot is two florins", "source": "Source: invented for this demonstration"}, cam(3218, 2987, 0.822), [1.0, 2.0, 3.3, 5.0, 6.7], "CAM-05"),
    "num_one": ("NUM-01", {"rows": [rw("The price in 1486", "$450.3M", "", 0, 1.0)], "caption": "", "source": "Source: Christie's", "cap_pct": 12.0}, cam(2193, 3000, 0.45),
                [0.6, 1.4, 2.0, 4.0, 6.7], "CAM-05"),
    "doc_default": ("DOC-01", {}, cam(2220, 1302.5, 0.7273, 2220, 1455, 1.2, "inout_cubic", 2.6), [0.8, 1.5, 2.6, 3.4, 6.7], "CAM-05"),
    "doc_two": ("DOC-01", {"lit": [{"box": "1850, 1240, 2640, 1330", "at": 1.0, "hold_s": 0}, {"box": "2130, 1345, 2270, 1405", "at": 3.4, "hold_s": 0}],
                           "reading": "Jan van Eyck was here.", "original": "Johannes de eyck fuit hic", "reading_at": 1.8, "pad_px": 36},
                cam(2220, 1330, 0.95, 2220, 1420, 1.35, "inout_cubic", 5.0), [0.8, 1.6, 2.6, 4.4, 5.6], "CAM-05"),
}
PREVIEW = {"KEY-01": "key_default", "NUM-01": "num_default", "DOC-01": "doc_default"}
THUMB_AT = {"KEY-01": 4.8, "NUM-01": 4.9, "DOC-01": 3.4}


def build_lab(dest: Path, projects: Path) -> Path:
    src = projects / "technique_lab"
    sbl = json.loads((src / "storyboard.json").read_text(encoding="utf-8"))
    asset = dict(sbl["assets"]["arn_A"])
    (dest / "media").mkdir(parents=True, exist_ok=True)
    shutil.copy(src / asset["file"], dest / "media" / "arn.jpg")
    asset["file"] = "media/arn.jpg"
    shots, t = [], 0.0
    for name, (tid, params, camera, _times, base) in EXAMPLES.items():
        camera = [dict(k, at={"t": round(t + k["at"]["t"], 3)} if "t" in k["at"] else k["at"]) for k in camera]       # a key's time is written from the start of its shot above
        shots.append({"id": "s_" + name, "start": {"t": round(t, 3)}, "technique": base, "intent": "point_at", "slots": {"image": {"asset": "arn_A"}}, "params": {"camera": camera},
                      "transition_in": None, "locked": False, "source": "agent", "note": name,
                      "overlays": [{"id": "o1", "technique": tid, "intent": "point_at", "start": {"t": round(t, 3)}, "dur": DUR, "params": params, "locked": False, "source": "agent", "note": ""}]})
        t += DUR + 1.0
    sb = {"schema": "bti.storyboard/1", "project": dest.name, "title": "explain examples", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json", "audio": None,
          "assets": {"arn_A": asset}, "shots": shots, "end": {"t": t, "fade_s": 0}, "approvals": {"storyboard": None}}
    (dest / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    words = [{"w": "w%d" % i, "s": round(i * 0.5, 3), "e": round(i * 0.5 + 0.4, 3)} for i in range(int(t * 2) + 10)]
    (dest / "timing.json").write_text(json.dumps({"duration": t + 5, "words": words, "beats": [], "chapters": []}), encoding="utf-8")
    return dest


def starts() -> dict:
    t, out = 0.0, {}
    for name in EXAMPLES:
        out[name] = t
        t += DUR + 1.0
    return out


def open_lab(tmp: str, projects: Path):
    from bti.engine.api import open_project
    p = open_project(build_lab(Path(tmp) / "explainlab", projects))
    bad = [i for i in p.validate() if i["level"] == "error"]
    if bad:
        raise SystemExit("the examples do not validate: %s" % bad[:3])
    return p


def sheet(frames, times, path: Path) -> None:
    import cv2
    import numpy as np
    cols = 3
    cell_w = 640
    cells = []
    for f, t in zip(frames, times):
        c = cv2.resize(f, (cell_w, int(round(f.shape[0] * cell_w / f.shape[1]))), interpolation=cv2.INTER_AREA)
        label = "t = %.1f s" % t
        x1 = c.shape[1] - 6                                      # the time sits in the top right corner: nothing of the overlays lives there
        cv2.rectangle(c, (x1 - 14 * len(label) - 10, 6), (x1, 34), (0, 0, 0), -1)
        cv2.putText(c, label, (x1 - 14 * len(label) - 4, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cells.append(c)
    while len(cells) % cols:
        cells.append(np.zeros_like(cells[0]))
    rows = [np.hstack(cells[i:i + cols]) for i in range(0, len(cells), cols)]
    cv2.imwrite(str(path), np.vstack(rows))


def stills(out: Path, projects: Path) -> None:
    import cv2
    out.mkdir(parents=True, exist_ok=True)
    st = starts()
    with tempfile.TemporaryDirectory() as tmp:
        p = open_lab(tmp, projects)
        for name, (tid, params, camera, times, base) in EXAMPLES.items():
            frames = []
            for t in times:
                f = p.frame_at(st[name] + t, STILL_W)
                cv2.imwrite(str(out / ("%s_%04.1f.png" % (name, t))), f)
                frames.append(f)
            sheet(frames, times, out / ("sheet_%s.png" % name))
            print(name, times, frames[0].shape)


def timing(projects: Path) -> None:
    """Milliseconds per frame at 1920 px (40 frames spread over each example, the first one cold) with the overlay and the same frames of the base shot alone."""
    with tempfile.TemporaryDirectory() as tmp:
        p = open_lab(tmp, projects)
        st = starts()
        sb = p.storyboard()
        plain = json.loads(json.dumps(sb))
        for s in plain["shots"]:
            s["overlays"] = []

        def measure(name):
            ts = [st[name] + 0.25 + k * (6.5 / 40) for k in range(40)]
            t0 = time.perf_counter()
            p.frame_at(ts[0], 1920)
            cold = (time.perf_counter() - t0) * 1000
            ms = []
            for t in ts[1:]:
                t0 = time.perf_counter()
                p.frame_at(t, 1920)
                ms.append((time.perf_counter() - t0) * 1000)
            ms.sort()
            return cold, ms
        for name in EXAMPLES:
            p.use_draft(None)
            cold, ms = measure(name)
            p.use_draft(plain)
            _c, base = measure(name)
            p.use_draft(None)
            print("%-12s first %5.0f ms | median %5.1f  mean %5.1f  p90 %5.1f  max %5.1f ms | base shot alone: median %5.1f ms | the overlay adds about %5.1f ms" % (
                name, cold, statistics.median(ms), statistics.mean(ms), ms[int(0.9 * len(ms))], ms[-1], statistics.median(base), statistics.median(ms) - statistics.median(base)))


def leaders(projects: Path) -> None:
    """For the eight-label example at its moments: per label the side the plan chose, the distance between its box and the edge of its detail's ellipse, the threshold
    of `leader` auto and the strength of the line (0 none .. 1 full)."""
    from bti.engine.techniques import explain_over as X
    st = starts()
    with tempfile.TemporaryDirectory() as tmp:
        p = open_lab(tmp, projects)
        scene = p._scene()
        idx = list(EXAMPLES).index("key_crowd")
        cs = scene.shots[idx]
        r = cs.overlays[0][1]
        for t in EXAMPLES["key_crowd"][3]:
            view = cs.base.view(st["key_crowd"] + t)
            pos = r.layout(view, t)
            print("t = %.1f s" % t)
            for i, (left, base, vis) in sorted(pos.items()):
                lb = r.labels[i]
                sg = r.leader_segment(view, lb, r.arts[i], left, base)
                sides = r.plan(view)
                if sg is None:
                    print("  %-20s side %-2s no segment" % (lb["text"], sides[i]))
                    continue
                gap, thr = sg[4], sg[5]
                print("  %-20s side %-2s gap %5.1f px  threshold %5.1f px  line %.2f" % (lb["text"], sides[i], gap, thr, X.smooth((gap - thr) / (0.5 * thr))))


def preview(projects: Path) -> None:
    import cv2
    dest = ROOT / "style" / "gae" / "previews"
    dest.mkdir(parents=True, exist_ok=True)
    st = starts()
    with tempfile.TemporaryDirectory() as tmp:
        p = open_lab(tmp, projects)
        for tid, name in PREVIEW.items():
            t0 = st[name]
            p.render_range(t0, t0 + DUR, dest / (tid + ".mp4"), 640, 15)
            f = p.frame_at(t0 + THUMB_AT[tid], 480)
            cv2.imwrite(str(dest / (tid + ".jpg")), f, [cv2.IMWRITE_JPEG_QUALITY, 88])
            print(tid, (dest / (tid + ".mp4")).stat().st_size, (dest / (tid + ".jpg")).stat().st_size)


if __name__ == "__main__":
    args = sys.argv[1:]
    projects = ROOT / "projects"
    if "--projects" in args:
        i = args.index("--projects")
        projects = Path(args[i + 1])
        del args[i:i + 2]
    if not args or args[0] not in ("stills", "timing", "preview", "leaders"):
        raise SystemExit(__doc__)
    if args[0] == "stills":
        stills(Path(args[1]) if len(args) > 1 else ROOT / ".scratch" / "compover" / "stills", projects)
    elif args[0] == "timing":
        timing(projects)
    elif args[0] == "leaders":
        leaders(projects)
    else:
        preview(projects)
