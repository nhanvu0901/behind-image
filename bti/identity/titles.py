"""Text rules of the channel identity: chapter numbers, title case, the artist and year line. Pure functions, no I/O.

Titles may hold non-ASCII letters and apostrophes ("L'Ecole d'Athenes", "Dürer's Hands"): nothing here uses `str.title()` (which
would make "Dürer'S"); only the first letter of a word is raised, and a word that is already mixed case is left as it is.
"""
from __future__ import annotations

import re

# Small words of a title: lower case, except as the first or the last word of the title, or the first word after a colon.
SMALL_WORDS = frozenset(("a", "an", "the", "and", "or", "nor", "but", "for", "yet", "so", "of", "in", "on", "to", "at", "by", "as", "vs", "via",
                         "per", "with", "from", "into"))
# Particles inside a person's name: "Jan van Eyck", "Leonardo da Vinci".
NAME_PARTICLES = frozenset(("van", "von", "der", "den", "de", "del", "della", "di", "da", "du", "le", "la", "el", "al", "bin", "ibn", "ten", "ter", "zu"))

_NUMBER = re.compile(r"^\s*\d{1,3}\s*[.)]\s*")
_SPACE = re.compile(r"\s+")


def strip_number(text: str) -> str:
    """"5. The Mirror" -> "The Mirror". Only a number followed by a dot or a bracket is removed ("1434 Portrait" stays)."""
    return _NUMBER.sub("", str(text or "")).strip()


def one_line(text) -> str:
    return _SPACE.sub(" ", str(text or "")).strip()


def is_shouting(text: str) -> bool:
    """True when the text has letters and none of them is lower case (a card written in capitals)."""
    letters = [c for c in str(text or "") if c.isalpha()]
    return bool(letters) and not any(c.islower() for c in letters)


def _raise_first(word: str) -> str:
    """The first letter of `word` in capitals; after a one-letter start and an apostrophe ("O'Keeffe", "D'Athenes") the next one too."""
    for i, c in enumerate(word):
        if c.isalpha():
            out = word[:i] + c.upper() + word[i + 1:]
            j = i + 1
            if j + 1 < len(out) and out[j] in "'\u2019" and out[j + 1].isalpha():
                out = out[:j + 1] + out[j + 1].upper() + out[j + 2:]
            return out
    return word


def _bare(word: str) -> str:
    return "".join(c for c in word if c.isalnum()).lower()


def _case(text: str, small: frozenset) -> str:
    text = one_line(text)
    if not text:
        return ""
    shout = is_shouting(text)
    out = []
    after_colon = False
    tokens = text.split(" ")
    for n, token in enumerate(tokens):
        parts = token.split("-")
        done = []
        for k, part in enumerate(parts):
            # the first word, the first after a colon (a new title starts there) and the last word are capitalised whatever they are
            first = (n == 0 and k == 0) or (after_colon and k == 0) or (n == len(tokens) - 1 and k == len(parts) - 1)
            word = part.lower() if shout else part
            if not first and _bare(part) in small:
                done.append(part.lower())
            else:
                done.append(_raise_first(word))
        out.append("-".join(done))
        after_colon = token.endswith(":")
    return " ".join(out)


def title_case(text: str) -> str:
    """"THE MERCHANT AND HIS BRAND" -> "The Merchant and His Brand". Text with lower case letters keeps the case of its words
    (only the first letter of each is raised, small words go down except first, last and after a colon); applying it twice gives the same
    text."""
    return _case(text, SMALL_WORDS)


def name_case(text: str) -> str:
    """The same for a person's name: "JAN VAN EYCK" -> "Jan van Eyck"."""
    return _case(text, NAME_PARTICLES)


def pretty(text: str, *, name: bool = False) -> str:
    """A text written in capitals gets its case back; any other text is kept exactly as it is (only blanks are tidied)."""
    t = one_line(text)
    if not t or not is_shouting(t):
        return t
    return name_case(t) if name else title_case(t)


def mark_title(number: int, raw: str) -> str:
    """The line of a chapter mark: number, a dot, the title in title case. "THE MIRROR", 5 -> "5. The Mirror"."""
    return "%d. %s" % (int(number), title_case(strip_number(raw)))


def artist_year(artist: str, year) -> str:
    """"Jan van Eyck, 1434" (the second line of the label); one part alone when the other is empty."""
    a, y = one_line(artist), one_line(year)
    return ", ".join(p for p in (a, y) if p)


def small_caps_line(artist: str, year) -> str:
    """"JAN VAN EYCK · 1434": the line under the title of the `dim` opening, in capitals."""
    a, y = one_line(artist), one_line(year)
    return " · ".join(p for p in (a.upper(), y.upper()) if p)
