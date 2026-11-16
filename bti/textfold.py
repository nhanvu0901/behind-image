"""One way to fold text for comparing and searching, shared by the engine (word anchors), the library (search, artwork
matching) and the script stage (word and heading matching).

`fold` lower-cases and removes accents of any script (NFKD, then the combining marks go) and maps the letters that do not
decompose to their base letters: đ/Đ to d, ø to o, ł to l, ß to ss, æ to ae and so on. `tokens` folds and splits into words made of
letters and digits of any script. Use these for BOTH sides of every comparison."""
from __future__ import annotations

import re
import unicodedata

_SPECIAL = str.maketrans({"đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "ħ": "h", "Ħ": "H",
                          "ı": "i", "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "þ": "th", "Þ": "TH", "’": "'"})
_NOT_WORD = re.compile(r"[\W_]+")


def fold(s) -> str:
    """Case-folded text without accents; everything else is kept (spaces, punctuation)."""
    s = unicodedata.normalize("NFKD", str(s or "").translate(_SPECIAL).casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def squash(s) -> str:
    """`fold`, then every run of non-letters/digits removed (the engine's anchor comparison)."""
    return _NOT_WORD.sub("", fold(s))


def tokens(s) -> list[str]:
    """`fold`, split into words of letters and digits of any script."""
    return [t for t in _NOT_WORD.split(fold(s)) if t]


def norm(s) -> str:
    """Tokens joined by single spaces: the form used for substring search and key building."""
    return " ".join(tokens(s))
