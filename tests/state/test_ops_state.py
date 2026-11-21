"""The state answer and the real operations (bti/ops): `picks.ops` and `storyboard.ops` with the registry's own example in a dry run, the change
log actions, and the size and depth limits of the operations routes answering with `code`, `fix` and `retry`. The project is the operations'
own fixture (tests/ops), the real engine, nothing from the network."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "ops"))

from ops_helpers import PID, make_project, pk, pk_rev, sb, sb_rev  # noqa: E402
from state_helpers import action, ids  # noqa: E402

engine_api = pytest.importorskip("bti.engine.api")

from bti.editor.app import create_app  # noqa: E402
from bti.ops import registry  # noqa: E402
from bti.ops.errors import ERRORS  # noqa: E402


@pytest.fixture()
def oc(root):
    """The app with the real engine on the operations' fixture project."""
    d = make_project(root)
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.pid, c.pdir, c.root = PID, d, root
        c.sb = f"/api/projects/{PID}/storyboard/ops"
        c.pk = f"/api/projects/{PID}/picks/ops"
        yield c


def state(c):
    r = c.get(f"/api/projects/{PID}/state")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("aid,doc,route", [("picks.ops", "picks", "/picks/ops"), ("storyboard.ops", "storyboard", "/storyboard/ops")])
