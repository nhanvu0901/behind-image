"""The title document of a project: `projects/<pid>/title.json` (schema `bti.title/1`), written atomically, with a revision (sha1 of the canonical JSON, the way
`agent.json` and `auto.json` have theirs).

    {"schema": "bti.title/1",
     "chosen": {"text", "by", "at", "source": "agent" | "person", "option": n | null},   the title in use; `by` is `agent:<model id>` or the actor that set it
     "candidates": [{"text", "form", "lines", "scores", "why"}],                         what the agent returned (the first one was its choice)
     "narration_rev": "<rev>",                                                           the narration revision the candidates were written from
     "written": {"at", "model", "agent", "note", "job_id", "session"} | null,            how the last generation went
     "history": [{"text", "by", "at", "source"}]}                                        the titles that were in use before (oldest first, at most KEEP)

Its state (`state_of`): `none` (no document, or none with a title), `done`, `stale` (an agent's title whose narration was changed since: the revision of the
narration now is not the one it was written from). A title SET by a person or an operator (`chosen.source` is `person`) is never stale, and a generation the
automatic run starts never replaces it (the state answer does not offer the action then); only a generation asked for by hand does.

Nothing here calls a model. `chosen_text(pdir)` never raises: it is what the storyboard compiler, the export and the output folder read."""
from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any

from bti.script import store as sstore

from . import check as C
from . import rules as R

SCHEMA = "bti.title/1"
FILE = "title.json"
KEEP = 20                       # titles kept in `history`
STATES = ("none", "done", "stale")


class TitleError(Exception):
    """A refusal: `code` is the stable word (a sentence in texts.VI, errmsg.js and hints.py), `status` the HTTP status."""

    def __init__(self, code: str, message: str, status: int = 422, **extra: Any):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra


def empty_doc() -> dict:
    return {"schema": SCHEMA, "chosen": None, "candidates": [], "narration_rev": None, "written": None, "history": []}


def revision(doc: dict) -> str:
    return sstore.revision(doc)


EMPTY_REV = revision(empty_doc())            # the revision of a project with no title yet (what a first PUT sends as `base_rev`)


def project_file(pdir: Path | str) -> Path:
    return Path(pdir) / FILE


_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()


def lock(pdir: Path | str) -> threading.RLock:
    key = str(Path(pdir).resolve())
    with _GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


# ------------------------------------------------------------------------------------------------ reading
def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _chosen(raw: Any) -> dict | None:
    if not isinstance(raw, dict) or not _str(raw.get("text")).strip():
        return None
    opt = raw.get("option")
    return {"text": _str(raw["text"]).strip(), "by": _str(raw.get("by")) or None, "at": _str(raw.get("at")) or None,
            "source": "person" if raw.get("source") == "person" else "agent",
            "option": opt if isinstance(opt, int) and not isinstance(opt, bool) and opt > 0 else None}


def _candidate(raw: Any) -> dict | None:
    if not isinstance(raw, dict) or not _str(raw.get("text")).strip():
        return None
    sc = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    return {"text": _str(raw["text"]).strip(), "form": raw.get("form") if raw.get("form") in R.FORMS else "other",
            "lines": [x for x in (raw.get("lines") or []) if isinstance(x, str)][:R.LINES_MAX] if isinstance(raw.get("lines"), list) else [],
            "scores": {k: sc[k] for k in R.SCORE_KEYS if isinstance(sc.get(k), int) and not isinstance(sc.get(k), bool)},
            "why": _str(raw.get("why")).strip()}


def normalize(raw: Any) -> dict:
    """The full document, whatever `raw` is: what cannot be read is dropped (a document that holds no title counts as none)."""
    doc = empty_doc()
    if not isinstance(raw, dict):
        return doc
    doc["chosen"] = _chosen(raw.get("chosen"))
    doc["candidates"] = [c for c in (_candidate(x) for x in raw["candidates"]) if c is not None][:R.MAX_CANDIDATES] if isinstance(raw.get("candidates"), list) else []
    doc["narration_rev"] = raw["narration_rev"] if isinstance(raw.get("narration_rev"), str) and raw["narration_rev"] else None
    w = raw.get("written")
    doc["written"] = copy.deepcopy(w) if isinstance(w, dict) else None
    hist = raw.get("history") if isinstance(raw.get("history"), list) else []
    doc["history"] = [h for h in ({"text": _str(x.get("text")).strip(), "by": _str(x.get("by")) or None, "at": _str(x.get("at")) or None,
                                   "source": "person" if x.get("source") == "person" else "agent"} for x in hist if isinstance(x, dict)) if h["text"]][-KEEP:]
    return doc


def read(pdir: Path | str) -> tuple[dict, str | None]:
    """(the normalised document, a problem sentence or None). No file is the empty document; a file that cannot be read is the empty document too, with the problem
    named (the next write replaces it)."""
    try:
        raw = sstore.read_object(project_file(pdir), "title")
    except sstore.DocumentCorrupt as e:
        return empty_doc(), str(e)
    return (normalize(raw) if raw is not None else empty_doc()), None


