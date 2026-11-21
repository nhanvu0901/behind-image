"""A run of the bench: end to end with the fake agents (the mock model of the test launchers, and a fake app for the steps no route of this checkout serves yet): the copy of the
sample project, the repeats, the criteria recorded, the files written, the source project byte for byte the same afterwards, `--yes-cost`, `compare`."""
import io
import json
from pathlib import Path

import pytest

from bti.evals import cases, cli, report, runner, samples
from fake_app import FakeApp

REPO = Path(__file__).resolve().parents[2]


def write_cases(tmp_path, step, *docs):
    root = tmp_path / "cases"
    (root / step).mkdir(parents=True, exist_ok=True)
    for d in docs:
        doc = {"schema": "bti.eval.case/1", "step": step, "title": d["name"], "why": "test", "request": {}, **d}
        (root / step / (d["name"] + ".json")).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return root


def run_bench(step, transport, samples_root, projects_root, tmp_path, *, agent="gem", repeat=2, names=None, cases_root=None, **kw):
    return runner.run(step=step, agent_id=agent, repeat=repeat, transport=transport, case_names=names, samples_root=samples_root, projects_root=projects_root,
                      cases_root=cases_root, app_url="http://test", poll=0.01, **kw)


# ------------------------------------------------------------------------------------------------------------------------ the real app, the mock agent
def test_the_outline_bench_end_to_end_on_a_copy_and_the_sample_is_byte_identical_afterwards(tmp_path, client, transport, samples, root):
    cr = write_cases(tmp_path, "outline",
                     {"name": "outline-pass", "sample": {"project": "arnolfini-from-books", "start": "book"},
                      "criteria": [{"id": "chapters", "kind": "outline.chapters_between", "min": 3, "max": 12}, {"id": "no-errors", "kind": "outline.no_error_issues"}]},
                     {"name": "outline-fail", "sample": {"project": "arnolfini-from-books", "start": "book"},
                      "criteria": [{"id": "twenty", "kind": "outline.chapters_between", "min": 20, "max": 30}, {"id": "thesis", "kind": "outline.thesis_and_hooks", "hooks": 3}]})
    before = samples_mod_hash(samples)
    lines = []
    rec, outputs = run_bench("outline", transport, samples, root, tmp_path, cases_root=cr, say=lines.append)
    assert samples_mod_hash(samples) == before and rec["sample_unchanged"] is True            # nothing was written into the sample
    assert [d.name for d in root.iterdir()] == []                                              # the copies were removed again, through the app
    assert all(not p["id"].startswith("eval-") for p in client.get("/api/projects").json())
    assert rec["schema"] == "bti.eval.run/1" and rec["command"] == {"step": "outline", "agent": "gem", "repeat": 2, "cases": ["outline-fail", "outline-pass"]}
    assert rec["agent"] == {"id": "gem", "label": "Gemini giả", "model": "mock"}
    assert rec["briefing"]["hash"].startswith("sha1:") and "prompts/outline.md" in rec["briefing"]["files"] and rec["briefing"]["missing"] == []
    by = {c["name"]: c for c in rec["cases"]}
    assert len(by["outline-pass"]["repeats"]) == 2 and len(by["outline-fail"]["repeats"]) == 2
    for rep in by["outline-pass"]["repeats"]:
        assert rep["passed"] is True and all(c["passed"] for c in rep["criteria"]) and rep["error"] is None and rep["skipped"] is None
        assert [c["id"] for c in rep["criteria"]] == ["chapters", "no-errors"]
        assert rep["criteria"][0]["value"] >= 3 and rep["criteria"][0]["kind"] == "outline.chapters_between"
        assert rep["seconds"] is not None and rep["project"].startswith("eval-") and rep["cleanup"] is None and rep["agent"]["id"] == "gem" and rep["jobs"][0]["state"] == "done"
        assert rep["model_calls"] == 1
    for rep in by["outline-fail"]["repeats"]:
        assert rep["passed"] is False
        twenty = next(c for c in rep["criteria"] if c["id"] == "twenty")
        assert twenty["passed"] is False and isinstance(twenty["value"], int) and "wanted 20 to 30" in twenty["detail"]
    assert any("[outline-pass 1/2] passed 2/2" in l for l in lines) and any("[outline-fail 2/2] FAILED" in l and "twenty" in l for l in lines)
    assert set(outputs) == {"outline-pass-1", "outline-pass-2", "outline-fail-1", "outline-fail-2"}
    assert outputs["outline-pass-1"]["outline"]["chapters"] and outputs["outline-pass-1"]["brief"]["sources"]            # the documents are kept for a reader


