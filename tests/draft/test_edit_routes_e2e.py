"""Edit by instruction, end to end through the HTTP routes (contract A2 to A4).

Why this file exists: the unit tests of `fastedit`, `merge` and `run` call the pieces one by one, or call `draft_run.start` with
test-only hooks, so the real route `POST /api/projects/{pid}/draft/edit` never reached the real functions. The first real request
failed with `TypeError: fast_edit() takes 2 positional arguments but 3 were given`. Everything here goes through the app (`create_app`
and the test client): `POST /draft/edit`, the long-job route until the job ends, `GET /draft/thread`, the storyboard routes, `resolve`,
`undo`, the frame route. NOTHING of `bti.draft` is replaced.

The only stand-ins are the ones a real run also has outside the code under test:
  * the model of the fast path is the `mock` provider (selected through `PUT /api/settings/models`), whose canned answers are queued
    through its own `set_canned`; `HeldModel` holds that provider's answer on an event, which is how "the owner saves while the job
    waits" is made deterministic (it wraps the provider, it does not touch bti.draft);
  * the deep path runs the fake `agy` program of the draft tests (BTI_AGY_BIN), the same way test_agy.py does.
"""
from __future__ import annotations

import copy
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from bti.draft import decompile as D
from bti.draft.inputs import load_inputs
from bti.draft.thread import load_thread, turns_dir
from bti.editor.app import create_app
from bti.longjob import manager as global_mgr
from bti.script.providers import mock
from helpers import GOOD, clean_spec
from test_agy import fake  # noqa: F401  (the fake agy program and its fixture)


# ----------------------------------------------------------------------------------------------------------- helpers
def strip(o):
    """A document without the derived `_` keys (what two storyboards are compared by)."""
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def why(job: dict) -> str:
    """What a failed long job says, for the message of an assert."""
    return "state=%s code=%s error=%s log=%s" % (job.get("state"), job.get("error_code"), job.get("error"), job.get("log_tail"))


class HeldModel:
    """Holds the mock provider's answer until `release` is set; `entered` is set when a call arrives. It wraps the PROVIDER (the
    stand-in of the model), so the time the model takes is under the test's control."""

    def __init__(self, monkeypatch):
        self.entered = threading.Event()
        self.release = threading.Event()
        real = mock.complete

        def held(spec, system, user, **kw):
            self.entered.set()
            assert self.release.wait(60), "the test never released the model"
            return real(spec, system, user, **kw)

        monkeypatch.setattr(mock, "complete", held)


