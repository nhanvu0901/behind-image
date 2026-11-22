"""Viewer review rejects incomplete model answers and limits repair rounds."""
import pytest

from bti.draft.review import ReviewError, review_and_repair


def test_repairs_only_flagged_shots_then_reports_remaining():
    answers = iter([
        {"shots": [{"id": "a", "problems": [{"code": "picture_mismatch", "detail": "Person is cropped."}]}, {"id": "b", "problems": []}]},
        {"shots": [{"id": "a", "problems": [{"code": "picture_mismatch", "detail": "Person remains cropped."}]}, {"id": "b", "problems": []}]},
        {"shots": [{"id": "a", "problems": [{"code": "picture_mismatch", "detail": "Still cropped."}]}, {"id": "b", "problems": []}]},
    ])
    edits = []
    result = review_and_repair(lambda: ["a", "b"], lambda ids: next(answers), lambda ids, instruction: edits.append((ids, instruction)))
    assert len(edits) == 2
    assert all(ids == ["a"] for ids, _ in edits)
    assert "Person is cropped." in edits[0][1]
    assert result["warnings"][0]["code"] == "review_picture_mismatch"
    assert result["warnings"][0]["shot"] == "a"


def test_clean_review_never_edits():
    result = review_and_repair(lambda: ["a"], lambda ids: {"shots": [{"id": "a", "problems": []}]}, lambda *_: pytest.fail("unexpected edit"))
    assert result["warnings"] == []
    assert result["rounds"] == 0


def test_incomplete_review_is_not_a_clean_review():
    with pytest.raises(ReviewError):
        review_and_repair(lambda: ["a", "b"], lambda ids: {"shots": [{"id": "a", "problems": []}]}, lambda *_: None)


def test_prepare_sheets_uses_named_moment_and_midpoint(tmp_path):
    import numpy as np
    import cv2
    from bti.draft.review import prepare_sheets

    class Bundle:
        def spec(self, technique):
            return {"params": [{"name": "text", "type": "text"}]}

    class Project:
        bundle = Bundle()
        def resolve(self):
            return {"shots": [{"id": "a", "_t0": 0.0, "_t1": 4.0, "technique": "x", "params": {"text": "visible"}},
                              {"id": "b", "_t0": 4.0, "_t1": 6.0, "technique": "x", "params": {}}]}
        def timing(self):
            return {"words": [{"w": "A", "s": 0.1}, {"w": "woman", "s": 1.0}, {"w": "appears", "s": 2.0}, {"w": "next", "s": 4.5}]}
        def frame_at(self, t, width):
            calls.append((t, width))
            return np.zeros((360, width, 3), dtype=np.uint8)

    calls = []
    rows, sheets = prepare_sheets(Project(), {"names": [{"name": "woman"}]}, tmp_path)
    assert calls == [(1.0, 640), (5.0, 640)]
    assert rows[0]["words"] == "A woman appears"
    assert rows[0]["text"] == ["visible"]
    assert rows[0]["frames"][0]["time"] == 1.0
    assert rows[1]["frames"][0]["time"] == 5.0
    assert len(sheets) == 1 and cv2.imread(str(sheets[0])) is not None


