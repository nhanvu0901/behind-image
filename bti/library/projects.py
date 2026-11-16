"""create_project: turn one or several catalogue entries (the same artwork in different books) into a project
folder `projects/<slug>/` with project.json and source/ text. Never overwrites, never writes a storyboard."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from . import catalogue, config, extract

PID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
STAGES = ["selected", "script", "voiced", "storyboard", "approved", "rendered"]


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


def create_project(work_ids: list[str], slug: str | None = None, projects_root: Path | None = None) -> dict:
    root = Path(projects_root or config.PROJECTS_DIR)
    if not isinstance(work_ids, list) or not work_ids:
        raise ProjectError("work_ids must be a non-empty list")
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
    d.mkdir(parents=True)
    try:
        src = d / "source"
        src.mkdir()
        sources = []
        for w in works:
            bid = w["id"].split("/")[0]
            t = extract.work_text(w)
            base = f"{bid}_{w['n']:03d}"
            (src / f"{base}.txt").write_text(t["text"] + "\n", encoding="utf-8")
            catalogue.write_json(src / f"{base}.json", {
                "work_id": w["id"], "book_id": bid, "title": w["title"], "artist": w.get("artist"),
                "year": w.get("year"), "pdf_pages": w["pdf_pages"], "ocr": t["ocr"],
                "text_source": t["text_source"], "words": len(t["text"].split()),
                "note": "Trích từ sách có bản quyền, chỉ dùng nội bộ để nghiên cứu."})
            sources.append({"work_id": w["id"], "book_id": bid, "pdf_pages": w["pdf_pages"]})
        proj = {"id": slug, "title": head["title"], "artist": head.get("artist"), "year": head.get("year"),
                "stage": "selected", "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "sources": sources, "artwork_key": keys[0]}
        if len(set(keys)) > 1:
            proj["mixed_artwork_keys"] = keys
        catalogue.write_json(d / "project.json", proj)
    except BaseException:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
        raise
    return proj


def infer_stage(d: Path) -> str:
    """selected < script < voiced < storyboard < approved < rendered, from which files exist."""
    import json
    stage = "selected"
    if any((d / n).is_file() for n in ("script.md", "script.txt", "script.json")):
        stage = "script"
    audio = d / "audio"
    if (d / "timing.json").is_file() or (audio.is_dir() and any(audio.iterdir())):
        stage = "voiced"
    sbf = d / "storyboard.json"
    if sbf.is_file():
        stage = "storyboard"
        try:
            appr = (json.loads(sbf.read_text(encoding="utf-8")).get("approvals") or {}).get("storyboard")
            if appr:
                stage = "approved"
        except Exception:
            pass
        for sub in ("render", "output", "out"):
            p = d / sub
            if p.is_dir() and any(p.glob("*.mp4")):
                stage = "rendered"
        if any(d.glob("*.mp4")):
            stage = "rendered"
    return stage
