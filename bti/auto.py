"""Automatic running of one project: which gates an agent may approve, and which kinds of spending an agent may confirm.

    projects/<pid>/auto.json     {"schema": "bti.auto/1", "enabled": false,
                                  "gates": {"outline": true, "narration": true, "picks": true, "storyboard": true},
                                  "spend": {"model": true, "machine_time": true, "paid": false}}
                                 written atomically, with a revision (sha1 of the canonical JSON, the way `agent.json` has it).

The document says what the OWNER allowed; nothing here runs anything (the automatic run, `bti/auto_run/`, is built on top of it).

    * `enabled` is the switch: while it is false no agent approves any gate (the owner approves on the page).
    * `gates` says which gates an agent may approve once `enabled` is true.
    * `spend` says which kinds of cost an agent may confirm: `model` (an agent works), `machine_time` (the server is busy for a long
      while). `paid` (money) is never allowed to an agent: the key is part of the document but its value is always false, a file that
      says true is read as false and a PUT with true is refused.

A file that is missing, unreadable or odd counts as the defaults above (nothing is allowed); reading never fails. The routes are in
`bti/editor/auto_api.py` (GET and PUT `/api/projects/{pid}/auto`, and the check the four approval routes make).
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

from bti.fsio import atomic_replace
from bti.script import store as sstore

SCHEMA = "bti.auto/1"
FILE = "auto.json"
GATES = ("outline", "narration", "picks", "storyboard")
SPEND = ("model", "machine_time", "paid")
NEVER = ("paid",)                         # the kinds of spend that are never allowed to an agent, whatever the file says
DEFAULT_GATES = {g: True for g in GATES}
DEFAULT_SPEND = {"model": True, "machine_time": True, "paid": False}
KEYS = ("enabled", "gates", "spend")

RUN_ACTOR = "agent:auto"                  # the actor of every call an automatic run makes (bti/auto_run/loop.py): the one caller that may start the work of its own job
ACTOR_FORMS = ["human", "agent:<model id>", "cli:<name>"]
ACTOR_RE = re.compile(r"^(human|agent:[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,79}|cli:[A-Za-z0-9][A-Za-z0-9._-]{0,39})$")   # the form `bti.ops` takes


class AutoError(Exception):
    """A refusal of the auto routes: `code` is the stable word, `status` the HTTP status, `fields` the request fields that are wrong."""

    def __init__(self, code: str, message: str, status: int = 422, **extra: Any):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra


# --------------------------------------------------------------------------------------------------------------- the document
def default_doc() -> dict:
    return {"schema": SCHEMA, "enabled": False, "gates": dict(DEFAULT_GATES), "spend": dict(DEFAULT_SPEND)}


def normalize(raw: Any) -> dict:
    """The full document, whatever `raw` is: a key that is missing or not a boolean has its default, unknown keys are dropped, `paid` is false."""
    doc = default_doc()
    if isinstance(raw, dict):
        doc["enabled"] = raw.get("enabled") is True
        gates = raw.get("gates") if isinstance(raw.get("gates"), dict) else {}
        spend = raw.get("spend") if isinstance(raw.get("spend"), dict) else {}
        for g in GATES:
            if isinstance(gates.get(g), bool):
                doc["gates"][g] = gates[g]
        for k in SPEND:
            if isinstance(spend.get(k), bool):
                doc["spend"][k] = spend[k]
    for k in NEVER:
        doc["spend"][k] = False
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
    """(the normalised document, a problem sentence or None). No file is the defaults; a file that cannot be read counts as the defaults
    too (nothing is allowed), with the problem named: the next change made through the route replaces it."""
    if project_dir is None:
        return default_doc(), None
    try:
        raw = sstore.read_object(project_file(project_dir), "auto")
    except sstore.DocumentCorrupt as e:
        return default_doc(), str(e)
    return normalize(raw), None


# ----------------------------------------------------------------------------------------------------------------- the rule
def gate_allowed(doc: dict, gate: str) -> bool:
    """May an agent approve `gate` now: automatic running is on and the owner allowed this gate."""
    return bool(doc.get("enabled") is True and gate in GATES and (doc.get("gates") or {}).get(gate) is True)


def spend_allowed(doc: dict, kind: str) -> bool:
    """May an agent confirm a cost of this kind: the owner allowed it (`paid` never)."""
    return bool(kind not in NEVER and kind in SPEND and (doc.get("spend") or {}).get(kind) is True)


def gate_refusal(doc: dict, gate: str) -> str | None:
    """None when an agent may approve `gate`; else why not: `auto_off` or `gate_not_allowed`."""
    if gate_allowed(doc, gate):
        return None
    return "auto_off" if doc.get("enabled") is not True else "gate_not_allowed"


def public(doc: dict) -> dict:
    """The part of the document the state answer and the routes show: {enabled, gates, spend}."""
    return {"enabled": doc["enabled"], "gates": dict(doc["gates"]), "spend": dict(doc["spend"])}


def warnings_of(raw: Any, problem: str | None) -> list[dict]:
    out = []
    if problem:
        out.append({"code": "auto_file_unreadable",
                    "message": "Tệp auto.json của dự án không đọc được, nên coi như chưa cho agent tự chạy. Bật lại để ghi tệp mới."})
    if isinstance(raw, dict) and isinstance(raw.get("spend"), dict) and raw["spend"].get("paid") is True:
        out.append({"code": "paid_ignored", "message": "Việc tốn tiền luôn cần chủ dự án: agent không bao giờ được xác nhận chi tiền."})
    return out


def view(project_dir: Path | str) -> dict:
    """GET /api/projects/{pid}/auto: {schema, rev, enabled, gates, spend, warnings}."""
    raw = None
    problem = None
    try:
        raw = sstore.read_object(project_file(project_dir), "auto")
    except sstore.DocumentCorrupt as e:
        problem = str(e)
    doc = normalize(raw)
    return {"schema": SCHEMA, "rev": revision(doc), **public(doc), "warnings": warnings_of(raw, problem)}


# --------------------------------------------------------------------------------------------------------------------- change
def _quarantine(path: Path) -> None:
    """Move an unreadable auto.json aside (auto.json.corrupt-<time>) so that a new choice never silently overwrites it."""
    try:
        atomic_replace(path, path.with_name("%s.corrupt-%d" % (path.name, int(time.time()))))
    except OSError:
        pass


def _bool_map(name: str, value: Any, allowed: tuple[str, ...]) -> list[dict]:
    """The `fields` problems of one of the two maps of a change."""
    if not isinstance(value, dict):
        return [{"path": name, "problem": "must be an object {name: true | false}", "allowed": list(allowed)}]
    out = []
    for k, v in value.items():
        if k not in allowed:
            out.append({"path": "%s.%s" % (name, str(k)[:40]), "problem": "is not one of the known names", "allowed": list(allowed)})
        elif not isinstance(v, bool):
            out.append({"path": "%s.%s" % (name, k), "problem": "must be true or false"})
        elif k in NEVER and v:
            out.append({"path": "%s.%s" % (name, k), "problem": "an agent never spends money: this stays false", "allowed": [False]})
    return out


def update(project_dir: Path | str, changes: dict, base_rev: Any) -> dict:
    """PUT /api/projects/{pid}/auto: `changes` holds `enabled`, `gates` and/or `spend` (a key left out stays; the maps change only the names
    they list). 422 `invalid_field` (with `fields`), 409 `stale` when `base_rev` is not the saved revision (nothing is written). Answers
    like `view`."""
    if not isinstance(base_rev, str) or not base_rev:
        raise AutoError("invalid_field", "base_rev (string) is required", fields=[{"path": "base_rev", "problem": "is required: the `rev` of GET .../auto"}])
    fields: list[dict] = []
    for k in changes:
        if k not in KEYS:
            fields.append({"path": str(k)[:40], "problem": "is not a field of this request", "allowed": ["base_rev", "actor", *KEYS]})
    if "enabled" in changes and not isinstance(changes["enabled"], bool):
        fields.append({"path": "enabled", "problem": "must be true or false"})
    if "gates" in changes:
        fields += _bool_map("gates", changes["gates"], GATES)
    if "spend" in changes:
        fields += _bool_map("spend", changes["spend"], SPEND)
    if fields:
        raise AutoError("invalid_field", "The change is not valid: %s %s." % (fields[0]["path"], fields[0]["problem"]), fields=fields)
    path = project_file(project_dir)
    with _lock(project_dir):
        problem = None
        raw = None
        try:
            raw = sstore.read_object(path, "auto")
        except sstore.DocumentCorrupt as e:
            problem = str(e)
        doc = normalize(raw)
        cur = revision(doc)
        if base_rev != cur:
            raise AutoError("stale", "the automatic-running settings changed since you loaded them; reload before saving", 409, rev=cur)
        new = normalize(doc)
        if "enabled" in changes:
            new["enabled"] = changes["enabled"]
        new["gates"].update(changes.get("gates") or {})
        new["spend"].update(changes.get("spend") or {})
        if new != doc or problem or raw != doc:
            if problem:
                _quarantine(path)
            sstore.write_json_atomic(path, new, levels=0)       # levels 0: a deleted project folder is never made again (ProjectGone)
    return view(project_dir)
