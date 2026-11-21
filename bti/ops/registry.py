"""The one registry of operations.

Every operation is declared once, with `@op(document, name, summary=..., schema=..., example=..., sentences=...)` on the function
that applies it. Everything else is derived from this table: the check of a request, `GET /api/ops/schema`, the sentences of
the change log and the generated `docs/OPS.md`.

An applying function has the form `fn(ctx, o)`: `ctx` is a `bti.ops.ctx.Ctx` (the working document, the project's facts, the
refs, the change list) and `o` an operation already checked against its schema. It changes `ctx.doc` in place and says what it
did with `ctx.say(...)`, or raises an `OpError` through the `ctx` helpers. Nothing here knows about HTTP or about files.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .errors import OpError, small
from . import schemacheck

DOCS = ("picks", "storyboard")


@dataclass(frozen=True)
class OpDef:
    name: str
    doc: str                        # "picks" | "storyboard"
    summary: str                    # one English sentence
    schema: dict                    # JSON Schema of the operation object
    example: dict                   # one filled example that applies to the test fixture project
    sentences: dict                 # variant -> Vietnamese template of the `changes[].what` sentence
    fn: Callable[[Any, dict], None]


_OPS: dict[str, dict[str, OpDef]] = {d: {} for d in DOCS}


def op(doc: str, name: str, *, summary: str, schema: dict, example: dict, sentences: dict | str):
    """Register the applying function of operation `name` of document `doc`."""
    if doc not in _OPS:
        raise ValueError("unknown document %r" % doc)
    if name in _OPS[doc]:
        raise ValueError("operation %s/%s is registered twice" % (doc, name))
    if isinstance(sentences, str):
        sentences = {"default": sentences}

    def deco(fn):
        _OPS[doc][name] = OpDef(name, doc, summary, schema, example, dict(sentences), fn)
        return fn
    return deco


def defs(doc: str) -> dict[str, OpDef]:
    """The operations of a document, in the order they were declared."""
    return _OPS[doc]


def schema_document() -> dict:
    """The answer of `GET /api/ops/schema`."""
    return {d: {name: {"summary": o.summary, "schema": o.schema, "example": o.example} for name, o in _OPS[d].items()} for d in DOCS}


def check_ops(doc: str, ops: list) -> list[dict]:
    """Check every operation of a batch against its schema (nothing else; no document is read). Returns the operations.
    Raises `unknown_op` for a name that is not an operation of `doc`, `invalid_field` (every wrong field, with its path
    `ops[i].field` and, when the set is small, `allowed`) for a shape that does not fit."""
    table = _OPS[doc]
    fields: list[dict] = []
    first_index: int | None = None
    for i, o in enumerate(ops):
        if not isinstance(o, dict):
            raise OpError("invalid_field", "ops[%d] must be an object" % i, op_index=i,
                          fields=[{"path": "ops[%d]" % i, "problem": "must be an object with an `op` name"}])
        if not isinstance(o.get("op"), str):
            raise OpError("invalid_field", "ops[%d].op is required (a string)" % i, op_index=i,
                          fields=[{"path": "ops[%d].op" % i, "problem": "is required (a string)", "allowed": list(table)}])
        d = table.get(o["op"])
        if d is None:
            raise OpError("unknown_op", "ops[%d].op: %r is not an operation of the %s document" % (i, o["op"][:40], doc), op_index=i,
                          fields=[{"path": "ops[%d].op" % i, "problem": "is not an operation of the %s document" % doc,
                                   "allowed": list(table)}])
        found = schemacheck.validate(d.schema, o, "ops[%d]" % i)
        if found and first_index is None:
            first_index = i
        fields.extend(found)
        if len(fields) >= schemacheck.MAX_FIELDS:
            break
    if fields:
        raise OpError("invalid_field", "%s: %s" % (fields[0]["path"], fields[0]["problem"]), fields=fields[:schemacheck.MAX_FIELDS],
                      op_index=first_index)
    return ops


def names(doc: str) -> list[str]:
    return list(_OPS[doc])


__all__ = ["OpDef", "op", "defs", "schema_document", "check_ops", "names", "small", "DOCS"]
