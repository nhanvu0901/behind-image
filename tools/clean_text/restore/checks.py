"""The checks by code on a model answer for one work. Nothing is written unless every check passes.

`check_answer(originals, answer, prompt_lines)` -> Check. `originals` maps "page_NNNN" to the text of each BODY page of the
work, in order. Failures reject the answer (it is retried once with the failures listed); warnings are only reported."""
from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field

from .pages import PARA, Item, TAGS, is_structural, parse_page, prose_count, render

PAGE_RATIO = (0.6, 1.5)             # length of a restored page / length of the original page
SHORT_PAGE_CHARS = 300              # below this a page is mostly structure and a few words move the ratio a lot
SHORT_PAGE_RATIO = (0.5, 2.0)
PARA_MIN_CHARS = 200                # paragraph-level check applies to original paragraphs at least this long
PARA_RATIO = (0.4, 2.0)
STRUCT_SIMILARITY = 0.75            # a structural line may change only by a name correction
LEAK_MIN_CHARS = 25
MARKER_RE = re.compile(r"^\s*={3}\s*(page_\d{4}|names|readings)\s*={3}\s*$", re.I)
UNCLEAR_RE = re.compile(r"\[\[\?(.*?)\?\]\]", re.S)
NAME_LINE_RE = re.compile(r"^\s*(?:[-*]\s+)?(.+?)\s*=>\s*(.+?)\s*$")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
CAP_RE = re.compile(r"\b[A-Z][A-Za-zÀ-ɏ'’-]{2,}")
MAX_FAILURES_SHOWN = 15
MAX_READINGS = 12                   # more declared readings than this in one work: a warning
MAX_READINGS_SHARE = 0.08           # readings covering more than this share of the input characters: a warning


@dataclass
class Check:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages: dict[str, str] = field(default_factory=dict)          # restored text per page (only when ok)
    names: list[tuple[str, str]] = field(default_factory=list)
    unclear: dict[str, int] = field(default_factory=dict)        # `[[? ?]]` passages per page
    unclear_chars: int = 0
    page_ratios: dict[str, float] = field(default_factory=dict)
    ratio: float = 0.0
    new_names: list[str] = field(default_factory=list)
    readings: list[tuple[str, str]] = field(default_factory=list)   # declared changes of meaning: (literal form, what was written)
    readings_dropped: list[dict] = field(default_factory=list)      # readings lines left out of the list: {"line", "why"}
    names_dropped: list[dict] = field(default_factory=list)         # names lines left out of the list: {"line", "why"}

    @property
    def ok(self) -> bool:
        return not self.failures


def norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def prompt_lines_of(template_text: str) -> set[str]:
    """The lines of the prompt template that the model must never echo (placeholders removed, short lines dropped)."""
    text = re.sub(r"\{\{[A-Z_]+\}\}", "", template_text)
    return {n for n in (norm_line(l) for l in text.split("\n")) if len(n) >= LEAK_MIN_CHARS}


