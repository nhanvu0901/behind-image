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

    inputs/wants.json         the pictures to choose, each with its numbered candidates (up to eight: their page title, site and, for those found by
                              Wikipedia or the web, a few words about them), and the pictures of the owner's books (B1, B2 ...)
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

from . import images, shapes, tighten
from .inputs import Inputs

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = REPO_ROOT / "skills" / "picks_auto"
IS_WINDOWS = os.name == "nt"
PREFIX = "bti-picks-"
HELPER_MODULE = "bti.picks.auto.helper"
BOOKS_PER_SHEET = 12
MAX_BOOK_PICTURES = 24
MAX_SHOWN = 8                  # candidates of one wanted picture the choosing session looks at
CANDIDATE_KEYS = ("n", "title", "source", "author", "licence", "flag", "width", "height", "page_url", "media")
CANDIDATE_MORE = ("page_title", "site", "snippet")        # only the candidates Wikipedia or the web found have them


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


def wrappers(root: Path, python: str, repo: Path, helpers: tuple[str, ...] = ("check", "crop")) -> dict:
    """One-line wrapper scripts in `root`, so the agent runs `./check` / `./crop ...` and nothing else."""
    cmds = {}
    for name in helpers:
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
    narr = {"note": "Your lines are those with `target: true`. The others are not yours: they keep what they have.", "chapters": lines}
    if isinstance(inp.picks.get("subjects"), list):
        narr["existing_subjects"] = inp.picks["subjects"]
    if isinstance(inp.picks.get("names"), list):
        narr["existing_names"] = [n for n in inp.picks["names"] if isinstance(n, dict) and n.get("line") not in inp.targets]
    _json(root / "inputs" / "narration.json", narr)
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


def plan_regions_to_tighten(inp: Inputs, plan: dict) -> list[str]:
    """Region names referenced by lines in `plan` (show or fallback) that need the second look: all newly declared plan regions plus any existing non-tight region."""
    from bti.media import contentbox as pcb
    surface = tighten.surface_box((inp.painting.width, inp.painting.height), inp.painting.content_box) if inp.painting.content_box is not None else None
    seen: list[str] = []
    subject_regions = [s["where"]["region"] for s in plan.get("subjects", []) if isinstance(s.get("where"), dict) and "region" in s["where"]]
    lines = list(plan["lines"]) + [{"show": [{"type": "detail", "region": name}]} for name in subject_regions]
    for ln in lines:
        for it in list(ln["show"]) + ([ln["fallback"]] if ln.get("fallback") else []):
            if it["type"] == "detail":
                name = it["region"]
                if name in seen:
                    continue
                if name in plan["regions"]:
                    if surface is not None:
                        reg = shapes.box_to_region(plan["regions"][name]["box"], inp.painting.width, inp.painting.height)
                        if pcb.clamp_region(reg, surface) is None:
                            continue
                    seen.append(name)
                elif name in inp.painting.regions and not inp.painting.regions[name].get("tight"):
                    seen.append(name)
    return seen


def _copy_full_painting(src_file: Path, root: Path) -> str:
    ext = Path(src_file).suffix.lower() or ".jpg"
    rel = "inputs/main_full" + ext
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest)
    return rel


