"""A batch of operations: the request, and the pure function that applies it.

`parse_request` checks the envelope (`base_rev`, `actor`, `ops`, `dry_run`, `scope`, `note`). `apply_ops` takes a document, the
operations, a scope and the project's facts and either returns the new document with the list of changes, or raises one
`OpError`; it reads and writes no file and knows nothing of HTTP. All or nothing: the document you pass in is never touched,
the result is a private copy.

After the operations, the result goes through the same validation the existing save uses. An error that is NEW (not already
there before the batch, by code and place) refuses the batch with `validation_failed`; problems that were there before never
block it.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from . import registry
from .ctx import Ctx
from .errors import OpError

MAX_OPS = 200
MAX_NOTE = 2000
MAX_SCOPE_IDS = 2000
ENVELOPE = ("base_rev", "actor", "ops", "dry_run", "scope", "note")
ACTOR_FORMS = ["human", "agent:<model id>", "cli:<name>"]
_ACTOR = re.compile(r"^(human|agent:[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,79}|cli:[A-Za-z0-9][A-Za-z0-9._-]{0,39})$")
SCOPE_KEYS = ("shots", "chapters", "beats")


@dataclass
class Request:
    base_rev: str
    actor: str
    ops: list
    dry_run: bool = False
    scope: dict | None = None
    note: str = ""


@dataclass
class Result:
    doc: dict                                   # the new document (a private copy)
    changes: list = field(default_factory=list)
    created: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)  # validation issues of the new document, warnings included
    touched_by: dict = field(default_factory=dict)
    placeholders: set = field(default_factory=set)
    applied: int = 0


def _lone_surrogate(obj: Any) -> bool:
    if isinstance(obj, str):
        try:
            obj.encode("utf-8")
            return False
        except UnicodeEncodeError:
            return True
    if isinstance(obj, dict):
        return any(_lone_surrogate(k) or _lone_surrogate(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_lone_surrogate(v) for v in obj)
    return False


def parse_request(body: Any) -> Request:
    """The envelope of a batch, checked. `invalid_request` lists every wrong field in `fields`."""
    if not isinstance(body, dict):
        raise OpError("invalid_request", "The request body must be a JSON object.", fields=[{"path": "", "problem": "must be a JSON object"}])
    fields: list[dict] = []
    for k in body:
        if k not in ENVELOPE:
            fields.append({"path": str(k)[:40], "problem": "is not a field of a batch request", "allowed": list(ENVELOPE)})
    base = body.get("base_rev")
    if not isinstance(base, str) or not base or len(base) > 128:
        fields.append({"path": "base_rev", "problem": "is required: the revision you read the document at (a non-empty string)"})
    actor = body.get("actor")
    if not isinstance(actor, str) or not _ACTOR.match(actor):
        fields.append({"path": "actor", "problem": "is required and must be human, agent:<model id> or cli:<name>", "allowed": ACTOR_FORMS})
    ops = body.get("ops")
    if not isinstance(ops, list):
        fields.append({"path": "ops", "problem": "is required: a list of 1 to %d operations" % MAX_OPS})
    elif not 1 <= len(ops) <= MAX_OPS:
        fields.append({"path": "ops", "problem": "must have 1 to %d operations (got %d); send more than that in several batches" % (MAX_OPS, len(ops))})
    dry = body.get("dry_run", False)
    if not isinstance(dry, bool):
        fields.append({"path": "dry_run", "problem": "must be true or false"})
    note = body.get("note", "")
    if note is None:
        note = ""
    if not isinstance(note, str) or len(note) > MAX_NOTE:
        fields.append({"path": "note", "problem": "must be a text of at most %d characters" % MAX_NOTE})
    scope = body.get("scope")
    if scope is not None:
        if not isinstance(scope, dict) or len(scope) != 1 or next(iter(scope)) not in SCOPE_KEYS:
            fields.append({"path": "scope", "problem": "must be null or an object with exactly one of shots, chapters, beats", "allowed": list(SCOPE_KEYS)})
        else:
            key, vals = next(iter(scope.items()))
            if not isinstance(vals, list) or not 1 <= len(vals) <= MAX_SCOPE_IDS or not all(isinstance(v, str) and 0 < len(v) <= 64 for v in vals):
                fields.append({"path": "scope.%s" % key, "problem": "must be a list of 1 to %d ids (text)" % MAX_SCOPE_IDS})
    if not fields and _lone_surrogate(body):
        fields.append({"path": "", "problem": "holds a character that cannot be stored (a lone surrogate): remove it"})
    if fields:
        raise OpError("invalid_request", "The batch request is not valid: %s %s." % (fields[0]["path"] or "body", fields[0]["problem"]), fields=fields)
    return Request(base_rev=base, actor=actor, ops=ops, dry_run=dry, scope=scope, note=note)


def apply_ops(kind: str, doc: dict, ops: list, facts: Any, *, actor: str = "human", scope: dict | None = None,
              fetched: dict | None = None, dry_run: bool = False) -> Result:
    """Apply `ops` to a copy of `doc` (kind `picks` or `storyboard`) and return the new document, the changes and the issues.
    `fetched` (picks): `{op index: {asset_key, asset}}`, the pictures the imports of the batch brought in before the document was
    locked. Raises `OpError`; the document passed in is not changed."""
    registry.check_ops(kind, ops)
    work = copy.deepcopy(doc)
    scope_ids = facts.resolve_scope(scope, work) if scope else None
    ctx = Ctx(kind, work, facts, actor=actor, scope_ids=scope_ids, fetched=fetched, dry_run=dry_run)
    table = registry.defs(kind)
    for i, o in enumerate(ops):
        ctx.begin(i, o["op"])
        table[o["op"]].fn(ctx, o)
        ctx.end()
    problem = facts.document_problem(work)
    if problem:
        raise OpError("validation_failed", "The batch would leave a document the save refuses: %s." % problem)
    after, new = new_errors(facts, doc, work, ctx.placeholders)
    if new:
        raise _refusal(new, ctx, facts, work)
    return Result(doc=work, changes=ctx.changes, created=ctx.created, issues=after, touched_by=ctx.touched_by,
                  placeholders=ctx.placeholders, applied=len(ops))


def new_errors(facts: Any, old: dict, new: dict, skip_assets: set | frozenset = frozenset()) -> tuple[list[dict], list[dict]]:
    """`(issues of the new document, the errors among them that are new)`. A problem that was already in `old` (same code, same
    place, found by shot and overlay id or by line and asset) is not new, so it never blocks. `skip_assets` are the stand-ins of a
    dry run's imports."""
    after = [i for i in facts.issues(new) if i.get("asset") not in skip_assets]
    errors = [i for i in after if i.get("level") == "error"]
    if not errors:
        return after, []
    known = {facts.fingerprint(i, old) for i in facts.issues(old) if i.get("level") == "error"}
    return after, [i for i in errors if facts.fingerprint(i, new) not in known]


def _refusal(new: list[dict], ctx: Ctx, facts: Any, work: dict) -> OpError:
    issues, fields, seen = [], [], set()
    for it in new[:50]:
        cands = [ctx.touched_by[k] for k in facts.issue_keys(it, work) if k in ctx.touched_by]
        idx = max(cands) if cands else None
        item = dict(it)
        if idx is not None:
            item["op_index"] = idx
            f = {"path": "ops[%d]" % idx, "problem": str(it.get("message"))[:300]}
            if (f["path"], f["problem"]) not in seen:
                seen.add((f["path"], f["problem"]))
                fields.append(f)
        issues.append(item)
    first = issues[0]
    return OpError("validation_failed",
                   "The batch would leave %d new error%s in the document, for example: %s" % (
                       len(new), "" if len(new) == 1 else "s", str(first.get("message"))[:300]),
                   issues=issues, fields=fields or None, op_index=first.get("op_index"))
