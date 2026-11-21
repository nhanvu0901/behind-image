"""Edit by instruction, end to end through the HTTP routes (contract A2 to A4), on the synthetic project.

Why this file exists: the unit tests of `merge` and `run` call the pieces one by one, or call `draft_run.start` with test-only hooks, so the
real route `POST /api/projects/{pid}/draft/edit` never reached the real functions. Everything here goes through the app (`create_app` and
the test client): `POST /draft/edit`, the long-job route until the job ends, `GET /draft/thread`, the storyboard routes, `resolve`, `undo`.
NOTHING of `bti.draft` is replaced.

Since worker c2box the fast path answers with typed operations and its tests are in `test_box_storyboard.py` (on the fixture project of
`tests/ops`); the slow path writes through the same door and its tests are in `test_box_slow.py`. What stays here is what the two share:
the plumbing of the job and the thread, the quota messages, the tampering guard, and the slow path on the synthetic project.

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

    def edit_answer(self, ids: list[str], overrides: dict | None = None, summary: str = "Đã đổi cách dựng của cảnh đầu.") -> str:
        """A good answer of the fast path in the CURRENT contract (typed operations): the first shot of `ids` takes another core treatment."""
        sb = self.saved()
        first = next(s for s in sb["shots"] if s["id"] == ids[0])
        tech = "CAM-03" if first["technique"] != "CAM-03" else "CAM-01"
        return json.dumps({"status": "applied", "summary": summary, "reason": "", "ops": [{"op": "set_technique", "shot": ids[0], "technique": tech}]},
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
def test_f_deep_one_chapter_with_the_fake_agy(env, fake):
    """The slow path writes through the typed operations: ONE batch of `replace_range` (change log, actor, note, undo)."""
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
    assert turn["limits"] == {"minutes": 30, "repairs": 2, "part_minutes": 35}               # told to the card when the slow path starts
    after = env.saved()
    b, a = {s["id"]: s for s in before["shots"]}, {s["id"]: s for s in after["shots"]}
    new = [sid for sid in a if sid not in b]
    assert len(new) == 1 and ids[0] not in a                                                  # the shot was replaced by a new one (a new id)
    assert a[new[0]]["note"] == "slower push-in" and a[new[0]]["source"] == "agent"
    assert all(a[sid] == b[sid] for sid in a if sid in b)                                    # every other shot is byte for byte the same
    assert turn["after_rev"] == env.rev() != rev0
    # one batch of the change log, with the same actor and note as the fast path
    log = env.client.get(env.u("/changes?doc=storyboard")).json()["changes"]
    assert len(log) == 1 and log[0]["batch"] == turn["batch"] and log[0]["note"] == "làm chậm cú đẩy máy trong chương này"
    assert log[0]["actor"].startswith("agent:") and [o["op"] for o in log[0]["ops"]] == ["replace_range"] and log[0]["ops"][0]["from_shot"] == ids[0]
    assert log[0]["scope"]["shots"]
    assert [c["shot_id"] for c in turn["changes"]] == new and turn["changes"][0]["before_id"] == ids[0] and turn["changes"][0]["after_id"] == new[0]
    assert turn["batch_changes"] and turn["batch_changes"][0]["what"].startswith("Cảnh ")
    # the frames of the card: before the old id, after the new one
    for when in ("before", "after"):
        r = env.client.get(env.u("/draft/edit/%s/frames/%s/%s.jpg" % (turn["id"], new[0], when)))
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg", (when, r.text[:200])
    # and it can be undone through the card's route
    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text
    assert env.saved() == before


# ----------------------------------------------------------------------------------------------------------- (g)
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


def test_the_scope_is_said_in_words_for_every_kind_of_scope(env):
    """Contract A5: '2 cảnh đang chọn', 'Chương: <name>', 'Cả video'; never a raw id."""
    ids = env.content_ids("c01")[:2]
    mock.set_canned([json.dumps({"status": "cannot", "reason": "Không làm được.", "summary": "", "ops": []}, ensure_ascii=False)] * 3)
    _, t1 = env.run_edit("sửa", ids, mode="fast")
    _, t2 = env.run_edit("sửa", chapter="c02", mode="fast")
    _, t3 = env.run_edit("sửa", all_=True, mode="fast")
    assert t1["scope_words"] == "2 cảnh đang chọn"
    assert t2["scope_words"] == "Chương: The mirror"
    assert t3["scope_words"] == "Cả video"


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


# ----------------------------------------------------------------------------------------------------------- fast path v2: only changed shots, owner words, no leaked defaults
def test_n_the_deep_paths_change_list_gets_the_same_treatment(env, fake):
    ids = env.content_ids("c01")
    env.deep_cfg(fake.dir, {ids[0]: {"note": "slower push-in"}},
                 notes_json={"summary": "Slowed the push-in of s0001.", "changes": [{"shot": ids[0], "what": "Camera easing changed."}]})
    _, turn = env.run_edit("làm chậm", chapter="c01", mode="deep")
    assert turn["status"] == "applied", turn
    assert turn["summary"] == "Đã sửa 1 cảnh: Đổi ghi chú của cảnh." and turn["summary_source"] == "code"
    assert turn["changes"][0]["what"] == "Đổi ghi chú của cảnh." and turn["changes"][0]["what_source"] == "code"

