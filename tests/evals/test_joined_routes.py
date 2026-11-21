"""The bench against the JOINED app (worker join2, round two): the drivers of the step-5 request box (`draft.edit`, answered through typed operations), of the step-4
request box (`picks.edit`) and of the pictures agent (`picks.auto`) work through the real routes, with the fake agents, and their three cases each run and are scored
instead of being skipped. The model of the boxes is the mock provider, answering the way a careful agent would for each request of the nine cases (the briefings'
own data: lines, shots, pictures); the agent in a work folder is the fake runner of tests/picks; the picture sources are fakes. No model, no program, no network.

The cases need what a sample project of the repository does not have yet: the sample `arnolfini-from-books` has an outline and no narration (`script/narration.json`), so on the
real sample the cases of `edit_picks` and `picks_agent` are skipped with the sentence of `samples.copy_project`, said below; these tests build samples that have them."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO / "tests" / "ops", REPO / "tests" / "draft", REPO / "tests" / "picks", REPO / "tests" / "e2e" / "stages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import box_mock  # noqa: E402  (the canned answers of the two boxes, built from the data of the briefing)
from auto_helpers import FakeAgent, fake_book_thumb, fake_thumb, install_agent, install_sources, make_auto_project  # noqa: E402
from cli_helpers import AppTransport  # noqa: E402
from ops_helpers import make_project as make_ops_project  # noqa: E402

from bti.evals import runner  # noqa: E402
from bti.picks.auto import search as asearch  # noqa: E402
from bti.script.providers import mock  # noqa: E402

ADD_OVERLAY = {"op": "add_overlay", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 220, "ry": 220}, "start": {"w": 70}, "dur": 4, "ref": "ring"}


# ------------------------------------------------------------------------------------------------------------------------ the agent of the boxes
def _json(status: str, summary: str = "", reason: str = "", ops: list | None = None) -> str:
    return json.dumps({"status": status, "summary": summary, "reason": reason, "ops": ops or []}, ensure_ascii=False)


def careful_agent(user: str) -> str | None:
    """What a careful agent answers to each request of the nine cases; None for any other prompt (the mock answers it)."""
    ask = box_mock._request(user)
    if box_mock.STORYBOARD_HEADING in user:
        if "Mona Lisa" in ask:
            return _json("cannot", reason="Dự án chưa có bức tranh này. Hãy nhập hình ở bước Chọn hình trước.")
        if "vòng sáng" in ask:
            shot = next(s for s in box_mock._section(user, "### The shots in scope", "### The shot before") if not s.get("locked"))
            return _json("applied", "Đã thêm một vòng sáng quanh chiếc gương.", ops=[{**ADD_OVERLAY, "shot": shot["id"]}])
        return box_mock.storyboard_answer(user)
    if box_mock.PICTURES_HEADING in user:
        if "tiếng Nhật" in ask:
            return _json("cannot", reason="Việc dịch lời dẫn không phải việc của bước Chọn hình.")
        if "bỏ qua" in ask:
            line = box_mock._section(user, "### The lines in scope", "### The line before")[0]
            return _json("applied", "Dòng này giờ dùng lại tranh chính.", ops=[{"op": "skip_beat", "beat": line["id"], "reason": "Không cần hình riêng."}])
        return box_mock.pictures_answer(user)
    return None


# ------------------------------------------------------------------------------------------------------------------------ the fixtures
@pytest.fixture()
def joined(tmp_path, monkeypatch):
    """The joined app (real engine, the routes of the boxes and of the pictures agent), a projects folder, a samples folder with a project that has a storyboard (the
    fixture project of tests/ops, as `arnolfini`) and one that has an approved narration and a main painting (`arnolfini-from-books`), and the fake agents."""
    import bti.longjob.config as lcfg
    from bti.editor.app import create_app
    from bti.engine import api as engine_api
    from bti.longjob import manager
    cfg = tmp_path / "server.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(lcfg, "CONFIG_PATH", cfg)
    root, samples = tmp_path / "projects", tmp_path / "samples"
    root.mkdir()
    samples.mkdir()
    make_ops_project(samples, "arnolfini")
    make_auto_project(samples, "arnolfini-from-books")
    (tmp_path / "work").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "work"))
    install_sources(monkeypatch)
    monkeypatch.setattr(asearch, "default_fetch_thumb", fake_thumb)
    monkeypatch.setattr(asearch, "default_book_thumb", fake_book_thumb)
    fake = install_agent(monkeypatch, FakeAgent())
    real = mock.complete

    def complete(spec, system, user, **kw):
        canned = careful_agent(user)
        if canned is None:
            return real(spec, system, user, **kw)
        mock.CALLS.append({"model": spec.get("id"), "user_len": len(user), "retry": False, "user": user})
        return canned
    monkeypatch.setattr(mock, "complete", complete)
    manager.configure(projects_root=root)
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()

    class J:
        pass
    j = J()
    j.client, j.root, j.samples, j.fake, j.transport = client, root, samples, fake, AppTransport(client)

    def run(step, names=None, repeat=1, **kw):
        return runner.run(step=step, agent_id="gem", repeat=repeat, transport=j.transport, case_names=names, samples_root=samples, projects_root=root,
                          app_url="http://test", poll=0.01, **kw)
    j.run = run
    yield j
    client.__exit__(None, None, None)
    with manager._lock:
        for x in list(manager._jobs.values()):
            x.cancel.set()
        manager._jobs.clear()


def scored(rec, step):
    """{case name: its one repeat}, after checking that every case ran (none skipped) and was scored (every criterion has a value, none says nothing could be checked)."""
    reps = {c["name"]: c["repeats"][0] for c in rec["cases"]}
    assert len(reps) == 3, sorted(reps)
    for name, rep in reps.items():
        assert rep["skipped"] is None, "%s was skipped: %s" % (name, rep["skipped"])
        assert rep["error"] is None, "%s: %s" % (name, rep["error"])
        assert rep["criteria"] and all("nothing to check" not in c["detail"] for c in rep["criteria"]), (name, rep["criteria"])
        assert rep["cleanup"] is None and rep["jobs"], name
    return reps


def passing(rep):
    return {c["id"] for c in rep["criteria"] if c["passed"]}


# ------------------------------------------------------------------------------------------------------------------------ the three steps
def test_the_step_5_box_is_driven_through_typed_operations_and_its_three_cases_are_scored(joined):
    rec, outputs = joined.run("edit_storyboard")
    reps = scored(rec, "edit_storyboard")
    assert set(reps) == {"edit-add-a-ring-of-light", "edit-asks-for-a-picture-the-project-lacks", "edit-zoom-slower"}
    assert {"cannot", "scope"} <= passing(reps["edit-asks-for-a-picture-the-project-lacks"])
    assert {"scope", "changed", "slower"} <= passing(reps["edit-zoom-slower"])
    assert {"scope", "overlays"} <= passing(reps["edit-add-a-ring-of-light"])
    cannot = outputs["edit-asks-for-a-picture-the-project-lacks-1"]["answer"]
    assert cannot["code"] == "no_change" and "Hãy nhập hình" in cannot["reason"]                           # the turn of a request the box could not do: no_change, with the model's sentence
    ring = outputs["edit-add-a-ring-of-light-1"]
    assert ring["answer"]["code"] == "applied" and ring["before"]["shots"] != ring["after"]["shots"]
    zoom = outputs["edit-zoom-slower-1"]
    assert zoom["scope"] == {"shots": ["s0004", "s0005"]} and zoom["answer"]["code"] == "applied"
    posts = [b for m, p, b in joined.transport.log if m == "POST" and p.endswith("/draft/edit")]
    assert len(posts) == 3 and all(b["mode"] == "auto" and b["base_rev"] and b["instruction"] for b in posts)
    assert rec["sample_unchanged"] is True and joined.root.exists() and [d.name for d in joined.root.iterdir()] == []        # the copies were removed again, through the app


def test_the_step_4_box_is_driven_through_its_action_and_its_three_cases_are_scored(joined):
    rec, outputs = joined.run("edit_picks")
    reps = scored(rec, "edit_picks")
    assert set(reps) == {"edit-picks-asks-for-something-impossible", "edit-picks-reuse-the-main-painting", "edit-picks-skip-a-line"}
    assert passing(reps["edit-picks-asks-for-something-impossible"]) == {"cannot", "scope"}
    assert passing(reps["edit-picks-reuse-the-main-painting"]) == {"scope", "changed", "no-errors"}
    assert passing(reps["edit-picks-skip-a-line"]) == {"scope", "changed", "no-errors"}
    assert reps["edit-picks-asks-for-something-impossible"]["passed"] is True and reps["edit-picks-skip-a-line"]["passed"] is True
    cannot = outputs["edit-picks-asks-for-something-impossible-1"]["answer"]
    assert cannot["code"] == "no_change" and cannot["reason"] and cannot["state"] == "done"
    skip = outputs["edit-picks-skip-a-line-1"]
    assert skip["after"]["beats"]["b0006"]["status"] == "skip" and skip["answer"]["code"] == "applied"
    assert [b for m, p, b in joined.transport.log if m == "POST" and p.endswith("/picks/edit")][0]["base_rev"]      # the revision comes from the action's template
    assert rec["sample_unchanged"] is True and [d.name for d in joined.root.iterdir()] == []


def test_the_pictures_agent_is_driven_through_its_action_and_its_three_cases_are_scored(joined):
    rec, outputs = joined.run("picks_agent")
    reps = scored(rec, "picks_agent")
    assert set(reps) == {"picks-agent-credits-every-picture", "picks-agent-decides-every-line", "picks-agent-uses-variety"}
    decides = reps["picks-agent-decides-every-line"]
    assert decides["passed"] is True and passing(decides) == {"decided", "main", "no-errors"}
    assert "no-flags" in passing(reps["picks-agent-credits-every-picture"])
    assert "decided" in passing(reps["picks-agent-uses-variety"])
    assert "variety" not in passing(reps["picks-agent-uses-variety"])                                      # the fake agent brings four different pictures, not six: scored, and failed, not skipped
    out = outputs["picks-agent-decides-every-line-1"]
    assert out["picks"]["main_asset"] == "A" and len(out["picks"]["beats"]) == 6 and out["job"]["state"] == "done" and out["job"]["kind"] == "picks"
    assert [c["mode"] for c in joined.fake.calls[:2]] == ["plan", "choose"]
    posts = [b for m, p, b in joined.transport.log if m == "POST" and p.endswith("/picks/auto")]
    assert len(posts) == 3 and all(b["actor"] == "agent:eval" for b in posts)                              # the bench names itself in the body the answer described
    assert rec["sample_unchanged"] is True and [d.name for d in joined.root.iterdir()] == []


def test_a_sample_without_a_narration_keeps_the_cases_that_need_one_skipped_with_their_sentence(tmp_path, joined):
    """The repository's own sample `arnolfini-from-books` (an outline, no narration): the cases of the pictures steps are skipped, never failed, and say why."""
    shutil.rmtree(joined.samples / "arnolfini-from-books")
    shutil.copytree(REPO / "projects" / "arnolfini-from-books", joined.samples / "arnolfini-from-books")
    for step in ("edit_picks", "picks_agent"):
        rec, outputs = joined.run(step)
        reps = [c["repeats"][0] for c in rec["cases"]]
        assert len(reps) == 3 and outputs == {}
        for rep in reps:
            assert rep["skipped"] and "has no script/narration.json" in rep["skipped"] and rep["criteria"] == [] and rep["passed"] is False
        assert rec["summary"]["ran"] == 0 and rec["summary"]["skipped"] == 3
    assert [d.name for d in joined.root.iterdir()] == []


