"""Engine facade (design section 8.1). Everything the editor backend needs; nothing else is public API.

    p = open_project(Path("projects/arnolfini"))
    p.frame_at(12.5, width=960)        # BGR uint8 ndarray
    p.render_range(10, 20, Path("out.mp4"))
    issues = p.validate(draft); rev = p.save(draft)

Extra helpers beyond the design (backwards compatible): `Project.revision()`, `Project.dir`, `Project.technique_available(id)`.
A Project is safe to keep alive in a long-running process (LRU image cache, size- and font-keyed layer caches) but is not
thread-safe: callers serialise access (the backend holds a lock).
"""
from __future__ import annotations

import copy
import logging
from collections import OrderedDict
from pathlib import Path

import numpy as np

from . import registry as R
from . import storyboard as SB
from .errors import DataError, RenderError
from .scene import Scene
from .timing import Timing

__all__ = ["open_project", "Project", "load_style", "ValidationError", "RenderError"]
ValidationError = SB.ValidationError
log = logging.getLogger("bti.engine")


def load_style(style_id: str) -> dict:
    """{"style": style.json, "techniques": [...], "intents": [...]}; FileNotFoundError for an unknown style."""
    b = R.load_bundle(style_id)
    return {"style": copy.deepcopy(b.style), "techniques": copy.deepcopy(b.techniques), "intents": list(SB.INTENTS)}


def open_project(project_dir: Path) -> "Project":
    return Project(Path(project_dir))


