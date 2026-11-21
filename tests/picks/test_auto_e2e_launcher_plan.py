"""The throw-away instance of the end-to-end proof (tests/e2e/picks_auto/launch_picks_auto.py) has a fake agent that writes a plan: that plan must pass the check of the program
(every line has its `kinds`, an `outside` line its `fallback`), or the script cannot run any more (fixes3). The launcher patches the app when it is imported, so only its function
`make_plan` is taken from the source and run here."""
import ast
from pathlib import Path

import pytest

from bti.picks.auto import shapes

SRC = Path(__file__).resolve().parents[1] / "e2e" / "picks_auto" / "launch_picks_auto.py"
BEATS = [{"id": "b%04d" % n, "chapter": "c%02d" % ((n + 1) // 2), "words": 60} for n in range(1, 7)]
IDS = [b["id"] for b in BEATS]


def make_plan(first_run):
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "make_plan")
    lines = {bid: {"no": n} for n, bid in enumerate(IDS, 1)}
    ns = {"shapes": shapes, "_inputs": lambda ws: ({"plan": {"targets": list(IDS), "existing_regions": []}}, lines)}
    exec(compile(ast.Module([fn], []), str(SRC), "exec"), ns)
    return ns["make_plan"](None, first_run)


@pytest.mark.parametrize("first_run", [True, False])
def test_the_fake_agents_plan_passes_the_check_of_the_program(first_run):
    plan = make_plan(first_run)
    raw_rep = shapes.check_plan(plan, shapes.PlanCtx(beats=BEATS, targets=list(IDS), existing_regions={}))
    assert not raw_rep.ok and sum("thing_missing" in e for e in raw_rep.errors) == len(plan["regions"])
    for r in plan["regions"]:
        r["thing"] = "convex mirror on wall" if "MIRROR" in r["name"] else "joined hands in center"
    rep = shapes.check_plan(plan, shapes.PlanCtx(beats=BEATS, targets=list(IDS), existing_regions={}))
    assert rep.ok, rep.errors
    assert all(ln.get("kinds") for ln in plan["lines"]) and [ln["kinds"] for ln in rep.value["lines"]][0] == ["whole"]
    for ln in plan["lines"]:
        if "outside" in ln["kinds"]:
            assert ln.get("fallback"), ln["beat"]                                            # an `outside` line names what is shown when nothing is found
    wants = shapes.wants_of(rep.value)
    assert [w["type"] for w in wants] == ["context", "map", "clip"] and wants[0]["kinds"] == ["outside"]
    assert (wants[0]["search"] == "Krakatoa 1883 ash cloud") is first_run                       # the first run asks for what nothing can fill, the next one for the painter
