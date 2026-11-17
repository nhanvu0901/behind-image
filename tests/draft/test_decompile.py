import copy

import pytest

from bti.draft import spec as S
from bti.draft.compile import compile_specs, summary_text
from bti.draft.decompile import clean, decompile, scope_violations, chapters_of_shots
from bti.draft.inputs import clone_inputs, load_inputs
from bti.draft.providers import auto
from helpers import clean_spec


def _specs(dec):
    out = {}
    for cid, d in dec.items():
        clean_s, probs = S.shape_problems(copy.deepcopy(d["spec"]), cid) if d["spec"]["shots"] else ({"shots": []}, [])
        assert not [p for p in probs if p["level"] == "error"], probs
        if clean_s["shots"]:
            out[cid] = clean_s
    return out


def test_round_trip_of_the_real_arnolfini_storyboard(arnolfini):
    inp = load_inputs(arnolfini)
    inp = clone_inputs(inp, edit_shots=set())                 # nothing may change
    specs = _specs(decompile(inp, set()))
    res = compile_specs(inp, specs, draw=False)
    orig = inp.current["shots"]
    new = res.storyboard["shots"]
    assert [s["id"] for s in new] == [s["id"] for s in orig]
    for a, b in zip(orig, new):
        assert clean(a) == clean(b), a["id"]
    assert res.violations == [] and not res.errors, summary_text(res)


def test_a_changed_shot_is_rebuilt_and_the_rest_stays(arnolfini):
    inp = load_inputs(arnolfini)
    target = next(s for s in inp.current["shots"] if s["technique"] == "CAM-05")
    inp = clone_inputs(inp, edit_shots={target["id"]}, scope=chapters_of_shots(inp, {target["id"]}))
    dec = decompile(inp, {target["id"]})
    for d in dec.values():
        for s in d["spec"]["shots"]:
            if s["id"] == target["id"]:
                assert s["in_scope"] is True
                s["note"] = "slower, as the owner asked"
                s["technique"] = "CAM-01"
                s["params"] = {}
    res = compile_specs(inp, _specs(dec), draw=False)
    new = {s["id"]: s for s in res.storyboard["shots"]}
    assert new[target["id"]]["technique"] == "CAM-01" and new[target["id"]]["note"] == "slower, as the owner asked"
    assert res.violations == [], summary_text(res)


def test_a_change_outside_the_scope_is_refused_and_named(arnolfini):
    inp = load_inputs(arnolfini)
    shots = inp.current["shots"]
    target, other = shots[3], shots[5]
    inp = clone_inputs(inp, edit_shots={target["id"]}, scope=chapters_of_shots(inp, {target["id"], other["id"]}))
    dec = decompile(inp, {target["id"]})
    for d in dec.values():
        for s in d["spec"]["shots"]:
            if s["id"] == other["id"]:
                s["note"] = "sneaky"
    res = compile_specs(inp, _specs(dec), draw=False)
    assert any(other["id"] in v["message"] and v["code"] == "edit_outside_scope" for v in res.violations)


def test_a_locked_shot_cannot_be_changed_even_when_selected(arnolfini):
    inp = load_inputs(arnolfini)
    t = inp.current["shots"][3]
    t["locked"] = True
    inp = clone_inputs(inp, edit_shots={t["id"]}, scope=chapters_of_shots(inp, {t["id"]}))
    dec = decompile(inp, {t["id"]})
    for d in dec.values():
        for s in d["spec"]["shots"]:
            if s["id"] == t["id"]:
                s["technique"] = "STATIC-01"
    res = compile_specs(inp, _specs(dec), draw=False)
    new = {s["id"]: s for s in res.storyboard["shots"]}
    assert clean(new[t["id"]]) == clean(t)                      # the compiler kept it anyway
    assert res.violations == []


def test_scope_violations_direct():
    class Inp:
        pass
    from bti.draft.inputs import DraftInputs
    words = [{"w": "w%d" % i, "s": float(i), "e": i + 0.5} for i in range(20)]
    tm = {"duration": 20.0, "words": words, "beats": [], "chapters": []}
    mk = lambda i, w, note="": {"id": i, "start": {"w": w, "off": 0.0, "text": "w%d" % w}, "technique": "CAM-01", "slots": {}, "params": {}, "overlays": [], "locked": False, "note": note}
    cur = {"assets": {}, "shots": [mk("s1", 0), mk("s2", 5), mk("s3", 10)], "end": {"t": 20.0}}
    inp = DraftInputs(timing=tm, picks={"assets": {}}, current=cur)
    new = copy.deepcopy(cur)
    new["shots"][1]["note"] = "ok"
    assert scope_violations(inp, new, {"s2"}) == []
    new["shots"][2]["note"] = "bad"
    v = scope_violations(inp, new, {"s2"})
    assert len(v) == 1 and "s3" in v[0]["message"]
    new = copy.deepcopy(cur)
    new["shots"].append(mk("s9", 15))
    assert scope_violations(inp, new, {"s2"})                   # a new shot far from the scope
    del new["shots"][0]
    assert any("s1" in x["message"] for x in scope_violations(inp, new, {"s2"}))