def split_answer(answer: str, expected: list[str]):
    """-> (pages by id, page order as returned, name lines, reading lines or None when there is no readings block, failures, warnings)."""
    failures: list[str] = []
    warnings: list[str] = []
    lines = answer.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # one code fence wrapped around the whole answer is dropped
    nz = [i for i, l in enumerate(lines) if l.strip()]
    if len(nz) >= 2 and lines[nz[0]].strip().startswith("```") and lines[nz[-1]].strip() == "```":
        lines = lines[nz[0] + 1:nz[-1]]
    pages: dict[str, list[str]] = {}
    order: list[str] = []
    names: list[str] = []
    readings: list[str] | None = None
    block: str | None = None             # "names" or "readings" while inside one of the closing blocks
    cur: list[str] | None = None
    seen_names = False
    pre = 0
    dup: list[str] = []
    after_names_pages = False
    for l in lines:
        m = MARKER_RE.match(l)
        if m:
            tag = m.group(1).lower()
            if tag in ("names", "readings"):
                block, cur = tag, None
                if tag == "names":
                    seen_names = True
                elif readings is None:
                    readings = []
                continue
            if block:
                after_names_pages = True
            block = None
            order.append(tag)
            if tag in pages:
                dup.append(tag)
                cur = []                       # the second copy is discarded
            else:
                pages[tag] = []
                cur = pages[tag]
            continue
        if block == "names":
            names.append(l)
        elif block == "readings":
            readings.append(l)
        elif cur is not None:
            cur.append(l)
        elif l.strip():
            pre += 1
    if pre:
        warnings.append(f"{pre} line(s) before the first page marker were ignored")
    for tag in sorted(set(dup)):
        failures.append(f"{tag} was returned {order.count(tag)} times; each page must come back once")
    if after_names_pages:
        failures.append("page text follows the `=== names ===` / `=== readings ===` block; those blocks must come after the last page")
    if not seen_names:
        failures.append("the `=== names ===` block is missing after the last page (write it even when no name was corrected)")
    missing = [p for p in expected if p not in pages]
    if missing:
        failures.append("missing page(s): " + ", ".join(missing))
    extra = [p for p in dict.fromkeys(order) if p not in expected]
    if extra:
        failures.append("page(s) that were not part of the input: " + ", ".join(extra))
    uniq = list(dict.fromkeys(order))
    if not missing and not extra and not dup and uniq != expected:
        failures.append("pages are out of order; expected " + ", ".join(expected))
    return pages, uniq, names, readings, failures, warnings


def _digits(s: str) -> list[str]:
    return re.findall(r"\d+", s)


def _first_words(s: str, n: int = 60) -> str:
    s = s.strip()
    return s[:n] + ("..." if len(s) > n else "")


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", s.lower()))


def _probably_missing(oi: list[Item], ni: list[Item]) -> list[str]:
    """Original paragraphs that share almost no words with any returned paragraph (a hint for the retry message)."""
    new_sets = [_words(i.text) for i in ni if i.kind == PARA]
    gone = []
    for o in oi:
        if o.kind != PARA:
            continue
        ow = _words(o.text)
        if not ow:
            continue
        best = max((len(ow & w) / len(ow | w) for w in new_sets if w), default=0.0)
        if best < 0.15:
            gone.append(o.text)
    return gone


