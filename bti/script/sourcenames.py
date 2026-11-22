"""Does a text name the books it was written from? Pure functions on strings: no model, no project, no files.

The video is a story told by a narrator to a viewer who has never heard of the books behind it, so the spoken text must not name their
authors, must not speak of "the books" or "the sources", and must not carry a remark that was meant for the owner. The checks of the
script step (`validate.py`) and the criterion of the bench (`bti/evals/criteria.py`) both read this module, so the app and the bench
look at the same thing.

    author_names(brief)            {surname: [given names]} of every source book of the project (from the brief's `author` fields)
    find_authors(text, names)      the surnames the text names, in order of first appearance
    find_source_talk(text)         [(kind, words)]: where the text speaks about the sources themselves
    find_owner_address(text)       [words]: where a text addresses the owner or gives an instruction (the outline's conflict text)

What counts, and what does not (each rule is tested in tests/script/test_sourcenames.py):

  * An author is named when the SURNAME stands in the text as a whole word with its capital: "Payne says", "Payne's reading", "Brooke-Hitching"
    and the short form "Hitching" of a double surname, "Susie Hodge". The lower-case word is another word ("hitching a ride"), a longer word is
    another word ("Hodges").
  * A historical person who shares the surname is not an author: when another capitalised word stands before the surname inside a sentence
    ("Sir Thomas Hodge", "the sculptor John Payne"), the text names somebody else, and so does an article before it ("the Payne family"). The word
    before does not save the hit when it is the author's own given name ("Susie Hodge"), an initial ("J. Payne"), a title of a modern writer
    (Dr, Prof, Mr, Mrs, Ms), or the first word of its sentence ("Then Hodge says"). A later bare "Hodge" for that other person is a false hit:
    the check is a warning for a person to read, not a verdict.
  * "the Book of Exodus", "a book on the shelf", "the books on the table" are the painted or the biblical thing, not the sources: the plural
    "the books" counts only when no place or relation word follows it, and the singular "the book" only when it SAYS something ("the book argues").
  * The titles of the books are not looked for: some are plain phrases ("A New Way of Seeing"), and the prompts already forbid naming them.
"""
from __future__ import annotations

import re

# words that are not a surname even when the author field ends with one
_NOT_SURNAMES = {"anonymous", "unknown", "various", "editors", "editor", "staff", "author", "authors", "al", "et"}
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "dr", "prof"}
_SPLIT = re.compile(r"\s*(?:;|&|/|\band\b|\bund\b|\bwith\b)\s*", re.I)
_TITLES = {"dr", "prof", "professor", "mr", "mrs", "ms", "miss"}        # "Dr Hodge" is still the author
MIN_SURNAME = 3                                                          # "Li" and "Wu" are too short to look for as a whole word


def _tokens(person: str) -> list[str]:
    out = []
    for t in person.replace(" ", " ").split():
        if t.strip(".,").lower() in _SUFFIXES:
            continue
        out.append(t.strip(","))
    return out


def surnames(author: str) -> list[tuple[str, list[str]]]:
    """[(surname, given names)] of the people in an author field of a book (`book.json` `author`).

    "James Payne" -> [("Payne", ["James"])]; "Rose-Marie and Rainer Hagen" -> [("Hagen", ["Rose-Marie", "Rainer"])];
    "Edward Brooke-Hitching" -> [("Brooke-Hitching", ["Edward"])]; "Payne, James" -> [("Payne", ["James"])].
    A name of one word is taken as a surname only when no other person of the field has a longer name."""
    people: list[list[str]] = []
    for part in _SPLIT.split(str(author or "")):
        part = part.strip(" .")
        if not part:
            continue
        if "," in part:
            bits = [b.strip() for b in part.split(",") if b.strip()]
            if len(bits) == 2 and len(bits[0].split()) == 1:            # "Surname, Given names"
                people.append(_tokens(bits[1]) + [bits[0]])
            else:
                people += [_tokens(b) for b in bits]
        else:
            people.append(_tokens(part))
    people = [p for p in people if p]
    full = [p for p in people if len(p) >= 2]
    singles = [p[0] for p in people if len(p) == 1]
    out: list[tuple[str, list[str]]] = []
    if full:
        given_shared = singles                                           # "Rose-Marie and Rainer Hagen": the single word is a given name
        for p in full:
            out.append((p[-1], list(p[:-1]) + given_shared))
    else:
        out = [(s, []) for s in singles]
    seen, res = set(), []
    for sur, given in out:
        key = sur.lower()
        letters = re.sub(r"[^\w]", "", sur)
        if key in seen or key in _NOT_SURNAMES or len(letters) < MIN_SURNAME:
            continue
        seen.add(key)
        res.append((sur, given))
    return res


