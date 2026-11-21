"""The prompt box on typed operations, through the app (worker c2box): the fixture project of `tests/ops` (ten shots with a locked one and a locked
overlay, six narration lines, a picks document, four pictures), the mock model with canned answers, and the routes exactly as the page calls them.
Nothing here calls a real model, the network or the owner's folders.

    def test_x(box):
        box.model([box.answer([...ops...])])
        job, turn = box.run_edit("làm vòng sáng to hơn", ["s0002"])
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "tests" / "ops", REPO / "tests" / "picks", REPO / "tests" / "script"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi.testclient import TestClient  # noqa: E402

from bti.script.providers import mock  # noqa: E402
from ops_helpers import PID, make_project, read_json  # noqa: E402

# the registry's own examples apply to this project; the ids below are its own
CAM = {"camera": [{"at": {"rel": 0.0}, "cx": 800, "cy": 500, "zoom": 1.08, "ease": "inout_cubic"},
                  {"at": {"rel": 1.0}, "cx": 800, "cy": 450, "zoom": 1.2, "ease": "inout_cubic"}]}


def ans(ops=None, summary="Vòng sáng ở cảnh này to hơn.", status="applied", reason="") -> str:
    """An answer of the model in the shape of the briefing."""
    return json.dumps({"status": status, "summary": summary, "reason": reason, "ops": ops or []}, ensure_ascii=False)


def set_ring(shot="s0002", overlay="o1", rx=260):
    return {"op": "set_params", "shot": shot, "overlay": overlay, "params": {"rx": rx, "ry": rx}}


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def why(job: dict) -> str:
    """What a failed long job says, for the message of an assert."""
    return "state=%s code=%s error=%s log=%s" % (job.get("state"), job.get("error_code"), job.get("error"), job.get("log_tail"))


class HeldModel:
    """Holds the mock provider's answer until `release` is set; `entered` is set when a call arrives. It wraps the PROVIDER (the stand-in of the
    model), so the time the model takes is under the test's control."""

    def __init__(self, monkeypatch):
        self.entered, self.release = threading.Event(), threading.Event()
        real = mock.complete

        def held(spec, system, user, **kw):
            self.entered.set()
            assert self.release.wait(60), "the test never released the model"
            return real(spec, system, user, **kw)

        monkeypatch.setattr(mock, "complete", held)


class Box:
    def __init__(self, client: TestClient, pdir: Path):
        self.client, self.pdir, self.pid = client, pdir, pdir.name

    # -- plumbing
    def u(self, tail: str = "") -> str:
        return "/api/projects/%s%s" % (self.pid, tail)

    def model(self, answers: list[str]) -> None:
        mock.set_canned(answers)

    def prompts(self) -> list[str]:
        return [c["user"] for c in mock.CALLS]

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

    # -- the documents as the page reads them
    def sb(self) -> dict:
        r = self.client.get(self.u())
        assert r.status_code == 200, r.text
        return r.json()

    def sb_rev(self) -> str:
        return self.sb()["rev"]

    def saved(self) -> dict:
        return strip(self.sb()["storyboard"])

    def shot(self, sid: str, doc: dict | None = None) -> dict:
        return next(s for s in (doc or self.saved())["shots"] if s["id"] == sid)

    def raw_bytes(self, name: str = "storyboard.json") -> bytes:
        return (self.pdir / name).read_bytes()

    def picks(self) -> dict:
        r = self.client.get(self.u("/picks"))
        assert r.status_code == 200, r.text
        return r.json()

    def changes(self, doc: str | None = None) -> list[dict]:
        r = self.client.get(self.u("/changes") + ("?doc=%s" % doc if doc else ""))
        assert r.status_code == 200, r.text
        return r.json()["changes"]

    def log_dir(self) -> Path:
        return self.pdir / "changes"

    def state(self) -> dict:
        r = self.client.get(self.u("/state"))
        assert r.status_code == 200, r.text
        return r.json()

    # -- step 5
    def thread(self) -> list[dict]:
        r = self.client.get(self.u("/draft/thread"))
        assert r.status_code == 200, r.text
        return r.json()["turns"]

    def turn(self, turn_id: str, picks: bool = False) -> dict:
        turns = self.picks_thread() if picks else self.thread()
        return next(t for t in turns if t["id"] == turn_id)

    def post_edit(self, instruction: str, shots=None, *, chapter: str | None = None, all_: bool = False, mode: str = "fast", **extra):
        scope = {"shots": shots} if shots is not None else ({"chapter": chapter} if chapter else {"all": True} if all_ else {})
        body = {"instruction": instruction, "scope": scope, "mode": mode}
        body.update(extra)
        return self.client.post(self.u("/draft/edit"), json=body)

    def run_edit(self, instruction: str, shots=None, **kw) -> tuple[dict, dict]:
        r = self.post_edit(instruction, shots, **kw)
        assert r.status_code == 200, r.text
        body = r.json()
        return self.wait_job(body["job_id"]), self.turn(body["turn_id"])

    def card_undo(self, turn: dict):
        """"Hoàn tác" on the card: the route the page calls."""
        return self.client.post(self.u("/draft/edit/%s/undo" % turn["id"]), json={"force": False})

    # -- step 4
    def picks_thread(self) -> list[dict]:
        r = self.client.get(self.u("/picks/edit/thread"))
        assert r.status_code == 200, r.text
        return r.json()["turns"]

    def post_picks_edit(self, instruction: str, beats=None, *, chapter: str | None = None, all_: bool = False, **extra):
        scope = {"beats": beats} if beats is not None else ({"chapter": chapter} if chapter else {"all": True} if all_ else {})
        body = {"instruction": instruction, "scope": scope}
        body.update(extra)
        return self.client.post(self.u("/picks/edit"), json=body)

    def run_picks_edit(self, instruction: str, beats=None, **kw) -> tuple[dict, dict]:
        r = self.post_picks_edit(instruction, beats, **kw)
        assert r.status_code == 200, r.text
        body = r.json()
        return self.wait_job(body["job_id"]), self.turn(body["turn_id"], picks=True)

    def picks_card_undo(self, turn: dict):
        return self.client.post(self.u("/picks/edit/%s/undo" % turn["id"]), json={})


def make_box(tmp_path, monkeypatch):
    """The app on a copy of the `ops1` fixture project, the mock model for the two boxes, a clean change log."""
    import bti.longjob.config as lcfg
    from bti.editor.app import create_app
    from bti.engine import api as engine_api
    from bti.longjob import manager as global_mgr
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(tmp_path / "run" / "settings.json"))
    cfg = tmp_path / "server.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(lcfg, "CONFIG_PATH", cfg)
    root = tmp_path / "projects"
    root.mkdir()
    pdir = make_project(root)
    mock.clear_canned()
    del mock.CALLS[:]
    global_mgr.configure(projects_root=root)
    app = create_app(projects_root=root, engine_module=engine_api, media_module=None)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.put("/api/settings/models", json={"edit.fast": "mock", "picks": "mock"})
    assert r.status_code == 200, r.text
    box = Box(client, pdir)
    box.app, box.root = app, root
    return box


def cleanup(box: Box) -> None:
    from bti.longjob import manager as global_mgr
    mock.clear_canned()
    act = global_mgr.active(box.pid, "draft")
    if act:                                                  # a test that failed in the middle must not leave a job behind
        global_mgr.cancel(act["id"])
        global_mgr.wait(act["id"], timeout=30)
