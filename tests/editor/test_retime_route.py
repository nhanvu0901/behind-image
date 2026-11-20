"""`POST /api/projects/{pid}/storyboard/retime`, the guard `storyboard_off_voice` on the approval and the export, and the video's title through
`PUT /api/projects/{pid}/identity` (worker introflow). Real engine, a small synthetic project whose storyboard the compiler wrote for a voice
with the new silences; the voice is then "made again" by writing another timing.json (another lead and title silence)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("cv2")
engine_api = pytest.importorskip("bti.engine.api")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "draft"))

from bti.draft import retime as RT  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.editor.common import compute_rev, storyboard_approval  # noqa: E402
from intro_helpers import brand03, compiled, intro_timing, make_project, style_doc  # noqa: E402,F401  (brand03 is a fixture)

PID = "intro"
P = "/api/projects/%s" % PID


@pytest.fixture()
def rc(tmp_path, brand03):
    proj = make_project(tmp_path, intro_timing(5.0, 10.2), PID)
    sb = compiled(proj).storyboard
    (proj / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    (proj / "audio").mkdir()
    (proj / "audio" / "mix.m4a").write_bytes(b"x" * 64)
    root = tmp_path / "projects"
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    with TestClient(app) as c:
        c.root, c.proj = root, proj
        yield c


def saved(c):
    return json.loads((c.proj / "storyboard.json").read_text(encoding="utf-8"))


def voice_again(c, lead=7.0, title=12.0):
    (c.proj / "timing.json").write_text(json.dumps(intro_timing(lead, title)), encoding="utf-8")
    return intro_timing(lead, title)


def rev(c):
    return c.get(P).json()["rev"]


def retime(c, base=None, **kw):
    return c.post("%s/storyboard/retime" % P, json={"base_rev": base if base is not None else rev(c), **kw})


def history(c):
    h = c.proj / "history"
    return sorted(h.glob("*.json")) if h.is_dir() else []


# ------------------------------------------------------------------------------------------------------------------ the route
def test_a_storyboard_that_fits_the_voice_is_left_alone_and_no_revision_is_written(rc):
    r0, raw, n = rev(rc), saved(rc), len(history(rc))
    r = retime(rc)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rev"] == r0 and body["changed"] == [] and body["report"]["inserted"] == [] and body["report"]["moved"] == [] and body["report"]["left"] == []
    assert saved(rc) == raw and len(history(rc)) == n and not (rc.proj / "changes").exists()


def test_after_the_voice_is_made_again_retime_puts_it_right_in_one_logged_batch_that_undo_takes_back(rc):
    before = saved(rc)
    new_t = voice_again(rc)
    assert RT.project_off_voice(rc.proj)                                       # the storyboard is off the new voice
    r0 = rev(rc)
    r = retime(rc, actor="cli:test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rev"] != r0 and body["changed"] and body["batch"] == "batch_0001"
    after = saved(rc)
    assert compute_rev(after) == body["rev"] and RT.project_off_voice(rc.proj) == [] and after["end"] == {"t": new_t["duration"]}
    assert len(history(rc)) >= 1                                              # saved the way the page's PUT saves (the older file is in history/)
    rep = body["report"]
    assert rep["left"] == [] and rep["end"]["to"] == {"t": new_t["duration"]} and {m["what"] for m in rep["moved"]} == {"start"}
    # one batch in the change log, in the operations' shape
    log = rc.get("%s/changes" % P).json()["changes"]
    assert [(c["batch"], c["doc"], c["actor"], c["ops"], c["undo_of"]) for c in log] == [("batch_0001", "storyboard", "cli:test", [{"op": "retime"}], None)]
    assert {c["target"]["shot"] for c in log[0]["changes"]} == set(body["changed"]) and all(c["what"].startswith("Cảnh ") for c in log[0]["changes"])
    assert log[0]["rev_before"] == r0 and log[0]["rev_after"] == body["rev"]
    # the same call twice: nothing changes, no new revision, no new batch
    again = retime(rc)
    assert again.status_code == 200 and again.json()["changed"] == [] and again.json()["rev"] == body["rev"] and len(rc.get("%s/changes" % P).json()["changes"]) == 1
    # undo: the whole document the batch changed comes back: the shots, and also the end of the video (fixes3: they used to stay as the retime left them)
    u = rc.post("%s/changes/batch_0001/undo" % P, json={"base_rev": body["rev"], "actor": "cli:test"})
    assert u.status_code == 200, u.text
    restored = saved(rc)
    assert restored["shots"] == before["shots"] and restored["end"] == before["end"] and restored.get("identity") == before.get("identity")
    assert {k: v for k, v in restored.items() if k != "approvals"} == {k: v for k, v in before.items() if k != "approvals"}
    parts = [c["target"] for c in u.json()["changes"] if "part" in c["target"]]
    assert parts == [{"part": "end"}]                                                 # the identity did not change here: the document had its style already


def test_a_stale_base_rev_is_409_and_nothing_is_written(rc):
    voice_again(rc)
    raw, n = saved(rc), len(history(rc))
    r = retime(rc, "0" * 64)
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["rev"] == rev(rc)
    assert saved(rc) == raw and len(history(rc)) == n


@pytest.mark.parametrize("body", [{}, {"base_rev": ""}, {"base_rev": 5}])
def test_a_missing_base_rev_is_422(rc, body):
    r = rc.post("%s/storyboard/retime" % P, json=body)
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"


def test_a_bad_actor_is_422_and_unknown_project_404(rc):
    assert retime(rc, actor="somebody").status_code == 422
    assert rc.post("/api/projects/nope/storyboard/retime", json={"base_rev": "x"}).status_code == 404


def test_a_locked_card_is_left_and_the_answer_says_so(rc):
    doc = saved(rc)
    mark = next(s for s in doc["shots"] if s["technique"] == "ID-MARK-01")
    mark["locked"] = True
    (rc.proj / "storyboard.json").write_text(json.dumps(doc), encoding="utf-8")
    voice_again(rc)
    r = retime(rc)
    assert r.status_code == 200
    left = r.json()["report"]["left"]
    assert ("card_off", mark["id"], True) in [(p["code"], p["shot"], p["locked"]) for p in left]        # the locked card is left where it was and reported ...
    assert [p["code"] for p in left if not p["locked"]] == ["title_off"]                                  # ... and so is the beat before it (it ends where the card starts)
    assert next(s for s in saved(rc)["shots"] if s["id"] == mark["id"])["start"] == mark["start"]


# ------------------------------------------------------------------------------------------------------------------ the guard
def approve(c, base=None):
    return c.post("%s/approve" % P, json={"rev": base if base is not None else rev(c)})


def test_approving_is_refused_while_the_storyboard_does_not_fit_the_voice_and_works_after_the_retime(rc):
    assert approve(rc).status_code == 200                                      # it fits the voice it was made for
    assert storyboard_approval(saved(rc)) == "fresh"
    voice_again(rc)
    r = approve(rc)
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "storyboard_off_voice" and body["retry"] == "after_fix" and "storyboard.retime" in body["fix"]
    assert {p["code"] for p in body["problems"]} >= {"title_off", "card_off", "end_off"}
    assert "does not fit the voice" in body["detail"]
    assert retime(rc).status_code == 200
    assert storyboard_approval(saved(rc)) == "stale"                           # the revision changed: the earlier approval no longer stands
    assert approve(rc).status_code == 200 and storyboard_approval(saved(rc)) == "fresh"


def test_the_export_is_refused_while_the_storyboard_does_not_fit_the_voice(rc):
    assert approve(rc).status_code == 200
    voice_again(rc)
    r = rc.post("%s/export/start" % P)
    assert r.status_code == 409 and r.json()["code"] == "storyboard_off_voice" and r.json()["problems"], r.text
    assert "storyboard.retime" in r.json()["fix"]


# ------------------------------------------------------------------------------------------------------------ the video's title
def put_identity(c, body, base=None):
    return c.put("%s/identity" % P, json={**body, "base_rev": base if base is not None else rev(c)})


def beat(c):
    return next(s for s in saved(c)["shots"] if s["technique"] == "ID-BRAND-03")


def test_the_video_title_is_set_changed_and_removed_through_the_route(rc):
    assert rc.get("%s/identity" % P).json()["video_title"] is None
    r = put_identity(rc, {"video_title": "  The Mirror\nThat Remembers "})                # the style stays: only the title was sent
    assert r.status_code == 200, r.text
    assert r.json()["style"] == "raking" and r.json()["video_title"] == "The Mirror That Remembers" and beat(rc)["id"] in r.json()["changed"]
    assert saved(rc)["identity"] == {"style": "raking", "video_title": "The Mirror That Remembers"}
    assert beat(rc)["params"]["title"] == "The Mirror That Remembers" and beat(rc)["params"]["subtitle"] == "Intro · Some Painter, 1434"
    assert rc.get("%s/identity" % P).json()["video_title"] == "The Mirror That Remembers"
    assert [i for i in rc.get(P).json()["issues"] if i["level"] == "error"] == []
    r = put_identity(rc, {"video_title": "Another Title", "style": "raking"})
    assert r.status_code == 200 and beat(rc)["params"]["title"] == "Another Title"
    same = put_identity(rc, {"video_title": "Another Title"})
    assert same.status_code == 200 and same.json()["changed"] == []
    r = put_identity(rc, {"video_title": ""})
    assert r.status_code == 200 and r.json()["video_title"] is None
    assert saved(rc)["identity"] == {"style": "raking"} and beat(rc)["params"]["title"] == "Intro" and rc.get("%s/identity" % P).json()["video_title"] is None


@pytest.mark.parametrize("body, status, code", [({"video_title": "x" * 91}, 422, "video_title_too_long"), ({"video_title": 5}, 422, "video_title_invalid"),
                                                ({"video_title": ["a"]}, 422, "video_title_invalid"), ({}, 422, "identity_style_required")])
def test_a_title_that_is_not_one_line_of_90_characters_is_refused(rc, body, status, code):
    raw = saved(rc)
    r = put_identity(rc, body)
    assert r.status_code == status and r.json()["code"] == code, r.text
    assert saved(rc) == raw


def test_a_title_of_exactly_90_characters_is_fine_and_the_style_choice_keeps_it(rc):
    t = "a" * 90
    assert put_identity(rc, {"video_title": t}).status_code == 200 and saved(rc)["identity"]["video_title"] == t
    assert put_identity(rc, {"style": "dim"}).status_code == 200
    assert saved(rc)["identity"] == {"style": "dim", "video_title": t}              # choosing another style does not lose the title
    assert put_identity(rc, {"video_title": t}, "0" * 64).status_code == 409


def test_a_full_recompile_keeps_the_video_title(rc):
    put_identity(rc, {"video_title": "The Mirror That Remembers"})
    again = compiled(rc.proj).storyboard
    assert again["identity"] == {"style": "raking", "video_title": "The Mirror That Remembers"}


# ------------------------------------------------------------------------------------------------------------ fixes3: a title on a storyboard that is off the voice, and the undo of a retime
def title_put(c, text="The Mirror That Remembers", **kw):
    return c.put("%s/title" % P, json={"base_rev": c.get("%s/title" % P).json()["rev"], "text": text, "actor": "cli:test", **kw})


def test_the_identity_route_answers_storyboard_off_voice_instead_of_the_validators_raw_errors(rc):
    voice_again(rc)                                                              # the voice was made again: the cards and the beat sit where the old voice put them
    raw, n = saved(rc), len(history(rc))
    for body in ({"video_title": "The Mirror That Remembers"}, {"style": "dim"}, {"video_title": "x", "style": "raking"}):
        r = put_identity(rc, body)
        assert r.status_code == 409, r.text
        j = r.json()
        assert j["code"] == "storyboard_off_voice" and j["retry"] == "after_fix" and "storyboard.retime" in j["fix"], j
        assert {p["code"] for p in j["problems"]} >= {"title_off", "card_off", "end_off"} and "does not fit the voice" in j["detail"]
    assert saved(rc) == raw and len(history(rc)) == n                              # nothing was written
    assert put_identity(rc, {"video_title": "x"}, "0" * 64).status_code == 409 and put_identity(rc, {"video_title": "x"}, "0" * 64).json()["code"] == "stale_revision"
    assert retime(rc).status_code == 200
    ok = put_identity(rc, {"video_title": "The Mirror That Remembers"})             # fitted to the voice: the same call works
    assert ok.status_code == 200, ok.text
    assert beat(rc)["params"]["title"] == "The Mirror That Remembers"


def test_a_title_set_while_the_storyboard_is_off_the_voice_is_stored_and_retime_writes_it_onto_the_beat_and_undo_takes_it_back(rc):
    before = saved(rc)
    voice_again(rc)
    off_raw = saved(rc)
    r = title_put(rc)
    assert r.status_code == 200, r.text
    sb = r.json()["storyboard"]
    assert sb["off_voice"] is True and sb["code"] == "storyboard_off_voice" and sb["changed"] == [] and sb["approval_was_fresh"] is False
    assert sb["sentence"].startswith("Storyboard đang lệch với giọng đọc") and "Khớp lại với giọng đọc" in sb["sentence"] and "ngay khi khớp xong" in sb["sentence"]
    g = rc.get("%s/title" % P).json()["storyboard"]                               # the strip of the page reads this: it says so instead of failing
    assert g == {"exists": True, "title": None, "same": False, "off_voice": True}
    assert r.json()["title"]["text"] == "The Mirror That Remembers" and saved(rc) == off_raw                # stored in the title document, the storyboard untouched
    assert rc.get("%s/title" % P).json()["title"]["text"] == "The Mirror That Remembers"
    # the same title again says the same thing and still stores it
    assert title_put(rc, "Another One Entirely").json()["storyboard"]["off_voice"] is True
    assert title_put(rc, "The Mirror That Remembers").status_code == 200
    # retime reads the title document: the beat shows the title as soon as it is fitted to the voice
    rt = retime(rc, actor="cli:test")
    assert rt.status_code == 200, rt.text
    after = saved(rc)
    assert RT.project_off_voice(rc.proj) == [] and after["identity"]["video_title"] == "The Mirror That Remembers"
    assert beat(rc)["params"]["title"] == "The Mirror That Remembers" and rt.json()["report"]["video_title"] == {"from": None, "to": "The Mirror That Remembers"}
    assert rc.get("%s/title" % P).json()["storyboard"] == {"exists": True, "title": "The Mirror That Remembers", "same": True, "off_voice": False}
    # the title is in the batch, so the undo takes it back with the rest of the document
    u = rc.post("%s/changes/batch_0001/undo" % P, json={"base_rev": rt.json()["rev"], "actor": "cli:test"})
    assert u.status_code == 200, u.text
    restored = saved(rc)
    assert restored.get("identity") == before.get("identity") and "video_title" not in (restored.get("identity") or {})
    assert {k: v for k, v in restored.items() if k != "approvals"} == {k: v for k, v in off_raw.items() if k != "approvals"}
    assert {"part": "end"} in [c["target"] for c in u.json()["changes"]] and {"part": "identity"} in [c["target"] for c in u.json()["changes"]]
    assert all(c["what"] for c in u.json()["changes"])


def test_the_title_document_wins_over_the_title_the_storyboard_carries_and_a_fitted_storyboard_is_left_alone(rc):
    assert put_identity(rc, {"video_title": "Written Through The Identity Route"}).status_code == 200
    r0, raw = rev(rc), saved(rc)
    again = retime(rc)                                                           # no title document: the storyboard's own title stays, nothing to move
    assert again.status_code == 200 and again.json()["changed"] == [] and again.json()["rev"] == r0 and saved(rc) == raw
    assert title_put(rc, "The Title Document Says This").json()["storyboard"]["changed"]    # on the voice: applied in the same call
    assert saved(rc)["identity"]["video_title"] == "The Title Document Says This"
    again = retime(rc)
    assert again.json()["changed"] == [] and again.json()["report"]["video_title"] is None


def test_the_undo_of_a_retime_names_a_part_that_was_changed_since_and_writes_nothing(rc):
    voice_again(rc)
    rt = retime(rc, actor="cli:test")
    assert rt.status_code == 200 and rt.json()["batch"] == "batch_0001"
    doc = saved(rc)
    doc["end"] = {"t": doc["end"]["t"] + 3.0}                                    # the page saved another end after the retime
    (rc.proj / "storyboard.json").write_text(json.dumps(doc), encoding="utf-8")
    raw = saved(rc)
    u = rc.post("%s/changes/batch_0001/undo" % P, json={"base_rev": rev(rc), "actor": "cli:test"})
    assert u.status_code == 409 and u.json()["code"] == "undo_conflict", u.text
    assert {"thing": {"part": "end"}, "key": "part:end", "batches": []} in u.json()["conflicts"] and "part end" in u.json()["detail"]
    assert saved(rc) == raw


def test_overlay_fitting_is_in_the_same_change_log_batch(rc):
    sb = saved(rc)
    timing = intro_timing(5.0, 10.2)
    f = RT._Fit(sb, timing, style_doc())
    i = next(i for i, s in enumerate(sb['shots']) if 'w' in s.get('start', {}) and f.t1[i] - f.t0[i] > 2)
    shot = sb['shots'][i]
    shot.setdefault('overlays', []).append({'id': 'fit-test', 'technique': 'X-ANN-01', 'intent': 'point_at',
                                             'start': dict(shot['start']), 'dur': f.t1[i] - f.t0[i] + 1,
                                             'params': {'text': 'Example'}, 'slots': {}})
    (rc.proj / 'storyboard.json').write_text(json.dumps(sb), encoding='utf-8')
    response = retime(rc, actor='cli:test')
    assert response.status_code == 200, response.text
    item = next(o for o in response.json()['report']['overlays'] if o['overlay'] == 'fit-test')
    log = rc.get('%s/changes' % P).json()['changes']
    change = next(c for c in log[0]['changes'] if c['target'].get('overlay') == 'fit-test')
    assert len(log) == 1 and change['from'] == item['from'] and change['to'] == item['to']