def compare_page(pid: str, orig_text: str, new_lines: list[str]) -> tuple[list[str], list[str], str | None, int, int, float]:
    """-> (failures, warnings, restored text or None, unclear count, unclear chars, length ratio)."""
    fails: list[str] = []
    warns: list[str] = []
    oi = parse_page(orig_text)
    ni = parse_page("\n".join(new_lines))
    ok_kinds = [i.kind for i in oi]
    nk = [i.kind for i in ni]
    unknown = [k for k in nk if k.startswith("unknown:")]
    if unknown:
        fails.append(f"{pid}: line(s) that look like structure but are not one of the allowed tags ({', '.join(sorted(set(unknown)))}); "
                     "do not invent tags or markdown headings")
    if nk != ok_kinds:
        po, pn = prose_count(oi), prose_count(ni)
        if po != pn:
            fails.append(f"{pid}: {pn} paragraphs returned, the original has {po}; keep every paragraph, each on one line, "
                         "with a blank line between paragraphs")
        so, sn = [k for k in ok_kinds if k != PARA], [k for k in nk if k != PARA]
        if so != sn:
            fails.append(f"{pid}: the structural lines differ (original: {', '.join(so) or 'none'}; returned: {', '.join(sn) or 'none'})")
        for idx, (a, b) in enumerate(zip(ok_kinds, nk)):
            if a != b:
                want = "a paragraph" if a == PARA else f"[{a}]"
                start = f' starting "{_first_words(oi[idx].text, 50)}"' if oi[idx].text else ""
                got = "a paragraph" if b == PARA else f"[{b}]"
                fails.append(f"{pid}: first difference at line {idx + 1}: expected {want}{start}, got {got}")
                break
        if po != pn:
            gone = _probably_missing(oi, ni)
            if gone:
                fails.append(f"{pid}: probably missing: " + "; ".join(f'"{_first_words(g, 50)}"' for g in gone[:3]))
        return fails, warns, None, 0, 0, 0.0
    new_lines_out: list[str] = []
    unclear = 0
    unclear_chars = 0
    for idx, (o, n) in enumerate(zip(oi, ni)):
        line = n.line.strip()
        if o.kind == "page-type":
            if n.text != o.text:
                fails.append(f"{pid}: the [page-type] line changed ({o.text!r} -> {n.text!r}); it must stay as it was")
            line = o.line.strip()
        elif is_structural(o.kind):
            if _digits(o.text) != _digits(n.text):
                fails.append(f"{pid}: numbers changed in a structural line [{o.kind}]: \"{_first_words(o.text, 70)}\" -> \"{_first_words(n.text, 70)}\"")
            sim = difflib.SequenceMatcher(None, o.text, n.text).ratio() if (o.text or n.text) else 1.0
            if sim < STRUCT_SIMILARITY:
                fails.append(f"{pid}: a structural line [{o.kind}] was rewritten (similarity {sim:.2f}); only a name inside may change: "
                             f"\"{_first_words(o.text, 70)}\" -> \"{_first_words(n.text, 70)}\"")
        else:
            lo, ln = len(o.text), len(n.text)
            if lo >= PARA_MIN_CHARS:
                r = ln / lo
                if r < PARA_RATIO[0] or r > PARA_RATIO[1]:
                    fails.append(f"{pid}: paragraph {idx + 1} (\"{_first_words(o.text, 50)}\") came back at {r:.2f} of its original length "
                                 f"({'too short: something was dropped' if r < 1 else 'too long: something was added'})")
            elif lo and ln == 0:
                fails.append(f"{pid}: an empty paragraph came back for \"{_first_words(o.text, 50)}\"")
        c = len(UNCLEAR_RE.findall(line))
        rest = UNCLEAR_RE.sub("", line)
        if "[[?" in rest or "?]]" in rest:
            fails.append(f"{pid}: an unbalanced `[[?` / `?]]` marker in \"{_first_words(line, 70)}\"")
        unclear += c
        unclear_chars += sum(len(x) for x in UNCLEAR_RE.findall(line))
        new_lines_out.append(line)
    lo_tot, ln_tot = len(orig_text.strip()), len("\n".join(new_lines).strip())
    ratio = ln_tot / lo_tot if lo_tot else 1.0
    lo_r, hi_r = SHORT_PAGE_RATIO if lo_tot < SHORT_PAGE_CHARS else PAGE_RATIO
    if ratio < lo_r or ratio > hi_r:
        fails.append(f"{pid}: the page came back at {ratio:.2f} of its original length; it must stay between {lo_r} and {hi_r} "
                     f"({'something was dropped' if ratio < 1 else 'something was added'})")
    restored = render(new_lines_out, [i.blank_before for i in oi])
    return fails, warns, restored, unclear, unclear_chars, ratio


def _prose_numbers(texts: list[str]) -> Counter:
    c: Counter = Counter()
    for t in texts:
        for i in parse_page(t):
            if i.kind == PARA:
                for m in NUM_RE.findall(i.text):
                    tok = m.replace(",", "")
                    if len(tok.replace(".", "")) >= 2:
                        c[tok] += 1
    return c


def _capitalised(text: str) -> set[str]:
    """Capitalised words that are not the first word of a sentence, from the prose lines."""
    out: set[str] = set()
    for i in parse_page(text):
        if i.kind != PARA:
            continue
        for sent in re.split(r"(?<=[.!?])\s+|:\s+|“|\"", i.text):
            words = sent.split()
            for w in words[1:]:
                m = CAP_RE.match(w.strip("([“\"'‘"))
                if m:
                    out.add(m.group(0).strip("'’-"))
    return out


