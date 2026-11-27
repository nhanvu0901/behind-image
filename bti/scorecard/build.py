"""Orchestration: build, save, and load `project_dir/scorecard/`."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bti.output import facts as F
from bti.output import fsutil

from . import audio as A
from . import metrics as M
from . import record as R
from . import render as RD
from . import sheets as SH


def scorecard_dir(project_dir: Path) -> Path:
    return Path(project_dir) / "scorecard"


def load_scorecard(project_dir: Path) -> dict | None:
    doc = fsutil.read_json(scorecard_dir(project_dir) / "scorecard.json")
    return doc if isinstance(doc, dict) and doc.get("schema") == M.SCHEMA else None


def load_record(project_dir: Path) -> dict | None:
    doc = fsutil.read_json(scorecard_dir(project_dir) / "record.json")
    return doc if isinstance(doc, dict) and doc.get("schema") == R.RECORD_SCHEMA else None


def _current_revs(project_dir: Path) -> tuple[str | None, str | None]:
    pdir = Path(project_dir)
    sb_rev = None
    try:
        from bti.editor.common import compute_rev, read_json
        sb = read_json(pdir / "storyboard.json")
        if isinstance(sb, dict):
            sb_rev = compute_rev(sb)
    except (OSError, ValueError):
        pass
    exp_rev = None
    vpath, manifest = A.find_exported_video(pdir)
    if vpath is not None and manifest is not None:
        from bti.output import parts as P
        exp_rev = P.sha(manifest.get("storyboard_rev"), manifest.get("audio_sig"), manifest.get("created"))
    return sb_rev, exp_rev


def is_stale(project_dir: Path, sc: dict | None) -> bool:
    if sc is None:
        return True
    sb_rev, exp_rev = _current_revs(project_dir)
    return sc.get("storyboard_rev") != sb_rev or sc.get("export_rev") != exp_rev


def make_for_project(
    project_dir: Path,
    *,
    tools: Any = None,
    loudness: dict | None = None,
    sheets: bool = True,
    engine_project: Any = None,
    style_root: Path | None = None,
    repo_root: Path | None = None,
) -> dict:
    """Compute metrics, audio checks, contact sheets, and render record; write atomically to `project_dir/scorecard/`."""
    pdir = Path(project_dir)
    sdir = scorecard_dir(pdir)
    fsutil.ensure_dir(sdir)
    f = F.collect(pdir)
    if f.sb is None:
        raise ValueError("storyboard.json is missing or unreadable")

    sb_rev = f.sb_rev
    vpath, manifest = A.find_exported_video(pdir)
    exported = vpath is not None and manifest is not None
    exp_rev = None
    if exported and manifest is not None:
        from bti.output import parts as P
        exp_rev = P.sha(manifest.get("storyboard_rev"), manifest.get("audio_sig"), manifest.get("created"))
    if loudness is None and exported and manifest is not None:
        loudness = manifest.get("loudness")
    audio_info = A.measure_export_audio(vpath, f.timing, tools=tools, loudness=loudness) if (exported or loudness is not None) else None

    sc = M.compute_metrics(
        pdir,
        sb=f.sb,
        picks=f.picks,
        timing=f.timing,
        audio=audio_info,
        exported=exported,
        storyboard_rev=sb_rev,
        export_rev=exp_rev,
        style_root=style_root,
    )

    sheet_entries: list[dict] = []
    sheet_source: str | None = None
    sheets_error: str | None = None
    if sheets:
        try:
            sheet_entries, sheet_source = SH.render_sheets(
                pdir,
                sdir / "sheets",
                video_path=vpath if exported else None,
                tools=tools,
                engine_project=engine_project,
                title=f.title or f.pid,
            )
        except Exception as exc:     # noqa: BLE001 - metrics and record still save if frame rendering fails
            sheets_error = "%s: %s" % (type(exc).__name__, str(exc)[:180])
    sc["sheets"] = sheet_entries
    sc["sheet_source"] = sheet_source
    if sheets_error:
        sc["sheets_error"] = sheets_error

    rec = R.build_record(pdir, sc, facts=f, repo_root=repo_root)
    fsutil.write_json(sdir / "scorecard.json", sc)
    fsutil.write_text(sdir / "scorecard.md", RD.scorecard_md(sc, title=f.title or f.pid))
    fsutil.write_json(sdir / "record.json", rec)
    fsutil.write_text(sdir / "record.md", RD.record_md(rec))
    return {"scorecard": sc, "record": rec, "sheets": sheet_entries, "dir": str(sdir)}