def samples_mod_hash(s):
    return samples.tree_hash(s / "arnolfini-from-books") + samples.tree_hash(s / "arnolfini")


def test_the_narration_bench_starts_from_an_approved_outline(tmp_path, client, transport, samples, root):
    cr = write_cases(tmp_path, "narration", {"name": "narration-x", "sample": {"project": "arnolfini-from-books", "start": "outline_approved"},
                                               "criteria": [{"id": "no-errors", "kind": "narration.no_error_issues"}, {"id": "chapters", "kind": "narration.chapters_match_outline"},
                                                            {"id": "ten", "kind": "narration.minutes_at_least", "minutes": 600}]})
    rec, outputs = run_bench("narration", transport, samples, root, tmp_path, repeat=1, cases_root=cr)
    rep = rec["cases"][0]["repeats"][0]
    got = {c["id"]: c for c in rep["criteria"]}
    assert rep["error"] is None and got["no-errors"]["passed"] is True and got["chapters"]["passed"] is True, rep
    assert got["ten"]["passed"] is False and got["ten"]["value"] > 0                                    # ten HOURS: it measured, it did not pass
    assert outputs["narration-x-1"]["narration"]["chapters"] and outputs["narration-x-1"]["outline"]["chapters"]
    assert [d.name for d in root.iterdir()] == [] and rec["sample_unchanged"] is True
    assert rec["briefing"]["files"] == ["prompts/script.md", "prompts/rules_format.md", "prompts/rules_voice.md"]


def test_the_copy_is_never_a_project_of_the_owner_and_only_its_own_copies_are_removed(tmp_path, client, transport, samples, root):
    owner = root / "owners-video"
    owner.mkdir()
    (owner / "project.json").write_text(json.dumps({"id": "owners-video", "title": "Mine"}), encoding="utf-8")
    cr = write_cases(tmp_path, "outline", {"name": "outline-a", "sample": {"project": "arnolfini-from-books", "start": "book"},
                                             "criteria": [{"id": "c", "kind": "outline.no_error_issues"}]})
    rec, _ = run_bench("outline", transport, samples, root, tmp_path, repeat=1, cases_root=cr)
    assert [d.name for d in root.iterdir()] == ["owners-video"] and (owner / "project.json").is_file()
    deletes = [p for m, p, _ in transport.log if m == "DELETE"]
    assert len(deletes) == 1 and deletes[0].startswith("/api/projects/eval-") and deletes[0].endswith("?confirm=" + rec["cases"][0]["repeats"][0]["project"])
    assert runner._remove_copy(transport, "owners-video", set()) == "refused to remove owners-video: this run did not make it"
    assert (owner / "project.json").is_file()


def test_keep_leaves_the_copies_in_the_app(tmp_path, client, transport, samples, root):
    cr = write_cases(tmp_path, "outline", {"name": "outline-a", "sample": {"project": "arnolfini-from-books", "start": "book"}, "criteria": [{"id": "c", "kind": "outline.no_error_issues"}]})
    rec, _ = run_bench("outline", transport, samples, root, tmp_path, repeat=1, cases_root=cr, keep=True)
    assert [d.name for d in root.iterdir()] == [rec["cases"][0]["repeats"][0]["project"]] and not [x for x in transport.log if x[0] == "DELETE"]


# ------------------------------------------------------------------------------------------------------------------------ the command
def command(argv, transport, tmp_path, samples, root, cases_root=None):
    out, err = io.StringIO(), io.StringIO()
    argv = list(argv)
    if cases_root:
        argv += ["--cases-root", str(cases_root)]
    code = cli.main(argv + ["--samples-root", str(samples), "--projects-root", str(root), "--out", str(tmp_path / "out"), "--poll", "0.01"], stdout=out, stderr=err, transport=transport)
    return code, out.getvalue(), err.getvalue()


