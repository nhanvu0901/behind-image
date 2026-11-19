"""How a batch reads and writes each document: one adapter per document, the same small interface for the runner.

    kind          "picks" | "storyboard"
    lock()        a context manager: the lock the existing saves of that document take (so a batch and a page save never interleave)
    read()        (document, revision) as the page reads it; called under the lock
    rev_of(doc)   the revision a document would have
    facts(doc)    the project's facts for `bti.ops.batch.apply_ops`
    prefetch(ops) {op index: fetched picture} for the operations that need the network (picks imports), run before the lock
    write(doc, issues)   save the document the way the page's PUT saves it; returns (revision, the document as written)
    finish_undo(new, before)   a last touch on a document an undo restored

The storyboard adapter is given the app's own helpers (the storyboard lock, the project's engine object, a function that forgets
its caches), so the batch uses the very lock, revision and file the page's `PUT /api/projects/{pid}/storyboard` uses.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

from bti.engine import storyboard as SB
from bti.picks import doc as pdoc
from bti.picks import service as psvc
from bti.picks.errors import PicksError

from .errors import ERRORS, OpError
from .facts import PicksFacts, StoryboardFacts
from .things import strip_derived

_IMPORT_CODES = ("unknown_source", "not_found", "source_rate_limited", "source_unreachable", "source_error")


def import_error(e: PicksError, index: int) -> OpError:
    """A failed import as a typed error: the code stays the existing one (`source_rate_limited` keeps its wait time)."""
    code = e.code if e.code in _IMPORT_CODES and e.code in ERRORS else "import_failed"
    extra: dict[str, Any] = dict(e.extra)               # `retry_after` and `retryable` of the existing routes stay
    if code == "import_failed" and e.code:
        extra["cause"] = e.code
    return OpError(code, e.detail, status=e.status, retry="later" if e.extra.get("retryable") and code != "unknown_source" else None,
                   op_index=index, fields=[{"path": "ops[%d]" % index, "problem": e.detail}], **extra)


class PicksAdapter:
    kind = "picks"

    def __init__(self, pdir: Path):
        self.pdir = Path(pdir)

    def lock(self):
        return pdoc.Held(self.pdir)

    def read(self) -> tuple[dict, str]:
        d = pdoc.load_or_new(self.pdir)
        return d, pdoc.revision(d)

    def rev_of(self, doc: dict) -> str:
        return pdoc.revision(pdoc.normalize(doc))

    def facts(self, doc: dict) -> PicksFacts:
        return PicksFacts.from_project(self.pdir)

    def prefetch(self, ops: list) -> dict:
        out: dict[int, dict] = {}
        for i, o in enumerate(ops):
            if o.get("op") == "import":
                try:
                    out[i] = psvc.fetch_asset(self.pdir, o["source"], o["source_id"])
                except PicksError as e:
                    raise import_error(e, i)
        return out

    def write(self, doc: dict, issues: list) -> tuple[str, dict]:
        pdoc.save(self.pdir, doc)                    # normalises, drops an approval that no longer matches, keeps picks.prev.json
        saved = pdoc.load(self.pdir)
        return pdoc.revision(saved), saved

    def finish_undo(self, new: dict, before: dict) -> dict:
        """An undo that gives back exactly the content the owner had approved gives the approval back with it (it stands only while
        the content and the narration still match, which is checked whenever it is read)."""
        if pdoc.revision(pdoc.normalize(new)) == pdoc.revision(pdoc.normalize(before)):
            new["approval"] = copy.deepcopy(before.get("approval"))
        return new


class StoryboardAdapter:
    kind = "storyboard"

    def __init__(self, pid: str, pdir: Path, *, project: Callable, saved: Callable, slock: Callable, forget: Callable):
        self.pid, self.pdir = pid, Path(pdir)
        self._project, self._saved, self._slock, self._forget = project, saved, slock, forget

    def lock(self):
        return self._slock(self.pid)

    def read(self) -> tuple[dict, str]:
        from bti.editor.common import compute_rev
        d = self._saved(self.pid)
        return d, compute_rev(d)

    def rev_of(self, doc: dict) -> str:
        from bti.editor.common import compute_rev
        return compute_rev(doc)

    def facts(self, doc: dict) -> StoryboardFacts:
        return StoryboardFacts(self.pdir, self._project(self.pid), doc)

    def prefetch(self, ops: list) -> dict:
        return {}

    def write(self, doc: dict, issues: list) -> tuple[str, dict]:
        """Save like the page's PUT: the approvals record stays as it is (the approval then names an older revision, so it no longer
        stands), the previous file goes to history/, the file is replaced atomically. Errors that were already in the document do
        not refuse the save (the batch made none); every other rule is the save's own."""
        from bti.editor.common import compute_rev
        new = strip_derived(doc)
        new["approvals"] = doc.get("approvals") or {"storyboard": None}
        SB.save(self.pdir, new, [i for i in issues if i.get("level") != "error"])
        self._forget(self.pid)
        return compute_rev(new), new

    def finish_undo(self, new: dict, before: dict) -> dict:
        return new
