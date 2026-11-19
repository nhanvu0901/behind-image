"""What the automatic picks job keeps between its parts, and between a run and the next one that resumes it:
`projects/<pid>/cache/picks_auto/` (a cache: deleting it only costs the work it holds).

    run.json       which lines the run works on and how far it got (`key` says what it was made for; `stage`)
    plan.json      part 1: the plan the agent wrote, checked and with the rules applied, and the model that made it
    search.json    part 2: for every wanted picture, its candidates (with thumbnails) or why there are none
    choice.json    part 3: the agent's choice, checked
    last.json      what the page shows after a run: the result, and the reason of every line the agent wrote
    thumbs/        the thumbnails of the candidates (small JPEGs, named by a hash of the source and id)
    runs/<id>/     the transcript of each agent session

A run is resumed only when its `key` (the narration, the main painting and the lines it works on) is the same and it did not finish;
a finished run or a different request starts again from nothing."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from bti.script import store as sstore

SCHEMA = "bti.picks.auto/1"
FILES = ("run.json", "plan.json", "search.json", "choice.json")
LEVELS = 2                           # cache/picks_auto: the project folder exists, the two below it may be made


def cache_dir(pdir: Path) -> Path:
    return Path(pdir) / "cache" / "picks_auto"


def read(pdir: Path, name: str) -> dict | None:
    """The saved file, or None when it is missing or damaged (a cache that cannot be read is a cache that is not there)."""
    try:
        d = json.loads((cache_dir(pdir) / name).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def write(pdir: Path, name: str, obj: dict) -> None:
    sstore.write_json_atomic(cache_dir(pdir) / name, obj, levels=LEVELS)


def run_key(narration_rev: str, main_key: str, requested: list[str], redo: bool, owner_note: str = "") -> str:
    """What a run is for: the narration, the main painting, the lines the REQUEST covers (not the lines that are left to do: those change as
    the run writes), whether it chooses again, and the owner's words."""
    raw = json.dumps({"narration": narration_rev, "main": main_key, "requested": sorted(requested), "redo": bool(redo), "note": owner_note}, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def reset(pdir: Path) -> None:
    """Forget the saved parts of an earlier run (the thumbnails stay: they are keyed by what they show)."""
    for name in FILES:
        try:
            (cache_dir(pdir) / name).unlink(missing_ok=True)
        except OSError:
            pass


def begin(pdir: Path, key: str, targets: list[str], redo: bool) -> tuple[dict, bool]:
    """The run state of this request and whether it RESUMES an earlier run (the same key and not finished). Otherwise the saved parts are
    forgotten and a new state is written."""
    cur = read(pdir, "run.json")
    if cur and cur.get("key") == key and cur.get("stage") != "done":
        return cur, True
    reset(pdir)
    state = {"schema": SCHEMA, "key": key, "targets": list(targets), "redo": bool(redo), "stage": "plan", "started": time.time(),
             "written": [], "model": None}
    write(pdir, "run.json", state)
    return state, False


def save_run(pdir: Path, state: dict) -> None:
    write(pdir, "run.json", state)


def session_dir(pdir: Path, run_started: float, part: str) -> Path:
    d = cache_dir(pdir) / "runs" / time.strftime("%Y%m%d-%H%M%S", time.localtime(run_started))
    d.mkdir(parents=True, exist_ok=True)
    return d


def prune_runs(pdir: Path, keep: int = 5) -> None:
    """Keep the transcripts of the newest `keep` runs (folders under runs/ that this module made, one level deep)."""
    base = cache_dir(pdir) / "runs"
    try:
        runs = sorted(p for p in base.iterdir() if p.is_dir() and not p.is_symlink())
    except OSError:
        return
    for p in runs[:-keep]:
        try:
            for f in p.iterdir():
                if f.is_file() and not f.is_symlink():
                    f.unlink()
            p.rmdir()
        except OSError:
            pass


def thumb_path(pdir: Path, source: str, source_id: str) -> Path:
    h = hashlib.sha1(("%s:%s" % (source, source_id)).encode("utf-8")).hexdigest()[:16]
    return cache_dir(pdir) / "thumbs" / (h + ".jpg")