def test_a_run_says_what_it_is_about_to_ask_and_starts_nothing_without_yes_cost(tmp_path, client, transport, samples, root):
    cr = write_cases(tmp_path, "outline", {"name": "outline-a", "sample": {"project": "arnolfini-from-books", "start": "book"}, "criteria": [{"id": "c", "kind": "outline.no_error_issues"}]},
                     {"name": "outline-b", "sample": {"project": "arnolfini-from-books", "start": "book"}, "criteria": [{"id": "c", "kind": "outline.no_error_issues"}]})
    code, out, err = command(["run", "--step", "outline", "--agent", "gem", "--repeat", "3"], transport, tmp_path, samples, root, cr)
    assert code == 3 and "agent gem (mock)" in out and "2 cases x 3 repeats = 6 runs" in out and "1 agent call" in out and "at least 6 agent run(s)" in out
    assert "nothing was started" in out and "--yes-cost" in out
    assert [m for m, p, _ in transport.log if m != "GET"] == [] and list(root.iterdir()) == [] and not (tmp_path / "out").exists()
    code, out, err = command(["run", "--step", "outline", "--agent", "gem", "--repeat", "1", "--yes-cost"], transport, tmp_path, samples, root, cr)
    assert code == 0, err
    assert "# Bench run " in out and "| outline-a | 1/1 | 1/1 |" in out and "run file: " in out
    files = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert [f for f in files if f.endswith(".json")] and [f for f in files if f.endswith(".md")] and [f for f in files if not f.endswith((".json", ".md"))]


def test_the_command_refuses_what_it_cannot_do_with_a_sentence_and_a_code(tmp_path, client, transport, samples, root):
    cr = write_cases(tmp_path, "outline", {"name": "outline-a", "sample": {"project": "arnolfini-from-books", "start": "book"}, "criteria": [{"id": "c", "kind": "outline.no_error_issues"}]})
    code, out, err = command(["run", "--step", "outline", "--agent", "nobody", "--yes-cost"], transport, tmp_path, samples, root, cr)
    assert code == 2 and "no agent 'nobody'" in err and "gem" in err
    assert command(["run", "--step", "outline", "--agent", "gem", "--repeat", "0", "--yes-cost"], transport, tmp_path, samples, root, cr)[0] == 2
    assert command(["run", "--step", "outline", "--agent", "gem", "--case", "nope", "--yes-cost"], transport, tmp_path, samples, root, cr)[0] == 2
    code, out, err = command(["run", "--step", "outline", "--agent", "off", "--yes-cost"], FakeApp(root), tmp_path, samples, root, cr)
    assert code == 3 and "cannot run on this machine: Chưa đăng nhập." in err
    assert command(["run", "--step", "lunch"], transport, tmp_path, samples, root)[0] == 2
    assert command(["frobnicate"], transport, tmp_path, samples, root)[0] == 2
    assert [m for m, p, _ in transport.log if m != "GET"] == []


def test_list_shows_the_cases_and_the_kinds_of_criteria():
    out = io.StringIO()
    assert cli.main(["list", "--step", "edit_storyboard"], stdout=out) == 0
    assert "edit-zoom-slower" in out.getvalue() and "arnolfini/as_is" in out.getvalue() and "3 cases" in out.getvalue()
    out = io.StringIO()
    assert cli.main(["list", "--criteria"], stdout=out) == 0
    assert "outline.chapters_between" in out.getvalue() and "needs: outline" in out.getvalue() and "edit.metric_moved" in out.getvalue()


# ------------------------------------------------------------------------------------------------------------------------ steps without a real route here: the fake app
EDIT_CASE = {"name": "edit-slower", "sample": {"project": "arnolfini", "start": "as_is"},
             "request": {"instruction": "Zoom chậm hơn.", "scope": {"shots": ["s0004", "s0005"]}, "mode": "fast"},
             "criteria": [{"id": "scope", "kind": "edit.only_scope_changed"}, {"id": "changed", "kind": "edit.changed_something_in_scope"},
                          {"id": "slower", "kind": "edit.metric_moved", "metric": "zoom_rate", "direction": "decrease"}, {"id": "no-errors", "kind": "edit.no_error_issues"}]}


