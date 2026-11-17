"""create_project: turn one or several catalogue entries (the same artwork in different books) into a project
folder `projects/<slug>/` with project.json and source/ text. Never overwrites, never writes a storyboard."""
from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

from . import catalogue, config, dossiers

PID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
STAGES = ["selected", "script", "voiced", "picked", "storyboard", "approved", "rendered"]


class ProjectError(ValueError):
    def __init__(self, msg: str, status: int = 422):
        super().__init__(msg)
        self.status = status


def make_slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", catalogue.norm(text).replace(" ", "-")).strip("-")
    return (s or "project")[:48].strip("-") or "project"


def parse_work_id(wid: str) -> tuple[str, int]:
    if not isinstance(wid, str) or not config.WORK_ID_RE.fullmatch(wid):
        raise ProjectError(f"invalid work id {wid!r}")
    bid, n = wid.split("/")
    if bid not in config.BOOK_BY_ID:
        raise ProjectError(f"unknown book {bid!r}", 404)
    return bid, int(n)


def create_project(work_ids: list[str] | None, slug: str | None = None, projects_root: Path | None = None,
                   artwork_key: str | None = None, exclude: list[str] | None = None) -> dict:
    """Project from an ARTWORK (`artwork_key`, minus the `exclude`d work ids) or from explicit `work_ids`.
    Writes project.json and source/ (a copy of the dossier and its body texts as they are now)."""
    root = Path(projects_root or config.PROJECTS_DIR)
    if artwork_key is not None:
        art = catalogue.load_artworks().get(artwork_key) if isinstance(artwork_key, str) else None
        if art is None:
            raise ProjectError(f"artwork {artwork_key!r} not found", 404)
        if work_ids:
            raise ProjectError("give artwork_key or work_ids, not both")
        if exclude is None:  # default: low-trust (machine-translated) sources are left out unless nothing else is left
            low = {w for w in art["works"] if catalogue.book_trust(w.split("/")[0])["trust"] == "low"}
            exclude = list(low) if len(low) < len(art["works"]) else []
        if not (isinstance(exclude, list) and all(isinstance(x, str) for x in exclude)):
            raise ProjectError("exclude must be a list of strings")
        excl = set(exclude)
        work_ids = [w for w in art["works"] if w not in excl]
    if not isinstance(work_ids, list) or not work_ids:
        raise ProjectError("work_ids must be a non-empty list")
    if not all(isinstance(w, str) for w in work_ids):
        raise ProjectError("work_ids must be a list of strings")
    if len(set(work_ids)) != len(work_ids):
        raise ProjectError("duplicate work ids")
    works = []
    for wid in work_ids:
        bid, n = parse_work_id(wid)
        w = catalogue.load_work(bid, n)
        if w is None:
            raise ProjectError(f"work {wid} not found", 404)
        works.append(w)
    books = [w["id"].split("/")[0] for w in works]
    if len(set(books)) != len(books):
        raise ProjectError("pick at most one entry per book")
    head = next((w for w in works if w.get("artist") and w.get("year")), next((w for w in works if w.get("artist")), works[0]))
    slug = slug or make_slug(head["title"])
    if not isinstance(slug, str) or not PID_RE.fullmatch(slug):
        raise ProjectError("slug must match [a-z0-9][a-z0-9_-]{0,63}")
    if slug.startswith(("lab_", "demo_")):
        raise ProjectError("slug may not start with lab_ or demo_")
    d = root / slug
    if d.exists():
        raise ProjectError(f"project {slug!r} already exists", 409)
    keys = [w.get("artwork_key") for w in works]
    key = artwork_key or keys[0]
    root.mkdir(parents=True, exist_ok=True)
    try:
        d.mkdir()                       # exclusive: of two simultaneous creates of one slug, one gets the folder, the other 409
    except FileExistsError:
        raise ProjectError(f"project {slug!r} already exists", 409)
    try:
        src = d / "source"
        tmp = d / ".dossier_tmp"
        doc = dossiers.build_one(key, {"works": [w["id"] for w in works]}, out_dir=tmp)
        src.mkdir()
        for s in doc["sources"]:
            base = Path(s["file"]).name
            shutil.copyfile(tmp / s["file"], src / base)
            s["file"] = base
        catalogue.write_json(src / "dossier.json", doc)
        shutil.rmtree(tmp)
        sources = [{"work_id": s["work_id"], "book_id": s["book_id"], "pdf_pages": s["pdf_pages"]}
                   for s in doc["sources"]]
        proj = {"id": slug, "title": doc["identity"]["title"] or head["title"],
                "artist": doc["identity"]["artist"], "year": doc["identity"]["year"],
                "stage": "selected", "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "sources": sources, "artwork_key": key, "dossier": "source/dossier.json",
                "library_dossier": f"library/dossiers/{key}/dossier.json"}
        if len(set(keys)) > 1:
            proj["mixed_artwork_keys"] = keys
        catalogue.write_json(d / "project.json", proj)
    except BaseException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return proj


