"""What a project says about itself, read once and read-only: the documents of the steps, their approvals and revisions, the long jobs, the change log, the automatic runs.

`collect(pdir)` never raises: a file that cannot be read is a sentence in `problems` and the fact stays empty. Nothing here writes, locks or starts anything, and nothing here asks the
engine or a model (the shot times are `times.py`). The stage questions that are not plain files (is the voice done? the export?) live in three small functions
(`voice_done`, `picks_done`, `export_done`) so a test can stand in for them.

The state of a step is made here from the documents, the way the page's step bar makes it, but without "running": a job that is running when this is read (the one that is calling,
at its last part) does not hide what it has just made."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bti.script import store as sstore

from . import words

log = logging.getLogger("bti.output")

GATES = ("outline", "narration", "picks", "storyboard")


class _Idle:
    """A long-job manager that never has a job running (the voice state asks it)."""

    def active(self, pid, kind=None):
        return None


@dataclass
class Facts:
    pid: str
    pdir: Path
    meta: dict = field(default_factory=dict)
    key: str = ""
    title: str = ""
    artist: str = ""
    year: str = ""
    created: str | None = None
    eligible: bool = True
    skip_reason: str | None = None
    outline: Any = None
    narration: Any = None
    outline_ok: bool = False
    narration_ok: bool = False
    outline_rev: str | None = None
    narration_rev: str | None = None
    title_doc: dict | None = None        # titlestep: the title document when it holds a title (bti.title.store), else None
    title_rev: str | None = None
    title_state: str = "none"            # none | done | stale
    picks: dict | None = None
    picks_ok: bool = False
    picks_rev: str | None = None
    sb: dict | None = None
    sb_rev: str | None = None
    sb_approval: str = "none"            # none | fresh | stale (bti.editor.common.storyboard_approval)
    timing: dict | None = None
    timing_sha: str | None = None
    voice_manifest: dict | None = None
    voice_ok: bool = False
    export_manifest: dict | None = None
    export_ok: bool = False
    export_reason: str | None = None
    approvals: dict = field(default_factory=dict)     # gate -> {by, at, stands} | None
    steps: list = field(default_factory=list)         # [{step, label, state}]
    current: str | None = None
    jobs: list = field(default_factory=list)
    changes: list = field(default_factory=list)
    auto_runs: list = field(default_factory=list)
    agents: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)


def title_public(f: "Facts") -> dict | None:
    """The title as `state.json` and the README name it: {text, by, at, source, state, candidates}; None when the project has none."""
    d = f.title_doc
    ch = (d or {}).get("chosen")
    if not ch:
        return None
    return {"text": ch["text"], "by": ch.get("by"), "at": ch.get("at"), "source": ch.get("source"), "state": f.title_state, "candidates": len((d or {}).get("candidates") or [])}


def sha_file(path: Path) -> str | None:
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def sig_file(path: Path) -> str | None:
    """A cheap signature of a big file: its size and its modification time."""
    try:
        st = Path(path).stat()
        return "%d-%d" % (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------ the three stage questions
def voice_done(pdir: Path, pid: str) -> bool:
    """Is the voice made and current (`bti.voice.describe`, with no job counted as running)?"""
    from bti.voice import describe
    return describe(Path(pdir), pid, manager=_Idle(), full=False)["state"] == "done"


def picks_done(pdir: Path, picks: dict | None) -> bool:
    from bti.picks import context, doc
    nv = context.narration_view(Path(pdir))
    return bool(picks is not None and doc.approval_state(picks, nv["rev"], nv["approved"])["approved"])


def export_done(pdir: Path) -> tuple[dict | None, bool, str | None]:
    """(manifest, the export stands, why not): the video and its files are there and the storyboard and the audio are the ones it was made from."""
    from bti.export import run
    m = run.read_manifest(Path(pdir))
    if m is None:
        return None, False, "none"
    reason = run.stale_reason(Path(pdir), m)
    return m, reason is None, reason


# ------------------------------------------------------------------------------------------------ the readers
def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_JOB_CACHE: dict[tuple, dict | None] = {}          # (path, mtime_ns, size) -> the row of that record: a record can hold a megabyte of log lines, so it is read once


def _job_row(path: Path, script: bool) -> dict | None:
    try:
        st = path.stat()
    except OSError:
        return None
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _JOB_CACHE:
        return _JOB_CACHE[key]
    r = _read_json(path)
    row = None
    if isinstance(r, dict) and isinstance(r.get("id"), str):
        meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
        raw_agent = r.get("agent") if script else meta.get("agent")
        ag = raw_agent if isinstance(raw_agent, dict) else {}
        model = r.get("model") if script else meta.get("model")
        kind = str(r.get("kind") or "")
        detail, names = "", ""
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        if kind == "draft" and meta.get("mode") == "edit":
            kind, detail = "edit", words.one_line(meta.get("instruction") or "", 240)
        elif kind == "title":
            detail = words.one_line(res.get("title") or "", 120)          # titlestep
        elif kind == "draft":
            detail = ("%s cảnh" % res["n_shots"]) if res.get("n_shots") else ""
        elif kind == "picks" and meta.get("action") == "edit":
            kind, detail = "picks_edit", words.one_line(meta.get("instruction") or "", 240)
        elif kind == "picks":
            if res.get("lines_total") is not None:
                detail = "%s/%s dòng có hình" % (res.get("lines_with_pictures"), res.get("lines_total"))
        elif kind == "voice":
            names = " + ".join(str(x) for x in (meta.get("provider"), meta.get("aligner")) if x)          # the voice has no agent: who made it is the voice engine and the aligner
            detail = ("%s câu" % meta["chunks"]) if meta.get("chunks") else ""
        elif kind == "export" and res.get("report_status"):
            detail = "kiểm tra: " + str(res["report_status"])
            if res.get("parts_rendered") is not None and res.get("parts_reused") is not None:
                detail += " · dựng mới %d, dùng lại %d đoạn" % (res["parts_rendered"], res["parts_reused"])
        elif kind in ("outline", "narration"):
            ch = r.get("chapters") if isinstance(r.get("chapters"), list) else []
            detail = str(ch[0].get("message") or "") if kind == "outline" and ch and isinstance(ch[0], dict) else ("%d chương" % len(ch) if ch else "")
        who = ag.get("label") or (names or None if kind == "voice" else None)
        row = {"id": r["id"], "kind": kind, "agent": who, "model": model if isinstance(model, str) else None,
               "created": r.get("created") if isinstance(r.get("created"), (int, float)) else None,
               "finished": r.get("finished") if isinstance(r.get("finished"), (int, float)) else None,
               "state": str(r.get("state") or ""), "error_code": r.get("error_code") or r.get("error_kind"),
               "error": words.one_line(r.get("error") or "", 300), "detail": detail}
    if len(_JOB_CACHE) > 2000:
        _JOB_CACHE.clear()
    _JOB_CACHE[key] = row
    return row


def read_jobs(pdir: Path) -> list[dict]:
    """The long jobs of the project from their records (`cache/jobs` for the script, `cache/longjobs` for the rest), oldest first, as plain rows."""
    rows: dict[str, dict] = {}
    for sub, script in (("jobs", True), ("longjobs", False)):
        d = Path(pdir) / "cache" / sub
        try:
            files = sorted(d.glob("*.json"))
        except OSError:
            continue
        for f in files:
            row = _job_row(f, script)
            if row is not None:
                rows[row["id"]] = dict(row)
    return sorted(rows.values(), key=lambda x: (x["created"] or 0, x["id"]))


def read_changes(pdir: Path) -> list[dict]:
    """The records of the change log, oldest first, each with `undone_by`."""
    from bti.ops.log import ChangeLog
    d = Path(pdir) / "changes"
    if not d.is_dir():
        return []
    recs = ChangeLog(pdir).list(limit=100000)
    return list(reversed(recs))


def read_auto_runs(pdir: Path) -> list[dict]:
    d = Path(pdir) / "auto_runs"
    out = []
    try:
        files = sorted(d.glob("*.json"))
    except OSError:
        return out
    for f in files:
        r = _read_json(f)
        if isinstance(r, dict) and isinstance(r.get("id"), str):
            out.append(r)
    return out


def _agent_label(pdir: Path, role: str) -> str | None:
    try:
        from bti import agents as AG
        return AG.model_for_project(Path(pdir), role).label
    except Exception:       # noqa: BLE001 - a label that cannot be read is simply left out
        return None


def _approval(record: Any, stands: bool, at_key: str = "approved_at") -> dict | None:
    if not isinstance(record, dict) or not (record.get("approved") is True or record.get(at_key) or record.get("at") or record.get("rev")):
        return None
    by = record.get("by")
    return {"by": by if isinstance(by, str) and by else None, "at": record.get(at_key) or record.get("at"), "stands": bool(stands)}


# ------------------------------------------------------------------------------------------------ collect
def collect(pdir: Path, *, jobs: bool = True) -> Facts:
    pdir = Path(pdir)
    f = Facts(pid=pdir.name, pdir=pdir)
    prob = f.problems.append

    # the project itself
    try:
        f.meta = sstore.read_object(pdir / "project.json", "project") or {}
    except Exception as e:      # noqa: BLE001
        prob("project.json cannot be read: %s" % str(e)[:150])
    if not (pdir / "project.json").is_file():
        f.eligible, f.skip_reason = False, "no_project_file"
    elif f.meta.get("protected") is True:
        f.eligible, f.skip_reason = False, "protected"
    elif f.meta.get("imported") is True:
        f.eligible, f.skip_reason = False, "imported"
    from .paths import folder_key
    f.key = folder_key(f.meta, f.pid)
    f.created = f.meta.get("created_at") if isinstance(f.meta.get("created_at"), str) else None
    f.title, f.artist, f.year = (str(f.meta.get(k) or "") for k in ("title", "artist", "year"))

    # the script
    try:
        f.outline, f.narration = sstore.load_outline(pdir), sstore.load_narration(pdir)
        if f.outline is not None:
            f.outline_rev, f.outline_ok = f.outline.rev(), bool(f.outline.approved_fresh())
        if f.narration is not None:
            f.narration_rev = f.narration.rev()
            f.narration_ok = bool(sstore.narration_approval(f.narration, f.outline)["approved"])
    except Exception as e:      # noqa: BLE001
        prob("the script cannot be read: %s" % str(e)[:150])

    # the title (titlestep)
    try:
        from bti.title import store as tstore
        tdoc, tproblem = tstore.read(pdir)
        if tdoc.get("chosen"):
            f.title_doc, f.title_rev, f.title_state = tdoc, tstore.revision(tdoc), tstore.state_of(tdoc, f.narration_rev)
        if tproblem:
            prob("title.json cannot be read: %s" % tproblem[:150])
    except Exception as e:      # noqa: BLE001
        prob("the title cannot be read: %s" % str(e)[:150])

    # the picks
    try:
        from bti.picks import doc as pdoc
        f.picks = pdoc.load(pdir)
        if f.picks is not None:
            f.picks_rev = pdoc.revision(f.picks)
            f.picks_ok = bool(picks_done(pdir, f.picks))
    except Exception as e:      # noqa: BLE001
        prob("the picks cannot be read: %s" % str(e)[:150])

    # the storyboard
    try:
        from bti.editor.common import compute_rev, read_json, storyboard_approval
        if (pdir / "storyboard.json").is_file():
            sb = read_json(pdir / "storyboard.json")
            if isinstance(sb, dict):
                f.sb, f.sb_rev, f.sb_approval = sb, compute_rev(sb), storyboard_approval(sb)
    except Exception as e:      # noqa: BLE001
        prob("storyboard.json cannot be read: %s" % str(e)[:150])

    # the voice
    f.timing = _read_json(pdir / "timing.json")
    f.timing = f.timing if isinstance(f.timing, dict) else None
    f.timing_sha = sha_file(pdir / "timing.json") if f.timing is not None else None
    vm = _read_json(pdir / "voice" / "voice.json")
    f.voice_manifest = vm if isinstance(vm, dict) else None
    try:
        f.voice_ok = bool(f.voice_manifest is not None and voice_done(pdir, f.pid))
    except Exception as e:      # noqa: BLE001
        prob("the state of the voice cannot be read: %s" % str(e)[:150])

    # the export
    try:
        f.export_manifest, f.export_ok, f.export_reason = export_done(pdir)
    except Exception as e:      # noqa: BLE001
        prob("the export cannot be read: %s" % str(e)[:150])

    # who approved what
    f.approvals = {
        "outline": _approval(f.outline.approval, f.outline_ok) if f.outline is not None else None,
        "narration": _approval(f.narration.approval, f.narration_ok) if f.narration is not None else None,
        "picks": _approval(f.picks.get("approval"), f.picks_ok) if f.picks is not None else None,
        "storyboard": _approval((f.sb.get("approvals") or {}).get("storyboard") if isinstance((f.sb or {}).get("approvals"), dict) else None, f.sb_approval == "fresh") if f.sb else None,
    }

    # the steps
    f.steps, f.current = steps_of(f)

    # the logs
    if jobs:
        try:
            f.jobs = read_jobs(pdir)
        except Exception as e:      # noqa: BLE001
            prob("the job records cannot be read: %s" % str(e)[:150])
        try:
            f.changes = read_changes(pdir)
        except Exception as e:      # noqa: BLE001
            prob("the change log cannot be read: %s" % str(e)[:150])
        f.auto_runs = read_auto_runs(pdir)
    f.agents = agents_of(f)
    return f


def steps_of(f: Facts) -> tuple[list[dict], str | None]:
    """The six steps with one of: done, current, stale (made, but its approval or its input changed), locked."""
    sb_exists = f.sb is not None
    st: dict[str, str] = {"artwork": "done" if (f.pdir / "project.json").is_file() else "locked"}
    st["script"] = "done" if f.narration_ok else "current"
    narr = f.narration_ok
    if f.voice_ok:
        st["voice"] = "done"
    elif f.voice_manifest is not None and f.voice_manifest.get("finished_at"):
        st["voice"] = "stale"
    else:
        st["voice"] = "current" if narr else "locked"
    if f.picks_ok:
        st["picks"] = "done"
    elif f.picks is not None and (f.picks.get("approval") or {}).get("approved"):
        st["picks"] = "stale"
    else:
        st["picks"] = "current" if narr else "locked"
    if f.sb_approval == "fresh":
        st["edit"] = "done"
    elif sb_exists:
        st["edit"] = "current" if f.sb_approval == "none" else "stale"
    else:
        st["edit"] = "current" if (f.voice_ok and f.picks_ok) else "locked"
    if f.export_ok:
        st["export"] = "done"
    elif f.sb_approval == "fresh":
        st["export"] = "stale" if f.export_manifest is not None else "current"
    else:
        st["export"] = "locked"
    steps = [{"step": s, "label": words.STEP_LABEL[s], "state": st[s]} for s in words.STEP_ORDER]
    current = next((s["step"] for s in steps if s["state"] in ("current", "stale")), None)
    return steps, current


def agents_of(f: Facts) -> dict:
    """The agent of each step: the one that worked on it (the newest job that names one), else the project's choice."""
    by_step = {"script": ("outline", "narration"), "picks": ("picks", "picks_edit"), "edit": ("draft", "edit")}
    out: dict[str, str] = {}
    for step, kinds in by_step.items():
        names = [j["agent"] for j in f.jobs if j["kind"] in kinds and j.get("agent") and j.get("state") == "done"]
        label = names[-1] if names else _agent_label(f.pdir, {"script": "script.narration", "picks": "picks", "edit": "draft"}[step])
        if label:
            out[step] = label
    vj = [j for j in f.jobs if j["kind"] == "voice" and j.get("state") == "done" and j.get("agent")]
    if vj:
        out["voice"] = vj[-1]["agent"]
    return out


def event_times(f: Facts) -> dict:
    """The time each step was reached, from the documents' own stamps (never the clock)."""
    t = {"artwork": f.created}
    t["script"] = (f.approvals.get("narration") or {}).get("at") if f.narration_ok else None
    t["voice"] = (f.voice_manifest or {}).get("finished_at") if f.voice_ok else None
    t["picks"] = (f.approvals.get("picks") or {}).get("at") if f.picks_ok else None
    t["edit"] = (f.approvals.get("storyboard") or {}).get("at") if f.sb_approval == "fresh" else None
    t["export"] = (f.export_manifest or {}).get("created") if f.export_ok else None
    return t


def last_event(f: Facts) -> str | None:
    """The newest stamp the project's own documents carry (an ISO string), so a folder's 'updated' moves only when the project does."""
    cands = [v for v in event_times(f).values() if v]
    cands += [c.get("time") for c in f.changes if c.get("time")]
    cands += [v for a in f.approvals.values() if a for v in [a.get("at")] if v]
    cands = [c for c in cands if words.parse_time(c) is not None]
    return max(cands, key=lambda c: words.parse_time(c)) if cands else None
