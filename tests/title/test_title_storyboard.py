"""A title reaches the storyboard: a PUT while a storyboard exists applies the channel identity again with the new title in the same request (the revision changes, the approval
stops standing, the answer says so), a same title changes nothing, a refusal of the engine never undoes the title, the function the job calls does the same, and a full draft compile
writes `identity.video_title` from the document. Real engine, a copy of the demo project (the pattern of tests/editor/test_identity_route.py)."""
import json
import shutil

import pytest

pytest.importorskip("cv2")
engine_api = pytest.importorskip("bti.engine.api")

from bti import identity as ID  # noqa: E402
from bti.editor.common import compute_rev, storyboard_approval  # noqa: E402
from bti.title import apply as tapply, store as T  # noqa: E402
from editor_helpers import PID, REPO  # noqa: E402

P = "/api/projects/%s" % PID
STYLE = json.loads((REPO / "style" / "gae" / "style.json").read_text(encoding="utf-8"))
TITLE = "The Saint Who Was Also an Advertisement"


def put_title_card(root):
    """The demo project has a chapter card but no title card: give it one (the pattern of the identity route's tests)."""
    f = root / PID / "storyboard.json"
    sb = json.loads(f.read_text(encoding="utf-8"))
    card = {"id": "s0099", "start": {"t": 5.0}, "technique": "X-CARD-02", "slots": {"background": {"asset": "A"}},
            "params": {"title": "DEMO PORTRAIT", "artist": "GENERATED", "year": "2026"}, "intent": "structure", "transition_in": None,
            "overlays": [], "locked": False, "source": "agent", "note": "title card"}
    sb["shots"].insert(1, card)
    f.write_text(json.dumps(sb, indent=1), encoding="utf-8")


@pytest.fixture()
def rc(make_client, root):
    if not STYLE.get("identity"):
        pytest.skip("style/gae/style.json has no identity block")
    shutil.copytree(REPO / "projects" / PID, root / PID, ignore=shutil.ignore_patterns("cache", "history"))
    put_title_card(root)
    return make_client(engine_module=engine_api)


def saved(c):
    return json.loads((c.root / PID / "storyboard.json").read_text(encoding="utf-8"))


def choose(c, style="raking"):
    r = c.put(P + "/identity", json={"style": style, "base_rev": c.get(P).json()["rev"]})
    assert r.status_code == 200, r.text
    return r.json()