class Env:
    def __init__(self, client: TestClient, pdir):
        self.client, self.pdir, self.pid = client, pdir, pdir.name

    # -- plumbing
    def u(self, tail: str = "") -> str:
        return "/api/projects/%s%s" % (self.pid, tail)

    def wait_job(self, job_id: str, timeout: float = 120.0) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            r = self.client.get("/api/longjobs/%s" % job_id)
            assert r.status_code == 200, r.text
            j = r.json()
            if j["state"] not in ("queued", "running", "waiting"):
                return j
            time.sleep(0.05)
        raise AssertionError("the job did not end: %s" % self.client.get("/api/longjobs/%s" % job_id).text)

    def thread(self) -> list[dict]:
        r = self.client.get(self.u("/draft/thread"))
        assert r.status_code == 200, r.text
        return r.json()["turns"]

    def turn(self, turn_id: str) -> dict:
        return next(t for t in self.thread() if t["id"] == turn_id)

    def state(self) -> dict:
        r = self.client.get(self.u())
        assert r.status_code == 200, r.text
        return r.json()

    def rev(self) -> str:
        return self.state()["rev"]

    def saved(self) -> dict:
        """storyboard.json as the app serves it, without `_` keys."""
        return strip(self.state()["storyboard"])

    def raw(self) -> dict:
        return json.loads((self.pdir / "storyboard.json").read_text(encoding="utf-8"))

    # -- the request, exactly as the page sends it
    def post_edit(self, instruction: str, shots=None, *, chapter: str | None = None, all_: bool = False, mode: str = "fast", **extra):
        scope = {"shots": shots} if shots is not None else ({"chapter": chapter} if chapter else {"all": True} if all_ else {})
        body = {"instruction": instruction, "scope": scope, "mode": mode}
        body.update(extra)
        return self.client.post(self.u("/draft/edit"), json=body)

    def run_edit(self, instruction: str, shots=None, **kw) -> tuple[dict, dict]:
        """POST /draft/edit, wait for the long job, return (job record, turn from GET /draft/thread)."""
        r = self.post_edit(instruction, shots, **kw)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) >= {"job_id", "turn_id"}, body
        job = self.wait_job(body["job_id"])
        return job, self.turn(body["turn_id"])

    # -- the draft specs the model is shown, and the answers a model gives
    def decomp(self) -> dict:
        inp = load_inputs(self.pdir, for_edit=True)
        return D.decompile(inp)

    def content_ids(self, chapter: str | None = None) -> list[str]:
        out = []
        for cid, d in self.decomp().items():
            if chapter in (None, cid):
                out += [s["id"] for s in d["spec"]["shots"]]
        return out

    def spec_shots(self, ids: list[str]) -> list[dict]:
        """The scope shots as the model sees them in the prompt (draft spec shots with the helper fields)."""
        want = set(ids)
        out = []
        for cid, d in self.decomp().items():
            for s in d["spec"]["shots"]:
                if s["id"] in want:
                    out.append(copy.deepcopy(s))
        return out

    def edit_answer(self, ids: list[str], overrides: dict[str, dict], summary: str = "Đã đổi hai cảnh theo yêu cầu.") -> str:
        """A good `edit` answer: the scope's shots echoed back as the prompt showed them (helper fields included), with `overrides`
        applied by shot id."""
        shots = self.spec_shots(ids)
        for s in shots:
            s.update(overrides.get(s["id"], {}))
        return json.dumps({"result": "edit", "summary": summary, "shots": shots,
                           "changes": [{"shot": sid, "what": "Đổi cảnh %d theo yêu cầu." % (i + 1)} for i, sid in enumerate(overrides)]},
                          ensure_ascii=False)

    def deep_cfg(self, fake_dir, overrides: dict[str, dict], notes_json: dict | None = None) -> None:
        """What the fake agy writes into out/: every chapter's decompiled spec with `overrides` (by shot id) applied."""
        specs = {}
        for cid, d in self.decomp().items():
            sp = copy.deepcopy(d["spec"])
            for s in sp["shots"]:
                s.update(overrides.get(s["id"], {}))
            specs[cid] = sp
        (fake_dir / "cfg.json").write_text(json.dumps({"specs": specs, "victim": str(self.pdir / "timing.json"),
                                                       "notes_json": notes_json}), encoding="utf-8")

    def manual_save(self, mutate) -> str:
        """The owner saves the storyboard by hand through PUT /storyboard (what the editor does). Returns the new rev."""
        st = self.state()
        sb = strip(st["storyboard"])
        mutate(sb)
        r = self.client.put(self.u("/storyboard"), json={"storyboard": sb, "base_rev": st["rev"]})
        assert r.status_code == 200, r.text
        return r.json()["rev"]


# ----------------------------------------------------------------------------------------------------------- fixtures
@pytest.fixture()
def sb_proj(proj):
    """The synthetic project with a saved storyboard (two chapters, six content shots, a chapter card)."""
    from bti.draft.compile import compile_specs
    inp = load_inputs(proj)
    res = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False)
    assert not res.errors
    (proj / "storyboard.json").write_text(json.dumps(res.storyboard, indent=1), encoding="utf-8")
    return proj


@pytest.fixture()
def env(sb_proj, tmp_path, monkeypatch):
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(tmp_path / "run" / "settings.json"))
    # no `git status` of the comic repository from a test: a server.json without it
    cfg = tmp_path / "server.json"
    cfg.write_text("{}", encoding="utf-8")
    import bti.longjob.config as lcfg
    monkeypatch.setattr(lcfg, "CONFIG_PATH", cfg)
    mock.clear_canned()
    global_mgr.configure(projects_root=sb_proj.parent)
    app = create_app(projects_root=sb_proj.parent)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.put("/api/settings/models", json={"edit.fast": "mock"})
    assert r.status_code == 200, r.text
    e = Env(client, sb_proj)
    yield e
    mock.clear_canned()
    act = global_mgr.active(e.pid, "draft")
    if act:                                                  # a test that failed in the middle must not leave a job behind
        global_mgr.cancel(act["id"])
        global_mgr.wait(act["id"], timeout=30)


