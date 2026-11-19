"""Outline and narration data classes, atomic load/save, revisions and approvals.

Revision = sha1 of the canonical JSON of the document without its `approval` block. An approval stores the
revision it approved; any edit changes the revision, so the approval is dropped on save and is stale when
checked against a document that changed behind its back. Ids are never renumbered: new ids come from a
counter stored in the document, which only grows.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from bti.fsio import atomic_replace

SCHEMA_OUTLINE = "bti.outline/1"
SCHEMA_NARRATION = "bti.narration/1"
CERTAINTY = ("established", "likely", "disputed")
ROLES = ("cold_open", "chapter", "closing")
# The ids the rest of the code can read back. A chapter id is what the narration parser finds in a heading (`parse.CH_ID_RE`
# is built from this source); a beat id is what `Narration.new_beat_id` makes. Anything else is refused, never coerced.
CHAPTER_ID_SRC = r"c\d{1,6}"
CHAPTER_ID_RE = re.compile(CHAPTER_ID_SRC)
BEAT_ID_RE = re.compile(r"b\d{1,8}")
FACT_ID_RE = re.compile(r"f\d{1,8}")
HOOK_ID_RE = re.compile(r"h\d{1,6}")
MAX_NOTES = 5                       # remarks to the owner an outline keeps (the prompt asks for at most three)
MAX_NOTE_CHARS = 600


# ---------------------------------------------------------------- locks
# LOCK ORDER (every code path that takes more than one of these takes them in this order, and releases in the reverse):
#
#     1. script_lock(project)      this module: outline.json, narration.json and everything under script/
#     2. storyboard lock(project)  bti.editor.common.save_lock(): storyboard.json, history/, approvals
#     3. ENGINE_LOCK               bti.editor.engine_adapter: one engine call at a time (process wide)
#
# Who takes what: the script routes and the model job (when it finishes a chapter) take 1 only. The storyboard routes (save,
# approve, restore, regions, proposals apply) take 2, and inside it 3. DELETE of a project takes 1 then 2 (then 3 through
# `forget`), each with a 2 second limit: if it cannot get both, nothing is removed and the answer is 409. Previews hold their
# own per-project render lock, never 1 or 2. Nothing holds 3 and then asks for 1 or 2.
# Every writer, after it has its lock, checks that the project still exists (404 if not), and the write helpers never create
# a project folder (`make_parent`), so a writer that lost the race to a delete cannot bring the folder back.
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def script_lock(pdir: Path) -> threading.RLock:
    """The one lock of a project's script files. Every read-modify-write of outline.json / narration.json (a save from the
    page, an op, an approval, an import, and a model job that finishes a chapter) holds it, so none can overwrite another."""
    key = str(Path(pdir).resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def forget_lock(pdir: Path) -> None:
    """Drop the lock object of a project that was deleted (a later project with the same slug gets a new one)."""
    with _LOCKS_GUARD:
        _LOCKS.pop(str(Path(pdir).resolve()), None)


class StaleRevision(Exception):
    """The caller's revision is not the current one."""


class ProjectGone(FileNotFoundError):
    """A write was refused because the project folder (or the folder it belongs in) does not exist any more."""


class DocumentCorrupt(Exception):
    """A file of a project is not readable (not UTF-8, not JSON, or not an object). The message names the file; `what` is the
    stable code the page translates (`data_error` in the 409 answer): "script", "project", "source", "library"."""

    def __init__(self, message: str, what: str = "script"):
        super().__init__(message)
        self.what = what


def make_parent(path: Path, levels: int = 1) -> None:
    """Make the folder of `path` when at most `levels` folders are missing, and never more: the project folder itself is
    never re-created by a write (it would bring back a deleted project). `levels=1` suits `<project>/script/x.json`;
    `<project>/cache/previews/x.mp4` needs 2."""
    parent = Path(path).parent
    missing = 0
    probe = parent
    while not probe.exists():
        missing += 1
        if missing > levels or probe.parent == probe:
            raise ProjectGone(f"cannot write {Path(path).name}: the project folder is gone")
        probe = probe.parent
    if missing:
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except FileNotFoundError:
            raise ProjectGone(f"cannot write {Path(path).name}: the project folder is gone")


