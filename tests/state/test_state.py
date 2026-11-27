"""GET /api/projects/{pid}/state: the steps the page's step bar shows, and every call that can be made now."""
import json
import shutil
import threading

import pytest

from state_helpers import DEMO_SRC, PID, STAGES, action, build, ids, make_book_project, route_ok, wait_job

SCRIPT_REDO = ["outline.generate", "outline.import", "narration.generate", "narration.import", "narration.ops"]
PICKS_OPEN = ["picks.search", "picks.import", "picks.import_book_image", "picks.import_clip", "picks.put", "picks.edit", "picks.ops"]
PICKS_OPEN_MAIN = ["picks.search", "picks.import", "picks.import_book_image", "picks.import_clip", "picks.put", "picks.auto", "picks.edit", "picks.ops"]    # c3picks: with a main painting the agent's choice of pictures is ready too, before the request box
EDIT_OPEN = ["draft.start", "storyboard.validate", "storyboard.preview", "storyboard.put", "storyboard.ops", "draft.edit", "identity.set"]
EDIT_OPEN_NO_DRAFT = EDIT_OPEN[1:]       # titlestep: with no title written and an agent that could write it, `draft.start` waits (need `title_done`) and comes last, after the other gated calls

# The exact list of action ids at each stage, in the order the answer gives them: the repair of a damaged project, then what
# moves the project forward, then the other calls that are ready, then the ones gated ahead (each group in the order of the steps).
EXPECTED = {
    "new": ["outline.generate", "pipeline.set", "outline.import", "title.set", "outline.approve", "narration.generate", "narration.import", "narration.ops",
            "narration.approve", "title.generate"],
    "outline_waiting": ["outline.approve", "pipeline.set", "outline.generate", "outline.import", "narration.import", "title.set", "narration.generate",
                        "narration.ops", "narration.approve", "title.generate"],
    # titlestep: once the narration is approved the title is the first thing that advances (the step `script` comes before the voice); with a storyboard it is ready but does not advance
    "narration_approved": ["title.generate", "voice.generate", "pipeline.set", *SCRIPT_REDO, "title.set", *PICKS_OPEN, "picks.suggest", "picks.auto", "picks.approve"],       # no main painting yet: picks.auto is gated (needs main_asset)
    "voiced": ["title.generate", "pipeline.set", *SCRIPT_REDO, "title.set", "voice.generate", *PICKS_OPEN, "picks.suggest", "picks.auto", "picks.approve"],
    "picks_approved": ["title.generate", "pipeline.set", *SCRIPT_REDO, "title.set", "voice.generate", *PICKS_OPEN_MAIN, "picks.suggest", "draft.start"],
    "proposal_waiting": ["title.generate", "proposal.apply", "pipeline.set", *SCRIPT_REDO, "title.set", "voice.generate", *PICKS_OPEN_MAIN, "picks.suggest", "draft.start"],
    "drafted": ["storyboard.review", "storyboard.approve", "pipeline.set", *SCRIPT_REDO, "title.generate", "title.set", "voice.generate", *PICKS_OPEN_MAIN, *EDIT_OPEN_NO_DRAFT, "music.set", "scorecard.make", "picks.suggest", "draft.start", "music.auto"],
    "storyboard_approved": ["export.start", "pipeline.set", *SCRIPT_REDO, "title.generate", "title.set", "voice.generate", *PICKS_OPEN_MAIN, *EDIT_OPEN_NO_DRAFT, "music.set", "scorecard.make", "picks.suggest", "draft.start", "music.auto"],
    "exported": ["pipeline.set", *SCRIPT_REDO, "title.generate", "title.set", "voice.generate", *PICKS_OPEN_MAIN, *EDIT_OPEN_NO_DRAFT, "music.set", "export.start", "scorecard.make", "picks.suggest", "draft.start", "music.auto"],
}
STAGE_OF = {"new": "selected", "outline_waiting": "selected", "narration_approved": "script", "voiced": "voiced",
            "picks_approved": "picked", "proposal_waiting": "picked", "drafted": "storyboard", "storyboard_approved": "approved",
            "exported": "rendered"}