@pytest.mark.parametrize("behaviour,passed,failing", [("good", True, []), ("sloppy", False, ["scope"]), ("fails", False, None)])
def test_the_edit_of_the_storyboard_is_driven_and_judged(tmp_path, samples, root, behaviour, passed, failing):
    app = FakeApp(root, behaviour)
    cr = write_cases(tmp_path, "edit_storyboard", EDIT_CASE)
    rec, outputs = run_bench("edit_storyboard", app, samples, root, tmp_path, repeat=1, cases_root=cr)
    rep = rec["cases"][0]["repeats"][0]
    assert rep["passed"] is passed, rep
    if failing is not None:
        assert [c["id"] for c in rep["criteria"] if not c["passed"]] == failing
    o = outputs["edit-slower-1"]
    if behaviour == "fails":
        assert "the edit ended as failed" in rep["error"] or "agy_timeout" in rep["error"]
        assert o["answer"]["code"] == "failed" and not next(c for c in rep["criteria"] if c["id"] == "changed")["passed"]
    else:
        assert o["scope"] == {"shots": ["s0004", "s0005"]} and o["answer"]["code"] == "applied" and o["before"]["shots"] and o["after"]["shots"]
    assert app.deleted == [rep["project"]] and rec["sample_unchanged"] is True
    post = next(b for m, p, b in app.log if m == "POST" and p.endswith("/draft/edit"))
    assert post["instruction"] == "Zoom chậm hơn." and post["mode"] == "fast" and post["scope"] == {"shots": ["s0004", "s0005"]} and post["base_rev"]
    if behaviour == "good":
        assert next(c for c in rep["criteria"] if c["id"] == "slower")["value"]["moved"]


def test_a_request_the_project_cannot_do_is_judged_by_the_answer(tmp_path, samples, root):
    app = FakeApp(root, "cannot")
    cr = write_cases(tmp_path, "edit_storyboard", {"name": "edit-cannot", "sample": {"project": "arnolfini", "start": "as_is"},
                                                    "request": {"instruction": "Thay hình bằng Mona Lisa.", "scope": {"shots": ["s0004"]}},
                                                    "criteria": [{"id": "cannot", "kind": "edit.answered_cannot"}, {"id": "scope", "kind": "edit.only_scope_changed"}]})
    rec, outputs = run_bench("edit_storyboard", app, samples, root, tmp_path, repeat=1, cases_root=cr)
    rep = rec["cases"][0]["repeats"][0]
    assert rep["passed"] is True and rep["error"] is None, rep
    assert outputs["edit-cannot-1"]["answer"]["code"] == "cannot" and "nhập hình" in outputs["edit-cannot-1"]["answer"]["reason"]


def test_a_failed_job_is_a_failed_repeat_with_the_reason_never_a_lost_run(tmp_path, samples, root):
    app = FakeApp(root, "fails")
    cr = write_cases(tmp_path, "draft", {"name": "draft-x", "sample": {"project": "arnolfini", "start": "as_is"}, "request": {"apply": True},
                                          "criteria": [{"id": "no-errors", "kind": "draft.no_error_issues"}, {"id": "pace", "kind": "draft.shot_pace"}]})
    rec, _ = run_bench("draft", app, samples, root, tmp_path, repeat=2, cases_root=cr)
    for rep in rec["cases"][0]["repeats"]:
        assert rep["passed"] is False and "agy_timeout" in rep["error"] and "Quá giờ" in rep["error"] and rep["skipped"] is None
        assert all(c["passed"] is False and "nothing to check" in c["detail"] for c in rep["criteria"])
    assert app.deleted and len(app.deleted) == 2


def test_the_draft_is_driven_through_the_proposal_and_judged_on_the_storyboard(tmp_path, samples, root):
    app = FakeApp(root, "good")
    cr = write_cases(tmp_path, "draft", {"name": "draft-ok", "sample": {"project": "arnolfini", "start": "as_is"}, "request": {"body": {"chapters": ["c01"]}},
                                          "criteria": [{"id": "no-errors", "kind": "draft.no_error_issues"}, {"id": "covers", "kind": "draft.covers_the_narration", "slack": 1.0},
                                                       {"id": "pace", "kind": "draft.shot_pace", "median_min": 1.0, "median_max": 30.0, "shortest": 0.1, "longest": 400.0, "max_share_under_4": 1.0}]})
    rec, outputs = run_bench("draft", app, samples, root, tmp_path, repeat=1, cases_root=cr)
    rep = rec["cases"][0]["repeats"][0]
    assert rep["passed"] is True, rep
    start = next(b for m, p, b in app.log if p.endswith("/draft/start"))
    assert start == {"provider": "agy", "chapters": ["c01"]}
    assert any(p.endswith("/proposals/p1/apply") and b == {"accept": "all"} for m, p, b in app.log)
    assert outputs["draft-ok-1"]["proposal"] == "p1" and outputs["draft-ok-1"]["storyboard"]["shots"]