def _why(e: BaseException) -> str:
    """A short reason for the owner: no exception text, no path (the raw exception goes to the log only)."""
    import errno
    import logging
    logging.getLogger("bti.editor").info("project file not readable: %r", e)
    if isinstance(e, UnicodeDecodeError):
        return "it is not UTF-8 text"
    if isinstance(e, PermissionError):
        return "the server may not read it (permission denied)"
    if isinstance(e, IsADirectoryError):
        return "it is a folder, not a file"
    if isinstance(e, json.JSONDecodeError):
        return "it is not valid JSON (line %d, column %d)" % (e.lineno, e.colno)
    if isinstance(e, (RecursionError, ValueError)):
        return "it is not valid JSON"
    if isinstance(e, OSError) and e.errno == errno.ELOOP:
        return "it is a link that loops"
    return "it cannot be read"


def read_file_text(path: Path, what: str = "script", *, missing_ok: bool = True, errors: str = "strict") -> str | None:
    """THE reader of a project text file. The UTF-8 text of `path`; None when there is no such file (`missing_ok`) .
    DocumentCorrupt (naming the file by its name, with a short reason and no server path) when it is a folder, cannot be
    read, or is not UTF-8. Nothing is replaced silently, and a repaired file reads again at once (nothing is cached)."""
    import stat as _stat
    try:
        st = os.stat(path)
    except FileNotFoundError:
        st = None
    except NotADirectoryError:
        st = None
    except OSError as e:
        if getattr(e, "errno", None) == 40:                  # a link that loops: the file is not there
            st = None
        else:
            raise DocumentCorrupt("%s is corrupt: %s" % (Path(path).name, _why(e)), what)
    if st is None:
        if missing_ok:
            return None
        raise DocumentCorrupt("%s is missing" % Path(path).name, what)
    if not _stat.S_ISREG(st.st_mode):
        raise DocumentCorrupt("%s is corrupt: it is a folder, not a file" % Path(path).name, what)
    try:
        return Path(path).read_text(encoding="utf-8", errors=errors)
    except (OSError, UnicodeDecodeError) as e:
        raise DocumentCorrupt("%s is corrupt: %s" % (Path(path).name, _why(e)), what)


def read_object(path: Path, what: str = "script") -> dict | None:
    """The JSON object in `path`; None when there is no such file; DocumentCorrupt (naming the file) when it is there but is not
    readable, not UTF-8, not JSON, or not an object. Nothing is replaced silently."""
    text = read_file_text(path, what)
    if text is None:
        return None
    try:
        d = json.loads(text)
    except (ValueError, RecursionError) as e:
        raise DocumentCorrupt("%s is corrupt: %s" % (Path(path).name, _why(e)), what)
    if not isinstance(d, dict):
        raise DocumentCorrupt("%s is corrupt: the top level must be an object" % Path(path).name, what)
    return d


def read_text_strict(path: Path, what: str = "source") -> str:
    """UTF-8 text of `path`; DocumentCorrupt naming the file when it is missing, unreadable or not UTF-8."""
    return read_file_text(path, what, missing_ok=False)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def canonical_json(doc: dict) -> str:
    d = {k: v for k, v in doc.items() if k != "approval"}
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def revision(doc: dict) -> str:
    return hashlib.sha1(canonical_json(doc).encode("utf-8")).hexdigest()


def write_json_atomic(path: Path, data: Any, levels: int = 1) -> None:
    make_parent(path, levels)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_text_atomic(path: Path, text: str, levels: int = 1) -> None:
    make_parent(path, levels)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        atomic_replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _str(v: Any) -> str:
    return "" if v is None else str(v)


def _strs(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in v if str(x).strip()]


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError, OverflowError):
        return default


