"""GET and PUT /api/projects/{pid}/identity (contract 2026-11-18, section 7): the choice of the opening, channel-name beat and chapter
marks, saved the way a storyboard save is (same lock, same revision rule, same history copy). Real engine, a copy of the demo project;
the registry entries of the `ID-*` techniques and the identity block of style.json are the real ones."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("cv2")
engine_api = pytest.importorskip("bti.engine.api")

from bti.editor.app import create_app  # noqa: E402
from bti.editor.common import compute_rev  # noqa: E402
from editor_helpers import PID, REPO, editable  # noqa: E402

P = f"/api/projects/{PID}"
STYLE = json.loads((REPO / "style" / "gae" / "style.json").read_text(encoding="utf-8"))
BLOCK = STYLE.get("identity")


@pytest.fixture(autouse=True)
def _needs_the_block():
    if not BLOCK:
        pytest.skip("style/gae/style.json has no identity block yet")


def put_title_card(root, locked_card=False):
    """The demo project has a chapter card but no title card: give it one (inside the first shot, which has no overlay)."""
    f = root / PID / "storyboard.json"
    sb = json.loads(f.read_text(encoding="utf-8"))
    card = {"id": "s0099", "start": {"t": 5.0}, "technique": "X-CARD-02", "slots": {"background": {"asset": "A"}},
            "params": {"title": "DEMO PORTRAIT", "artist": "GENERATED", "year": "2026"}, "intent": "structure", "transition_in": None,
            "overlays": [], "locked": False, "source": "agent", "note": "title card"}
    sb["shots"].insert(1, card)
    for s in sb["shots"]:
        if s["id"] == "s0003":
            s["locked"] = locked_card
    f.write_text(json.dumps(sb, indent=1), encoding="utf-8")
    return sb


@pytest.fixture()
def rc(root):
    put_title_card(root)
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    with TestClient(app) as c:
        c.root = root
        yield c


def saved(c):
    return json.loads((c.root / PID / "storyboard.json").read_text(encoding="utf-8"))


def history(c):
    h = c.root / PID / "history"
    return sorted(h.glob("*.json")) if h.is_dir() else []


def choose(c, style, rev=None):
    rev = rev if rev is not None else c.get(P).json()["rev"]
    return c.put(f"{P}/identity", json={"style": style, "base_rev": rev})


# ------------------------------------------------------------------------------------------------------------ GET
def test_get_lists_the_options_with_their_words_and_no_style_yet(rc):
    r = rc.get(f"{P}/identity")
    assert r.status_code == 200
    body = r.json()
    assert body["style"] is None and body["default"] == BLOCK["default_style"]
    assert body["options"] == [{"id": k, "label": v["label_vi"]} for k, v in BLOCK["styles"].items()]
    assert [o["label"] for o in body["options"]] == ["Vệt sáng quét", "Tối lại, hiện tên"]


def test_get_unknown_project_is_404_and_a_project_without_a_storyboard_still_answers(rc):
    assert rc.get("/api/projects/nope/identity").status_code == 404
    (rc.root / "no_sb_yet").mkdir()
    (rc.root / "no_sb_yet" / "project.json").write_text("{}", encoding="utf-8")
    r = rc.get("/api/projects/no_sb_yet/identity")
    assert r.status_code == 200 and r.json()["style"] is None and len(r.json()["options"]) == 2


# ------------------------------------------------------------------------------------------------------------ PUT
def test_put_applies_the_style_and_answers_what_changed(rc):
    before = saved(rc)
    rev0 = rc.get(P).json()["rev"]
    r = choose(rc, "raking", rev0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"rev", "style", "changed", "skipped"}
    assert body["style"] == "raking" and body["skipped"] == [] and body["rev"] != rev0
    assert set(body["changed"]) == {"s0001", "s0099", "s0003"}               # the first shot (opening overlays), the title slot, the chapter card
    after = saved(rc)
    assert after["identity"] == {"style": "raking"} and compute_rev(after) == body["rev"]
    by = {s["id"]: s for s in after["shots"]}
    sd = BLOCK["styles"]["raking"]
    assert by["s0099"]["technique"] == sd["brand"] and by["s0099"]["params"]["text"] == BLOCK["channel_name"]
    assert by["s0003"]["technique"] == sd["mark"] and by["s0003"]["params"]["title"].startswith("1. ")
    assert {o["technique"] for o in by["s0001"]["overlays"]} >= {sd["open"], sd["label"]}
    assert [s["id"] for s in after["shots"]] == [s["id"] for s in before["shots"]]
    # what the page loads next is the new storyboard, valid, and the check has no error and no mismatch warning
    state = rc.get(P).json()
    assert state["rev"] == body["rev"] and state["storyboard"]["identity"] == {"style": "raking"}
    assert [i for i in state["issues"] if i["level"] == "error"] == []
    assert not [i for i in state["issues"] if i["code"] == "identity_technique_mismatch"]
    assert rc.get(f"{P}/identity").json()["style"] == "raking"


def test_the_choice_survives_a_reload_and_can_change(rc):
    assert choose(rc, "raking").status_code == 200
    r = choose(rc, "dim")
    assert r.status_code == 200 and r.json()["style"] == "dim"
    sd = BLOCK["styles"]["dim"]
    by = {s["id"]: s for s in saved(rc)["shots"]}
    assert by["s0003"]["technique"] == sd["mark"] and by["s0003"]["transition_in"]["technique"] == sd["mark_transition"]["technique"]
    app2 = create_app(projects_root=rc.root, engine_module=engine_api, media_module=None)          # a fresh process
    with TestClient(app2) as c2:
        assert c2.get(f"{P}/identity").json()["style"] == "dim"
        assert c2.get(P).json()["storyboard"]["identity"] == {"style": "dim"}


def test_the_same_style_again_changes_nothing_and_writes_no_history(rc):
    assert choose(rc, "raking").status_code == 200
    n = len(history(rc))
    rev = rc.get(P).json()["rev"]
    r = choose(rc, "raking", rev)
    assert r.status_code == 200 and r.json()["changed"] == [] and r.json()["rev"] == rev
    assert len(history(rc)) == n


def test_a_stale_base_rev_is_409_and_nothing_is_written(rc):
    rev0 = rc.get(P).json()["rev"]
    raw = saved(rc)
    files = len(history(rc))
    r = choose(rc, "raking", "0" * 64)
    assert r.status_code == 409 and r.json()["rev"] == rev0 and "base_rev" in r.json()["detail"]
    assert saved(rc) == raw and len(history(rc)) == files
    # a save by someone else makes the revision the page holds stale in the same way
    doc = editable(rc.get(P).json())
    doc["shots"][0]["note"] = "someone else"
    assert rc.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": rev0}).status_code == 200
    assert choose(rc, "raking", rev0).status_code == 409
    assert "identity" not in saved(rc)


@pytest.mark.parametrize("body, code", [({"style": "sepia"}, 422), ({"style": ""}, 422), ({"style": 5}, 422), ({}, 422), ({"style": "raking"}, 422)])
def test_bad_requests_are_422(rc, body, code):
    rev = rc.get(P).json()["rev"]
    r = rc.put(f"{P}/identity", json={**body, "base_rev": rev} if "style" in body and body != {"style": "raking"} else body)
    assert r.status_code == code, r.text
    assert "identity" not in saved(rc)


def test_an_unknown_style_names_the_choices(rc):
    r = choose(rc, "sepia")
    assert r.status_code == 422
    assert r.json()["code"] == "identity_style_unknown" and r.json()["allowed"] == list(BLOCK["styles"])
    assert "sepia" in r.json()["detail"]


def test_a_missing_base_rev_is_422(rc):
    r = rc.put(f"{P}/identity", json={"style": "raking"})
    assert r.status_code == 422 and "base_rev" in r.json()["detail"]


def test_unknown_project_and_missing_storyboard(rc):
    assert rc.put("/api/projects/nope/identity", json={"style": "raking", "base_rev": "x"}).status_code == 404
    (rc.root / "no_sb_yet2").mkdir()
    assert rc.put("/api/projects/no_sb_yet2/identity", json={"style": "raking", "base_rev": "x"}).status_code == 404


def test_a_locked_card_is_skipped_and_reported(root):
    put_title_card(root, locked_card=True)
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    with TestClient(app) as c:
        c.root = root
        r = choose(c, "raking")
        assert r.status_code == 200
        body = r.json()
        assert [x for x in body["skipped"] if x["shot"] == "s0003" and x["reason"] == "locked" and x["what"] == "mark"]
        assert "s0003" not in body["changed"]
        assert {s["id"]: s for s in saved(c)["shots"]}["s0003"]["technique"] == "X-CARD-01"
        # the check says it: a locked old card in a video with a chosen style is a warning
        assert [i for i in c.get(P).json()["issues"] if i["code"] == "identity_technique_mismatch"]


def test_no_title_slot_is_reported_and_the_rest_is_done(root):
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    with TestClient(app) as c:
        c.root = root
        r = choose(c, "dim")                     # the untouched demo project has no title card
        assert r.status_code == 200
        assert {"shot": None, "reason": "no_title_slot", "what": "brand"} == {k: r.json()["skipped"][0][k] for k in ("shot", "reason", "what")}
        assert "s0003" in r.json()["changed"] and saved(c)["identity"] == {"style": "dim"}


def test_the_approval_belongs_to_the_server_and_goes_stale(rc):
    rev = rc.get(P).json()["rev"]
    f = rc.root / PID / "storyboard.json"
    raw = saved(rc)
    raw["approvals"] = {"storyboard": {"rev": rev, "approved_at": "2026-11-18T00:00:00+0000"}}
    f.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    assert choose(rc, "raking", rev).status_code == 200
    after = saved(rc)
    assert after["approvals"]["storyboard"]["rev"] == rev != compute_rev(after)        # approved bytes are not the saved ones any more


# ------------------------------------------------------------------------------------------------------------ undo
def test_history_keeps_the_old_storyboard_and_the_restore_brings_it_back(rc):
    old = saved(rc)
    old_rev = compute_rev(old)
    files0 = history(rc)
    assert choose(rc, "raking").status_code == 200
    files1 = history(rc)
    assert len(files1) == len(files0) + 1
    newest = max(files1, key=lambda p: (p.stat().st_mtime_ns, p.name))
    kept = json.loads(newest.read_text(encoding="utf-8"))
    assert compute_rev(kept) == old_rev and "identity" not in kept                     # the copy IS the storyboard before the choice
    # the page's own restore: a damaged storyboard.json is replaced by the newest good copy of history/
    (rc.root / PID / "storyboard.json").write_text("{ not json", encoding="utf-8")
    r = rc.post(f"{P}/storyboard/restore", json={})
    assert r.status_code == 200 and r.json()["restored_from"] == newest.name
    back = saved(rc)
    assert compute_rev(back) == old_rev and "identity" not in back
    assert rc.get(f"{P}/identity").json()["style"] is None                              # and the selector says "Kiểu cũ" again


def test_the_page_undo_is_a_normal_save_of_the_previous_content(rc):
    old = saved(rc)
    state0 = rc.get(P).json()
    r = choose(rc, "raking", state0["rev"])
    assert r.status_code == 200
    put = rc.put(f"{P}/storyboard", json={"storyboard": old, "base_rev": r.json()["rev"]})
    assert put.status_code == 200 and put.json()["rev"] == state0["rev"]
    assert "identity" not in saved(rc) and rc.get(f"{P}/identity").json()["style"] is None


def test_edit_by_instruction_still_works_after_a_choice(rc):
    """The identity cards are shots like the others for every route that edits: a save with a changed note goes through."""
    assert choose(rc, "raking").status_code == 200
    state = rc.get(P).json()
    doc = editable(state)
    doc["shots"][0]["note"] = "an owner's note"
    r = rc.put(f"{P}/storyboard", json={"storyboard": doc, "base_rev": state["rev"]})
    assert r.status_code == 200 and saved(rc)["identity"] == {"style": "raking"}
