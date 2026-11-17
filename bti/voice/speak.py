"""Written text to spoken text (English).

The narration keeps the written form ("in 1434, Jan van Eyck painted ..."); the voice has to be given what is said
("in fourteen thirty-four, ..."). Everything here is a pure function.

The unit of work is a `Unit`: one or more written tokens (words as the narration spells them, split on white space) and the
words that are spoken for them. The unit is what lets the aligner give every WRITTEN word a time although the recogniser hears
spoken words ("1434" is heard as two words), and what keeps `timing.json` in the written words the storyboard anchors to.

Entry points: `speak_units(text, table)`, `speak(text, table)`, `cardinal(n)`, `ordinal(n)`, `year_words(n)`.
`table` is the per-project pronunciation table (written form -> spoken form); it is applied first, on whole tokens or on
runs of tokens, ignoring case and the punctuation around the run.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen",
         "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (10 ** 3, "thousand")]
_ORD_IRREG = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth", "nine": "ninth",
              "twelve": "twelfth"}
SCALE_WORDS = {"hundred", "thousand", "million", "billion", "trillion"}
MAX_NUMBER = 10 ** 15 - 1


@dataclass
class Unit:
    """`written`: the tokens of the narration; `spoken`: the text said for them (may be empty, may hold several words)."""
    written: list[str] = field(default_factory=list)
    spoken: str = ""

    def spoken_words(self) -> list[str]:
        return self.spoken.split()


# ---------------------------------------------------------------- numbers
def cardinal(n: int) -> str:
    """123 -> 'one hundred twenty-three' (no 'and', American style)."""
    n = int(n)
    if n < 0:
        return "minus " + cardinal(-n)
    if n > MAX_NUMBER:
        return " ".join(_ONES[int(c)] for c in str(n))      # too large to say as a number: digit by digit
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + ("-" + _ONES[o] if o else "")
    if n < 1000:
        h, r = divmod(n, 100)
        return _ONES[h] + " hundred" + (" " + cardinal(r) if r else "")
    for size, name in _SCALES:
        if n >= size:
            q, r = divmod(n, size)
            return cardinal(q) + " " + name + (" " + cardinal(r) if r else "")
    raise AssertionError("unreachable")


def _ordinal_word(w: str) -> str:
    """'twenty-one' -> 'twenty-first'; 'hundred' -> 'hundredth'; 'thirty' -> 'thirtieth'."""
    head, sep, last = w.rpartition("-")
    if not sep:
        head, sep, last = w.rpartition(" ")
    if last in _ORD_IRREG:
        last = _ORD_IRREG[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return head + sep + last


def ordinal(n: int) -> str:
    """15 -> 'fifteenth', 21 -> 'twenty-first', 100 -> 'one hundredth'."""
    return _ordinal_word(cardinal(n))


def _plural(words: str) -> str:
    """'thirty' -> 'thirties', 'hundred' -> 'hundreds'; only the last word changes."""
    head, sep, last = words.rpartition(" ")
    if last.endswith("y"):
        last = last[:-1] + "ies"
    else:
        last += "s"
    return head + sep + last


def year_words(y: int) -> str:
    """1434 -> 'fourteen thirty-four', 1905 -> 'nineteen oh five', 1900 -> 'nineteen hundred', 2007 -> 'two thousand seven',
    2020 -> 'twenty twenty', 1000 -> 'one thousand'."""
    y = int(y)
    if y % 1000 == 0:
        return cardinal(y)
    if 2000 <= y <= 2009:
        return cardinal(y)
    hi, lo = divmod(y, 100)
    if lo == 0:
        return cardinal(hi) + " hundred"
    if lo < 10:
        return cardinal(hi) + " oh " + cardinal(lo)
    return cardinal(hi) + " " + cardinal(lo)


def digits_words(s: str) -> str:
    return " ".join(_ONES[int(c)] for c in s if c.isdigit())


def decimal_words(whole: str, frac: str) -> str:
    return cardinal(int(whole.replace(",", "") or "0")) + " point " + digits_words(frac)


# ---------------------------------------------------------------- token anatomy
_LEAD = "\"“‘'([{"
_TRAIL = ".,;:!?\"”’')]}…"
_CURLY = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "…": "..."})
_ROMAN = re.compile(r"^(?=[IVXLCDM])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_ROMAN_VAL = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

REGNAL = {"henry", "louis", "charles", "philip", "pius", "john", "paul", "leo", "julius", "clement", "benedict", "gregory",
          "urban", "innocent", "alexander", "sixtus", "nicholas", "francis", "edward", "george", "william", "richard",
          "james", "frederick", "ferdinand", "napoleon", "maximilian", "rudolf", "alfonso", "elizabeth", "catherine",
          "peter", "boniface", "martin", "eugene", "adrian", "hadrian", "callixtus", "celestine", "honorius", "stephen",
          "victor", "anne", "mary", "joseph", "leopold", "otto", "ivan", "alexis", "christian", "gustav", "sigismund",
          "casimir", "manuel", "sebastian", "john-paul"}
CARDINAL_AFTER = {"war", "act", "chapter", "part", "book", "volume", "vol", "section", "phase", "scene", "canto", "psalm",
                  "season", "episode", "class", "type", "stage", "table", "figure", "fig", "plate", "number"}
COUNT_NOUNS = {"people", "men", "women", "pieces", "copies", "words", "years", "miles", "feet", "pounds", "dollars", "francs",
               "ducats", "florins", "guilders", "soldiers", "workers", "pages", "paintings", "works", "visitors", "votes",
               "books", "images", "pixels", "lines", "days", "hours", "minutes", "seconds", "cases", "deaths", "victims",
               "kilometres", "kilometers", "metres", "meters", "inches", "feet", "tons", "tonnes", "grams", "kilograms",
               "square", "cubic", "per", "times", "km", "cm", "mm", "kg", "lb", "lbs", "ft", "mph", "percent"}
YEAR_NOT_AFTER = {"about", "approximately", "over", "nearly", "some", "than", "only", "around", "roughly", "almost", "just",
                  "estimated", "fewer", "less", "more", "exactly", "all", "of"}
CURRENCY = {"$": ("dollar", "dollars", "cent", "cents"), "£": ("pound", "pounds", "penny", "pence"),
            "€": ("euro", "euros", "cent", "cents"), "¥": ("yen", "yen", "sen", "sen")}
ABBR = {   # lower-cased core (no final period) -> spoken
    "mr": "Mister", "mrs": "Missus", "ms": "Miss", "dr": "Doctor", "prof": "Professor", "st": "Saint", "mt": "Mount",
    "jr": "Junior", "sr": "Senior", "vs": "versus", "e.g": "for example", "i.e": "that is", "viz": "namely",
    "cf": "compare", "approx": "approximately", "etc": "et cetera", "fl": "active", "ed": "edited by", "eds": "edited by",
    "gen": "General", "col": "Colonel", "capt": "Captain", "lt": "Lieutenant", "sgt": "Sergeant", "rev": "Reverend",
    "hon": "Honorable", "fig": "figure", "figs": "figures", "vol": "volume", "vols": "volumes", "pl": "plate",
    "ca": "circa",
}
KEEP_PERIOD = {"etc"}               # may end a sentence: the period stays when the next word starts a new one
UNITS = {"cm": "centimeters", "mm": "millimeters", "km": "kilometers", "kg": "kilograms", "lb": "pounds", "lbs": "pounds",
         "ft": "feet", "mph": "miles per hour", "m": "meters", "g": "grams", "oz": "ounces", "kb": "kilobytes", "mb": "megabytes"}
YEAR_LABELS = {"ad": "A D", "bc": "B C", "ce": "C E", "bce": "B C E", "bp": "B P"}
SYMBOLS = {"&": "and", "+": "plus", "=": "equals", "@": "at", "×": "times", "*": "", "§": "section", "°": "degrees",
           "%": "percent", "≈": "about", "~": "about", "<": "less than", ">": "more than", "→": "to", "#": "number"}
FRACTIONS = {"½": "one half", "¼": "one quarter", "¾": "three quarters", "⅓": "one third", "⅔": "two thirds"}
DASHES = {"—", "–", "-", "―", "--"}

_RE_NUM = re.compile(r"^\d[\d,]*$")
_RE_DEC = re.compile(r"^(\d[\d,]*)\.(\d+)$")
_RE_ORD = re.compile(r"^(\d[\d,]*)(st|nd|rd|th)$", re.I)
_RE_YEARS = re.compile(r"^(\d{3,4})'?s$")
_RE_RANGE = re.compile(r"^(\d[\d,]*)[-–—](\d[\d,]*)$")
_RE_MONEY = re.compile(r"^([$£€¥])(\d[\d,]*)(?:\.(\d+))?$")
_RE_PCT = re.compile(r"^(\d[\d,]*(?:\.\d+)?)%$")
_RE_TIME = re.compile(r"^(\d{1,2}):(\d{2})(am|pm|a\.m\.|p\.m\.)?$", re.I)
_RE_DEG = re.compile(r"^(\d+(?:\.\d+)?)°([CF])?$")
_RE_FRAC = re.compile(r"^(\d{1,3})/(\d{1,3})$")
_RE_CIRCA = re.compile(r"^c(?:a)?\.(\d{3,4})$", re.I)
_RE_HASH = re.compile(r"^#(\d+)$")


def _split(tok: str) -> tuple[str, str, str]:
    """(leading punctuation, core, trailing punctuation) of one token."""
    i = 0
    while i < len(tok) and tok[i] in _LEAD:
        i += 1
    j = len(tok)
    while j > i and tok[j - 1] in _TRAIL:
        j -= 1
    return tok[:i], tok[i:j], tok[j:]


def roman_value(s: str) -> int | None:
    if not s or not _ROMAN.match(s):
        return None
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = _ROMAN_VAL[a]
        total += -v if b != " " and _ROMAN_VAL[b] > v else v
    return total if 1 <= total <= 39 else None


def _to_int(s: str) -> int:
    return int(s.replace(",", ""))


def _num_spoken(s: str, *, year_ok: bool = False) -> str:
    """A digit string (with commas) as spoken. Four digits without a comma may be a year."""
    if "," not in s and year_ok and len(s) == 4 and 1000 <= int(s) <= 2099:
        return year_words(int(s))
    return cardinal(_to_int(s))


def _money(sym: str, whole: str, frac: str | None, scale: str | None) -> str:
    one, many, c_one, c_many = CURRENCY[sym]
    w = _to_int(whole)
    if scale:                                   # "$1.5 million" -> "one point five million dollars"
        num = decimal_words(whole, frac) if frac else cardinal(w)
        return f"{num} {scale} {many}"
    if frac:
        if len(frac) == 2 or len(frac) == 1:
            c = int(frac.ljust(2, "0"))
            cents = f"{cardinal(c)} {c_one if c == 1 else c_many}"
            if w == 0:
                return cents
            return f"{cardinal(w)} {one if w == 1 else many} {cents}"
        return decimal_words(whole, frac) + " " + many
    return f"{cardinal(w)} {one if w == 1 else many}"


def _time(h: str, m: str, ap: str | None) -> str:
    hh, mm = int(h), int(m)
    say = cardinal(hh) if hh else "twelve"
    if mm == 0:
        say += "" if ap else " o'clock"
    elif mm < 10:
        say += " oh " + cardinal(mm)
    else:
        say += " " + cardinal(mm)
    if ap:
        say += " " + ("a m" if ap.lower().startswith("a") else "p m")
    return say


def _hyphen_parts(core: str) -> str | None:
    """'15th-century' -> 'fifteenth-century', '19th-and-20th' ..: convert the numeric parts of a hyphenated word."""
    if "-" not in core or core.startswith("-") or core.endswith("-"):
        return None
    parts = core.split("-")
    if not any(any(c.isdigit() for c in p) for p in parts):
        return None
    out = []
    for p in parts:
        m = _RE_ORD.match(p)
        if m:
            out.append(ordinal(_to_int(m.group(1))))
        elif _RE_NUM.match(p):
            out.append(cardinal(_to_int(p)))
        elif any(c.isdigit() for c in p):
            return None
        else:
            out.append(p)
    return "-".join(out)


def _next_core(toks: list[str], i: int) -> str:
    return _split(toks[i + 1])[1] if i + 1 < len(toks) else ""


def _convert(toks: list[str], i: int, prev_core: str) -> tuple[int, str]:
    """Convert the token at `i` (possibly with following tokens). Returns (tokens consumed, spoken core text WITHOUT the leading
    and trailing punctuation of the run). The caller re-attaches punctuation. Returns (1, core) unchanged when nothing applies."""
    lead, core, trail = _split(toks[i])
    low = core.lower()
    nxt = _next_core(toks, i)
    nxt_low = nxt.lower()

    if not core:
        return 1, ""
    # currency
    m = _RE_MONEY.match(core)
    if m:
        sym, whole, frac = m.groups()
        if nxt_low in SCALE_WORDS and not trail:
            return 2, _money(sym, whole, frac, nxt_low)
        return 1, _money(sym, whole, frac, None)
    m = _RE_PCT.match(core)
    if m:
        n = m.group(1)
        d = _RE_DEC.match(n)
        return 1, (decimal_words(d.group(1), d.group(2)) if d else cardinal(_to_int(n))) + " percent"
    m = _RE_TIME.match(core)
    if m:
        return 1, _time(*m.groups())
    m = _RE_DEG.match(core)
    if m:
        n = m.group(1)
        d = _RE_DEC.match(n)
        num = decimal_words(d.group(1), d.group(2)) if d else cardinal(int(n))
        return 1, num + " degrees" + {"C": " Celsius", "F": " Fahrenheit"}.get(m.group(2) or "", "")
    m = _RE_ORD.match(core)
    if m:
        return 1, ordinal(_to_int(m.group(1)))
    m = _RE_YEARS.match(core)
    if m:
        n = int(m.group(1))
        if 100 <= n <= 2099 and (n % 10 == 0):
            return 1, _plural(year_words(n))
    m = _RE_RANGE.match(core)
    if m:
        a, b = m.groups()
        left = _num_spoken(a, year_ok=True)
        if len(a) == 4 and len(b) == 2 and "," not in a:      # "1434-36": the second year is said short
            right = cardinal(int(b)) if int(b) >= 10 else "oh " + cardinal(int(b))
        else:
            right = _num_spoken(b, year_ok=True)
        return 1, f"{left} to {right}"
    m = _RE_CIRCA.match(core)
    if m:
        return 1, "circa " + _num_spoken(m.group(1), year_ok=True)
    m = _RE_FRAC.match(core)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        names = {2: "half", 3: "third", 4: "quarter"}
        if b in names and a >= 1:
            w = names[b] if a == 1 else (names[b] + "s")
            if b == 2 and a > 1:
                w = "halves"
            return 1, f"{cardinal(a)} {w}"
        return 1, f"{cardinal(a)} over {cardinal(b)}"
    m = _RE_DEC.match(core)
    if m:
        return 1, decimal_words(m.group(1), m.group(2))
    if _RE_NUM.match(core):
        n = core
        year_like = ("," not in n and len(n) == 4 and 1000 <= int(n) <= 2099 and nxt_low not in COUNT_NOUNS
                     and prev_core.lower() not in YEAR_NOT_AFTER)
        if nxt_low in YEAR_LABELS and "," not in n:
            year_like = True
        return 1, _num_spoken(n, year_ok=year_like)
    m = _RE_HASH.match(core)
    if m:
        return 1, "number " + cardinal(int(m.group(1)))
    if core in FRACTIONS:
        return 1, FRACTIONS[core]
    hp = _hyphen_parts(core)
    if hp is not None:
        return 1, hp
    # abbreviations and labels
    if low in YEAR_LABELS and core.isupper() or low in ("a.d", "b.c", "c.e", "b.c.e"):
        key = low.replace(".", "")
        return 1, YEAR_LABELS.get(key, core)
    if low in ("c", "ca") and trail.startswith(".") and re.match(r"^\d", nxt):
        return 1, "circa"
    if low == "no" and trail.startswith(".") and re.match(r"^\d", nxt):
        return 1, "number"
    if low == "al" and prev_core.lower() == "et" and trail.startswith("."):
        return 1, "alia"
    if low in ABBR and (trail.startswith(".") or low in ("vs", "e.g", "i.e")):
        return 1, ABBR[low]
    if low in UNITS and re.match(r"^\d[\d,.]*$", prev_core) and low not in ("m", "g"):
        return 1, UNITS[low]
    if low in ("m", "g") and re.match(r"^\d[\d,.]*$", prev_core) and not trail.startswith("."):
        return 1, UNITS[low]
    # Roman numerals after a name ("Henry VIII" -> "Henry the eighth"; "World War II" -> "World War two")
    base = core[:-2] if core.endswith("'s") else core
    suffix = "'s" if core.endswith("'s") else ""
    rv = roman_value(base)
    if rv is not None and prev_core[:1].isupper():
        p = prev_core.lower()
        if p in REGNAL:
            return 1, "the " + ordinal(rv) + suffix
        if p in CARDINAL_AFTER:
            return 1, cardinal(rv) + suffix
    if core in SYMBOLS:
        return 1, SYMBOLS[core]
    if core in FRACTIONS:
        return 1, FRACTIONS[core]
    # glued symbols: "AT&T" stays; "5×7" -> "5 by 7"
    if re.match(r"^\d+×\d+$", core):
        a, b = core.split("×")
        return 1, f"{cardinal(int(a))} by {cardinal(int(b))}"
    return 1, core


def _clean_spoken(s: str) -> str:
    s = s.translate(_CURLY)
    s = re.sub(r"[*_`]+", "", s)
    return re.sub(r"(?<=\w)\s*[—–―]\s*(?=\w)", ", ", s)     # a dash inside a sentence is a pause


def _apply_table(toks: list[str], table: dict[str, str] | None) -> list[Unit | str]:
    """Replace runs of tokens that the pronunciation table names. Returns a list in which a handled run is a Unit and every
    other token is still a plain string."""
    if not table:
        return list(toks)
    rules: dict[tuple[str, ...], str] = {}
    for k, v in table.items():
        key = tuple(w.lower() for w in str(k).split())
        if key and isinstance(v, str):
            rules[key] = v
    if not rules:
        return list(toks)
    longest = max(len(k) for k in rules)
    out: list[Unit | str] = []
    i = 0
    while i < len(toks):
        hit = None
        for n in range(min(longest, len(toks) - i), 0, -1):
            run = toks[i:i + n]
            cores = [_split(t)[1] for t in run]
            if any(not c for c in cores):
                continue
            # punctuation is allowed only at the two ends of the run, so a comma inside a phrase breaks the match
            if any(_split(t)[2] for t in run[:-1]) or any(_split(t)[0] for t in run[1:]):
                continue
            key = tuple(c.lower() for c in cores)
            if key in rules:
                hit = (n, rules[key], _split(run[0])[0], _split(run[-1])[2])
                break
        if hit:
            n, said, lead, trail = hit
            out.append(Unit(list(toks[i:i + n]), _clean_spoken(lead + said.strip() + trail).strip()))
            i += n
        else:
            out.append(toks[i])
            i += 1
    return out


def speak_units(text: str, table: dict[str, str] | None = None) -> list[Unit]:
    """The narration text as units (see the module doc). Whitespace splits the written tokens."""
    toks = str(text or "").split()
    items = _apply_table(toks, table)
    units: list[Unit] = []
    prev_core = ""
    i = 0
    while i < len(items):
        it = items[i]
        if isinstance(it, Unit):
            units.append(it)
            prev_core = _split(it.written[-1])[1]
            i += 1
            continue
        plain: list[str] = []
        j = i
        while j < len(items) and not isinstance(items[j], Unit):    # a run of plain tokens, converted with look-ahead
            plain.append(items[j])           # type: ignore[arg-type]
            j += 1
        k = 0
        while k < len(plain):
            tok = plain[k]
            lead, core, trail = _split(tok)
            if core in DASHES and not lead:
                # a stand-alone dash is a pause: it joins the previous unit as a comma
                if units:
                    p = units[-1]
                    p.written.append(tok)
                    if p.spoken and p.spoken[-1] not in ",.;:!?":
                        p.spoken += ","
                else:
                    units.append(Unit([tok], ""))
                k += 1
                continue
            used, said = _convert(plain, k, prev_core)
            last_tok = plain[k + used - 1]
            end_trail = _split(last_tok)[2]
            spoken = lead + said + end_trail
            if used == 1 and said == core and not (lead or end_trail):
                spoken = tok
            low = core.lower()
            if said != core and low in ABBR and end_trail.startswith(".") and low not in KEEP_PERIOD:
                spoken = lead + said + end_trail[1:]
            elif low in KEEP_PERIOD and said != core and end_trail.startswith("."):
                nxt = plain[k + used] if k + used < len(plain) else ""
                if nxt and not re.match(r"^[\"“(\[]?[A-Z0-9]", nxt):
                    spoken = lead + said + end_trail[1:]
            if low in ("c", "ca") and said == "circa":
                spoken = lead + said + end_trail[1:]
            if low == "no" and said == "number":
                spoken = lead + said + end_trail[1:]
            if low == "al" and said == "alia":
                spoken = lead + said + end_trail
            units.append(Unit(list(plain[k:k + used]), _clean_spoken(spoken).strip()))
            prev_core = _split(last_tok)[1]
            k += used
        i = j
    return units


def speak(text: str, table: dict[str, str] | None = None) -> str:
    return " ".join(u.spoken for u in speak_units(text, table) if u.spoken).strip()
