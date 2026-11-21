"""Runs ON the Windows server (test code only): tests/e2e/stages/launch.py (the second, throw-away instance of the app: fakes, mock model,
BTI_NO_REAL_MODELS=1, its own port and temp copies of the data) with the pieces the automatic picks job needs, all fake:
  - the two agents with the names of the real two (a private BTI_AGENT_CHOICES_FILE: "Gemini 3.8 Flash" runs the model `mock`, "Opus 5.5 High"
    `mock-opus`); no `agy` and no `claude` is ever started;
  - the agent in a work folder (`bti.picks.auto.session.agent_module`) is a FAKE RUNNER: it reads the folder's inputs and writes `out/plan.json`
    or `out/choice.json` the way an agent would (a different plan for each kind of line; a wanted picture that nothing can fill, once), shows
    steps in its progress, and stops at once when the job is cancelled. `PUT /api/_e2e/picks_auto {slow: true}` makes a session last until it is
    cancelled (to try the cancel button); `{fail: true}` makes the next session write a file that fails the check (twice: the part fails);
  - the picture sources are fakes with canned answers, and the thumbnails are small grey pictures (no network);
  - a project `picks-demo` with an approved narration of six lines and a main painting, whose picks hold only that painting; a second one, `picks-join`,
    the same, for the joined path of the prompt box and the agent (a request the box cannot do, handed to the agent from its card).
Usage (through remote.mjs): BTI_STAGES_LAUNCH=tests\\e2e\\picks_auto\\launch_picks_auto.py; the arguments are those of launch.py."""
import json
import os
import runpy
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests" / "picks"))
sys.path.insert(0, str(REPO / "tests" / "script"))
sys.path.insert(0, str(REPO / "tests" / "media"))
os.environ["BTI_REPO"] = str(REPO)

STEPS = {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}
CHOICES = {"default": "gemini", "steps": STEPS,
           "agents": [{"id": "gemini", "label": "Gemini 3.8 Flash", "model": "mock"}, {"id": "opus", "label": "Opus 5.5 High", "model": "mock-opus"}]}
choices = Path(tempfile.gettempdir()) / "bti-picks-auto-choices.json"
choices.write_text(json.dumps(CHOICES), encoding="utf-8")
os.environ["BTI_AGENT_CHOICES_FILE"] = str(choices)

STATE = {"slow": False, "fail": False, "plans": 0, "calls": []}

from bti.script import models as M  # noqa: E402

_load_raw, _resolve = M.load_raw, M.resolve


def load_raw(path=None):
    rows = list(_load_raw(path))
    if not any(r.get("id") == "mock-opus" for r in rows):
        rows.append({"id": "mock-opus", "label": "Mock (Opus giả)", "provider": "mock", "model": "mock", "key_env": None})
    return rows


M.load_raw = load_raw

# ---- the fake runner of the work-folder session
from bti.draft.providers.agy import AgyResult  # noqa: E402
from bti.picks.auto import search as asearch, session  # noqa: E402
from bti.picks.auto import shapes  # noqa: E402


def _inputs(ws):
    ctx = json.loads((Path(ws) / "inputs" / "context.json").read_text(encoding="utf-8"))
    nar = json.loads((Path(ws) / "inputs" / "narration.json").read_text(encoding="utf-8"))
    lines = {ln["id"]: ln for c in nar["chapters"] for ln in c["lines"]}
    return ctx, lines