def _safe_state(module: str, d: Path) -> dict:
    """`state(project_dir)` of a stage package, never raising: {"state": "none"|"running"|"stale"|"done", "detail": str, ...}."""
    try:
        import importlib
        out = importlib.import_module(module).state(d)
        if isinstance(out, dict) and out.get("state") in ("none", "running", "stale", "done"):
            return out
    except Exception:           # noqa: BLE001 - a stage that cannot answer must not break the home list
        pass
    return {"state": "none", "detail": ""}


def stage_states(d: Path) -> dict:
    """What each stage package says about the project, computed once and shared by the stage and the pipeline:
    {"voice": {...}, "picks": {...}, "export": {...}} (the draft's own state is not needed for steps or the stage)."""
    return {"voice": _safe_state("bti.voice", d), "picks": _safe_state("bti.picks", d), "export": _safe_state("bti.export", d)}


def infer_stage(d: Path, states: dict | None = None) -> str:
    """selected < script < voiced < picked < storyboard < approved < rendered: the furthest step for which every earlier step
    is done (design section 2).

    voiced   = the voice is fresh (`bti.voice.state` is done). A project that has `audio/` or `timing.json` but no voice manifest
               (an imported one) keeps its old meaning: those files are the voice.
    picked   = voiced and the picks approval is fresh.
    storyboard = a storyboard.json exists (an imported project has one without voice or picks: it still counts).
    approved = the storyboard approval names the current revision (a stale one leaves the stage at `storyboard`).
    rendered = a fresh export, or (old projects) a video file in render/, output/, out/ or the project folder."""
    import json
    st = states if states is not None else stage_states(d)
    stage = "selected"
    if any((d / n).is_file() for n in ("script.md", "script.txt", "script.json")):
        stage = "script"
    audio = d / "audio"
    legacy_voice = (d / "timing.json").is_file() or (audio.is_dir() and any(audio.iterdir()))
    has_manifest = (d / "voice" / "voice.json").is_file()
    voiced = st["voice"]["state"] == "done" or (legacy_voice and not has_manifest)
    if voiced:
        stage = "voiced"
        if st["picks"]["state"] == "done":
            stage = "picked"
    sbf = d / "storyboard.json"
    if sbf.is_file():
        stage = "storyboard"
        try:
            from bti.editor.common import storyboard_approval      # the ONE rule: an approval counts only for the current revision
            if storyboard_approval(json.loads(sbf.read_text(encoding="utf-8"))) == "fresh":
                stage = "approved"
        except Exception:
            pass
        for sub in ("render", "output", "out"):
            p = d / sub
            if p.is_dir() and any(p.glob("*.mp4")):
                stage = "rendered"
        if any(d.glob("*.mp4")) or st["export"]["state"] == "done":
            stage = "rendered"
    return stage
