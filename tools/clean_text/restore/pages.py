"""Reading and writing the clean page format (docs/design/2026-11-16-clean-text-format.md), line by line.

A page is a list of items. An item is one structural line (`[meta] ...`, `# ...`, `[continues]` and so on) or one prose
paragraph (the format keeps one paragraph per line). Blank lines carry no meaning except as separators, so a page is
compared and rebuilt through its items."""
from __future__ import annotations

import re
from dataclasses import dataclass

TAGS = ("page-type", "meta", "caption", "credit", "note", "quote", "continues", "sidebar-start", "sidebar-end")
_TAG_RE = re.compile(r"^\[([a-z][a-z-]*)\](?:[ \t]+(.*))?$")
_HEAD_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$")
PARA = "p"


@dataclass
class Item:
    kind: str            # a tag from TAGS, "#", "##", "p" (prose), or "unknown:<x>" for a line that looks structural but is not
    text: str            # the text after the tag (or the whole paragraph)
    line: str            # the line as written
    blank_before: bool   # a blank line stood before it (False for the first item)


def classify(line: str) -> tuple[str, str]:
    m = _TAG_RE.match(line)
    if m:
        tag = m.group(1)
        return (tag if tag in TAGS else f"unknown:{tag}"), (m.group(2) or "").strip()
    m = _HEAD_RE.match(line)
    if m:
        hashes = m.group(1)
        return (hashes if hashes in ("#", "##") else f"unknown:{hashes}"), m.group(2).strip()
    return PARA, line.strip()


def is_structural(kind: str) -> bool:
    return kind != PARA


def parse_page(text: str) -> list[Item]:
    items: list[Item] = []
    blank = False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            blank = True
            continue
        kind, body = classify(line)
        items.append(Item(kind, body, line, blank and bool(items)))
        blank = False
    return items


def page_type(text: str) -> str | None:
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.strip():
            kind, body = classify(raw.rstrip())
            return body if kind == "page-type" else None
    return None


def render(lines: list[str], blank_before: list[bool]) -> str:
    out: list[str] = []
    for line, blank in zip(lines, blank_before):
        if blank and out:
            out.append("")
        out.append(line)
    return "\n".join(out) + "\n"


def prose_count(items: list[Item]) -> int:
    return sum(1 for i in items if i.kind == PARA)
