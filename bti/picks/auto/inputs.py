"""What the automatic picks job reads before it starts (all of it files; no model, no network): the narration lines, the dossier's facts,
the main painting and the picks document as it stands. The refusals of the start route are raised here, as `AutoError`, so that the
route and the plain function an other worker calls give the same answer."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from bti.picks import context, doc

from . import shapes

MAX_LINES = 150
BEAT_RE = doc.BEAT_ID_RE


class AutoError(Exception):
    """A refusal: `code` is the stable word (its sentence is in texts.VI and in errmsg.js), `status` the HTTP status."""

    def __init__(self, code: str, message: str, status: int = 409, **extra):
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra


@dataclass
class Painting:
    key: str
    file: Path
    title: str
    artist: str
    year: str
    width: int                       # pixels of the stored file (what regions are measured in)
    height: int
    regions: dict = field(default_factory=dict)       # NAME -> {"box": [x0, y0, x1, y1], "label": str, "tight": bool, "thing": str, "rough": ..., "raw": dict}
    content_box: dict | None = None


@dataclass
class Inputs:
    pdir: Path
    identity: dict
    details: list
    facts: dict
    chapters: list                   # [{id, title, role, beats: [{id, text, show, facts}]}]
    beats: list                      # every line in narration order: {id, no, chapter, text, show, facts, words, seconds}
    picks: dict
    painting: Painting
    targets: list
    narration_rev: str
    owner_note: str = ""
    redo: bool = False
    requested: list = field(default_factory=list)      # the lines the request covers (all of them, or the ones it names): what a resumed run is matched on
    limited: bool = False

    def beat(self, bid: str) -> dict:
        return next(b for b in self.beats if b["id"] == bid)

    def plan_ctx(self) -> shapes.PlanCtx:
        return shapes.PlanCtx(beats=[{"id": b["id"], "chapter": b["chapter"], "words": b["words"]} for b in self.beats], targets=list(self.targets),
                              existing_regions={n: r["box"] for n, r in self.painting.regions.items()},
                              painting_title=self.painting.title, existing_names=list(self.picks.get("names") or []), existing_subjects=list(self.picks.get("subjects") or []), require_names=True, line_texts={b["id"]: b["text"] for b in self.beats})


def has_pictures(picks: dict, bid: str) -> bool:
    """A line that is settled: it has pictures, or the owner (or an earlier run) said it needs none."""
    b = picks["beats"].get(bid)
    return bool(b and (b["items"] or b["status"] == "skip"))


def _main(pdir: Path, picks: dict) -> Painting:
    from bti.media import contentbox as pcb
    key = picks.get("main_asset")
    a = picks["assets"].get(key) if key else None
    if not a:
        raise AutoError("picks_no_main", "no main painting is chosen: choose it first (picks.import with as_main)")
    f = Path(pdir) / a["file"]
    if a.get("kind") == "video" or not f.is_file() or int(a.get("width") or 0) <= 0 or int(a.get("height") or 0) <= 0:
        raise AutoError("main_asset_unreadable", "the main painting has no readable picture file")
    w, h = int(a["width"]), int(a["height"])
    a_copy = dict(a)
    pcb.ensure(a_copy, pdir)
    cbox = pcb.box_of(a_copy)
    regions = {}
    for name, r in (a.get("regions") or {}).items():
        box = shapes.region_to_box(r, w, h)
        if box is not None:
            regions[name] = {"box": box, "label": str(r.get("label") or ""), "tight": r.get("tight") is True,
                             "thing": str(r.get("thing") or ""), "rough": r.get("rough"), "raw": dict(r)}
    return Painting(key, f, str(a.get("title") or ""), str(a.get("artist") or ""), str(a.get("year") or ""), w, h, regions, content_box=cbox)


def load(pdir: Path, requested: list | None = None, *, redo: bool = False, owner_note: str = "", need_targets: bool = True) -> Inputs:
    """Read the project and decide which lines the job works on. `requested`: the lines the caller names (None: all of them).
    A line that already has pictures (or is skipped) is left alone unless `redo`. Raises `AutoError`."""
    pdir = Path(pdir)
    nv = context.narration_view(pdir)
    if not nv["present"] or not nv["approved"]:
        raise AutoError("narration_not_approved", "the narration is not approved (or changed): approve it first")
    picks = doc.load_or_new(pdir)
    painting = _main(pdir, picks)
    ids = nv["beat_ids"]
    if requested is not None:
        if not (isinstance(requested, list) and requested and all(isinstance(b, str) for b in requested)):
            raise AutoError("invalid", "beats must be a list of narration line ids, or null for all of them", 422)
        for b in requested:
            if b not in ids:
                raise AutoError("not_found", "line %s is not in the narration" % str(b)[:20], 404)
        wanted = list(dict.fromkeys(requested))
    else:
        wanted = list(ids)
    approved = doc.approval_state(picks, nv["rev"], nv["approved"])["approved"]
    if approved and not redo:
        raise AutoError("picks_approved", "the picks are approved: send redo true to let the agent choose again (the approval is then dropped)")
    targets = [b for b in ids if b in set(wanted) and (redo or not has_pictures(picks, b))]
    if need_targets and not targets:
        raise AutoError("picks_nothing_to_do", "every line already has pictures: send redo true to choose them again")
    if len(targets) > MAX_LINES:
        raise AutoError("too_many", "this would be %d lines: name at most %d of them in `beats` (a chapter at a time)" % (len(targets), MAX_LINES), 422)
    beats, no = [], 0
    chapters = []
    for c in nv["chapters"]:
        rows = []
        for b in c["beats"]:
            no += 1
            words = len(re.findall(r"\S+", b["text"]))
            beats.append({"id": b["id"], "no": no, "chapter": c["id"], "text": b["text"], "show": list(b["show"]), "facts": list(b["facts"]),
                          "words": words, "seconds": round(words / shapes.WORDS_PER_SECOND, 1)})
            rows.append(beats[-1])
        chapters.append({"id": c["id"], "title": c["title"], "role": c["role"], "beats": rows})
    ident = context.identity(pdir)
    return Inputs(pdir=pdir, identity=ident, details=context.details(pdir), facts=dict(nv["facts"]), chapters=chapters, beats=beats, picks=picks,
                  painting=painting, targets=targets, narration_rev=nv["rev"], owner_note=(owner_note or "").strip()[:1000], redo=bool(redo),
                  requested=sorted(wanted), limited=requested is not None)
