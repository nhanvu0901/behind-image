"""Beat operations. They never renumber ids: a split makes a fresh id, a drop leaves a gap that is never reused."""
from __future__ import annotations

from .store import Beat, NChapter, Narration, now_iso


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


def apply_op(n: Narration, op: dict) -> dict:
    """Dispatch for the API: {"op": "split|merge|drop|insert|move", ...}. Returns {"id": ...} where relevant."""
    kind = op.get("op")
    try:
        if kind == "split":
            return {"id": split_beat(n, op["beat"], int(op["at_word"]))}
        if kind == "merge":
            return {"id": merge_with_previous(n, op["beat"])}
        if kind == "drop":
            drop_beat(n, op["beat"])
            return {}
        if kind == "insert":
            return {"id": insert_beat(n, op["chapter"], op.get("after"), op.get("text", ""), op.get("facts"), op.get("show"))}
        if kind == "move":
            move_beat(n, op["beat"], op.get("to_chapter"), op.get("after"))
            return {}
    except (KeyError, TypeError, ValueError) as e:
        raise OpError(f"bad operation: {e}")
    raise OpError(f"unknown operation {kind!r}")