def author_names(brief: dict | None) -> dict[str, list[str]]:
    """{surname: [given names]} of every source of the brief, whether it is included or not (a narration that names the author of a book it
    was not given is just as much a review of books)."""
    out: dict[str, list[str]] = {}
    for s in (brief or {}).get("sources") or []:
        if not isinstance(s, dict):
            continue
        for sur, given in surnames(s.get("author") or ""):
            out.setdefault(sur, [])
            out[sur] += [g for g in given if g not in out[sur]]
    return out


def _name_regex(surname: str) -> re.Pattern:
    """The surname as a whole word, with its capital. A double surname is found by its last part too ("Brooke-Hitching", "Brooke Hitching" and
    "Hitching" all contain "Hitching"), because a narrator shortens it."""
    last = re.split(r"[-‐-―\s]+", surname.strip())[-1]
    return re.compile(r"(?<![\w])" + re.escape(last) + r"(?![\w])")


_SENTENCE_END = re.compile(r"[.!?][\"”’')\]]*\s+$")


def _word_before(text: str, start: int) -> tuple[str, bool] | None:
    """(the word right before `start`, whether it opens its sentence) or None when no word stands there (the text begins, or punctuation)."""
    m = re.search(r"([^\W\d_][\w'’\-]*)\.?[ \t]+$", text[:start])
    if not m:
        return None
    before = text[:m.start(1)]
    opens = not before.strip() or bool(_SENTENCE_END.search(before)) or before.rstrip().endswith(("\n", ":", "“", "\""))
    return m.group(1), opens


def find_authors(text: str, names: dict[str, list[str]]) -> list[str]:
    """The surnames of `names` that `text` names as the author of a source, in order of first appearance (see the module's note on false hits)."""
    hits: list[tuple[int, str]] = []
    for sur, given in names.items():
        rx = _name_regex(sur)
        gl = {g.lower().strip(".") for g in given}
        for m in rx.finditer(text or ""):
            prev = _word_before(text, m.start())
            if prev:
                word, opens = prev
                w = word.lower().strip(".")
                if w in ("the", "a", "an"):                                   # "the Payne family": a narrator never says "the Payne says"
                    continue
                # another person: a capitalised word inside the sentence that is neither this author's given name, nor an initial ("J. Payne"),
                # nor a title of a modern writer
                if word[:1].isupper() and not opens and len(w) > 1 and w not in gl and w not in _TITLES:
                    continue
            hits.append((m.start(), sur))
            break
    return [s for _, s in sorted(hits)]


# -------------------------------------------------------------------------------------------------------- speaking about the sources
_PLACE = r"on|in|at|by|beside|under|near|behind|above|below|lying|stacked|piled|that|which|he|she|they|and|of|from|around|between|upon|inside|within"
_SAYS = (r"says?|said|argues?|argued|notes?|noted|states?|stated|claims?|claimed|calls?|called|reads?|suggests?|suggested|agrees?|agreed|disagrees?|"
         r"disagreed|describes?|described|adds?|points|explains?|tells?|mentions?|reports?|records?|insists?|names?|gives?|offers?|differs?|differ|"
         r"settle|stop|stops|split|splits|diverge|conflict|contradict|contradicts|contradicted")

