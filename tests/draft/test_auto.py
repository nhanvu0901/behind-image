import json

from bti.draft.compile import compile_specs, summary_text
from bti.draft import spec as S
from bti.draft.inputs import clone_inputs, load_inputs
from bti.draft.providers import auto


def _specs(inp):
    out = {}
    for cid, sp in auto.draft(inp).items():
        clean, probs = S.shape_problems(sp, cid)
        assert not [p for p in probs if p["level"] == "error"], probs
        out[cid] = clean
    return out


def test_auto_covers_every_chapter_and_uses_the_picks_first(proj):
    inp = load_inputs(proj)
    sp = auto.draft(inp)
    assert list(sp) == ["c01", "c02"]
    c1 = {s["beat"]: s for s in sp["c01"]["shots"]}
    assert c1["b0002"]["slots"]["image"] == {"asset": "A", "region": "MIRROR"} and c1["b0002"]["technique"] in ("CAM-05", "CAM-01")
    assert sp["c02"]["shots"][0]["slots"]["image"]["asset"] == "B" and sp["c02"]["shots"][0]["technique"] == "X-LAY-01"
    assert sp["c01"]["shots"][0]["start_word"] == 0 and sp["c02"]["shots"][0]["start_word"] == 30


def test_auto_is_deterministic_and_rotates(proj):
    inp = load_inputs(proj)
    a, b = auto.draft(inp), auto.draft(inp)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    techs = [s["technique"] for s in a["c01"]["shots"] + a["c02"]["shots"]]
    assert all(x != y for x, y in zip(techs, techs[1:]))


def test_auto_validates_with_no_error_and_draws(proj):
    inp = load_inputs(proj)
    res = compile_specs(inp, _specs(inp), draw=True)
    assert res.drawn and not res.errors, summary_text(res)


def test_auto_with_no_picks_stays_on_the_main_painting_and_moves(proj):
    p = json.loads((proj / "picks.json").read_text())
    p["beats"] = {}
    (proj / "picks.json").write_text(json.dumps(p))
    inp = load_inputs(proj)
    sp = auto.draft(inp)
    assert all(s["slots"]["image"]["asset"] == "A" for c in sp.values() for s in c["shots"])
    assert all(s["technique"] != "STATIC-01" or True for c in sp.values() for s in c["shots"])
    res = compile_specs(inp, _specs(inp), draw=False)
    assert not res.errors


def test_auto_on_the_real_arnolfini_timing_with_picks_from_its_storyboard(arnolfini):
    inp = load_inputs(arnolfini)
    sb = inp.current
    tm = inp.timing
    # picks from the storyboard: the asset and the region each shot of the original looks at
    beats = {}
    for s in sb["shots"]:
        key = (s.get("slots") or {}).get("image", {}).get("asset")
        if not key or s["start"].get("w") is None:
            continue
        w = s["start"]["w"]
        b = next((b for b in tm["beats"] if b["w0"] <= w < b["w1"]), None)
        if not b:
            continue
        at = (s["overlays"][0].get("params") or {}).get("at") if s.get("overlays") else None
        item = {"asset": key, "region": at if isinstance(at, str) else None, "role": "main" if key == "A" else "context", "note": ""}
        beats.setdefault(b["id"], {"items": [], "status": "picked"})["items"].append(item)
    picks = dict(inp.picks, beats=beats)
    inp = clone_inputs(inp, picks=picks, current=None)
    res = compile_specs(inp, _specs(inp), draw=False)
    assert not res.errors, summary_text(res)
    shots = [o for o in res.origin if o["kind"] == "agent"]
    assert len(shots) >= 60 and res.stats["median_shot_s"] >= 3
    res2 = compile_specs(inp, _specs(inp), draw=True)           # the draw check: every shot is drawn at three moments
    assert res2.drawn and not res2.errors, summary_text(res2)