class Project:
    def __init__(self, project_dir: Path):
        self.dir = Path(project_dir)
        if not (self.dir / "storyboard.json").exists():
            raise FileNotFoundError(self.dir / "storyboard.json")
        self._saved = SB.load(self.dir)
        self._saved_mtime = (self.dir / "storyboard.json").stat().st_mtime_ns
        self._draft = None
        self._scenes: OrderedDict = OrderedDict()
        self._timings: dict = {}            # relative path -> (mtime_ns, Timing)

    # -- documents -------------------------------------------------------------------------------------------
    @property
    def bundle(self) -> R.StyleBundle:
        return R.load_bundle(self._saved.get("style", "gae"))

    def _reload_if_changed(self):
        mt = (self.dir / "storyboard.json").stat().st_mtime_ns
        if mt != self._saved_mtime:
            self._saved, self._saved_mtime = SB.load(self.dir), mt

    def storyboard(self) -> dict:
        self._reload_if_changed()
        return copy.deepcopy(self._saved)

    def _timing_for(self, sb) -> Timing:
        """The timing file named by document `sb` (default timing.json): inside the project, present, well formed.
        Any problem is a DataError that names it. Parsed files are cached by modification time."""
        rel = sb.get("timing") if isinstance(sb, dict) else None
        if rel is None or rel == "":
            rel = "timing.json"
        if not isinstance(rel, str):
            raise DataError("timing must be a file path inside the project", what="timing")
        path = SB.safe_rel(self.dir, rel)
        if path is None:
            raise DataError("timing %r must be a file inside the project" % rel, what="timing")
        try:
            mt = path.stat().st_mtime_ns
        except OSError:
            raise DataError("%s is missing" % rel, what="timing")
        hit = self._timings.get(rel)
        if hit is None or hit[0] != mt:
            tm = Timing.load(path)
            self._timings[rel] = hit = (mt, tm)
            self._scenes.clear()
        return hit[1]

    def _tm(self) -> Timing:
        self._reload_if_changed()
        return self._timing_for(self._saved)

    def timing(self) -> dict:
        return copy.deepcopy(self._tm().data)

    def revision(self) -> str:
        """Revision (sha256 of the canonical JSON) of the saved storyboard."""
        self._reload_if_changed()
        return SB.revision_of(self._saved)

    def technique_available(self, technique_id: str) -> bool:
        return self.bundle.available(technique_id)

    # -- resolve / validate ----------------------------------------------------------------------------------
    def resolve(self, storyboard: dict | None = None) -> dict:
        sb = storyboard if storyboard is not None else self.storyboard()
        return SB.resolve(sb, self._timing_for(sb), self._bundle_for(sb))

    def _bundle_for(self, sb) -> R.StyleBundle:
        style = sb.get("style", "gae") if isinstance(sb, dict) else "gae"
        return R.load_bundle(style)

    def validate(self, storyboard: dict | None = None) -> list[dict]:
        """Issues of `storyboard` (default: the saved one). Everything a later load needs is checked here: the style exists,
        the timing file is inside the project and readable, audio and asset files stay inside the project."""
        sb = storyboard if storyboard is not None else self.storyboard()
        if not isinstance(sb, dict):
            return SB.validate(sb, None, None, self.dir)
        issues: list[dict] = []
        try:
            bundle = self._bundle_for(sb)
        except DataError as e:
            issues.append({"level": "error", "path": "style", "code": "style_unusable", "args": {"style": sb.get("style")}, "message": e.message})
            try:
                bundle = self.bundle
            except DataError:
                bundle = R.load_bundle("gae")
        try:
            tm = self._timing_for(sb)
        except DataError as e:
            issues.append({"level": "error", "path": "timing", "code": "timing_unusable", "args": {"file": sb.get("timing")}, "message": e.message})
            tm = Timing({"duration": 0.0, "words": []})
        return issues + SB.validate(sb, tm, bundle, self.dir)

    def use_draft(self, storyboard: dict | None) -> None:
        self._draft = copy.deepcopy(storyboard) if storyboard is not None else None

    # -- rendering -------------------------------------------------------------------------------------------
    def _scene(self) -> Scene:
        self._reload_if_changed()
        sb = self._draft if self._draft is not None else self._saved
        tm, bundle = self._timing_for(sb), self._bundle_for(sb)
        key = (SB.revision_of(sb), self._draft is not None)
        sc = self._scenes.get(key)
        if sc is None:
            sc = Scene(self.dir, SB.resolve(sb, tm, bundle), tm, bundle)
            self._scenes[key] = sc
            while len(self._scenes) > 4:
                self._scenes.popitem(last=False)
        else:
            self._scenes.move_to_end(key)
        return sc

    def frame_at(self, t: float, width: int = 960) -> np.ndarray:
        """BGR uint8 frame, 16:9, `width` px wide."""
        return self._scene().frame_at(float(t), int(width))

    def render_range(self, t0: float, t1: float, out_path: Path, width: int = 640, fps: int = 15, on_progress=None, quality: str = "preview", threads: int | None = None) -> Path:
        """Silent H.264 of [t0, t1) written to out_path."""
        return self._scene().render_range(float(t0), float(t1), Path(out_path), int(width), int(fps), on_progress, quality, threads)

    def draw_check(self, storyboard: dict | None = None, width: int = 320) -> list[dict]:
        """The whole check in one call (see `draw_check_iter` for the step by step form)."""
        it = self.draw_check_iter(storyboard, width)
        while True:
            try:
                next(it)
            except StopIteration as done:
                return done.value

    def draw_check_iter(self, storyboard: dict | None = None, width: int = 320):
        """Generator form of `draw_check`: yields after the storyboard is compiled and after every drawn sample, and RETURNS the
        issues (`StopIteration.value`). A caller that holds a lock may release it between two `next()` calls: the draft is swapped
        in only while the storyboard is compiled (inside the first step, restored before that step yields); the samples are drawn
        from the compiled scene, which does not depend on the project's draft state.

        Draws three small frames (just inside the start, the middle, just inside the end) of every shot, one inside every overlay's
        span and one in the middle of every transition; the failures are issues
        `{"level": "error", "code": "undrawable", "path", "shot", "message"}`. Never raises for a technique failure and leaves
        the project's draft state as the caller had it."""
        issues: list[dict] = []
        seen: set = set()

        def fail(path, shot_id, message, technique=None, overlay=None, asset=None):
            if (path, message) not in seen:
                seen.add((path, message))
                issues.append({"level": "error", "code": "undrawable", "path": path, "shot": shot_id, "message": message,
                               "args": {"shot": shot_id, "technique": technique, "overlay": overlay, "asset": asset}})

        saved_draft = self._draft
        try:
            if storyboard is not None:
                self.use_draft(storyboard)
            scene = self._scene()
        except RenderError as e:
            fail(e.path or "", e.shot, e.message, e.technique, e.overlay, getattr(e, "asset", None))
            return issues
        except DataError as e:
            fail("", None, e.message)
            return issues
        except Exception as e:      # noqa: BLE001
            log.warning("draw_check: the storyboard cannot be compiled", exc_info=e)
            fail("", None, "the storyboard cannot be compiled")
            return issues
        finally:
            self._draft = saved_draft
        yield
        frame = 1 / 15.0
        for i, c in enumerate(scene.shots):
            sid = c.shot.get("id") if isinstance(c.shot.get("id"), str) else None
            t0, t1 = c.t0, c.t1
            if t0 is None or t1 is None:
                continue
            eps = min(0.05, (t1 - t0) / 10)            # just inside the shot: a camera move needs its largest buffer at an end
            times = [("shots[%d]" % i, t0 + eps), ("shots[%d]" % i, (t0 + t1) / 2), ("shots[%d]" % i, t1 - eps)]
            tr = c.shot.get("transition_in")
            if c.transition is not None and i > 0 and isinstance(tr, dict) and c.transition.dur > 0:
                times.append(("shots[%d].transition_in" % i, t0 + c.transition.dur / 2))
            for j, o in enumerate(c.shot.get("overlays") or []):
                ot0, ot1 = o.get("_t0"), o.get("_t1")
                if ot0 is None or ot1 is None:
                    continue
                times.append(("shots[%d].overlays[%d]" % (i, j), (ot0 + ot1) / 2))
            drawn: list = []
            for path, t in times:
                if any(abs(t - d) < frame for d in drawn):
                    continue            # closer than one frame to a frame already drawn
                drawn.append(t)
                try:
                    scene.frame_at(t, int(width))
                except RenderError as e:
                    fail(e.path or path, e.shot or sid, e.message, e.technique, e.overlay, getattr(e, "asset", None))
                except Exception as e:      # noqa: BLE001
                    log.warning("draw_check: %s cannot be drawn", path, exc_info=e)
                    fail(path, sid, "shot %s cannot be drawn" % (sid or i))
                yield
        return issues

    # -- editing support -------------------------------------------------------------------------------------
    def _asset_info(self, key: str, sb: dict) -> dict | None:
        a = (sb.get("assets") or {}).get(key)
        if not isinstance(a, dict):
            return None
        w, h = a.get("width"), a.get("height")
        ok = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0     # noqa: E731
        if not (ok(w) and ok(h)):
            w = h = None
            try:
                import cv2
                im = cv2.imread(str(self.dir / a["file"]), cv2.IMREAD_REDUCED_COLOR_8)
                if im is not None:
                    h, w = im.shape[0] * 8, im.shape[1] * 8
            except Exception:
                pass
        return {"key": key, "w": w, "h": h, "title": a.get("title"), "artist": a.get("artist"), "year": a.get("year"),
                "regions": a.get("regions") or {}}

    def default_params(self, technique_id: str, context: dict) -> dict:
        """Starting params for a freshly chosen technique.

        `context` (all keys optional): `asset` (asset key or {key,w,h,regions,...}), `asset_right`, `shot_id` (the asset is then the
        shot's main image), `region` (region name or [x, y] to focus on), `focus` (same, for camera techniques), `camera`
        ({cx,cy,zoom} at the playhead), `text`/`title`/`artist_year` (label text). Missing information falls back to registry defaults.
        """
        b = self.bundle
        spec = b.spec(technique_id)
        if spec is None:
            raise KeyError("unknown technique %r" % technique_id)
        sb = self._draft if self._draft is not None else self.storyboard()
        ctx = dict(context or {})
        for k in ("asset", "asset_right"):
            if isinstance(ctx.get(k), str):
                ctx[k] = self._asset_info(ctx[k], sb)
        if not ctx.get("asset") and ctx.get("shot_id"):
            for s in sb.get("shots", []):
                if s.get("id") == ctx["shot_id"]:
                    _, akey = SB.primary_slot(s)
                    if akey:
                        ctx["asset"] = self._asset_info(akey, sb)
        entry = R.RENDERERS.get(technique_id)
        if entry is not None and b.available(technique_id):
            params = entry[0].default_params(technique_id, spec, ctx, b)
        else:
            params = {p["name"]: p["default"] for p in spec["params"]}
        return copy.deepcopy(params)

    def save(self, storyboard: dict) -> str:
        """Validate (errors refuse the save with ValidationError), write atomically, back up to history/, return the revision."""
        issues = self.validate(storyboard)
        rev = SB.save(self.dir, storyboard, issues)
        self._saved = SB.strip_derived(copy.deepcopy(storyboard))
        self._saved_mtime = (self.dir / "storyboard.json").stat().st_mtime_ns
        return rev