def _approval(a: Any) -> dict:
    """`sha1` is the revision of the document that was approved. A narration approval also keeps `outline_sha1`: the revision
    of the outline it was approved against (see `narration_approval`)."""
    a = a if isinstance(a, dict) else {}
    out = {"approved": bool(a.get("approved")), "sha1": a.get("sha1"), "approved_at": a.get("approved_at")}
    if a.get("outline_sha1"):
        out["outline_sha1"] = a["outline_sha1"]
    if isinstance(a.get("by"), str) and a["by"]:         # c5cli: who approved (`human`, `agent:...`, `cli:...`); absent in an approval made before this existed
        out["by"] = a["by"]
    return out


def _source(s: Any, kind: str = "manual") -> dict:
    s = s if isinstance(s, dict) else {}
    out = {"kind": s.get("kind") or kind, "model": _str(s.get("model")), "created_at": s.get("created_at") or now_iso()}
    for k in ("outline_sha1",):
        if s.get(k):
            out[k] = s[k]
    return out


def _numeric_tail(id_: str) -> int:
    digits = "".join(ch for ch in str(id_) if ch.isdigit())
    return int(digits) if digits else 0


# ---------------------------------------------------------------- outline
@dataclass
class Hook:
    id: str
    text: str = ""


@dataclass
class Fact:
    id: str
    claim: str = ""
    sources: list[str] = field(default_factory=list)
    certainty: str = "likely"
    conflict: str | None = None


@dataclass
class OChapter:
    id: str
    role: str = "chapter"
    title: str = ""
    card: bool = False
    purpose: str = ""
    word_budget: int = 0
    facts: list[str] = field(default_factory=list)
    show: list[str] = field(default_factory=list)


@dataclass
class Outline:
    thesis: str = ""
    hook_options: list[Hook] = field(default_factory=list)
    hook_choice: str | None = None
    chapters: list[OChapter] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    target_words: int = 2000
    source: dict = field(default_factory=lambda: _source({}, "manual"))
    approval: dict = field(default_factory=lambda: _approval({}))
    counters: dict = field(default_factory=lambda: {"chapter": 0, "fact": 0})
    # remarks of the model to the OWNER (the `NOTE:` lines of the outline layout): something that is not a fact or a conflict, such as a source that looks
    # wrong. They are shown in the checks of the page, and the narration never sees them. Absent from the file (and from the revision) when there are none.
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Outline":
        d = d if isinstance(d, dict) else {}
        hooks = [Hook(_str(h.get("id")) or f"h{i + 1}", _str(h.get("text")))
                 for i, h in enumerate(d.get("hook_options") or []) if isinstance(h, dict)]
        chapters = []
        for c in d.get("chapters") or []:
            if not isinstance(c, dict):
                continue
            role = c.get("role") if c.get("role") in ROLES else "chapter"
            chapters.append(OChapter(_str(c.get("id")), role, _str(c.get("title")), bool(c.get("card")),
                                     _str(c.get("purpose")), _int(c.get("word_budget")), _strs(c.get("facts")),
                                     _strs(c.get("show"))))
        facts = []
        for f in d.get("facts") or []:
            if not isinstance(f, dict):
                continue
            cert = f.get("certainty") if f.get("certainty") in CERTAINTY else "likely"
            conflict = f.get("conflict")
            facts.append(Fact(_str(f.get("id")), _str(f.get("claim")), _strs(f.get("sources")), cert,
                              _str(conflict) if conflict else None))
        o = cls(_str(d.get("thesis")), hooks, d.get("hook_choice") or None, chapters, facts,
                _int(d.get("target_words"), 2000), _source(d.get("source")), _approval(d.get("approval")))
        o.notes = _strs(d.get("notes"))[:MAX_NOTES]
        c = d.get("counters") if isinstance(d.get("counters"), dict) else {}
        o.counters = {"chapter": max(_int(c.get("chapter")), max([_numeric_tail(x.id) for x in chapters], default=0)),
                      "fact": max(_int(c.get("fact")), max([_numeric_tail(x.id) for x in facts], default=0))}
        return o

    def to_dict(self) -> dict:
        d = self._to_dict()
        if self.notes:                      # only when there are some: an outline without notes keeps the revision (and the approval) it always had
            d["notes"] = self.notes
        return d

    def _to_dict(self) -> dict:
        return {
            "schema": SCHEMA_OUTLINE, "source": self.source, "thesis": self.thesis,
            "hook_options": [{"id": h.id, "text": h.text} for h in self.hook_options],
            "hook_choice": self.hook_choice,
            "chapters": [{"id": c.id, "role": c.role, "title": c.title, "card": c.card, "purpose": c.purpose,
                          "word_budget": c.word_budget, "facts": c.facts, "show": c.show} for c in self.chapters],
            "facts": [{"id": f.id, "claim": f.claim, "sources": f.sources, "certainty": f.certainty,
                       "conflict": f.conflict} for f in self.facts],
            "target_words": self.target_words, "counters": self._counters(), "approval": self.approval,
        }

    def _counters(self) -> dict:
        return {"chapter": max(self.counters.get("chapter", 0), max([_numeric_tail(c.id) for c in self.chapters], default=0)),
                "fact": max(self.counters.get("fact", 0), max([_numeric_tail(f.id) for f in self.facts], default=0))}

    def rev(self) -> str:
        return revision(self.to_dict())

    def fact_ids(self) -> set[str]:
        return {f.id for f in self.facts}

    def chapter(self, cid: str) -> OChapter | None:
        return next((c for c in self.chapters if c.id == cid), None)

    def approved_fresh(self) -> bool:
        return bool(self.approval.get("approved")) and self.approval.get("sha1") == self.rev()


