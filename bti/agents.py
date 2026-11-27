"""The two agents (Gemini 3.8 Flash, Opus 5.5 High), the choice of one per step, and which model a call of a step uses.
Contract: docs/design/2026-11-18-agent-choice.md.

    config/agent_choices.json    the agents (id, label, model id) and the roles of each step (`BTI_AGENT_CHOICES_FILE` replaces the path:
                                 tests offer a mock agent there). `load_choices()` reads and validates it.
    projects/<pid>/agent.json    the project's choice: {"schema": "bti.agent/1", "agent": id | null, "steps": {step: id}}, written atomically,
                                 with a revision (sha1 of the canonical JSON, the way the script and picks documents compute theirs).
    run/settings.json            key `agent`: the machine's default for projects without a choice (`bti.settings`).

`model_for_project(project_dir, role)` is the ONE function that decides the model of a call of steps 2 to 5, first that applies:
    1. the model named by the request            source "request"
    2. the project's choice for the role's step  "step"
    3. the project's agent                       "project"
    4. the machine's default agent               "default"
    5. `bti.settings.model_for(role)`            "role"
An agent id that the choices file does not list is skipped (the next rule applies) and reported as a warning by `project_view`.
A role that belongs to no step (`library.restore`) only knows rules 1 and 5. Reading a damaged `agent.json` never breaks a call: the
file counts as "no choice".
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bti import settings as S
from bti.fsio import atomic_replace
from bti.script import store as sstore
from bti.script.brief import REPO_ROOT

SCHEMA = "bti.agent/1"
FILE = "agent.json"
ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
SOURCES = ("request", "step", "project", "default", "role")

BUILTIN = {
    "default": "gemini",
    "agents": [
        {"id": "gemini", "label": "Gemini 3.8 Flash", "model": "agy:gemini-3.8-flash-high"},
        {"id": "opus", "label": "Opus 5.5 High", "model": "claude:claude-opus-5-5@high"},
    ],
    "steps": {"script": ["script.outline", "script.narration", "script.title"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"], "music": ["music"]},
}


class AgentError(Exception):
    """A refusal of the agent routes: `code` is the stable word the page translates, `status` the HTTP status."""

    def __init__(self, code: str, message: str, status: int = 422, **extra: Any):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra


# ------------------------------------------------------------------------------------------------ the choices file
@dataclass(frozen=True)
class Agent:
    id: str
    label: str
    model: str


@dataclass(frozen=True)
class Choices:
    default: str
    agents: tuple[Agent, ...]
    steps: dict                       # step id -> tuple of roles
    problems: tuple[str, ...] = ()    # what was wrong in the file (the GET answers carry them as warnings)

    def agent(self, agent_id: Any) -> Agent | None:
        return next((a for a in self.agents if a.id == agent_id), None) if isinstance(agent_id, str) else None

    def for_model(self, model: str | None) -> Agent | None:
        return next((a for a in self.agents if a.model == model), None) if model else None

    def step_of(self, role: str) -> str | None:
        return next((s for s, roles in self.steps.items() if role in roles), None)

    @property
    def ids(self) -> list[str]:
        return [a.id for a in self.agents]


def choices_path() -> Path:
    return Path(os.environ.get("BTI_AGENT_CHOICES_FILE") or (REPO_ROOT / "config" / "agent_choices.json"))


def _builtin(problems: list[str]) -> Choices:
    c = parse_choices(BUILTIN)
    return Choices(c.default, c.agents, c.steps, tuple(problems))


def parse_choices(raw: Any) -> Choices:
    """Validate a decoded choices file. A bad entry is dropped and named in `problems`; with no usable agent the built-in agents are used,
    with no usable step the built-in steps."""
    if not isinstance(raw, dict):
        return _builtin(["the choices file is not an object: the built-in agents are used"])
    problems: list[str] = []
    agents: list[Agent] = []
    for i, a in enumerate(raw.get("agents") if isinstance(raw.get("agents"), list) else []):
        ok = (isinstance(a, dict) and isinstance(a.get("id"), str) and ID_RE.fullmatch(a["id"]) and isinstance(a.get("label"), str)
              and a["label"].strip() and isinstance(a.get("model"), str) and a["model"].strip())
        if not ok:
            problems.append("agent #%d is not {id, label, model}" % (i + 1))
        elif any(x.id == a["id"] for x in agents):
            problems.append("agent id %r is listed twice" % a["id"])
        else:
            agents.append(Agent(a["id"], a["label"].strip()[:60], a["model"].strip()))
    if not agents:
        return _builtin(problems + ["no usable agent: the built-in agents are used"])
    default = raw.get("default")
    if not (isinstance(default, str) and any(a.id == default for a in agents)):
        if default is not None:
            problems.append("default %r is not a listed agent" % (default,))
        default = agents[0].id
    steps: dict[str, tuple[str, ...]] = {}
    seen: set[str] = set()
    raw_steps = raw.get("steps") if isinstance(raw.get("steps"), dict) else None
    if raw_steps is None:
        problems.append("steps are missing: the built-in steps are used")
        raw_steps = BUILTIN["steps"]
    for sid, roles in raw_steps.items():
        if not (isinstance(sid, str) and ID_RE.fullmatch(sid) and isinstance(roles, list)):
            problems.append("step %r is not {id: [roles]}" % (sid,))
            continue
        good = []
        for r in roles:
            if r not in S.ROLES:
                problems.append("step %s names an unknown role %r" % (sid, r))
            elif r in seen:
                problems.append("role %s is in two steps" % r)
            else:
                seen.add(r)
                good.append(r)
        if good:
            steps[sid] = tuple(good)
    if not steps:
        problems.append("no usable step: the built-in steps are used")
        steps = {sid: tuple(roles) for sid, roles in BUILTIN["steps"].items()}
    return Choices(default, tuple(agents), steps, tuple(problems))


def load_choices() -> Choices:
    """The validated choices file; never raises (a missing or unreadable file is the built-in pair, named in `problems`)."""
    p = choices_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _builtin(["%s cannot be read: the built-in agents are used" % p.name])
    return parse_choices(raw)


# ------------------------------------------------------------------------------------------------ availability
def model_availability(model: str, refresh: bool = False) -> dict:
    """{"available", "reason", "reason_code"} of one model id, from what the app already caches: the `agy models` list for `agy:`, the
    Claude Code check (installed and signed in) for `claude:`. It never calls a model. `reason` is the owner's sentence."""
    from bti.script import models as M
    from bti.script.providers import claudecode
    yes = {"available": True, "reason": None, "reason_code": None}
    try:
        if claudecode.is_api_id(model):
            if os.environ.get("BTI_NO_REAL_MODELS") == "1":
                info = claudecode.availability()
                return {"available": False, "reason": info["message"], "reason_code": info["reason"]}
            if not claudecode.api_key():
                return {"available": False, "reason": claudecode.API_KEY_MISSING, "reason_code": "claude_api_key_missing"}
            return yes if claudecode.find_claude() else {"available": False, "reason": claudecode.MISSING_HINT, "reason_code": "not_installed"}
        if claudecode.is_claude_id(model):
            info = M.claude_status(refresh)
            if info.get("ok"):
                return yes
            return {"available": False, "reason": info.get("message") or "Claude Code chưa dùng được trên máy chủ.", "reason_code": info.get("reason")}
        if str(model).startswith("agy:"):
            M.agy_models(refresh)
            spec = M.resolve(model)
            if spec is None:
                return {"available": False, "reason": "Antigravity không có mô hình này trong danh sách của nó.", "reason_code": "model_not_listed"}
            if spec.get("unavailable"):
                return {"available": False, "reason": spec["unavailable"], "reason_code": spec.get("unavailable_kind") or "agy_unavailable"}
            return yes
        spec = M.resolve(model)
        if spec is None:
            return {"available": False, "reason": "Mô hình này không có trong danh sách.", "reason_code": "unknown_model"}
        pub = M.public(spec)
        return yes if pub["enabled"] else {"available": False, "reason": pub["message"] or "Mô hình này chưa dùng được.", "reason_code": "disabled"}
    except Exception:      # noqa: BLE001 - the list of agents can never break a page
        return {"available": False, "reason": "Chưa kiểm tra được agent này.", "reason_code": "unreadable"}


