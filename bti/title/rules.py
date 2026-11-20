"""THE rules of a video's title: the limits and the refused phrases, in ONE place.

The task template the agent reads (`skills/title/TASK.template.md`) is rendered from the values below (`template_values()`), and the program's
check (`check.py`) reads the same values, so what the agent is told and what the program refuses cannot differ. A test renders the template and
looks for every phrase and number of this module in the text.

The wording of the rules is the owner's and the coordinator's (see docs/qa/FIX_title_step.md); this module holds only the numbers, the words and
the regular expressions that find them."""
from __future__ import annotations

import re

SCHEMA = "bti.title.choice/1"            # the file the agent writes (out/title.json)

# ---- length (rule 8): the limit is a refusal, the best range is a warning
MAX_CHARS = 60
BEST_MIN = 28
BEST_MAX = 55
MAX_WORDS = 9
MAX_QUESTION_MARKS = 1
PERSON_MAX_CHARS = MAX_CHARS            # a title typed by a person or an operator: the same limit, and one line (not the banned phrases)

# ---- the candidates (section 5 of the template)
MIN_CANDIDATES = 5
MAX_CANDIDATES = 8
WRITE_AT_LEAST = 12                     # candidates to write before striking the ones that fail (section 3; not checkable)
FORMS_AT_LEAST = 5                      # different forms among them (section 3; not checkable)
SCORE_KEYS = ("curiosity", "concrete", "central", "clear")
SCORE_MIN, SCORE_MAX = 1, 5
FIRST_CENTRAL_MIN = 4                   # a first choice that scores under this on `central` promises a sentence, not the video (section 3, step 5)
FORMS = ("contradiction", "question", "hidden", "really_is", "object", "number", "other")
WHY_MAX_CHARS = 240                     # a reason is one short sentence
LINES_MAX = 12                          # lines cited by one candidate

NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
                12: "twelve"}

# ---- rule 6: titles that could sit on any video. (what the owner reads, the pattern that finds it in a title)
VAGUE = (
    ("The Hidden Meaning", r"\bthe hidden meaning\b"),
    ("More Than Meets the Eye", r"\bmore than meets the eye\b"),
    ("A Closer Look", r"\ba closer look\b"),
    ("The Story Behind ...", r"\bthe story behind\b"),
    ("... Explained", r"\bexplained\W*$"),
    ("The Truth About ...", r"\bthe truth about\b"),
)

# ---- rule 7: borrowed excitement. Allowed only when the narration itself says exactly that (see check.py: a line the candidate cites holds the phrase)
BORROWED = (
    ("shocking", r"\bshocking\b"),
    ("secret", r"\bsecrets?\b"),
    ("insane", r"\binsane\b"),
    ("you won't believe", r"\byou won['’]t believe\b"),
    ("nobody knows", r"\bnobody knows\b"),
    ("the first", r"\bthe first\b"),
    ("the only", r"\bthe only\b"),
    ("the most", r"\bthe most\b"),
)

_VAGUE_RE = tuple((shown, re.compile(p, re.I)) for shown, p in VAGUE)
_BORROWED_RE = tuple((shown, re.compile(p, re.I)) for shown, p in BORROWED)


def norm(text: str) -> str:
    """One space between words, curly apostrophes made straight: the form the phrases are looked for in."""
    return re.sub(r"\s+", " ", str(text or "").replace("’", "'").replace("‘", "'")).strip()


def vague_in(title: str) -> list[str]:
    """The phrases of rule 6 that the title holds (as the owner reads them)."""
    t = norm(title)
    return [shown for shown, rx in _VAGUE_RE if rx.search(t)]


def borrowed_in(title: str) -> list[str]:
    """The words and phrases of rule 7 that the title holds."""
    t = norm(title)
    return [shown for shown, rx in _BORROWED_RE if rx.search(t)]


def borrowed_in_text(shown: str, text: str) -> bool:
    """Does `text` (a line of the narration) hold the phrase `shown` of rule 7?"""
    rx = dict(_BORROWED_RE).get(shown)
    return bool(rx and rx.search(norm(text)))


# ---- how the rules are written into the template
def quoted(items) -> str:
    """`"a", "b", "c"` (the way rules 6 and 7 of the template list them)."""
    return ", ".join('"%s"' % s for s in items)


def number_word(n: int) -> str:
    return NUMBER_WORDS.get(n, str(n))


def template_values() -> dict:
    """The values of the placeholders of the template that come from the rules (the renderer adds the project's own)."""
    return {
        "VAGUE_PHRASES": quoted(s for s, _ in VAGUE),
        "BORROWED_WORDS": quoted(s for s, _ in BORROWED),
        "BEST_MIN": BEST_MIN, "BEST_MAX": BEST_MAX, "MAX_CHARS": MAX_CHARS, "MAX_WORDS_TEXT": number_word(MAX_WORDS),
        "WRITE_AT_LEAST_TEXT": number_word(WRITE_AT_LEAST), "FORMS_AT_LEAST_TEXT": number_word(FORMS_AT_LEAST),
        "MIN_CANDIDATES_TEXT": number_word(MIN_CANDIDATES), "MAX_CANDIDATES_TEXT": number_word(MAX_CANDIDATES),
        "FIRST_CENTRAL_MIN": FIRST_CENTRAL_MIN, "FORMS_LIST": ", ".join("`%s`" % f for f in FORMS),
    }


def public() -> dict:
    """What `GET /api/projects/{pid}/title` says about the limits (the page shows the counter)."""
    return {"max_chars": MAX_CHARS, "best": [BEST_MIN, BEST_MAX], "max_words": MAX_WORDS, "person_max_chars": PERSON_MAX_CHARS}