# ---------------------------------------------------------------- narration
@dataclass
class Beat:
    id: str
    text: str = ""
    facts: list[str] = field(default_factory=list)
    show: list[str] = field(default_factory=list)
    locked: bool = False
    note: str = ""


@dataclass
class NChapter:
    id: str
    role: str = "chapter"
    title: str = ""
    card: bool = False
    beats: list[Beat] = field(default_factory=list)


@dataclass
class Narration:
    project: str = ""
    title: str = ""
    language: str = "en"
    source: dict = field(default_factory=lambda: _source({}, "manual"))
    chapters: list[NChapter] = field(default_factory=list)
    approval: dict = field(default_factory=lambda: _approval({}))
    counters: dict = field(default_factory=lambda: {"beat": 0})

    @classmethod
    def from_dict(cls, d: dict) -> "Narration":
        d = d if isinstance(d, dict) else {}
        chapters = []
        for c in d.get("chapters") or []:
            if not isinstance(c, dict):
                continue
            beats = [Beat(_str(b.get("id")), _str(b.get("text")), _strs(b.get("facts")), _strs(b.get("show")),
                          bool(b.get("locked")), _str(b.get("note")))
                     for b in c.get("beats") or [] if isinstance(b, dict)]
            role = c.get("role") if c.get("role") in ROLES else "chapter"
            chapters.append(NChapter(_str(c.get("id")), role, _str(c.get("title")), bool(c.get("card")), beats))
        n = cls(_str(d.get("project")), _str(d.get("title")), _str(d.get("language")) or "en",
                _source(d.get("source"), "paste"), chapters, _approval(d.get("approval")))
        cn = d.get("counters") if isinstance(d.get("counters"), dict) else {}
        top = max([_numeric_tail(b.id) for c in chapters for b in c.beats], default=0)
        n.counters = {"beat": max(_int(cn.get("beat")), top)}
        # a beat without an id gets a fresh one, never a reused one
        for c in n.chapters:
            for b in c.beats:
                if not b.id:
                    b.id = n.new_beat_id()
        return n

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA_NARRATION, "project": self.project, "title": self.title, "language": self.language,
            "source": self.source,
            "chapters": [{"id": c.id, "role": c.role, "title": c.title, "card": c.card,
                          "beats": [{"id": b.id, "text": b.text, "facts": b.facts, "show": b.show,
                                     "locked": b.locked, "note": b.note} for b in c.beats]} for c in self.chapters],
            "counters": {"beat": max(self.counters.get("beat", 0), max([_numeric_tail(b.id) for c in self.chapters for b in c.beats], default=0))},
            "approval": self.approval,
        }

    def rev(self) -> str:
        return revision(self.to_dict())

    def new_beat_id(self) -> str:
        top = max([_numeric_tail(b.id) for c in self.chapters for b in c.beats], default=0)
        n = max(self.counters.get("beat", 0), top) + 1
        self.counters["beat"] = n
        return f"b{n:04d}"

    def chapter(self, cid: str) -> NChapter | None:
        return next((c for c in self.chapters if c.id == cid), None)

    def find_beat(self, bid: str) -> tuple[NChapter, int] | None:
        for c in self.chapters:
            for i, b in enumerate(c.beats):
                if b.id == bid:
                    return c, i
        return None

    def approved_fresh(self) -> bool:
        """The narration's OWN hash still matches its approval. Whether the approval still counts also depends on the outline:
        use `narration_approval(narration, outline)` for that."""
        return bool(self.approval.get("approved")) and self.approval.get("sha1") == self.rev()


