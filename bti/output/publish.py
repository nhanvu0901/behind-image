"""`sync`: the ONE function that decides what is written into the output folder of a project, and writes it.

    sync(project_dir, output_root, moment="narration approved")  ->  {"key", "folder", "written": [...], "parts": {...}, "warnings": [...], "skipped": None | reason, "clean": ...}

It is called at every moment the project moves (an approval, the voice done, the export done, a document edited: see `hooks.py`) and by the rebuild command. It looks at the project as it
stands and, for each part of the folder (see `parts.py`):

    settled (the gate stands) and not yet written, or written from another revision  ->  write it
    not settled, written before, the document changed or the approval was withdrawn  ->  keep the old files and mark the part OUT OF DATE (state.json, README.md)
    settled and the files are what the document says                                 ->  nothing

then `state.json`, `README.md`, `log/` and the index are written. Every file is written atomically. One part that cannot be written is a warning with its sentence and the other parts go on;
`sync` raises only when the folder itself cannot be made, and `hooks.notify` never lets even that out. A run that finds nothing changed (the same fingerprint of the project) writes nothing."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import facts as F
from . import fsutil, index, parts as P, readme, render, words
from .paths import FINAL_VIDEO, LOG_DIR, PARTS, README_FILE, STATE_FILE, folder_of

log = logging.getLogger("bti.output")
SCHEMA = "bti.output/1"
CLEAN_MOMENTS = ("export", "export done")           # the moments at which a successful export is followed by the cleaning (unless the switch is off)
PART_IDS = ("sources", "outline", "narration", "voice", "pictures", "storyboard", "export")
PART_FOLDER = {"sources": "sources", "outline": "script", "narration": "script", "voice": "voice", "pictures": "pictures", "storyboard": "storyboard", "export": "export"}

_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()


class NotApplicable(Exception):
    """A project that has no output folder: a reference project, one imported without book data, or no project.json."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _lock(folder: Path) -> threading.RLock:
    with _GUARD:
        return _LOCKS.setdefault(str(Path(folder).resolve()), threading.RLock())


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ------------------------------------------------------------------------------------------------ what each part needs
def _settled(f, part: str) -> bool:
    return {"sources": True, "outline": f.outline_ok, "narration": f.narration_ok, "voice": f.voice_ok, "pictures": f.picks_ok, "storyboard": f.sb_approval == "fresh",
            "export": f.export_ok}[part]


def _rev_now(f, part: str) -> str | None:
    if part == "sources":
        return None            # decided by the writer (the files of source/ are read there)
    return {"outline": f.outline_rev, "narration": f.narration_rev, "voice": P.voice_rev(f), "pictures": f.picks_rev, "storyboard": f.sb_rev, "export": P.export_rev(f)}[part]


def _writer(part: str) -> Callable:
    return {"sources": P.write_sources, "outline": P.write_outline, "narration": P.write_narration, "voice": P.write_voice, "storyboard": P.write_storyboard,
            "export": P.write_export}.get(part)


def _files_exist(folder: Path, pub: dict) -> bool:
    return all((folder / x).exists() for x in (pub.get("files") or []))


def _sources_rev(f) -> str:
    """The revision of the sources part without writing it: the project's list of sources and the files of `source/`."""
    src = f.pdir / "source"
    shas = []
    if src.is_dir():
        for p in sorted(src.iterdir()):
            if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in (".txt", ".json"):
                shas.append(p.name + ":" + (P.sha_of(p) or ""))
    return P.sha(json.dumps(f.meta.get("sources"), sort_keys=True, ensure_ascii=False), *shas)


def fingerprint(f) -> str:
    """A short text that changes when anything the folder is made from changes."""
    return P.sha(json.dumps({
        "k": f.key, "pid": f.pid, "meta": [f.title, f.artist, f.year, f.created], "src": _sources_rev(f),
        "rev": [f.outline_rev, f.narration_rev, f.picks_rev, f.sb_rev, f.timing_sha, P.voice_rev(f), P.export_rev(f)],
        "ok": [f.outline_ok, f.narration_ok, f.picks_ok, f.sb_approval, f.voice_ok, f.export_ok], "appr": f.approvals,
        "jobs": [(j["id"], j["state"], j["finished"]) for j in f.jobs], "changes": [(c.get("batch"), c.get("undone_by")) for c in f.changes],
        "auto": [(r.get("id"), r.get("ended")) for r in f.auto_runs], "agents": f.agents, "problems": f.problems}, sort_keys=True, default=str))