def approve_as_stored(c):
    """The storyboard's approval as the approve route records it (by hand, like the identity route's tests: the demo project is not a real one)."""
    raw = saved(c)
    rev = compute_rev(raw)
    raw["approvals"] = {"storyboard": {"rev": rev, "approved_at": "2026-11-20T00:00:00+0000"}}
    (c.root / PID / "storyboard.json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
    assert storyboard_approval(saved(c)) == "fresh"
    return rev


def put(c, **body):
    rev = c.get(P + "/title").json()["rev"]
    return c.put(P + "/title", json={"base_rev": rev, **body})


def beat(sb):
    return next(s for s in sb["shots"] if s["technique"].startswith("ID-BRAND"))


def test_a_title_set_while_a_storyboard_exists_is_applied_in_the_same_request_and_the_approval_stops_standing(rc):
    choose(rc)
    before_rev = approve_as_stored(rc)
    r = put(rc, text=TITLE, actor="cli:operator")
    assert r.status_code == 200, r.text
    b = r.json()
    sb = saved(rc)
    assert b["storyboard"]["rev"] == compute_rev(sb) != before_rev and "s0099" in b["storyboard"]["changed"] and b["storyboard"]["approval_was_fresh"] is True
    assert b["storyboard"]["sentence"].startswith("Đã cập nhật tựa video trên storyboard (") and b["storyboard"]["sentence"].endswith("Storyboard đã đổi nên cần được duyệt lại.")
    assert sb["identity"] == {"style": "raking", "video_title": TITLE}
    assert beat(sb)["params"]["title"] == TITLE and beat(sb)["params"]["text"] == STYLE["identity"]["channel_name"]
    assert storyboard_approval(sb) == "stale"                                                    # the existing rule: the approved bytes are not the saved ones any more
    g = rc.get(P + "/title").json()
    assert g["storyboard"] == {"exists": True, "title": TITLE, "same": True, "off_voice": False}
    assert rc.get(P + "/identity").json()["video_title"] == TITLE


def test_the_same_title_again_changes_nothing_and_the_approval_keeps_standing(rc):
    choose(rc)
    put(rc, text=TITLE)
    rev = approve_as_stored(rc)
    r = put(rc, text=TITLE, actor="cli:other")
    assert r.status_code == 200 and r.json()["storyboard"] == {"rev": rev, "changed": [], "approval_was_fresh": False,
                                                              "sentence": "Storyboard đã có đúng tựa video này."}
    assert compute_rev(saved(rc)) == rev and storyboard_approval(saved(rc)) == "fresh"


def test_a_new_title_replaces_the_old_one_on_the_beat(rc):
    choose(rc)
    put(rc, text=TITLE)
    r = put(rc, text="Why Is a Saint Weighing a Ring?")
    assert r.status_code == 200 and beat(saved(rc))["params"]["title"] == "Why Is a Saint Weighing a Ring?" and saved(rc)["identity"]["video_title"] == "Why Is a Saint Weighing a Ring?"


def test_a_storyboard_that_has_no_style_yet_gets_the_default_one_with_the_title(rc):
    assert "identity" not in saved(rc)
    r = put(rc, text=TITLE)
    assert r.status_code == 200 and saved(rc)["identity"] == {"style": STYLE["identity"]["default_style"], "video_title": TITLE}


def test_a_refusal_of_the_engine_never_undoes_the_title(rc, monkeypatch):
    choose(rc)
    raw = saved(rc)

    def refuse(*a, **k):
        raise ID.IdentityError("identity_style_unknown", "the engine refused it")
    monkeypatch.setattr(ID, "apply_identity", refuse)
    r = put(rc, text=TITLE)
    assert r.status_code == 200
    sb = r.json()["storyboard"]
    assert sb["changed"] == [] and sb["rev"] is None and "the engine refused it" in sb["error"] and sb["sentence"].startswith("Chưa cập nhật được tựa video trên storyboard")
    assert saved(rc) == raw and T.chosen_text(rc.root / PID) == TITLE                           # the title is written; the storyboard takes it at the next draft or the next call
    assert rc.get(P + "/title").json()["storyboard"]["same"] is False


def test_a_storyboard_that_cannot_be_read_never_breaks_the_title(rc):
    (rc.root / PID / "storyboard.json").write_text("{ not json", encoding="utf-8")
    r = put(rc, text=TITLE)
    assert r.status_code == 200 and "error" in r.json()["storyboard"] and T.chosen_text(rc.root / PID) == TITLE


def test_the_function_the_job_calls_does_the_same_through_the_registered_hook(rc):
    choose(rc)
    approve_as_stored(rc)
    out = tapply.apply_to_storyboard(rc.root / PID, "A Title From The Job")
    assert out["changed"] and out["approval_was_fresh"] is True and saved(rc)["identity"]["video_title"] == "A Title From The Job"
    assert tapply.apply_to_storyboard(rc.root / "elsewhere" / PID, "x") is None                  # a project of another projects folder: no function registered for it


def test_a_project_without_a_storyboard_answers_none(client, root):
    from title_helpers import make_title_project
    make_title_project(root, "pk1")
    r = client.put("/api/projects/pk1/title", json={"base_rev": T.EMPTY_REV, "text": TITLE})
    assert r.status_code == 200 and r.json()["storyboard"] is None


def test_full_draft_proposal_apply_carries_person_and_agent_video_title_while_edit_keeps_old(rc):
    import copy
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import DraftInputs, normalize_timing
    from bti.draft.spec import shape_problems

    choose(rc)
    d = rc.root / PID
    sb = saved(rc)
    sb["identity"] = {"style": "raking", "video_title": "Old Stale Title"}
    (d / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")

    # Add a 15 s title+card gap before chapter 2 so compile places ID-BRAND-03, and keep `saved(rc)` off-voice beforehand.
    tm = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    words = tm["words"]
    split_w = next(i for i, w in enumerate(words) if w["s"] >= tm["chapters"][1]["start"] - 1e-6)
    for w in words[split_w:]:
        w["s"] = round(w["s"] + 15.0, 3)
        w["e"] = round(w["e"] + 15.0, 3)
    tm["duration"] = round(float(tm["duration"]) + 15.0, 3)
    gap_start = round(words[split_w - 1]["e"] + 0.05, 3)
    gap_end = round(words[split_w]["s"] - 0.05, 3)
    tm["chapters"][0].update({"id": "c01", "role": "cold_open", "title": "INTRO", "end": gap_start, "card": False})
    tm["chapters"][1].update({"id": "c02", "role": "chapter", "title": "DETAILS", "start": gap_end, "end": tm["duration"],
                              "card": True, "lead": {"kind": "title", "start": gap_start, "end": gap_end}})
    tm["beats"] = []
    narration = {"schema": "bti.narration/1", "project": PID, "chapters": []}
    picks = {"schema": "bti.picks/1", "main_asset": "A", "assets": copy.deepcopy(sb["assets"]), "beats": {}}
    specs = {}
    for idx, ch in enumerate(tm["chapters"]):
        bid = f"b{idx + 1:04d}"
        w0 = 0 if idx == 0 else split_w
        w1 = split_w if idx == 0 else len(words)
        tm["beats"].append({"id": bid, "chapter": ch["id"], "text": f"Sentence {idx + 1}.", "start": words[w0]["s"], "end": words[w1 - 1]["e"], "w0": w0, "w1": w1})
        narration["chapters"].append({"id": ch["id"], "role": ch["role"], "title": ch["title"], "beats": [{"id": bid, "text": f"Sentence {idx + 1}."}]})
        picks["beats"][bid] = {"items": [{"asset": "A", "role": "main"}], "kinds": ["detail"]}
        raw = {"schema": "bti.draft/1", "chapter": ch["id"], "shots": [
            {"beat": bid, "start_word": w0, "technique": "STATIC-01", "intent": "establish",
             "slots": {"image": {"asset": "A"}}, "params": {}, "note": f"ch {ch['id']}"}
        ]}
        clean, errs = shape_problems(raw, ch["id"])
        assert not errs, errs
        specs[ch["id"]] = clean
    tm_norm = normalize_timing(tm, narration)
    (d / "timing.json").write_text(json.dumps(tm_norm), encoding="utf-8")
    (d / "script").mkdir(exist_ok=True)
    (d / "script" / "narration.json").write_text(json.dumps(narration), encoding="utf-8")
    (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")

    # Person-set title while off-voice (make storyboard off-voice first).
    sb_off = copy.deepcopy(sb)
    for s in sb_off["shots"]:
        if s.get("intent") == "structure":
            s["start"] = {"t": 0.5}
    (d / "storyboard.json").write_text(json.dumps(sb_off, indent=1), encoding="utf-8")

    tget = rc.get(P + "/title").json()
    put = rc.put(P + "/title", json={"base_rev": tget["rev"], "text": "Person Chosen Title"})
    assert put.status_code == 200 and put.json()["storyboard"]["off_voice"] is True
    assert saved(rc)["identity"]["video_title"] == "Old Stale Title"

    res = compile_specs(DraftInputs(timing=tm_norm, picks=picks, narration=narration, current=saved(rc), title="Test Painting", style="gae", project_dir=d), specs, draw=False)
    assert res.storyboard["identity"]["video_title"] == "Person Chosen Title"

    prop_dir = d / "proposals"
    prop_dir.mkdir(exist_ok=True)
    (prop_dir / "p_full_person.json").write_text(json.dumps({"id": "p_full_person", "schema": "bti.proposal/1", "summary": "Full draft", "storyboard": res.storyboard}), encoding="utf-8")
    ar = rc.post(P + "/proposals/p_full_person/apply", json={"accept": "all"})
    assert ar.status_code == 200, ar.text
    after_person = saved(rc)
    assert after_person["identity"]["video_title"] == "Person Chosen Title"
    brand = next(s for s in after_person["shots"] if s.get("technique", "").startswith("ID-BRAND-"))
    assert brand["params"]["title"] == "Person Chosen Title"

    # Subsequent identity.set keeps the applied video_title.
    cur_rev = rc.get(P).json()["rev"]
    ir = rc.put(P + "/identity", json={"style": "dim", "base_rev": cur_rev})
    assert ir.status_code == 200, ir.text
    assert saved(rc)["identity"]["video_title"] == "Person Chosen Title"

    # Agent-generated title in title.json also lands on the applied full draft.
    T.write_generated(d, [{"text": "Agent Chosen Title", "form": "object", "lines": ["b0001"],
                           "scores": {"curiosity": 4, "concrete": 5, "central": 4, "clear": 5}, "why": "Ngắn gọn."}],
                      by="agent:mock", narration_rev_=T.narration_rev(d),
                      written={"model": "mock", "agent": "gem", "job_id": "j1", "session": "s1"})
    res_agent = compile_specs(DraftInputs(timing=tm_norm, picks=picks, narration=narration, current=saved(rc), title="Test Painting", style="gae", project_dir=d), specs, draw=False)
    assert res_agent.storyboard["identity"]["video_title"] == "Agent Chosen Title"
    (prop_dir / "p_full_agent.json").write_text(json.dumps({"id": "p_full_agent", "schema": "bti.proposal/1", "summary": "Full agent", "storyboard": res_agent.storyboard}), encoding="utf-8")
    ar2 = rc.post(P + "/proposals/p_full_agent/apply", json={"accept": "all"})
    assert ar2.status_code == 200, ar2.text
    assert saved(rc)["identity"]["video_title"] == "Agent Chosen Title"

    # Edit mode preserves what the storyboard already has (even when title.json changed afterward).
    rc.put(P + "/title", json={"base_rev": rc.get(P + "/title").json()["rev"], "text": "Person Changed Later"})
    cur_sb = saved(rc)
    cur_sb["identity"]["video_title"] = "Kept By Edit Mode"
    (d / "storyboard.json").write_text(json.dumps(cur_sb, indent=1), encoding="utf-8")
    first_shot_id = cur_sb["shots"][0]["id"]
    res_edit = compile_specs(DraftInputs(timing=tm_norm, picks=picks, narration=narration, current=cur_sb, title="Test Painting", style="gae", project_dir=d,
                                         edit_shots={first_shot_id}), specs, draw=False)
    assert res_edit.storyboard["identity"]["video_title"] == "Kept By Edit Mode"
    assert not any(c["kind"] == "identity" for c in __import__("bti.editor.proposals", fromlist=["diff"]).diff(cur_sb, res_edit.storyboard))
