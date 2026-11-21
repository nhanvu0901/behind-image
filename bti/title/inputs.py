"""What the title job reads before it starts (all of it files; no model, no network): the approved narration, the outline's thesis and hook, the painting's identity,
the channel's name. The refusals of the start route are raised here, as `TitleError`, so that the route and the plain function the automatic run calls give the same answer."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from bti.picks import context
from bti.script import store as sstore

from .store import TitleError

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTE_MAX = 600                 # the owner's wish for this title, in their words


@dataclass
class Inputs:
    pdir: Path
    identity: dict                       # {title, artist, year}
    channel: str
    chapters: list                       # [{id, title, role, lines: [{id, no, text}]}]
    lines: dict                          # line id -> text
    outline: dict                        # {thesis, hook, hook_options, chapters: [{id, role, title, purpose}]}
    narration_rev: str
    language: str = "en"
    owner_note: str = ""
    n_lines: int = 0
    n_chapters: int = 0
    order: list = field(default_factory=list)


def channel_name() -> str:
    """The channel's name as a person reads it (the style's `identity.channel_name`, written in capitals there): `Raking Light`."""
    name = ""
    try:
        from bti import identity as ID
        style = json.loads((REPO_ROOT / "style" / "gae" / "style.json").read_text(encoding="utf-8"))
        cfg = ID.read(style)
        name = cfg.channel_name if cfg else ""
    except Exception:       # noqa: BLE001 - the name is only a word in the task
        name = ""
    name = name or "Raking Light"
    return " ".join(w.capitalize() for w in name.split()) if name.upper() == name else name


def check_note(note) -> str | None:
    """The owner's note, trimmed (None when there is none). TitleError `title_note_invalid` (not text), `title_note_too_long`."""
    if note is None:
        return None
    if not isinstance(note, str):
        raise TitleError("title_note_invalid", "note must be text", 422, field="note")
    text = re.sub(r"\s+", " ", note).strip()
    if len(text) > NOTE_MAX:
        raise TitleError("title_note_too_long", "note must be at most %d characters (it has %d)" % (NOTE_MAX, len(text)), 422, field="note")
    return text or None


def _outline_json(o) -> dict:
    if o is None:
        return {"thesis": "", "hook": "", "hook_options": [], "chapters": []}
    options = [{"id": h.id, "text": h.text} for h in o.hook_options]
    chosen = next((h.text for h in o.hook_options if h.id == o.hook_choice), "")
    return {"thesis": o.thesis, "hook": chosen, "hook_options": options,
            "chapters": [{"id": c.id, "role": c.role, "title": c.title, "purpose": c.purpose} for c in o.chapters]}


def load(pdir: Path, note: str | None = None) -> Inputs:
    """Read the project. TitleError 409 `narration_not_approved` when there is no approved narration (or it changed after it was approved)."""
    pdir = Path(pdir)
    nv = context.narration_view(pdir)
    if not nv["present"] or not nv["approved"]:
        raise TitleError("narration_not_approved", "the narration is not approved (or changed): approve it first", 409)
    chapters, lines, order, no = [], {}, [], 0
    for c in nv["chapters"]:
        rows = []
        for b in c["beats"]:
            no += 1
            rows.append({"id": b["id"], "no": no, "text": b["text"]})
            lines[b["id"]] = b["text"]
            order.append(b["id"])
        chapters.append({"id": c["id"], "title": c["title"], "role": c["role"], "lines": rows})
    if not lines:
        raise TitleError("narration_not_approved", "the narration has no lines", 409)
    try:
        outline = _outline_json(sstore.load_outline(pdir))
    except Exception:       # noqa: BLE001 - a damaged outline never stops a title: the narration is what the title is true to
        outline = _outline_json(None)
    try:
        narr = sstore.load_narration(pdir)
        language = (getattr(narr, "language", None) or "en") if narr is not None else "en"
    except Exception:       # noqa: BLE001
        language = "en"
    try:
        ident = context.identity(pdir)
    except Exception:       # noqa: BLE001 - a damaged dossier: the title is about the narration
        ident = {"title": "", "artist": "", "year": ""}
    return Inputs(pdir=pdir, identity=ident, channel=channel_name(), chapters=chapters, lines=lines, outline=outline, narration_rev=nv["rev"],
                  language=language, owner_note=note or "", n_lines=len(lines), n_chapters=len(chapters), order=order)
