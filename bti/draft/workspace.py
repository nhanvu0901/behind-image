"""The agent's workspace (design section 7.3): a new folder in the system temp directory that holds COPIES only.

    TASK.md                 the instructions (from skills/storyboard_draft/TASK.template.md)
    INSTRUCTION.md          edit mode only: the owner's words and the scope
    check / defaults / still   (.cmd on Windows) the three helper commands, each a one-line wrapper around `python -m bti.draft.*`
    inputs/beats.json       chapters and beats: text, facts, show words, start, end, w0, w1, the picks of each beat
    inputs/words.tsv        index, word, start, end
    inputs/assets.json      the pictures: copy path, copy size, source size, scale, regions
    inputs/techniques.md    the registry in short, generated
    inputs/style.json       the style constants (pacing)
    inputs/current/<chapter>.json   the saved storyboard as draft specs, `locked` and `in_scope` marked (re-draft and edit)
    inputs/compile_input.json       what the helper commands compile from (do not edit)
    images/<key>.jpg        copies no larger than 1568 px on the long side
    out/                    what the agent writes: <chapter>.json, regions.json, notes.md
    look/                   stills the agent draws for itself

Only `out/` is read back. The project and the repository are never inside the workspace."""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from bti.engine import registry as R

from . import decompile as D
from . import spec as S
from . import techniques_md
from .inputs import DraftError, DraftInputs, narration_notes, beat_picks

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "skills" / "storyboard_draft" / "TASK.template.md"
MAX_IMAGE_PX = 1568
NOTES_MAX = 8000
IS_WINDOWS = os.name == "nt"
PREFIX = "bti-draft-"


@dataclass
class Workspace:
    root: Path
    inputs: DraftInputs
    mode: str = "draft"
    scale: dict = field(default_factory=dict)


@dataclass
class OutResult:
    specs: dict = field(default_factory=dict)
    regions: dict = field(default_factory=dict)
    notes: str = ""
    problems: list = field(default_factory=list)
    files: list = field(default_factory=list)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _json(path: Path, obj) -> None:
    _write(path, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def clean_old(max_age_s: float = 2 * 86400) -> int:
    """Remove workspaces of earlier runs that are older than `max_age_s`. Returns how many."""
    n = 0
    base = Path(tempfile.gettempdir())
    for d in base.glob(PREFIX + "*"):
        try:
            if d.is_dir() and time.time() - d.stat().st_mtime > max_age_s:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        except OSError:
            continue
    return n


# ------------------------------------------------------------------------------------------- images
def _copy_image(src: Path, dst: Path) -> tuple[int, int, int, int] | None:
    """Write a downscaled copy; -> (source w, source h, copy w, copy h) or None when the file cannot be read."""
    import cv2
    im = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if im is None:
        return None
    h, w = im.shape[:2]
    k = min(1.0, MAX_IMAGE_PX / float(max(w, h)))
    out = im if k >= 1.0 else cv2.resize(im, (max(1, int(round(w * k))), max(1, int(round(h * k)))), interpolation=cv2.INTER_AREA)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(dst), out, [cv2.IMWRITE_JPEG_QUALITY, 90]):
        return None
    return w, h, out.shape[1], out.shape[0]


def _rewrite_assets(assets: dict, copies: dict) -> dict:
    """The assets that have a copy in the workspace, with `file` pointing at it and `width`/`height` the SOURCE size."""
    out = {}
    for k, a in assets.items():
        if k in copies:
            b = copy.deepcopy(a)
            b["file"] = "images/%s.jpg" % k
            b["width"], b["height"] = copies[k][0], copies[k][1]
            out[k] = b
    return out


