"""Sentences to chunks: what is sent to the voice in one go.

The rule is our own copy of the one the comic pipeline uses (one chunk per sentence; a sentence under `min_chars` joins the
NEXT one, or the previous one when it is the last; a chunk over `max_chars` is cut at a comma). Nothing is imported from
that repository. Chunks never cross a beat: a beat starts a new chunk, so every beat of the narration owns whole chunks and
`timing.json` can say exactly where it starts.

Chunk id = hash of the spoken text, the voice settings and the seed. The seed comes from the hash of the spoken text, so an
unchanged sentence always gives the same audio; "read this sentence again" stores another seed for that text hash.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .speak import Unit, speak_units

_END = re.compile(r"[.!?][\"”')]*$")
_START = re.compile(r"^[\"“(\[]?[A-Z0-9]")


@dataclass
class Chunk:
    index: int
    id: str
    th: str                       # hash of the spoken text alone (what a re-seed is keyed by)
    seed: int
    spoken: str
    units: list[Unit]
    beat: str
    chapter: str
    gap: float = 0.0              # silence before this chunk, in seconds (set by `build_chunks`)
    gap_kind: str = "sentence"    # lead | sentence | beat | chapter | card | title
    first_in_beat: bool = False
    written: list[str] = field(default_factory=list)

    @property
    def spoken_words(self) -> list[str]:
        return self.spoken.split()


def _text(group: list[Unit]) -> str:
    return " ".join(u.spoken for u in group if u.spoken).strip()


def split_sentences(units: list[Unit]) -> list[list[Unit]]:
    """Cut after a unit that ends with . ! or ? when the next spoken word starts with a capital letter or a digit."""
    out: list[list[Unit]] = []
    cur: list[Unit] = []
    for i, u in enumerate(units):
        cur.append(u)
        if u.spoken and _END.search(u.spoken):
            nxt = next((v.spoken for v in units[i + 1:] if v.spoken), "")
            if not nxt or _START.match(nxt):
                out.append(cur)
                cur = []
    if cur:
        out.append(cur)
    return [g for g in out if _text(g)]


def chunk_units(units: list[Unit], min_chars: int = 40, max_chars: int = 280) -> list[list[Unit]]:
    """The comic rule on groups of units."""
    sents = split_sentences(units)
    merged: list[list[Unit]] = []
    pending: list[Unit] = []
    for sent in sents:
        if pending:
            if len(_text(pending)) + 1 + len(_text(sent)) <= max_chars:
                sent = pending + sent
            else:
                merged.append(pending)
            pending = []
        if len(_text(sent)) < min_chars:
            pending = sent
        else:
            merged.append(sent)
    if pending:
        if merged and len(_text(merged[-1])) + 1 + len(_text(pending)) <= max_chars:
            merged[-1] = merged[-1] + pending
        else:
            merged.append(pending)
    out: list[list[Unit]] = []
    for sent in merged:
        if len(_text(sent)) <= max_chars:
            out.append(sent)
            continue
        parts: list[list[Unit]] = []
        cur: list[Unit] = []
        for u in sent:
            cur.append(u)
            if u.spoken.endswith(","):
                parts.append(cur)
                cur = []
        if cur:
            parts.append(cur)
        buf: list[Unit] = []
        for part in parts:
            if buf and len(_text(buf)) + len(_text(part)) + 1 > max_chars:
                out.append(buf)
                buf = list(part)
            else:
                buf = buf + part
        if buf:
            out.append(buf)
    return out


def text_hash(spoken: str) -> str:
    return hashlib.sha1(spoken.encode("utf-8")).hexdigest()[:10]


def default_seed(th: str) -> int:
    return int(th, 16) % (2 ** 31)


def chunk_id(spoken: str, settings_sig: str, seed: int) -> str:
    return hashlib.sha1(f"{spoken}|{settings_sig}|{seed}".encode("utf-8")).hexdigest()[:12]


def next_seed(seed: int) -> int:
    """The seed a "read again" moves to (deterministic, so a test can predict it)."""
    return (int(seed) * 1103515245 + 12345) % (2 ** 31)


def build_chunks(narration, table: dict | None, cfg: dict, settings_sig: str, seeds: dict | None = None) -> list[Chunk]:
    """All chunks of an approved narration, in order, with the silence before each. `narration` is a `bti.script.store.Narration`."""
    sil = cfg["silence"]
    lo, hi = int(cfg["chunk"]["min_chars"]), int(cfg["chunk"]["max_chars"])
    seeds = seeds or {}
    out: list[Chunk] = []
    cold = bool(narration.chapters) and narration.chapters[0].role == "cold_open"
    title_at = None                       # the chapter whose lead holds the title card
    if cold:
        title_at = next((i for i, c in enumerate(narration.chapters) if i > 0 and c.beats and any(b.text.strip() for b in c.beats)), None)
    elif narration.chapters:
        title_at = 0
    for ci, ch in enumerate(narration.chapters):
        first_of_chapter = True
        for beat in ch.beats:
            units = speak_units(beat.text, table)
            for gi, group in enumerate(chunk_units(units, lo, hi)):
                spoken = _text(group)
                th = text_hash(spoken)
                seed = int(seeds[th]) if th in seeds else default_seed(th)
                c = Chunk(index=len(out), id=chunk_id(spoken, settings_sig, seed), th=th, seed=seed, spoken=spoken, units=group,
                          beat=beat.id, chapter=ch.id, first_in_beat=(gi == 0),
                          written=[w for u in group for w in u.written])
                extra = float(sil["card"]) if ch.card else 0.0
                if first_of_chapter and ci == title_at:
                    # the title card: before the first chapter after a cold open, or at the very start without one
                    c.gap_kind, c.gap = "title", float(sil["title"]) + extra
                elif not out:
                    c.gap_kind, c.gap = "lead", float(sil["lead"]) + extra
                elif first_of_chapter:
                    c.gap_kind = "card" if ch.card else "chapter"
                    c.gap = float(sil["card"] if ch.card else sil["chapter"])
                elif gi == 0:
                    c.gap_kind, c.gap = "beat", float(sil["beat"])
                else:
                    c.gap_kind, c.gap = "sentence", float(sil["sentence"])
                first_of_chapter = False
                out.append(c)
    return out
