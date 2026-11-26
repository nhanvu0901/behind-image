"""Atomic storage and optimistic concurrency for music documents."""
from __future__ import annotations

import copy
import threading
from pathlib import Path

from bti.script import store as sstore
from .document import MusicError, validate

_LOCKS = {}
_GUARD = threading.Lock()


def _lock(pdir):
    with _GUARD:
        return _LOCKS.setdefault(str(Path(pdir).resolve()), threading.RLock())


def read(pdir):
    return sstore.read_object(Path(pdir) / "music.json", "music")


def revision(doc):
    return sstore.revision(doc if doc is not None else {})


def set_document(pdir, doc, library, timing, duration, *, base_rev, landmarks=None):
    with _lock(pdir):
        current = read(pdir)
        if not isinstance(base_rev, str) or base_rev != revision(current):
            error = MusicError("music changed since it was read; reload before saving")
            error.code, error.retry = "stale_revision", "later"
            error.fix = "Reload the music document and retry."
            raise error
        validate(doc, library, timing, duration, landmarks)
        saved = copy.deepcopy(doc)
        saved["schema"] = "bti.music/1"
        sstore.write_json_atomic(Path(pdir) / "music.json", saved, levels=0)
        return saved


def clear(pdir, *, base_rev):
    with _lock(pdir):
        current = read(pdir)
        if not isinstance(base_rev, str) or base_rev != revision(current):
            error = MusicError("music changed since it was read; reload before clearing")
            error.code, error.retry = "stale_revision", "later"
            error.fix = "Reload the music document and retry."
            raise error
        (Path(pdir) / "music.json").unlink(missing_ok=True)
