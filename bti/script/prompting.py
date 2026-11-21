"""Fill the prompt templates in prompts/ by string replacement. The text the "copy prompt" button gives and the text
sent to a model through the API are the same text."""
from __future__ import annotations

import re
from pathlib import Path

from .brief import REPO_ROOT, build_brief, load_options, render_brief
from .stats import MAX_SENTENCE_WORDS, WPS_DEFAULT
from .store import NChapter, Narration, Outline

PROMPTS = REPO_ROOT / "prompts"
SYSTEM = ("You are a careful researcher and narrator for a video channel about paintings. "
          "Follow the instructions in the user message exactly, including the output layout.")
RETRY_MARK = "YOUR PREVIOUS ANSWER WAS REJECTED."
CUT_MARK = "YOUR PREVIOUS ANSWER IS TOO LONG."          # the note of the one rewrite of a chapter that came out over its budget (generate.py)


class PromptError(Exception):
    pass


def _read(name: str, root: Path | None = None) -> str:
    p = (root or PROMPTS) / name
    if not p.is_file():
        raise PromptError(f"missing template {name}")
    return re.sub(r"<!--.*?-->\s*", "", p.read_text(encoding="utf-8"), flags=re.S).strip()


def _format_section(which: str, root: Path | None) -> str:
    p = (root or PROMPTS) / "rules_format.md"
    if not p.is_file():
        raise PromptError("missing template rules_format.md")
    text = p.read_text(encoding="utf-8")
    parts = re.split(r"<!--\s*section:(\w+)\s*-->", text)
    secs = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    if which not in secs:
        raise PromptError(f"rules_format.md has no section {which}")
    return secs[which]


def render_outline(o: Outline) -> str:
    """The outline in the same text layout `parse_outline` reads."""
    L = ["OUTLINE", "", f"THESIS: {o.thesis}", "", "HOOKS"]
    L += [f"{h.id}: {h.text}" for h in o.hook_options]
    if o.hook_choice:
        L.append(f"HOOK CHOICE: {o.hook_choice}")
    L += ["", "FACTS"]
    for f in o.facts:
        line = f"{f.id} | {f.certainty} | {', '.join(f.sources)} | {f.claim}"
        if f.conflict:
            line += f" | conflict: {f.conflict}"
        L.append(line)
    L += ["", "CHAPTERS"]
    for c in o.chapters:
        L += [f"## {c.id} {c.title}", f"ROLE: {c.role}", f"CARD: {'yes' if c.card else 'no'}", f"BUDGET: {c.word_budget}",
              f"PURPOSE: {c.purpose}", f"FACTS: {', '.join(c.facts)}", f"SHOW: {'; '.join(c.show)}", ""]
    L.append(f"TARGET WORDS: {o.target_words}")
    return "\n".join(L)


def render_written(n: Narration, chapter_ids: list[str]) -> str:
    out = []
    for c in n.chapters:
        if c.id in chapter_ids and c.beats:
            out.append(f"## {c.id} {c.title}\n" + "\n\n".join(b.text for b in c.beats))
    return "\n\n".join(out)


def render_chapter(c: NChapter) -> str:
    """One written chapter in the layout the model answers in (its own answer, given back to it to be cut)."""
    out = [f"## {c.id} {c.title}"]
    for b in c.beats:
        out += [b.text, ">> facts: " + ", ".join(b.facts) + " | show: " + "; ".join(b.show), ""]
    return "\n".join(out).strip()


def cut_note(words: int, budget: int, written: NChapter) -> str:
    """The note of the rewrite of a chapter that is over its budget: how many words to cut, what to cut first, and the text to cut."""
    aim = max(1, round(budget * 0.95))
    return (f"{CUT_MARK} It has {words} words and the budget of this chapter is {budget}, a ceiling. Write the chapter again with at most {budget} words "
            f"(aim for {aim}): that is {words - aim} words fewer. Keep its order, its best lines and the facts it rests on; cut the least necessary detail first: "
            "a second example, a repeated explanation, a reading of a small point. Add nothing new. Here is your previous answer:\n\n" + render_chapter(written))


def _fill(template: str, values: dict[str, str]) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), template)


def _notes(notes: str, opt_notes: str = "") -> str:
    n = "\n".join(x for x in (opt_notes.strip(), (notes or "").strip()) if x)
    return f"OWNER NOTES FOR THIS RUN (follow them; they override your taste)\n{n}" if n else ""


def build_prompt(phase: str, pdir: Path, *, notes: str = "", chapters: list[str] | None = None,
                 narration: Narration | None = None, outline: Outline | None = None, brief: dict | None = None,
                 retry_message: str | None = None, cut_message: str | None = None, wps: float = WPS_DEFAULT, root: Path | None = None) -> dict:
    """-> {"system", "user", "text"}; `text` is `user` (what the owner pastes into another chat). `retry_message` is the validator's sentence for a second try
    of an answer that could not be used; `cut_message` (made by `cut_note()`) is the note of the rewrite of a chapter that is over its budget."""
    brief = brief or build_brief(pdir)
    opts = load_options(pdir)
    target = outline.target_words if outline else opts["target_words"]
    limits = {"MAX_SENTENCE_WORDS": str(MAX_SENTENCE_WORDS)}           # the one sentence limit, said by the templates through these words
    vals = {"BRIEF": render_brief(brief), "TARGET_WORDS": str(target), "WORDS_PER_SECOND": str(wps), **limits,
            "NOTES": _notes(notes, opts["notes"]), "RULES_VOICE": _fill(_read("rules_voice.md", root), limits)}
    if phase == "outline":
        vals["FORMAT_OUTLINE"] = _format_section("outline", root)
        text = _fill(_read("outline.md", root), vals)
    elif phase == "script":
        if outline is None:
            raise PromptError("the script prompt needs an outline")
        want = chapters or [c.id for c in outline.chapters]
        bad = [c for c in want if outline.chapter(c) is None]
        if bad:
            raise PromptError(f"unknown chapter(s): {', '.join(bad)}")
        rest = [c.id for c in outline.chapters if c.id not in want]
        prev = render_written(narration, rest) if narration else ""
        vals["OUTLINE"] = render_outline(outline)
        vals["FORMAT_SCRIPT"] = _format_section("script", root)
        vals["PREVIOUS"] = ("THE CHAPTERS ALREADY WRITTEN (context only; do not repeat them, do not rewrite them)\n" + prev + "\n") if prev else ""
        budgets = "\n".join(f"- {c.id} {c.title}: at most {c.word_budget} words (aim for {max(1, round(c.word_budget * 0.9))} to {c.word_budget})"
                            for c in outline.chapters if c.id in want)
        if len(want) == len(outline.chapters):
            task = "Write the whole narration, every chapter, in outline order.\n"
        else:
            task = "Write ONLY the chapters listed here. Do not write the others.\n"
        vals["TASK"] = f"{task}{budgets}\nChapters to write now: {', '.join(want)}"
        text = _fill(_read("script.md", root), vals)
    else:
        raise PromptError(f"unknown phase {phase!r}")
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    if retry_message:
        text += f"\n{RETRY_MARK} {retry_message}\nWrite the answer again, complete, in the exact layout above.\n"
    if cut_message:
        text += f"\n{cut_message}\n\nWrite the answer again, complete, in the exact layout above.\n"
    return {"system": SYSTEM, "user": text, "text": text}
