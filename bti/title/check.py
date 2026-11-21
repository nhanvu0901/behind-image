"""The program's check of a title: of the file the agent writes (`out/title.json`) and of a title a person or an operator types.

    check_choice(obj, lines)   -> Report     the agent's file; `lines` is {narration line id: its text}. Errors are refusals (the repair message is their text),
                                             warnings are what the template says the check only warns about. `Report.value` is the cleaned document
                                             (`candidates`, the first one is the choice), only when there is no error.
    check_text(text)           -> (clean text, problem | None)     a title a person typed: one line, at most MAX_CHARS characters (not the banned phrases)

The limits and the refused phrases are those of `rules.py`, the one place the task template is rendered from."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from bti.identity.titles import SMALL_WORDS, one_line

from . import rules as R

VIETNAMESE = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
BRACKETS = "()[]{}<>〈〉「」"
DOUBLE_QUOTES = "\"“”„«»‘"          # a straight or curly double quote, guillemets, an opening single quote (the apostrophe stays allowed)
SECOND_HALF = re.compile(r"[:：|–—]|\s-\s")
WORD = re.compile(r"[a-z]+(?:'[a-z]+)?", re.I)
DIGITS = re.compile(r"\d[\d,.]*\d|\d")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    value: dict | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def text(self) -> str:
        """What `./check` prints, and what the repair message carries."""
        lines = ["ERROR " + e for e in self.errors] + ["WARNING " + w for w in self.warnings]
        lines.append("%d error(s), %d warning(s)" % (len(self.errors), len(self.warnings)))
        return "\n".join(lines)

    def problems(self) -> str | None:
        return None if self.ok else self.text()


def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0x200D, 0xFE0F, 0x20E3) or 0x2B00 <= o <= 0x2BFF or unicodedata.category(ch) == "So" and o > 0x2000


def _shouted(word: str) -> bool:
    letters = [c for c in word if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters)


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(R.norm(text))]


def _stem(w: str) -> str:
    w = w[:-2] if w.endswith("'s") else w
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def content_words(text: str) -> set[str]:
    return {_stem(w) for w in _tokens(text) if w not in SMALL_WORDS and len(w) >= 3}


def _total(c: dict) -> int:
    s = c.get("scores") or {}
    return sum(int(s.get(k) or 0) for k in R.SCORE_KEYS)


def _title_case_problem(title: str) -> str | None:
    """A word that should start with a capital and does not (the small words and words with a digit are let through)."""
    words = [w for w in re.split(r"\s+", R.norm(title)) if w]
    for i, w in enumerate(words):
        bare = re.sub(r"^[^\w]+|[^\w]+$", "", w)
        if not bare or not bare[0].isalpha() or any(ch.isdigit() for ch in bare):
            continue
        if bare[0].islower() and (bare.lower() not in SMALL_WORDS or i == 0 or i == len(words) - 1):
            return bare
    return None


def _title_problems(title: str, cited_text: str, where: str, rep: Report) -> None:
    """The rules a title is judged by, appended to `rep`. `cited_text`: the text of the lines the candidate cites (a word of rule 7 passes when it says it too)."""
    shown = '%s ("%s")' % (where, title)
    n = len(title)
    if n > R.MAX_CHARS:
        rep.errors.append("%s is %d characters: the limit is %d (longer is cut off on a phone). Shorten it or replace it." % (shown, n, R.MAX_CHARS))
    elif not R.BEST_MIN <= n <= R.BEST_MAX:
        rep.warnings.append("%s is %d characters: %d to %d is best." % (shown, n, R.BEST_MIN, R.BEST_MAX))
    words = title.split()
    if len(words) > R.MAX_WORDS:
        rep.errors.append("%s has %d words: at most %d." % (shown, len(words), R.MAX_WORDS))
    elif len(words) > R.BEST_MAX_WORDS:
        rep.warnings.append("%s has %d words: %d or fewer is best (at most %d)." % (shown, len(words), R.BEST_MAX_WORDS, R.MAX_WORDS))
    for phrase in R.vague_in(title):
        rep.errors.append('%s holds "%s": a title that could sit on any video (rule 6).' % (shown, phrase))
    for phrase in R.borrowed_in(title):
        if not R.borrowed_in_text(phrase, cited_text):
            rep.errors.append('%s holds "%s": borrowed excitement (rule 7). Only a line you cite may say it first.' % (shown, phrase))
    if SECOND_HALF.search(title):
        rep.errors.append("%s has a colon, a dash or a bar that makes a second half: one line, one idea (rule 8)." % shown)
    if any(c in BRACKETS for c in title):
        rep.errors.append("%s has brackets: none are allowed (rule 8)." % shown)
    if any(_is_emoji(c) for c in title):
        rep.errors.append("%s has an emoji or a symbol: none are allowed (rule 8)." % shown)
    loud = [w for w in words if _shouted(re.sub(r"[^\w']", "", w))]
    if loud:
        rep.errors.append("%s has a word in capitals (%s): none are allowed (rule 8)." % (shown, ", ".join(loud[:3])))
    if title.count("?") > R.MAX_QUESTION_MARKS:
        rep.errors.append("%s has %d question marks: at most %d." % (shown, title.count("?"), R.MAX_QUESTION_MARKS))
    held = cited_text.replace(",", "")
    for d in DIGITS.findall(title):
        if d.replace(",", "") not in held:
            rep.errors.append("%s has the number %s and none of the lines it cites says it (rule 3). Cite the line that says it, or write what the narration writes." % (shown, d))
    if any(c in DOUBLE_QUOTES for c in title):
        rep.warnings.append("%s has quotation marks: only when the words are written in the painting itself (rule 8)." % shown)
    bad = _title_case_problem(title)
    if bad:
        rep.warnings.append('%s is not in Title Case: "%s" starts with a small letter (rule 8).' % (shown, bad))


def _clean_candidate(i: int, c: Any, lines: dict, rep: Report) -> dict | None:
    where = "candidates[%d]" % i
    if not isinstance(c, dict):
        rep.errors.append("%s must be an object {text, form, lines, scores, why}" % where)
        return None
    ok = True
    raw = c.get("text")
    if not isinstance(raw, str) or not raw.strip():
        rep.errors.append("%s.text must be the title, as text" % where)
        return None
    if "\n" in raw.strip() or "\r" in raw.strip():
        rep.errors.append("%s.text must be one line" % where)
    title = one_line(raw)
    # the form
    form = c.get("form")
    if form not in R.FORMS:
        rep.errors.append('%s.form must be one of %s (got %r)' % (where, ", ".join(R.FORMS), str(form)[:30]))
        ok = False
    # the lines it cites
    cited = c.get("lines")
    ids: list[str] = []
    if not (isinstance(cited, list) and cited and all(isinstance(x, str) for x in cited)):
        rep.errors.append("%s.lines must be a list of narration line ids (at least one) that make the title true" % where)
        ok = False
    else:
        ids = list(dict.fromkeys(cited))
        unknown = [x for x in ids if x not in lines]
        if unknown:
            rep.errors.append("%s.lines names %s: not a line of inputs/narration.json" % (where, ", ".join(unknown[:5])))
            ok = False
        if len(ids) > R.LINES_MAX:
            rep.errors.append("%s.lines cites %d lines: at most %d (the ones that make the title true)" % (where, len(ids), R.LINES_MAX))
            ok = False
    cited_text = " ".join(lines.get(x, "") for x in ids)
    # the scores
    scores = c.get("scores")
    clean_scores: dict = {}
    if not isinstance(scores, dict):
        rep.errors.append("%s.scores must be an object with %s" % (where, ", ".join(R.SCORE_KEYS)))
        ok = False
    else:
        for k in R.SCORE_KEYS:
            v = scores.get(k)
            if isinstance(v, bool) or not isinstance(v, int) or not R.SCORE_MIN <= v <= R.SCORE_MAX:
                rep.errors.append("%s.scores.%s must be a whole number from %d to %d" % (where, k, R.SCORE_MIN, R.SCORE_MAX))
                ok = False
            else:
                clean_scores[k] = v
    # the reason
    why = c.get("why")
    if not isinstance(why, str) or not why.strip():
        rep.errors.append("%s.why must be one short Vietnamese sentence (the owner reads it)" % where)
        ok = False
    else:
        why = one_line(why)
        if not VIETNAMESE.search(why):
            rep.errors.append("%s.why must be Vietnamese, with all its accents (the owner reads it)" % where)
            ok = False
        elif len(why) > R.WHY_MAX_CHARS:
            rep.errors.append("%s.why is %d characters: one short sentence, at most %d" % (where, len(why), R.WHY_MAX_CHARS))
            ok = False
    _title_problems(title, cited_text, where, rep)
    if ids and title and not (content_words(title) & content_words(cited_text)):
        rep.warnings.append('%s ("%s"): none of its words is in the lines it cites (%s): cite the lines that make it true (rule 3).' % (where, title, ", ".join(ids[:4])))
    if not ok:
        return None
    return {"text": title, "form": form, "lines": ids, "scores": clean_scores, "why": why}


def check_choice(obj: Any, lines: dict) -> Report:
    """The report of the agent's `out/title.json`. `lines`: {narration line id: text}."""
    rep = Report()
    if not isinstance(obj, dict):
        rep.errors.append("title.json must be a JSON object (see the end of TASK.md for its shape)")
        return rep
    if obj.get("schema") != R.SCHEMA:
        rep.errors.append('schema must be "%s"' % R.SCHEMA)
    cands = obj.get("candidates")
    if not isinstance(cands, list):
        rep.errors.append("candidates must be a list of %d to %d candidates" % (R.MIN_CANDIDATES, R.MAX_CANDIDATES))
        return rep
    if len(cands) < R.MIN_CANDIDATES:
        rep.errors.append("candidates has %d: at least %d are needed (every one passing every rule)" % (len(cands), R.MIN_CANDIDATES))
    if len(cands) > R.MAX_CANDIDATES:
        rep.errors.append("candidates has %d: at most %d (keep the best)" % (len(cands), R.MAX_CANDIDATES))
    clean: list[dict] = []
    seen: dict[str, int] = {}
    for i, c in enumerate(cands[:R.MAX_CANDIDATES + 4], 1):
        one = _clean_candidate(i, c, lines, rep)
        key = re.sub(r"[^a-z0-9]+", " ", R.norm(c.get("text") if isinstance(c, dict) and isinstance(c.get("text"), str) else "").lower()).strip()
        if key and key in seen:
            rep.errors.append("candidates[%d] has the same text as candidates[%d]: no two candidates say the same thing" % (i, seen[key]))
        elif key:
            seen[key] = i
        if one is not None:
            clean.append(one)
    if clean and len(clean) == len(cands):
        first = clean[0]
        if first["scores"].get("central", 0) < R.FIRST_CENTRAL_MIN:
            rep.warnings.append("the first candidate scores %d on `central`: under %d it is not the first choice, whatever its curiosity" % (first["scores"].get("central", 0), R.FIRST_CENTRAL_MIN))
        if _total(first) < max(_total(c) for c in clean):
            rep.warnings.append("the first candidate does not have the highest total score: the best goes first")
    if rep.ok:
        rep.value = {"candidates": clean}
    return rep


def check_text(text: Any) -> tuple[str, str | None]:
    """A title a person typed: (the text, None) or ("", the code of the problem): `title_invalid` (not text or empty), `title_not_one_line`, `title_too_long`.
    The banned phrases are not looked for here: a person may write what they want, up to the limit."""
    if not isinstance(text, str) or not text.strip():
        return "", "title_invalid"
    s = text.strip()
    if "\n" in s or "\r" in s:
        return "", "title_not_one_line"
    s = one_line(s)
    if len(s) > R.PERSON_MAX_CHARS:
        return "", "title_too_long"
    return s, None