@pytest.fixture()
def held(monkeypatch):
    return HeldModel(monkeypatch)


# ----------------------------------------------------------------------------------------------------------- (a)
def test_a_fast_two_shots_applied_then_undone(env):
    ids = env.content_ids("c01")[:2]
    assert len(ids) == 2
    before = env.saved()
    rev0 = env.rev()
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"technique": "CAM-03"}, ids[1]: {"note": "slow look at the mirror"}})])

    job, turn = env.run_edit("zoom chậm hơn vào hai cảnh đầu", ids, mode="fast")

    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied", turn
    assert turn["path"] == "fast" and turn["escalated"] is False
    assert turn["summary"] == "Đã đổi hai cảnh theo yêu cầu."
    assert turn["before_rev"] == rev0
    after = env.saved()
    rev1 = env.rev()
    assert rev1 != rev0 and turn["after_rev"] == rev1                    # the page reads the same revision the editor uses
    # only the two shots differ
    b = {s["id"]: s for s in before["shots"]}
    a = {s["id"]: s for s in after["shots"]}
    assert list(a) == list(b)                                           # no shot added or removed, same order
    changed = {sid for sid in a if a[sid] != b[sid]}
    assert changed == set(ids), changed
    for sid in ids:
        assert a[sid]["source"] == "agent"
    assert a[ids[0]]["technique"] == "CAM-03" and a[ids[1]]["note"] == "slow look at the mirror"
    assert {c["shot_id"] for c in turn["changes"]} == set(ids)
    assert all(c["op"] == "changed" and c["what"] for c in turn["changes"])
    assert turn["has_undo"] is True

    # undo through the route
    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "undone"
    assert r.json()["rev"] == r.json()["after_rev"] == env.rev()          # the shapes of FIX_A_core.md section 10 (rev and after_rev)
    assert env.turn(turn["id"])["status"] == "undone"
    assert env.saved() == before
    assert env.rev() == rev0


# ----------------------------------------------------------------------------------------------------------- (b)
def test_b_fast_cannot_is_no_change(env):
    ids = env.content_ids("c01")[:1]
    rev0 = env.rev()
    raw0 = (env.pdir / "storyboard.json").read_bytes()
    mock.set_canned([json.dumps({"result": "cannot", "summary": "", "reason": "Cần một bức tranh mới, dự án chưa có."}, ensure_ascii=False)])

    job, turn = env.run_edit("thêm bức tranh của họa sĩ khác", ids, mode="fast")

    assert job["state"] == "done", why(job)
    assert turn["status"] == "no_change", turn
    assert "Cần một bức tranh mới" in turn["summary"]                    # the owner sees why
    assert turn["path"] == "fast"
    assert env.rev() == rev0 and (env.pdir / "storyboard.json").read_bytes() == raw0
    assert env.client.get(env.u("/draft")).json()["last_run"] is None    # E12: an edit never writes the draft's last run


# ----------------------------------------------------------------------------------------------------------- (c)
ESCALATE = {"result": "escalate", "summary": "", "reason": "Cần nhìn vào chi tiết trên tranh, chưa có vùng nào cho nó."}


def test_c_fast_escalate_with_mode_fast_does_not_run_deep(env, fake):
    ids = env.content_ids("c01")[:1]
    rev0 = env.rev()
    mock.set_canned([json.dumps(ESCALATE, ensure_ascii=False)])

    job, turn = env.run_edit("zoom sát chiếc nhẫn", ids, mode="fast")

    assert turn["status"] in ("failed", "no_change"), turn
    assert "Cần nhìn vào chi tiết" in turn["summary"]
    assert turn["path"] == "fast" and turn["escalated"] is False
    assert fake.calls() == []                                            # agy was never started
    assert env.rev() == rev0


