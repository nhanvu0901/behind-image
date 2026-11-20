"""One still of every OFFERED technique (the 26 of `style/gae/techniques.json`), drawn by the engine on fixture pictures, and two contact sheets (worker catalogue, 2026-11-20).

    tools/deploy/snapshot_py.sh NAME tests/engine/catalogue_stills.py OUTDIR      (on the Windows server, in a snapshot; OUTDIR is a folder of the snapshot)

The pictures are those of `projects/technique_lab` (the Arnolfini Portrait, the Virgin and Child with Canon van der Paele, a portrait of a man in a turban, a crop of a
detail and its ultraviolet-style version, a clip). Each technique is drawn the way its `use_when` says it is used (a map joins two places, a time axis has three dates, a figure
stands over a picture, an outside picture is shown at its default fit ...). Nothing is written outside OUTDIR; a technique that fails to draw is listed in `report.json`.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from bti.draft.compile import panel_region_camera  # noqa: E402
from bti.engine.api import open_project  # noqa: E402

LAB = REPO / "projects" / "technique_lab"
SHOT_S = 10.0
STEP = 0.5


def build_assets(out: Path) -> dict:
    src = json.loads((LAB / "storyboard.json").read_text(encoding="utf-8"))["assets"]
    keep = {"A": "arn_A", "V": "arn_V", "T": "arn_turban", "D": "diag_D", "U": "diag_UV", "VID": "text_VH"}
    assets = {}
    for new, old in keep.items():
        a = copy.deepcopy(src[old])
        f = LAB / a["file"]
        dst = out / a["file"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        assets[new] = a
    assets["A"]["title"] = "The Arnolfini Portrait"
    assets["A"]["artist"], assets["A"]["year"] = "Jan van Eyck", "1434"
    assets["V"]["title"], assets["V"]["artist"], assets["V"]["year"] = "Virgin and Child with Canon van der Paele", "Jan van Eyck", "1436"
    assets["T"]["title"], assets["T"]["artist"], assets["T"]["year"] = "Portrait of a Man in a Turban", "Jan van Eyck", "1433"
    assets["V"]["regions"] = {"CANON": {"x": 3000, "y": 1700, "rx": 500, "ry": 500, "label": "Canon"}}
    return assets


def main(outdir: str) -> int:
    out = Path(outdir).resolve()
    lab = out / "lab"
    (lab / "media").mkdir(parents=True, exist_ok=True)
    assets = build_assets(lab)
    words = [{"w": "w%d" % i, "s": round(i * STEP, 3), "e": round(i * STEP + 0.4, 3)} for i in range(900)]
    (lab / "timing.json").write_text(json.dumps({"duration": 400.0, "words": words, "beats": [], "chapters": []}), encoding="utf-8")
    skel = {"schema": "bti.storyboard/1", "project": "catalogue", "title": "catalogue", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
            "audio": None, "assets": assets, "shots": [], "end": {"t": 400.0}, "approvals": {"storyboard": None}}
    (lab / "storyboard.json").write_text(json.dumps(skel), encoding="utf-8")
    p = open_project(lab)
    report: dict = {}
    shots: list = []
    frames: dict = {}                 # technique id -> (time of the still, short title)
    counter = {"s": 0}

    def cam(cx, cy, z0, z1=None, e="linear"):
        z1 = z0 if z1 is None else z1
        return [{"at": {"rel": 0.0}, "cx": cx, "cy": cy, "zoom": z0, "ease": e}, {"at": {"rel": 1.0}, "cx": cx, "cy": cy, "zoom": z1, "ease": e}]

    WIDTH_FIT = 1920 / 4386.0            # the Arnolfini fills the screen's width at this zoom
    A_INFO = {"w": 4386.0, "h": 6000.0, "regions": assets["A"]["regions"]}
    Z_FIT = 0.955 * 1080.0 / 6000.0

    def region_cam(tid, name):
        """The camera the draft compiler gives CAM-01, CAM-03 and CAM-05 on a region (bti.draft.compile `region_camera`)."""
        r = A_INFO["regions"][name]
        rx, ry = float(r.get("rx") or 0.08 * A_INFO["w"]), float(r.get("ry") or r.get("rx") or 0.08 * A_INFO["w"])
        z_det = max(Z_FIT * 1.3, min(1920 * 0.5 / (2 * rx), 1080 * 0.5 / (2 * ry), 6.0))
        cx, cy = float(r["x"]), float(r["y"])
        if tid == "CAM-05":
            return [{"at": {"rel": 0.0}, "cx": A_INFO["w"] / 2, "cy": A_INFO["h"] / 2, "zoom": Z_FIT, "ease": "inout_cubic"}, {"at": {"rel": 1.0}, "cx": cx, "cy": cy, "zoom": z_det, "ease": "linear"}]
        z1 = z_det * 0.85
        return cam(cx, cy, z1, z1 * 1.142)

    def base(tid, t0, slots, params=None, overlays=None, transition=None, note=""):
        counter["s"] += 1
        sid = "s%03d" % counter["s"]
        s = {"id": sid, "start": {"t": t0}, "technique": tid, "intent": "explore", "slots": slots, "params": params or {}, "transition_in": transition,
             "overlays": overlays or [], "locked": False, "source": "agent", "note": note}
        shots.append(s)
        return s

    def ov(oid, tid, t, dur, params, slots=None):
        return {"id": oid, "technique": tid, "intent": "point_at", "start": {"t": t}, "dur": dur, "params": params, "slots": slots or {}, "locked": False, "source": "agent", "note": ""}

    def dp(tid, ctx):
        return p.default_params(tid, ctx)

    plan = []                          # (technique id, title, still time, builder)

    def add(tid, title, tf, builder):
        plan.append((tid, title, tf, builder))

    A = {"image": {"asset": "A"}}
    # --- camera
    add("CAM-01", "push-in on the mirror", 9.5, lambda t0: base("CAM-01", t0, {"image": {"asset": "A", "region": "MIRROR"}}, {"camera": region_cam("CAM-01", "MIRROR"), "shadow": True}))
    add("CAM-05", "zoom and shift to the hands", 9.5, lambda t0: base("CAM-05", t0, {"image": {"asset": "A", "region": "HANDS"}}, {"camera": region_cam("CAM-05", "HANDS"), "shadow": True}))
    add("CAM-03", "pull-back to a wide band", 9.0, lambda t0: base("CAM-03", t0, A, {"camera": [{"at": {"rel": 0.0}, "cx": 2220, "cy": 1790, "zoom": 1.1, "ease": "in_quad"},
                                                                                                    {"at": {"rel": 1.0}, "cx": 2193, "cy": 2100, "zoom": WIDTH_FIT, "ease": "linear"}], "shadow": True}))
    add("CAM-04", "pan up the tabard", 5.0, lambda t0: base("CAM-04", t0, {"image": {"asset": "A", "region": "TABARD"}}, {"camera": [{"at": {"rel": 0.0}, "cx": 2193, "cy": 4200, "zoom": WIDTH_FIT, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 2193, "cy": 1900, "zoom": WIDTH_FIT, "ease": "linear"}], "shadow": True}))
    add("STATIC-01", "whole on the matte", 4.0, lambda t0: base("STATIC-01", t0, A, dp("STATIC-01", {"asset": "A"})))
    # --- labels and rings
    add("X-ANN-01", "one-line label", 4.0, lambda t0: base("CAM-01", t0, {"image": {"asset": "A", "region": "AMBER"}}, {"camera": region_cam("CAM-01", "AMBER"), "shadow": True},
                                                              [ov("o1", "X-ANN-01", t0 + 0.5, 5.0, {**dp("X-ANN-01", {}), "text": "AMBER BEADS"})]))
    add("AN-01", "ring around a small roundel", 2.0, lambda t0: base("CAM-01", t0, {"image": {"asset": "A", "region": "MIRROR"}}, {"camera": cam(2220, 1790, 0.9, 1.0), "shadow": True},
                                                                      [ov("o1", "AN-01", t0 + 0.5, 4.5, {**dp("AN-01", {"asset": "A", "region": "R1"}), "at": "R1", "radius": 120})]))
    add("HI-01", "spotlight on the lit candle (wide frame)", 4.0, lambda t0: base("CAM-01", t0, A, {"camera": cam(2193, 1500, WIDTH_FIT), "shadow": True},
                                                                              [ov("o1", "HI-01", t0 + 0.5, 6.0, {**dp("HI-01", {"asset": "A", "region": "LIT"}), "at": "LIT", "rx": 330, "ry": 330, "floor": 0.6})]))
    add("KEY-01", "key of labels", 8.0, lambda t0: base("CAM-01", t0, A, {"camera": cam(2193, 1900, WIDTH_FIT), "shadow": True},
                                                         [ov("o1", "KEY-01", t0 + 0.3, 8.5, {"labels": [
                                                             {"text": "Latin inscription", "ref": "INSCR", "side": "n", "at": 0.5, "style": "italic"},
                                                             {"text": "Amber beads", "ref": "AMBER", "side": "w", "at": 1.5, "style": "italic"},
                                                             {"text": "Convex mirror", "ref": "MIRROR", "side": "e", "at": 2.5, "style": "italic"},
                                                             {"text": "Joined hands", "ref": "HANDS", "side": "s", "at": 3.5, "style": "italic"}]})]))
    add("DOC-01", "a lit line and its reading", 5.5, lambda t0: base("CAM-01", t0, {"image": {"asset": "A", "region": "INSCR"}}, {"camera": cam(2220, 1500, 1.0, 1.1), "shadow": True},
                                                                      [ov("o1", "DOC-01", t0 + 0.3, 8.0, {"lit": [{"ref": "INSCR", "at": 0.6}], "reading": "Jan van Eyck was here. 1434",
                                                                                                          "original": "Johannes de eyck fuit hic · 1434", "reading_at": 1.6})]))
    add("AN-03", "perspective lines", 5.5, lambda t0: base("STATIC-01", t0, A, dp("STATIC-01", {"asset": "A"}),
                                                            [ov("o1", "AN-03", t0 + 0.3, 8.0, {**dp("AN-03", {"asset": "A"}), "vanishing_point": [2193, 2000]})]))
    add("AN-06", "grid and a triangle", 5.5, lambda t0: base("STATIC-01", t0, A, dp("STATIC-01", {"asset": "A"}), [ov("o1", "AN-06", t0 + 0.3, 8.0, dp("AN-06", {"asset": "A"}))]))
    add("AN-05", "ruler: a real size", 4.0, lambda t0: base("STATIC-01", t0, A, {"camera": cam(2193, 3000, 0.9 * Z_FIT, 0.92 * Z_FIT), "shadow": True},
                                                            [ov("o1", "AN-05", t0 + 0.3, 8.0, {**dp("AN-05", {"asset": "A"}), "frame_zoom": 0.9 * Z_FIT, "width_label": "59.7 cm", "height_label": "82.5 cm", "medium_caption": "OIL ON OAK PANEL"})]))
    add("X-ANN-03", "recap labels in the closing", 6.0, lambda t0: base("STATIC-01", t0, A, dp("STATIC-01", {"asset": "A"}), [
        ov("o1", "X-ANN-03", t0 + 0.3, 8.0, {**dp("X-ANN-03", {"asset": "A"}), "text": "HANDS", "at": "HANDS"}),
        ov("o2", "X-ANN-03", t0 + 0.8, 7.5, {**dp("X-ANN-03", {"asset": "A"}), "text": "SIGNATURE", "at": "INSCR"}),
        ov("o3", "X-ANN-03", t0 + 1.3, 7.0, {**dp("X-ANN-03", {"asset": "A"}), "text": "CANDLE", "at": "LIT"})]))
    # --- outside pictures and comparisons
    add("X-LAY-01", "an outside picture at its default fit", 4.0, lambda t0: base("X-LAY-01", t0, {"image": {"asset": "T"}}, dp("X-LAY-01", {"asset": "T"})))
    add("X-ANN-02", "two-line label of another artwork", 4.0, lambda t0: base("X-LAY-01", t0, {"image": {"asset": "T"}}, dp("X-LAY-01", {"asset": "T"}),
                                                                             [ov("o1", "X-ANN-02", t0 + 0.5, 5.0, {**dp("X-ANN-02", {}), "title": "PORTRAIT OF A MAN IN A TURBAN", "artist_year": "JAN VAN EYCK, 1433"})]))
    add("LAY-01", "two panels: a detail and another work", 5.0, lambda t0: base("LAY-01", t0, {"left": {"asset": "A", "region": "MIRROR"}, "right": {"asset": "V"}}, {
        **dp("LAY-01", {"asset": "A", "region": "MIRROR", "asset_right": "V"}), "camera_left": panel_region_camera(A_INFO, "MIRROR", 900, 740), "caption_left": "The Arnolfini Portrait", "caption_left_sub": "Jan van Eyck, 1434",
        "caption_right": "Virgin and Child with Canon van der Paele", "caption_right_sub": "Jan van Eyck, 1436"}))
    add("X-CMP-01", "swap one side of a split", 6.0, lambda t0: base("X-CMP-01", t0, {"anchor": {"asset": "A", "region": "MIRROR"}, "swap_1": {"asset": "V"}, "swap_2": {"asset": "T"}},
                                                                    {**dp("X-CMP-01", {"asset": "A", "region": "MIRROR", "asset_right": "V"}), "camera_anchor": panel_region_camera(A_INFO, "MIRROR", 900, 740), "seconds_per_swap": 4.0}))
    add("FOOT-01", "a clip, full frame", 4.0, lambda t0: base("FOOT-01", t0, {"footage": {"asset": "VID"}}, {**dp("FOOT-01", {}), "label": "A WORKSHOP TODAY"}))
    add("STATE-01", "the same crop in two states", 5.5, lambda t0: base("STATE-01", t0, {"a": {"asset": "D"}, "b": {"asset": "U"}},
                                                                       {**dp("STATE-01", {"asset": "D"}), "label_a": "Colour", "label_b": "Infrared", "holds": "1.5; 4.0; 1.5"}))
    # --- the devices that make one point
    add("MAP-01", "a journey between two places", 9.0, lambda t0: base("MAP-01", t0, {}, {**dp("MAP-01", {}), "region_iso": [], "region_label": "", "sea_names": False, "view_start_width_km": 2400,
        "places": [{"id": "lubeck", "name": "Lübeck", "lonlat": [10.6866, 53.8655], "at": 0.8, "label_side": "auto"}, {"id": "bruges", "name": "Bruges", "lonlat": [3.2247, 51.2093], "at": 3.2, "label_side": "auto"}],
        "route": [{"from": "lubeck", "to": "bruges", "via": "", "shape": "curve", "at": 1.5, "draw_s": 2.0, "head": "dot"}]}))
    add("TIME-01", "three dated events", 9.0, lambda t0: base("TIME-01", t0, {}, {**dp("TIME-01", {}), "items": [
        {"date": 1415, "label": "Born at Baerle", "side": "auto", "at": 0.8, "accent": False}, {"date": 1444, "label": "Citizen of Bruges", "side": "auto", "at": 2.4, "accent": True},
        {"date": 1462, "label": "Joins a brotherhood", "side": "auto", "at": 4.0, "accent": False}], "focus_s": 5.5}))
    add("NUM-01", "a large figure over the thing counted", 6.5, lambda t0: base("CAM-01", t0, {"image": {"asset": "A", "region": "FURSLEEVE"}}, {"camera": cam(3500, 2700, 0.9, 1.0), "shadow": True}, [
        ov("o1", "NUM-01", t0 + 0.3, 8.0, {"rows": [{"label": "An ordinary gown", "value": "600", "units": "pelts", "count": 12, "at": 0.6}, {"label": "This gown", "value": "2,000", "units": "pelts", "count": 40, "at": 2.6}],
                                            "caption": "each dot is fifty squirrel pelts", "source": ""})]))
    add("STATIC-09", "one year, on a calm part of the picture", 4.0, lambda t0: base("X-LAY-01", t0, {"image": {"asset": "T"}}, dp("X-LAY-01", {"asset": "T"}),
                                                                                 [ov("o1", "STATIC-09", t0 + 0.5, 5.0, {**dp("STATIC-09", {}), "year": "1433", "x_pct": 20, "y_pct": 50})]))
    add("TREE-01", "who is tied to whom", 9.0, lambda t0: base("TREE-01", t0, {}, {**dp("TREE-01", {}), "nodes": [
        {"id": "duke", "name": "Philip the Good", "sub": "Duke of Burgundy", "row": -1, "col": -1, "at": 0.5, "strong": True},
        {"id": "jan", "name": "Jan van Eyck", "sub": "painter", "row": -1, "col": -1, "at": 1.5, "strong": True},
        {"id": "gio", "name": "Giovanni Arnolfini", "sub": "merchant", "row": -1, "col": -1, "at": 2.5, "strong": False}],
        "edges": [{"from": "duke", "to": "jan", "kind": "link", "label": "court painter", "at": 1.2}, {"from": "gio", "to": "jan", "kind": "link", "label": "sat for him", "at": 3.0}]}))
    add("TR-01", "a dissolve from a detail to another picture", 7.0, lambda t0: (
        base("CAM-01", t0, {"image": {"asset": "A", "region": "MIRROR"}}, {"camera": cam(2220, 1790, 0.9, 1.0), "shadow": True}),
        base("CAM-01", t0 + 5.0, {"image": {"asset": "V"}}, dp("CAM-01", {"asset": "V"}), transition={"technique": "TR-01", "dur": 4.0, "params": {}})))

    for k, (tid, title, tf, builder) in enumerate(plan):
        t0 = k * SHOT_S
        try:
            builder(t0)
            frames[tid] = (t0 + tf, title)
        except Exception as e:      # noqa: BLE001
            report[tid] = {"stage": "build", "error": "%s: %s" % (type(e).__name__, str(e)[:200])}
    # shots must be in time order and cover the whole range; a gap is filled by a held first shot
    shots.sort(key=lambda s: s["start"]["t"])
    doc = copy.deepcopy(skel)
    doc["shots"] = shots
    doc["end"] = {"t": len(plan) * SHOT_S + 2.0}
    issues = p.validate(doc)
    errors = [i for i in issues if i["level"] == "error"]
    report["_validate_errors"] = [{"path": i["path"], "code": i["code"], "message": i["message"][:200]} for i in errors][:30]
    p.use_draft(doc)
    stills = out / "stills"
    stills.mkdir(exist_ok=True)
    cells = []
    for tid, (t, title) in frames.items():
        try:
            fr = p.frame_at(t, 960)
            cv2.imwrite(str(stills / ("%s.jpg" % tid)), fr, [cv2.IMWRITE_JPEG_QUALITY, 88])
            report.setdefault(tid, {"stage": "drawn", "t": t})
            cells.append((tid, title, fr))
        except Exception as e:      # noqa: BLE001
            report[tid] = {"stage": "draw", "error": "%s: %s" % (type(e).__name__, str(e)[:300])}
    # contact sheets: 3 columns, 5 rows of 640 x 360
    cw, chh, cols, rows = 640, 360, 3, 5
    for n in range(0, len(cells), cols * rows):
        part = cells[n:n + cols * rows]
        sheet = np.full((rows * (chh + 30), cols * cw, 3), 24, np.uint8)
        for i, (tid, title, fr) in enumerate(part):
            r, c = divmod(i, cols)
            y0, x0 = r * (chh + 30), c * cw
            sheet[y0 + 30:y0 + 30 + chh, x0:x0 + cw] = cv2.resize(fr, (cw, chh), interpolation=cv2.INTER_AREA)
            cv2.putText(sheet, "%s  %s" % (tid, title), (x0 + 8, y0 + 21), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (230, 230, 230), 1, cv2.LINE_AA)
        cv2.imwrite(str(out / ("sheet_%d.jpg" % (n // (cols * rows) + 1))), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"drawn": sorted(t for t, r in report.items() if isinstance(r, dict) and r.get("stage") == "drawn"),
                      "failed": {t: r for t, r in report.items() if isinstance(r, dict) and r.get("stage") in ("build", "draw")}, "validate_errors": report["_validate_errors"]},
                     indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "scratch_catalogue"))
