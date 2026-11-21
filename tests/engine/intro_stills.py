"""Stills and the preview clip of ID-BRAND-03 (the channel-name beat that also writes the video's title), drawn on real paintings of the
reference projects. Run it on the Windows server in a snapshot (never on the Mac); it writes only under OUTDIR, a folder of the snapshot:

    tools/deploy/snapshot_py.sh NAME tests/engine/intro_stills.py OUTDIR            # contact sheet and full frames
    tools/deploy/snapshot_py.sh NAME tests/engine/intro_stills.py OUTDIR preview    # also style/gae-ready ID-BRAND-03.mp4 and .jpg (640 px, 30 fps, 9.1 s)

The pictures come from `projects/technique_lab` (the Arnolfini Portrait and the Virgin and Child with Canon van der Paele); the camera is
the one the identity applier writes for a beat: the whole painting at the fitted size with a 3 % push over the shot.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from bti.engine.api import open_project  # noqa: E402
from bti.engine.techniques.camera import fit_zoom  # noqa: E402

LAB = REPO / "projects" / "technique_lab"
TITLE = "The Saint Who Was Also an Advertisement"
SUB = "St. Eligius · Petrus Christus, 1449"
TITLE_ARN = "The Mirror in the Arnolfini Portrait"
SUB_ARN = "The Arnolfini Portrait \u00b7 Jan van Eyck, 1434"
TITLE70 = "The Goldsmith, the Bride and the Mirror That Saw Everything Behind Her"      # 70 characters
NOMINAL = 9.1
assert len(TITLE70) == 70


def camera_of(asset):
    w, h = float(asset["width"]), float(asset["height"])
    z = fit_zoom(h)
    key = lambda rel, zz: {"at": {"rel": rel}, "cx": round(w / 2, 2), "cy": round(h / 2, 2), "zoom": round(zz, 5), "ease": "linear"}
    return [key(0.0, z), key(1.0, z * 1.03)]


def build(out: Path):
    """One lab with the shots to draw; returns (project, {name: (start, length)})."""
    lab = out / "lab"
    if lab.exists():
        shutil.rmtree(lab)
    (lab / "media").mkdir(parents=True)
    src = json.loads((LAB / "storyboard.json").read_text(encoding="utf-8"))["assets"]
    assets = {}
    for key in ("arn_A", "arn_V"):
        a = dict(src[key])
        shutil.copyfile(LAB / a["file"], lab / a["file"])
        assets[key] = a
    shots, plan, t = [], {}, 0.0

    def add(name, asset, length, params):
        nonlocal t
        shots.append({"id": name, "start": {"t": round(t, 3)}, "technique": "ID-BRAND-03" if params is not None else "CAM-01", "intent": "structure",
                      "slots": {"image": {"asset": asset}}, "params": dict(params or {}, camera=camera_of(assets[asset])), "transition_in": None,
                      "overlays": [], "locked": False, "source": "agent", "note": name})
        plan[name] = (t, length)
        t += length

    add("paele", "arn_V", NOMINAL, {"title": TITLE, "subtitle": SUB})
    add("paele70", "arn_V", NOMINAL, {"title": TITLE70, "subtitle": SUB})
    add("paele_alone", "arn_V", 4.5, {})
    add("arn", "arn_A", NOMINAL, {"title": TITLE_ARN, "subtitle": SUB_ARN})
    add("arn_title_only", "arn_A", NOMINAL, {"title": TITLE_ARN})
    add("end", "arn_A", 3.0, None)
    sb = {"schema": "bti.storyboard/1", "project": "intro", "title": "intro", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
          "audio": None, "assets": assets, "shots": shots, "end": {"t": round(t, 3), "fade_s": 0}, "approvals": {"storyboard": None}}
    (lab / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    words = [{"w": "w%d" % i, "s": round(i * 0.5, 3), "e": round(i * 0.5 + 0.4, 3)} for i in range(120)]
    (lab / "timing.json").write_text(json.dumps({"duration": 90.0, "words": words, "beats": [], "chapters": []}), encoding="utf-8")
    p = open_project(lab)
    bad = [i for i in p.validate() if i["level"] == "error"]
    assert not bad, bad
    return p, plan


def label(img, text):
    cv2.putText(img, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def contact(p, start, name, out: Path, n=12, cols=4):
    times = np.linspace(0.1, NOMINAL - 0.1, n)
    tiles = []
    for tau in times:
        f = p.frame_at(start + float(tau), 960)
        tiles.append(label(cv2.resize(f, (480, 270), interpolation=cv2.INTER_AREA), "%.2f s" % tau))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, n, cols)]
    cv2.imwrite(str(out / name), np.vstack(rows))
    return [round(float(x), 2) for x in times]


def main(argv):
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    p, plan = build(out)
    shot = lambda name, tau, width=1920: p.frame_at(plan[name][0] + tau, width)
    written = []

    def save(name, img):
        cv2.imwrite(str(out / name), img)
        written.append(name)

    print("contact sheet at", contact(p, plan["paele"][0], "contact_sheet_paele.png", out))
    written.append("contact_sheet_paele.png")
    save("still_name_alone.png", shot("paele", 4.3))
    save("still_second_sweep_mid.png", shot("paele", 5.3))
    save("still_final_hold.png", shot("paele", 8.9))
    save("still_final_hold_70chars.png", shot("paele70", 8.9))
    save("still_no_line_name_alone.png", shot("paele_alone", 4.0))
    save("still_arnolfini_second_sweep_mid.png", shot("arn", 5.3))
    save("still_arnolfini_final_hold.png", shot("arn", 8.9))
    save("still_arnolfini_title_only_final.png", shot("arn_title_only", 8.9))
    save("still_first_sweep_mid.png", shot("paele", 1.3))
    if "preview" in argv:
        # the preview of the registry: the Arnolfini Portrait, a title and a small line, 640 px, 30 fps, the whole 9.1 s; the thumbnail is the final hold
        a0, _ = plan["arn"]
        p.render_range(a0, a0 + NOMINAL - 1e-3, out / "ID-BRAND-03.mp4", width=640, fps=30)
        cv2.imwrite(str(out / "ID-BRAND-03.jpg"), p.frame_at(a0 + 7.0, 640), [cv2.IMWRITE_JPEG_QUALITY, 88])
        written += ["ID-BRAND-03.mp4", "ID-BRAND-03.jpg"]
    for w in written:
        print("wrote", out / w, (out / w).stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
