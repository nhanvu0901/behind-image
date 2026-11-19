"""Cleaning the working folder after a successful export: exactly the paths below, nothing else, and only when nothing of the project is running.

Every entry is a cache: the app makes it again when it needs it, and the documents of the project never read it back. The list was made by reading what writes each path and what reads it:

    cache/export/           render parts, the joined video, the mux scratch (bti/export/run.py). `part_key` includes the storyboard's revision, so after any edit no part
                            is reused; the next export renders again, as it would anyway. (The only loss: exporting the SAME storyboard again no longer skips the render.)
    cache/frames/           the page's preview frames (bti/editor/frames.py): made again when a frame is asked for.
    cache/thumbs/           thumbnails of the page: made again on demand.
    cache/previews/         the short "Xem thử" clips (bti/editor/jobs.py): made again on demand.
    cache/uploads/          the scratch of an upload in progress (bti/editor/picks_api.py).
    cache/picks_auto/runs/  the transcripts of the pictures agent's runs (`*-events.jsonl`, the largest part of cache/picks_auto): nothing reads them back. The rest of cache/picks_auto
                            (its plan, search, choice, `last.json` with the reason of every line that the page shows, the candidates' thumbnails) is small and stays.
    cache/voice/            the voice stage's scratch folder (bti/voice/files.py `workdir`): the mix is made again from `voice/chunks`.
    cache/wave_*.json       the waveform of the mix for the page (bti/editor/audio.py): made again on demand.
    cache/longjobs/work/    the work folders of the long jobs (the voice's alignment scratch, the aligner's heard words): `Part.is_done` decides by the files the part writes, not by these.
    cache/longjobs/*.log    the text logs of the long jobs. The RECORDS (`*.json`) stay: the app lists them (GET /api/projects/{pid}/longjobs, the state answer) and `log/jobs.md` is made from them.

What stays: `cache/jobs/*.json` and `cache/longjobs/*.json` (records the app reads), `cache/draft/` (the request box's thread and its turns: the page shows them and a turn can be undone from them), the rest of `cache/picks_auto/`,
`cache/picks/` (the paid picture suggestions: asking again costs money), and everything that is not under `cache/`: the documents, `changes/`, `history/`, `proposals/`, `media/`, `audio/`,
`voice/`, `export/`, `auto_runs/`."""
from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Callable

from . import fsutil

log = logging.getLogger("bti.output")

CACHE_DIRS = ("export", "frames", "thumbs", "previews", "uploads", "picks_auto/runs", "voice", "longjobs/work")
CACHE_GLOBS = ("wave_*.json", "longjobs/*.log")


def targets(pdir: Path, keep_logs: set[str] = frozenset()) -> list[Path]:
    """The existing paths the cleaning would remove (directories whole; log and wave files one by one)."""
    cache = Path(pdir) / "cache"
    out: list[Path] = []
    if not cache.is_dir() or cache.is_symlink():
        return out
    for name in CACHE_DIRS:
        p = cache / name
        if p.exists() or p.is_symlink():
            out.append(p)
    for pattern in CACHE_GLOBS:
        for p in sorted(cache.glob(pattern)):
            if p.stem in keep_logs and p.suffix == ".log":
                continue
            out.append(p)
    return out


def _inside(cache: Path, p: Path) -> bool:
    try:
        return p.resolve().is_relative_to(cache.resolve()) and p.resolve() != cache.resolve()
    except OSError:
        return False


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        def onerr(func, p, exc):            # a read-only file on Windows: make it writable once and try again
            try:
                os.chmod(p, 0o700)
                func(p)
            except OSError:
                raise exc[1] if isinstance(exc, tuple) else exc
        shutil.rmtree(path, onerror=onerr)


def clean_project(pdir: Path, *, busy: Callable[[], dict | None] | None = None, keep_logs: set[str] = frozenset(), dry_run: bool = False) -> dict:
    """Remove the caches of one project. `busy()` returns a running job of the project that is not the caller's own (or None): then nothing is removed.
    -> {"done", "reason", "freed_bytes", "files", "removed": [...], "errors": [...]}; with `dry_run` nothing is removed and the answer says what would be."""
    pdir = Path(pdir)
    res = {"done": False, "reason": None, "freed_bytes": 0, "files": 0, "removed": [], "errors": [], "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    if busy is not None:
        j = busy()
        if j:
            res["reason"] = "job_running"
            res["job"] = {"id": j.get("id"), "kind": j.get("kind")}
            return res
    cache = pdir / "cache"
    items = targets(pdir, set(keep_logs))
    if not items:
        res.update(done=True, reason="nothing_to_clean")
        return res
    groups = {"cache/longjobs/*.log": [0, 0], "cache/wave_*.json": [0, 0]}      # name -> [files, bytes]: the files that are removed one by one
    for p in items:
        if not _inside(cache, p):
            res["errors"].append("%s: outside the cache folder, left alone" % p.name)
            continue
        n, b = fsutil.dir_bytes(p)
        group = None
        if p.is_file():
            group = "cache/wave_*.json" if p.name.startswith("wave_") else "cache/longjobs/*.log"
        if not dry_run:
            try:
                _remove(p)
            except OSError as e:
                res["errors"].append("%s: %s" % (p.relative_to(pdir).as_posix(), str(e)[:120]))
                continue
        res["files"] += n
        res["freed_bytes"] += b
        if group:
            groups[group][0] += n
            groups[group][1] += b
        else:
            res["removed"].append(p.relative_to(pdir).as_posix())
    res["removed"] += ["%s (%d files)" % (g, v[0]) for g, v in groups.items() if v[0]]
    res["done"] = not res["errors"]
    res["reason"] = None if res["done"] else "some_not_removed"
    return res
