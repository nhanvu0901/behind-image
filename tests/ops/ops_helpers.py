"""Helpers of the operations tests: one fixture project that has everything the two documents need, and small request helpers.

The project `ops1` is a library-style project (an approved outline and narration of six beats, `b0001` to `b0006`, made by the
picks helpers) with, besides:

    media/            four pictures: A 1200x1600, B 1600x1000, C 1000x1000, D 1200x1500 (made with Pillow, no network)
    timing.json       250 words, one every 0.35 s from 0.4 s; six beats and three chapters that match the narration
    storyboard.json   ten shots `s0001` to `s0010`: `s0006` is locked (and so is its overlay), `s0002` has two overlays, `s0004` one
    picks.json        main picture A; b0001 shows A (region HEAD), b0002 is skipped, b0003 shows B, the rest have no picture

The examples of `docs/OPS.md` are written for this project.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "tests" / "picks", REPO / "tests" / "script"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from PIL import Image  # noqa: E402
from picks_helpers import make_project as make_library_project  # noqa: E402

PID = "ops1"
PD_ID = "File:Jan van Eyck - The Arnolfini Portrait - Google Art Project.jpg"       # the picture the fake Commons source serves
SIZES = {"A": (1200, 1600), "B": (1600, 1000), "C": (1000, 1000), "D": (1200, 1500)}
FILES = {"A": "media/a_portrait.png", "B": "media/b_landscape.png", "C": "media/c_detail.png", "D": "media/d_other.png"}
STEP = 0.35
N_WORDS = 250
DURATION = 90.0


def word(i):
    return "word%d" % i


def word_t(i):
    return round(0.4 + STEP * i, 3)


def anchor(i, off=0.0):
    return {"w": i, "off": off, "text": word(i)}


def timing_doc():
    words = [{"w": word(i), "s": word_t(i), "e": round(word_t(i) + 0.3, 3)} for i in range(N_WORDS)]
    edges = [0, 40, 80, 120, 170, 210, 250]
    beats = []
    for k in range(6):
        w0, w1 = edges[k], edges[k + 1]
        beats.append({"chapter": ["COLD OPEN", "COLD OPEN", "THE ROOM", "THE ROOM", "CLOSING", "CLOSING"][k], "text": "",
                      "start": words[w0]["s"], "end": words[w1 - 1]["e"], "w0": w0, "w1": w1})
    chapters = [{"name": "COLD OPEN", "start": words[0]["s"], "end": words[79]["e"]},
                {"name": "THE ROOM", "start": words[80]["s"], "end": words[169]["e"]},
                {"name": "CLOSING", "start": words[170]["s"], "end": words[249]["e"]}]
    return {"duration": DURATION, "words": words, "beats": beats, "chapters": chapters}


def _asset(key, title, regions):
    w, h = SIZES[key]
    return {"file": FILES[key], "kind": "image", "title": title, "artist": "Test", "year": "2026", "width": w, "height": h,
            "credit": {"source": "generated", "source_url": "", "author": "test", "licence": "CC0", "licence_url": "", "flag": None},
            "regions": regions}


def _region(x, y, rx, ry, label):
    return {"x": x, "y": y, "rx": rx, "ry": ry, "label": label}


def picks_assets():
    return {"A": _asset("A", "Test portrait", {"HEAD": _region(600, 380, 180, 200, "Head"), "HANDS": _region(620, 900, 200, 120, "Hands")}),
            "B": _asset("B", "Test landscape", {"CENTRE": _region(800, 500, 200, 200, "Centre")}),
            "C": _asset("C", "Test detail", {}), "D": _asset("D", "Test other work", {})}


def storyboard_assets():
    a = picks_assets()
    a["A"]["regions"]["CENTRE"] = _region(600, 500, 200, 200, "Centre")
    return a


def _shot(sid, start, tech, intent, slots, params, overlays=(), locked=False, source="import", note=""):
    return {"id": sid, "start": anchor(start), "technique": tech, "intent": intent, "slots": slots, "params": params, "transition_in": None,
            "overlays": list(overlays), "locked": locked, "source": source, "note": note}


def _cam(a, b):
    return {"camera": [{"at": {"rel": 0.0}, "cx": a[0], "cy": a[1], "zoom": a[2], "ease": "inout_cubic"},
                       {"at": {"rel": 1.0}, "cx": b[0], "cy": b[1], "zoom": b[3] if len(b) > 3 else b[2], "ease": "linear"}]}


def storyboard_doc():
    def img(k):
        return {"image": {"asset": k}}

    def ov(oid, tech, intent, start, dur, params, locked=False, source="import"):
        return {"id": oid, "technique": tech, "intent": intent, "start": anchor(start), "dur": dur, "params": params, "locked": locked,
                "source": source, "note": ""}
    shots = [
        {**_shot("s0001", 0, "STATIC-01", "establish", img("A"), {}), "start": {"t": 0.0}},
        _shot("s0002", 22, "CAM-05", "point_at", img("A"), _cam((600, 800, 0.675), (600, 640, 1.215)),
              [ov("o1", "HI-01", "isolate", 28, 5.0, {"at": "CENTRE", "rx": 200, "ry": 200, "floor": 0.2, "ramp_in": 0.5, "ramp_out": 0.5}),
               ov("o2", "AN-01", "point_at", 34, 3.0, {"at": "CENTRE", "radius": 180, "draw_s": 0.5, "hold_s": 2.0, "fade_s": 0.4})]),
        _shot("s0003", 48, "X-CARD-01", "structure", {}, {"title": "THE DETAILS"}),
        _shot("s0004", 62, "CAM-01", "explore", img("B"), _cam((800, 500, 1.08), (800, 400, 1.296)),
              [ov("o1", "STATIC-02", "context", 65, 6.0, {"text": "WINTER LANDSCAPE", "size_px": 24})]),
        _shot("s0005", 85, "LAY-01", "compare", {"left": {"asset": "A"}, "right": {"asset": "D"}}, {}),
        _shot("s0006", 110, "CAM-04", "explore", img("C"), _cam((500, 500, 1.08), (500, 400, 1.404)),
              [ov("o1", "X-ANN-01", "point_at", 115, 4.0, {"text": "RED GLAZE"}, locked=True, source="human")], locked=True, source="human",
              note="Fixed by the editor; agents must not touch."),
        _shot("s0007", 140, "CAM-03", "compare", img("C"), _cam((500, 500, 1.404), (500, 500, 1.08))),
        _shot("s0008", 168, "CAM-03", "establish", img("B"), _cam((800, 500, 1.4148), (800, 500, 1.08))),
        _shot("s0009", 200, "X-LAY-01", "context", img("D"), _cam((600, 750, 0.72), (600, 600, 0.936))),
        _shot("s0010", 226, "STATIC-01", "establish", img("A"), {}),
    ]
    return {"schema": "bti.storyboard/1", "project": PID, "title": "Ops test", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30},
            "timing": "timing.json", "assets": storyboard_assets(), "shots": shots, "end": {"t": DURATION}, "approvals": {"storyboard": None}}


def picks_doc():
    def item(asset, region=None, role="detail"):
        return {"asset": asset, "region": region, "role": role, "note": ""}
    return {"schema": "bti.picks/1", "main_asset": "A", "assets": picks_assets(),
            "beats": {"b0001": {"items": [item("A", "HEAD")], "status": "picked", "note": ""},
                      "b0002": {"items": [], "status": "skip", "note": ""},
                      "b0003": {"items": [item("B", None, "context")], "status": "picked", "note": ""}}}


def make_project(root: Path, pid: str = PID) -> Path:
    """The fixture project, in `root`: library files (narration, dossier), media, timing, storyboard and picks."""
    from bti.picks import doc as pdoc
    d = make_library_project(root, pid)
    (d / "media").mkdir(exist_ok=True)
    for key, (w, h) in SIZES.items():
        Image.new("RGB", (w, h), (90 + 30 * "ABCD".index(key), 100, 110)).save(d / FILES[key])
    (d / "timing.json").write_text(json.dumps(timing_doc()), encoding="utf-8")
    (d / "storyboard.json").write_text(json.dumps(storyboard_doc(), indent=1), encoding="utf-8")
    pdoc.save(d, picks_doc())
    return d


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def snapshot(d: Path) -> dict:
    """Every file of a project folder (bytes), to prove that a refused batch wrote nothing at all."""
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(Path(d).rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- requests
def sb_rev(client) -> str:
    return client.get("/api/projects/%s" % PID).json()["rev"]


def pk_rev(client) -> str:
    return client.get("/api/projects/%s/picks" % PID).json()["rev"]


def batch(client, kind, ops, *, rev=None, actor="agent:test-model", dry_run=None, scope=None, note=None, **extra):
    """POST a batch to the storyboard (`kind == "sb"`) or the picks (`"pk"`) route; the revision is read when not given."""
    body = {"base_rev": rev if rev is not None else (sb_rev(client) if kind == "sb" else pk_rev(client)), "actor": actor, "ops": ops}
    if dry_run is not None:
        body["dry_run"] = dry_run
    if scope is not None:
        body["scope"] = scope
    if note is not None:
        body["note"] = note
    body.update(extra)
    return client.post(client.sb if kind == "sb" else client.pk, json=body)


def sb(client, ops, **kw):
    return batch(client, "sb", ops, **kw)


def pk(client, ops, **kw):
    return batch(client, "pk", ops, **kw)


def shots(client):
    """The saved storyboard's shots, read from the file (what a reader of the file sees)."""
    return read_json(client.pdir / "storyboard.json")["shots"]


def shot(client, sid):
    return next(s for s in shots(client) if s["id"] == sid)


def picks(client):
    return read_json(client.pdir / "picks.json")


def paths(resp):
    """The `fields[].path` of an error answer."""
    return [f["path"] for f in resp.json().get("fields") or []]