def check_answer(originals: dict[str, str], answer: str, prompt_lines: set[str] | None = None,
                 all_input_text: str | None = None) -> Check:
    res = Check()
    expected = list(originals)
    pages, order, name_lines, reading_lines, fails, warns = split_answer(answer, expected)
    res.failures += fails
    res.warnings += warns
    restored: dict[str, str] = {}
    for pid in expected:
        if pid not in pages:
            continue
        f, w, text, uc, ucc, ratio = compare_page(pid, originals[pid], pages[pid])
        res.failures += f
        res.warnings += w
        res.page_ratios[pid] = round(ratio, 3)
        res.unclear[pid] = uc
        res.unclear_chars += ucc
        if text is not None:
            restored[pid] = text
    tot_o = sum(len(t.strip()) for t in originals.values())
    tot_n = sum(len(t.strip()) for t in restored.values()) if len(restored) == len(expected) else 0
    res.ratio = round(tot_n / tot_o, 3) if tot_o and tot_n else 0.0
    # nothing of the prompt may come back
    if prompt_lines:
        leaked = []
        in_lines = {norm_line(l) for l in (all_input_text if all_input_text is not None else "\n".join(originals.values())).split("\n")}
        for pid in pages:
            for l in pages[pid]:
                nl = norm_line(l)
                if nl in in_lines:
                    continue                       # a line the input itself has is not a leak
                if len(nl) >= LEAK_MIN_CHARS and (nl in prompt_lines or any(p in nl for p in prompt_lines)):
                    leaked.append(f"{pid}: \"{_first_words(l, 70)}\"")
        for l in name_lines:
            nl = norm_line(l)
            if len(nl) >= LEAK_MIN_CHARS and (nl in prompt_lines or any(p in nl for p in prompt_lines)):
                leaked.append(f"names block: \"{_first_words(l, 70)}\"")
        for l in reading_lines or []:
            nl = norm_line(l)
            if len(nl) >= LEAK_MIN_CHARS and (nl in prompt_lines or any(p in nl for p in prompt_lines)):
                leaked.append(f"readings block: \"{_first_words(l, 70)}\"")
        if leaked:
            res.failures.append("lines of the instructions came back in the answer: " + "; ".join(leaked[:4]))
    # names block
    src = all_input_text if all_input_text is not None else "\n".join(originals.values())
    out_text = "\n".join(restored.values())
    seen = set()
    src_t = _tol(src)
    for l in name_lines:
        if not l.strip() or norm_line(l) in ("(none)", "none", "-", "(nothing)"):
            continue
        m = NAME_LINE_RE.match(l)
        if not m:
            _drop(res.names_dropped, res.warnings, "names", l, "not of the form `old => new`")
            continue
        old, new = m.group(1).strip(" `\"'"), m.group(2).strip(" `\"'")
        if not old or not new or _tol_form(old) == _tol_form(new) or len(old) > 80 or len(new) > 80:
            _drop(res.names_dropped, res.warnings, "names", l, "empty, too long, or old and new are the same")
        elif not _found(old, src_t):
            _drop(res.names_dropped, res.warnings, "names", l, "the old form is not in the input")
        elif (old, new) not in seen:
            seen.add((old, new))
            res.names.append((old, new))
    for old, new in res.names:
        left = len(re.findall(r"(?<!\w)" + re.escape(old) + r"(?!\w)", out_text))
        if left and out_text:
            res.warnings.append(f"name \"{old}\" is listed as corrected but still occurs {left} time(s) in the restored text")
    _check_readings(res, reading_lines, src, out_text, restored, expected)
    _check_quotes(res, src, out_text)
    # numbers and names that the text did not have
    in_nums = _prose_numbers(list(originals.values()))
    out_nums = _prose_numbers(list(restored.values())) if len(restored) == len(expected) else in_nums
    added = out_nums - in_nums
    dropped = in_nums - out_nums
    if added:
        res.failures.append("numbers that are not in the original were added: " + ", ".join(sorted(added)[:12])
                            + "; keep every number exactly as written and add none")
    if dropped:
        res.warnings.append("numbers of the original are missing from the result: " + ", ".join(sorted(dropped)[:12]))
    if restored and len(restored) == len(expected):
        in_caps = _capitalised(src)
        known = {w for _, new in res.names for w in re.findall(r"[A-Za-zÀ-ɏ'’-]+", new)}
        known |= {w for _, new in res.readings for w in re.findall(r"[A-Za-z\u00c0-\u024f'\u2019-]+", new)}
        known |= {w for w in in_caps}
        new_caps = sorted(w for w in _capitalised(out_text) if w not in known and w.rstrip("s") not in known)
        res.new_names = new_caps[:40]
        if new_caps:
            res.warnings.append("capitalised words in the result that are neither in the input nor in the names block: "
                                + ", ".join(new_caps[:12]))
    if not res.failures:
        res.pages = restored
    return res