def narration_approval(n: "Narration | None", o: "Outline | None") -> dict:
    """THE one place that decides whether a narration approval stands (stage, pipeline step, home list, `GET /narration`).

    `{"approved": bool, "reason": str | None}`. `reason` says why a recorded approval does NOT stand:
      - "narration_edited"       the narration changed after it was approved (its hash differs);
      - "outline_not_approved"   the outline is missing, edited since its approval, or not approved;
      - "outline_changed"        the outline is approved, but it is not the outline this narration was approved against
                                 (the approval record holds the outline's hash; an old record without it never stands).
    `reason` is None when nothing was approved, or when the approval stands."""
    ap = n.approval if n is not None else {}
    if n is None or not ap.get("approved"):
        return {"approved": False, "reason": None}
    if ap.get("sha1") != n.rev():
        return {"approved": False, "reason": "narration_edited"}
    if o is None or not o.approved_fresh():
        return {"approved": False, "reason": "outline_not_approved"}
    if ap.get("outline_sha1") != o.rev():
        return {"approved": False, "reason": "outline_changed"}
    return {"approved": True, "reason": None}


def chapter_order_differs(n: "Narration", o: "Outline") -> bool:
    mine = [c.id for c in n.chapters if o.chapter(c.id) is not None]
    theirs = [c.id for c in o.chapters if c.id in set(mine)]
    return mine != theirs


def chapter_diff(n: "Narration | None", o: "Outline | None") -> dict:
    """The chapter ids of the narration against the outline:
    `not_in_outline`        the narration has the chapter, the outline does not (drop it with `drop_chapter`);
    `missing_in_narration`  an outline chapter the narration does not have at all (`add_chapter`, or write it);
    `empty_in_narration`    an outline chapter the narration has, but with no beat that has text (write it);
    `order`                 True when the chapters both documents share are in a different order (`order_like_outline`)."""
    if n is None or o is None:
        return {"not_in_outline": [], "missing_in_narration": [], "empty_in_narration": [], "order": False}
    have = {c.id: c for c in n.chapters}
    return {"order": chapter_order_differs(n, o),
            "not_in_outline": [c.id for c in n.chapters if o.chapter(c.id) is None],
            "missing_in_narration": [c.id for c in o.chapters if c.id not in have],
            "empty_in_narration": [c.id for c in o.chapters if c.id in have and not any(b.text.strip() for b in have[c.id].beats)]}


# ---------------------------------------------------------------- shape check of a document sent by a client
def _is_str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _id_problem(p: str, v, rx: re.Pattern, what: str, required: bool = True) -> str | None:
    if v is None or v == "":
        return None if not required else f"{p}.id must be {what}"
    if not isinstance(v, str):
        return f"{p}.id must be a string ({what})"
    if not rx.fullmatch(v):
        return f"{p}.id {v[:40]!r} is not valid: it must be {what}"
    return None