def public_agents(refresh: bool = False) -> dict:
    """GET /api/agents: {agents: [{id, label, model, available, reason, reason_code}], default, machine_default, warnings}."""
    ch = load_choices()
    machine = S.get_machine_agent()
    warnings = [{"code": "choices_file", "message": p} for p in ch.problems]
    if machine is not None and ch.agent(machine) is None:
        warnings.append({"code": "unknown_agent", "where": "machine", "agent": machine,
                         "message": "Agent mặc định của máy (%s) không còn trong danh sách, nên bỏ qua." % machine})
    return {"agents": [{"id": a.id, "label": a.label, "model": a.model, **model_availability(a.model, refresh)} for a in ch.agents],
            "default": ch.default, "machine_default": machine if ch.agent(machine) else None, "warnings": warnings}


def set_machine_default(agent_id: Any) -> dict:
    """PUT /api/settings/agent: store the machine default (None clears it) and answer like `public_agents`."""
    ch = load_choices()
    if agent_id is not None and ch.agent(agent_id) is None:
        raise AgentError("unknown_agent", "unknown agent %r (choose one of: %s)" % (str(agent_id)[:40], ", ".join(ch.ids)), 422, allowed=ch.ids)
    S.set_machine_agent(agent_id)
    return public_agents()


# ------------------------------------------------------------------------------------------------ the project's document
def empty_doc() -> dict:
    return {"schema": SCHEMA, "agent": None, "steps": {}}


