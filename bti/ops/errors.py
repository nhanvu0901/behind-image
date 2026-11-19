"""Typed errors of the operations library.

One class, `OpError`, and one table, `ERRORS`: every code the batch routes can answer with, its HTTP status, whether a retry
can help, and the canonical `fix` sentence (an imperative an agent can act on). `docs/OPS.md` is generated from this table.

An error body is `{code, detail, fix, retry}` plus, when it applies, `fields` (a list of `{path, problem, allowed?}`),
`op_index` (the operation that caused it) and a few named extras (`current_rev`, `issues`, `conflicts`, ...). The routes raise
it through `bti.editor.common.ApiError(status, detail, **body)`; nothing in this package knows about HTTP.
"""
from __future__ import annotations

from typing import Any

RETRY = ("no", "after_fix", "later")

# code -> (HTTP status, retry, canonical fix sentence, what it means)
ERRORS: dict[str, tuple[int, str, str, str]] = {
    "invalid_request": (422, "after_fix",
                        "Send a JSON object with base_rev, actor and 1 to 200 operations, and correct the fields listed.",
                        "The request body is not a valid batch (missing or wrong envelope field, wrong number of operations, bad scope)."),
    "unknown_op": (422, "after_fix", "Use one of the operation names listed in allowed.",
                   "An operation name is not one of the operations of this document."),
    "invalid_field": (422, "after_fix", "Correct the fields listed and send the batch again.",
                      "A field of an operation is missing, has the wrong type, is out of range or is not allowed."),
    "unknown_shot": (422, "after_fix", "Use a shot id from allowed, or a $ref made by an earlier operation of the batch.",
                     "No shot with this id exists in the storyboard."),
    "unknown_overlay": (422, "after_fix", "Use an overlay id of that shot from allowed, or a $ref made by an earlier operation.",
                        "The shot has no overlay with this id."),
    "unknown_beat": (422, "after_fix", "Use a beat id of the approved narration (allowed lists them when there are few).",
                     "No beat with this id exists in the narration."),
    "unknown_asset": (422, "after_fix",
                      "Use an asset key from allowed, or import the picture first with an import operation and refer to it by its $ref.",
                      "No asset with this key exists in the document."),
    "unknown_region": (422, "after_fix", "Use one of the allowed region names, or add the region first with set_region.",
                       "The asset has no region with this name."),
    "unknown_technique": (422, "after_fix", "Use one of the allowed technique ids.",
                          "No technique with this id exists in the style registry."),
    "wrong_technique_kind": (422, "after_fix",
                             "Use a technique of the kind that fits: base or card for a shot, overlay for an overlay.",
                             "The technique exists but its kind does not fit where it is used."),
    "technique_unavailable": (422, "after_fix", "Use a technique the engine can draw (engine.available is true in the registry).",
                              "The technique is in the registry but the engine cannot draw it yet."),
    "unknown_param": (422, "after_fix", "Use one of the allowed parameter names of this technique.",
                      "The technique has no parameter with this name."),
    "unknown_slot": (422, "after_fix", "Use one of the allowed slot names of this technique.",
                     "The technique has no slot with this name."),
    "slot_kind_mismatch": (422, "after_fix", "Use an asset of the kind the slot takes (allowed lists the kinds).",
                           "The asset is of another kind than the slot takes (image, video or mask)."),
    "unknown_ref": (422, "after_fix",
                    "Define the ref on an earlier operation of the batch (import, split_shot, add_overlay) before you use it.",
                    "A $ref names nothing that an earlier operation of this batch created, or something of another kind."),
    "duplicate_ref": (422, "after_fix", "Give every ref in a batch a different name.",
                      "Two operations of the batch define the same ref."),
    "shot_too_short": (422, "after_fix", "Choose a time that leaves every piece at least 0.2 seconds long.",
                       "The time would make a shot shorter than 0.2 seconds."),
    "not_consecutive": (422, "after_fix", "Give shots that follow each other in the storyboard, in their order.",
                        "The shots named are not a run of neighbours."),
    "span_mismatch": (422, "after_fix",
                      "Make the first new shot start where the replaced run starts and keep every other start inside the run.",
                      "The new shots of replace_range do not cover exactly the span of the shots they replace."),
    "video_not_main": (422, "after_fix", "Choose an image as the main picture.", "A video cannot be the main picture."),
    "locked": (409, "after_fix", "Send unlock for that shot or overlay first, or leave it out of the batch.",
               "The shot (or overlay) is locked; every operation on it is refused except unlock."),
    "out_of_scope": (422, "after_fix", "Remove the operation from the batch, or send the batch with a wider scope.",
                     "An operation touches something outside the scope the batch declared."),
    "stale_revision": (409, "after_fix",
                       "Read the document again, apply your operations to the new revision and send again with base_rev set to current_rev.",
                       "base_rev is not the current revision of the document; nothing was written."),
    "validation_failed": (422, "after_fix",
                          "Correct what the issues say in the operations named by op_index, then send the batch again; nothing was written.",
                          "The batch would leave the document with a new error that the existing save would refuse."),
    "undo_conflict": (409, "after_fix",
                      "Undo the later batches first (newest first), or leave the things named in conflicts as they are.",
                      "Something the batch changed was changed again since, so it cannot be put back."),
    "undo_unavailable": (409, "no",
                         "Make the change again with new operations: the copies of this batch were removed when the log was pruned.",
                         "The record is still listed but its copies of the document are gone."),
    "batch_not_found": (404, "no", "Take a batch id from the list at GET /api/projects/{pid}/changes.",
                        "No batch with this id is in the log."),
    "project_not_found": (404, "no", "Take the project id from GET /api/projects.", "No project with this id exists."),
    "document_missing": (404, "after_fix", "Make the storyboard first (step 5 of the pipeline), then send operations.",
                         "The project has no storyboard yet."),
    "document_corrupt": (409, "no", "Restore a good copy of the file (the storyboard has POST /api/projects/{pid}/storyboard/restore).",
                         "A file of the project cannot be read."),
    "unknown_source": (422, "after_fix", "Use one of the allowed sources.", "The picture source of an import is not one of the known sources."),
    "not_found": (404, "after_fix", "Use a source_id from GET /api/projects/{pid}/picks/book-images.",
                  "The picture to import is not part of the project's books."),
    "source_rate_limited": (503, "later",
                            "Wait retry_after seconds (a minute when it is null), then send the batch again; nothing was written.",
                            "The picture source asked for fewer requests."),
    "source_unreachable": (503, "later", "Send the batch again in a minute; nothing was written.",
                           "The picture source is busy or did not answer."),
    "source_error": (502, "no", "Choose another picture or another source; nothing was written.",
                     "The picture source answered with an error."),
    "import_failed": (502, "no", "Check source and source_id, or choose another picture; nothing was written.",
                      "A picture could not be brought into the project (any other reason)."),
}


class OpError(Exception):
    """One typed refusal. `status`, `retry` and `fix` default to the table; a caller may sharpen `fix` for its case."""

    def __init__(self, code: str, detail: str, *, fix: str | None = None, status: int | None = None, retry: str | None = None,
                 fields: list[dict] | None = None, op_index: int | None = None, **extra: Any):
        spec = ERRORS[code]
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status if status is not None else spec[0]
        self.retry = retry or spec[1]
        self.fix = fix or spec[2]
        self.fields = fields or None
        self.op_index = op_index
        self.extra = extra

    def body(self) -> dict:
        """Everything of the error body except `detail` (the route passes that apart)."""
        out: dict[str, Any] = {"code": self.code, "fix": self.fix, "retry": self.retry}
        if self.fields:
            out["fields"] = self.fields
        if self.op_index is not None:
            out["op_index"] = self.op_index
        out.update(self.extra)
        return out

    def __repr__(self) -> str:
        return "OpError(%s, %r)" % (self.code, self.detail)


SMALL = 60        # `allowed` is given whenever the set has at most this many members


def small(values) -> list | None:
    """The values as a list when there are at most SMALL of them, else None (a long list is no help to a reader)."""
    vals = list(values)
    return vals if len(vals) <= SMALL else None
