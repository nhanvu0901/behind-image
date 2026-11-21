"""Cold-open checks on `c01` (chapter with role `cold_open`). Pure functions on strings and chapter objects: no model, no project, no I/O.

Rules checked on the cold-open chapter:
  * first line short (<= 25 words) and pointing at something visible;
  * painting's title (by distinguishing words) and painter's name (by surname) both spoken outside quotations, and both within the first 72 words;
  * an early contradiction/turn ("but" / "yet") within the first 72 words;
  * closes on an open question ("?" in the cold open's last line);
  * no plan-of-the-video phrases ("in this video", "today we will", "let's find out", ...);
  * cold-open word count between 60 and 145 words.
"""
from __future__ import annotations

import re

from .stats import count_words
from .store import Beat, NChapter, Narration, Outline
from . import sourcenames
from .. import textfold

MIN_WORDS = 60
MAX_WORDS = 145
MAX_FIRST_LINE_WORDS = 25
EARLY_WINDOW_WORDS = 72

_STOP_WORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "at", "to", "by", "for", "and", "or", "with", "from", "into",
    "his", "her", "its", "their", "our", "my", "your", "this", "that", "these", "those", "is", "are",
    "was", "were", "as", "la", "le", "les", "de", "du", "des", "der", "die", "das", "den", "il", "lo",
    "gli", "i", "el", "los", "las", "y", "e", "et", "und",
})
_PARTICLES = frozenset({"van", "von", "da", "del", "della", "di", "de", "der", "den", "ter", "ten", "la", "le"})
_EPITHETS = re.compile(r"\b(?:the\s+(?:younger|elder)|il\s+(?:vecchio|giovane))\b", re.I)
_PLACEHOLDER_TITLES = frozenset({"unknown", "untitled", "none", "n/a", "na", "null", "test"})
_PLACEHOLDER_ARTISTS = frozenset({"unknown", "anonymous", "various", "unknown artist", "anonymous artist", "none", "n/a"})

# Explicit quoted spans (preserving apostrophes like Costanza's and van Eyck's)
_DBL_QUOTES = re.compile(r'["“][^"”\n]*["”]')
_SGL_QUOTES = re.compile(r"(?<!\w)[‘']([^’'\n]+)[’'](?!\w)")
# Spoken indirect quotation / translated inscription (e.g. "In English it says, Jan van Eyck was here, 1434.")
_INSCRIPTION_QUOTE = re.compile(
    r"(?:"
    r"(?:in\s+\w+\s+(?:the\s+(?:line|writing|inscription|signature|text|motto|scroll|banner|lettering)|it)\s+(?:says|reads))"
    r"|(?:(?:the\s+(?:inscription|writing|signature|text|motto|scroll|banner|lettering|line)|it)\s+(?:says|reads))"
    r"|which\s+(?:says|reads)"
    r"|translates?\s+(?:as|to)"
    r")\b[^.!?\n]*(?:[.!?]|$)",
    re.I,
)

_EARLY_TURN = re.compile(r"\b(?:but|yet)\b", re.I)
_ROADMAP = [
    re.compile(p, re.I)
    for p in (
        r"\bin\s+this\s+(?:video|episode|film|essay|talk)\b",
        r"\btoday\s+we(?:'re|\s+are|\s+will|'ll)(?:\s+going\s+to)?\s+(?:look|examine|explore|dive|see|uncover|discover|find|show|talk)\b",
        r"\btoday\s+we\s+will\b",
        r"\btoday\s+we(?:'re|\s+are)\s+going\s+to\b",
        r"\blet(?:'s|\s+us)\s+(?:find\s+out|explore|take\s+a\s+look\s+at|dive\s+in|dive\s+into)\b",
        r"\bwe(?:'re|\s+are|\s+will|'ll)\s+(?:going\s+to\s+)?(?:explore|examine|dive\s+into|look\s+at)\b",
        r"\bwelcome\s+back\b",
        r"\bin\s+the\s+next\s+(?:few|\d+)\s+minutes\b",
    )
]