def test_the_ops_example_body_is_the_registrys_own_and_the_route_accepts_it(oc, aid, doc, route):
    a = action(state(oc), aid)
    first = next(iter(registry.defs(doc).values()))
    assert a["method"] == "POST" and a["path"] == f"/api/projects/{PID}{route}" and a["ready"] is True and a["advances"] is False
    assert a["body"]["ops"] == [first.example] and a["body"]["dry_run"] is True                      # taken from the registry, not written by hand
    assert a["body"]["actor"].startswith("agent:") and a["body"]["base_rev"] == (sb_rev(oc) if doc == "storyboard" else pk_rev(oc))
    assert a["fill"] == ["ops"] and a["body_template"]["ops"] is None and a["body_template"]["dry_run"] is False
    before = {p.name: p.read_bytes() for p in oc.pdir.iterdir() if p.is_file()}
    r = oc.post(a["path"], json=a["body"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["dry_run"] is True and j["batch"] is None and j["applied"] == 1 and j["changes"]
    assert before == {p.name: p.read_bytes() for p in oc.pdir.iterdir() if p.is_file()}              # a dry run writes nothing


def test_the_template_is_a_batch_the_route_takes(oc):
    a = action(state(oc), "picks.ops")
    body = {**a["body_template"], "ops": [{"op": "skip_beat", "beat": "b0004"}]}
    r = oc.post(a["path"], json=body)
    assert r.status_code == 200 and r.json()["batch"] and r.json()["applied"] == 1, r.text


def test_the_change_log_actions_appear_with_the_first_batch_and_undo_the_newest_one(oc):
    st = state(oc)
    assert "changes.list" not in ids(st) and "changes.undo" not in ids(st)
    assert pk(oc, [{"op": "skip_beat", "beat": "b0004"}]).status_code == 200
    st = state(oc)
    lst, undo = action(st, "changes.list"), action(st, "changes.undo")
    assert (lst["method"], lst["path"], lst["body"], lst["ready"]) == ("GET", f"/api/projects/{PID}/changes", None, True)
    assert lst["step"] == "picks" and undo["step"] == "picks"
    assert undo["path"] == f"/api/projects/{PID}/changes/batch_0001/undo" and undo["method"] == "POST" and undo["ready"] is True
    assert undo["body"]["base_rev"] == pk_rev(oc) and undo["body"]["actor"].startswith("agent:")
    assert oc.get(lst["path"]).status_code == 200 and oc.get(lst["path"]).json()["changes"][0]["batch"] == "batch_0001"
    r = oc.post(undo["path"], json=undo["body"])
    assert r.status_code == 200 and r.json()["undo_of"] == "batch_0001" and r.json()["batch"] == "batch_0002", r.text
    after = action(state(oc), "changes.undo")                                  # the batch that was undone is not offered again
    assert after["path"].endswith("/changes/batch_0002/undo")


def test_the_newest_batch_that_can_be_undone_is_found_past_one_that_cannot(oc):
    assert sb(oc, [{"op": "lock", "shot": "s0003"}]).status_code == 200                     # batch 1 (storyboard)
    assert pk(oc, [{"op": "skip_beat", "beat": "b0004"}]).status_code == 200                # batch 2 (picks)
    # the page edits the same line afterwards: batch 2 can no longer be undone, batch 1 still can
    doc = json.loads((oc.pdir / "picks.json").read_text(encoding="utf-8"))
    doc["beats"]["b0004"]["note"] = "edited by the page"
    r = oc.put(f"/api/projects/{PID}/picks", json={"picks": doc, "base_rev": pk_rev(oc)})
    assert r.status_code == 200, r.text
    undo = action(state(oc), "changes.undo")
    assert undo["path"].endswith("/changes/batch_0001/undo") and undo["step"] == "edit" and undo["body"]["base_rev"] == sb_rev(oc)
    assert oc.post(undo["path"], json=undo["body"]).status_code == 200


def test_no_undo_is_offered_when_nothing_can_be_undone(oc):
    assert pk(oc, [{"op": "skip_beat", "beat": "b0004"}]).status_code == 200
    doc = json.loads((oc.pdir / "picks.json").read_text(encoding="utf-8"))
    doc["beats"]["b0004"]["note"] = "edited by the page"
    assert oc.put(f"/api/projects/{PID}/picks", json={"picks": doc, "base_rev": pk_rev(oc)}).status_code == 200
    st = state(oc)
    assert "changes.list" in ids(st) and "changes.undo" not in ids(st)


def test_the_operations_routes_refuse_by_size_and_depth_with_code_fix_and_retry(oc):
    """The body limits are answered before any route runs (bti.editor.common.DepthLimitMiddleware); the net of bti.editor.hints completes them."""
    deep = '{"a":' * 60 + "1" + "}" * 60
    for url in (oc.pk, oc.sb, f"/api/projects/{PID}/changes/batch_0001/undo"):
        r = oc.post(url, content=deep, headers={"content-type": "application/json"})
        b = r.json()
        assert r.status_code == 422 and b["code"] == "too_deep" and b["retry"] == "after_fix" and b["fix"].endswith("."), (url, r.text)
        assert "detail" in b
    big = b'{"a":"' + b"x" * (9 * 1024 * 1024) + b'"}'
    for url in (oc.pk, oc.sb):
        r = oc.post(url, content=big, headers={"content-type": "application/json"})
        b = r.json()
        assert r.status_code == 413 and b["code"] == "too_large" and b["retry"] == "after_fix" and b["fix"].endswith("."), (url, r.text)


def test_every_error_of_the_operations_is_one_vocabulary_with_the_rest(oc):
    r = oc.post(oc.pk, content=b"{", headers={"content-type": "application/json"})
    b = r.json()
    assert r.status_code == 422 and b["code"] == "invalid_request" and b["fields"][0]["path"] == "" and b["fix"] == ERRORS["invalid_request"][2]
    r = oc.post("/api/projects/nope/picks/ops", json={"base_rev": "x", "actor": "human", "ops": [{"op": "skip_beat", "beat": "b0001"}]})
    assert r.status_code == 404 and r.json()["code"] == "project_not_found"
    r = oc.put(f"/api/projects/{PID}/storyboard", json={"storyboard": {}})
    assert r.json()["code"] == "invalid_request" and r.json()["fields"][0]["path"] == "base_rev"      # the same code the operations use for a missing base_rev
    r = oc.post(oc.pk, json={"base_rev": "old", "actor": "human", "ops": [{"op": "skip_beat", "beat": "b0001"}]})
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == pk_rev(oc)
    r = oc.put(f"/api/projects/{PID}/storyboard", json={"storyboard": {}, "base_rev": "old"})
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == sb_rev(oc)
    assert r.json()["fix"] == ERRORS["stale_revision"][2]                                      # one sentence for both


# ---------------------------------------------------------------- c2box: the prompt boxes in the state answer
def test_the_two_boxes_are_listed_with_a_template_their_routes_take(oc, monkeypatch):
    """`draft.edit` (step 5) and `picks.edit` (step 4): the caller supplies the instruction and the scope (`fill`); the template names the revision
    to read from and every other field the route takes. The step 4 route takes the template as it is (a scope of lines, a chapter or `all`)."""
    import bti.draft.run as draft_run
    s = state(oc)
    sb, pk_ = action(s, "draft.edit"), action(s, "picks.edit")
    assert sb["fill"] == ["instruction", "scope"] and sb["body_template"] == {"instruction": None, "scope": None, "base_rev": sb_rev(oc), "mode": "auto"}
    assert pk_["method"] == "POST" and pk_["path"] == f"/api/projects/{PID}/picks/edit" and pk_["step"] == "picks"
    assert pk_["fill"] == ["instruction", "scope"] and pk_["body_template"] == {"instruction": None, "scope": None, "base_rev": pk_rev(oc)}
    assert pk_["body"] is None and pk_["long_job"] is True and pk_["uses_model"] is True and pk_["cost"]["kind"] == "model" and pk_["agent"]["id"]
    assert pk_["follow"] == "GET /api/longjobs/{job_id}" and pk_["advances"] is False and pk_["gate"] is False
    seen = {}

    def fake_start(pid, d, **kw):
        seen.update(kw)
        return {"id": "fakejob", "turn_id": "t_x", "meta": {"model": "mock", "agent": None}}
    monkeypatch.setattr(draft_run, "start_picks", fake_start)
    for scope in ({"beats": ["b0003"]}, {"chapter": "c01"}, {"all": True}):
        r = oc.post(pk_["path"], json={**pk_["body_template"], "instruction": "dòng này chỉ cho xem khuôn mặt", "scope": scope})
        assert r.status_code == 200 and r.json()["job_id"] == "fakejob", r.text
        assert seen["edit_scope"] == scope and seen["base_rev"] == pk_rev(oc)


def test_the_picks_box_is_not_ready_while_an_edit_job_runs_or_when_its_agent_cannot_run(oc, monkeypatch):
    import bti.agents as agents_mod
    a = action(state(oc), "picks.edit")
    assert a["ready"] is True and a["needs"] == []
    from bti.editor import state_api
    monkeypatch.setattr(state_api.Ctx, "busy", lambda self, family: family == "draft")
    assert action(state(oc), "picks.edit")["needs"] == ["no_running_job"]


def test_the_refusals_of_the_picks_box_routes_carry_code_fix_and_retry(oc):
    u = f"/api/projects/{PID}/picks/edit"
    for body, code in (({"instruction": "", "scope": {"all": True}}, "edit_empty_instruction"), ({"instruction": "x", "scope": {}}, "edit_bad_scope"),
                       ({"instruction": "x", "scope": {"beats": ["b9999"]}}, "edit_bad_scope"), ({"instruction": "x" * 2001, "scope": {"all": True}}, "edit_bad_scope"),
                       ({"instruction": "x", "scope": {"all": True}, "model": 5}, "bad_model"), ([], "invalid_request")):
        r = oc.post(u, json=body)
        assert r.status_code == 422 and r.json()["code"] == code and r.json()["fix"] and r.json()["retry"] in ("after_fix", "no", "later"), (body, r.text)
    r = oc.post(u, json={"instruction": "x", "scope": {"all": True}, "base_rev": "0" * 40})
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == pk_rev(oc)


def test_the_change_log_of_a_box_turn_is_what_changes_undo_names(oc):
    """The state names the newest batch that can be undone: the list of changes on both pages shows "Hoàn tác" on that row."""
    from bti.ops import runner  # noqa: F401
    r = oc.post(oc.sb, json={"base_rev": sb_rev(oc), "actor": "agent:mock", "note": "làm vòng sáng to hơn", "scope": {"shots": ["s0002"]},
                             "ops": [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 260, "ry": 260}}]})
    assert r.status_code == 200, r.text
    s = state(oc)
    u = action(s, "changes.undo")
    assert u["path"].endswith("/changes/%s/undo" % r.json()["batch"]) and u["step"] == "edit" and u["body"]["base_rev"] == sb_rev(oc)
    log = oc.get(f"/api/projects/{PID}/changes?doc=storyboard").json()["changes"]
    assert log[0]["batch"] == r.json()["batch"] and log[0]["note"] == "làm vòng sáng to hơn" and log[0]["undone_by"] is None