def narration_rev(pdir: Path | str) -> str | None:
    """The revision of the narration now (None when there is none or it cannot be read)."""
    try:
        n = sstore.load_narration(Path(pdir))
        return n.rev() if n is not None else None
    except Exception:       # noqa: BLE001 - a damaged narration is the script step's problem
        return None


def state_of(doc: dict, current_rev: str | None) -> str:
    ch = doc.get("chosen")
    if not ch:
        return "none"
    if ch.get("source") == "person":
        return "done"
    written = doc.get("narration_rev")
    return "stale" if (written and current_rev and written != current_rev) else "done"


def state(pdir: Path | str) -> str:
    """none | done | stale of the project's title (never raises)."""
    try:
        doc, _ = read(pdir)
        return state_of(doc, narration_rev(pdir))
    except Exception:       # noqa: BLE001
        return "none"


def chosen_text(pdir: Path | str) -> str | None:
    """The title in use (one line), or None when the project has none. Never raises: the storyboard compiler, the export and the output folder call it."""
    try:
        doc, _ = read(pdir)
    except Exception:       # noqa: BLE001
        return None
    ch = doc.get("chosen")
    return ch["text"] if ch else None


# ------------------------------------------------------------------------------------------------ writing
def _write(pdir: Path | str, doc: dict) -> None:
    sstore.write_json_atomic(project_file(pdir), doc, levels=0)      # levels 0: a deleted project folder is never made again (ProjectGone)


def _push_history(doc: dict) -> None:
    ch = doc.get("chosen")
    if ch:
        doc["history"] = (doc.get("history") or []) + [{"text": ch["text"], "by": ch.get("by"), "at": ch.get("at"), "source": ch.get("source")}]
        doc["history"] = doc["history"][-KEEP:]


def set_title(pdir: Path | str, *, base_rev: Any, actor: str, text: Any = None, option: Any = None, at: str | None = None) -> dict:
    """A person or an operator sets the title: `text` (one line, at most R.PERSON_MAX_CHARS characters) or `option` (the number, from 1, of a candidate the agent
    returned). -> the new document. TitleError: 422 `title_invalid` / `title_not_one_line` / `title_too_long` / `title_option_unknown` / `title_choice_needed`,
    409 `stale_revision` (`rev` is the revision now). Nothing is written on a refusal."""
    if not isinstance(base_rev, str) or not base_rev:
        raise TitleError("invalid_request", "base_rev (string) is required", 422, field="base_rev")
    if (text is None) == (option is None):
        raise TitleError("title_choice_needed", "send `text` (a title) or `option` (the number of a candidate), one of them", 422)
    with lock(pdir):
        doc, problem = read(pdir)
        cur = revision(doc)
        if base_rev != cur:
            raise TitleError("stale_revision", "the title changed since you loaded it; reload before saving", 409, rev=cur)
        chosen_option = None
        if option is not None:
            cands = doc["candidates"]
            if isinstance(option, bool) or not isinstance(option, int) or not 1 <= option <= len(cands):
                raise TitleError("title_option_unknown", "option must be the number (from 1) of a candidate: there are %d" % len(cands), 422, field="option")
            new_text, chosen_option = cands[option - 1]["text"], option
        else:
            new_text, bad = C.check_text(text)
            if bad:
                raise TitleError(bad, {"title_invalid": "text must be the title, as text (not empty)",
                                       "title_not_one_line": "text must be one line",
                                       "title_too_long": "text is longer than %d characters" % R.PERSON_MAX_CHARS}[bad], 422, field="text")
            chosen_option = next((i for i, c in enumerate(doc["candidates"], 1) if c["text"] == new_text), None)
        from bti.script.store import now_iso
        new = copy.deepcopy(doc)
        cur_ch = doc.get("chosen")
        if not (cur_ch and cur_ch["text"] == new_text and cur_ch.get("source") == "person" and cur_ch.get("by") == actor):
            _push_history(new)
        new["chosen"] = {"text": new_text, "by": actor, "at": at or now_iso(), "source": "person", "option": chosen_option}
        _write(pdir, new)
        return new


def write_generated(pdir: Path | str, candidates: list, *, by: str, narration_rev_: str | None, written: dict, at: str | None = None) -> dict:
    """The end of a generation: the candidates the agent returned and their first one as the title in use. The title that was in use goes to `history`. -> the document."""
    from bti.script.store import now_iso
    with lock(pdir):
        doc, _ = read(pdir)
        new = copy.deepcopy(doc)
        _push_history(new)
        new["candidates"] = copy.deepcopy(candidates)
        new["chosen"] = {"text": candidates[0]["text"], "by": by, "at": at or now_iso(), "source": "agent", "option": 1}
        new["narration_rev"] = narration_rev_
        new["written"] = written
        _write(pdir, new)
        return new