def doc_problem(kind: str, d) -> str | None:
    """None when `d` is a plausible outline/narration document, else what is wrong. `from_dict` is forgiving by design
    (it reads files written by older code); a document a client SENDS must have the right shape instead of being coerced:
    ids match the patterns the parsers read back and are unique, every enum (`role`, `certainty`) is one of its values, every
    flag (`card`, `locked`) is a boolean, every text is a string, every number is finite."""
    name = "outline" if kind == "outline" else "narration"
    if not isinstance(d, dict):
        return f"{name} (object) is required"
    chs = d.get("chapters")
    if not isinstance(chs, list):
        return f"{name}.chapters must be a list"
    seen: set[str] = set()
    seen_beats: set[str] = set()
    for i, c in enumerate(chs):
        p = f"{name}.chapters[{i}]"
        if not isinstance(c, dict):
            return f"{p} must be an object"
        bad = _id_problem(p, c.get("id"), CHAPTER_ID_RE, "c followed by digits, like c01")
        if bad:
            return bad
        if c["id"] in seen:
            return f"{p}.id {c['id']!r} is used twice"
        seen.add(c["id"])
        for k in ("title", "role", "purpose"):
            if k in c and not isinstance(c[k], str):
                return f"{p}.{k} must be a string"
        if "role" in c and c["role"] not in ROLES:
            return f"{p}.role must be one of {', '.join(ROLES)}"
        if "card" in c and not isinstance(c["card"], bool):
            return f"{p}.card must be true or false"
        if kind == "outline":
            for k in ("facts", "show"):
                if k in c and not _is_str_list(c[k]):
                    return f"{p}.{k} must be a list of strings"
            if "word_budget" in c and not _is_num(c["word_budget"]):
                return f"{p}.word_budget must be a finite number"
        else:
            beats = c.get("beats", [])
            if not isinstance(beats, list):
                return f"{p}.beats must be a list"
            for j, b in enumerate(beats):
                bp = f"{p}.beats[{j}]"
                if not isinstance(b, dict):
                    return f"{bp} must be an object"
                bad = _id_problem(bp, b.get("id"), BEAT_ID_RE, "b followed by digits, like b0001", required=False)
                if bad:
                    return bad
                if b.get("id"):
                    if b["id"] in seen_beats:
                        return f"{bp}.id {b['id']!r} is used twice (beat ids are unique in the whole narration)"
                    seen_beats.add(b["id"])
                for k in ("text", "note"):
                    if k in b and b[k] is not None and not isinstance(b[k], str):
                        return f"{bp}.{k} must be a string"
                for k in ("facts", "show"):
                    if k in b and not _is_str_list(b[k]):
                        return f"{bp}.{k} must be a list of strings"
                if "locked" in b and not isinstance(b["locked"], bool):
                    return f"{bp}.locked must be true or false"
    if kind == "outline":
        if "thesis" in d and not isinstance(d["thesis"], str):
            return f"{name}.thesis must be a string"
        for k in ("facts", "hook_options"):
            if k in d and not (isinstance(d[k], list) and all(isinstance(x, dict) for x in d[k])):
                return f"{name}.{k} must be a list of objects"
        if "target_words" in d and not _is_num(d["target_words"]):
            return f"{name}.target_words must be a finite number"
        fseen: set[str] = set()
        for i, f in enumerate(d.get("facts") or []):
            fp = f"{name}.facts[{i}]"
            for k in ("id", "claim"):
                if k in f and not isinstance(f[k], str):
                    return f"{fp}.{k} must be a string"
            if "sources" in f and not _is_str_list(f["sources"]):
                return f"{fp}.sources must be a list of strings"
            if "certainty" in f and f["certainty"] not in CERTAINTY:
                return f"{fp}.certainty must be one of {', '.join(CERTAINTY)}"
            if "conflict" in f and f["conflict"] is not None and not isinstance(f["conflict"], str):
                return f"{fp}.conflict must be a string or null"
        for i, h in enumerate(d.get("hook_options") or []):
            for k in ("id", "text"):
                if k in h and not isinstance(h[k], str):
                    return f"{name}.hook_options[{i}].{k} must be a string"
        if d.get("hook_choice") is not None and not isinstance(d.get("hook_choice"), str):
            return f"{name}.hook_choice must be a string or null"
        if "notes" in d and not (_is_str_list(d["notes"]) and len(d["notes"]) <= MAX_NOTES):
            return f"{name}.notes must be a list of at most {MAX_NOTES} strings"
    else:
        for k in ("project", "title", "language"):
            if k in d and d[k] is not None and not isinstance(d[k], str):
                return f"{name}.{k} must be a string"
    return None


