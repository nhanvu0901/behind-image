"""Tolerant parsers for the text a model (or the owner) pastes: `parse_script` and `parse_outline`.

Same spirit as the comic pipeline's script importer: take the text after the LAST marker line, drop fences,
hook lists, audit tables, word counts and commentary, and when the text cannot be placed refuse WITHOUT writing
anything, listing every paragraph with its word count and first 70 characters so the owner sees what the parser saw.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .stats import count_words
from .. import textfold
from .store import CERTAINTY, Beat, Fact, Hook, NChapter, Narration, OChapter, Outline, now_iso

FINAL_RE = re.compile(r"^[\W_]*FINAL\s+SCRIPT[\W_]*$", re.I | re.M)
OUTLINE_RE = re.compile(r"^[\W_]*OUTLINE[\W_]*$", re.I | re.M)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
RULE_RE = re.compile(r"^\s*([-*_=])(\s*\1){2,}\s*$")
HEAD_RE = re.compile(r"^\s*#{2,3}\s+(.*?)\s*#*\s*$")
CH_ID_RE = re.compile(r"^\[?\s*(c\d+)\s*\]?\b[\s:.\-–—]*(.*)$", re.I)
PARA_ID_RE = re.compile(r"\b[A-Z]{3}-\d{2,3}\b")
FACT_ID_RE = re.compile(r"\bf\d+\b", re.I)

# a block that starts with one of these labels is commentary; the "tail" labels end the script
_LABELS = (r"hook options?|hooks?|chosen hook|hook choice|spoken word count|word count|total words?|fact trace|"
           r"audit|sources?|notes?|unsupported facts|opening chain|flow check|issue mention check|length check|"
           r"budget check|word budget|self[- ]check|checks?|summary|commentary|reading level")
LABEL_RE = re.compile(rf"^\W*({_LABELS})\s*(:|$)", re.I)
TAIL_LABELS = re.compile(r"^\W*(spoken word count|word count|total words?|fact trace|audit|sources?|notes?|unsupported facts|"
                         r"opening chain|flow check|issue mention check|length check|budget check|self[- ]check|checks?)\s*(:|$)", re.I)
WORDCOUNT_LINE = re.compile(r"^\W*(?:chapter |total |spoken )?(?:word count|words?)\s*[:=]?\s*~?\d+.*$|^\W*[\(\[]\s*~?\d+\s+words?\s*[\)\]]\W*$", re.I)
LIST_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*•]|h\d+\s*:)\s+")


@dataclass
class ParseResult:
    ok: bool
    narration: Narration | None = None
    outline: Outline | None = None
    issues: list[dict] = field(default_factory=list)
    error: str | None = None
    paragraphs: list[dict] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    chapter_ids: list[str] = field(default_factory=list)

    def add(self, level: str, code: str, message: str, **where) -> None:
        self.issues.append({"level": level, "code": code, "message": message, **where})

    def public(self) -> dict:
        return {"ok": self.ok, "error": self.error, "issues": self.issues, "paragraphs": self.paragraphs,
                "dropped": self.dropped}


def _clean_inline(s: str) -> str:
    s = s.replace(" ", " ")
    s = re.sub(r"\*\*|__|`", "", s)
    s = re.sub(r"(?<![\w*])\*(\S[^*]*?)\*(?![\w*])", r"\1", s)
    return s.strip()


def _norm(s: str) -> str:
    return textfold.norm(s)


def paragraph_listing(text: str) -> list[dict]:
    """Every paragraph (blank-line separated; chapter lines do not count): number, words, first 70 chars,
    and `heading`, the chapter line it sits under (None before the first one)."""
    out, heading = [], None
    for blk in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        buf: list[str] = []

        def flush():
            t = " ".join(buf).strip()
            if t:
                out.append({"n": len(out) + 1, "words": count_words(t), "start": t[:70] + ("…" if len(t) > 70 else ""),
                            "heading": heading})
            buf.clear()

        for ln in blk.split("\n"):
            if HEAD_RE.match(ln) and not ln.lstrip().startswith("####"):
                flush()
                heading = _clean_inline(HEAD_RE.match(ln).group(1))
            elif ln.strip().startswith(">>"):
                continue                                     # a metadata line, not part of the paragraph
            elif ln.strip():
                buf.append(ln.strip())
        flush()
    return out


def _fail(res: ParseResult, reason: str, text: str, what: str) -> ParseResult:
    res.ok = False
    res.paragraphs = paragraph_listing(text)
    lines = [f'{what} {reason}', f"Found {len(res.paragraphs)} paragraph(s):"]
    cur = object()
    for p in res.paragraphs[:60]:
        if p["heading"] != cur:
            cur = p["heading"]
            lines.append(f"  ## {cur}" if cur else "  (before any chapter line)")
        lines.append(f'  [{p["n"]}] {p["words"]} words: "{p["start"]}"')
    if len(res.paragraphs) > 60:
        lines.append(f"  ... and {len(res.paragraphs) - 60} more")
    lines.append("Fix the text (or ask for a new answer with the current prompt) and paste it again. Nothing was saved.")
    res.error = "\n".join(lines)
    return res


def _after_marker(text: str, marker: re.Pattern) -> str:
    ms = list(marker.finditer(text))
    return text[ms[-1].end():] if ms else text


# ===================================================================== script
def _parse_meta(line: str, known_facts: set[str] | None) -> dict:
    body = re.sub(r"^\s*>>\s*", "", line)
    out = {"facts": [], "show": [], "note": ""}
    for part in re.split(r"\s\|\s|\|", body):
        k, _, v = part.partition(":")
        k = k.strip().lower()
        v = v.strip()
        if k in ("facts", "fact"):
            out["facts"] = [] if v.lower() in ("", "none", "-", "n/a") else [m.lower() for m in FACT_ID_RE.findall(v)]
        elif k in ("show", "shows", "on screen", "screen"):
            out["show"] = [] if v.lower() in ("", "none", "-") else [x.strip() for x in v.split(";") if x.strip()]
        elif k in ("note", "notes"):
            out["note"] = v
    return out


def _scan_script(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """-> items [("heading", raw) | ("para", text) | ("meta", line)], dropped lines/blocks (short descriptions)."""
    items: list[tuple[str, str]] = []
    dropped: list[str] = []
    para: list[str] = []
    in_comment = False
    in_list = False

    def flush():
        nonlocal para
        if para:
            blk = " ".join(para).strip()
            if blk:
                items.append(("para", blk))
        para = []

    lines = text.replace("\r\n", "\n").split("\n")
    for raw in lines:
        if FENCE_RE.match(raw):
            flush()
            continue
        line = raw.rstrip()
        if not line.strip():
            flush()
            in_comment = in_list = False
            continue
        if in_comment:
            dropped.append(line.strip()[:70])
            continue
        if RULE_RE.match(line):
            flush()
            continue
        if line.lstrip().startswith("|") and line.count("|") >= 2:     # audit table row
            flush()
            dropped.append(line.strip()[:70])
            continue
        if HEAD_RE.match(line) and not line.lstrip().startswith("####"):
            flush()
            items.append(("heading", _clean_inline(HEAD_RE.match(line).group(1))))
            continue
        if re.match(r"^\s*>>", line):
            flush()
            items.append(("meta", line.strip()))
            continue
        clean = _clean_inline(line)
        if LABEL_RE.match(clean) and not para:
            flush()
            dropped.append(clean[:70])
            if TAIL_LABELS.match(clean) and any(i[0] == "para" for i in items):
                items.append(("tail", clean))
                break
            in_comment = True
            continue
        if WORDCOUNT_LINE.match(clean):
            flush()
            dropped.append(clean[:70])
            continue
        if LIST_ITEM.match(clean) and not para:
            # a bullet or numbered list is never a narration paragraph (hook lists, audit lists)
            flush()
            in_list = True
            dropped.append(clean[:70])
            continue
        if in_list:
            dropped.append(clean[:70])
            continue
        para.append(clean)
    flush()
    items = [i for i in items if i[0] != "tail"]
    return items, dropped


def parse_script(text: str, outline: Outline | None = None, *, project: str = "", title: str = "",
                 counter_start: int = 0) -> ParseResult:
    """Text -> Narration. `counter_start`: highest beat number already used (ids continue from it)."""
    res = ParseResult(False)
    if not text or not text.strip():
        return _fail(res, "The text is empty.", "", "The script could not be read.")
    body = _after_marker(text, FINAL_RE)
    items, dropped = _scan_script(body)
    res.dropped = dropped
    known = outline.fact_ids() if outline else None
    heads = [i for i in items if i[0] == "heading"]

    # placing chapters
    ochs = list(outline.chapters) if outline else []
    placed: dict[str, dict] = {}                      # outline chapter id -> {"title","beats":[...]}
    order: list[str] = []
    cur: dict | None = None
    unmatched: list[str] = []
    pre_dropped = 0
    used_pos = 0
    by_pos = bool(ochs) and len(heads) == len(ochs)

    def place(raw: str) -> dict | None:
        nonlocal used_pos
        m = CH_ID_RE.match(raw)
        cid = m.group(1).lower() if m else None
        ttl = (m.group(2) if m else raw).strip().strip("[]").strip(" -–—:.")
        oc = None
        if ochs:
            if cid:
                oc = next((c for c in ochs if c.id.lower() == cid), None)
            if oc is None and ttl:
                oc = next((c for c in ochs if _norm(c.title) == _norm(ttl) and _norm(ttl)), None)
            if oc is None and by_pos and not cid and used_pos < len(ochs):
                oc = ochs[used_pos]
                res.add("warning", "chapter_by_position", f'chapter heading "{raw}" was matched to {oc.id} by its position',
                        chapter=oc.id)
            used_pos += 1
            if oc is None:
                unmatched.append(raw)
                return None
            key = oc.id
            title_, role, card = oc.title, oc.role, oc.card
        else:
            key = cid or f"c{len(order) + 1:02d}"
            title_ = ttl or key.upper()
            role = "cold_open" if "cold open" in _norm(title_) else "closing" if _norm(title_) in ("closing", "close", "outro") else "chapter"
            card = False
        if key in placed:
            res.add("warning", "chapter_twice", f"chapter {key} appears twice in the text; its paragraphs were joined", chapter=key)
            return placed[key]
        placed[key] = {"id": key, "title": title_, "role": role, "card": card, "beats": []}
        order.append(key)
        return placed[key]

    pending_unmatched = False
    for kind, val in items:
        if kind == "heading":
            cur = place(val)
            pending_unmatched = cur is None
        elif kind == "para":
            if cur is not None:
                cur["beats"].append({"text": val, "facts": [], "show": [], "note": ""})
            elif not heads:
                continue                                  # handled below
            elif pending_unmatched:
                pass                                       # paragraphs of an unplaceable chapter
            else:
                pre_dropped += 1
        elif kind == "meta":
            if cur is None or not cur["beats"]:
                res.add("warning", "meta_orphan", f'a ">>" line has no paragraph before it: "{val[:60]}"')
                continue
            m = _parse_meta(val, known)
            b = cur["beats"][-1]
            b["facts"], b["show"] = m["facts"] or b["facts"], m["show"] or b["show"]
            b["note"] = m["note"] or b["note"]

    if not heads:
        paras = [v for k, v in items if k == "para"]
        if not paras:
            return _fail(res, "No narration paragraphs were found.", body, "The script could not be placed.")
        if len(ochs) > 1:
            return _fail(res, f"The text has no chapter lines (## c01 TITLE) and the outline has {len(ochs)} chapters.",
                         body, "The script could not be placed.")
        key = ochs[0].id if ochs else "c01"
        ch = {"id": key, "title": ochs[0].title if ochs else "SCRIPT", "role": ochs[0].role if ochs else "chapter",
              "card": bool(ochs and ochs[0].card), "beats": []}
        for kind, val in items:
            if kind == "para":
                ch["beats"].append({"text": val, "facts": [], "show": [], "note": ""})
            elif kind == "meta" and ch["beats"]:
                m = _parse_meta(val, known)
                ch["beats"][-1].update({k: m[k] for k in ("facts", "show", "note") if m[k]})
        placed[key] = ch
        order = [key]
        res.add("warning", "no_chapter_lines", "the text has no chapter lines; all paragraphs were put in " + key)

    if unmatched:
        known_list = ", ".join(f"{c.id} {c.title}" for c in ochs)
        return _fail(res, "Chapter line(s) that match no chapter of the outline (by id or by title): "
                     + "; ".join(f'"{u}"' for u in unmatched) + f". The outline has: {known_list}.", body, "The script could not be placed.")
    if pre_dropped:
        res.add("info", "preamble_dropped", f"{pre_dropped} paragraph(s) before the first chapter line were dropped as commentary")
    order_ids = [c.id for c in ochs if c.id in placed] + [k for k in order if k not in {c.id for c in ochs}]
    chapters: list[NChapter] = []
    n = Narration(project=project, title=title, language="en", counters={"beat": counter_start},
                  source={"kind": "paste", "model": "", "created_at": now_iso()})
    for key in order_ids:
        ch = placed[key]
        beats = []
        for raw in ch["beats"]:
            beats.append(Beat(n.new_beat_id(), raw["text"], raw["facts"], raw["show"], False, raw["note"]))
            for f in raw["facts"]:
                if known is not None and f not in known:
                    res.add("warning", "unknown_fact", f"fact id {f} is not in the outline", chapter=key, beat=beats[-1].id)
        chapters.append(NChapter(key, ch["role"], ch["title"], ch["card"], beats))
    n.chapters = chapters
    if not any(c.beats for c in chapters):
        return _fail(res, "The chapter lines were found but no narration paragraphs follow them.", body, "The script could not be placed.")
    for c in chapters:
        if not c.beats:
            res.add("warning", "chapter_empty", f"chapter {c.id} has no paragraphs", chapter=c.id)
    res.ok, res.narration, res.chapter_ids = True, n, order_ids
    return res


# ===================================================================== outline
_KEYS = {"role": "role", "card": "card", "budget": "budget", "word budget": "budget", "words": "budget",
         "purpose": "purpose", "facts": "facts", "show": "show"}


def _yes(v: str) -> bool:
    return v.strip().lower() in ("yes", "y", "true", "1", "có", "co")


def _parse_fact_line(line: str, fallback_id: str, res: ParseResult, known_paras: set[str] | None) -> Fact | None:
    line = re.sub(r"^\s*[-*•]\s*", "", line)
    conflict = None
    m = re.search(r"\|\s*conflicts?\s*:\s*(.+)$", line, re.I)
    if m:
        conflict, line = m.group(1).strip(), line[: m.start()]
    fields = [f.strip() for f in line.split("|")]
    if len(fields) < 2:
        return None
    fid = fallback_id
    if FACT_ID_RE.fullmatch(fields[0]):
        fid = fields.pop(0).lower()
    cert, sources, rest = None, [], []
    for f in fields:
        if f.lower() in CERTAINTY and cert is None:
            cert = f.lower()
        elif PARA_ID_RE.search(f) and len(PARA_ID_RE.sub("", f).strip(" ,;/&and")) < 4:
            sources += PARA_ID_RE.findall(f)
        else:
            rest.append(f)
    claim = " | ".join(rest).strip()
    if not claim:
        return None
    if conflict and conflict.lower() in ("none", "null", "-", "no"):
        conflict = None
    if known_paras is not None:
        for s in sources:
            if s not in known_paras:
                res.add("warning", "unknown_source_id", f"fact {fid} cites {s}, which is not a paragraph of the brief", fact=fid)
    if not sources:
        res.add("warning", "fact_no_source", f"fact {fid} cites no source paragraph", fact=fid)
    return Fact(fid, claim, sources, cert or "likely", conflict)


def parse_outline(text: str, known_paragraph_ids: set[str] | list[str] | None = None, *, target_words: int = 2000) -> ParseResult:
    res = ParseResult(False)
    if not text or not text.strip():
        return _fail(res, "The text is empty.", "", "The outline could not be read.")
    known = set(known_paragraph_ids) if known_paragraph_ids else None
    body = _after_marker(text, OUTLINE_RE)
    thesis, hooks, hook_choice, facts, chapters, target = "", [], None, [], [], None
    section, cur, last_key = None, None, None
    fact_n = 0

    for raw in body.replace("\r\n", "\n").split("\n"):
        if FENCE_RE.match(raw) or RULE_RE.match(raw) or not raw.strip():
            last_key = None if not raw.strip() else last_key
            continue
        line = _clean_inline(raw)
        low = line.lower()
        hm = HEAD_RE.match(raw)
        if hm and not raw.lstrip().startswith("####"):
            cm = CH_ID_RE.match(_clean_inline(hm.group(1)))
            ttl = _clean_inline(hm.group(1))
            cid = cm.group(1).lower() if cm else f"c{len(chapters) + 1:02d}"
            ttl = (cm.group(2) if cm else ttl).strip().strip("[]").strip(" -–—:.")
            cur = OChapter(cid, "chapter", ttl)
            chapters.append(cur)
            section, last_key = "chapter", None
            continue
        m = re.match(r"^(thesis|question)\s*:\s*(.*)$", low)
        if m:
            thesis, section, last_key = line.split(":", 1)[1].strip(), "thesis", "thesis"
            continue
        if re.match(r"^(hooks?|hook options?)\s*:?\s*$", low):
            section, cur = "hooks", None
            continue
        m = re.match(r"^(hook choice|chosen hook|hook chosen)\s*:\s*(.*)$", low)
        if m:
            hook_choice = line.split(":", 1)[1].strip()
            continue
        if re.match(r"^facts\s*:?\s*$", low) and cur is None:
            section = "facts"
            continue
        if re.match(r"^chapters\s*:?\s*$", low):
            section, cur = "chapters", None
            continue
        m = re.match(r"^(target words|target|total words)\s*[:=]\s*~?([\d,]+)", low)
        if m:
            target = int(m.group(2).replace(",", ""))
            continue
        if section == "hooks":
            hm2 = re.match(r"^\s*(?:[-*•]\s*)?(?:(h\d+)|(\d+)[.)])?\s*[:.)-]?\s*(.+)$", line, re.I)
            txt = hm2.group(3).strip() if hm2 else line
            hid = (hm2.group(1) or (f"h{hm2.group(2)}" if hm2 and hm2.group(2) else f"h{len(hooks) + 1}")).lower()
            hooks.append(Hook(hid, txt.strip('"“” ')))
            continue
        if section == "facts" and "|" in line:
            fact_n += 1
            f = _parse_fact_line(line, f"f{fact_n:02d}", res, known)
            if f:
                facts.append(f)
            continue
        if section == "chapter" and cur is not None:
            km = re.match(r"^([A-Za-z ]{3,12})\s*:\s*(.*)$", line)
            if km and km.group(1).strip().lower() in _KEYS:
                k, v = _KEYS[km.group(1).strip().lower()], km.group(2).strip()
                last_key = k
                if k == "role":
                    cur.role = v.lower().replace(" ", "_") if v.lower().replace(" ", "_") in ("cold_open", "chapter", "closing") else "chapter"
                elif k == "card":
                    cur.card = _yes(v)
                elif k == "budget":
                    mm = re.search(r"\d[\d,]*", v)
                    cur.word_budget = int(mm.group(0).replace(",", "")) if mm else 0
                elif k == "purpose":
                    cur.purpose = v
                elif k == "facts":
                    cur.facts = [x.lower() for x in FACT_ID_RE.findall(v)]
                elif k == "show":
                    cur.show = [x.strip() for x in v.split(";") if x.strip()]
                continue
            if last_key == "purpose":
                cur.purpose = (cur.purpose + " " + line).strip()
                continue
            if last_key == "show":
                cur.show += [x.strip() for x in line.split(";") if x.strip()]
                continue
        if section == "thesis" and last_key == "thesis":
            thesis = (thesis + " " + line).strip()

    if not chapters:
        return _fail(res, "No chapters were found (a chapter starts with a line like: ## c01 COLD OPEN).", body, "The outline could not be read.")
    seen = set()
    for c in chapters:                                   # ids are unique
        while c.id in seen:
            c.id = f"c{len(seen) + 1:02d}"
        seen.add(c.id)
    if chapters[0].role == "chapter" and "cold open" in _norm(chapters[0].title):
        chapters[0].role = "cold_open"
    if chapters[-1].role == "chapter" and _norm(chapters[-1].title) in ("closing", "close", "conclusion"):
        chapters[-1].role = "closing"
    tw = target or sum(c.word_budget for c in chapters) or target_words
    if any(c.word_budget <= 0 for c in chapters):
        share = max(1, round(tw / len(chapters)))
        for c in chapters:
            if c.word_budget <= 0:
                c.word_budget = share
                res.add("warning", "budget_defaulted", f"chapter {c.id} had no budget; set to {share}", chapter=c.id)
    if not thesis:
        res.add("warning", "no_thesis", "the outline has no THESIS line")
    if not facts:
        res.add("warning", "no_facts", "the outline has no fact table")
    fids = {f.id for f in facts}
    for c in chapters:
        for f in c.facts:
            if f not in fids:
                res.add("warning", "unknown_fact", f"chapter {c.id} uses fact {f}, which is not in the fact table", chapter=c.id)
    if hooks and not any(h.id == (hook_choice or "").lower() for h in hooks):
        mm = re.search(r"\d+", hook_choice or "")
        choice = f"h{mm.group(0)}" if mm else None
        hook_choice = choice if choice and any(h.id == choice for h in hooks) else hooks[0].id
        if not mm:
            res.add("info", "hook_defaulted", f"no valid HOOK CHOICE; {hook_choice} was chosen")
    elif hook_choice:
        hook_choice = hook_choice.lower()
    o = Outline(thesis, hooks, hook_choice, chapters, facts, tw, {"kind": "paste", "model": "", "created_at": now_iso()})
    o.counters = {"chapter": len(chapters), "fact": max([int(re.sub(r"\D", "", f.id) or 0) for f in facts], default=0)}
    res.ok, res.outline = True, o
    return res
