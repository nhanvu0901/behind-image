"""A one-off proof of the rule of `outside_on_painting` on the REAL storyboard of the first run of the new picture rules (project `eligius`, 2026-11-20), by the worker fixes4:
`tools/deploy/snapshot_py.sh fixes4 tests/engine/outside_real_proof.py proof_in3` (read-only copies of `projects/eligius/{storyboard,timing,picks}.json` in the folder given). Not a test.
It prints what the check flags under the old rule (half of the line, any number of kinds) and under the new one (45% of a line with one kind, 25% of a line with two, at least 3.5 seconds)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True

import bti.engine.api  # noqa: E402,F401  (registers the techniques)
from bti.engine import registry as R, storyboard as SB, viewchecks as VC  # noqa: E402
from bti.engine.timing import Timing  # noqa: E402

IN = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "proof_in3"
sb = json.loads((IN / "storyboard.json").read_text(encoding="utf-8"))
picks = json.loads((IN / "picks.json").read_text(encoding="utf-8"))
tmp = Path(tempfile.mkdtemp(prefix="outside_proof_"))
try:
    from PIL import Image
    d = tmp / "eligius"
    d.mkdir()
    for f in ("storyboard.json", "timing.json", "picks.json"):
        shutil.copyfile(IN / f, d / f)
    for key, a in sb["assets"].items():                          # a flat picture of the declared size: the check reads sizes, never pixels
        t = d / a["file"]
        t.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (int(a.get("width") or 8), int(a.get("height") or 8)), (96, 90, 84)).save(t)
    tm = Timing.load(d / "timing.json")
    bundle = R.load_bundle("gae")
    beats = {b["id"]: b for b in json.loads((d / "timing.json").read_text(encoding="utf-8"))["beats"]}

    def flagged():
        out = SB.validate(json.loads((d / "storyboard.json").read_text(encoding="utf-8")), tm, bundle, d)
        return [i for i in out if i["code"] == "outside_on_painting"]

    def show(label, rows):
        print("%s: %d line(s) flagged" % (label, len(rows)))
        for i in sorted(rows, key=lambda i: i["args"]["beat"]):
            a, b = i["args"], i["args"]["beat"]
            print("   %s kinds %-18s line %.1f s, picture on %.1f s = %2.0f%%   (needs %s)" % (
                b, ",".join(picks["beats"][b]["kinds"]), a["beat_seconds"], a["seconds"], a["share"] * 100,
                ("%.0f%% and %.1f s = %.1f s" % (a["limit"] * 100, a.get("min_seconds", 0), a.get("needed_seconds", a["limit"] * a["beat_seconds"])))))
    new = flagged()
    old_consts = (VC.OUTSIDE_ON_PAINTING_SHARE, VC.OUTSIDE_ON_PAINTING_SHARE_TWO, VC.OUTSIDE_ON_PAINTING_MIN_SECONDS)
    VC.OUTSIDE_ON_PAINTING_SHARE, VC.OUTSIDE_ON_PAINTING_SHARE_TWO, VC.OUTSIDE_ON_PAINTING_MIN_SECONDS = 0.5, 0.5, 0.0      # the rule before this change
    old = flagged()
    VC.OUTSIDE_ON_PAINTING_SHARE, VC.OUTSIDE_ON_PAINTING_SHARE_TWO, VC.OUTSIDE_ON_PAINTING_MIN_SECONDS = old_consts
    show("OLD rule (half of the line)", old)
    show("NEW rule (45% / 25% / 3.5 s)", new)
    names_old, names_new = {i["args"]["beat"] for i in old}, {i["args"]["beat"] for i in new}
    print("no longer flagged: %s | newly flagged: %s" % (sorted(names_old - names_new), sorted(names_new - names_old)))
    for b in ("b0011", "b0058", "b0035"):
        print("  %s: %s kinds, %.1f s -> %s" % (b, ",".join(picks["beats"][b]["kinds"]), beats[b]["end"] - beats[b]["start"], "flagged" if b in names_new else "passes"))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