# ---------------------------------------------------------------- files
def script_dir(pdir: Path) -> Path:
    return Path(pdir) / "script"


def _load(path: Path) -> dict | None:
    return read_object(path, "script")


def load_outline(pdir: Path) -> Outline | None:
    d = _load(script_dir(pdir) / "outline.json")
    return None if d is None else Outline.from_dict(d)


def load_narration(pdir: Path) -> Narration | None:
    d = _load(script_dir(pdir) / "narration.json")
    return None if d is None else Narration.from_dict(d)


def _save(path: Path, obj, base_rev: str | None, *, backup: bool = True) -> str:
    """Write `obj`; the approval is dropped unless it still matches the new revision.
    `base_rev`, when given, must equal the revision currently on disk."""
    if path.is_dir():           # a folder in place of the document: 409 before anything is written (a damaged FILE is replaceable)
        raise DocumentCorrupt("%s is corrupt: it is a folder, not a file" % path.name, "script")
    if base_rev is not None and path.is_file():
        cur = type(obj).from_dict(_load(path)).rev()
        if cur != base_rev:
            raise StaleRevision(cur)
    rev = obj.rev()
    if obj.approval.get("sha1") != rev:
        obj.approval = {"approved": False, "sha1": None, "approved_at": None}
    if backup and path.is_file():
        try:
            write_text_atomic(path.with_suffix(".prev.json"), path.read_text(encoding="utf-8"))
        except OSError:
            pass
    write_json_atomic(path, obj.to_dict())
    return rev


def save_outline(pdir: Path, o: Outline, base_rev: str | None = None, *, backup: bool = True) -> str:
    return _save(script_dir(pdir) / "outline.json", o, base_rev, backup=backup)


def save_narration(pdir: Path, n: Narration, base_rev: str | None = None, *, backup: bool = True) -> str:
    return _save(script_dir(pdir) / "narration.json", n, base_rev, backup=backup)


def disk_rev(path: Path, kind: str = "narration") -> str | None:
    cls = Outline if kind == "outline" else Narration
    return cls.from_dict(_load(path)).rev() if path.is_file() else None


def approve(pdir: Path, kind: str, rev: str, by: str | None = None) -> dict:
    """Stamp the approval of the saved file `kind` ("outline" | "narration"); `rev` must be its current revision.
    A narration approval also records the revision of the outline file it is approved against (`outline_sha1`).
    `by` (c5cli) is who approved: `human`, `agent:<model id>` or `cli:<name>`."""
    path = script_dir(pdir) / f"{kind}.json"
    d = _load(path)
    if d is None:
        raise FileNotFoundError(kind)
    cur = (Outline if kind == "outline" else Narration).from_dict(d).rev()
    if cur != rev:
        raise StaleRevision(cur)
    ap = {"approved": True, "sha1": cur, "approved_at": now_iso()}
    if by:
        ap["by"] = by
    if kind == "narration":
        o = load_outline(pdir)
        ap["outline_sha1"] = o.rev() if o is not None else None
    d["approval"] = ap
    write_json_atomic(path, d)
    return d["approval"]


def unapprove(pdir: Path, kind: str) -> None:
    path = script_dir(pdir) / f"{kind}.json"
    d = _load(path)
    if d is not None:
        d["approval"] = {"approved": False, "sha1": None, "approved_at": None}
        write_json_atomic(path, d)


def paste_path(pdir: Path, kind: str) -> Path:
    return script_dir(pdir) / ("last_paste.txt" if kind == "narration" else "last_paste_outline.txt")


def keep_paste(pdir: Path, kind: str, text: str) -> None:
    write_text_atomic(paste_path(pdir, kind), text)


def read_paste(pdir: Path, kind: str) -> str:
    return read_file_text(paste_path(pdir, kind), "script", errors="replace") or ""


def clear_paste(pdir: Path, kind: str) -> None:
    try:
        paste_path(pdir, kind).unlink()
    except FileNotFoundError:
        pass