# ------------------------------------------------------------------------------------------------ the state document
def read_state(folder: Path) -> dict | None:
    st = fsutil.read_json(folder / STATE_FILE)
    return st if isinstance(st, dict) and st.get("schema") == SCHEMA else None


def _owner_gives_way(prev: dict | None, f, explicit: bool, projects_root: Path) -> bool:
    """May this project write into a folder whose state says another project made it? Yes when asked explicitly, when that project is gone, or when this one is newer."""
    if prev is None or prev.get("project") == f.pid or explicit:
        return True
    if not (projects_root / str(prev.get("project"))).is_dir():
        return True
    a, b = words.parse_time(prev.get("project_created")), words.parse_time(f.created)
    return a is None or b is None or b >= a


def purge_content(folder: Path) -> None:
    """A project takes the folder over from another one: what the other project made goes (the files of its parts and its video); `state.json` stays for its record of runs."""
    import shutil
    for name in list(PARTS.values()) + [LOG_DIR]:
        p = folder / name
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p, ignore_errors=True)
    fsutil.remove(folder / FINAL_VIDEO)
    fsutil.remove(folder / README_FILE)


def _warning(part: str, e: Exception) -> dict:
    return {"code": "output_part_failed", "part": part, "detail": "%s: %s" % (type(e).__name__, str(e)[:200]),
            "sentence": "Chưa lưu được phần \"%s\" vào thư mục output (%s). Phần khác vẫn được lưu; thử lại bằng `bti output <dự án>`." % (words.PART_LABEL.get(part, part), str(e)[:120] or type(e).__name__)}


