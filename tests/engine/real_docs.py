"""The two finished videos (`christus-st-eligius`, `eyck-the-arnolfini-portrait`) as read-only fixtures: their storyboard, timing and picks, copied from the server's
`output/<key>/` folders (worker catalogue, 2026-11-20). They use techniques the catalogue now hides (the owner's finished videos must stay valid and draw as before).

    helpers: kinds_project / flagged (the viewer checks of the catalogue pass with hand-made `kinds`), build_project(dest, key, media=None) -> a project folder the engine opens (stub pictures of the declared size, or the real ones from `media`)
    CLI (on the Windows server, in a snapshot):
      tools/deploy/snapshot_py.sh NAME tests/engine/real_docs.py issues            # prints the issues of validate() of both videos as JSON
      tools/deploy/snapshot_py.sh NAME tests/engine/real_docs.py flag [--no-picture]  # prints what the checks of the catalogue pass flag on St. Eligius with hand-made kinds
      tools/deploy/snapshot_py.sh NAME tests/engine/real_docs.py frames MEDIA_ROOT # prints the sha256 of the middle frame of every shot of both videos as JSON
    MEDIA_ROOT is the server's `output` folder: the pictures are read from `<MEDIA_ROOT>/<key>/4_pictures/<asset key>.<ext>` (the main painting: `main.<ext>`; read only); a picture that is not there is a
    stub. Nothing is written outside a temporary folder.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True

FIX = Path(__file__).parent / "fixtures" / "catalogue"
KEYS = {"eligius": "christus-st-eligius", "arnolfini": "eyck-the-arnolfini-portrait"}


def load(name: str) -> dict:
    return json.loads((FIX / name / "storyboard.json").read_text(encoding="utf-8"))


def timing_path(name: str) -> Path:
    return FIX / name / "timing.json"


def _stub(path: Path, w: int, h: int) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (int(w), int(h)), (96, 90, 84))
    if path.suffix.lower() in (".jpg", ".jpeg"):
        im.save(path, quality=60)
    else:
        im.save(path)


def build_project(dest: Path, name: str, media_root: Path | None = None) -> Path:
    """`dest/<name>/` with storyboard.json, timing.json, picks.json and a picture for every asset (the real one when `media_root` has it, else a flat stub of the declared size)."""
    d = Path(dest) / name
    d.mkdir(parents=True, exist_ok=True)
    for f in ("storyboard.json", "timing.json", "picks.json"):
        shutil.copyfile(FIX / name / f, d / f)
    sb = load(name)
    main_key = json.loads((FIX / name / "picks.json").read_text(encoding="utf-8")).get("main_asset")
    for key, a in sb["assets"].items():
        target = d / a["file"]
        real = None
        if media_root is not None:
            folder = Path(media_root) / KEYS[name] / "4_pictures"
            if folder.is_dir():
                real = next((p for p in folder.glob(key + ".*")), None)
                if real is None and key == main_key:          # the main painting is `main.jpg` in the output folder
                    real = next((p for p in folder.glob("main.*")), None)
        if real is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real, target)
        else:
            _stub(target, a.get("width") or 8, a.get("height") or 8)
    return d


def issues_of(name: str, dest: Path, media_root: Path | None = None) -> list[dict]:
    """The issues of `bti.engine.storyboard.validate` for the stored storyboard, as plain rows (level, code, path, message, args) in the engine's order."""
    import bti.engine.api  # noqa: F401  (registers the techniques)
    from bti.engine import registry as R
    from bti.engine import storyboard as SB
    from bti.engine.timing import Timing
    d = build_project(dest, name, media_root)
    out = SB.validate(json.loads((d / "storyboard.json").read_text(encoding="utf-8")), Timing.load(d / "timing.json"), R.load_bundle("gae"), d)
    return [{"level": i["level"], "code": i["code"], "path": i.get("path"), "message": i.get("message"), "args": i.get("args")} for i in out]


