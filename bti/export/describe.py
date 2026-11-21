"""The video description and `chapters.txt` (design section 8, item 4). The wording lives in `description.template.txt`, so
that the channel's identity can change it later without touching code. The text is English: it is for the video's viewers.

Template syntax: `{{name}}` is replaced by a value. A paragraph (a block of lines between blank lines) that holds a
placeholder whose value is empty is dropped completely, so a missing part leaves no stray heading behind.
"""
from __future__ import annotations

import re
from pathlib import Path

from .mux import chapter_marks, merge_short

TEMPLATE = Path(__file__).with_name("description.template.txt")
FLAGS = ("rejected", "unknown", "small")


def clock(seconds: float) -> str:
    """`mm:ss`, or `h:mm:ss` from one hour on (YouTube's chapter format)."""
    s = int(seconds)
    return "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else "%02d:%02d" % (s // 60, s % 60)


def chapter_lines(marks) -> list[str]:
    return ["%s %s" % (clock(m["start"]), m["title"]) for m in marks]


def used_assets(storyboard: dict) -> list[str]:
    """Keys of the assets that appear in a shot (slots of shots, overlays and transitions), in order of first use."""
    assets = storyboard.get("assets") if isinstance(storyboard.get("assets"), dict) else {}
    seen: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            a = o.get("asset")
            if isinstance(a, str) and a in assets and a not in seen:
                seen.append(a)
            for k, v in o.items():
                if k != "asset":
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for shot in storyboard.get("shots") or []:
        walk(shot)
    return seen


def _name(a: dict) -> str:
    t = str(a.get("title") or "").strip()
    return "“%s”" % t if t else "Untitled image"


def credit_line(a: dict) -> str:
    c = a.get("credit") if isinstance(a.get("credit"), dict) else {}
    who = str(c.get("author") or a.get("artist") or "").strip()
    bits = [_name(a)]
    if who:
        bits.append("— " + who)
    lic = str(c.get("licence") or "").strip()
    if lic:
        bits.append("(%s)" % lic)
    line = " ".join(bits)
    url = str(c.get("source_url") or "").strip()
    return line + (", " + url if url else "")


def flag_note(a: dict) -> str | None:
    c = a.get("credit") if isinstance(a.get("credit"), dict) else {}
    f = c.get("flag")
    if f not in FLAGS:
        return None
    why = {"rejected": "its licence does not allow reuse as it stands", "unknown": "its licence could not be confirmed",
           "small": "the file is small, so it may look soft"}[f]
    return "Note: %s — %s. Check the credit before publishing." % (_name(a), why)


def book_lines(project_meta: dict, titles=None) -> list[str]:
    """One line per book the script used (from `project.json` `sources`), with its title and author when the library knows it."""
    seen, out = set(), []
    for s in project_meta.get("sources") or []:
        bid = s.get("book_id") if isinstance(s, dict) else None
        if not isinstance(bid, str) or bid in seen:
            continue
        seen.add(bid)
        t = (titles or {}).get(bid) if isinstance(titles, dict) else None
        if isinstance(t, dict):
            out.append("%s%s" % (t.get("title") or bid, (" — " + t["author"]) if t.get("author") else ""))
        else:
            out.append(bid)
    return out


def library_titles() -> dict:
    """`{book_id: {title, author}}` from the library configuration; empty when it cannot be read."""
    try:
        from bti.library.config import BOOKS
        return {b["id"]: {"title": b.get("title"), "author": b.get("author")} for b in BOOKS}
    except Exception:   # noqa: BLE001 - the description still works with the book ids
        return {}


def artwork_line(storyboard: dict, project_meta: dict) -> str:
    """`Jan van Eyck, The Arnolfini Portrait (1434)` from the project's record, else from the main asset."""
    title = str(project_meta.get("title") or "").strip()
    artist = str(project_meta.get("artist") or "").strip()
    year = str(project_meta.get("year") or "").strip()
    if not title:
        keys = used_assets(storyboard)
        a = (storyboard.get("assets") or {}).get(keys[0]) if keys else None
        if isinstance(a, dict):
            title, artist, year = str(a.get("title") or ""), str(a.get("artist") or ""), str(a.get("year") or "")
    if not title:
        return ""
    s = "%s, %s" % (artist, title) if artist else title
    return s + (" (%s)" % year if year else "")


def render_template(template: str, values: dict) -> str:
    paras = re.split(r"\n\s*\n", template.strip("\n"))
    out = []
    for p in paras:
        names = re.findall(r"\{\{(\w+)\}\}", p)
        if any(not str(values.get(n, "")).strip() for n in names):
            continue
        out.append(re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m.group(1), "")), p))
    return "\n\n".join(out).strip() + "\n"


def video_title_of(storyboard: dict, video_title: str | None = None) -> str:
    """titlestep: the first line of the description. The video's own title (`video_title`: the project's title document; else `identity.video_title` of the storyboard, the one the
    channel-name beat shows), else what it was before: the storyboard's title (the painting's)."""
    t = str(video_title or "").strip()
    if not t:
        ident = storyboard.get("identity") if isinstance(storyboard.get("identity"), dict) else {}
        v = ident.get("video_title")
        t = re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""
    return t


def build_description(storyboard: dict, timing: dict, project_meta: dict, *, duration: float, template: str | None = None, titles=None, video_title: str | None = None) -> dict:
    """`{description, chapters, credits, notes}`: the two texts and the lists they were made from. The first line is the video's title (`video_title_of`), then the painting,
    painter and year as before."""
    template = template if template is not None else TEMPLATE.read_text(encoding="utf-8")
    marks, merged = merge_short(chapter_marks(timing.get("chapters"), duration))
    assets = storyboard.get("assets") or {}
    keys = used_assets(storyboard)
    credits = [credit_line(assets[k]) for k in keys]
    notes = [n for n in (flag_note(assets[k]) for k in keys) if n]
    title = video_title_of(storyboard, video_title) or str(storyboard.get("title") or project_meta.get("title") or "").strip()
    values = {
        "title": title,
        "artwork": artwork_line(storyboard, project_meta),
        "chapters": "\n".join(chapter_lines(marks)) if len(marks) >= 2 else "",
        "books": "\n".join(book_lines(project_meta, titles)),
        "credits": "\n".join(credits),
        "notes": "\n".join(notes),
    }
    return {"description": render_template(template, values), "chapters": ("\n".join(chapter_lines(marks)) + "\n") if marks else "",
            "credits": credits, "notes": notes, "merged_chapters": merged}
