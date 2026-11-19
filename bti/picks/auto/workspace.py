"""The agent's work folder for the automatic picks job: a new folder in the system temp directory that holds COPIES only.

    TASK.md                   the instructions (skills/picks_auto/PLAN.template.md or CHOOSE.template.md)
    check, crop               (.cmd on Windows) the two helper commands, one-line wrappers around `python -m bti.picks.auto.helper`
    inputs/context.json       what `check` validates against (do not edit)
    inputs/narration.json     the lines of the narration, chapter by chapter, with which of them are yours (`target`)
    inputs/facts.json         the dossier's facts, id -> sentence
    inputs/dossier.json       the painting's identity and the named details of the dossier
    inputs/painting.json      the main painting: its size, the regions it already has (as boxes), the copies below
    inputs/main_large.jpg     the copy `crop` cuts from (at most 3600 px on the long side)
    images/main.jpg           the main painting to look at (at most 1568 px)
    out/                      what the agent writes: plan.json (part 1) or choice.json (part 3). Only this is read back.
    look/                     the crops and grids the agent makes for itself

and, for the choose session only:

    inputs/wants.json         the pictures to choose, each with its numbered candidates, and the pictures of the owner's books (B1, B2 ...)
    inputs/regions.json       the proposed boxes on the main painting
    images/w_<id>.jpg         one contact sheet of numbered thumbnails per wanted picture
    images/books_<k>.jpg      contact sheets of the pictures in the owner's books
    images/d_<NAME>.jpg       the crop of each proposed box

The project folder and the repository are never inside it."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import images, shapes
from .inputs import Inputs

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = REPO_ROOT / "skills" / "picks_auto"
IS_WINDOWS = os.name == "nt"
PREFIX = "bti-picks-"
HELPER_MODULE = "bti.picks.auto.helper"
BOOKS_PER_SHEET = 12
MAX_BOOK_PICTURES = 24


class WorkspaceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class Workspace:
    root: Path
    mode: str
    notes: list = field(default_factory=list)


def clean_old(max_age_s: float = 2 * 86400) -> int:
    """Remove work folders of earlier runs that are older than `max_age_s` (only folders this module made: its own name prefix)."""
    n = 0
    base = Path(tempfile.gettempdir())
    for d in base.glob(PREFIX + "*"):
        try:
            if d.is_dir() and not d.is_symlink() and time.time() - d.stat().st_mtime > max_age_s:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        except OSError:
            continue
    return n


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _json(path: Path, obj) -> None:
    _write(path, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def wrappers(root: Path, python: str, repo: Path) -> dict:
    """`check` and `crop`: one-line wrappers, so that the agent runs `./check` and `./crop ...` and nothing else."""
    cmds = {}
    for name in ("check", "crop"):
        if IS_WINDOWS:
            f = Path(root) / (name + ".cmd")
            _write(f, '@echo off\r\nset "PYTHONPATH=%s"\r\nset PYTHONUTF8=1\r\n"%s" -m %s %s %%*\r\n' % (repo, python, HELPER_MODULE, name))
            cmds[name] = ".\\" + name + ".cmd"
        else:
            f = Path(root) / name
            _write(f, "#!/bin/sh\nPYTHONPATH='%s' PYTHONUTF8=1 exec '%s' -m %s %s \"$@\"\n"
                   % (str(repo).replace("'", "'\\''"), python.replace("'", "'\\''"), HELPER_MODULE, name))
            f.chmod(f.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            cmds[name] = "./" + name
    return cmds


def render(text: str, values: dict) -> str:
    """`{{KEY}}` replaced; `{{#KEY}}...{{/KEY}}` kept (without its markers) when the value of KEY is not empty, else removed."""
    def block(m):
        return m.group(2) if str(values.get(m.group(1)) or "").strip() else ""
    text = re.sub(r"\{\{#([A-Z_]+)\}\}\n?(.*?)\{\{/\1\}\}\n?", block, text, flags=re.S)
    for k, v in values.items():
        text = text.replace("{{%s}}" % k, str(v))
    return text


def _common(inp: Inputs, root: Path, mode: str, ctx_json: dict) -> dict:
    """The files both sessions share. -> the wrapper commands."""
    p = inp.painting
    (root / "images").mkdir(parents=True, exist_ok=True)
    for sub in ("inputs", "out", "look"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    try:
        sw, sh, cw, ch = images.save_scaled(p.file, root / "images" / "main.jpg", images.VIEW_SIDE, 90)
        images.save_scaled(p.file, root / "inputs" / "main_large.jpg", images.LARGE_SIDE, 90)
    except images.ImageError:
        raise WorkspaceError("main_asset_unreadable", "the main painting cannot be read as a picture")
    _json(root / "inputs" / "painting.json", {
        "key": p.key, "title": p.title, "artist": p.artist, "year": p.year, "source_size": [sw, sh], "image": "images/main.jpg",
        "image_size": [cw, ch], "large": "inputs/main_large.jpg",
        "note": "A box is [x0, y0, x1, y1] in FRACTIONS of the painting: 0 is the left or top edge, 1 the right or bottom edge.",
        "regions": {n: {"box": r["box"], "label": r["label"]} for n, r in p.regions.items()}})
    lines = []
    for c in inp.chapters:
        rows = []
        for b in c["beats"]:
            row = {"id": b["id"], "no": b["no"], "text": b["text"], "facts": b["facts"], "show": b["show"], "words": b["words"],
                   "seconds": b["seconds"], "target": b["id"] in inp.targets}
            cur = inp.picks["beats"].get(b["id"])
            if b["id"] not in inp.targets and cur and (cur["items"] or cur["status"] == "skip"):
                row["already"] = ("needs no picture of its own" if not cur["items"] else
                                  [{"asset": i["asset"], "region": i["region"], "role": i["role"]} for i in cur["items"]])
            rows.append(row)
        lines.append({"id": c["id"], "title": c["title"], "role": c["role"], "lines": rows})
    _json(root / "inputs" / "narration.json", {"note": "Your lines are those with `target: true`. The others are not yours: they keep what they have.",
                                              "chapters": lines})
    _json(root / "inputs" / "facts.json", inp.facts)
    _json(root / "inputs" / "dossier.json", {"identity": inp.identity, "details": inp.details})
    _json(root / "inputs" / "context.json", {"mode": mode, **ctx_json})
    return wrappers(root, sys.executable, REPO_ROOT)


def _values(inp: Inputs, cmds: dict, limits, extra: dict) -> dict:
    p = inp.painting
    return {"CHECK_CMD": cmds["check"], "CROP_CMD": cmds["crop"], "TITLE": p.title or "(no title)", "ARTIST": p.artist or "(unknown)",
            "YEAR": p.year or "(unknown)", "N_TARGETS": len(inp.targets), "N_LINES": len(inp.beats), "N_CHAPTERS": len(inp.chapters),
            "MAX_MINUTES": int(limits.minutes), "MAX_STEPS": int(limits.steps), "OWNER_NOTE": inp.owner_note,
            "TARGET_LIST": ", ".join(inp.targets), **extra}


def _template(name: str, template: Path | None) -> str:
    f = Path(template or (SKILL_DIR / name))
    if not f.is_file():
        raise WorkspaceError("template_missing", "skills/picks_auto/%s is missing" % name)
    return f.read_text(encoding="utf-8")


def build_plan(inp: Inputs, limits, *, root: Path | None = None, template: Path | None = None) -> Workspace:
    """The folder of part 1 (plan)."""
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix=PREFIX))
    root.mkdir(parents=True, exist_ok=True)
    cmds = _common(inp, root, "plan", {"plan": inp.plan_ctx().to_json()})
    _write(root / "TASK.md", render(_template("PLAN.template.md", template), _values(inp, cmds, limits, {})))
    return Workspace(root=root, mode="plan")


def build_choose(inp: Inputs, plan: dict, search: dict, limits, *, books: list, root: Path | None = None, template: Path | None = None) -> tuple[Workspace, shapes.ChoiceCtx]:
    """The folder of part 3 (choose): the plan's wanted pictures with their candidates, the owner's book pictures, and the proposed boxes.
    `search`: the saved search state (`bti.picks.auto.search`). `books`: [{"n", "label", "source_id", "thumb": Path | None}]."""
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix=PREFIX))
    root.mkdir(parents=True, exist_ok=True)
    shown = {wid: w for wid, w in search["wants"].items() if w.get("candidates")}
    used = [n for n in plan["regions"] if any(i["type"] == "detail" and i["region"] == n for ln in plan["lines"] for i in ln["show"])]
    ctx = shapes.ChoiceCtx(wants={wid: len(w["candidates"]) for wid, w in shown.items()}, books=len(books), regions=used)
    cmds = _common(inp, root, "choose", {"choice": ctx.to_json()})
    # the wanted pictures
    by_line = {ln["beat"]: ln for ln in plan["lines"]}
    rows = []
    for wid, w in shown.items():
        b = inp.beat(w["beat"])
        sheet = None
        if w["type"] != "map":
            sheet = "images/w_%s.jpg" % wid.replace(".", "_")
            images.contact_sheet([(str(c["n"]), (Path(inp.pdir) / c["thumb"]) if c.get("thumb") else None) for c in w["candidates"]], root / sheet)
        rows.append({"id": wid, "line": w["beat"], "line_no": b["no"], "line_text": b["text"], "line_reason": by_line.get(w["beat"], {}).get("reason", ""),
                     "type": w["type"], "kind": w.get("kind"), "what": w["what"], "searched": w.get("queries", []), "sheet": sheet,
                     "candidates": [{k: c.get(k) for k in ("n", "title", "source", "author", "licence", "flag", "width", "height", "page_url", "media")}
                                    for c in w["candidates"]]})
    book_rows = []
    sheets = []
    for k in range(0, len(books), BOOKS_PER_SHEET):
        chunk = books[k:k + BOOKS_PER_SHEET]
        dest = "images/books_%d.jpg" % (k // BOOKS_PER_SHEET + 1)
        images.contact_sheet([("B%d" % b["n"], b.get("thumb")) for b in chunk], root / dest, cols=4)
        sheets.append(dest)
    for b in books:
        book_rows.append({"n": "B%d" % b["n"], "label": b["label"]})
    _json(root / "inputs" / "wants.json", {"note": "Pick the number of a candidate on that want's sheet, \"B<number>\" for a picture of the owner's books, or null.",
                                          "wants": rows, "books": {"sheets": sheets, "pictures": book_rows}})
    # the proposed boxes
    reg_rows = []
    for name in used:
        r = plan["regions"][name]
        lines = [ln["beat"] for ln in plan["lines"] if any(i["type"] == "detail" and i["region"] == name for i in ln["show"])]
        dest = "images/d_%s.jpg" % name
        try:
            images.crop(inp.painting.file, r["box"], root / dest)
        except images.ImageError:
            dest = None
        reg_rows.append({"name": name, "box": r["box"], "what": r["what"], "lines": lines, "line_texts": {b: inp.beat(b)["text"] for b in lines}, "crop": dest})
    _json(root / "inputs" / "regions.json", {"note": "`crop` is exactly what the camera will show for the box.", "regions": reg_rows})
    extra = {"N_WANTS": len(rows), "N_BOOKS": len(books), "N_REGIONS": len(reg_rows), "WANT_LIST": ", ".join(w["id"] for w in rows),
             "REGION_LIST": ", ".join(used)}
    _write(root / "TASK.md", render(_template("CHOOSE.template.md", template), _values(inp, cmds, limits, extra)))
    return Workspace(root=root, mode="choose"), ctx