def test_model_review_supplies_sheets_and_requires_complete_json(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.draft.review import run_model_review

    (tmp_path / "sheet-001.jpg").write_bytes(b"fake")
    rows = [{"id": "a", "words": "woman", "text": [], "frames": [{"time": 1.0, "sheet": "sheet-001.jpg"}]}]
    class Provider:
        def run(self, workspace, **kwargs):
            assert "sheet-001.jpg" in (workspace / "shots.json").read_text(encoding="utf-8")
            assert "picture_mismatch" in (workspace / "TASK.md").read_text(encoding="utf-8")
            (workspace / "out" / "review.json").write_text(json.dumps({"shots": [{"id": "a", "problems": []}]}), encoding="utf-8")
            return SimpleNamespace(status="ok")
    assert run_model_review(tmp_path, rows, model="test", provider=Provider())["shots"][0]["id"] == "a"


def test_scoped_repair_uses_request_box_parts(tmp_path):
    from types import SimpleNamespace
    from bti.draft.review import scoped_edit
    calls = []
    def make_parts(project, **kwargs):
        calls.append(kwargs)
        return [SimpleNamespace(run=lambda ctx: {"status": "applied"})]
    ctx = SimpleNamespace(cancelled=lambda: False)
    scoped_edit(tmp_path, ["s1"], "Correct the picture", model="agent-model", ctx=ctx, make_parts=make_parts)
    assert calls[0]["edit_scope"] == {"shots": ["s1"]}
    assert calls[0]["instruction"] == "Correct the picture"
    assert calls[0]["model"] == "agent-model"


def test_repair_splits_long_instructions_without_changing_shot_scope():
    ids = ["shot-%02d" % n for n in range(12)]
    answers = iter([{"shots": [{"id": sid, "problems": [{"code": "text_wrong", "detail": "x" * 350}]} for sid in ids]},
                    {"shots": [{"id": sid, "problems": []} for sid in ids]}])
    edits = []
    review_and_repair(lambda: ids, lambda _: next(answers), lambda shots, instruction: edits.append((shots, instruction)))
    assert len(edits) > 1
    assert all(len(instruction) <= 2000 for _, instruction in edits)
    assert [sid for shots, _ in edits for sid in shots] == ids


def test_review_job_saves_final_report_for_current_revision(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from bti.draft import review
    from bti.editor.common import compute_rev
    storyboard = {"shots": [{"id": "s1"}]}
    (tmp_path / "storyboard.json").write_text(json.dumps(storyboard), encoding="utf-8")
    calls = []
    def fake_round(project_dir, directory, model, ctx):
        calls.append("review")
        problems = [{"code": "picture_mismatch", "detail": "The person is cropped."}] if len(calls) == 1 else []
        return [{"id": "s1"}], {"shots": [{"id": "s1", "problems": problems}]}
    def fake_edit(project_dir, shots, instruction, *, model, ctx):
        calls.append((shots, instruction))
    ctx = SimpleNamespace(cancelled=lambda: False, progress=lambda *_: None)
    result = review.run_job(tmp_path, "fake-model", ctx, review_round=fake_round, edit=fake_edit)
    assert calls[1][0] == ["s1"]
    assert result["warnings"] == []
    assert review.load_report(tmp_path, compute_rev(storyboard))["rounds"] == 1
    assert review.load_report(tmp_path, "stale") is None


def test_review_state_action_precedes_storyboard_approval(tmp_path, monkeypatch):
    from bti.editor import state_api
    c = state_api.Ctx(tmp_path, "p", {"steps": [{"id": "edit", "state": "current"}]}, [])
    c.sb_exists, c.sb_rev = True, "revision"
    c.draft_ready = {"voice": True, "picks": True}
    monkeypatch.setattr(c, "agent", lambda role: {"usable": True})
    monkeypatch.setattr(state_api, "_model_needs", lambda *_: [])
    actions = state_api.build_actions(c)
    selected = [x for x in actions if x["id"] in ("storyboard.review", "storyboard.approve")]
    assert selected[0]["id"] == "storyboard.review"
    assert selected[0]["advances"] and selected[0]["long_job"]
    assert selected[0]["cost"]["kind"] == "model"


def test_warnings_follow_the_reviewed_revision(tmp_path):
    from bti.draft.review import save_report, issues_for
    result = {"revision": "a" * 64, "rounds": 2, "warnings": [{"level": "warn", "code": "review_text_wrong", "shot": "s1", "message": "Wrong caption."}], "history": []}
    save_report(tmp_path, result)
    issues = issues_for(tmp_path, "a" * 64)
    assert issues[0]["code"] == "review_text_wrong"
    assert issues[0]["args"]["shot"] == "s1"
    assert issues_for(tmp_path, "b" * 64) == []


def test_review_fails_closed_when_storyboard_changes(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.draft.review import run_job, ReviewError
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps({"shots": [{"id": "s1"}]}), encoding="utf-8")
    def review_round(project_dir, directory, model, ctx):
        path.write_text(json.dumps({"shots": [{"id": "s2"}]}), encoding="utf-8")
        return [{"id": "s1"}], {"shots": [{"id": "s1", "problems": []}]}
    ctx = SimpleNamespace(cancelled=lambda: False, progress=lambda *_: None)
    with pytest.raises(ReviewError, match="changed"):
        run_job(tmp_path, "mock", ctx, review_round=review_round)


def test_review_honours_cancellation_before_model(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.draft.review import run_job
    from bti.longjob import Cancelled
    (tmp_path / "storyboard.json").write_text(json.dumps({"shots": [{"id": "s1"}]}), encoding="utf-8")
    ctx = SimpleNamespace(cancelled=lambda: True, progress=lambda *_: None)
    with pytest.raises(Cancelled):
        run_job(tmp_path, "mock", ctx, review_round=lambda *_: pytest.fail("model called"))


def test_auto_run_does_not_skip_unavailable_review():
    from bti.auto_run.loop import Run
    run = object.__new__(Run)
    run.until = None
    run._nothing_to_do = lambda st, acts: {"reason": "nothing_to_do", "action": acts[0]["id"]}
    state = {"steps": [], "auto": {"enabled": True}, "jobs": [], "next_actions": [
        {"id": "storyboard.review", "ready": False, "advances": False, "needs": ["agent_usable"]},
        {"id": "storyboard.approve", "ready": True, "advances": True}]}
    stop, action = run._decide(state)
    assert action is None and stop["action"] == "storyboard.review"


def test_review_route_starts_job_with_auto_actor(proj, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from bti.editor.draft_api import router
    from bti.draft import review
    calls = []
    def fake_start(pid, project_dir, **kw):
        calls.append((pid, kw))
        return {"id": "j1", "meta": {"model": "mock", "agent": {"id": "mock"}}}
    monkeypatch.setattr(review, "start", fake_start)
    app = FastAPI()
    app.state.projects_root = proj.parent
    app.include_router(router)
    response = TestClient(app).post("/api/projects/%s/draft/review" % proj.name, json={"actor": "agent:auto"})
    assert response.status_code == 200 and response.json()["job_id"] == "j1"
    assert calls[0][1]["run_ok"] is True


def test_review_job_splits_model_rounds_into_longjob_parts(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.draft.review import make_job_parts, load_report
    from bti.editor.common import compute_rev
    sb = {"shots": [{"id": "s1"}]}
    (tmp_path / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    observed = []
    def review_round(project, directory, model, ctx):
        count = sum(item == "review" for item in observed)
        observed.append("review")
        problems = [{"code": "text_wrong", "detail": "Wrong caption."}] if count == 0 else []
        return [{"id": "s1"}], {"shots": [{"id": "s1", "problems": problems}]}
    def edit(project, shots, instruction, **kwargs):
        observed.append("edit")
    ctx = SimpleNamespace(cancelled=lambda: False, progress=lambda *_: None)
    parts = make_job_parts(tmp_path, "mock", review_round=review_round, edit=edit)
    assert len(parts) >= 5
    for part in parts:
        part.run(ctx)
    assert observed == ["review", "edit", "review"]
    assert load_report(tmp_path, compute_rev(sb))["rounds"] == 1


def test_report_is_stale_if_timed_words_change(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.draft import review
    from bti.editor.common import compute_rev
    sb = {"shots": [{"id": "s1"}]}
    (tmp_path / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    timing = tmp_path / "timing.json"
    timing.write_text('{"words": []}', encoding="utf-8")
    ctx = SimpleNamespace(cancelled=lambda: False, progress=lambda *_: None)
    fake = lambda *_: ([{"id": "s1"}], {"shots": [{"id": "s1", "problems": []}]})
    review.run_job(tmp_path, "mock", ctx, review_round=fake)
    assert review.load_report(tmp_path, compute_rev(sb)) is not None
    timing.write_text('{"words": ["changed"]}', encoding="utf-8")
    assert review.load_report(tmp_path, compute_rev(sb)) is None


def test_start_review_uses_one_draft_job_and_project_agent(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bti.draft import review, run as draft_run
    (tmp_path / "storyboard.json").write_text('{}', encoding="utf-8")
    checked, started = [], []
    monkeypatch.setattr(draft_run, "refuse_while_agent_busy", lambda pid, manager, run_ok=False: checked.append((pid, run_ok)))
    monkeypatch.setattr(draft_run, "readiness", lambda d: {"ok": True})
    monkeypatch.setattr(draft_run, "_resolve", lambda d, role, model: SimpleNamespace(model="chosen", public=lambda: {"id": "selected"}))
    monkeypatch.setattr(draft_run, "_check_agent_installed", lambda model: None)
    class Manager:
        def start(self, **kwargs):
            started.append(kwargs)
            return {"id": "job"}
    assert review.start("p", tmp_path, manager=Manager(), run_ok=True)["id"] == "job"
    assert checked == [("p", True)]
    assert started[0]["kind"] == "draft" and started[0]["meta"]["model"] == "chosen"


def test_full_draft_edit_appends_review_to_same_agent_job(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bti.draft import run, review
    inp = SimpleNamespace(current={"shots": [{"id": "s1"}]})
    monkeypatch.setattr(run, "refuse_while_agent_busy", lambda *a, **kw: None)
    monkeypatch.setattr(run, "load_inputs", lambda *a, **kw: inp)
    monkeypatch.setattr(run, "resolve_edit_scope", lambda *a: ({"s1"}, ["c1"], "cả video"))
    monkeypatch.setattr(run, "_resolve", lambda *a: SimpleNamespace(model="chosen", public=lambda: {}))
    monkeypatch.setattr(run, "_check_agent_installed", lambda *a: None)
    monkeypatch.setattr(run, "make_edit_parts", lambda *a, **kw: ["edit-part"])
    monkeypatch.setattr(review, "after_full_edit_parts", lambda *a, **kw: ["review-part"])
    captured = []
    class Manager:
        def start(self, **kwargs):
            captured.append(kwargs)
            return {"id": "j1"}
    run.start("p", tmp_path, instruction="Change the video", edit_scope={"all": True}, manager=Manager())
    assert captured[0]["kind"] == "draft"
    assert captured[0]["parts"] == ["edit-part", "review-part"]


def test_model_review_rejects_symlink_output(tmp_path):
    from types import SimpleNamespace
    from bti.draft.review import ReviewError, run_model_review
    outside = tmp_path / "unrelated.json"
    outside.write_text('{"shots": []}', encoding="utf-8")
    class Provider:
        def run(self, workspace, **kwargs):
            try:
                (workspace / "out" / "review.json").symlink_to(outside)
            except OSError:
                pytest.skip("symlinks unavailable")
            return SimpleNamespace(status="ok")
    with pytest.raises(ReviewError):
        run_model_review(tmp_path, [], model="fake", provider=Provider())


def test_full_edit_review_reports_agent_unavailable_by_its_code(tmp_path, monkeypatch):
    from bti.draft import review, run
    from bti.draft.inputs import DraftError
    from bti.draft.thread import append_turn
    from bti.longjob import Part, PartError
    append_turn(tmp_path, {"id": "t1", "status": "applied", "doc": "storyboard"})
    monkeypatch.setattr(review, "make_job_parts", lambda *a: [Part(key="r", title="Review", run=lambda ctx: None)])
    def missing(model):
        raise DraftError("agy_missing", "not installed")
    monkeypatch.setattr(run, "_check_agent_installed", missing)
    part = review.after_full_edit_parts(tmp_path, "mock", "t1")[0]
    with pytest.raises(PartError) as error:
        part.run(None)
    assert error.value.code == "agy_missing"


def test_review_action_waits_for_picks_and_voice(tmp_path, monkeypatch):
    from bti.editor import state_api
    c = state_api.Ctx(tmp_path, "p", {"steps": [{"id": "edit", "state": "current"}]}, [])
    c.sb_exists, c.sb_rev = True, "a" * 64
    monkeypatch.setattr(state_api, "_model_needs", lambda *_: [])
    action = state_api.b_storyboard_review(c)
    assert set(action["needs"]) == {"voice_done", "picks_approved"}


def test_review_job_part_cancels_before_calling_provider(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.draft.review import make_job_parts
    from bti.longjob import Cancelled
    (tmp_path / "storyboard.json").write_text(json.dumps({"shots": [{"id": "s1"}]}), encoding="utf-8")
    parts = make_job_parts(tmp_path, "mock", review_round=lambda *_: pytest.fail("provider called"))
    with pytest.raises(Cancelled):
        parts[0].run(SimpleNamespace(cancelled=lambda: True))


def test_review_preserves_provider_rate_limit(tmp_path):
    from types import SimpleNamespace
    from bti.draft.inputs import DraftError
    from bti.draft.review import run_model_review
    class Provider:
        def run(self, workspace, **kwargs):
            return SimpleNamespace(status="error", error_code="agy_rate_limit", error_message="quota", retry_after_seconds=60)
    with pytest.raises(DraftError) as error:
        run_model_review(tmp_path, [], model="fake", provider=Provider())
    assert error.value.code == "agy_rate_limit"


def test_full_edit_review_runs_only_after_applied_turn(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bti.draft import review, run
    from bti.draft.thread import append_turn, update_turn
    from bti.longjob import Part
    called = []
    append_turn(tmp_path, {"id": "t1", "status": "applied", "doc": "storyboard"})
    monkeypatch.setattr(review, "make_job_parts", lambda *a: [Part(key="r", title="Review", run=lambda ctx: called.append("review"))])
    monkeypatch.setattr(run, "_check_agent_installed", lambda model: None)
    part = review.after_full_edit_parts(tmp_path, "mock", "t1")[0]
    ctx = SimpleNamespace()
    assert not part.is_done(ctx)
    part.run(ctx)
    assert called == ["review"]
    update_turn(tmp_path, "t1", status="no_change")
    assert part.is_done(ctx)


def test_review_job_keeps_provider_rate_limit_and_retry_time(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.draft.inputs import DraftError
    from bti.draft.review import make_job_parts
    from bti.longjob import PartError
    (tmp_path / "storyboard.json").write_text(json.dumps({"shots": [{"id": "s1"}]}), encoding="utf-8")
    def rate_limited(*args):
        raise DraftError("agy_rate_limit", "quota", retry_after_seconds=60)
    ctx = SimpleNamespace(cancelled=lambda: False, meta={})
    with pytest.raises(PartError) as error:
        make_job_parts(tmp_path, "fake", review_round=rate_limited)[0].run(ctx)
    assert error.value.code == "agy_rate_limit"
    assert ctx.meta["retry_after_seconds"] == 60