def sync(project_dir: Path, output_root: Path, *, moment: str = "rebuild", explicit: bool = False, job: dict | None = None, tools: Any = None, clean: bool | None = None,
         busy: Callable[[], dict | None] | None = None, sheets: bool = True, force: bool = False) -> dict:
    """Bring the output folder of this project up to date. `explicit`: the rebuild command (it also takes a folder over from another project). `job`: the long job that is calling, as
    {"id", "kind"} (its record still says running; it is written as done). `clean`: remove the working folder's caches when the export stands (None: only at the moments of
    `CLEAN_MOMENTS`, and then only when the switch is on). `tools`: an `export.render.Tools` (ffmpeg) for the contact sheets; None makes them from the settings. `sheets=False`: no contact sheets."""
    pdir = Path(project_dir)
    f = F.collect(pdir)
    if not f.eligible:
        if explicit:
            raise NotApplicable(f.skip_reason or "not_eligible")
        return {"key": f.key, "skipped": f.skip_reason, "written": [], "warnings": []}
    if job and job.get("id"):
        for j in f.jobs:
            if j["id"] == job["id"] and j["state"] in ("queued", "waiting", "running"):
                j["state"], j["finished"] = "done", time.time()
    out_root = Path(output_root)
    folder = folder_of(out_root, f.key)
    with _lock(folder):
        prev = read_state(folder)
        if not _owner_gives_way(prev, f, explicit, pdir.parent):
            return {"key": f.key, "skipped": "older_project", "written": [], "warnings": []}
        fsutil.ensure_dir(folder)
        fsutil.sweep_parts(folder)
        for stale in folder.glob(".frames-*"):          # the scratch folder of a contact-sheet run that was cut short
            if stale.is_dir() and not stale.is_symlink():
                import shutil
                shutil.rmtree(stale, ignore_errors=True)
        takeover = prev is not None and prev.get("project") != f.pid
        if takeover:
            purge_content(folder)
        st_parts: dict[str, dict] = {} if takeover or not prev else dict(prev.get("parts") or {})
        fp = fingerprint(f)
        want_clean = bool(clean) if clean is not None else moment in CLEAN_MOMENTS
        rewrite = explicit or force                      # a rebuild writes every settled part again (a file whose content is the same is left alone)
        plan = _plan(f, folder, st_parts, rewrite)
        blocking = [w for w in (prev or {}).get("warnings") or [] if w.get("code") != "output_sheets_failed"]       # a video that cannot be cut into frames is not tried again at every change
        if (not force and not explicit and not want_clean and prev and not takeover and prev.get("fingerprint") == fp and not blocking
                and all(action == "keep" or (action == "mark" and _marked(st_parts[part], why)) for part, (action, why, _rev) in plan.items())):
            return {"key": f.key, "folder": str(folder), "skipped": "unchanged", "written": [], "warnings": []}
        written: list[str] = []
        warnings: list[dict] = []
        stamp = now_iso()

        # --- the parts
        pictures_dirty = False
        for part in PART_IDS:
            action, why, now_rev = plan[part]
            pub = st_parts.get(part)
            if action == "write":
                try:
                    res = _write_part(part, f, folder, tools, sheets, moment, warnings)
                except Exception as e:      # noqa: BLE001 - one part never stops the others
                    log.warning("output: part %s of %s could not be written", part, f.pid, exc_info=True)
                    warnings.append(_warning(part, e))
                    if pub and not _files_exist(folder, pub):
                        st_parts.pop(part, None)          # what the state says is there is not: do not claim it
                    continue
                res.update(at=stamp, out_of_date=False, reason=None)
                st_parts[part] = {**(pub or {}), **res}
                written += res.get("files") or []
                if part == "storyboard":
                    pictures_dirty = True
            elif action == "mark":
                st_parts[part] = {**pub, "out_of_date": True, "reason": why}
        # the pictures part narrows to what the approved storyboard shows, and follows it when it is rewritten
        pp = st_parts.get("pictures")
        if pp and f.picks_ok and f.sb_approval == "fresh" and (pictures_dirty or pp.get("basis") != "storyboard") and not pp.get("out_of_date"):
            try:
                res = P.write_pictures(f, folder, basis_storyboard=True)
                st_parts["pictures"] = {**pp, **res, "at": stamp, "out_of_date": False, "reason": None}
                written += res.get("files") or []
            except Exception as e:      # noqa: BLE001
                log.warning("output: the pictures of %s could not be narrowed to the storyboard", f.pid, exc_info=True)
                warnings.append(_warning("pictures", e))
        # the contact sheets of the video (they need the video and the storyboard it was made from)
        ex = st_parts.get("export")
        retry = rewrite or moment in CLEAN_MOMENTS
        if sheets and ex and not ex.get("out_of_date") and f.export_ok and (rewrite or not ex.get("sheets") or ex.get("sheets_for") != ex.get("rev") or not all((folder / x).exists() for x in ex["sheets"])):
            if ex.get("sheets_error_for") == ex.get("rev") and not retry:
                warnings += [w for w in (prev or {}).get("warnings") or [] if w.get("code") == "output_sheets_failed"]
            else:
                try:
                    ff = _ffmpeg(tools)
                    names = P.write_contact_sheets(f, folder, ff[0], ff[1])
                    ex["sheets"], ex["sheets_for"] = names, ex.get("rev")
                    ex.pop("sheets_error_for", None)
                    written += names
                except Exception as e:      # noqa: BLE001 - the video is there; the sheets are a convenience
                    log.warning("output: the contact sheets of %s could not be made", f.pid, exc_info=True)
                    ex["sheets_error_for"] = ex.get("rev")
                    warnings.append({"code": "output_sheets_failed", "part": "export", "detail": "%s: %s" % (type(e).__name__, str(e)[:200]),
                                     "sentence": "Chưa làm được các tờ ảnh tổng hợp của video (%s). Video vẫn được lưu; thử lại bằng `bti output <dự án>`." % (str(e)[:120] or type(e).__name__)})
        # --- the log
        st_log = _write_log(f, folder, prev if not takeover else None, warnings)
        # --- cleaning (only after a successful export)
        clean_rec = (prev or {}).get("clean") if not takeover else None
        if want_clean:
            clean_rec = _clean(f, moment, job, busy)
        # --- state.json, README.md, the index
        st = _build_state(f, st_parts, prev, takeover, stamp, moment, fp, warnings, clean_rec, st_log, pdir)
        fsutil.write_text(folder / README_FILE, readme.readme_md(f, st))
        fsutil.write_json(folder / STATE_FILE, st)
        try:
            index.update(out_root)
        except Exception:       # noqa: BLE001 - the index is rebuilt by the next sync
            log.warning("output: the index could not be written", exc_info=True)
        return {"key": f.key, "folder": str(folder), "skipped": None, "written": written, "parts": {k: {x: v.get(x) for x in ("rev", "out_of_date", "reason")} for k, v in st_parts.items()},
                "warnings": warnings, "clean": clean_rec, "takeover": takeover}


