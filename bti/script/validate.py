"""Validation of an outline and of a narration (design section 2.7).

Issue = {"level": "error"|"warning"|"info", "code", "message", "chapter"?, "beat"?}.
Errors block approval. Warnings and info never do.
"""
from __future__ import annotations

import re

from .stats import WPS_DEFAULT, count_words, minutes, narration_stats
from .store import Narration, Outline

MARKUP = [
    (re.compile(r"^\s*#{1,6}\s"), "a heading mark (#)"),
    (re.compile(r"^\s*>>"), "a metadata line (>>)"),
    (re.compile(r"\*\*|__"), "bold marks"),
    (re.compile(r"`"), "a code mark"),
    (re.compile(r"<[^>\n]{1,40}>"), "an HTML or angle-bracket tag"),
    (re.compile(r"\[[^\]\n]{1,80}\]"), "square brackets (a tag or stage direction)"),
    (re.compile(r"\((?:pause|beat|music|sfx|cut|b-?roll|show|visual|on screen|silence)\b[^)]*\)", re.I), "a stage direction"),
    (re.compile(r"\b(?:facts|show)\s*:\s*\S", re.I), "a facts/show metadata fragment"),
    (re.compile(r"\b[A-Z]{3}-\d{2,3}\b"), "a source paragraph id"),
    (re.compile(r"\bf\d{2,}\b"), "a fact id"),
    (re.compile(r"^\s*(?:word count|hook|chapter \d+)\b\s*[:=]", re.I), "a label"),
    (re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S"), "a list marker"),
    (re.compile(r"\|"), "a table bar"),
]
SPOKEN_CHARS = re.compile(r"[;:()—–…]|\.\.\.")


def issue(level: str, code: str, message: str, **where) -> dict:
    return {"level": level, "code": code, "message": message, **where}


def markup_in(text: str) -> str | None:
    for rx, label in MARKUP:
        if rx.search(text):
            return label
    return None


def validate_outline(o: Outline, brief: dict | None = None) -> list[dict]:
    out: list[dict] = []
    if not o.thesis.strip():
        out.append(issue("error", "no_thesis", "The thesis is empty: write the one question this video answers."))
    if not o.chapters:
        out.append(issue("error", "no_chapters", "The outline has no chapters."))
    seen = set()
    for c in o.chapters:
        if not c.id or c.id in seen:
            out.append(issue("error", "duplicate_chapter", f"Chapter id {c.id!r} is empty or used twice.", chapter=c.id))
        seen.add(c.id)
        if not c.title.strip():
            out.append(issue("error", "chapter_no_title", f"Chapter {c.id} has no title.", chapter=c.id))
        if c.word_budget <= 0:
            out.append(issue("error", "chapter_no_budget", f"Chapter {c.id} has no word budget.", chapter=c.id))
    fids = [f.id for f in o.facts]
    if len(set(fids)) != len(fids):
        out.append(issue("error", "duplicate_fact", "Two facts share an id."))
    known_f = set(fids)
    known_p = set(brief["paragraph_ids"]) if brief else None
    for f in o.facts:
        if not f.sources:
            out.append(issue("warning", "fact_no_source", f"Fact {f.id} cites no source paragraph.", fact=f.id))
        elif known_p is not None:
            bad = [s for s in f.sources if s not in known_p]
            if bad:
                out.append(issue("warning", "unknown_source_id", f"Fact {f.id} cites {', '.join(bad)}, not in the brief.", fact=f.id))
        if f.certainty == "disputed" and not f.conflict:
            out.append(issue("warning", "disputed_no_conflict", f"Fact {f.id} is disputed but no conflict is described.", fact=f.id))
    for c in o.chapters:
        for fid in c.facts:
            if fid not in known_f:
                out.append(issue("warning", "unknown_fact", f"Chapter {c.id} uses fact {fid}, which is not in the fact table.", chapter=c.id))
    used = {fid for c in o.chapters for fid in c.facts}
    for f in o.facts:
        if f.id not in used:
            out.append(issue("warning", "fact_unused", f"Fact {f.id} is not used by any chapter.", fact=f.id))
    if o.hook_options and o.hook_choice not in {h.id for h in o.hook_options}:
        out.append(issue("warning", "no_hook_choice", "No hook option is chosen."))
    total = sum(c.word_budget for c in o.chapters)
    if o.target_words and total and abs(total - o.target_words) > 0.15 * o.target_words:
        out.append(issue("warning", "budget_sum", f"The chapter budgets add up to {total} words; the target is {o.target_words}."))
    return out


def outline_gate(o: Outline | None) -> dict | None:
    """None when the outline is approved and fresh, else an issue (the "stale outline approval" error)."""
    if o is None:
        return issue("error", "outline_missing", "There is no outline: the narration follows an approved outline.")
    if not o.approval.get("approved"):
        return issue("error", "outline_not_approved", "The outline is not approved. Approve it before approving the narration.")
    if o.approval.get("sha1") != o.rev():
        return issue("error", "outline_stale", "Stale outline approval: the outline changed after it was approved. Approve it again.")
    return None


def _ngrams(words: list[str], n: int) -> set[tuple]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def source_overlap(n: Narration, brief: dict, size: int = 8) -> float:
    """Share of narration words inside an 8-word run copied from an included source (information only)."""
    tok = lambda s: re.findall(r"[a-z0-9']+", s.lower())
    src: set[tuple] = set()
    for s in brief["sources"]:
        if s["included"]:
            src |= _ngrams(tok(" ".join(p["text"] for p in s["paragraphs"])), size)
    covered = total = 0
    for c in n.chapters:
        for b in c.beats:
            w = tok(b.text)
            total += len(w)
            mark = [False] * len(w)
            for i in range(len(w) - size + 1):
                if tuple(w[i:i + size]) in src:
                    for j in range(i, i + size):
                        mark[j] = True
            covered += sum(mark)
    return round(covered / total, 3) if total else 0.0


def validate_narration(n: Narration, outline: Outline | None, *, wps: float = WPS_DEFAULT, brief: dict | None = None) -> list[dict]:
    out: list[dict] = []
    gate = outline_gate(outline)
    if gate:
        out.append(gate)
    st = narration_stats(n, outline, wps)
    have = {c.id for c in n.chapters}
    if outline:
        for oc in outline.chapters:
            c = n.chapter(oc.id)
            if c is None or not c.beats:
                out.append(issue("error", "chapter_missing", f"Chapter {oc.id} {oc.title} is missing from the narration.", chapter=oc.id))
        for c in n.chapters:
            if outline.chapter(c.id) is None:
                out.append(issue("warning", "unknown_chapter", f"Chapter {c.id} {c.title} is not in the outline.", chapter=c.id))
    known = outline.fact_ids() if outline else None
    for c in n.chapters:
        for b in c.beats:
            where = {"chapter": c.id, "beat": b.id}
            w = count_words(b.text)
            if not b.text.strip():
                out.append(issue("error", "empty_beat", f"Beat {b.id} in {c.id} is empty.", **where))
                continue
            m = markup_in(b.text)
            if m:
                out.append(issue("error", "markup_in_text", f"Beat {b.id} in {c.id} has {m} in its text; the text must be spoken words only.", **where))
            elif SPOKEN_CHARS.search(b.text):
                out.append(issue("warning", "spoken_chars", f"Beat {b.id} in {c.id} has punctuation the voice does not pause on (; : ( ) or a dash); use commas and full stops.", **where))
            if w > 90:
                out.append(issue("warning", "beat_too_long", f"Beat {b.id} in {c.id} has {w} words (more than 90); split it.", **where))
            if not b.show:
                out.append(issue("warning", "no_show", f"Beat {b.id} in {c.id} has no hint of what is on screen.", **where))
            if known is not None:
                for f in b.facts:
                    if f not in known:
                        out.append(issue("warning", "unknown_fact", f"Beat {b.id} cites fact {f}, which is not in the outline.", **where))
    target = outline.target_words if outline else 0
    if target:
        ratio = st["words"] / target
        if ratio < 0.70:
            out.append(issue("error", "words_under", f"Only {st['words']} words, under 70% of the target {target}."))
        elif abs(ratio - 1) > 0.15:
            out.append(issue("warning", "words_off_target", f"{st['words']} words; the target is {target} (more than 15% away)."))
    for ch in st["chapters"]:
        if ch["budget"] and ch["id"] in have and ch["words"] and abs(ch["words"] / ch["budget"] - 1) > 0.30:
            out.append(issue("warning", "chapter_off_budget", f"Chapter {ch['id']} {ch['title']} has {ch['words']} words; its budget is {ch['budget']} (more than 30% away).", chapter=ch["id"]))
    out.append(issue("info", "length", f"{st['words']} words, about {st['minutes']:.1f} minutes at {wps} words per second."))
    for note in st["sentence_profile"]["notes"]:
        out.append(issue("info", "sentence_profile", note))
    if outline and brief:
        cited = {fid for c in n.chapters for b in c.beats for fid in b.facts}
        used_paras = {p for f in outline.facts if f.id in cited for p in f.sources}
        parts = []
        for s in brief["sources"]:
            ids = {p["id"] for p in s["paragraphs"]}
            if ids and s["included"]:
                parts.append(f"{s['code']} {len(ids & used_paras)}/{len(ids)}")
        if parts:
            out.append(issue("info", "source_share", "Source paragraphs behind the cited facts: " + ", ".join(parts) + "."))
        ov = source_overlap(n, brief)
        out.append(issue("info", "overlap", f"{ov:.0%} of the words sit in runs of 8 or more words copied from the sources (information only)."))
    return out


def blocking(issues: list[dict]) -> list[dict]:
    return [i for i in issues if i["level"] == "error"]