# ------------------------------------------------------------------------------------------- build
def _wrappers(root: Path, python: str, repo: Path) -> dict:
    cmds = {}
    for name, mod in (("check", "bti.draft.check"), ("defaults", "bti.draft.defaults"), ("still", "bti.draft.still")):
        if IS_WINDOWS:
            f = root / (name + ".cmd")
            _write(f, '@echo off\r\nset "PYTHONPATH=%s"\r\nset PYTHONUTF8=1\r\n"%s" -m %s %%*\r\n' % (repo, python, mod))
            cmds[name] = ".\\" + name + ".cmd"
        else:
            f = root / name
            _write(f, "#!/bin/sh\nPYTHONPATH='%s' PYTHONUTF8=1 exec '%s' -m %s \"$@\"\n" % (str(repo).replace("'", "'\\''"), python.replace("'", "'\\''"), mod))
            f.chmod(f.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            cmds[name] = "./" + name
    return cmds


def _beats_doc(inp: DraftInputs) -> dict:
    notes = narration_notes(inp.narration)
    chapters = []
    for c in inp.timing["chapters"]:
        beats = []
        for b in inp.timing["beats"]:
            if b["chapter"] != c["id"]:
                continue
            n = notes.get(b["id"], {})
            beats.append({"id": b["id"], "text": b["text"], "facts": n.get("facts", []), "show": n.get("show", []), "start": round(b["start"], 3),
                          "end": round(b["end"], 3), "w0": b["w0"], "w1": b["w1"], "picks": beat_picks(inp.picks, b["id"])})
        chapters.append({"id": c["id"], "name": c["name"], "start": round(c["start"], 3), "end": round(c["end"], 3), "card": c["card"],
                         "w0": c["w0"], "w1": c["w1"], "beats": beats})
    return {"title": inp.title, "duration": round(inp.timing["duration"], 3), "n_words": len(inp.timing["words"]),
            "main_asset": inp.picks["main_asset"], "chapters": chapters}


def render_template(text: str, mode: str, values: dict) -> str:
    """`{{#DRAFT}}..{{/DRAFT}}` and `{{#EDIT}}..{{/EDIT}}` blocks are kept for their mode only; `{{KEY}}` is replaced."""
    for m in ("DRAFT", "EDIT"):
        keep = (m == mode.upper())
        text = re.sub(r"\{\{#%s\}\}\n?(.*?)\{\{/%s\}\}\n?" % (m, m), (lambda g: g.group(1)) if keep else (lambda g: ""), text, flags=re.S)
    for k, v in values.items():
        text = text.replace("{{%s}}" % k, str(v))
    return text


def build(inp: DraftInputs, *, root: Path | None = None, python: str | None = None, instruction: str | None = None,
          scope_words: str = "", repo_root: Path | None = None, template: Path | None = None) -> Workspace:
    """Make the workspace. `instruction` switches to edit mode (design 7.4); `inp.edit_shots` is then the set of shot ids in scope."""
    import sys
    repo = Path(repo_root or REPO_ROOT)
    python = python or sys.executable
    mode = "edit" if instruction is not None else "draft"
    if not (inp.project_dir and Path(inp.project_dir).is_dir()):
        raise DraftError("project_missing", "the project folder is missing")
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix=PREFIX))
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("inputs/current", "images", "out", "look"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    bundle = R.load_bundle(inp.style)

    # pictures
    all_assets = dict(inp.picks["assets"])
    for k, a in ((inp.current or {}).get("assets") or {}).items():
        if isinstance(a, dict):
            all_assets[k] = a
    copies: dict = {}
    for k, a in all_assets.items():
        f = Path(inp.project_dir) / a["file"] if isinstance(a.get("file"), str) and a["file"] and ".." not in a["file"].replace("\\", "/").split("/") else None
        if a.get("kind") == "image" and f is not None and f.is_file():
            got = _copy_image(f, root / "images" / ("%s.jpg" % k))
            if got:
                copies[k] = got
    assets_doc = {}
    for k, a in all_assets.items():
        c = copies.get(k)
        rec = {"title": a.get("title"), "artist": a.get("artist"), "year": a.get("year"), "kind": a.get("kind"),
               "credit": a.get("credit"), "regions": (a.get("regions") or {})}
        if c:
            rec.update(file="images/%s.jpg" % k, source_size=[c[0], c[1]], image_size=[c[2], c[3]], scale=round(c[0] / float(c[2]), 4))
        else:
            rec.update(file=None, note="no picture file is available for this asset: do not use it")
        assets_doc[k] = rec
    _json(root / "inputs" / "assets.json", {"main_asset": inp.picks["main_asset"],
                                            "note": "All coordinates and region numbers are in SOURCE pixels. Multiply a position you measure on the copy by `scale`.",
                                            "assets": assets_doc})

    # words, beats, style, techniques
    _write(root / "inputs" / "words.tsv", "index\tword\tstart\tend\n" + "".join("%d\t%s\t%.3f\t%.3f\n" % (i, w["w"].replace("\t", " "), w["s"], w["e"]) for i, w in enumerate(inp.timing["words"])))
    _json(root / "inputs" / "beats.json", _beats_doc(inp))
    shutil.copyfile(bundle.dir / "style.json", root / "inputs" / "style.json")
    _write(root / "inputs" / "techniques.md", techniques_md.generate(bundle))

    # the saved storyboard as specs (re-draft, edit)
    scope_ids = set(inp.edit_shots) if inp.edit_shots is not None else None
    if inp.current:
        for cid, d in D.decompile(inp, scope_ids).items():
            if d["spec"]["shots"]:
                _json(root / "inputs" / "current" / ("%s.json" % cid), d["spec"])

    # what the helpers compile from
    current = copy.deepcopy(inp.current) if inp.current else None
    if current:
        current["assets"] = _rewrite_assets(current.get("assets") or {}, copies)
    picks = copy.deepcopy(inp.picks)
    picks["assets"] = _rewrite_assets(picks["assets"], copies)
    if picks["main_asset"] not in picks["assets"]:
        raise DraftError("main_asset_unreadable", "the main painting has no readable picture file")
    _json(root / "inputs" / "compile_input.json", {
        "schema": "bti.draft.input/1", "title": inp.title, "style": inp.style, "timing": inp.timing, "picks": picks, "current": current,
        "scope": inp.scope, "edit_shots": sorted(scope_ids) if scope_ids is not None else None, "reserved_ids": inp.reserved_ids,
        "mode": mode})

    cmds = _wrappers(root, python, repo)
    chapters = inp.in_scope()
    names = {c["id"]: c for c in inp.timing["chapters"]}
    values = {
        "CHECK_CMD": cmds["check"], "DEFAULTS_CMD": cmds["defaults"], "STILL_CMD": cmds["still"],
        "MAIN_ASSET": inp.picks["main_asset"], "N_WORDS": len(inp.timing["words"]), "DURATION": "%.0f" % inp.timing["duration"],
        "CHAPTER_LIST": "\n".join("- `%s` %s (words %d to %d, %.0f s to %.0f s)" % (c, names[c]["name"], names[c]["w0"], names[c]["w1"] - 1, names[c]["start"], names[c]["end"]) for c in chapters),
        "N_CHAPTERS": len(chapters), "REDRAFT": "yes" if inp.current else "no",
        "SCOPE_WORDS": scope_words or "the whole video",
        "INSTRUCTION": instruction or "",
    }
    tpl = Path(template or TEMPLATE)
    if not tpl.is_file():
        raise DraftError("template_missing", "skills/storyboard_draft/TASK.template.md is missing")
    _write(root / "TASK.md", render_template(tpl.read_text(encoding="utf-8"), mode, values))
    if instruction is not None:
        _write(root / "INSTRUCTION.md", "# The owner's instruction\n\n%s\n\n# Scope\n\n%s\n\nShots marked `in_scope: true` in inputs/current/ are the only ones you may change.\n"
               % (instruction, scope_words or "the whole video"))
    return Workspace(root=root, inputs=inp, mode=mode, scale={k: v[0] / float(v[2]) for k, v in copies.items()})


# ------------------------------------------------------------------------------------------- read back
def read_out(root: Path, chapters: list[str], assets: dict | None = None) -> OutResult:
    """Read `out/` and nothing else. A file that is a symbolic link, too big or not valid is reported, never followed."""
    out_dir = Path(root) / "out"
    res = OutResult()
    for cid in chapters:
        f = out_dir / ("%s.json" % cid)
        if f.is_symlink():
            res.problems.append(S.problem("spec_symlink", cid, None, "out/%s.json is a link; write a real file" % cid))
            continue
        if not f.exists():
            continue
        spec, probs = S.load_spec(f, cid)
        res.problems += probs
        if spec.get("shots"):
            res.specs[cid] = spec
        res.files.append(f.name)
    rf = out_dir / "regions.json"
    if rf.is_file() and not rf.is_symlink():
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            data = None
            res.problems.append(S.problem("regions_json", None, None, "out/regions.json is not valid JSON (%s)" % str(e)[:100]))
        res.regions, probs = S.regions_problems(data, assets or {})
        res.problems += probs
    nf = out_dir / "notes.md"
    if nf.is_file() and not nf.is_symlink():
        try:
            res.notes = nf.read_text(encoding="utf-8", errors="replace")[:NOTES_MAX]
        except OSError:
            pass
    return res


def load_workspace(root: Path) -> tuple[DraftInputs, dict]:
    """The inputs the helper commands compile from (project_dir = the workspace, whose images/ holds the copies)."""
    root = Path(root).resolve()
    f = root / "inputs" / "compile_input.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DraftError("workspace_invalid", "%s is not a draft workspace (inputs/compile_input.json is missing or unreadable)" % root.name)
    inp = DraftInputs(timing=d["timing"], picks=d["picks"], current=d.get("current"), title=d.get("title") or "", style=d.get("style") or "gae",
                      audio=None, project_dir=root, scope=d.get("scope"), reserved_ids=list(d.get("reserved_ids") or []),
                      edit_shots=set(d["edit_shots"]) if d.get("edit_shots") is not None else None, timing_file="timing.json")
    return inp, d


def workspace_compile(root: Path, *, draw: bool = True, engine=None):
    """Compile what the agent wrote in `out/` (what `check` prints). -> (CompileResult, OutResult)."""
    from .compile import compile_specs
    inp, _ = load_workspace(root)
    res = read_out(root, inp.in_scope(), inp.picks["assets"])
    from .engine import scaled_images
    assets = dict(inp.picks["assets"])
    assets.update((inp.current or {}).get("assets") or {})
    with scaled_images(Path(root), assets):
        out = compile_specs(inp, res.specs, regions=res.regions, spec_problems=res.problems, degrade=False, draw=draw, engine=engine)
    return out, res
