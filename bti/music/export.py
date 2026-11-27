"""Resolve music cues and collect their source signatures for an export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bti.editor.common import file_signature
from bti.engine.timing import Timing
from . import library, store
from .document import MusicError, validate


def recording_path(root, row):
    name = row.get("file")
    if not isinstance(name, str) or not name or name in (".", "..") or "/" in name or "\\" in name or ":" in name:
        raise MusicError("recording file must be a single filename")
    root = Path(root).resolve()
    path = root / name
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise MusicError("recording file is missing or outside the music library")
    return path


def signature(project_dir):
    doc = store.read(project_dir)
    if doc is None:
        return None
    rows = library.index()
    root = library.directory()
    used = sorted({c.get("recording") for c in doc.get("cues", []) if isinstance(c, dict) and isinstance(c.get("recording"), str)})
    sources = []
    for ident in used:
        row = rows.get(ident)
        if not row:
            raise MusicError("recording is not in the library")
        path = recording_path(root, row)
        sources.append([row, file_signature(path)])
    payload = json.dumps([doc, sources], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def landmarks(storyboard, timing):
    chapters = [c.get("start") for c in timing.chapters if isinstance(c, dict)]
    answer = {"chapters": chapters}
    for shot in storyboard.get("shots", []):
        tech = str(shot.get("technique", ""))
        if tech == "X-CARD-02" or tech.startswith("ID-BRAND-"):
            answer["ident"] = timing.resolve(shot.get("start"))
            break
    return answer


def prepare(project_dir, timing_data, storyboard, duration):
    doc = store.read(project_dir)
    if doc is None:
        return None
    rows = library.index()
    timing = Timing(timing_data)
    cues = validate(doc, rows, timing, duration, landmarks(storyboard, timing))
    root = library.directory()
    from .inputs import pauses
    gaps = pauses(timing.words)
    words = [w for w in timing.words if isinstance(w, dict) and isinstance(w.get("s"), (int, float))
             and isinstance(w.get("e"), (int, float)) and w["e"] > w["s"]]
    last_word = max((w["e"] for w in words), default=duration)
    speech = []
    if words:
        start = words[0]["s"]
        for gap in gaps:
            if gap["start"] > start:
                speech.append([start, gap["start"]])
            start = gap["end"]
        if last_word > start:
            speech.append([start, last_word])
    paths = []
    credits = []
    seen = set()
    for cue in cues:
        row = rows[cue["recording"]]
        if row.get("license") not in ("CC0", "Public domain"):
            raise MusicError("recording licence is not CC0 or public domain")
        paths.append((recording_path(root, row), {**cue, "pauses": gaps, "voice_end": last_word, "speech": speech}))
        if cue["recording"] not in seen:
            seen.add(cue["recording"])
            title = str(row.get("title") or "").strip()
            composer = str(row.get("composer") or "").strip()
            performer = str(row.get("performer") or "").strip()
            credit = title + (" — " + composer if composer else "")
            if performer and performer.casefold() not in {composer.casefold(), composer.split()[-1].casefold() if composer else ""}:
                credit += "; performed by " + performer
            credits.append("%s (%s)" % (credit, row["license"]))
    return {"cues": paths, "credits": credits, "signature": signature(project_dir)}