def build_choose(inp: Inputs, plan: dict, search: dict, limits, *, books: list, root: Path | None = None, template: Path | None = None,
                 second: bool = False) -> tuple[Workspace, shapes.ChoiceCtx]:
    """The folder of part 3 (choose): the plan's wanted pictures with their candidates, the owner's book pictures, and the second-look gridded cut-outs.
    `search`: the saved search state (`bti.picks.auto.search`). `books`: [{"n", "label", "source_id", "thumb": Path | None}].
    `second`: the folder of the SECOND session of a run that searched the web again (`bti.picks.auto.webround`): `search` then holds only the wants that
    got new candidates (numbered from 1), there are no boxes to review, and each want says what the first session answered (`earlier`)."""
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix=PREFIX))
    root.mkdir(parents=True, exist_ok=True)
    shown = {wid: {**w, "candidates": w["candidates"][:MAX_SHOWN]} for wid, w in search["wants"].items() if w.get("candidates")}
    used = [] if second else plan_regions_to_tighten(inp, plan)
    cutouts: dict[str, dict] = {}
    reg_rows: list[dict] = []
    if used:
        full_rel = _copy_full_painting(inp.painting.file, root)
        try:
            full_im = tighten._open_rgb(inp.painting.file)
        except images.ImageError:
            raise WorkspaceError("main_asset_unreadable", "the main painting cannot be read as a picture")
        sw, sh = inp.painting.width, inp.painting.height
        surface = tighten.surface_box((sw, sh), inp.painting.content_box)
        for name in used:
            lines = [ln["beat"] for ln in plan["lines"]
                     if any(i["type"] == "detail" and i["region"] == name for i in list(ln["show"]) + ([ln["fallback"]] if ln.get("fallback") else []))]
            line_texts = {b: inp.beat(b)["text"] for b in lines}
            if name in plan["regions"]:
                r = plan["regions"][name]
                rough_px = list(shapes.crop_pixels(r["box"], sw, sh))
                what, thing, existing = r["what"], str(r.get("thing") or ""), False
            else:
                er = inp.painting.regions[name]
                rough_px = tighten.region_to_rough_px(er["raw"], (sw, sh), surface)
                what, thing, existing = er["label"] or name, str(er.get("thing") or ""), True
            geom = tighten.cutout_geom(rough_px, (sw, sh), surface, margin=tighten.MARGIN_INITIAL)
            dest = "images/d_%s.jpg" % name
            tighten.render_cutout(inp.painting.file, geom, root / dest, with_grid=True, full_im=full_im)
            cutouts[name] = {
                **geom, "name": name, "existing": existing, "what": what, "thing": thing,
                "full_image": full_rel, "cutout": dest, "line_texts": list(line_texts.values()),
            }
            reg_rows.append({
                "name": name, "existing": existing, "what": what, "thing": thing,
                "lines": lines, "line_texts": line_texts, "cutout": dest,
                "cutout_size": list(geom["cutout_size"]), "rough_px": list(geom["rough_px"]),
            })
    subject_wants = {"%s.%d" % (ln["beat"], n): item["entity"] for ln in plan["lines"]
                     for n, item in enumerate(ln["show"], 1) if isinstance(item, dict) and item.get("entity")
                     and any(subject.get("id") == item["entity"] for subject in plan.get("subjects", []))}
    ctx = shapes.ChoiceCtx(wants={wid: len(w["candidates"]) for wid, w in shown.items()}, books=len(books), regions=used, cutouts=cutouts,
                           subject_wants={wid: sid for wid, sid in subject_wants.items() if wid in shown},
                           period_wants=[wid for wid, sid in subject_wants.items() if wid in shown and shown[wid].get("type") == "context"],
                           modern_wants=[wid for wid in subject_wants if wid in shown and shown[wid].get("modern_fallback")
                                         and all(c.get("source") in ("pexels", "pixabay") for c in shown[wid]["candidates"])],
                           incomplete_wants=[wid for wid in subject_wants if wid in shown and shown[wid].get("period_incomplete")])
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
        row = {"id": wid, "line": w["beat"], "line_no": b["no"], "line_text": b["text"], "line_reason": by_line.get(w["beat"], {}).get("reason", ""),
               "type": w["type"], "kind": w.get("kind"), "what": w["what"], "searched": w.get("queries", []), "sheet": sheet,
               "candidates": [{**{k: c.get(k) for k in CANDIDATE_KEYS}, **{k: c[k] for k in CANDIDATE_MORE if c.get(k)},
                               **({"step": c["step"]} if c.get("step") in (2, 3) else {})} for c in w["candidates"]]}
        if w.get("entity"):
            row["entity"] = w["entity"]
        if w.get("aspect"):
            row["aspect"] = w["aspect"]
        if w.get("period") and w["type"] == "context":
            row["period"] = w["period"]
        if w.get("kinds"):                              # what the line does (the plan's `kinds`): an `outside` line wants the thing itself
            row["kinds"] = list(w["kinds"])
        if w.get("wider"):
            row["wider"] = list(w["wider"])
        if w.get("places"):
            row["places"] = list(w["places"])
        if second:
            row["first_look"] = w.get("earlier") or ""
        rows.append(row)
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
    _json(root / "inputs" / "regions.json", {
        "note": "Each `cutout` is cut from the full-resolution painting (+15% margin, inside painted surface), scaled to 1,024 px long side, with a 100-px grid in cut-out pixels.",
        "regions": reg_rows,
    })
    extra = {"N_WANTS": len(rows), "N_BOOKS": len(books), "N_REGIONS": len(reg_rows), "WANT_LIST": ", ".join(w["id"] for w in rows),
             "REGION_LIST": ", ".join(used), "SECOND_LOOK": "yes" if second else ""}
    _write(root / "TASK.md", render(_template("CHOOSE.template.md", template), _values(inp, cmds, limits, extra)))
    return Workspace(root=root, mode="choose"), ctx