def _words_folded(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", textfold.fold(text))


def find_cold_open(n: Narration, outline: Outline | None) -> NChapter | None:
    """Return the narration chapter that corresponds to the outline's `cold_open` role (or the narration's own when there is no outline)."""
    if outline is not None:
        for oc in outline.chapters:
            if oc.role == "cold_open":
                return n.chapter(oc.id)
    for c in n.chapters:
        if c.role == "cold_open":
            return c
    return None


def strip_quotations(text: str) -> str:
    """Remove direct quotations and spoken translated-inscription clauses so names inside them do not count as ordinary speech."""
    s = _DBL_QUOTES.sub(" ", text or "")
    s = _SGL_QUOTES.sub(" ", s)
    s = _INSCRIPTION_QUOTE.sub(" ", s)
    return s


def first_n_words(beats: list[Beat], limit: int = EARLY_WINDOW_WORDS) -> tuple[str, int]:
    """(spoken text truncated at `limit` whitespace words preserving sentence punctuation, total words across `beats`)."""
    all_parts: list[str] = []
    early_parts: list[str] = []
    total = 0
    for b in beats:
        t = (b.text or "").strip()
        if not t:
            continue
        all_parts.append(t)
        ws = t.split()
        if total < limit:
            take = ws[: max(0, limit - total)]
            if take:
                early_parts.append(" ".join(take))
        total += len(ws)
    return " ".join(early_parts), total


def title_tokens(title: str) -> list[str]:
    """Distinguishing tokens of a painting title (e.g. 'The Arnolfini Portrait' -> ['arnolfini', 'portrait'])."""
    raw = (title or "").strip()
    if not raw or textfold.fold(raw).strip() in _PLACEHOLDER_TITLES:
        return []
    toks = [w.strip("'") for w in _words_folded(raw) if w.strip("'") and w.strip("'") not in _STOP_WORDS]
    reduced = [w for w in toks if w not in _PARTICLES]
    if len(reduced) >= 2:
        return reduced
    return toks


def title_spoken(unquoted_text: str, title: str) -> bool:
    """True when the painting's distinguishing title words are spoken in `unquoted_text`."""
    req = title_tokens(title)
    if not req:
        return True
    have = {w[:-2] if w.endswith("'s") else w.strip("'") for w in _words_folded(unquoted_text)}
    if len(req) <= 3:
        return all(t in have for t in req)
    hits = sum(1 for t in req if t in have)
    return hits >= min(3, len(req))


def painter_surnames(artist: str) -> list[str]:
    """Distinguishing surname(s) for a painter, handling multi-word names and epithets like 'Jan van Eyck' or 'Hans Holbein the Younger'."""
    raw = (artist or "").strip()
    if not raw or textfold.fold(raw).strip() in _PLACEHOLDER_ARTISTS:
        return []
    cleaned = _EPITHETS.sub(" ", raw).strip(" ,.")
    pairs = sourcenames.surnames(cleaned)
    out: list[str] = []
    for sur, _ in pairs:
        parts = re.split(r"[-‐-―\s]+", textfold.fold(sur).strip())
        last = (parts[-1] if parts else "").strip("'")
        if len(last) >= 2 and last not in _PARTICLES and last not in _PLACEHOLDER_ARTISTS:
            out.append(last)
    if not out:
        toks = [w.strip("'") for w in _words_folded(cleaned) if w.strip("'") and w.strip("'") not in _STOP_WORDS]
        if toks:
            out.append(toks[-1])
    return out


def painter_spoken(unquoted_text: str, artist: str) -> bool:
    """True when any surname of the painter is spoken in `unquoted_text`."""
    surs = painter_surnames(artist)
    if not surs:
        return True
    have = {w[:-2] if w.endswith("'s") else w.strip("'") for w in _words_folded(unquoted_text)}
    return any(s in have for s in surs)


def find_roadmap(text: str) -> list[str]:
    """Return matching plan-of-the-video phrases found in `text`, in appearance order."""
    hits: list[tuple[int, str]] = []
    for rx in _ROADMAP:
        m = rx.search(text or "")
        if m:
            hits.append((m.start(), m.group(0)))
    hits.sort(key=lambda x: x[0])
    seen: list[str] = []
    for _, phrase in hits:
        if phrase not in seen:
            seen.append(phrase)
    return seen


def inspect(ch: NChapter | None, brief: dict | None) -> dict:
    """Inspect a cold-open chapter against the six cold-open rules. Safe when `ch` is empty or `brief` is None."""
    if ch is None or not ch.beats:
        return {"present": False}
    non_empty = [b for b in ch.beats if (b.text or "").strip()]
    if not non_empty:
        return {"present": False}

    first_beat = non_empty[0]
    last_beat = non_empty[-1]
    early_text, total_words = first_n_words(non_empty, EARLY_WINDOW_WORDS)
    full_text = " ".join((b.text or "").strip() for b in non_empty)
    unquoted_full = strip_quotations(full_text)
    unquoted_early = strip_quotations(early_text)

    painting = (brief or {}).get("painting") if isinstance(brief, dict) else None
    has_painting = isinstance(painting, dict) and bool((painting.get("title") or "").strip() or (painting.get("artist") or "").strip())
    title = str((painting or {}).get("title") or "").strip()
    artist = str((painting or {}).get("artist") or "").strip()

    missing: list[str] = []
    late: list[str] = []
    if has_painting:
        has_title_need = bool(title_tokens(title))
        has_artist_need = bool(painter_surnames(artist))
        t_ok = title_spoken(unquoted_full, title) if has_title_need else True
        a_ok = painter_spoken(unquoted_full, artist) if has_artist_need else True
        if not t_ok:
            missing.append("title")
        if not a_ok:
            missing.append("artist")
        if not missing:
            if has_title_need and not title_spoken(unquoted_early, title):
                late.append("title")
            if has_artist_need and not painter_spoken(unquoted_early, artist):
                late.append("artist")

    roadmap_hits: list[tuple[str, list[str]]] = []
    for b in non_empty:
        found = find_roadmap(b.text)
        if found:
            roadmap_hits.append((b.id, found))

    return {
        "present": True,
        "chapter": ch.id,
        "first_beat_id": first_beat.id,
        "first_beat_words": count_words(first_beat.text),
        "last_beat_id": last_beat.id,
        "has_closing_question": "?" in last_beat.text,
        "has_early_turn": bool(_EARLY_TURN.search(early_text)),
        "total_words": total_words,
        "missing_names": missing,
        "late_names": late,
        "title": title,
        "artist": artist,
        "roadmap": roadmap_hits,
    }
