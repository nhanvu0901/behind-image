"""Running a batch against a project: the order of the steps, the lock, the write and the log. No HTTP in here.

    1. the envelope and every operation are checked against their schemas   (nothing is read, nothing is downloaded)
    2. the revision is compared with `base_rev`                              (a cheap early refusal, without the lock)
    3. imports run: the pictures are downloaded                              (no lock held; a dry run downloads nothing)
    4. under the document's lock: the revision again, then the operations, then the validation
    5. a dry run, or a batch that changed nothing, stops here and writes nothing
    6. the document is saved the way the page saves it, then one record is added to the change log

An undo is a batch like any other: it is checked, applied under the same lock and logged (with `undo_of`).
"""
from __future__ import annotations

from typing import Any

from bti.script.store import now_iso

from . import registry, things, undo as U
from .batch import Request, apply_ops, new_errors, parse_request
from .errors import OpError
from .log import ChangeLog, number, valid_batch_id

UNDO_KEYS = ("base_rev", "actor", "note")


def _stale(rev: str, doc: str) -> OpError:
    return OpError("stale_revision", "base_rev is not the current revision of the %s document." % doc, current_rev=rev)


def _answer(rev: str, applied: int, batch: str | None, dry: bool, changes: list, issues: list, created: dict, **more: Any) -> dict:
    return {"rev": rev, "applied": applied, "batch": batch, "dry_run": dry, "changes": changes, "issues": issues, "created": created, **more}


def run_batch(adapter, body: Any, log: ChangeLog) -> dict:
    """Apply a batch of operations to the document of `adapter`. Returns the answer of the route; raises `OpError`."""
    req: Request = parse_request(body)
    registry.check_ops(adapter.kind, req.ops)
    _, rev = adapter.read()
    if rev != req.base_rev:
        raise _stale(rev, adapter.kind)
    fetched = {} if req.dry_run else adapter.prefetch(req.ops)
    with adapter.lock():
        cur, rev = adapter.read()
        if rev != req.base_rev:
            raise _stale(rev, adapter.kind)
        res = apply_ops(adapter.kind, cur, req.ops, adapter.facts(cur), actor=req.actor, scope=req.scope, fetched=fetched,
                        dry_run=req.dry_run)
        if req.dry_run or adapter.rev_of(res.doc) == rev:
            return _answer(rev, res.applied, None, req.dry_run, res.changes, res.issues, res.created)
        new_rev, after = adapter.write(res.doc, res.issues)
        record = {"doc": adapter.kind, "time": now_iso(), "actor": req.actor, "note": req.note, "ops": req.ops, "applied": res.applied,
                  "changes": res.changes, "created": res.created, "rev_before": rev, "rev_after": new_rev,
                  "touched": things.changed_keys(adapter.kind, cur, after), "undo_of": None, "scope": req.scope}
        return _answer(new_rev, res.applied, _log(log, record, cur, after), False, res.changes, res.issues, res.created)


def _log(log: ChangeLog, record: dict, before: dict, after: dict) -> str | None:
    """Add the record. A document that was written stays written even if the log cannot be: the answer then has no batch id."""
    try:
        return log.write(record, before, after)
    except OSError:
        return None


def _undo_request(body: Any) -> dict:
    fields = []
    if not isinstance(body, dict):
        raise OpError("invalid_request", "The request body must be a JSON object.", fields=[{"path": "", "problem": "must be a JSON object"}])
    for k in body:
        if k not in UNDO_KEYS:
            fields.append({"path": str(k)[:40], "problem": "is not a field of an undo request", "allowed": list(UNDO_KEYS)})
    base = body.get("base_rev")
    if not isinstance(base, str) or not base or len(base) > 128:
        fields.append({"path": "base_rev", "problem": "is required: the revision you read the document at (a non-empty string)"})
    from .batch import ACTOR_FORMS, _ACTOR
    actor = body.get("actor")
    if not isinstance(actor, str) or not _ACTOR.match(actor):
        fields.append({"path": "actor", "problem": "is required and must be human, agent:<model id> or cli:<name>", "allowed": ACTOR_FORMS})
    note = body.get("note", "")
    if note is None:
        note = ""
    if not isinstance(note, str) or len(note) > 2000:
        fields.append({"path": "note", "problem": "must be a text of at most 2000 characters"})
    if fields:
        raise OpError("invalid_request", "The undo request is not valid: %s %s." % (fields[0]["path"], fields[0]["problem"]), fields=fields)
    return {"base_rev": base, "actor": actor, "note": note}


