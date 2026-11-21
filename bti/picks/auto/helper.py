"""The two helper commands of the agent's work folder (`./check` and `./crop`, one-line wrappers around this module; the folder is the
current directory).

    check                                   validate out/plan.json (or out/choice.json) the way the program will, in plain sentences
    crop --box x0,y0,x1,y1 -o look/x.jpg    cut a box (fractions of the painting) out of the main painting and write it, to look at it
    crop --grid -o look/grid.jpg            the main painting with a labelled grid, to read positions off as fractions

Nothing here reaches outside the work folder: every output path is checked the way the storyboard draft's helpers check theirs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import images, shapes, tighten

MODE_FILE = "inputs/context.json"


def load_context(root: Path) -> tuple[str, dict]:
    f = Path(root) / MODE_FILE
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        mode = d["mode"]
        if mode not in ("plan", "choose", "tighten"):
            raise KeyError(mode)
        return mode, d
    except (OSError, ValueError, KeyError):
        raise SystemExit("ERROR this is not a picks work folder (inputs/context.json is missing or unreadable)")


def out_file(root: Path, mode: str) -> Path:
    names = {"plan": "plan.json", "choose": "choice.json", "tighten": "tighten.json"}
    return Path(root) / "out" / names[mode]


def run_check(root: Path, *, allow_unconfirmed: bool = False) -> shapes.Report:
    """The report of the work folder's output file. The session uses this too (the repair message is its text)."""
    mode, ctx = load_context(root)
    obj, problem = shapes.read_json_file(out_file(root, mode), "out/%s" % out_file(root, mode).name)
    rep = shapes.Report()
    if problem:
        rep.errors.append(problem)
        return rep
    if mode == "plan":
        return shapes.check_plan(obj, shapes.PlanCtx.from_json(ctx["plan"]))
    if mode == "tighten":
        return tighten.check_tighten(obj, ctx["tighten"], ws_root=root, allow_unconfirmed=allow_unconfirmed)
    return shapes.check_choice(obj, shapes.ChoiceCtx.from_json(ctx["choice"]), ws_root=root, allow_unconfirmed=allow_unconfirmed)


def _parse_box(text: str):
    parts = [p for p in str(text).replace(";", ",").replace(" ", ",").split(",") if p != ""]
    try:
        return shapes.clean_box([float(p) for p in parts], "--box")
    except ValueError:
        return None, "--box must be four numbers like 0.40,0.10,0.62,0.30 (x0, y0, x1, y1 as fractions of the painting)"


def main(argv=None) -> int:
    from bti.draft.check import refuse_outside
    ap = argparse.ArgumentParser(prog="helper", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate your output file")
    c = sub.add_parser("crop", help="cut a box out of the main painting")
    c.add_argument("--box", help="x0,y0,x1,y1 as fractions of the painting (0 to 1)")
    c.add_argument("--grid", action="store_true", help="draw a labelled grid on the painting instead of cutting")
    c.add_argument("-o", "--out", required=True, help="where to write the picture, inside look/")
    c.add_argument("--width", type=int, default=images.CROP_SIDE, help="longest side of the picture written (default %d)" % images.CROP_SIDE)
    a = ap.parse_args(argv)
    root = Path.cwd()
    if a.cmd == "check":
        rep = run_check(root)
        print(rep.text())
        return 0 if rep.ok else 1
    bad = refuse_outside(a.out, "the output path (-o)")
    if bad:
        return bad
    if not (a.out.replace("\\", "/").startswith("look/") and not os.path.isabs(a.out)):
        print("ERROR write the picture inside look/ (for example -o look/head.jpg)", file=sys.stderr)
        return 2
    try:
        info = json.loads((root / "inputs" / "painting.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("ERROR inputs/painting.json is missing: this is not a picks work folder")
        return 2
    dest = root / a.out
    try:
        if a.grid:
            images.grid(root / info["image"], dest)
            print("wrote %s (the main painting with a grid; the labels are fractions, 0.5 is the middle)" % a.out)
            return 0
        if not a.box:
            print("ERROR give --box x0,y0,x1,y1 (or --grid)")
            return 2
        box, problem = _parse_box(a.box)
        if problem:
            print("ERROR " + problem)
            return 2
        *_, w, h = images.crop(root / info["large"], box, dest, max(64, min(1600, a.width)))
        sw, sh = info["source_size"]
        x0, y0, x1, y1 = shapes.crop_pixels(box, sw, sh)
        print("wrote %s: box %s is pixels %d to %d by %d to %d of the %d x %d painting, shown at %d x %d" % (a.out, box, x0, x1, y0, y1, sw, sh, w, h))
        return 0
    except images.ImageError as e:
        print("ERROR %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
