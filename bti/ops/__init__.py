"""Typed small operations for the picks and the storyboard: named operations with a declared shape, sent in batches, checked
before anything is written, logged, and undoable by batch.

    from bti.ops import apply_ops, registry
    result = apply_ops("storyboard", doc, [{"op": "lock", "shot": "s0003"}], facts, actor="agent:model")

`registry` holds every operation (name, document, JSON Schema, example, Vietnamese sentence, applying function); `apply_ops` is the
pure core (no files, no HTTP); `runner` adds the lock, the revision check, the save and the change log; `bti.editor.ops_api`
is the thin HTTP layer; `python -m bti.ops.doc` writes `docs/OPS.md` from the registry.
"""
from __future__ import annotations

from . import picks_ops, sb_ops  # noqa: F401  - importing them registers the operations
from . import registry
from .batch import Request, Result, apply_ops, parse_request
from .errors import ERRORS, OpError

__all__ = ["apply_ops", "parse_request", "registry", "Request", "Result", "OpError", "ERRORS"]
