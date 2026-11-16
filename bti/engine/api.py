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
from collections import OrderedDict
from pathlib import Path

import numpy as np

from . import registry as R
from . import storyboard as SB
from .scene import Scene
from .timing import Timing

__all__ = ["open_project", "Project", "load_style", "ValidationError"]
ValidationError = SB.ValidationError


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
        self._timing = None
        self._timing_mtime = None

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

    def _tm(self) -> Timing:
        path = self.dir / (self._saved.get("timing") or "timing.json")
        mt = path.stat().st_mtime_ns
        if self._timing is None or mt != self._timing_mtime:
            self._timing, self._timing_mtime = Timing.load(path), mt
            self._scenes.clear()
        return self._timing

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
        return SB.resolve(sb, self._tm(), self.bundle)

    def validate(self, storyboard: dict | None = None) -> list[dict]:
        sb = storyboard if storyboard is not None else self.storyboard()
        return SB.validate(sb, self._tm(), self.bundle, self.dir)

    def use_draft(self, storyboard: dict | None) -> None:
        self._draft = copy.deepcopy(storyboard) if storyboard is not None else None

    # -- rendering -------------------------------------------------------------------------------------------
    def _scene(self) -> Scene:
        self._reload_if_changed()
        tm = self._tm()
        sb = self._draft if self._draft is not None else self._saved
        key = (SB.revision_of(sb), self._draft is not None)
        sc = self._scenes.get(key)
        if sc is None:
            sc = Scene(self.dir, SB.resolve(sb, tm, self.bundle), tm, self.bundle)
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

    # -- editing support -------------------------------------------------------------------------------------
    def _asset_info(self, key: str, sb: dict) -> dict | None:
        a = (sb.get("assets") or {}).get(key)
        if not a:
            return None
        w, h = a.get("width"), a.get("height")
        if not (w and h):
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
        issues = SB.validate(storyboard, self._tm(), self.bundle, self.dir)
        rev = SB.save(self.dir, storyboard, issues)
        self._saved = SB.strip_derived(copy.deepcopy(storyboard))
        self._saved_mtime = (self.dir / "storyboard.json").stat().st_mtime_ns
        return rev