GATES = {"outline.approve", "narration.approve", "picks.approve", "storyboard.approve"}
OPS_ACTIONS = ("picks.ops", "storyboard.ops")
ACTION_KEYS = {"id", "step", "label", "method", "path", "body", "ready", "needs", "gate", "auto_ok", "long_job", "uses_model", "agent",
               "cost", "advances"}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Nothing heavy or paid starts: the starters of the voice, the draft, the export and the preview, and the picture search, answer
    at once. What the tests check is that the route takes the body the state gives, not what the stage does with it."""
    import bti.draft.run as draft_run
    import bti.editor.jobs as jobs_mod
    import bti.export.run as export_run
    import bti.voice.run as voice_run
    from bti.picks import service
    monkeypatch.setattr(voice_run, "start", lambda *a, **k: {"id": "fakevoicejob"})
    monkeypatch.setattr(draft_run, "start", lambda *a, **k: {"id": "fakedraftjob", "meta": {}})
    from bti.picks import auto as picks_auto                                          # c3picks: the agent's choice of pictures starts no model either
    monkeypatch.setattr(picks_auto, "start", lambda *a, **k: {"id": "fakepicksjob", "meta": {}})
    from bti.title import job as title_job                                              # titlestep: the title writer starts no agent either
    monkeypatch.setattr(title_job, "start", lambda *a, **k: {"id": "faketitlejob", "meta": {}})
    monkeypatch.setattr(export_run, "start", lambda *a, **k: {"id": "fakeexportjob"})
    monkeypatch.setattr(jobs_mod, "render_preview", lambda *a, **k: "/api/projects/x/files/cache/previews/p.mp4")
    monkeypatch.setattr(service, "search", lambda *a, **k: {"items": [], "errors": []})


@pytest.fixture()
def at(client, monkeypatch):
    """`at(stage)` -> (client, pid, state) of a fresh book project brought to `stage`."""
    def go(stage):
        make_book_project(client.root)
        pid = build(stage, client, monkeypatch)
        r = client.get(f"/api/projects/{pid}/state")
        assert r.status_code == 200, r.text
        return client, pid, r.json()
    return go


@pytest.mark.parametrize("stage", STAGES)
def test_the_exact_action_ids_at_each_stage(at, stage):
    c, pid, st = at(stage)
    assert ids(st) == EXPECTED[stage], repr(ids(st))
    assert st["project"] == pid and st["stage"] == STAGE_OF[stage]


@pytest.mark.parametrize("stage", STAGES)
def test_the_steps_are_the_ones_the_page_shows(at, stage):
    c, pid, st = at(stage)
    pipe = c.get(f"/api/projects/{pid}/pipeline").json()
    assert [s["step"] for s in st["steps"]] == [s["id"] for s in pipe["steps"]]
    assert st["stage"] == pipe["stage"] and st["current"] == pipe["current"]
    word = {"done": "done", "current": "current", "available": "current", "waiting": "locked", "locked": "locked", "no_data": "locked"}
    for s, p in zip(st["steps"], pipe["steps"]):
        assert s["state"] == word[p["state"]] and s["page_state"] == p["state"]
        assert s["detail"] == (p["reason"] or p["detail"])
        assert s["blocked_by"] == p.get("blocked_by") and s["label"] == p["label"]
    assert {a["step"] for a in st["next_actions"]} <= {s["step"] for s in st["steps"]}


@pytest.mark.parametrize("stage", STAGES)
def test_every_action_is_complete_and_honest(at, stage):
    from bti.editor.state_api import NEEDS
    c, pid, st = at(stage)
    for a in st["next_actions"]:
        assert ACTION_KEYS <= set(a), a["id"]
        assert a["method"] in ("GET", "POST", "PUT") and a["path"].startswith("/api/") and "{" not in a["path"], a["path"]
        assert a["ready"] == (not a["needs"]) and set(a["needs"]) <= set(NEEDS), (a["id"], a["needs"])
        assert a["advances"] in (True, False) and (not a["advances"] or a["ready"])
        assert a["gate"] == (a["id"] in GATES)
        assert a["auto_ok"] is (not a["gate"] and a["id"] != "picks.suggest")       # c5cli: by default nothing is automatic: no gate, and never the paid call (tests/state/test_auto.py has the rest)
        assert a["uses_model"] == (a["agent"] is not None)
        if a["agent"]:
            assert set(a["agent"]) == {"id", "label", "usable", "reason"} and a["agent"]["usable"] is True
        if a["cost"]:
            assert a["cost"]["kind"] in ("machine_time", "model", "paid") and a["cost"]["about"]
        if a["long_job"]:
            assert a["follow"].startswith("GET /api/")
        if a["body"] is None and a["method"] != "GET":
            assert a.get("fill") or not a["ready"] or a["id"] in ("export.start",) or a["id"].endswith(".cancel"), a["id"]
        if a.get("fill"):
            assert (a["body"] is None or a["id"] in OPS_ACTIONS) and set(a["fill"]) <= set(a["body_template"]), a["id"]
    assert not any(a["auto_ok"] for a in st["next_actions"] if a["gate"])         # c5cli: the owner turns automatic running on, per project


def test_costs_and_models_are_declared(at):
    c, pid, st = at("storyboard_approved")
    assert action(st, "voice.generate")["cost"] == {"kind": "machine_time", "about": "about 1 hour"}
    assert action(st, "export.start")["cost"] == {"kind": "machine_time", "about": "about 25 minutes"}


def test_export_cost_mentions_incremental_parts_when_parts_exist(at, tmp_path):
    c, pid, _ = at("exported")
    st = c.get("/api/projects/%s/state" % pid).json()
    assert action(st, "export.start")["cost"] == {
        "kind": "machine_time",
        "about": "only changed ~60 s parts (full export: about 25 minutes)",
    }
    d = action(st, "draft.start")
    assert d["cost"] == {"kind": "model", "about": "about 20 minutes"} and d["uses_model"] is True
    assert d["agent"] == {"id": "gem", "label": "Gemini giả", "usable": True, "reason": None}
    assert action(st, "picks.suggest")["cost"]["kind"] == "paid" and action(st, "picks.suggest")["auto_ok"] is False
    assert action(st, "outline.generate")["uses_model"] and action(st, "narration.generate")["uses_model"]
    assert action(st, "storyboard.validate")["cost"] is None and action(st, "picks.search")["agent"] is None


def test_an_agent_that_cannot_run_makes_its_calls_not_ready(at, monkeypatch):
    from bti import agents as AG
    monkeypatch.setattr(AG, "model_availability", lambda model, refresh=False: {"available": False, "reason": "Chưa đăng nhập", "reason_code": "x"})
    c, pid, st = at("picks_approved")
    d = action(st, "draft.start")
    assert d["ready"] is False and "agent_usable" in d["needs"] and d["agent"]["usable"] is False and d["agent"]["reason"] == "Chưa đăng nhập"
    assert d["advances"] is False
    assert action(st, "outline.generate")["ready"] is False and action(st, "picks.search")["ready"] is True


def test_labels_are_the_pages_words(at):
    c, pid, st = at("outline_waiting")
    assert action(st, "outline.approve")["label"] == "Duyệt dàn ý" and action(st, "narration.approve")["label"] == "Duyệt lời dẫn"
    assert action(st, "outline.generate")["label"] == "Lập dàn ý" and action(st, "narration.generate")["label"] == "Viết lời dẫn"


def test_the_example_bodies_hold_the_current_revisions(at):
    c, pid, st = at("outline_waiting")
    assert action(st, "outline.approve")["body"] == {"rev": c.get(f"/api/projects/{pid}/outline").json()["rev"]}
    assert action(st, "outline.generate")["body"] == {} and action(st, "narration.approve")["body"] is None


def _cases():
    return [(stage, aid) for stage in STAGES for aid in EXPECTED[stage]]


def test_the_operations_actions_are_listed_whenever_their_step_is_open(at):
    c, pid, st = at("narration_approved")
    assert "picks.ops" in ids(st) and "storyboard.ops" not in ids(st)          # step 5 is locked: nothing to operate on yet


@pytest.mark.parametrize("stage", STAGES)
def test_every_action_names_a_real_route(at, stage):
    c, pid, st = at(stage)
    for a in st["next_actions"]:
        assert route_ok(c.app, a["method"], a["path"]), (a["id"], a["method"], a["path"])


@pytest.mark.parametrize("stage,aid", _cases())
def test_every_example_body_is_accepted_by_its_route(at, stage, aid, monkeypatch):
    if aid == "storyboard.review":
        from bti.draft import review
        monkeypatch.setattr(review, "start", lambda *args, **kwargs: {"id": "fake-review", "meta": {}})
    c, pid, st = at(stage)
    a = action(st, aid)
    if a["body"] is None and a["method"] != "GET":
        assert a.get("fill") or not a["ready"] or aid == "export.start"        # a body the caller must supply, or none is read
    if aid in OPS_ACTIONS:
        # the body is a dry run of the registry's first example, written for the operations fixture project (tests/state/test_ops_state.py runs
        # it there): on another project the route answers it, or refuses it with a typed error of the operations
        from bti.ops.errors import ERRORS
        r = c.request(a["method"], a["path"], json=a["body"])
        assert r.status_code == 200 or (r.status_code in (404, 409, 422) and r.json()["code"] in ERRORS and r.json()["fix"]), (aid, r.text[:300])
        return
    if a.get("fill"):
        # the caller supplies content: the route refuses the empty template, and says which field (never a 5xx)
        r = c.request(a["method"], a["path"], json=a["body_template"])
        assert r.status_code in (404, 409, 422) and {"code", "fix", "retry", "detail"} <= set(r.json()), (aid, r.status_code, r.text[:300])
        return
    kw = {} if a["body"] is None else {"json": a["body"]}
    r = c.request(a["method"], a["path"], **kw)
    if a["ready"]:
        assert 200 <= r.status_code < 300, (aid, r.status_code, r.text[:300])
    else:
        # refused: with the new error keys (the reason is the one `needs` names)
        assert r.status_code < 300 or (r.status_code in (404, 409, 422) and {"code", "fix", "retry", "detail"} <= set(r.json())), (aid, r.text[:300])


def test_a_running_job_is_listed_and_can_be_cancelled(at):
    from bti.longjob import Part, manager
    c, pid, _ = at("narration_approved")
    gate = threading.Event()
    job = manager.start(kind="voice", pid=pid, project_dir=c.root / pid, parts=[Part(key="p", title="Đọc", run=lambda ctx: gate.wait(20) and None)])
    try:
        st = c.get(f"/api/projects/{pid}/state").json()
        assert [j["id"] for j in st["jobs"]] == [job["id"]]
        j = st["jobs"][0]
        assert {"id", "kind", "state", "progress", "started"} <= set(j) and j["kind"] == "voice" and j["state"] in ("queued", "running", "waiting")
        assert j["path"] == f"/api/longjobs/{job['id']}" and j["started"]
        gen = action(st, "voice.generate")
        assert gen["ready"] is False and "no_running_job" in gen["needs"]
        cancel = action(st, "voice.cancel")
        assert cancel["method"] == "POST" and cancel["path"] == f"/api/longjobs/{job['id']}/cancel" and cancel["ready"] and cancel["body"] is None
        assert cancel["job_id"] == job["id"]
        r = c.post(cancel["path"])
        assert r.status_code == 200
    finally:
        gate.set()
    assert manager.wait(job["id"], timeout=10)["state"] in ("cancelled", "done")
    assert c.get(f"/api/projects/{pid}/state").json()["jobs"] == []


def test_a_running_model_job_blocks_the_script_calls_and_can_be_cancelled(at):
    c, pid, _ = at("new")
    gate = threading.Event()

    def body(job):
        gate.wait(20)
    job = c.app.state.script_jobs.start("outline", pid, "mock", body)
    try:
        st = c.get(f"/api/projects/{pid}/state").json()
        assert [(j["id"], j["kind"]) for j in st["jobs"]] == [(job.id, "outline")]
        assert "no_running_job" in action(st, "outline.generate")["needs"] and "no_running_job" in action(st, "narration.generate")["needs"]
        cancel = action(st, "outline.cancel")
        assert cancel["path"] == f"/api/jobs/{job.id}/cancel"
        assert c.post(cancel["path"]).status_code == 200
    finally:
        gate.set()


def test_a_damaged_storyboard_still_answers_with_its_repair_first(at):
    c, pid, _ = at("drafted")
    d = c.root / pid
    (d / "history").mkdir()
    shutil.copy(d / "storyboard.json", d / "history" / "20261118-100000.json")
    (d / "storyboard.json").write_text("{ not json", encoding="utf-8")
    r = c.get(f"/api/projects/{pid}/state")
    assert r.status_code == 200
    st = r.json()
    first = st["next_actions"][0]
    assert first["id"] == "storyboard.restore" and first["ready"] is True and first["path"] == f"/api/projects/{pid}/storyboard/restore"
    assert [p["code"] for p in st["problems"]] == ["storyboard_corrupt"] and "restore" in st["problems"][0]["fix"]
    edit = next(x for x in st["steps"] if x["step"] == "edit")
    assert edit["problem"] == "storyboard_corrupt" and "Storyboard" in edit["detail"]
    assert not {"storyboard.approve", "storyboard.preview", "export.start"} & set(ids(st))
    assert c.post(first["path"], json=first["body"]).status_code == 200
    again = c.get(f"/api/projects/{pid}/state").json()
    assert again["problems"] == [] and "storyboard.approve" in ids(again)


def test_a_damaged_storyboard_without_a_good_copy_says_so(at):
    c, pid, _ = at("drafted")
    (c.root / pid / "storyboard.json").write_text("[1]", encoding="utf-8")
    st = c.get(f"/api/projects/{pid}/state").json()
    first = st["next_actions"][0]
    assert first["id"] == "storyboard.restore" and first["ready"] is False and first["needs"] == ["history_copy"]
    assert "draft" in st["problems"][0]["fix"]


def test_a_missing_timing_file_names_the_voice_as_the_repair(at):
    c, pid, _ = at("drafted")
    (c.root / pid / "timing.json").unlink()
    st = c.get(f"/api/projects/{pid}/state").json()
    assert st["next_actions"][0]["id"] == "voice.generate" and st["next_actions"][0]["ready"] is True
    assert [p["code"] for p in st["problems"]] == ["timing_unusable"] and "voice/generate" in st["problems"][0]["fix"]
    assert next(s for s in st["steps"] if s["step"] == "voice")["problem"] == "timing_unusable"


def test_a_damaged_project_file_still_answers(at):
    c, pid, _ = at("new")
    (c.root / pid / "project.json").write_text("[]", encoding="utf-8")
    r = c.get(f"/api/projects/{pid}/state")
    assert r.status_code == 200
    st = r.json()
    assert st["project"] == pid and st["next_actions"] == [] and st["problems"][0]["code"] == "project_file_damaged"
    assert all(s["state"] == "locked" for s in st["steps"])


def test_damaged_script_files_are_named_and_gate_the_script_calls(at):
    c, pid, _ = at("outline_waiting")
    (c.root / pid / "script" / "outline.json").write_text("{ no", encoding="utf-8")
    st = c.get(f"/api/projects/{pid}/state").json()
    assert st["problems"][0]["code"] == "document_corrupt" and st["problems"][0]["step"] == "script"
    assert "documents_readable" in action(st, "outline.generate")["needs"]


def test_an_imported_project_has_no_script_steps_but_can_be_edited(client, root, monkeypatch):
    shutil.copytree(DEMO_SRC, root / "imp", ignore=shutil.ignore_patterns("cache", "history"))
    st = client.get("/api/projects/imp/state").json()
    assert st["current"] == "edit" and [s["state"] for s in st["steps"]] == ["locked", "locked", "locked", "locked", "current", "locked"]
    assert [s["page_state"] for s in st["steps"][:4]] == ["no_data"] * 4
    assert not any(i.split(".")[0] in ("outline", "narration", "voice", "picks") for i in ids(st))
    assert "storyboard.approve" in ids(st) and "export.start" not in ids(st)
    rev = client.get("/api/projects/imp").json()["rev"]
    a = action(st, "storyboard.approve")
    assert a["body"] == {"rev": rev} and client.post(a["path"], json=a["body"]).status_code == 200
    after = client.get("/api/projects/imp/state").json()
    assert "storyboard.approve" not in ids(after) and action(after, "export.start")["needs"] == []         # the demo project has its audio mix
    (root / "imp" / "audio" / "narration.m4a").unlink()
    assert action(client.get("/api/projects/imp/state").json(), "export.start")["needs"] == ["audio_mix"]


def test_editing_the_narration_after_the_voice_makes_the_later_calls_wait(at):
    c, pid, _ = at("picks_approved")
    P = f"/api/projects/{pid}"
    n = c.get(P + "/narration").json()
    doc = n["narration"]
    doc["chapters"][0]["beats"][0]["text"] += " Once more."
    assert c.put(P + "/narration", json={"narration": doc, "base_rev": n["rev"]}).status_code == 200
    st = c.get(P + "/state").json()
    assert st["current"] == "script" and action(st, "narration.approve")["advances"] is True
    assert st["next_actions"][0]["id"] == "narration.approve"
    vs = next(s for s in st["steps"] if s["step"] == "voice")
    assert vs["page_state"] == "waiting" and vs["state"] == "locked" and vs["blocked_by"] == "script"
    assert action(st, "voice.generate")["needs"] == ["narration_approved"]
    assert "picks.approve" in ids(st) and "narration_approved" in action(st, "picks.approve")["needs"]
    assert "draft.start" not in ids(st) and "export.start" not in ids(st)         # steps 5 and 6 are locked while the narration is not approved


def test_the_state_of_an_unknown_project_is_the_usual_404(client):
    r = client.get("/api/projects/nope/state")
    assert r.status_code == 404 and r.json()["code"] == "project_not_found"
    assert client.get("/api/projects/Bad_ID/state").status_code == 404


def test_the_existing_project_routes_keep_their_answers(at):
    c, pid, st = at("picks_approved")
    pipe = c.get(f"/api/projects/{pid}/pipeline").json()
    assert set(pipe) == {"project", "title", "painting", "stage", "imported", "has_storyboard", "protected", "artwork_key", "current",
                         "steps", "outputs"}
    assert all(set(s) <= {"id", "n", "label", "state", "reason", "detail", "work", "blocked_by", "has_output"} for s in pipe["steps"])
    assert {p["id"] for p in c.get("/api/projects").json()} == {pid}


def test_the_search_body_uses_the_title_of_the_painting(at):
    c, pid, st = at("narration_approved")
    assert action(st, "picks.search")["body"] == {"query": "The Arnolfini Portrait Jan Van Eyck", "kind": "image"}


def test_the_answer_is_json_serialisable_and_stable(at):
    c, pid, st = at("storyboard_approved")
    again = c.get(f"/api/projects/{pid}/state").json()
    strip = lambda s: json.dumps({k: v for k, v in s.items() if k != "jobs"}, sort_keys=True)
    assert strip(st) == strip(again)


def test_picks_tighten_appears_only_when_main_has_non_tight_regions_and_never_advances(at):
    from bti.picks import doc
    c, pid, st = at("picks_approved")
    # Fresh picks have no non-tight regions: picks.tighten is absent
    assert "picks.tighten" not in ids(st)
    # Add a legacy non-tight region on MAIN: picks.tighten appears with ready=True, advances=False, model cost
    pd = doc.load(c.root / pid)
    pd["assets"]["MAIN"]["regions"]["MIRROR"] = {"x": 50, "y": 60, "rx": 20, "ry": 20, "label": "Gương"}
    with doc.Held(c.root / pid):
        doc.save(c.root / pid, pd)
    st2 = c.get(f"/api/projects/{pid}/state").json()
    act = action(st2, "picks.tighten")
    assert act["ready"] is True and act["advances"] is False and act["long_job"] is True and act["uses_model"] is True
    assert act["cost"]["kind"] == "model" and act["body"]["regions"] is None
    # Once every region is tight: true, picks.tighten disappears again
    pd = doc.load(c.root / pid)
    pd["assets"]["MAIN"]["regions"]["MIRROR"].update({"tight": True, "thing": "convex mirror on wall", "rough": [30, 40, 70, 80]})
    with doc.Held(c.root / pid):
        doc.save(c.root / pid, pd)
    st3 = c.get(f"/api/projects/{pid}/state").json()
    assert "picks.tighten" not in ids(st3)


def test_pipeline_setting_is_revision_checked_and_visible(at):
    c, pid, st = at("new")
    assert st["pipeline"]["value"] == "legacy"
    setting = next(a for a in st["next_actions"] if a["id"] == "pipeline.set")
    rev = st["pipeline"]["rev"]
    assert setting["body_template"]["base_rev"] == rev
    r = c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": rev})
    assert r.status_code == 200, r.text
    assert c.get(f"/api/projects/{pid}/state").json()["pipeline"]["value"] == "visual"
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "legacy", "base_rev": rev}).status_code == 409
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "other", "base_rev": r.json()["rev"]}).status_code == 422


@pytest.mark.parametrize("stage", ["narration_approved", "voiced", "picks_approved", "drafted"])
def test_pipeline_offers_only_its_own_automatic_actions(at, stage):
    c, pid, st = at(stage)
    legacy = set(ids(st))
    assert "visual.plan" not in legacy and "storyboard.compose" not in legacy
    setting = st["pipeline"]
    r = c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": setting["rev"]})
    assert r.status_code == 200
    visual = set(ids(c.get(f"/api/projects/{pid}/state").json()))
    assert "visual.plan" in visual
    assert not visual.intersection({"picks.auto", "picks.retry_missing", "picks.suggest", "picks.tighten", "draft.start", "proposal.apply", "draft.edit"})


def test_visual_gate_waits_for_visual_script(at):
    c, pid, st = at("voiced")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    st = c.get(f"/api/projects/{pid}/state").json()
    gate = next(a for a in st["next_actions"] if a["id"] == "picks.approve")
    assert "visual_script" in gate["needs"]


def test_visual_composer_requires_picks_approval_and_detects_visual_changes(at, monkeypatch):
    from bti.editor import state_api
    monkeypatch.setattr(state_api, "visual_errors", lambda d: [])
    c, pid, st = at("picks_approved")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    project = c.root / pid
    (project / "visual.json").write_text(json.dumps({"moments": [], "wanted": []}), encoding="utf-8")
    shutil.copy(DEMO_SRC / "timing.json", project / "timing.json")
    st = c.get(f"/api/projects/{pid}/state").json()
    compose = next(a for a in st["next_actions"] if a["id"] == "storyboard.compose")
    assert compose["ready"] and compose["advances"]


def test_picks_approval_invokes_recompose_for_visual_project(at, monkeypatch):
    from bti.compose import api as compose_api
    from bti.editor import state_api
    from state_helpers import make_picks
    c, pid, st = at("voiced")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    calls = []
    monkeypatch.setattr(compose_api, "compose_if_approved", lambda p: calls.append(p))
    monkeypatch.setattr(state_api, "visual_errors", lambda p: [])
    (c.root / pid / "visual.json").write_text('{"wanted": []}', encoding="utf-8")
    shutil.copy(DEMO_SRC / "timing.json", c.root / pid / "timing.json")
    make_picks(c, pid)
    assert calls == [c.root / pid]


def test_visual_review_calls_visual_worker(at, monkeypatch):
    import sys
    import types
    c, pid, st = at("drafted")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    calls = []
    module = types.ModuleType("bti.visual.review")
    module.start = lambda pid, d, **kw: (calls.append((pid, d)) or {"id": "fake", "meta": {}})
    monkeypatch.setitem(sys.modules, "bti.visual.review", module)
    r = c.post(f"/api/projects/{pid}/draft/review", json={"actor": "agent:auto"})
    assert r.status_code == 200, r.text
    assert calls == [(pid, c.root / pid)]


@pytest.mark.parametrize("stage", STAGES)
def test_the_exact_visual_action_ids_at_each_stage(at, stage, monkeypatch):
    from bti.editor import state_api
    monkeypatch.setattr(state_api, "visual_errors", lambda d: [])
    monkeypatch.setattr(state_api, "visual_composition_needs", lambda d: [])
    c, pid, st = at(stage)
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    if stage in {"picks_approved", "proposal_waiting", "drafted", "storyboard_approved", "exported"}:
        (c.root / pid / "visual.json").write_text('{"wanted": [], "moments": []}', encoding="utf-8")
    rows = ids(c.get(f"/api/projects/{pid}/state").json())
    picks = ["picks.search", "picks.import", "picks.import_book_image", "picks.import_clip", "picks.put"]
    edit = ["storyboard.validate", "storyboard.preview", "storyboard.put", "storyboard.ops", "identity.set"]
    late = ["pipeline.set", *SCRIPT_REDO, "title.generate", "title.set", "voice.generate", *picks, "visual.plan", "picks.ops", *edit, "music.set"]
    expected = {
        "new": EXPECTED["new"],
        "outline_waiting": EXPECTED["outline_waiting"],
        "narration_approved": ["title.generate", "voice.generate", "pipeline.set", *SCRIPT_REDO, "title.set", *picks, "picks.ops", "visual.plan", "picks.approve"],
        "voiced": ["title.generate", "pipeline.set", *SCRIPT_REDO, "title.set", "voice.generate", *picks, "picks.ops", "visual.plan", "picks.approve"],
        "picks_approved": ["title.generate", "pipeline.set", *SCRIPT_REDO, "title.set", "voice.generate", *picks, "picks.ops", "visual.plan", "storyboard.compose"],
        "proposal_waiting": ["title.generate", "storyboard.compose", "pipeline.set", *SCRIPT_REDO, "title.set", "voice.generate", *picks, "visual.plan", "picks.ops"],
        "drafted": ["storyboard.compose", *late, "scorecard.make", "storyboard.review", "storyboard.approve", "music.auto"],
        "storyboard_approved": ["storyboard.compose", "export.start", "scorecard.make", *late, "music.auto"],
        "exported": ["storyboard.compose", "scorecard.make", *late, "export.start", "music.auto"],
    }
    if stage == "drafted":
        import importlib.util
        if importlib.util.find_spec("bti.visual.review") is not None:
            expected[stage].remove("storyboard.review")
            expected[stage].insert(1, "storyboard.review")
    assert rows == expected[stage]


def test_auto_picks_gate_leaves_compose_as_the_next_run_action(at, monkeypatch):
    from bti import auto
    from bti.compose import api as compose_api
    from bti.editor import picks_api, state_api
    c, pid, st = at("picks_approved")
    p = c.root / pid
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    (p / "visual.json").write_text('{"wanted": [], "moments": []}', encoding="utf-8")
    shutil.copy(DEMO_SRC / "timing.json", p / "timing.json")
    settings = auto.view(p)
    auto.update(p, {"enabled": True}, settings["rev"])
    calls = []
    monkeypatch.setattr(compose_api, "compose_if_approved", lambda d: calls.append(d))
    monkeypatch.setattr(state_api, "visual_errors", lambda d: [])
    monkeypatch.setattr(picks_api.service, "approve", lambda *args: None)
    r = c.post(f"/api/projects/{pid}/picks/approve", json={"rev": "fake", "actor": "agent:auto"})
    assert r.status_code == 200, r.text
    assert calls == []


def test_visual_review_is_not_ready_without_the_visual_worker(at):
    import importlib.util
    if importlib.util.find_spec("bti.visual.review") is not None:
        pytest.skip("the visual review worker is already integrated")
    c, pid, st = at("drafted")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    action = next(a for a in c.get(f"/api/projects/{pid}/state").json()["next_actions"] if a["id"] == "storyboard.review")
    assert not action["ready"] and "visual_review_available" in action["needs"]


def test_visual_scorecard_does_not_advance_before_review(at, monkeypatch):
    from bti.editor import state_api
    monkeypatch.setattr(state_api, "visual_composition_needs", lambda d: [])
    c, pid, st = at("drafted")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    actions = c.get(f"/api/projects/{pid}/state").json()["next_actions"]
    score = next(a for a in actions if a["id"] == "scorecard.make")
    assert score["ready"] and not score["advances"]


def test_visual_edit_builder_waits_for_timing_and_edit_step(tmp_path):
    from types import SimpleNamespace
    from bti.editor.state_api import b_visual_edit
    (tmp_path / "visual.json").write_text('{"wanted": [], "moments": []}', encoding="utf-8")
    c = SimpleNamespace(pipeline={"value": "visual"}, d=tmp_path, has_timing=False,
                        open=lambda step: step == "edit", box_busy=lambda: False,
                        agent=lambda role: {"usable": True}, actor=lambda role: "agent:fake")
    row = b_visual_edit(c)
    assert row is not None and "timing" in row["needs"]
    c.open = lambda step: False
    assert b_visual_edit(c) is None


def test_visual_picks_gate_refuses_an_invalid_visual_script(at):
    c, pid, st = at("voiced")
    p = c.root / pid
    shutil.copy(DEMO_SRC / "timing.json", p / "timing.json")
    (p / "visual.json").write_text('{}', encoding="utf-8")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    gate = next(a for a in c.get(f"/api/projects/{pid}/state").json()["next_actions"] if a["id"] == "picks.approve")
    assert not gate["ready"] and "visual_script_valid" in gate["needs"]
    response = c.post(f"/api/projects/{pid}/picks/approve", json={"rev": None})
    assert response.status_code == 422 and response.json()["code"] == "validation_failed"
    assert c.get(f"/api/projects/{pid}/visual").json()["issues"]


def test_visual_compose_is_not_ready_for_invalid_script(at):
    c, pid, st = at("picks_approved")
    p = c.root / pid
    shutil.copy(DEMO_SRC / "timing.json", p / "timing.json")
    (p / "visual.json").write_text('{}', encoding="utf-8")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    action = next(a for a in c.get(f"/api/projects/{pid}/state").json()["next_actions"] if a["id"] == "storyboard.compose")
    assert not action["ready"] and "visual_script_valid" in action["needs"]


def test_visual_export_rejects_old_storyboard(at, monkeypatch):
    from bti.editor import state_api
    c, pid, st = at("storyboard_approved")
    p = c.root / pid
    (p / "visual.json").write_text('{}', encoding="utf-8")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    monkeypatch.setattr(state_api, "visual_errors", lambda d: [])
    action = next(a for a in c.get(f"/api/projects/{pid}/state").json()["next_actions"] if a["id"] == "export.start")
    assert not action["ready"] and "visual_composed" in action["needs"]
    response = c.post(f"/api/projects/{pid}/export/start")
    assert response.status_code == 422 and response.json()["code"] == "validation_failed"


def test_visual_review_and_scorecard_wait_for_current_composition(at, monkeypatch):
    from bti.editor import state_api
    c, pid, st = at("drafted")
    p = c.root / pid
    (p / "visual.json").write_text('{"wanted": [], "moments": []}', encoding="utf-8")
    assert c.put(f"/api/projects/{pid}/pipeline-setting", json={"pipeline": "visual", "base_rev": st["pipeline"]["rev"]}).status_code == 200
    monkeypatch.setattr(state_api, "visual_errors", lambda d: [])
    actions = {a["id"]: a for a in c.get(f"/api/projects/{pid}/state").json()["next_actions"]}
    for action in ("storyboard.review", "scorecard.make"):
        assert not actions[action]["ready"] and "visual_composed" in actions[action]["needs"]