@pytest.mark.parametrize("step,action", [("picks_agent", "picks.auto"), ("edit_picks", "picks.edit")])
def test_a_step_whose_action_the_app_does_not_list_yet_is_skipped_not_failed(tmp_path, samples, root, step, action):
    app = FakeApp(root, "good", actions={})
    req = {} if step == "picks_agent" else {"instruction": "Bỏ qua dòng này.", "scope": {"beats": ["b0001"]}}
    crit = [{"id": "main", "kind": "picks.main_painting_chosen"}] if step == "picks_agent" else [{"id": "scope", "kind": "picks.only_scope_changed", "beats": ["b0001"]}]
    cr = write_cases(tmp_path, step, {"name": "x-case", "sample": {"project": "arnolfini", "start": "as_is"}, "request": req, "criteria": crit})
    rec, outputs = run_bench(step, app, samples, root, tmp_path, repeat=2, cases_root=cr)
    reps = rec["cases"][0]["repeats"]
    assert all(r["skipped"] and action in r["skipped"] and "does not list the action" in r["skipped"] and r["criteria"] == [] and r["passed"] is False for r in reps)
    assert report.totals(rec)["ran"] == 0 and report.totals(rec)["skipped"] == 2 and outputs == {}
    assert "| x-case | skipped |" in report.summary_table(rec)
    assert len(app.deleted) == 2                                                          # the copies are removed even when the case was skipped


def test_the_pictures_agent_and_the_edit_of_the_picks_run_through_the_action_of_the_state_answer(tmp_path, samples, root):
    listed = {"id": "picks.auto", "method": "POST", "path": "/api/projects/PID/picks/auto", "ready": True, "needs": [], "body": {"beats": None, "actor": "agent:x"}, "long_job": True,
              "follow": "GET /api/longjobs/{job_id}"}
    app = FakeApp(root, "good")
    cr = write_cases(tmp_path, "picks_agent", {"name": "pa", "sample": {"project": "arnolfini", "start": "as_is"}, "request": {"body": {"beats": ["b0001"]}},
                                                "criteria": [{"id": "main", "kind": "picks.main_painting_chosen"}, {"id": "decided", "kind": "picks.every_beat_decided"}, {"id": "credited", "kind": "picks.credited"}]})

    class Listing(FakeApp):
        def request(self, method, path, body=None, timeout=60.0):
            if method == "GET" and path.endswith("/state"):
                pid = path.split("/")[3]
                a = {**listed, "path": "/api/projects/%s/picks/auto" % pid}
                self.actions = {"picks.auto": a}
            return super().request(method, path, body, timeout)
    app = Listing(root, "good")
    rec, outputs = run_bench("picks_agent", app, samples, root, tmp_path, repeat=1, cases_root=cr)
    rep = rec["cases"][0]["repeats"][0]
    assert rep["skipped"] is None and rep["passed"] is True, rep
    post = next(b for m, p, b in app.log if m == "POST" and p.endswith("/picks/auto"))
    assert post == {"beats": ["b0001"], "actor": "agent:eval"}                           # the example body of the answer, the case's fields, the bench's own actor
    assert outputs["pa-1"]["picks"]["main_asset"] == "MAIN"