def _plan(f, folder: Path, st_parts: dict, rewrite: bool = False) -> dict:
    """For each part: ("write" | "keep" | "mark" | "none", why, the revision now). `write`: it is settled and not yet written (or written from another revision, or its files are gone);
    `mark`: it was written, it is not settled now, and its document changed or its approval was withdrawn (`why`); `keep`: nothing to do."""
    out = {}
    for part in PART_IDS:
        pub = st_parts.get(part)
        settled = _settled(f, part)
        now_rev = _sources_rev(f) if part == "sources" else _rev_now(f, part)
        exists = True if part == "sources" else now_rev is not None
        if settled and exists:
            current = bool(pub and pub.get("rev") == now_rev and not pub.get("out_of_date") and _files_exist(folder, pub)) and not rewrite
            out[part] = ("keep" if current else "write", None, now_rev)
        elif pub:
            out[part] = ("mark", "changed" if (exists and now_rev != pub.get("rev")) or not exists else "approval_withdrawn", now_rev)
        else:
            out[part] = ("none", None, now_rev)
    return out


def _marked(pub: dict, why: str | None) -> bool:
    return bool(pub.get("out_of_date")) and pub.get("reason") == why


def _ffmpeg(tools: Any) -> tuple[list[str], dict | None]:
    if tools is None:
        from bti.export.render import Tools
        from bti.export.settings import load_settings
        tools = Tools.from_settings(load_settings())
    return list(tools.ffmpeg), getattr(tools, "env", None)


def _write_part(part: str, f, folder: Path, tools: Any, sheets: bool, moment: str, warnings: list) -> dict:
    if part == "pictures":
        return P.write_pictures(f, folder, basis_storyboard=f.sb_approval == "fresh")
    return _writer(part)(f, folder)


def _write_log(f, folder: Path, prev: dict | None, warnings: list) -> dict:
    label_of = P.label_of_factory(str((f.sb or {}).get("style") or "gae"))
    d = folder / LOG_DIR
    # the jobs: what the records say now, plus the rows of earlier runs of this project that the app has since pruned
    old = fsutil.read_json(d / "jobs.json") if prev else None
    rows = {r["id"]: r for r in (old.get("jobs") if isinstance(old, dict) and old.get("project") == f.pid else []) if isinstance(r, dict) and r.get("id")}
    rows.update({r["id"]: r for r in f.jobs})
    jobs = sorted(rows.values(), key=lambda r: (r.get("created") or 0, r["id"]))
    fsutil.write_json(d / "jobs.json", {"project": f.pid, "jobs": jobs})
    fsutil.write_text(d / "jobs.md", render.jobs_md(f, jobs, label_of))
    fsutil.write_text(d / "changes.md", render.changes_md(f, label_of))
    auto = render.auto_md(f, P.action_label)
    if auto:
        fsutil.write_text(d / "auto_runs.md", auto)
    else:
        fsutil.remove(d / "auto_runs.md")
    return {"changes": len(f.changes), "jobs": len(jobs), "auto_runs": len(f.auto_runs)}


