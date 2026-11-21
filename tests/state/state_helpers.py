"""Builders of the project stages the state tests look at, made with the real routes and files wherever a test can do it cheaply:
the outline and the narration through the mock model, the picks through picks.json and its approval route, the storyboard from the
demo project's file. Two things are stood in for, as the stage packages' own tests cover them: the voice and the export state
(`stage_states`), and the readiness the draft reads from timing.json (`bti.draft.run.readiness`)."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT_SRC = REPO / "projects" / "arnolfini-from-books"
DEMO_SRC = REPO / "projects" / "demo_stub"
PID = "arn"

STAGES = ["new", "outline_waiting", "narration_approved", "voiced", "picks_approved", "proposal_waiting", "drafted",
          "storyboard_approved", "exported"]


def route_ok(app, method: str, path: str) -> bool:
    """Whether the app has a route of its own for `method` and the concrete `path` (the static catch-all does not count)."""
    from starlette.routing import Match
    scope = {"type": "http", "method": method, "path": path, "root_path": "", "query_string": b"", "headers": []}
    return any(r.matches(scope)[0] == Match.FULL for r in app.router.routes if getattr(r, "path", None) != "/{path:path}")


def ids(state: dict) -> list[str]:
    return [a["id"] for a in state["next_actions"]]


def action(state: dict, aid: str) -> dict:
    return next(a for a in state["next_actions"] if a["id"] == aid)


def wait_job(c, jid: str, timeout: float = 20.0) -> dict:
    end = time.time() + timeout
    j = {}
    while time.time() < end:
        j = c.get(f"/api/jobs/{jid}").json()
        if j.get("state") in ("done", "error", "cancelled"):
            return j
        time.sleep(0.03)
    raise AssertionError(j)


def make_book_project(root: Path, pid: str = PID) -> Path:
    """A project made from a book, with nothing done yet (the sample project without its script)."""
    shutil.copytree(SCRIPT_SRC, root / pid, ignore=shutil.ignore_patterns("script", "cache", "history"))
    return root / pid


def make_picks(c, pid: str = PID) -> None:
    """picks.json with a main painting, approved through the route (the narration must be approved)."""
    from bti.picks import doc
    from picks_helpers import png_bytes
    d = c.root / pid
    (d / "media").mkdir(exist_ok=True)
    (d / "media" / "main.png").write_bytes(png_bytes(120, 160))
    pd = {"schema": doc.SCHEMA, "main_asset": "MAIN", "beats": {}, "approval": {"approved": False},
          "assets": {"MAIN": {"file": "media/main.png", "kind": "image", "title": "The Arnolfini Portrait", "artist": "Jan Van Eyck",
                              "year": "1434", "width": 120, "height": 160, "regions": {},
                              "credit": {"source": "commons", "source_url": "u", "author": "x", "licence": "PD", "flag": None}}}}
    doc.save(d, pd)
    rev = doc.revision(doc.load(d))
    r = c.post(f"/api/projects/{pid}/picks/approve", json={"rev": rev})
    assert r.status_code == 200, r.text


def put_storyboard(c, pid: str = PID, audio: bool = True) -> None:
    """The demo project's storyboard and timing as this project's first storyboard (no approval)."""
    d = c.root / pid
    sb = json.loads((DEMO_SRC / "storyboard.json").read_text(encoding="utf-8"))
    sb["approvals"] = {"storyboard": None}
    (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    shutil.copy(DEMO_SRC / "timing.json", d / "timing.json")
    if audio:
        (d / "audio").mkdir(exist_ok=True)
        (d / "audio" / "narration.m4a").write_bytes(b"x" * 64)


def build(stage: str, c, monkeypatch, pid: str = PID) -> str:
    """Bring the project `pid` (a fresh book project) to `stage`. Returns pid."""
    from bti.draft import run as draft_run
    from bti.library import projects as projects_mod
    P = f"/api/projects/{pid}"
    if stage == "new":
        return pid
    r = c.post(P + "/outline/generate", json={})
    assert r.status_code == 200, r.text
    assert wait_job(c, r.json()["job_id"])["state"] == "done"
    if stage == "outline_waiting":
        return pid
    o = c.get(P + "/outline").json()
    assert c.post(P + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    r = c.post(P + "/narration/generate", json={})
    assert r.status_code == 200, r.text
    assert wait_job(c, r.json()["job_id"])["state"] == "done"
    n = c.get(P + "/narration").json()
    assert c.post(P + "/narration/approve", json={"rev": n["rev"]}).status_code == 200
    if stage == "narration_approved":
        return pid
    flags = {"export": False}
    real = projects_mod.stage_states

    def stood_in(d):
        out = real(d)
        out["voice"] = {"state": "done", "detail": "Giọng đọc đã xong."}
        if flags["export"]:
            out["export"] = {"state": "done", "detail": "Đã xuất video."}
        return out
    monkeypatch.setattr(projects_mod, "stage_states", stood_in)
    ready = {"voice": {"ok": True}, "picks": {"ok": False}}
    monkeypatch.setattr(draft_run, "readiness", lambda d: {**ready, "ok": ready["voice"]["ok"] and ready["picks"]["ok"]})
    if stage == "voiced":
        return pid
    make_picks(c, pid)
    ready["picks"]["ok"] = True
    if stage == "picks_approved":
        return pid
    if stage == "proposal_waiting":
        (c.root / pid / "proposals").mkdir()
        sb = json.loads((DEMO_SRC / "storyboard.json").read_text(encoding="utf-8"))
        (c.root / pid / "proposals" / "draft_20261118-120000.json").write_text(
            json.dumps({"storyboard": sb, "author": "agent:mock", "created_at": "2026-11-18T12:00:00", "summary": "draft"}), encoding="utf-8")
        shutil.copy(DEMO_SRC / "timing.json", c.root / pid / "timing.json")
        monkeypatch.setattr(draft_run, "state", lambda d: {"state": "done", "detail": "Đã có bản nháp.", "proposal": "draft_20261118-120000"})
        return pid
    put_storyboard(c, pid)
    if stage == "drafted":
        return pid
    rev = c.get(P).json()["rev"]
    r = c.post(P + "/approve", json={"rev": rev})
    assert r.status_code == 200, r.text
    if stage == "storyboard_approved":
        return pid
    flags["export"] = True
    return pid