# The `kinds` of the 61 lines of the St. Eligius narration, made by hand (worker catalogue) from the narration: what each sentence does, in the words of the pictures step
# (`detail whole outside compare journey dates figure inscription construction relations idea`, one or two, in the order the line speaks).
ELIGIUS_KINDS = {
    "b0001": ["detail"], "b0002": ["detail"], "b0003": ["whole", "detail"], "b0004": ["detail"], "b0005": ["whole"], "b0006": ["detail", "outside"], "b0007": ["outside"],
    "b0008": ["outside", "journey"], "b0009": ["detail"], "b0010": ["detail"], "b0011": ["detail", "outside"], "b0012": ["outside"], "b0013": ["outside"],
    "b0014": ["outside", "journey"], "b0015": ["outside"], "b0016": ["detail", "outside"], "b0017": ["detail", "idea"], "b0018": ["whole"], "b0019": ["detail"],
    "b0020": ["outside"], "b0021": ["outside"], "b0022": ["idea"], "b0023": ["detail"], "b0024": ["detail"], "b0025": ["idea"], "b0026": ["detail"], "b0027": ["outside"],
    "b0028": ["figure"], "b0029": ["outside"], "b0030": ["figure"], "b0031": ["detail"], "b0032": ["detail"], "b0033": ["detail", "outside"], "b0034": ["detail"],
    "b0035": ["outside"], "b0036": ["outside"], "b0037": ["detail"], "b0038": ["detail"], "b0039": ["idea"], "b0040": ["detail"], "b0041": ["detail"], "b0042": ["outside"],
    "b0043": ["construction"], "b0044": ["detail"], "b0045": ["compare"], "b0046": ["outside"], "b0047": ["idea"], "b0048": ["inscription"], "b0049": ["dates"],
    "b0050": ["detail"], "b0051": ["idea"], "b0052": ["idea"], "b0053": ["detail"], "b0054": ["outside"], "b0055": ["outside"], "b0056": ["outside"],
    "b0057": ["outside", "journey"], "b0058": ["whole"], "b0059": ["whole"], "b0060": ["whole", "idea"], "b0061": ["outside"],
}
# what the pictures step would have found for the counted thing of b0028 (the 42 caravels): the old picks had no line for it at all
CARAVEL_PICTURE = {"asset": "caravel_view", "region": None, "role": "context", "note": "a 15th-century caravel (hand-made for the proof)"}


def kinds_project(dest: Path, name: str, kinds: dict, extra_items: dict | None = None, media_root: Path | None = None) -> Path:
    """The project folder of `name` whose picks.json carries `kinds` per beat (and `extra_items`: {beat id: [item]} added to the line, a new line when it had none)."""
    d = build_project(dest, name, media_root)
    pk = json.loads((d / "picks.json").read_text(encoding="utf-8"))
    for bid, ks in kinds.items():
        pk["beats"].setdefault(bid, {"items": [], "status": "picked", "note": ""})["kinds"] = list(ks)
    for bid, items in (extra_items or {}).items():
        pk["beats"].setdefault(bid, {"items": [], "status": "picked", "note": ""})["items"] += [dict(i) for i in items]
    (d / "picks.json").write_text(json.dumps(pk, ensure_ascii=False), encoding="utf-8")
    return d


def flagged(name: str, dest: Path, kinds: dict, extra_items: dict | None = None, media_root: Path | None = None) -> list[dict]:
    """The viewer checks of the catalogue pass on the stored storyboard of `name` with those kinds: [{code, path, message, args}]."""
    import bti.engine.api  # noqa: F401
    from bti.engine import registry as R
    from bti.engine import storyboard as SB
    from bti.engine import viewchecks as VC
    from bti.engine.timing import Timing
    d = kinds_project(dest, name, kinds, extra_items, media_root)
    out = SB.validate(json.loads((d / "storyboard.json").read_text(encoding="utf-8")), Timing.load(d / "timing.json"), R.load_bundle("gae"), d)
    return [i for i in out if i["code"] in VC.CATALOGUE_ISSUES]


def frame_hashes(name: str, dest: Path, media_root: Path | None, width: int = 480) -> dict:
    """{shot id: sha256 of its middle frame (BGR bytes, `width` px wide)} of every shot of the stored storyboard."""
    from bti.engine.api import open_project
    from bti.engine.timing import Timing
    d = build_project(dest, name, media_root)
    p = open_project(d)
    sb = p.storyboard()
    tm = Timing.load(d / "timing.json")

    def t_of(a):
        return tm.resolve(a) if isinstance(a, dict) else float(a)
    starts = [t_of(s["start"]) for s in sb["shots"]]
    ends = starts[1:] + [t_of(sb["end"])]
    out = {}
    for s, a, b in zip(sb["shots"], starts, ends):
        fr = p.frame_at((a + b) / 2.0, width)
        out[s["id"]] = hashlib.sha256(fr.tobytes()).hexdigest()[:20]
    return out


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "issues"
    media = Path(argv[1]) if len(argv) > 1 and cmd != "flag" else None
    tmp = Path(tempfile.mkdtemp(prefix="bti-realdocs-"))
    try:
        res = {}
        if cmd == "flag":
            extra = None if "--no-picture" in argv else {"b0028": [CARAVEL_PICTURE]}
            rows = flagged("eligius", tmp, ELIGIUS_KINDS, extra)
            print(json.dumps([{"code": r["code"], "path": r["path"], "args": r["args"], "message": r["message"]} for r in rows], ensure_ascii=False, indent=1))
            return 0
        for name in KEYS:
            res[name] = issues_of(name, tmp, media) if cmd == "issues" else frame_hashes(name, tmp, media)
        print(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