def test_c_fast_escalate_with_mode_auto_starts_the_deep_path(env, fake):
    ids = env.content_ids("c01")[:2]
    rev0 = env.rev()
    mock.set_canned([json.dumps(ESCALATE, ensure_ascii=False)])
    env.deep_cfg(fake.dir, {ids[0]: {"note": "close on the ring"}},
                 notes_json={"summary": "Đã zoom sát chiếc nhẫn.", "changes": [{"shot": ids[0], "what": "Zoom sát chi tiết."}]})

    job, turn = env.run_edit("zoom sát chiếc nhẫn", ids, mode="auto")

    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied", turn
    assert turn["path"] == "deep" and turn["escalated"] is True
    assert len(fake.calls()) == 1                                        # the deep run happened, once
    assert env.rev() != rev0
    assert env.saved()["shots"][[s["id"] for s in env.saved()["shots"]].index(ids[0])]["note"] == "close on the ring"


# ----------------------------------------------------------------------------------------------------------- (d)
def test_d_manual_save_of_another_shot_while_the_job_waits_is_merged(env, held):
    ids = env.content_ids("c01")[:2]
    other = env.content_ids("c02")[0]
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": "agent note"}})])
    r = env.post_edit("sửa cảnh đầu", ids, mode="fast")
    assert r.status_code == 200, r.text
    assert held.entered.wait(30), "the job never reached the model"

    def touch(sb):
        next(s for s in sb["shots"] if s["id"] == other)["note"] = "owner note"
    env.manual_save(touch)
    held.release.set()

    job = env.wait_job(r.json()["job_id"])
    turn = env.turn(r.json()["turn_id"])
    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied", turn
    by_id = {s["id"]: s for s in env.saved()["shots"]}
    assert by_id[ids[0]]["note"] == "agent note" and by_id[ids[0]]["source"] == "agent"
    assert by_id[other]["note"] == "owner note"                          # the owner's save is still there
    assert env.rev() == turn["after_rev"]


# ----------------------------------------------------------------------------------------------------------- (e)
def _conflict(env, held):
    ids = env.content_ids("c01")[:2]
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": "agent note"}})])
    r = env.post_edit("sửa cảnh đầu", ids, mode="fast")
    assert r.status_code == 200, r.text
    assert held.entered.wait(30), "the job never reached the model"

    def touch(sb):
        next(s for s in sb["shots"] if s["id"] == ids[0])["note"] = "owner note"
    owner_rev = env.manual_save(touch)
    held.release.set()
    job = env.wait_job(r.json()["job_id"])
    turn = env.turn(r.json()["turn_id"])
    assert job["state"] == "done", why(job)
    assert turn["status"] == "needs_choice", turn
    assert turn["conflicts"], turn
    assert env.rev() == owner_rev                                        # nothing was written
    return ids, turn, owner_rev


def test_e_needs_choice_then_resolve_overwrite(env, held):
    ids, turn, _ = _conflict(env, held)
    other = env.content_ids("c02")[0]
    # the owner also changes an unrelated shot while the turn waits for the choice: overwrite must not drop it
    env.manual_save(lambda sb: next(s for s in sb["shots"] if s["id"] == other).update(note="owner note elsewhere"))

    r = env.client.post(env.u("/draft/edit/%s/resolve" % turn["id"]), json={"action": "overwrite"})

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "applied"
    assert r.json()["rev"] == r.json()["after_rev"] == env.rev()
    by_id = {s["id"]: s for s in env.saved()["shots"]}
    assert by_id[ids[0]]["note"] == "agent note" and by_id[ids[0]]["source"] == "agent"
    assert by_id[other]["note"] == "owner note elsewhere"
    t = env.turn(turn["id"])
    assert t["status"] == "applied" and t["after_rev"] == env.rev() and t["has_undo"] is True


def test_e_needs_choice_then_resolve_discard(env, held):
    ids, turn, owner_rev = _conflict(env, held)
    r = env.client.post(env.u("/draft/edit/%s/resolve" % turn["id"]), json={"action": "discard"})
    assert r.status_code == 200, r.text
    assert env.turn(turn["id"])["status"] == "cancelled"
    assert env.rev() == owner_rev
    assert {s["id"]: s for s in env.saved()["shots"]}[ids[0]]["note"] == "owner note"
    # a turn that is not waiting for a choice cannot be resolved again
    assert env.client.post(env.u("/draft/edit/%s/resolve" % turn["id"]), json={"action": "overwrite"}).status_code == 409