def run_undo(adapters: dict, batch: str, body: Any, log: ChangeLog) -> dict:
    """Undo one batch of the log (see `bti.ops.undo`). `adapters` maps a document name to its adapter."""
    req = _undo_request(body)
    rec = log.get(batch) if valid_batch_id(batch) else None
    if rec is None or rec.get("doc") not in adapters:
        raise OpError("batch_not_found", "There is no batch %s in the change log of this project." % str(batch)[:40])
    kind = rec["doc"]
    adapter = adapters[kind]
    _, rev = adapter.read()
    if rev != req.get("base_rev"):
        raise _stale(rev, kind)
    with adapter.lock():
        cur, rev = adapter.read()
        if rev != req["base_rev"]:
            raise _stale(rev, kind)
        both = log.copies(batch)
        if both is None:
            raise OpError("undo_unavailable", "The copies of batch %s were removed when the change log was pruned." % batch)
        before, after = both
        later = [r for r in log.records(kind) if number(r["batch"]) > number(batch)]
        keys, conflicts = U.find_conflicts(kind, cur, before, after, later)
        if conflicts:
            raise U.conflict_error(conflicts, batch)
        new = U.restore_shots(cur, before, keys) if kind == "storyboard" else U.restore_picks(cur, before, keys)
        new = adapter.finish_undo(new, before)
        facts = adapter.facts(cur)
        problem = facts.document_problem(new)
        if problem:
            raise OpError("undo_conflict", "Batch %s cannot be undone: the result would not be a valid document (%s)." % (batch, problem),
                          conflicts=[])
        after_issues, bad = new_errors(facts, cur, new)
        if bad:
            raise OpError("undo_conflict", "Batch %s cannot be undone: it would leave a new error in the document (%s)."
                          % (batch, str(bad[0].get("message"))[:200]), conflicts=[], issues=bad[:20])
        changes = U.undo_changes(kind, new, before, after, keys, facts)
        if adapter.rev_of(new) == rev:
            return _answer(rev, 1, None, False, [], after_issues, {"shots": [], "overlays": [], "assets": [], "refs": {}}, undo_of=batch)
        new_rev, written = adapter.write(new, after_issues)
        record = {"doc": kind, "time": now_iso(), "actor": req["actor"], "note": req["note"],
                  "ops": [{"op": "undo", "batch": batch}], "applied": 1, "changes": changes,
                  "created": {"shots": [], "overlays": [], "assets": [], "refs": {}}, "rev_before": rev, "rev_after": new_rev,
                  "touched": things.changed_keys(kind, cur, written), "undo_of": batch, "scope": None}
        bid = _log(log, record, cur, written)
        return _answer(new_rev, 1, bid, False, changes, after_issues, record["created"], undo_of=batch)


def list_changes(log: ChangeLog, doc: Any, limit: Any) -> dict:
    """The answer of `GET /api/projects/{pid}/changes`: the newest records first, without the copies."""
    fields = []
    if doc is not None and doc not in ("picks", "storyboard"):
        fields.append({"path": "doc", "problem": "must be picks or storyboard (leave it out for both)", "allowed": ["picks", "storyboard"]})
    n = 50
    if limit is not None:
        try:
            n = int(limit)
        except (TypeError, ValueError):
            n = 0
        if not 1 <= n <= 200:
            fields.append({"path": "limit", "problem": "must be a whole number from 1 to 200"})
    if fields:
        raise OpError("invalid_request", "The query is not valid: %s %s." % (fields[0]["path"], fields[0]["problem"]), fields=fields)
    return {"changes": log.list(doc, n)}
