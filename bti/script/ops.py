"""Beat operations. They never renumber ids: a split makes a fresh id, a drop leaves a gap that is never reused."""
from __future__ import annotations

from .store import Beat, NChapter, Narration, Outline, now_iso


class OpError(Exception):
    pass


def _locate(n: Narration, bid: str) -> tuple[NChapter, int]:
    hit = n.find_beat(bid)
    if hit is None:
        raise OpError(f"beat {bid} not found")
    return hit


def _union(a: list[str], b: list[str]) -> list[str]:
    return a + [x for x in b if x not in a]


def split_beat(n: Narration, bid: str, at_word: int) -> str:
    """Split at a word: the first `at_word` words stay in the beat, the rest become a new beat after it (returned id)."""
    ch, i = _locate(n, bid)
    b = ch.beats[i]
    if b.locked:
        raise OpError(f"beat {bid} is locked")
    words = b.text.split()
    if not 0 < at_word < len(words):
        raise OpError(f"cannot split a beat of {len(words)} words at word {at_word}")
    new = Beat(n.new_beat_id(), " ".join(words[at_word:]), list(b.facts), list(b.show))
    b.text = " ".join(words[:at_word])
    ch.beats.insert(i + 1, new)
    return new.id


def merge_with_previous(n: Narration, bid: str) -> str:
    """Join a beat to the one before it in the same chapter; returns the id that remains."""
    ch, i = _locate(n, bid)
    if i == 0:
        raise OpError(f"beat {bid} is the first of its chapter; there is nothing to merge it with")
    prev, b = ch.beats[i - 1], ch.beats[i]
    if prev.locked or b.locked:
        raise OpError("a locked beat cannot be merged")
    prev.text = (prev.text.rstrip() + " " + b.text.lstrip()).strip()
    prev.facts, prev.show = _union(prev.facts, b.facts), _union(prev.show, b.show)
    if b.note:
        prev.note = (prev.note + " " + b.note).strip()
    del ch.beats[i]
    return prev.id


def drop_beat(n: Narration, bid: str) -> None:
    ch, i = _locate(n, bid)
    if ch.beats[i].locked:
        raise OpError(f"beat {bid} is locked")
    del ch.beats[i]


def drop_chapter(n: Narration, chapter_id: str) -> None:
    """Remove a chapter and its beats from the narration. Refused while any of its beats is locked (the rule `drop` uses)."""
    ch = n.chapter(chapter_id)
    if ch is None:
        raise OpError(f"chapter {chapter_id} not found")
    locked = [b.id for b in ch.beats if b.locked]
    if locked:
        raise OpError(f"beat {', '.join(locked)} is locked: chapter {chapter_id} cannot be dropped")
    n.chapters = [c for c in n.chapters if c.id != chapter_id]


def add_chapter(n: Narration, outline: Outline | None, chapter_id: str) -> None:
    """Add an outline chapter that the narration lacks, at the outline's position, with the outline's title and no beats."""
    oc = outline.chapter(chapter_id) if outline is not None else None
    if oc is None:
        raise OpError(f"chapter {chapter_id} is not in the outline")
    if n.chapter(chapter_id) is not None:
        raise OpError(f"chapter {chapter_id} is already in the narration")
    n.chapters.append(NChapter(oc.id, oc.role, oc.title, oc.card, []))
    order = {c.id: i for i, c in enumerate(outline.chapters)}
    n.chapters.sort(key=lambda c: order.get(c.id, 10_000))


def order_like_outline(n: Narration, outline: Outline | None) -> None:
    """Put the chapters in the outline's order; chapters the outline does not have keep their relative order at the end."""
    if outline is None:
        raise OpError("there is no outline to follow")
    order = {c.id: i for i, c in enumerate(outline.chapters)}
    n.chapters.sort(key=lambda c: order.get(c.id, 10_000))


def insert_beat(n: Narration, chapter_id: str, after: str | None = None, text: str = "",
                facts: list[str] | None = None, show: list[str] | None = None) -> str:
    """Insert a new beat in a chapter, after beat `after` (None = at the start). Returns the new id."""
    ch = n.chapter(chapter_id)
    if ch is None:
        raise OpError(f"chapter {chapter_id} not found")
    idx = 0
    if after:
        hit = n.find_beat(after)
        if hit is None or hit[0] is not ch:
            raise OpError(f"beat {after} is not in chapter {chapter_id}")
        idx = hit[1] + 1
    b = Beat(n.new_beat_id(), text, list(facts or []), list(show or []))
    ch.beats.insert(idx, b)
    return b.id


def move_beat(n: Narration, bid: str, to_chapter: str | None = None, after: str | None = None) -> None:
    """Move a beat after beat `after` (None = to the start of the chapter), in its own chapter or in `to_chapter`."""
    ch, i = _locate(n, bid)
    dest = n.chapter(to_chapter) if to_chapter else ch
    if dest is None:
        raise OpError(f"chapter {to_chapter} not found")
    if after == bid:
        raise OpError("a beat cannot be moved after itself")
    b = ch.beats.pop(i)
    idx = 0
    if after:
        hit = n.find_beat(after)
        if hit is None or hit[0] is not dest:
            ch.beats.insert(i, b)
            raise OpError(f"beat {after} is not in chapter {dest.id}")
        idx = hit[1] + 1
    dest.beats.insert(idx, b)


def _need(op: dict, key: str, typ, what: str, optional: bool = False):
    v = op.get(key)
    if v is None:
        if optional:
            return None
        raise OpError(f"bad operation: {key} ({what}) is required")
    if isinstance(v, bool) or not isinstance(v, typ):
        raise OpError(f"bad operation: {key} must be {what}, not {type(v).__name__}")
    return v


def _str_list(op: dict, key: str):
    v = op.get(key)
    if v is None:
        return None
    if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
        raise OpError(f"bad operation: {key} must be a list of strings")
    return v


def apply_op(n: Narration, op: dict, outline: Outline | None = None) -> dict:
    """Dispatch for the API: {"op": "split|merge|drop|insert|move|drop_chapter|add_chapter|order_like_outline" (`add_chapter` needs the outline), ...}. Returns {"id": ...} where relevant.
    Every field is type-checked; nothing is coerced (a list is not turned into text, a string is not turned into a list)."""
    if not isinstance(op, dict):
        raise OpError("bad operation: each operation must be an object")
    kind = op.get("op")
    if kind == "split":
        return {"id": split_beat(n, _need(op, "beat", str, "a beat id"), _need(op, "at_word", int, "an integer"))}
    if kind == "merge":
        return {"id": merge_with_previous(n, _need(op, "beat", str, "a beat id"))}
    if kind == "drop":
        drop_beat(n, _need(op, "beat", str, "a beat id"))
        return {}
    if kind == "drop_chapter":
        drop_chapter(n, _need(op, "chapter", str, "a chapter id"))
        return {}
    if kind == "add_chapter":
        add_chapter(n, outline, _need(op, "chapter", str, "a chapter id"))
        return {}
    if kind == "order_like_outline":
        order_like_outline(n, outline)
        return {}
    if kind == "insert":
        return {"id": insert_beat(n, _need(op, "chapter", str, "a chapter id"), _need(op, "after", str, "a beat id", True),
                                  _need(op, "text", str, "a string", True) or "", _str_list(op, "facts"), _str_list(op, "show"))}
    if kind == "move":
        move_beat(n, _need(op, "beat", str, "a beat id"), _need(op, "to_chapter", str, "a chapter id", True),
                  _need(op, "after", str, "a beat id", True))
        return {}
    raise OpError(f"unknown operation {kind!r}")
