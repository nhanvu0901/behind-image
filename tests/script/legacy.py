"""Converter for the legacy hand-made script layout (demo_runs/claude_code/script.txt):
blocks headed `[NAME]`, one paragraph per line. Tests and tools only.

legacy_to_layout(text) -> (script text in the `## cNN NAME` layout, [(id, title)])
outline_for(chapters, target) -> an Outline whose chapters match the converted script
"""
from __future__ import annotations

import re
from pathlib import Path

from bti.script.store import OChapter, Outline

LEGACY = Path(__file__).resolve().parents[2] / "demo_runs" / "claude_code" / "script.txt"


def read_legacy() -> str:
    return LEGACY.read_text(encoding="utf-8")


def legacy_blocks(text: str) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.fullmatch(r"\[([^\]]+)\]", line)
        if m:
            blocks.append((m.group(1).replace("_", " "), []))
        elif blocks:
            blocks[-1][1].append(line)
    return blocks


def legacy_to_layout(text: str, with_meta: bool = False) -> tuple[str, list[tuple[str, str]]]:
    out, chapters = ["FINAL SCRIPT", ""], []
    for i, (name, paras) in enumerate(legacy_blocks(text), 1):
        cid = f"c{i:02d}"
        chapters.append((cid, name))
        out.append(f"## {cid} {name}")
        for p in paras:
            out.append(p)
            if with_meta:
                out.append(">> facts: | show: the whole painting")
            out.append("")
    return "\n".join(out), chapters


def outline_for(chapters: list[tuple[str, str]], target: int = 2000) -> Outline:
    n = len(chapters)
    cs = []
    for i, (cid, name) in enumerate(chapters):
        role = "cold_open" if name == "COLD OPEN" else "closing" if name == "CLOSING" else "chapter"
        cs.append(OChapter(cid, role, name, role == "chapter", f"purpose of {name}", round(target / n)))
    return Outline("the thesis", [], None, cs, [], target)