# ----------------------------------------------------------------------------------------------------------- (f)
def test_f_deep_one_chapter_with_the_fake_agy(env, fake):
    ids = env.content_ids("c01")
    rev0 = env.rev()
    before = env.saved()
    env.deep_cfg(fake.dir, {ids[0]: {"note": "slower push-in"}},
                 notes_json={"summary": "Đã làm chậm cú đẩy máy ở cảnh đầu.", "changes": [{"shot": ids[0], "what": "Đẩy máy chậm hơn."}]})

    job, turn = env.run_edit("làm chậm cú đẩy máy trong chương này", chapter="c01", mode="deep")

    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied", turn
    assert turn["path"] == "deep" and turn["escalated"] is False
    assert turn["summary"] == "Đã làm chậm cú đẩy máy ở cảnh đầu."
    assert turn["conversation_id"] == "conv-1"
    assert turn["scope"]["kind"] == "chapter" and turn["scope"]["chapter"] == "c01"
    after = env.saved()
    b, a = {s["id"]: s for s in before["shots"]}, {s["id"]: s for s in after["shots"]}
    assert {sid for sid in a if a[sid] != b[sid]} == {ids[0]}
    assert a[ids[0]]["note"] == "slower push-in" and a[ids[0]]["source"] == "agent"
    assert turn["after_rev"] == env.rev() != rev0
    assert [c["shot_id"] for c in turn["changes"]] == [ids[0]]
    # and it can be undone
    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text
    assert env.saved() == before


# ----------------------------------------------------------------------------------------------------------- (g)
def test_g_before_and_after_frames_of_an_applied_turn(env):
    ids = env.content_ids("c01")[:2]
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"technique": "CAM-03"}, ids[1]: {"note": "x"}})])
    _, turn = env.run_edit("đổi hai cảnh", ids, mode="fast")
    assert turn["status"] == "applied", turn
    for when in ("before", "after"):
        for sid in ids:
            r = env.client.get(env.u("/draft/edit/%s/frames/%s/%s.jpg" % (turn["id"], sid, when)))
            assert r.status_code == 200, (when, sid, r.text[:200])
            assert r.headers["content-type"] == "image/jpeg"
            assert r.content[:3] == b"\xff\xd8\xff" and len(r.content) > 500
    assert (turns_dir(env.pdir) / turn["id"] / "before.json").is_file()


# ----------------------------------------------------------------------------------------------------------- more routes
def test_fast_repair_call_through_the_route(env):
    ids = env.content_ids("c01")[:1]
    good = env.edit_answer(ids, {ids[0]: {"note": "after the repair"}}, summary="Đã sửa sau khi chỉnh lại.")
    mock.set_canned(["this is not json at all", good])
    _, turn = env.run_edit("sửa cảnh", ids, mode="fast")
    assert turn["status"] == "applied", turn
    assert len(mock.CALLS) >= 2


def test_fast_failure_leaves_the_storyboard_and_says_why(env):
    ids = env.content_ids("c01")[:1]
    rev0 = env.rev()
    mock.set_canned(["not json", "still not json"])
    job, turn = env.run_edit("sửa cảnh", ids, mode="fast")
    assert job["state"] == "error"
    assert turn["status"] == "failed" and turn["error"], turn
    assert turn["summary"]                                               # one sentence for the owner, not empty
    assert env.rev() == rev0


def test_fast_shot_outside_the_scope_is_refused(env):
    ids = env.content_ids("c01")[:1]
    other = env.content_ids("c02")[0]
    rev0 = env.rev()
    bad = env.edit_answer([ids[0], other], {ids[0]: {"note": "a"}, other: {"note": "b"}})
    mock.set_canned([bad, bad])
    job, turn = env.run_edit("sửa", ids, mode="fast")
    assert turn["status"] == "failed", turn
    assert env.rev() == rev0


def test_edit_with_an_explicit_model_is_used_by_the_fast_path(env):
    ids = env.content_ids("c01")[:1]
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": "n"}})])
    _, turn = env.run_edit("sửa", ids, mode="fast", model="mock")
    assert turn["status"] == "applied", turn
    assert mock.CALLS and mock.CALLS[-1]["model"] == "mock"
    assert turn["model"] == "mock"


