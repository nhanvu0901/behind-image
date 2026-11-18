"""The fast path's draw check: draw only what an edit can have affected (contract A2, "a draw check of the changed shots only").

The engine's `Project.draw_check` draws three frames of EVERY shot (82 shots: about 8 seconds on the server). A two-shot edit needs the
frames of the shots it changed or added, of any shot whose start or effective end moved (the shot list around a replaced range), and
the transition into the shot that follows a drawn shot (that transition shows the drawn shot's last frames). Everything else is
byte-for-byte what was saved and already draws. The frame times are the engine's (`draw_check_iter`): just inside the start, the
middle, just inside the end, the middle of the transition in, the middle of every overlay; frames closer than one frame are drawn once.

`draw_changed` returns a `DrawReport` that also lists the frames it drew, so a test can prove that no other shot was drawn."""
from __future__ import annotations

import concurrent.futures
import json
from dataclasses import dataclass, field
from pathlib import Path

from bti.engine.api import RenderError, _default_check_threads
from bti.engine.errors import DataError
from bti.engine.timing import Timing

from .decompile import resolve_shots
from .engine import DraftProject
from .inputs import DraftInputs

EPS_T = 1e-4
FRAME = 1 / 15.0


@dataclass
class DrawReport:
    issues: list = field(default_factory=list)
    frames: list = field(default_factory=list)      # (shot id, path, time) of every frame drawn
    shots: set = field(default_factory=set)         # shot ids with at least one frame drawn
    full: set = field(default_factory=set)          # the shots drawn completely
    transition_only: set = field(default_factory=set)


def _canon(shot: dict) -> str:
    return json.dumps({k: v for k, v in shot.items() if not str(k).startswith("_")}, sort_keys=True, ensure_ascii=False)


def affected_shots(inp: DraftInputs, new_sb: dict) -> tuple[set[str], set[str]]:
    """(shots to draw completely, shots of which only the transition in is drawn), by id, for `new_sb` against the saved storyboard."""
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    dur = inp.timing["duration"]
    old = {rc["shot"]["id"]: (_canon(rc["shot"]), rc["t0"], rc["t1"]) for rc in resolve_shots(inp.current, tm, dur)
           if isinstance(rc["shot"].get("id"), str)}
    new = [rc for rc in resolve_shots(new_sb, tm, dur) if isinstance(rc["shot"].get("id"), str)]
    full: set[str] = set()
    for rc in new:
        sid = rc["shot"]["id"]
        o = old.get(sid)
        if o is None or o[0] != _canon(rc["shot"]) or abs(o[1] - rc["t0"]) > EPS_T or abs(o[2] - rc["t1"]) > EPS_T:
            full.add(sid)
    trans: set[str] = set()
    for a, b in zip(new, new[1:]):
        nid = b["shot"]["id"]
        if a["shot"]["id"] in full and nid not in full and isinstance(b["shot"].get("transition_in"), dict):
            trans.add(nid)
    return full, trans


def draw_changed(inp: DraftInputs, new_sb: dict, *, threads: int | None = None, width: int = 320) -> DrawReport:
    """Draw check of `new_sb` for the shots the edit can have affected. A failure of a technique is an issue
    `{"level": "error", "code": "undrawable", "path", "shot", "message"}`, as the engine reports it."""
    full, trans = affected_shots(inp, new_sb)
    rep = DrawReport(full=full, transition_only=trans)
    if not (full or trans) or not inp.project_dir:
        return rep
    issues: list[dict] = []
    seen: set = set()

    def fail(path, shot_id, message, technique=None, overlay=None, asset=None):
        if (path, message) not in seen:
            seen.add((path, message))
            issues.append({"level": "error", "code": "undrawable", "path": path, "shot": shot_id, "message": message,
                           "args": {"shot": shot_id, "technique": technique, "overlay": overlay, "asset": asset}})

    eng = DraftProject(inp.project_dir, new_sb, inp.timing)
    try:
        saved = eng._draft
        try:
            eng.use_draft(new_sb)
            scene = eng._scene()
        except RenderError as e:
            fail(e.path or "", e.shot, e.message, e.technique, e.overlay, getattr(e, "asset", None))
            rep.issues = issues
            return rep
        except DataError as e:
            fail("", None, e.message)
            rep.issues = issues
            return rep
        except Exception:      # noqa: BLE001
            fail("", None, "the storyboard cannot be compiled")
            rep.issues = issues
            return rep
        finally:
            eng._draft = saved

        jobs = []
        for i, c in enumerate(scene.shots):
            sid = c.shot.get("id") if isinstance(c.shot.get("id"), str) else None
            if sid not in full and sid not in trans:
                continue
            t0, t1 = c.t0, c.t1
            if t0 is None or t1 is None:
                continue
            eps = min(0.05, (t1 - t0) / 10)
            times = []
            if sid in full:
                times += [("shots[%d]" % i, t0 + eps), ("shots[%d]" % i, (t0 + t1) / 2), ("shots[%d]" % i, t1 - eps)]
            tr = c.shot.get("transition_in")
            if c.transition is not None and i > 0 and isinstance(tr, dict) and c.transition.dur > 0:
                times.append(("shots[%d].transition_in" % i, t0 + c.transition.dur / 2))
            if sid in full:
                for j, o in enumerate(c.shot.get("overlays") or []):
                    ot0, ot1 = o.get("_t0"), o.get("_t1")
                    if ot0 is not None and ot1 is not None:
                        times.append(("shots[%d].overlays[%d]" % (i, j), (ot0 + ot1) / 2))
            drawn: list = []
            for path, t in times:
                if any(abs(t - d) < FRAME for d in drawn):
                    continue
                drawn.append(t)
                jobs.append((len(jobs), path, sid, i, t))

        def draw_job(job):
            idx, path, sid, i, t = job
            try:
                scene.frame_at(t, int(width))
                return None
            except RenderError as e:
                return (idx, e.path or path, e.shot or sid, e.message, e.technique, e.overlay, getattr(e, "asset", None))
            except Exception:      # noqa: BLE001
                return (idx, path, sid, "shot %s cannot be drawn" % (sid or i), None, None, None)

        rep.frames = [(j[2], j[1], j[4]) for j in jobs]
        rep.shots = {j[2] for j in jobs}
        n = max(1, int(threads if threads is not None else _default_check_threads()))
        if n == 1 or len(jobs) <= 1:
            results = [draw_job(j) for j in jobs]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
                results = list(ex.map(draw_job, jobs))
        for r in results:
            if r is not None:
                fail(*r[1:])
    finally:
        eng.close()
    rep.issues = issues
    return rep
