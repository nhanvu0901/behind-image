"""Outline and narration data classes, atomic load/save, revisions and approvals.

Revision = sha1 of the canonical JSON of the document without its `approval` block. An approval stores the
revision it approved; any edit changes the revision, so the approval is dropped on save and is stale when
checked against a document that changed behind its back. Ids are never renumbered: new ids come from a
counter stored in the document, which only grows.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_OUTLINE = "bti.outline/1"
SCHEMA_NARRATION = "bti.narration/1"
CERTAINTY = ("established", "likely", "disputed")
ROLES = ("cold_open", "chapter", "closing")


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def script_lock(pdir: Path) -> threading.RLock:
    """The one lock of a project's script files. Every read-modify-write of outline.json / narration.json (a save from the
    page, an op, an approval, an import, and a model job that finishes a chapter) holds it, so none can overwrite another."""
    key = str(Path(pdir).resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


class StaleRevision(Exception):
    """The caller's revision is not the current one."""


class DocumentCorrupt(Exception):
    """A script document on disk is not readable (not UTF-8, not JSON, or not an object). The message names the file."""


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def canonical_json(doc: dict) -> str:
    d = {k: v for k, v in doc.items() if k != "approval"}
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def revision(doc: dict) -> str:
    return hashlib.sha1(canonical_json(doc).encode("utf-8")).hexdigest()


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
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
    except (TypeError, ValueError):
        return default


def _approval(a: Any) -> dict:
    a = a if isinstance(a, dict) else {}
    return {"approved": bool(a.get("approved")), "sha1": a.get("sha1"), "approved_at": a.get("approved_at")}


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
        c = d.get("counters") if isinstance(d.get("counters"), dict) else {}
        o.counters = {"chapter": max(_int(c.get("chapter")), max([_numeric_tail(x.id) for x in chapters], default=0)),
                      "fact": max(_int(c.get("fact")), max([_numeric_tail(x.id) for x in facts], default=0))}
        return o

    def to_dict(self) -> dict:
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
        return bool(self.approval.get("approved")) and self.approval.get("sha1") == self.rev()


# ---------------------------------------------------------------- shape check of a document sent by a client
def _is_str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def doc_problem(kind: str, d) -> str | None:
    """None when `d` is a plausible outline/narration document, else what is wrong. `from_dict` is forgiving by design
    (it reads files written by older code); a document a client SENDS must have the right shape instead of being coerced."""
    name = "outline" if kind == "outline" else "narration"
    if not isinstance(d, dict):
        return f"{name} (object) is required"
    chs = d.get("chapters")
    if not isinstance(chs, list):
        return f"{name}.chapters must be a list"
    seen = set()
    for i, c in enumerate(chs):
        p = f"{name}.chapters[{i}]"
        if not isinstance(c, dict):
            return f"{p} must be an object"
        if not isinstance(c.get("id"), str) or not c["id"].strip():
            return f"{p}.id must be a non-empty string"
        if c["id"] in seen:
            return f"{p}.id {c['id']!r} is used twice"
        seen.add(c["id"])
        for k in ("title", "role", "purpose"):
            if k in c and not isinstance(c[k], str):
                return f"{p}.{k} must be a string"
        if kind == "outline":
            for k in ("facts", "show"):
                if k in c and not _is_str_list(c[k]):
                    return f"{p}.{k} must be a list of strings"
            if "word_budget" in c and not _is_num(c["word_budget"]):
                return f"{p}.word_budget must be a number"
        else:
            beats = c.get("beats", [])
            if not isinstance(beats, list):
                return f"{p}.beats must be a list"
            for j, b in enumerate(beats):
                bp = f"{p}.beats[{j}]"
                if not isinstance(b, dict):
                    return f"{bp} must be an object"
                for k in ("id", "text", "note"):
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
            return f"{name}.target_words must be a number"
    return None


# ---------------------------------------------------------------- files
def script_dir(pdir: Path) -> Path:
    return Path(pdir) / "script"


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise DocumentCorrupt("%s is corrupt: %s" % (path.name, str(e)[:120]))
    if not isinstance(d, dict):
        raise DocumentCorrupt("%s is corrupt: the top level must be an object" % path.name)
    return d


def load_outline(pdir: Path) -> Outline | None:
    d = _load(script_dir(pdir) / "outline.json")
    return None if d is None else Outline.from_dict(d)


def load_narration(pdir: Path) -> Narration | None:
    d = _load(script_dir(pdir) / "narration.json")
    return None if d is None else Narration.from_dict(d)


def _save(path: Path, obj, base_rev: str | None, *, backup: bool = True) -> str:
    """Write `obj`; the approval is dropped unless it still matches the new revision.
    `base_rev`, when given, must equal the revision currently on disk."""
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


def approve(pdir: Path, kind: str, rev: str) -> dict:
    """Stamp the approval of the saved file `kind` ("outline" | "narration"); `rev` must be its current revision."""
    path = script_dir(pdir) / f"{kind}.json"
    d = _load(path)
    if d is None:
        raise FileNotFoundError(kind)
    cur = (Outline if kind == "outline" else Narration).from_dict(d).rev()
    if cur != rev:
        raise StaleRevision(cur)
    d["approval"] = {"approved": True, "sha1": cur, "approved_at": now_iso()}
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
    p = paste_path(pdir, kind)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def clear_paste(pdir: Path, kind: str) -> None:
    try:
        paste_path(pdir, kind).unlink()
    except FileNotFoundError:
        pass