def test_a_sample_with_a_narration_but_no_main_painting_says_what_the_agent_needs(tmp_path, joined):
    p = joined.samples / "arnolfini-from-books"
    (p / "picks.json").unlink()
    rec, _ = joined.run("picks_agent", names=["picks-agent-decides-every-line"])
    rep = rec["cases"][0]["repeats"][0]
    assert rep["skipped"] and "picks.auto" in rep["skipped"] and "main_asset" in rep["skipped"] and rep["criteria"] == []
    assert rec["sample_unchanged"] is True


def test_the_answer_of_a_request_the_box_could_not_do_is_judged_as_cannot_for_both_boxes():
    """The turn of a typed-operations box ends `no_change` (the model said cannot, nothing written) or `escalate` (it needs a picture the project lacks)."""
    from bti.evals import criteria
    for code in ("cannot", "no_change", "escalate"):
        r = criteria.evaluate_all([{"id": "c", "kind": "edit.answered_cannot"}], {"answer": {"code": code, "reason": "Cần một hình mà dự án chưa có."}, "before": {"beats": {}}, "after": {"beats": {}}})
        assert r[0]["passed"] is True, code
    r = criteria.evaluate_all([{"id": "c", "kind": "edit.answered_cannot"}], {"answer": {"code": "applied", "reason": "x"}, "before": {"beats": {}}, "after": {"beats": {}}})
    assert r[0]["passed"] is False
    r = criteria.evaluate_all([{"id": "c", "kind": "edit.answered_cannot"}], {"answer": {"code": "no_change", "reason": "x"}, "before": {"beats": {}}, "after": {"beats": {"b0001": {"status": "skip", "items": []}}}})
    assert r[0]["passed"] is False and r[0]["value"]["unchanged"] is False                              # said cannot but the picks changed: not a pass