def build_tighten(pdir: Path, main_asset: dict, entries: list[dict], limits, *, root: Path | None = None,
                  template: Path | None = None) -> tuple[Workspace, dict]:
    """Work folder for standalone `picks.tighten`: only non-tight regions on the main painting, gridded full-res cut-outs, and `./check`."""
    from bti.media import contentbox as pcb
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix=PREFIX))
    for sub in ("images", "inputs", "out", "look"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    src_file = Path(pdir) / main_asset["file"]
    try:
        sw, sh, cw, ch = images.save_scaled(src_file, root / "images" / "main.jpg", images.VIEW_SIDE, 90)
        full_im = tighten._open_rgb(src_file)
    except images.ImageError:
        raise WorkspaceError("main_asset_unreadable", "the main painting cannot be read as a picture")
    full_rel = _copy_full_painting(src_file, root)
    asset_copy = dict(main_asset)
    pcb.ensure(asset_copy, pdir)
    surface = tighten.surface_box((sw, sh), pcb.box_of(asset_copy))
    cutouts: dict[str, dict] = {}
    reg_rows: list[dict] = []
    for entry in entries:
        name = entry["name"]
        raw_r = entry["raw"]
        rough_px = tighten.region_to_rough_px(raw_r, (sw, sh), surface)
        geom = tighten.cutout_geom(rough_px, (sw, sh), surface, margin=tighten.MARGIN_INITIAL)
        dest = "images/d_%s.jpg" % name
        tighten.render_cutout(src_file, geom, root / dest, with_grid=True, full_im=full_im)
        line_texts = entry.get("line_texts") or {}
        cutouts[name] = {
            **geom, "name": name, "existing": True,
            "what": str(entry.get("label") or name),
            "thing": str(entry.get("thing") or ""),
            "full_image": full_rel, "cutout": dest,
            "line_texts": list(line_texts.values()),
        }
        reg_rows.append({
            "name": name, "label": str(entry.get("label") or ""), "thing": str(entry.get("thing") or ""),
            "lines": list(entry.get("lines") or []), "line_texts": line_texts,
            "cutout": dest, "cutout_size": list(geom["cutout_size"]), "rough_px": list(geom["rough_px"]),
        })
    tctx = {"regions": list(cutouts), "cutouts": cutouts}
    _json(root / "inputs" / "painting.json", {
        "title": str(main_asset.get("title") or ""), "artist": str(main_asset.get("artist") or ""),
        "year": str(main_asset.get("year") or ""), "source_size": [sw, sh],
        "image": "images/main.jpg", "image_size": [cw, ch],
    })
    _json(root / "inputs" / "regions.json", {
        "note": "Measure each region's tight box in its cut-out's 100-px grid pixels (`out/tighten.json`).",
        "regions": reg_rows,
    })
    _json(root / "inputs" / "context.json", {"mode": "tighten", "tighten": tctx})
    cmds = wrappers(root, sys.executable, REPO_ROOT, helpers=("check",))
    vals = {
        "CHECK_CMD": cmds["check"],
        "TITLE": str(main_asset.get("title") or "(no title)"),
        "ARTIST": str(main_asset.get("artist") or "(unknown)"),
        "YEAR": str(main_asset.get("year") or "(unknown)"),
        "N_REGIONS": len(reg_rows),
        "REGION_LIST": ", ".join(cutouts),
        "MAX_MINUTES": int(limits.minutes),
        "MAX_STEPS": int(limits.steps),
    }
    _write(root / "TASK.md", render(_template("TIGHTEN.template.md", template), vals))
    return Workspace(root=root, mode="tighten"), tctx
