"""What the title step says about itself: the answer of `GET /api/projects/{pid}/title` and the short summary the state answer carries (`title`).

    overview(pid, pdir)  -> {rev, state, title, candidates, narration_rev, current_narration_rev, stale, agent, running, history, written, limits, storyboard, problems}
    summary(pdir)        -> {state, text, by, at, source, candidates, stale}     (the state answer; never raises)

`state`: `none` (no title yet), `done`, `stale` (an agent's title written from a narration that has changed since). `title` is the title in use ({text, by, at, source,
option}), `candidates` what the agent returned (the first was its choice), `storyboard` what the saved storyboard shows now ({exists, title, same, off_voice}): `off_voice` is
true while the storyboard does not sit where the voice puts its cards (`bti.draft.retime.project_off_voice`): it cannot take a title until `storyboard.retime` has fitted it."""
from __future__ import annotations

import json
from pathlib import Path

from bti.draft import retime as draft_retime, run as draft_run

from . import job, rules as R, store


def _storyboard_title(pdir: Path) -> dict:
    f = Path(pdir) / "storyboard.json"
    if not f.is_file():
        return {"exists": False, "title": None}
    try:
        sb = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"exists": True, "title": None}
    ident = sb.get("identity") if isinstance(sb, dict) else None
    t = ident.get("video_title") if isinstance(ident, dict) else None
    return {"exists": True, "title": t if isinstance(t, str) and t else None}


def overview(pid: str, pdir: Path) -> dict:
    pdir = Path(pdir)
    doc, problem = store.read(pdir)
    cur = store.narration_rev(pdir)
    st = store.state_of(doc, cur)
    res = draft_run._resolve(pdir, job.ROLE, None)
    sb = _storyboard_title(pdir)
    sb["off_voice"] = bool(sb["exists"] and draft_retime.project_off_voice(pdir))          # never raises: a storyboard that cannot be read says nothing here
    chosen = doc["chosen"]
    problems = [{"code": "document_corrupt", "detail": problem}] if problem else []
    return {"rev": store.revision(doc), "state": st, "title": chosen, "candidates": doc["candidates"], "narration_rev": doc["narration_rev"], "current_narration_rev": cur,
            "stale": st == "stale", "agent": res.public(), "running": job.active_job(pid), "history": doc["history"], "written": doc["written"], "limits": R.public(),
            "storyboard": {**sb, "same": bool(sb["exists"] and chosen and sb["title"] == chosen["text"])}, "problems": problems}


def summary(pdir: Path) -> dict:
    """For the state answer. Never raises."""
    try:
        doc, problem = store.read(pdir)
        st = store.state_of(doc, store.narration_rev(pdir))
        ch = doc["chosen"] or {}
        return {"state": st, "text": ch.get("text"), "by": ch.get("by"), "at": ch.get("at"), "source": ch.get("source"), "candidates": len(doc["candidates"]),
                "stale": st == "stale", **({"problem": problem} if problem else {})}
    except Exception:       # noqa: BLE001
        return {"state": "none", "text": None, "by": None, "at": None, "source": None, "candidates": 0, "stale": False}
