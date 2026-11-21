"""`python -m bti.draft.still [workspace] --shot c03:4 -o look/c03_4.jpg [--at 0.5] [--width 640]`

Draws ONE small frame of a compiled shot (chapter id and shot number, counted from 1 in that chapter's file) so that you can look at
your own work. `--at` is where in the shot, 0 = first frame, 1 = last (default 0.5). The compiled shot must be drawable: run `check` first."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="still", description=__doc__.split("\n")[0])
    ap.add_argument("workspace", nargs="?", default=".")
    ap.add_argument("--shot", required=True, help="chapter:number, like c03:4")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--at", type=float, default=0.5)
    ap.add_argument("--width", type=int, default=640)
    a = ap.parse_args(argv)
    from .check import refuse_outside
    bad = refuse_outside(a.workspace, "the workspace path")
    if not bad and a.out:                                   # `-o` is taken from the workspace argument, like the write below
        bad = refuse_outside(os.path.join(a.workspace, a.out), "the output path (-o)")
    if bad:
        return bad
    import cv2
    from .compile import compile_specs
    from .engine import DraftProject, scaled_images
    from .inputs import DraftError
    from .workspace import load_workspace, read_out
    try:
        cid, _, num = a.shot.partition(":")
        n = int(num)
    except ValueError:
        print("ERROR --shot must look like c03:4 (chapter id, colon, shot number from 1)")
        return 2
    try:
        inp, _ = load_workspace(a.workspace)
        res = read_out(a.workspace, inp.in_scope(), inp.picks["assets"])
        assets = dict(inp.picks["assets"])
        assets.update((inp.current or {}).get("assets") or {})
        root = Path(a.workspace).resolve()
        eng = DraftProject(root, {"schema": "bti.storyboard/1", "assets": assets, "shots": [], "end": {"t": 1.0}}, inp.timing)
        try:
            with scaled_images(root, assets):
                out = compile_specs(inp, res.specs, regions=res.regions, spec_problems=res.problems, degrade=False, draw=False, engine=eng)
                idx = out.shot_index(cid, n)
                if idx is None:
                    print("ERROR no shot %s: the compiler has no shot number %d in chapter %s (is the file out/%s.json written and are its shots valid?)" % (a.shot, n, cid, cid))
                    return 2
                o = out.origin[idx]
                t = o["t0"] + min(1.0, max(0.0, a.at)) * (o["t1"] - o["t0"])
                t = min(t, o["t1"] - 0.02)
                eng.use_draft(out.storyboard)
                frame = eng.frame_at(t, max(64, min(1280, a.width)))
        finally:
            eng.close()
    except DraftError as e:
        print("ERROR %s: %s" % (e.code, e.message))
        return 2
    except Exception as e:      # noqa: BLE001
        print("ERROR the shot cannot be drawn: %s: %s" % (type(e).__name__, str(e)[:200]))
        return 1
    dest = Path(a.out or ("look/%s_%d.jpg" % (cid, n)))
    if not dest.is_absolute():
        dest = Path(a.workspace) / dest
    if refuse_outside(dest, "the output path"):             # `-o` is relative to the workspace argument: a workspace below this folder must not reach out of it
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    from bti.engine import viewchecks as VC
    from bti.engine.timing import Timing
    sh = out.storyboard["shots"][idx]
    cam = (sh.get("params") or {}).get("camera") if isinstance(sh.get("params"), dict) else None
    pose = ""
    if isinstance(cam, list) and cam:
        try:
            keys = VC._Ctx(out.storyboard, Timing(inp.timing), eng.bundle, root,
                            [o["t0"] for o in out.origin], float(inp.timing["duration"]), lambda _d, _r: None).keys_of(idx, (o["t0"], o["t1"]))
            if keys:
                cx, cy, z = VC.camera_at(keys, t)
                hw, hh = 1920.0 / (2.0 * z), 1080.0 / (2.0 * z)
                pose = ", frame centre (%.1f, %.1f) zoom %.4f rect [%.0f, %.0f, %.0f, %.0f]" % (cx, cy, z, cx - hw, cy - hh, cx + hw, cy + hh)
        except Exception:       # noqa: BLE001
            pose = ""
    print("wrote %s (shot %s at %.2f s, technique %s%s)" % (dest, a.shot, t, o["technique"], pose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