def test_deep_run_that_tampers_is_thrown_away(env, fake):
    from bti.editor.common import compute_rev
    ids = env.content_ids("c01")
    rev0 = compute_rev(env.raw())
    env.deep_cfg(fake.dir, {ids[0]: {"note": "must not land"}})
    fake.mode("tamper")
    job, turn = env.run_edit("sửa", chapter="c01", mode="deep")
    assert job["state"] == "error" and job["error_code"] == "draft_tampered", why(job)
    assert turn["status"] == "failed" and turn["error"] == "draft_tampered", turn
    assert compute_rev(env.raw()) == rev0                                # the tampered run changed nothing in the storyboard


def test_deep_without_agy_is_refused_before_a_turn_exists(env, monkeypatch):
    monkeypatch.setenv("BTI_AGY_BIN", "")
    r = env.post_edit("sửa", chapter="c01", mode="deep")
    assert r.status_code == 409 and r.json()["code"] == "agy_missing", r.text
    assert env.thread() == []


def test_escalate_in_auto_without_agy_fails_the_turn_in_words(env, monkeypatch):
    monkeypatch.setenv("BTI_AGY_BIN", "")
    ids = env.content_ids("c01")[:1]
    mock.set_canned([json.dumps(ESCALATE, ensure_ascii=False)])
    job, turn = env.run_edit("zoom sát chiếc nhẫn", ids, mode="auto")
    assert job["state"] == "error", job
    assert turn["status"] == "failed" and turn["error"] == "agy_missing", turn
    assert turn["summary"] and "agy" in turn["summary"]


def test_auto_picks_fast_for_a_small_scope_and_the_turn_says_so_from_the_start(env, held):
    ids = env.content_ids("c01")[:2]
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": "n"}})])
    r = env.post_edit("sửa", ids, mode="auto")
    assert r.status_code == 200, r.text
    assert held.entered.wait(30)
    t = env.turn(r.json()["turn_id"])
    assert t["status"] == "running" and t["path"] == "fast" and t["job_id"] == r.json()["job_id"]
    held.release.set()
    env.wait_job(r.json()["job_id"])
    assert env.turn(r.json()["turn_id"])["status"] == "applied"


def test_a_model_answer_in_a_code_fence_with_words_around_it_is_read(env):
    ids = env.content_ids("c01")[:1]
    answer = "Đây là kết quả:\n```json\n" + env.edit_answer(ids, {ids[0]: {"note": "fenced"}}) + "\n```\nHết."
    mock.set_canned([answer])
    _, turn = env.run_edit("sửa", ids, mode="fast")
    assert turn["status"] == "applied", turn
    assert not mock.CALLS[-1]["retry"]


def test_the_scope_is_said_in_words_for_every_kind_of_scope(env):
    """Contract A5: '2 cảnh đang chọn', 'Chương: <name>', 'Cả video'; never a raw id."""
    ids = env.content_ids("c01")[:2]
    mock.set_canned([json.dumps({"result": "cannot", "reason": "Không làm được."}, ensure_ascii=False)] * 3)
    _, t1 = env.run_edit("sửa", ids, mode="fast")
    _, t2 = env.run_edit("sửa", chapter="c02", mode="fast")
    _, t3 = env.run_edit("sửa", all_=True, mode="fast")
    assert t1["scope_words"] == "2 cảnh đang chọn"
    assert t2["scope_words"] == "Chương: The mirror"
    assert t3["scope_words"] == "Cả video"


def test_a_fast_edit_of_a_whole_chapter_and_the_prompt_carries_the_thread(env):
    ids1 = env.content_ids("c01")[:1]
    mock.set_canned([env.edit_answer(ids1, {ids1[0]: {"note": "first"}}, summary="Đã đổi lần một.")])
    _, t1 = env.run_edit("lần một", ids1, mode="fast")
    assert t1["status"] == "applied", t1
    ids2 = env.content_ids("c01")
    mock.set_canned([env.edit_answer(ids2, {ids2[1]: {"note": "second"}}, summary="Đã đổi lần hai.")])
    _, t2 = env.run_edit("lần hai", chapter="c01", mode="fast")
    assert t2["status"] == "applied", t2
    assert "lần một" in mock.CALLS[-1]["user"] and "Đã đổi lần một." in mock.CALLS[-1]["user"]     # the last turns are in the prompt