def normalize(raw: Any) -> dict:
    doc = empty_doc()
    if isinstance(raw, dict):
        a = raw.get("agent")
        doc["agent"] = a if isinstance(a, str) and a else None
        st = raw.get("steps")
        if isinstance(st, dict):
            doc["steps"] = {k: v for k, v in st.items() if isinstance(k, str) and k and isinstance(v, str) and v}
    return doc


def revision(doc: dict) -> str:
    return sstore.revision(doc)


def project_file(project_dir: Path | str) -> Path:
    return Path(project_dir) / FILE


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock(project_dir: Path | str) -> threading.RLock:
    key = str(Path(project_dir).resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def read_project(project_dir: Path | str | None) -> tuple[dict, str | None]:
    """(the normalised document, a problem sentence or None). No file is no choice; a file that cannot be read or is not an object is
    no choice too, with the problem named (the next choice made through the route replaces it)."""
    if project_dir is None:
        return empty_doc(), None
    try:
        raw = sstore.read_object(project_file(project_dir), "agent")
    except sstore.DocumentCorrupt as e:
        return empty_doc(), str(e)
    return normalize(raw), None


# ------------------------------------------------------------------------------------------------ which model a call uses
@dataclass(frozen=True)
class Resolved:
    model: str
    agent_id: str | None
    label: str
    source: str

    def public(self) -> dict:
        """What a job record, the answer of a start route and the GET route say: {id, label, model, source}."""
        return {"id": self.agent_id, "label": self.label, "model": self.model, "source": self.source}


def label_of_model(model: str, choices: Choices | None = None) -> str:
    """The agent's label for a model id; for a model no agent offers, the model's own label (else the id)."""
    ch = choices or load_choices()
    a = ch.for_model(model)
    if a:
        return a.label
    try:
        from bti.script import models as M
        spec = M.resolve(model)
        if spec and spec.get("label"):
            return str(spec["label"])
    except Exception:      # noqa: BLE001
        pass
    return model


def _resolved(model: str, source: str, ch: Choices) -> Resolved:
    a = ch.for_model(model)
    return Resolved(model, a.id if a else None, a.label if a else label_of_model(model, ch), source)


def _resolve(doc: dict, machine: str | None, ch: Choices, role: str, requested: str | None) -> Resolved:
    if isinstance(requested, str) and requested.strip():
        return _resolved(requested.strip(), "request", ch)
    step = ch.step_of(role)
    if step:
        for source, wanted in (("step", doc["steps"].get(step)), ("project", doc["agent"]), ("default", machine)):
            a = ch.agent(wanted)
            if a:
                return Resolved(a.model, a.id, a.label, source)
    return _resolved(S.model_for(role), "role", ch)


def model_for_project(project_dir: Path | str | None, role: str, requested: str | None = None, *, choices: Choices | None = None) -> Resolved:
    """The model a call of `role` uses for this project (see the module doc for the five rules). `requested` is the model the request
    named, if any. `project_dir` may be None (no project: only the request, the machine's default and the role's setting apply)."""
    ch = choices or load_choices()
    doc, _ = read_project(project_dir)
    return _resolve(doc, S.get_machine_agent(), ch, role, requested)


def _warnings(doc: dict, machine: str | None, ch: Choices, problem: str | None) -> list[dict]:
    out = []
    if problem:
        out.append({"code": "agent_file_unreadable",
                    "message": "Tệp agent.json của dự án không đọc được, nên coi như chưa chọn agent. Chọn lại để ghi tệp mới."})
    if doc["agent"] and ch.agent(doc["agent"]) is None:
        out.append({"code": "unknown_agent", "where": "agent", "agent": doc["agent"],
                    "message": "Agent của dự án (%s) không còn trong danh sách, nên bỏ qua." % doc["agent"]})
    for step, wanted in doc["steps"].items():
        if step in ch.steps and ch.agent(wanted) is None:
            out.append({"code": "unknown_agent", "where": "steps." + step, "agent": wanted,
                        "message": "Agent đã chọn cho bước %s (%s) không còn trong danh sách, nên bỏ qua." % (step, wanted)})
    if machine and ch.agent(machine) is None:
        out.append({"code": "unknown_agent", "where": "machine", "agent": machine,
                    "message": "Agent mặc định của máy (%s) không còn trong danh sách, nên bỏ qua." % machine})
    out.extend({"code": "choices_file", "message": p} for p in ch.problems)
    return out


def project_view(project_dir: Path | str) -> dict:
    """GET /api/projects/{pid}/agent: {rev, agent, steps, effective: {step: {id, label, model, source}}, warnings}."""
    ch = load_choices()
    doc, problem = read_project(project_dir)
    machine = S.get_machine_agent()
    effective = {step: _resolve(doc, machine, ch, roles[0], None).public() for step, roles in ch.steps.items()}
    return {"rev": revision(doc), "agent": doc["agent"], "steps": doc["steps"], "effective": effective,
            "warnings": _warnings(doc, machine, ch, problem)}


_ABSENT = object()


def _quarantine(path: Path) -> None:
    """Move an unreadable agent.json aside (agent.json.corrupt-<time>) so that a new choice never silently overwrites it."""
    try:
        atomic_replace(path, path.with_name("%s.corrupt-%d" % (path.name, int(time.time()))))
    except OSError:
        pass


def update_project(project_dir: Path | str, changes: dict, base_rev: Any) -> dict:
    """PUT /api/projects/{pid}/agent: `changes` holds `agent` and/or `steps` (a key present with null clears that choice, `steps: null`
    clears every step choice, a key left out stays). 422 `unknown_agent` / `unknown_step` / `invalid_payload`, 409 `stale` when `base_rev`
    is not the revision of the saved document (nothing is written). Answers like `project_view`."""
    ch = load_choices()
    if not isinstance(base_rev, str) or not base_rev:
        raise AgentError("invalid_payload", "base_rev (string) is required")
    agent = changes.get("agent", _ABSENT)
    steps = changes.get("steps", _ABSENT)
    if agent is not _ABSENT and agent is not None and ch.agent(agent) is None:
        raise AgentError("unknown_agent", "unknown agent %r (choose one of: %s)" % (str(agent)[:40], ", ".join(ch.ids)), 422, allowed=ch.ids)
    if steps is not _ABSENT and steps is not None:
        if not isinstance(steps, dict):
            raise AgentError("invalid_payload", "steps must be an object {step: agent id | null} or null")
        for step, wanted in steps.items():
            if step not in ch.steps:
                raise AgentError("unknown_step", "unknown step %r (choose one of: %s)" % (str(step)[:40], ", ".join(ch.steps)), 422,
                                 allowed=list(ch.steps))
            if wanted is not None and ch.agent(wanted) is None:
                raise AgentError("unknown_agent", "unknown agent %r (choose one of: %s)" % (str(wanted)[:40], ", ".join(ch.ids)), 422, allowed=ch.ids)
    path = project_file(project_dir)
    with _lock(project_dir):
        doc, problem = read_project(project_dir)
        cur = revision(doc)
        if base_rev != cur:
            raise AgentError("stale", "the agent choice changed since you loaded it; reload before saving", 409, rev=cur)
        new = {"schema": SCHEMA, "agent": doc["agent"], "steps": dict(doc["steps"])}
        if agent is not _ABSENT:
            new["agent"] = agent
        if steps is None:
            new["steps"] = {}
        elif steps is not _ABSENT:
            for step, wanted in steps.items():
                if wanted is None:
                    new["steps"].pop(step, None)
                else:
                    new["steps"][step] = wanted
        if new != doc or problem:
            if problem:
                _quarantine(path)
            sstore.write_json_atomic(path, new, levels=0)      # levels 0: a deleted project folder is never made again (ProjectGone)
    return project_view(project_dir)
