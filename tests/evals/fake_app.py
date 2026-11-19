"""A fake app for the drivers that no real route of this checkout serves yet (the pictures agent, the edit of the picks) and for the draft and the edit by words without
a model: it reads and writes the COPY of the sample project the bench made (a folder in the projects root), answers the routes the drivers call, and does what its
`behaviour` says the agent does. It is a Transport, so the bench talks to it as to the app."""
import copy
import json
import re
from pathlib import Path

from bti.cli.transport import Reply, Transport


class FakeApp(Transport):
    def __init__(self, root: Path, behaviour: str = "good", actions: dict | None = None):
        self.root, self.behaviour, self.log = Path(root), behaviour, []
        self.actions = actions if actions is not None else {}         # id -> the dict of the state answer (listed actions)
        self.jobs: dict[str, dict] = {}
        self.deleted: list[str] = []
        self.turns: list[dict] = []
        self.agent_of: dict[str, str] = {}

    # ---- helpers
    def d(self, pid: str) -> Path:
        return self.root / pid

    def read(self, pid: str, name: str):
        f = self.d(pid) / name
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None

    def write(self, pid: str, name: str, doc) -> None:
        (self.d(pid) / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def job(self, kind: str, state: str = "done", **kw) -> str:
        jid = "%016x" % (len(self.jobs) + 1)
        self.jobs[jid] = {"id": jid, "kind": kind, "state": state, **kw}
        return jid

    # ---- the transport
    def request(self, method, path, body=None, timeout=60.0):
        self.log.append((method, path, body))
        base, _, query = path.partition("?")
        m = re.match(r"^/api/projects/([a-z0-9_-]+)(/.*)?$", base)
        if base == "/api/agents":
            return Reply(200, {"agents": [{"id": "gem", "label": "Gemini giả", "model": "mock", "available": True, "reason": None},
                                           {"id": "off", "label": "Tắt", "model": "mock-off", "available": False, "reason": "Chưa đăng nhập."}]})
        jm = re.match(r"^/api/(?:longjobs|jobs)/([0-9a-f]{16})$", base)
        if jm:
            j = self.jobs.get(jm.group(1))
            return Reply(200, j) if j else Reply(404, {"detail": "no", "code": "job_not_found"})
        if not m:
            return Reply(404, {"detail": "no route", "code": "route_not_found"})
        pid, rest = m.group(1), m.group(2) or ""
        if method == "DELETE" and rest == "" and query == "confirm=" + pid:
            self.deleted.append(pid)
            return Reply(200, {"ok": True})
        if rest == "/agent":
            if method == "PUT":
                self.agent_of[pid] = body["agent"]
            return Reply(200, {"rev": "r1", "agent": self.agent_of.get(pid), "steps": {}, "effective": {k: {"id": self.agent_of.get(pid) or "gem", "label": "x", "model": "mock", "source": "project"}
                                                                                                          for k in ("script", "picks", "storyboard")}})
        if method == "GET" and rest == "":
            sb, tm = self.read(pid, "storyboard.json"), self.read(pid, "timing.json")
            return Reply(200, {"storyboard": sb, "timing": tm, "issues": [], "rev": "rev-%d" % len(json.dumps(sb or {}))}) if sb else Reply(409, {"detail": "no storyboard", "code": "storyboard_not_found"})
        if method == "GET" and rest == "/state":
            return Reply(200, {"project": pid, "next_actions": list(self.actions.values())})
        if method == "GET" and rest == "/picks":
            picks = self.read(pid, "picks.json") or {"main_asset": None, "assets": {}, "beats": {}}
            return Reply(200, {"picks": picks, "issues": [], "narration": {"beat_ids": sorted(picks.get("beats") or {}) or ["b0001"]}})
        if method == "POST" and rest == "/draft/start":
            return Reply(200, {"job_id": self.job("draft", **({"state": "error", "error_code": "agy_timeout", "error": "Quá giờ."} if self.behaviour == "fails" else {}))})
        if method == "GET" and rest == "/draft":
            return Reply(200, {"state": {"state": "done", "proposal": "p1"}})
        if method == "POST" and rest == "/proposals/p1/apply":
            return Reply(200, {"applied": True})
        if method == "POST" and rest == "/draft/edit":
            return self.edit(pid, body)
        if method == "GET" and rest == "/draft/thread":
            return Reply(200, {"turns": self.turns})
        a = next((x for x in self.actions.values() if x["path"] == base and x["method"] == method), None)
        if a is not None:
            return self.act(pid, a, body)
        return Reply(404, {"detail": "no route %s %s" % (method, rest), "code": "route_not_found"})

    # ---- what the "agent" does
    def edit(self, pid: str, body: dict) -> Reply:
        sb = self.read(pid, "storyboard.json")
        scope = set((body.get("scope") or {}).get("shots") or [])
        status, summary = "applied", "Đã làm chậm chuyển động."
        if self.behaviour == "fails":                       # the agent stopped without an answer: nothing was written
            return Reply(200, {"job_id": self.job("draft", state="error", error_code="agy_timeout", error="Quá giờ."), "turn_id": "t0"})
        if self.behaviour == "cannot":
            status, summary = "cannot", "Dự án chưa có bức tranh này: hãy nhập hình trước."
        else:
            for s in sb["shots"]:
                if s["id"] in scope:
                    for v in s.get("params", {}).values():
                        if isinstance(v, list) and v and isinstance(v[0], dict) and "zoom" in v[0]:
                            v[-1]["zoom"] = round(v[0]["zoom"] + (v[-1]["zoom"] - v[0]["zoom"]) * 0.5, 4)        # half the zoom: slower
                elif self.behaviour == "sloppy" and s["id"] == "s0001":
                    s["note"] = "changed outside the scope"
            self.write(pid, "storyboard.json", sb)
        tid = "t%d" % (len(self.turns) + 1)
        self.turns.append({"id": tid, "status": status, "summary": summary, "notes": "", "error": None})
        return Reply(200, {"job_id": self.job("draft"), "turn_id": tid})

    def act(self, pid: str, a: dict, body) -> Reply:
        picks = self.read(pid, "picks.json") or {"main_asset": "MAIN", "assets": {"MAIN": {"kind": "image", "credit": {"source": "commons", "licence": "PD"}}}, "beats": {}}
        if a["id"] == "picks.auto":
            picks["beats"] = {"b0001": {"items": [{"asset": "MAIN", "region": None}], "status": "picked"}}
        else:
            for b in (body or {}).get("scope", {}).get("beats", []):
                picks["beats"][b] = {"items": [], "status": "skip"}
        self.write(pid, "picks.json", picks)
        return Reply(200, {"job_id": self.job("picks")})
