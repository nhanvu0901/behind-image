"""The working context of one batch: the document being changed and everything an applying function needs.

`Ctx` holds a private copy of the document (`ctx.doc`), the project's facts, the scope, the refs defined so far, the list of
changes and the ids created. It also does the bookkeeping that makes the answer truthful: an operation calls
`ctx.touch(key)` BEFORE it changes a thing (see `bti.ops.things`), and when the operation returns, a thing whose value did not
change takes its sentence back out of `changes` (an operation that changes nothing is not reported as a change).
"""
from __future__ import annotations

import re
from typing import Any

from . import registry, things
from .errors import OpError, small

REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")


def pic_name(doc: dict, key: str) -> str:
    """`hình “Title”` for an asset of a document (its key when it has no title); long titles are cut."""
    a = (doc.get("assets") or {}).get(key) or {}
    title = " ".join(str(a.get("title") or "").split())
    if len(title) > 58:
        title = title[:57] + "…"
    return "hình “%s”" % (title or key)


class Ctx:
    def __init__(self, kind: str, doc: dict, facts: Any, *, actor: str = "human", scope_ids: set[str] | None = None,
                 fetched: dict | None = None, dry_run: bool = False):
        self.kind = kind                          # "picks" | "storyboard"
        self.doc = doc
        self.facts = facts
        self.actor = actor
        self.source = "human" if actor == "human" else "agent"     # the `source` an item gets: who wrote it
        self.scope_ids = scope_ids                # None: no scope; else the ids (shots, or beats for picks) the batch may touch
        self.fetched = fetched or {}              # picks: op index -> {asset_key, asset} (imports run before the lock)
        self.dry_run = dry_run
        self.index = 0
        self.op_name = ""
        self.refs: dict[str, dict] = {}
        self.created: dict[str, Any] = {"shots": [], "overlays": [], "assets": [], "refs": {}}
        self.changes: list[dict] = []
        self.touched_by: dict[str, int] = {}      # thing key -> index of the last operation that changed it
        self.placeholders: set[str] = set()       # asset keys that stand for an import of a dry run
        self.imported: set[str] = set()           # asset keys an import of this batch made or found (sentences call them "the picture just imported")
        self._snaps: dict[str, str] = {}
        self._mark = 0

    # ---------------------------------------------------------------- errors
    def fail(self, code: str, detail: str, *, fields: list[dict] | None = None, **extra: Any) -> None:
        raise OpError(code, detail, fields=fields, op_index=self.index, **extra)

    def bad(self, field: str, problem: str, *, allowed: Any = None, code: str = "invalid_field", **extra: Any) -> None:
        """Refuse the operation because of one field. `field` is relative to the operation (`items[1].region`)."""
        entry: dict[str, Any] = {"path": "ops[%d].%s" % (self.index, field) if field else "ops[%d]" % self.index, "problem": problem}
        if allowed is not None:
            vals = small(allowed)
            if vals is not None:
                entry["allowed"] = vals
        self.fail(code, "ops[%d]%s: %s" % (self.index, "." + field if field else "", problem), fields=[entry], **extra)

    # ---------------------------------------------------------------- refs
    def resolve(self, value: Any, kind: str, field: str) -> Any:
        """The id behind `value`: an id as it is, or the id a `$name` ref was given by an earlier operation of the batch."""
        if isinstance(value, str) and value.startswith("$"):
            name = value[1:]
            hit = self.refs.get(name)
            if hit is None:
                self.bad(field, "no operation before this one defined the ref %r" % name, allowed=sorted(self.refs), code="unknown_ref")
            if hit["kind"] != kind:
                self.bad(field, "the ref %r is a %s, but a %s is needed here" % (name, hit["kind"], kind), code="unknown_ref",
                         allowed=sorted(r for r, h in self.refs.items() if h["kind"] == kind))
            return hit["id"]
        return value

    def ref_shot(self, value: Any) -> str | None:
        """The shot of an overlay `$ref` (None for a plain id)."""
        if isinstance(value, str) and value.startswith("$"):
            hit = self.refs.get(value[1:])
            return hit.get("shot") if hit else None
        return None

    def define_ref(self, name: str | None, kind: str, ident: str, shot: str | None = None) -> None:
        if not name:
            return
        if name in self.refs:
            self.bad("ref", "the ref %r is already defined by an earlier operation" % name, code="duplicate_ref")
        self.refs[name] = {"kind": kind, "id": ident, "shot": shot}
        self.created["refs"][name] = ident

    # ---------------------------------------------------------------- scope
    def in_scope(self, ident: str, field: str, what: str) -> None:
        if self.scope_ids is not None and ident not in self.scope_ids:
            self.bad(field, "%s %s is outside the scope of this batch" % (what, ident), code="out_of_scope",
                     allowed=sorted(self.scope_ids))

    def whole_document(self, why: str) -> None:
        """An operation that changes something shared by every line or shot is outside any scope."""
        if self.scope_ids is not None:
            self.bad("", "%s changes something that belongs to the whole document, which a scoped batch may not touch" % why,
                     code="out_of_scope")

    # ---------------------------------------------------------------- bookkeeping
    def begin(self, index: int, name: str) -> None:
        self.index, self.op_name = index, name
        self._snaps = {}
        self._mark = len(self.changes)

    def touch(self, key: str) -> None:
        """Call before an operation changes the thing `key` (the first call of an operation takes the snapshot)."""
        if key not in self._snaps:
            self._snaps[key] = things.canon(things.get(self.kind, self.doc, key))

    def end(self) -> None:
        if not self._snaps:
            return
        moved = [k for k, snap in self._snaps.items() if things.canon(things.get(self.kind, self.doc, k)) != snap]
        if not moved:
            del self.changes[self._mark:]          # the operation changed nothing: nothing to report
            return
        for k in moved:
            self.touched_by[k] = self.index

    def pic(self, key: str) -> str:
        """How a sentence names a picture: `hình “Title”`, or `hình vừa nhập` for one this batch imported."""
        return "hình vừa nhập" if key in self.imported else pic_name(self.doc, key)

    # ---------------------------------------------------------------- the answer
    def say(self, target: dict, time: str | None = None, variant: str = "default", **vars: Any) -> None:
        """Add a `changes` entry: the Vietnamese sentence of this operation (its template is in the registry)."""
        tmpl = registry.defs(self.kind)[self.op_name].sentences[variant]
        what = tmpl.format(**vars).replace("!", "")          # a title that came from outside may hold one; the owner reads none
        self.changes.append({"target": target, "time": time, "what": what})