# (kind, regex): kind `books` the books, `sources` the sources, `passage` a passage of a book, `doubt` a doubt about a source or a remark to
# the owner. Every pattern is case-insensitive.
_TALK: list[tuple[str, re.Pattern]] = [(k, re.compile(p, re.I)) for k, p in (
    ("books", r"\b(?:both|two|three|all three|the two|the three|the other|these|those|two of the|three of the|one of the|each of the|"
              r"both of the|most of the)\s+books\b"),
    ("books", rf"\bthe books\b(?!\s+(?:{_PLACE})\b)"),
    ("books", rf"\b(?:the|this|that|which|each|every)\s+book\s+(?:{_SAYS})\b"),
    ("books", r"\b(?:both|two|three|all three|these|those|our|the)\s+authors\b"),
    ("books", rf"\bthe author\s+(?:{_SAYS}|writes|wrote)\b"),
    ("sources", r"\b(?:the|both|two|three|all three|all the|these|those|our|several|most|other)\s+sources\b(?!\s+of\b)"),
    ("sources", r"\b(?:this|that)\s+source\b(?!\s+of\b)"),
    ("sources", rf"\b(?:the|one|another|a single|only one)\s+source\s+(?:{_SAYS})\b"),
    ("passage", r"\b(?:this|that|the)\s+passage\s+(?:may|might|could|seems?|appears?|probably|perhaps|possibly)\b"),
    ("passage", r"\b(?:this|that|the|these|those)\s+paragraphs?\b"),
    ("doubt", r"\b(?:may|might|could)\s+(?:actually\s+)?(?:describe|refer to|be about|be describing|concern)\s+(?:a\s+|an\s+)?(?:different|another|other)\s+"
              r"(?:painting|work|picture|portrait|artwork)\b"),
    ("doubt", r"\b(?:unreliable|untrustworthy)\s+(?:source|sources|book|books|passage|text|account|translation|edition)\b"),
    ("doubt", r"\b(?:source|sources|book|books|passage|text|account|translation|edition)\s+(?:is|are|may be|might be|seems|appears)\s+(?:not\s+)?"
              r"(?:unreliable|doubtful|dubious|questionable|mistaken|garbled|wrong)\b"),
    ("doubt", r"\b(?:machine[- ]translat\w+|mistranslat\w+)\b"),
    ("doubt", r"\bbefore (?:it|this|that) is used\b"),
    ("owner", r"\b(?:the owner|the editor|the operator|the reader|the checker)\s+(?:should|must|needs? to|may want to|might want to|ought to)\b"),
    ("owner", r"\b(?:please|kindly)\s+(?:check|verify|note|confirm|review|ignore)\b"),
    ("owner", r"\b(?:TODO|FIXME|TBD)\b"),
)]


def find_source_talk(text: str) -> list[tuple[str, str]]:
    """[(kind, the words found)] where the text speaks about the sources themselves, or carries a remark that was meant for the owner. At most
    one hit per kind, the first in the text (a line is flagged once, the sentence names what was found)."""
    seen: dict[str, tuple[int, str]] = {}
    for kind, rx in _TALK:
        m = rx.search(text or "")
        if m and (kind not in seen or m.start() < seen[kind][0]):
            seen[kind] = (m.start(), m.group(0))
    return [(k, w) for k, (_, w) in sorted(seen.items(), key=lambda kv: kv[1][0])]


# -------------------------------------------------------------------------------------------------------- a remark to the owner
_OWNER = [re.compile(p, re.I) for p in (
    r"\b(?:the )?(?:owner|operator|editor|user|reviewer|person who approves)\s+(?:should|must|needs? to|may want to|might want to|can|could|will want to|ought to)\b",
    r"\b(?:before it is used|before using (?:it|this|that)|should be checked|needs? (?:checking|to be checked|verification|a check)|must be verified|"
    r"to be verified|worth checking|worth a check)\b",
    r"(?:^|[.!?]\s+)(?:please\s+)?(?:check|verify|confirm|review|ignore|disregard|do not use|don't use|do not rely|use with care|use with caution|treat (?:it|this)|"
    r"be careful|beware|remember to|make sure|take care)\b",
    r"\b(?:TODO|FIXME|TBD)\b",
    r"\b(?:please|kindly)\s+(?:check|verify|note|confirm|review|ignore)\b",
)]


def find_owner_address(text: str) -> list[str]:
    """The words where `text` (a fact's conflict text) speaks to the owner or gives an instruction instead of stating what the sources say."""
    out = []
    for rx in _OWNER:
        m = rx.search(text or "")
        if m:
            out.append(m.group(0).strip(" .!?"))
    return out


# -------------------------------------------------------------------------------------------------------- attribution phrases (literature-review voice)
ATTRIBUTION_PHRASES: tuple[str, ...] = (
    "one reading",
    "another reading",
    "a reading",
    "has been read as",
    "is read as",
    "some see",
    "others see",
    "historians",
    "scholars",
    "critics",
    "has been described as",
    "according to",
    "it has been suggested",
    "is thought to",
    "is believed",
)

_ATTRIBUTION: list[re.Pattern] = [
    (re.compile(r"\ba\s+reading\b(?!\s+(?:room|desk|lamp|table|stand|glass|glasses)\b)", re.I)
     if p == "a reading"
     else re.compile(r"\b" + re.escape(p).replace(r"\ ", r"\s+") + r"\b", re.I))
    for p in ATTRIBUTION_PHRASES
]


def find_attribution(text: str) -> list[str]:
    """Return attribution / literature-review phrases in `text`, in order of first appearance (case-insensitively deduplicated)."""
    hits: list[tuple[int, str]] = []
    for rx in _ATTRIBUTION:
        for m in rx.finditer(text or ""):
            hits.append((m.start(), m.group(0)))
    hits.sort(key=lambda x: x[0])
    seen: set[str] = set()
    out: list[str] = []
    for _, phrase in hits:
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            out.append(phrase)
    return out