def _clean(f, moment: str, job: dict | None, busy: Callable[[], dict | None] | None) -> dict:
    from bti import settings as S
    from . import clean as C
    if not f.export_ok:
        return {"done": False, "reason": "export_failed", "at": now_iso()}
    if (f.export_manifest or {}).get("report_status") == "error":
        return {"done": False, "reason": "export_failed", "at": now_iso()}
    if not S.get_output_settings()["clean_after_export"]:
        return {"done": False, "reason": "switched_off", "at": now_iso()}
    if busy is None:
        busy = _default_busy(f.pid, (job or {}).get("id"))
    return C.clean_project(f.pdir, busy=busy, keep_logs={job["id"]} if job and job.get("id") else set())


def _default_busy(pid: str, own_job: str | None) -> Callable[[], dict | None]:
    """A long job of the project that is running and is not the caller's own: it may be writing the very files the cleaning would remove. (The automatic run only watches: it is let through.)"""
    def busy():
        try:
            from bti.longjob import manager
            for kind in ("voice", "draft", "picks", "export"):
                j = manager.active(pid, kind)
                if j and j.get("id") != own_job:
                    return j
        except Exception:       # noqa: BLE001 - no runner, no running job
            return None
        return None
    return busy


def _build_state(f, st_parts: dict, prev: dict | None, takeover: bool, stamp: str, moment: str, fp: str, warnings: list, clean_rec: dict | None, st_log: dict, pdir: Path) -> dict:
    """The new state.json. The runs are kept whoever made them; everything else of an earlier project is dropped when this one takes the folder over."""
    prev = prev or {}
    runs = [dict(r) for r in (prev.get("runs") or [])]
    if takeover:
        prev = {}
    reached_prev = prev.get("reached") or {}
    ev = F.event_times(f)
    reached = {s["step"]: (ev.get(s["step"]) or reached_prev.get(s["step"]) or stamp) for s in f.steps if s["state"] == "done"}
    steps = [{"step": s["step"], "label": s["label"], "state": s["state"], "reached": reached.get(s["step"])} for s in f.steps]
    furthest = next((s["step"] for s in reversed(f.steps) if s["state"] == "done"), None)
    if runs and runs[-1].get("project") == f.pid:
        runs[-1].update(last_write=stamp, reached=furthest, writes=int(runs[-1].get("writes") or 0) + 1)
    else:
        runs.append({"project": f.pid, "first_write": stamp, "last_write": stamp, "reached": furthest, "writes": 1})
    exp = st_parts.get("export") or {}
    video = (exp.get("video") or prev.get("video")) if exp.get("rev") else None
    out = {
        "schema": SCHEMA, "key": f.key,
        "artwork": {"key": f.meta.get("artwork_key") or f.key, "title": f.title, "artist": f.artist, "year": f.year},
        "project": f.pid, "project_created": f.created, "updated": F.last_event(f) or prev.get("updated") or stamp,
        "current": f.current, "status": "done" if (video and not exp.get("out_of_date")) else "in_progress",
        "steps": steps, "reached": reached,
        "gates": {g: ({"approved": True, "by": a.get("by"), "at": a.get("at"), "stands": a.get("stands")} if a else None) for g, a in f.approvals.items()},
        "agents": f.agents, "video": video,
        "parts": {k: {x: v.get(x) for x in ("rev", "at", "files", "out_of_date", "reason", "basis", "count", "counts", "regions", "unused_left_out", "missing", "sheets", "sheets_for",
                                              "duration", "words", "sheets_error_for") if x in v} for k, v in st_parts.items()},
        "revisions": {"outline": (st_parts.get("outline") or {}).get("rev"), "narration": (st_parts.get("narration") or {}).get("rev"), "voice": (st_parts.get("voice") or {}).get("rev"),
                      "picks": (st_parts.get("pictures") or {}).get("rev"), "storyboard": (st_parts.get("storyboard") or {}).get("rev"), "export": exp.get("rev")},
        "clean": clean_rec, "log": st_log, "warnings": warnings, "last_sync": {"moment": moment, "at": stamp}, "fingerprint": fp, "runs": runs,
    }
    return out