_CHAR_MAP = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"})
_ELLIPSIS = re.compile(r"\s*(?:\.{3,}|\u2026|(?:\.\s){2,}\.)\s*")


def _tol(s: str) -> str:
    """Tolerant form for matching: curly -> straight quotes and apostrophes, dashes alike, runs of whitespace, case."""
    return re.sub(r"\s+", " ", s.translate(_CHAR_MAP)).strip().lower()


def _tol_form(s: str) -> str:
    """A declared form made tolerant: also without surrounding quotation marks or backticks and without final punctuation."""
    s = _tol(s).strip(" `\"'")
    s = s.rstrip(".,;:!?\u2026 ").strip(" `\"'")
    return s


def _found(form: str, text_t: str) -> bool:
    """Is the declared form in the (already tolerant) text? An ellipsis in the middle of a long form splits it into a part
    before and a part after, which must both be found, in that order."""
    parts = [p.strip(" `\"'") for p in _ELLIPSIS.split(_tol_form(form)) if p.strip(" `\"'")]
    pos = 0
    for part in parts:
        i = text_t.find(part, pos)
        if i < 0:
            return False
        pos = i + len(part)
    return bool(parts)


def _drop(into: list, warnings: list, what: str, line: str, why: str) -> None:
    into.append({"line": line.strip()[:300], "why": why})
    warnings.append(f"{what} line dropped ({why}): \"{_first_words(line, 100)}\"")


def _check_readings(res: Check, lines: list[str] | None, src: str, out_text: str, restored: dict, expected: list[str]) -> None:
    """The optional `=== readings ===` block: each line `literal form in the input => what you wrote`. It is an audit list, never
    a condition: a line that cannot be used is left out and recorded in `readings_dropped`, it never rejects a work."""
    if lines is None:
        return
    src_t, out_t = _tol(src), _tol(out_text)
    complete = len(restored) == len(expected)
    seen: set[tuple[str, str]] = set()
    for l in lines:
        if not l.strip() or norm_line(l) in ("(none)", "none", "-", "(nothing)"):
            continue
        m = NAME_LINE_RE.match(l)
        if not m:
            _drop(res.readings_dropped, res.warnings, "readings", l, "not of the form `old => new`")
            continue
        old, new = m.group(1).strip(" `"), m.group(2).strip(" `")
        if not _tol_form(old) or not _tol_form(new):
            _drop(res.readings_dropped, res.warnings, "readings", l, "empty side")
        elif _tol_form(old) == _tol_form(new):
            _drop(res.readings_dropped, res.warnings, "readings", l, "old and new are the same")
        elif not _found(old, src_t):
            _drop(res.readings_dropped, res.warnings, "readings", l, "the old form is not in the input")
        elif complete and not _found(new, out_t):
            _drop(res.readings_dropped, res.warnings, "readings", l, "the new form is not in the output")
        elif (old, new) not in seen:
            seen.add((old, new))
            res.readings.append((old, new))
    if len(res.readings) > MAX_READINGS:
        res.warnings.append(f"{len(res.readings)} readings in one work (more than {MAX_READINGS}): the model is rewriting, not restoring")
    chars = sum(len(o) for o, _ in res.readings)
    total = len(src)
    if total and chars / total > MAX_READINGS_SHARE:
        res.warnings.append(f"the readings cover {100 * chars / total:.1f} percent of the input (more than {int(MAX_READINGS_SHARE * 100)}): "
                            "the model is rewriting, not restoring")


def _check_quotes(res: Check, src: str, out_text: str) -> None:
    if '"' not in src and ("\u201c" in src or "\u201d" in src) and '"' in out_text:
        res.warnings.append(f"straight double quotes in the result ({out_text.count(chr(34))}) where the input has only curly ones")


def failures_text(failures: list[str]) -> str:
    shown = failures[:MAX_FAILURES_SHOWN]
    s = "\n".join(f"- {f[:400]}" for f in shown)
    if len(failures) > len(shown):
        s += f"\n- ... and {len(failures) - len(shown)} more"
    return s