def test_a_failed_turn_keeps_a_vietnamese_sentence_for_every_cause(env, monkeypatch):
    """The model is unreachable (a provider error): the turn is failed, with a code the page has a sentence for and one sentence."""
    ids = env.content_ids("c01")[:1]
    rev0 = env.rev()

    def boom(spec, system, user, **kw):
        from bti.script.providers import ProviderError
        raise ProviderError("rate_limit", "rate limit or quota reached (mock)")
    monkeypatch.setattr(mock, "complete", boom)
    job, turn = env.run_edit("sửa", ids, mode="fast")
    assert job["state"] == "error" and job["error_code"] == "agy_rate_limit", why(job)
    assert turn["status"] == "failed" and turn["error"] == "agy_rate_limit" and "Hạn mức" in turn["summary"], turn
    assert env.rev() == rev0


# ----------------------------------------------------------------------------------------------------------- the turn owns only the agent's shots
def _start_held(env, held, ids, note="agent note", instruction="sửa cảnh đầu"):
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": note}})])
    r = env.post_edit(instruction, ids, mode="fast")
    assert r.status_code == 200, r.text
    assert held.entered.wait(30), "the job never reached the model"
    return r


def _finish_held(env, held, r):
    held.release.set()
    job = env.wait_job(r.json()["job_id"])
    assert job["state"] == "done", why(job)
    return env.turn(r.json()["turn_id"])


def _by_id(sb):
    return {s["id"]: s for s in sb["shots"]}


def test_h_the_owners_save_of_another_shot_is_not_the_turns_change_and_undo_keeps_it(env, held):
    a = env.content_ids("c01")[:1]
    b = env.content_ids("c02")[0]
    before = env.saved()
    r = _start_held(env, held, a)
    env.manual_save(lambda sb: next(s for s in sb["shots"] if s["id"] == b).update(note="owner note on B"))
    turn = _finish_held(env, held, r)

    assert turn["status"] == "applied", turn
    assert [c["shot_id"] for c in turn["changes"]] == a, turn["changes"]                     # (a) A only, not B
    now = _by_id(env.saved())
    assert now[a[0]]["note"] == "agent note" and now[b]["note"] == "owner note on B"          # (b) both changes are there
    # the stored `after` is the document that was written, not a later read
    from bti.draft.thread import get_turn_storyboard
    assert strip(get_turn_storyboard(env.pdir, turn["id"], "after"))["shots"] == strip(env.raw())["shots"]

    env.manual_save(lambda sb: sb.update(title="Owner title after the turn"))                 # a top-level part, changed after the turn
    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text                                                      # (c)
    now = _by_id(env.saved())
    assert now[a[0]]["note"] == _by_id(before)[a[0]]["note"]                                  # A is back to before the turn
    assert now[a[0]].get("source") == _by_id(before)[a[0]].get("source")
    assert now[b]["note"] == "owner note on B"                                               # B keeps the owner's change
    assert env.raw().get("title") == "Owner title after the turn"                            # and so does everything else


def test_h_overwrite_after_a_conflict_owns_only_the_conflicting_agent_shot(env, held):
    a = env.content_ids("c01")[:1]
    c = env.content_ids("c02")[1]
    before = env.saved()
    r = _start_held(env, held, a)
    env.manual_save(lambda sb: next(s for s in sb["shots"] if s["id"] == a[0]).update(note="owner note on A"))
    turn = _finish_held(env, held, r)
    assert turn["status"] == "needs_choice", turn
    env.manual_save(lambda sb: next(s for s in sb["shots"] if s["id"] == c).update(note="owner note on C"))   # while the turn waits

    r = env.client.post(env.u("/draft/edit/%s/resolve" % turn["id"]), json={"action": "overwrite"})
    assert r.status_code == 200, r.text
    t = env.turn(turn["id"])
    assert t["status"] == "applied" and [x["shot_id"] for x in t["changes"]] == a, t["changes"]   # (d) A only, not C
    now = _by_id(env.saved())
    assert now[a[0]]["note"] == "agent note" and now[c]["note"] == "owner note on C"

    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text
    now = _by_id(env.saved())
    assert now[a[0]]["note"] == _by_id(before)[a[0]]["note"]
    assert now[c]["note"] == "owner note on C"                                                # C is still the owner's