# ------------------------------------------------------------------------------------------------------------------------ the samples
def test_the_copies_have_the_shape_of_their_start(tmp_path, samples):
    root = tmp_path / "copies"
    root.mkdir()
    book = samples_copy(samples, root, "arnolfini-from-books", "book", "eval-t-1-1")
    assert (book / "project.json").is_file() and not (book / "script").exists()
    out = samples_copy(samples, root, "arnolfini-from-books", "outline_approved", "eval-t-2-1")
    assert (out / "script" / "outline.json").is_file()
    asis = samples_copy(samples, root, "arnolfini", "as_is", "eval-t-3-1")
    assert (asis / "storyboard.json").is_file() and (asis / "timing.json").is_file() and not (asis / "cache").exists()
    for d in (book, out, asis):
        meta = json.loads((d / "project.json").read_text(encoding="utf-8"))
        assert "protected" not in meta and meta["eval_copy"] is True                      # a reference project is protected; its copy can be removed through the app
    locked = samples_copy(samples, root, "arnolfini", "as_is_locked", "eval-t-4-1")
    shots = json.loads((locked / "storyboard.json").read_text(encoding="utf-8"))["shots"]
    assert [i for i, s in enumerate(shots) if s.get("locked")] == list(range(4, len(shots), 5))
    assert json.loads((samples / "arnolfini" / "project.json").read_text(encoding="utf-8")).get("protected") is True            # the sample keeps its flag
    with pytest.raises(samples_error(), match="no script/narration.json"):
        samples_copy(samples, root, "arnolfini-from-books", "narration_approved", "eval-t-5-1")
    assert not (root / "eval-t-5-1").exists()                                              # the partial copy was taken away
    with pytest.raises(samples_error(), match="no beat ids"):
        samples_copy(samples, root, "arnolfini", "redraft", "eval-t-6-1")
    with pytest.raises(samples_error(), match="unknown start"):
        samples_copy(samples, root, "arnolfini", "lunch", "eval-t-7-1")
    with pytest.raises(samples_error(), match="is not in"):
        samples_copy(samples, root, "nope", "book", "eval-t-8-1")
    with pytest.raises(samples_error(), match="already exists"):
        samples_copy(samples, root, "arnolfini", "as_is", "eval-t-3-1")


def samples_copy(samples_root, root, name, start, new_id):
    return samples.copy_project(samples_root, name, start, root, new_id)


def samples_error():
    return samples.SampleError


def test_a_redraft_gets_picks_made_from_the_finished_storyboard_when_the_timing_has_beat_ids(tmp_path, samples):
    d = samples / "arnolfini"
    tm = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    for i, b in enumerate(tm["beats"]):
        b["id"] = "b%04d" % (i + 1)
    (d / "timing.json").write_text(json.dumps(tm), encoding="utf-8")
    root = tmp_path / "copies"
    root.mkdir()
    c = samples_copy(samples, root, "arnolfini", "redraft", "eval-t-1-1")
    assert not (c / "storyboard.json").exists()
    picks = json.loads((c / "picks.json").read_text(encoding="utf-8"))
    assert picks["schema"] == "bti.picks/1" and picks["main_asset"] == "A" and picks["approval"] == {"approved": True} and picks["assets"]["A"]["file"].startswith("media/")
    assert picks["beats"] and all(b["items"][0]["asset"] and b["status"] == "picked" for b in picks["beats"].values())


