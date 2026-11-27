"""The model's factual music-placement inputs, built from existing project files."""
from __future__ import annotations

import math
from pathlib import Path

from bti.editor.common import read_json
from bti.engine.timing import Timing
from bti.picks import context
from . import library
from .document import MusicError
from .export import landmarks


def pauses(words, minimum=1.2):
    out = []
    for a, b in zip(words, words[1:]):
        end, start = a.get("e"), b.get("s")
        if isinstance(end, (float, int)) and not isinstance(end, bool) and isinstance(start, (float, int)) and not isinstance(start, bool) and math.isfinite(end) and math.isfinite(start) and start - end >= minimum:
            out.append({"start": round(end, 4), "end": round(start, 4), "duration": round(start - end, 4)})
    return out


def load(pdir, *, need_library=True):
    pdir = Path(pdir)
    try:
        sb = read_json(pdir / "storyboard.json")
        timing = Timing.load(pdir / "timing.json")
        duration = timing.resolve(sb["end"])
        marks = landmarks(sb, timing)
        rows = {key: {**row, "character": row.get("character") or row.get("forces") or "unknown"}
                for key, row in library.index().items()}
        if need_library and not rows:
            raise MusicError("the music library is empty")
        project = context.project_json(pdir)
        dossier = context.dossier(pdir)
        identity = context.identity(pdir)
        raw_identity = dossier.get("identity") if isinstance(dossier.get("identity"), dict) else {}
        identity["place"] = str(raw_identity.get("place") or project.get("place") or "")
        chapters = []
        for chapter in timing.chapters:
            if not isinstance(chapter, dict):
                continue
            ident = chapter.get("id")
            chapters.append({"id": ident, "title": chapter.get("name"), "start": chapter.get("start"), "end": chapter.get("end"),
                             "lines": [b for b in timing.beats if isinstance(b, dict) and b.get("chapter") == ident]})
        return {"painting": identity, "narration": chapters, "timing": timing.data, "storyboard": sb, "duration": duration,
                "landmarks": marks, "pauses": pauses(timing.words), "library": rows}
    except MusicError:
        raise
    except Exception as exc:
        raise MusicError("storyboard, timing or project inputs cannot be read: %s" % exc) from exc