def make_plan(ws, first_run):
    ctx, lines = _inputs(ws)
    p = ctx["plan"]
    regions = [
        {"name": "MIRROR", "box": [0.40, 0.30, 0.60, 0.55], "what": "Tấm gương lồi", "thing": "convex mirror on back wall"},
        {"name": "HEAD", "box": [0.10, 0.05, 0.30, 0.25], "what": "Khuôn mặt", "thing": "man's face"},
    ]
    regions = [r for r in regions if r["name"] not in p["existing_regions"]]
    out = []
    for i, bid in enumerate(p["targets"]):
        n = lines[bid]["no"]
        extra = {}                                           # fixes3: every line says its `kinds`, and an `outside` line a `fallback` (the plan check refuses a plan without them)
        if n == 1:
            show, why, kinds = [{"type": "whole"}], "Mở bằng cả bức tranh để người xem thấy cả căn phòng.", ["whole"]
        elif n == 2:
            show, why, kinds = [{"type": "detail", "region": "MIRROR"}], "Lời dẫn nói về tấm gương: đi vào đúng chi tiết đó.", ["detail"]
        elif n == 3:
            kinds, extra = ["outside"], {"fallback": {"type": "whole"}}
            if first_run:                                    # nothing can fill this one: it stays without a picture and the owner is told why
                show = [{"type": "context", "search": "Krakatoa 1883 ash cloud", "alt": ["Krakatoa eruption painting"], "kind": "work", "entity": "Krakatoa", "period": "then",
                         "what": "Tro núi lửa Krakatoa"}]
                why = "Nói về tro núi lửa: cần một hình về vụ phun trào Krakatoa."
            else:
                show = [{"type": "context", "search": "Jan van Eyck portrait", "alt": [], "kind": "portrait", "entity": "Jan van Eyck", "period": "then", "what": "Chân dung họa sĩ"}]
                why = "Nói về họa sĩ, không phải về bức tranh: cần chân dung của ông."
        elif n == 4:
            show, why = [{"type": "map", "places": ["Bruges, Belgium", "Antwerp, Belgium"], "what": "Bản đồ Bruges và Antwerp"},
                         {"type": "clip", "search": "canal boat", "what": "Kênh đào", "seconds": 6}], \
                "Câu này nói bức tranh được vẽ ở đâu: một bản đồ cho thấy vị trí, rồi một đoạn phim kênh đào."
            kinds, extra = ["outside", "journey"], {"fallback": {"type": "whole"}}
        elif n == 5:
            show, why, kinds = [{"type": "detail", "region": "HEAD"}, {"type": "whole"}], "Khuôn mặt người đàn ông, rồi lùi ra cả bức tranh.", ["detail", "whole"]
        else:
            show, why, kinds = [], "Vẫn cùng ý với đoạn trước, không cần hình mới.", ["idea"]
        out.append({"beat": bid, "reason": why, "kinds": kinds, "show": show, **extra})
    return {"schema": shapes.PLAN_SCHEMA, "regions": regions, "lines": out, "names": []}


