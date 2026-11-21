"""The throw-away instance of the end-to-end proof (tests/e2e/picks_auto/launch_picks_auto.py) has a fake agent that writes a plan and a
choice: both must pass the real checks (`check_plan` including valid `thing` fields; `check_choice` / `FakeRunner.run` including tight cut-out
pixel boxes confirmed after the check sheet), or the e2e script cannot run any more. The launcher patches the app when it is imported, so
only its needed symbols are taken from the AST source and run here."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from auto_helpers import make_auto_project

from bti.draft.providers.agy import AgyResult
from bti.picks.auto import helper, inputs as ainputs, session, shapes, workspace

SRC = Path(__file__).resolve().parents[1] / "e2e" / "picks_auto" / "launch_picks_auto.py"
BEATS = [{"id": "b%04d" % n, "chapter": "c%02d" % ((n + 1) // 2), "words": 60} for n in range(1, 7)]
IDS = [b["id"] for b in BEATS]


def _load_symbol(name, ns):
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)
    exec(compile(ast.Module([node], []), str(SRC), "exec"), ns)
    return ns[name]


def make_plan(first_run):
    lines = {bid: {"no": n} for n, bid in enumerate(IDS, 1)}
    ns = {"shapes": shapes, "_inputs": lambda ws: ({"plan": {"targets": list(IDS), "existing_regions": []}}, lines)}
    return _load_symbol("make_plan", ns)(None, first_run)


def _choose_workspace(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    pdir = make_auto_project(root, "e2e1")
    inp = ainputs.load(pdir)
    plan_rep = shapes.check_plan(make_plan(True), inp.plan_ctx())
    assert plan_rep.ok, plan_rep.errors
    search = {
        "wants": {
            "b0004.1": {
                "want_id": "b0004.1", "beat": "b0004", "type": "map", "kind": None,
                "what": "Bản đồ Bruges và Antwerp", "places": ["Bruges, Belgium", "Antwerp, Belgium"],
                "candidates": [{"n": 1, "source": "osm", "source_id": "1:12:51.2090:3.2247:Bruges", "title": "Bản đồ Bruges", "thumb": None}],
            },
            "b0004.2": {
                "want_id": "b0004.2", "beat": "b0004", "type": "clip", "kind": None,
                "what": "Kênh đào", "queries": ["canal boat"],
                "candidates": [{"n": 1, "source": "commons", "source_id": "File:Canal boat.mp4", "title": "Canal boat", "thumb": None}],
            },
        }
    }
    ws, cctx = workspace.build_choose(
        inp, plan_rep.value, search, session.Limits(minutes=45, steps=180, repairs=2),
        books=[], root=tmp_path / "ws",
    )
    return ws.root, cctx


@pytest.mark.parametrize("first_run", [True, False])
def test_the_fake_agents_plan_passes_the_check_of_the_program(first_run):
    plan = make_plan(first_run)
    rep = shapes.check_plan(plan, shapes.PlanCtx(beats=BEATS, targets=list(IDS), existing_regions={}))
    assert rep.ok, rep.errors
    assert all(r.get("thing") for r in plan["regions"])
    assert all(ln.get("kinds") for ln in plan["lines"]) and [ln["kinds"] for ln in rep.value["lines"]][0] == ["whole"]
    for ln in plan["lines"]:
        if "outside" in ln["kinds"]:
            assert ln.get("fallback"), ln["beat"]                                            # an `outside` line names what is shown when nothing is found
    wants = shapes.wants_of(rep.value)
    assert [w["type"] for w in wants] == ["context", "map", "clip"] and wants[0]["kinds"] == ["outside"]
    assert (wants[0]["search"] == "Krakatoa 1883 ash cloud") is first_run                       # the first run asks for what nothing can fill, the next one for the painter


def test_the_fake_agents_choice_uses_tight_cutout_boxes_and_confirms_after_check_sheet(tmp_path):
    ws, cctx = _choose_workspace(tmp_path)
    make_choice = _load_symbol("make_choice", {"Path": Path, "json": json, "shapes": shapes})

    # Pass 1: tight cut-out boxes before check sheet -> refused with check_sheet_ready and draws look/check_1.jpg
    c1 = make_choice(ws)
    assert [r["name"] for r in c1["regions"]] == ["MIRROR", "HEAD"]
    for r in c1["regions"]:
        cw, ch = cctx.cutouts[r["name"]]["cutout_size"]
        assert r["action"] == "tight" and r.get("confirmed") is not True
        x0, y0, x1, y1 = r["box"]
        assert 0 <= x0 < x1 <= cw and 0 <= y0 < y1 <= ch
    (ws / "out" / "choice.json").write_text(json.dumps(c1, ensure_ascii=False), encoding="utf-8")
    rep1 = helper.run_check(ws)
    assert not rep1.ok and any("check_sheet_ready" in e for e in rep1.errors)
    assert (ws / "look" / "check_1.jpg").is_file()

    # Pass 2: after check sheet exists, make_choice confirms and passes the real check
    c2 = make_choice(ws)
    assert all(r["action"] == "tight" and r.get("confirmed") is True for r in c2["regions"])
    (ws / "out" / "choice.json").write_text(json.dumps(c2, ensure_ascii=False), encoding="utf-8")
    rep2 = helper.run_check(ws)
    assert rep2.ok, rep2.errors
    assert set(rep2.value["regions"]) == {"MIRROR", "HEAD"}
    assert all(r["action"] == "tight" and r["confirmed"] is True for r in rep2.value["regions"].values())


def test_fake_runner_repairs_choose_after_check_sheet(tmp_path):
    ws, _ = _choose_workspace(tmp_path)
    state = {"slow": False, "fail": False, "plans": 0, "calls": []}
    lines = {bid: {"no": n} for n, bid in enumerate(IDS, 1)}
    ns = {
        "Path": Path,
        "json": json,
        "shapes": shapes,
        "_inputs": lambda _ws: ({"plan": {"targets": list(IDS), "existing_regions": []}}, lines),
        "STATE": state,
        "AgyResult": AgyResult,
        "time": SimpleNamespace(time=lambda: 0.0, sleep=lambda _s: None),
    }
    _load_symbol("make_plan", ns)
    _load_symbol("make_choice", ns)
    FakeRunner = _load_symbol("FakeRunner", ns)

    def _check(_turn):
        rep = helper.run_check(ws)
        return None if rep.ok else rep.text()

    res = FakeRunner.run(ws, model="mock", max_repairs=2, check=_check)
    assert res.status == "ok" and res.turns == 2 and res.repairs == 1
    assert (ws / "look" / "check_1.jpg").is_file()
    final_rep = helper.run_check(ws)
    assert final_rep.ok, final_rep.errors
