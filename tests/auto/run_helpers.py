"""Helpers of the automatic-run tests (worker c6auto), in a module of their own so that no test imports `conftest` by name.

`World` is the fake pipeline: the voice, the draft and the export are stood in by REAL long jobs of the app's runner with quick parts, and what they do changes
what the state answer reads (a flag), so a run walks a project through them the way it would for real, in milliseconds. Nothing heavy, paid or model-driven
starts. `Scripted` is a transport with made-up answers for the unit tests of the loop."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO / "tests" / "state", REPO / "tests" / "cli", REPO / "tests" / "picks", REPO / "tests" / "script"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from bti.cli.transport import Reply, Transport  # noqa: E402
from cli_helpers import AppTransport  # noqa: E402,F401  (re-exported for the tests)
from state_helpers import DEMO_SRC, PID, STAGES, make_book_project, make_picks, put_storyboard  # noqa: E402,F401

FINAL = ("done", "error", "cancelled", "interrupted")
P = "/api/projects/%s" % PID


def wait_longjob(c, jid: str, timeout: float = 30.0) -> dict:
    end = time.time() + timeout
    j: dict = {}
    while time.time() < end:
        j = c.get("/api/longjobs/%s" % jid).json()
        if j.get("state") in FINAL:
            return j
        time.sleep(0.03)
    raise AssertionError("the job did not end: %r" % (j,))


def wait_script_job(c, jid: str, timeout: float = 20.0) -> dict:
    end = time.time() + timeout
    j: dict = {}
    while time.time() < end:
        j = c.get("/api/jobs/%s" % jid).json()
        if j.get("state") in ("done", "error", "cancelled"):
            return j
        time.sleep(0.03)
    raise AssertionError(j)


def set_auto(c, pid: str = PID, **change) -> dict:
    rev = c.get("/api/projects/%s/auto" % pid).json()["rev"]
    r = c.put("/api/projects/%s/auto" % pid, json={"base_rev": rev, **change})
    assert r.status_code == 200, r.text
    return r.json()


def state(c, pid: str = PID) -> dict:
    return c.get("/api/projects/%s/state" % pid).json()


def start_run(c, pid: str = PID, **body) -> dict:
    r = c.post("/api/projects/%s/auto/run" % pid, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def finish_run(c, started: dict, pid: str = PID, timeout: float = 60.0) -> tuple[dict, dict]:
    """(the ended job, the run record) of a run started with `start_run`."""
    job = wait_longjob(c, started["job_id"], timeout)
    run = c.get("/api/projects/%s/auto/runs/%s" % (pid, started["run_id"])).json()
    return job, run


def run_to_end(c, pid: str = PID, **body) -> tuple[dict, dict]:
    return finish_run(c, start_run(c, pid, **body), pid)


def actions_of(run: dict) -> list[str]:
    return [s["action"] for s in run["steps"]]


class World:
    """The project `arn` and the fakes of its heavy steps. `flags` say what has been made; `calls` lists every start the fakes were asked for."""

    def __init__(self, c, monkeypatch, delay: float = 0.04):
        import bti.draft.run as draft_run
        import bti.draft.review as viewer_review
        import bti.editor.jobs as jobs_mod
        import bti.export.run as export_run
        import bti.voice.run as voice_run
        from bti.library import projects as projects_mod
        from bti.picks import service
        self.c, self.delay, self.pid = c, delay, PID
        self.flags = {"voice": False, "draft": False, "export": False, "picks_ok": False}
        self.calls: list[str] = []
        self.fail: dict[str, tuple[str, str]] = {}          # kind -> (code, sentence): that job fails
        self.hold: dict[str, float] = {}                    # kind -> seconds that job takes (cancel-aware)
        self.proposal = "draft_20261118-120000"
        real = projects_mod.stage_states

        def stood_in(d):
            out = real(d)
            if self.flags["voice"]:
                out["voice"] = {"state": "done", "detail": "Giọng đọc đã xong."}
            if self.flags["export"]:
                out["export"] = {"state": "done", "detail": "Đã xuất video."}
            return out
        monkeypatch.setattr(projects_mod, "stage_states", stood_in)
        monkeypatch.setattr(draft_run, "readiness", lambda d: {"voice": {"ok": self.flags["voice"]}, "picks": {"ok": self.flags["picks_ok"]},
                                                                "ok": self.flags["voice"] and self.flags["picks_ok"]})
        monkeypatch.setattr(draft_run, "state", lambda d: ({"state": "done", "detail": "Đã có bản nháp.", "proposal": self.proposal} if self.flags["draft"]
                                                           else {"state": "none", "detail": "Chưa có bản nháp.", "proposal": None}))
        monkeypatch.setattr(voice_run, "start", lambda d, pid, *a, **k: self._job("voice", d, pid, lambda: self.flags.update(voice=True)))
        monkeypatch.setattr(draft_run, "start", lambda pid, d, *a, **k: self._job("draft", d, pid, self._write_proposal))
        monkeypatch.setattr(viewer_review, "start", lambda pid, d, *a, **k: self._job("draft", d, pid, self._write_review, record="review"))
        monkeypatch.setattr(export_run, "start", lambda d, *a, **k: self._job("export", d, Path(d).name, lambda: self.flags.update(export=True)))
        monkeypatch.setattr(jobs_mod, "render_preview", lambda *a, **k: "/api/projects/x/files/cache/previews/p.mp4")
        monkeypatch.setattr(service, "search", lambda *a, **k: {"items": [], "errors": []})

    # ---- the fake long jobs
    def _clean(self, sb: dict) -> dict:
        """The demo storyboard made clean for the stub engine (its warnings carry no code): the project name is this project's, and every picture file exists."""
        d = self.c.root / self.pid
        sb["project"] = self.pid
        for a in sb.get("assets", {}).values():
            f = d / a["file"]
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"x" * 16)
        if isinstance(sb.get("audio"), str):
            (d / sb["audio"]).parent.mkdir(parents=True, exist_ok=True)
            (d / sb["audio"]).write_bytes(b"x" * 64)
        return sb

    def _write_proposal(self) -> None:
        d = self.c.root / self.pid
        (d / "proposals").mkdir(exist_ok=True)
        sb = self._clean(json.loads((DEMO_SRC / "storyboard.json").read_text(encoding="utf-8")))
        (d / "proposals" / (self.proposal + ".json")).write_text(
            json.dumps({"storyboard": sb, "author": "agent:mock", "created_at": "2026-11-18T12:00:00", "summary": "draft"}), encoding="utf-8")
        import shutil
        shutil.copy(DEMO_SRC / "timing.json", d / "timing.json")
        self.flags["draft"] = True

    def _write_review(self) -> None:
        from bti.draft.review import save_report
        from bti.editor.common import compute_rev
        d = self.c.root / self.pid
        sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
        save_report(d, {"revision": compute_rev(sb), "rounds": 0, "history": [], "warnings": []})

    def _job(self, kind: str, d, pid: str, effect, *, record=None) -> dict:
        from bti.longjob import Part, PartError, manager
        self.calls.append(record or kind)
        seconds = self.hold.get(record or kind, self.delay)

        def run(ctx):
            end = time.time() + seconds
            while time.time() < end:
                if ctx.cancelled():
                    return None
                ctx.progress(0.5, "fake %s" % kind)
                time.sleep(0.01)
            if ctx.cancelled():
                return None
            if kind in self.fail:
                raise PartError(*self.fail[kind])
            effect()
            return {"fixture": kind}
        return manager.start(kind=kind, pid=pid, project_dir=Path(d), parts=[Part(key="p1", title="Phần giả", run=run, est_seconds=1)])

    def put_storyboard(self) -> None:
        """The demo project's storyboard as this project's first one, made clean for the stub engine."""
        d = self.c.root / self.pid
        put_storyboard(self.c, self.pid)
        sb = self._clean(json.loads((d / "storyboard.json").read_text(encoding="utf-8")))
        (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")

    # ---- stages
    def build(self, stage: str) -> str:
        """Bring the fresh book project to `stage` (one of tests/state/state_helpers.STAGES) with the real routes and the mock model."""
        c, pid = self.c, self.pid
        make_book_project(c.root)
        i = STAGES.index(stage)
        if i >= 1:
            r = c.post(P + "/outline/generate", json={})
            assert r.status_code == 200, r.text
            assert wait_script_job(c, r.json()["job_id"])["state"] == "done"
        if i >= 2:
            assert c.post(P + "/outline/approve", json={"rev": c.get(P + "/outline").json()["rev"]}).status_code == 200
            r = c.post(P + "/narration/generate", json={})
            assert r.status_code == 200, r.text
            assert wait_script_job(c, r.json()["job_id"])["state"] == "done"
            assert c.post(P + "/narration/approve", json={"rev": c.get(P + "/narration").json()["rev"]}).status_code == 200
        if i >= 3:
            self.flags["voice"] = True
        if i >= 4:
            make_picks(c, pid)
            self.flags["picks_ok"] = True
        if i == 5:
            self._write_proposal()
        if i >= 6:
            self.put_storyboard()
        if i >= 7:
            assert c.post(P + "/approve", json={"rev": c.get(P).json()["rev"]}).status_code == 200
        if i >= 8:
            self.flags["export"] = True
        return pid


class Scripted(Transport):
    """A transport with made-up answers for the unit tests of the loop: GET .../state answers the states in order (the last repeats), a GET of a document
    answers its entry of `docs`, a job path answers the records of `jobs[path]` in order, a POST answers `posts[(path)]` (a Reply, or a list of them)."""

    def __init__(self, project: str, states: list[dict], *, docs: dict | None = None, jobs: dict | None = None, posts: dict | None = None):
        self.pid, self.states, self.docs, self.jobs, self.posts = project, list(states), dict(docs or {}), {k: list(v) for k, v in (jobs or {}).items()}, dict(posts or {})
        self.log: list[tuple[str, str, object]] = []

    def request(self, method, path, body=None, timeout=60.0):
        self.log.append((method, path, body))
        if method == "GET" and path == "/api/projects/%s/state" % self.pid:
            return Reply(200, self.states.pop(0) if len(self.states) > 1 else self.states[0])
        if method == "GET" and path in self.docs:
            return Reply(200, self.docs[path])
        if method == "GET" and path in self.jobs:
            q = self.jobs[path]
            return Reply(200, q.pop(0) if len(q) > 1 else q[0])
        if method == "POST" and path in self.posts:
            r = self.posts[path]
            r = r.pop(0) if isinstance(r, list) and len(r) > 1 else (r[0] if isinstance(r, list) else r)
            return r(body) if callable(r) else r
        if method == "POST" and path.endswith("/cancel"):
            return Reply(200, {"state": "cancelled"})
        return Reply(404, {"detail": "no such route in the script: %s %s" % (method, path), "code": "route_not_found", "fix": "x", "retry": "no"})

    def paths(self, method: str | None = None) -> list[str]:
        return [p for m, p, _ in self.log if method is None or m == method]


# ---- made-up states
STEPS = [("artwork", "Tác phẩm"), ("script", "Kịch bản"), ("voice", "Giọng đọc"), ("picks", "Chọn hình"), ("edit", "Dựng hình"), ("export", "Xuất video")]


def act(aid: str, step: str, *, ready: bool = True, advances: bool = True, gate: bool = False, auto_ok: bool = True, cost=None, body="__none__", needs=None,
        long_job: bool = False, fill=None, label: str | None = None, pid: str = "arn", agent=None) -> dict:
    out = {"id": aid, "step": step, "label": label or aid, "method": "POST", "path": "/api/projects/%s/%s" % (pid, aid.replace(".", "/")),
           "body": {} if body == "__none__" else body, "ready": ready and not needs, "needs": list(needs or []), "gate": gate, "auto_ok": auto_ok, "long_job": long_job,
           "uses_model": False, "agent": agent, "cost": cost, "advances": advances and ready and not needs}
    if long_job:
        out["follow"] = "GET /api/longjobs/{job_id}"
    if fill:
        out["fill"], out["body_template"] = fill, {}
    return out


def made_state(actions: list[dict], *, done: tuple[str, ...] = ("artwork",), current: str = "script", auto: dict | None = None, jobs=None, pid: str = "arn",
               problems=None) -> dict:
    return {"project": pid, "stage": "x", "current": current,
            "steps": [{"step": s, "label": l, "state": "done" if s in done else ("current" if s == current else "locked"), "page_state": "x", "detail": "d-" + s,
                       "blocked_by": None, "problem": None} for s, l in STEPS],
            "next_actions": actions, "jobs": list(jobs or []), "problems": list(problems or []),
            "auto": auto or {"enabled": True, "gates": {g: True for g in ("outline", "narration", "picks", "storyboard")}, "spend": {"model": True, "machine_time": True, "paid": False}},
            "approvals": {}}
