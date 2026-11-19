"""The change log of a project: one record for every batch that wrote a document, kept in `projects/<pid>/changes/`, next to
`history/` (which keeps the older storyboards the page's saves replaced and is untouched by this).

Three files per batch, named by its id (`batch_0007`, one counter for the whole project):

    batch_0007.json          the record, without the documents: batch, doc, time, actor, note, ops (as sent), applied, changes,
                             created, rev_before, rev_after, touched (the thing keys that changed), undo_of, scope, copies
    batch_0007.before.json   the document as it was before the batch
    batch_0007.after.json    the document as the batch left it

The record is written last: it is what makes a batch exist, so a crash leaves at most two orphan copies, which the next prune
removes. Pruning keeps, per document (picks, storyboard), the newest RECORDS_KEEP records and, of those, the copies of only the
newest COPIES_KEEP: older records are still listed (`copies: false`) but can no longer be undone. All writes happen under one
lock, inside the lock of the document that was written (document lock first, then this one, never the reverse).
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from bti.script import store as sstore

LOG_DIR = "changes"
RECORDS_KEEP = 200
COPIES_KEEP = 50
BATCH_RE = re.compile(r"^batch_(\d{4,9})$")
_FILE_RE = re.compile(r"^batch_(\d{4,9})(\.before|\.after)?\.json$")
_LOG_LOCK = threading.RLock()
_DOC_OF: dict[tuple[str, int], str] = {}          # (log folder, number) -> document of that record (so a prune reads few files)


def valid_batch_id(bid: Any) -> bool:
    return isinstance(bid, str) and BATCH_RE.match(bid) is not None


def number(bid: str) -> int:
    return int(BATCH_RE.match(bid).group(1))


class ChangeLog:
    def __init__(self, pdir: Path):
        self.dir = Path(pdir) / LOG_DIR

    # ---------------------------------------------------------------- files
    def _rec(self, bid: str) -> Path:
        return self.dir / ("%s.json" % bid)

    def _copy(self, bid: str, which: str) -> Path:
        return self.dir / ("%s.%s.json" % (bid, which))

    def _names(self) -> list[str]:
        try:
            return [f.name for f in self.dir.iterdir() if f.is_file()]
        except OSError:
            return []

    def numbers(self) -> list[int]:
        """The numbers of the batches that have a record, ascending."""
        out = []
        for name in self._names():
            m = _FILE_RE.match(name)
            if m and not m.group(2):
                out.append(int(m.group(1)))
        return sorted(out)

    @staticmethod
    def _bid(n: int) -> str:
        return "batch_%04d" % n

    # ---------------------------------------------------------------- reading
    def get(self, bid: str) -> dict | None:
        """The record of a batch (without the copies), None when there is none or it cannot be read."""
        if not valid_batch_id(bid):
            return None
        try:
            return sstore.read_object(self._rec(bid), "changes")
        except sstore.DocumentCorrupt:
            return None

    def copies(self, bid: str) -> tuple[dict, dict] | None:
        """`(before, after)` documents of a batch, None when they were pruned or cannot be read."""
        try:
            b = sstore.read_object(self._copy(bid, "before"), "changes")
            a = sstore.read_object(self._copy(bid, "after"), "changes")
        except sstore.DocumentCorrupt:
            return None
        return (b, a) if b is not None and a is not None else None

    def records(self, doc: str | None = None) -> list[dict]:
        """Every record (of one document when `doc` is given), oldest first."""
        out = []
        for n in self.numbers():
            rec = self.get(self._bid(n))
            if rec is not None and (doc is None or rec.get("doc") == doc):
                out.append(rec)
        return out

    def list(self, doc: str | None = None, limit: int = 50) -> list[dict]:
        """The newest records first (of one document when `doc` is given), at most `limit`, each with `undone_by` (the id of the
        batch that undid it, or null). The documents' copies are not part of a record."""
        recs = self.records()
        undone: dict[str, str] = {}
        for r in recs:
            if r.get("undo_of"):
                undone[r["undo_of"]] = r["batch"]
        out = []
        for r in reversed(recs):
            if doc is not None and r.get("doc") != doc:
                continue
            out.append({**r, "undone_by": undone.get(r["batch"])})
            if len(out) >= limit:
                break
        return out

    # ---------------------------------------------------------------- writing
    def write(self, record: dict, before: dict, after: dict) -> str:
        """Add a record with its copies and prune; returns the batch id. The caller holds the lock of the document."""
        with _LOG_LOCK:
            nums = self.numbers()
            bid = self._bid((nums[-1] if nums else 0) + 1)
            rec = {**record, "batch": bid, "copies": True}
            sstore.write_json_atomic(self._copy(bid, "before"), before)
            sstore.write_json_atomic(self._copy(bid, "after"), after)
            sstore.write_json_atomic(self._rec(bid), rec)
            _DOC_OF[(str(self.dir), number(bid))] = rec["doc"]
            try:
                self._prune(rec["doc"])
            except OSError:
                pass                                 # a prune that fails leaves old files for the next one; the batch is logged
            return bid

    def _doc_of(self, n: int) -> str | None:
        key = (str(self.dir), n)
        if key not in _DOC_OF:
            rec = self.get(self._bid(n))
            if rec is None:
                return None
            _DOC_OF[key] = rec.get("doc")
        return _DOC_OF[key]

    def _drop(self, bid: str, *, record: bool) -> None:
        for p in (self._copy(bid, "before"), self._copy(bid, "after")) + ((self._rec(bid),) if record else ()):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

    def _prune(self, doc: str) -> None:
        mine = [n for n in self.numbers() if self._doc_of(n) == doc]
        for n in mine[:-RECORDS_KEEP]:
            self._drop(self._bid(n), record=True)
            _DOC_OF.pop((str(self.dir), n), None)
        kept = mine[-RECORDS_KEEP:]
        for n in kept[:-COPIES_KEEP]:
            bid = self._bid(n)
            if self._copy(bid, "before").exists() or self._copy(bid, "after").exists():
                self._drop(bid, record=False)
                rec = self.get(bid)
                if rec is not None and rec.get("copies"):
                    rec["copies"] = False
                    sstore.write_json_atomic(self._rec(bid), rec)
        have = set(self.numbers())                  # copies without a record (a crash between the writes) are removed
        for name in self._names():
            m = _FILE_RE.match(name)
            if m and m.group(2) and int(m.group(1)) not in have:
                try:
                    (self.dir / name).unlink()
                except FileNotFoundError:
                    pass