def test_the_hash_of_a_folder_changes_with_any_byte_and_the_briefing_hash_with_any_prompt(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f.txt").write_text("one", encoding="utf-8")
    h = samples.tree_hash(tmp_path / "a")
    assert samples.tree_hash(tmp_path / "a") == h
    (tmp_path / "a" / "f.txt").write_text("two", encoding="utf-8")
    assert samples.tree_hash(tmp_path / "a") != h
    for rel in ("prompts/outline.md", "prompts/rules_format.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8")
    b1 = runner.briefing("outline", tmp_path)
    (tmp_path / "prompts" / "outline.md").write_text("changed", encoding="utf-8")
    b2 = runner.briefing("outline", tmp_path)
    assert b1["hash"] != b2["hash"] and b1["files"] == b2["files"] == ["prompts/outline.md", "prompts/rules_format.md"]
    assert runner.briefing("picks_agent", tmp_path)["hash"] == "sha1:none"
    assert runner.briefing("draft", tmp_path)["missing"] == ["skills/storyboard_draft/TASK.template.md"]


# ------------------------------------------------------------------------------------------------------------------------ the report and compare
def fake_run(run_id, passes, agent="gem", model="mock", briefing="sha1:aaaa"):
    """A run record of one case with three repeats where `passes` is the list of (criterion id -> passed) dicts."""
    reps = [{"n": i + 1, "seconds": 10.0 + i, "skipped": None, "error": None, "passed": all(p.values()),
             "criteria": [{"id": k, "kind": "outline.chapters_between", "passed": v, "value": 6, "detail": "d"} for k, v in p.items()]} for i, p in enumerate(passes)]
    return {"schema": "bti.eval.run/1", "run_id": run_id, "command": {"step": "outline", "agent": agent, "repeat": len(passes)}, "agent": {"id": agent, "model": model},
            "briefing": {"hash": briefing}, "app": {"url": "u"}, "sample_unchanged": True, "cases": [{"name": "outline-chapter-count", "repeats": reps}]}


def test_the_summary_says_how_many_repeats_passed_and_which_criterion_failed_most():
    run = fake_run("r1", [{"chapters": True, "sourced": True}, {"chapters": False, "sourced": True}, {"chapters": False, "sourced": False}])
    s = report.case_stats(run["cases"][0])
    assert (s["passed_repeats"], s["ran"], s["checks"], s["checks_passed"], s["fails"].most_common(1)) == (1, 3, 6, 3, [("chapters", 2)])
    table = report.summary_table(run)
    assert "| outline-chapter-count | 1/3 | 3/6 | chapters (2x) | 11.0 |" in table
    assert "repeats that passed every criterion: 1 of 3 (33%)" in table and "criteria checks passed: 3 of 6 (50%)" in table and "byte for byte the same" in table
    assert report.summary_lines(run)[0] == "1 cases x repeats = 3 runs: 3 ran, 0 skipped"


def test_compare_shows_what_changed_between_two_runs():
    a = fake_run("r1", [{"chapters": True, "sourced": False}] * 3)
    b = fake_run("r2", [{"chapters": True, "sourced": True}, {"chapters": True, "sourced": True}, {"chapters": False, "sourced": True}], agent="opus", briefing="sha1:bbbb")
    text = report.compare(a, b)
    assert "agent: gem -> opus (CHANGED)" in text and "briefing: sha1:aaaa -> sha1:bbbb (CHANGED)" in text and "model: mock (unchanged)" in text
    assert "| outline-chapter-count | 0/3 | 2/3 | better | chapters 3/3 -> 2/3; sourced 0/3 -> 3/3 |" in text
    assert report.compare(b, a).count("WORSE") == 1 and "cases better: 1, worse: 0" in text
    c = fake_run("r3", [{"chapters": True}] * 3)
    c["cases"][0]["name"] = "other-case"
    assert "only in" in report.compare(a, c)


def test_the_files_of_a_run_are_written_and_read_back(tmp_path):
    run = fake_run("20261119-142301-ab12", [{"chapters": True}] * 2)
    p = report.write_run(run, tmp_path / "o", {"outline-chapter-count-1": {"outline": {"chapters": [1]}}})
    assert p.name == "20261119-142301-ab12.json" and (tmp_path / "o" / "20261119-142301-ab12.md").read_text(encoding="utf-8").startswith("# Bench run 20261119-142301-ab12")
    assert json.loads((tmp_path / "o" / "20261119-142301-ab12" / "outline-chapter-count-1.json").read_text(encoding="utf-8"))["outline"]["chapters"] == [1]
    assert report.load_run("20261119-142301-ab12", tmp_path / "o")["run_id"] == "20261119-142301-ab12" and report.load_run(str(p), tmp_path)["run_id"] == "20261119-142301-ab12"
    with pytest.raises(FileNotFoundError):
        report.load_run("nope", tmp_path / "o")
    (tmp_path / "o" / "bad.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        report.load_run("bad", tmp_path / "o")


def test_compare_and_show_through_the_command(tmp_path, client, transport, samples, root):
    cr = write_cases(tmp_path, "outline", {"name": "outline-a", "sample": {"project": "arnolfini-from-books", "start": "book"}, "criteria": [{"id": "c", "kind": "outline.chapters_between", "min": 3, "max": 12}]})
    for _ in range(2):
        assert command(["run", "--step", "outline", "--agent", "gem", "--repeat", "1", "--yes-cost"], transport, tmp_path, samples, root, cr)[0] == 0
    ids = sorted(p.stem for p in (tmp_path / "out").glob("*.json"))
    assert len(ids) == 2
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["compare", ids[0], ids[1], "--out", str(tmp_path / "out")], stdout=out, stderr=err) == 0 and "# Bench compare: %s -> %s" % (ids[0], ids[1]) in out.getvalue()
    out = io.StringIO()
    assert cli.main(["show", ids[0], "--out", str(tmp_path / "out")], stdout=out) == 0 and "| outline-a | 1/1 |" in out.getvalue()
    assert cli.main(["show", "nope", "--out", str(tmp_path / "out")], stdout=io.StringIO(), stderr=io.StringIO()) == 2