def test_h_a_shot_added_and_another_deleted_by_the_owner_meanwhile_are_not_the_turns(env, held):
    a = env.content_ids("c01")[:1]
    c02 = env.content_ids("c02")
    split, gone = c02[1], c02[2]
    r = _start_held(env, held, a)

    def owner(sb):
        shots = sb["shots"]
        i = next(k for k, s in enumerate(shots) if s["id"] == split)
        new = copy.deepcopy(shots[i])
        new["id"] = "s0990"
        new["start"] = {"w": new["start"]["w"] + 5, "off": 0.0}
        new["source"] = "user"
        shots.insert(i + 1, new)
        sb["shots"] = [s for s in shots if s["id"] != gone]
    env.manual_save(owner)
    turn = _finish_held(env, held, r)

    assert turn["status"] == "applied", turn                                                   # (e) not a conflict either
    assert [c["shot_id"] for c in turn["changes"]] == a, turn["changes"]
    now = _by_id(env.saved())
    assert "s0990" in now and gone not in now and now[a[0]]["note"] == "agent note"

    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text
    now = _by_id(env.saved())
    assert "s0990" in now and gone not in now                                                  # both survive undo
    assert now[a[0]]["note"] != "agent note"


# ----------------------------------------------------------------------------------------------------------- quota reset time
def test_quota_reset_time_reaches_the_turn_and_the_job_on_the_deep_path(env, fake):
    import re
    ids = env.content_ids("c01")
    env.deep_cfg(fake.dir, {ids[0]: {"note": "never applied"}})
    fake.mode("quota")                                   # canned output of the fake program: "Resets in 2m56s." and an error_code 429 line
    rev0 = env.rev()
    job, turn = env.run_edit("sửa", chapter="c01", mode="deep")
    assert job["state"] == "error" and job["error_code"] == "agy_rate_limit", why(job)
    assert "2 phút 56 giây" in job["error"]
    assert job["meta"]["retry_after_seconds"] == 176 and re.fullmatch(r"\d\d:\d\d", job["meta"]["retry_at"]), job["meta"]
    assert turn["status"] == "failed" and turn["error"] == "agy_rate_limit"
    assert turn["retry_after_seconds"] == 176 and re.fullmatch(r"\d\d:\d\d", turn["retry_at"]), turn
    assert "2 phút 56 giây" in turn["summary"]
    assert len(fake.calls()) == 1                        # never retried inside the job
    assert env.rev() == rev0


def test_quota_reset_time_reaches_the_turn_on_the_fast_path(env, monkeypatch):
    import re
    from bti.script.providers import antigravity
    ids = env.content_ids("c01")[:1]
    calls = []

    def limited(spec, system, user, **kw):
        calls.append(1)
        raise antigravity.classify("Individual quota reached. Resets in 22m20s. error_code 429")
    monkeypatch.setattr(mock, "complete", limited)
    job, turn = env.run_edit("sửa", ids, mode="fast")
    assert job["state"] == "error" and job["error_code"] == "agy_rate_limit", why(job)
    assert job["meta"]["retry_after_seconds"] == 1340
    assert turn["status"] == "failed" and turn["retry_after_seconds"] == 1340 and re.fullmatch(r"\d\d:\d\d|\d\d/\d\d \d\d:\d\d", turn["retry_at"])
    assert "22 phút 20 giây" in turn["summary"]
    assert len(calls) == 1                                # no repair call, no second try


def test_a_quota_without_a_time_says_so_without_inventing_one(env, monkeypatch):
    from bti.script.providers import antigravity
    ids = env.content_ids("c01")[:1]
    monkeypatch.setattr(mock, "complete", lambda *a, **k: (_ for _ in ()).throw(antigravity.classify("429 RESOURCE_EXHAUSTED quota")))
    job, turn = env.run_edit("sửa", ids, mode="fast")
    assert turn["error"] == "agy_rate_limit" and turn["retry_after_seconds"] is None and turn["retry_at"] is None
    assert "Hạn mức" in turn["summary"]