def make_choice(ws, confirmed=None):
    ws = Path(ws)
    ctx = json.loads((ws / "inputs" / "context.json").read_text(encoding="utf-8"))["choice"]
    if confirmed is None:
        st_file = ws / "look" / "tighten_state.json"
        st = json.loads(st_file.read_text(encoding="utf-8")) if st_file.is_file() else {}
        confirmed = bool(st.get("sheets"))
    cutouts = ctx.get("cutouts") or {}
    regions = []
    for r in ctx["regions"]:
        if r in cutouts:
            cw, ch = cutouts[r]["cutout_size"]
            box = [max(0, cw // 5), max(0, ch // 5), max(2, (cw * 4) // 5), max(2, (ch * 4) // 5)]
            entry = {"name": r, "action": "tight", "box": box, "reason": "Khung ôm sát chi tiết."}
            if confirmed:
                entry["confirmed"] = True
            regions.append(entry)
        else:
            regions.append({"name": r, "action": "keep", "reason": ""})
    return {"schema": shapes.CHOICE_SCHEMA,
            "wants": [{"id": w, "pick": 1, "reason": "Hình rõ nét, đúng thứ lời dẫn nói tới."} for w in ctx["wants"]],
            "regions": regions}


class FakeRunner:
    SUPPORTS_ALLOW = True

    @staticmethod
    def run(ws_root, *, model=None, timeout=1800.0, max_repairs=2, check=None, cancel=None, on_progress=None, **kw):
        ws = Path(ws_root)
        mode = json.loads((ws / "inputs" / "context.json").read_text(encoding="utf-8"))["mode"]
        STATE["calls"].append({"mode": mode, "model": model})
        if mode == "plan":
            STATE["plans"] += 1
        first_run = STATE["plans"] <= 1
        res = AgyResult(status="ok", elapsed=1.0)
        t0, steps = time.time(), 0
        while True:                                          # a few steps (or, slow, until it is cancelled)
            steps += 1
            if on_progress:
                on_progress({"steps": steps, "last_action": "view_file", "turn": 1, "out_files": 0, "elapsed": time.time() - t0})
            for _ in range(5):
                if cancel and cancel():
                    res.status, res.steps = "cancelled", steps
                    return res
                time.sleep(0.1)
            if not STATE["slow"] and steps >= 3:
                break
        out_path = ws / "out" / ("plan.json" if mode == "plan" else "choice.json")
        (ws / "out").mkdir(exist_ok=True)
        turn = 1
        while True:                                          # write output and re-run on repair rounds (e.g. check-sheet confirmation)
            if STATE["fail"]:
                out_path.write_text("{ not json", encoding="utf-8")
            else:
                data = make_plan(ws, first_run) if mode == "plan" else make_choice(ws)
                out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            res.steps, res.turns = steps, turn
            if check is None:
                break
            problems = check(turn)
            if not problems or turn > max_repairs:
                break
            turn += 1
            res.repairs += 1
        return res


session.agent_module = lambda model_id: FakeRunner
session.check_installed = lambda model_id: None
import bti.draft.guard as _guard  # noqa: E402
_guard.comic_repo_status = lambda: None            # the comic repository is never looked at, not even read-only

# ---- fake pictures: sources with canned answers, grey thumbnails. (launch.py puts its own Commons and Met, which answer every query from the
# fixtures, into the media facade AFTER this file ran: the fakes are put in place by `create_app` below, which launch.py calls last.)
from auto_helpers import FakeSource, fake_book_thumb, fake_thumb, meta  # noqa: E402
from bti.media import api as media_api  # noqa: E402


def install_fake_pictures():
    media_api._SOURCES["commons"] = FakeSource("commons", [meta("commons", "File:Portrait A.jpg", "Chân dung họa sĩ A", "portrait"),
                                                          meta("commons", "File:Portrait B.jpg", "Chân dung họa sĩ B", "portrait"),
                                                          meta("commons", "File:Canal boat.mp4", "Canal boat", "canal", kind="video")])
    media_api._SOURCES["met"] = FakeSource("met", [meta("met", "436535", "Portrait of a man", "portrait")])
    media_api._SOURCES["osm"] = FakeSource("osm", [meta("osm", "1:12:51.2090:3.2247:Bruges", "Bản đồ Bruges", "bruges")])
    asearch.default_fetch_thumb = fake_thumb
    asearch.default_book_thumb = fake_book_thumb
    import bti.media.clips as _clips
    _clips.normalize = lambda src, dest, **kw: Path(dest).write_bytes(Path(src).read_bytes())          # a fake clip is not a video: nothing to convert
    media_api._probe_upload_video = lambda p: {"width": 1920, "height": 1080, "duration": 7.5}


# ---- the demo project, made inside the temp projects folder the launcher gives the app
import bti.editor.app as A  # noqa: E402
from auto_helpers import make_auto_project  # noqa: E402

_create_app = A.create_app


def create_app(*a, **k):
    root = Path(k.get("projects_root") or a[0])
    for pid in ("picks-demo", "picks-join"):
        if not (root / pid).is_dir():
            make_auto_project(root, pid)
    install_fake_pictures()
    app = _create_app(*a, **k)

    def switch(body: dict):
        STATE.update({x: bool(body[x]) for x in ("slow", "fail") if x in body})
        if body.get("reset"):
            STATE.update(plans=0, calls=[])
        return {k2: v for k2, v in STATE.items() if k2 != "calls"} | {"calls": list(STATE["calls"])}

    def calls():
        return {"calls": list(STATE["calls"]), "plans": STATE["plans"]}
    app.add_api_route("/api/_e2e/picks_auto", switch, methods=["PUT"])
    app.add_api_route("/api/_e2e/picks_auto_calls", calls, methods=["POST"])          # a POST: the app answers an unknown GET under /api with "not found" before a route added here
    return app


A.create_app = create_app

runpy.run_path(str(REPO / "tests" / "e2e" / "stages" / "launch.py"), run_name="__main__")
