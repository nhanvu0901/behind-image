"""Compile a resolved storyboard into a Scene: `frame_at` and `render_range`.

Frame pipeline (matches the benchmark's `frame_fn`):
  shot lookup (bisect on shot starts, +1e-6) -> base renderer -> overlays in list order
  -> optional transition_in (both shots rendered during the overlap) -> end fade -> uint8 -> resize.
"""
from __future__ import annotations

import bisect
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from . import registry as R
from . import techniques  # noqa: F401  (registers every renderer)
from .base import BaseRenderer, Ctx, OverlayRenderer, TransitionRenderer
from . import guard
from .errors import RenderError
from .storyboard import missing_of
from .vfx import ramp, to_u8

DEFAULT_END_FADE_S = 1.6
guard.install()          # every cv2.resize / warp now refuses a buffer over guard.MAX_PIXELS


def render_error(exc: BaseException, shot: dict, technique: str | None, index: int, overlay: tuple | None = None,
                 transition: bool = False) -> RenderError:
    """`exc` as a RenderError that names the shot, the technique and (when there is one) the overlay."""
    if isinstance(exc, RenderError):
        return exc
    path = "shots[%d]" % index
    oid = None
    if overlay is not None:
        oid = overlay[1]
        path += ".overlays[%d]" % overlay[0]
    elif transition:
        path += ".transition_in"
    sid = shot.get("id") if isinstance(shot, dict) else None
    where = "shot %s" % sid if sid else "shot %d" % index
    if oid:
        where += ", overlay %s" % oid
    elif overlay is not None:
        where += ", overlay %d" % overlay[0]
    elif transition:
        where += ", transition"
    detail = str(exc).strip() or type(exc).__name__
    if not isinstance(exc, (KeyError, ValueError)):
        detail = "%s: %s" % (type(exc).__name__, detail)
    err = RenderError("%s (%s) cannot be drawn: %s" % (where, technique, detail[:200]), shot=sid if isinstance(sid, str) else None,
                      overlay=oid if isinstance(oid, str) else None, technique=technique, path=path)
    err.__cause__ = exc
    return err


class CompiledShot:
    def __init__(self, shot, base: BaseRenderer | None, overlays, transition, index: int = 0, error: RenderError | None = None):
        # overlays: list of (index in the shot's overlay list, renderer)
        self.shot, self.base, self.overlays, self.transition = shot, base, overlays, transition
        self.index, self.error = index, error
        self.t0, self.t1 = shot["_t0"], shot["_t1"]

    def render(self, t):
        if self.error is not None:
            raise self.error
        tid = self.shot.get("technique")
        try:
            f = self.base.render(t)
        except Exception as e:      # noqa: BLE001
            raise render_error(e, self.shot, tid, self.index) from e
        if self.overlays:
            try:
                view = self.base.view(t)
            except Exception as e:      # noqa: BLE001
                raise render_error(e, self.shot, tid, self.index) from e
            for j, o in self.overlays:
                try:
                    f = o.apply(f, t, view)
                except Exception as e:      # noqa: BLE001
                    ov = self.shot["overlays"][j]
                    raise render_error(e, self.shot, ov.get("technique"), self.index, overlay=(j, ov.get("id"))) from e
        return f

    def blend(self, f_out, f_in, p):
        try:
            return self.transition.blend(f_out, f_in, p)
        except Exception as e:      # noqa: BLE001
            raise render_error(e, self.shot, self.shot["transition_in"].get("technique"), self.index, transition=True) from e


class Placeholder(BaseRenderer):
    """Stands in for a shot whose technique is INCOMPLETE (a required slot or parameter is empty): a neutral frame that
    names the technique and what is missing. An incomplete storyboard can be saved but never approved, so this is only a
    working picture for the editor."""

    def __init__(self, tid, shot, ctx, missing):
        super().__init__(tid, shot, ctx)
        what = ", ".join("%s %s" % (k, n) for k, n in missing)
        img = np.full((ctx.h, ctx.w, 3), 48, np.uint8)
        for i, line in enumerate((tid, "incomplete: " + what)):
            cv2.putText(img, line, (80, ctx.h // 2 - 20 + i * 70), cv2.FONT_HERSHEY_SIMPLEX, 1.6 if i == 0 else 1.2,
                        (170, 170, 170), 2, cv2.LINE_AA)
        self._frame = img.astype(np.float32)

    def render(self, t):
        return self._frame.copy()


class Scene:
    def __init__(self, project_dir: Path, sb: dict, timing, bundle: R.StyleBundle):
        self.ctx = Ctx(project_dir, sb, timing, bundle)
        self.sb = sb
        self.end_t = sb["end"]["_t"]
        self.end_fade_s = float(sb["end"].get("fade_s", DEFAULT_END_FADE_S))
        self.shots: list[CompiledShot] = []
        for i, s in enumerate(sb["shots"]):
            tid = s["technique"]
            stage = [tid, None]          # what is being built, for the error message
            try:
                cls, kind = R.RENDERERS[tid]
                miss = missing_of(bundle.spec(tid), s, "base")
                base = Placeholder(tid, s, self.ctx, miss) if miss else cls(tid, s, self.ctx)
                ovs = []
                for j, o in enumerate(s.get("overlays") or []):
                    stage = [o["technique"], (j, o.get("id"))]
                    ocls, _ = R.RENDERERS[o["technique"]]
                    if missing_of(bundle.spec(o["technique"]), o, "overlay", s):
                        continue                    # incomplete overlay: skipped, never an error
                    ovs.append((j, ocls(o["technique"], o, base, self.ctx)))
                tr = None
                if s.get("transition_in"):
                    stage = [s["transition_in"]["technique"], "transition"]
                    ttid = s["transition_in"]["technique"]
                    tcls, _ = R.RENDERERS[ttid]
                    if not missing_of(bundle.spec(ttid), s["transition_in"], "transition"):
                        tr = tcls(ttid, s["transition_in"], self.ctx)
                self.shots.append(CompiledShot(s, base, ovs, tr, i))
            except Exception as e:      # noqa: BLE001
                # one shot that cannot be built must not hide the others: it raises when (and only when) it is drawn
                ov = stage[1] if isinstance(stage[1], tuple) else None
                self.shots.append(CompiledShot(s, None, [], None, i, error=render_error(e, s, stage[0], i, overlay=ov, transition=stage[1] == "transition")))
        self.starts = [c.t0 for c in self.shots]
        self.starts[0] = min(self.starts[0], 0.0)    # the first shot also covers t < its start (benchmark: shots[0].t0 = 0)

    def shot_index(self, t: float) -> int:
        return max(0, bisect.bisect_right(self.starts, t + 1e-6) - 1)

    def shot_at(self, t: float) -> CompiledShot:
        return self.shots[self.shot_index(t)]

    def frame_float(self, t: float):
        i = self.shot_index(t)
        c = self.shots[i]
        f = c.render(t)
        tr = c.transition
        if tr is not None and i > 0 and tr.dur > 0 and t < c.t0 + tr.dur:
            p = (t - c.t0) / tr.dur
            f = c.blend(self.shots[i - 1].render(t), f, p)
        if self.end_fade_s > 0:
            fade = 1 - ramp(t, self.end_t - self.end_fade_s, self.end_fade_s, "inout_sine")
            if fade < 1:
                f = f * fade
        return f

    def frame_at(self, t: float, width: int = 1920) -> np.ndarray:
        with guard.limited():
            f = to_u8(self.frame_float(t))
        return resize_frame(f, width)

    def render_range(self, t0: float, t1: float, out_path: Path, width: int = 640, fps: int = 15, on_progress=None, quality: str = "preview", threads: int | None = None) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        w, h = even_size(width)
        if quality not in ("preview", "final"):
            raise ValueError("quality must be 'preview' or 'final'")
        crf, preset = ("15", "medium") if quality == "final" else ("27", "veryfast")
        if threads:
            cv2.setNumThreads(int(threads))
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (w, h), "-r", str(fps),
                              "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-g", "60",
                              "-threads", str(int(threads) if threads else 4), "-movflags", "+faststart", str(out_path)], stdin=subprocess.PIPE)
        i0 = int(round(t0 * fps))
        n = max(1, int(round((t1 - t0) * fps)))       # the length, not two rounded ends: 3.0 s at 15 fps is always 45 frames
        i1 = i0 + n
        ok = False
        broken_pipe = False
        try:
            for k, i in enumerate(range(i0, i1)):
                fr = self.frame_at(i / fps, 1920)
                if (w, h) != (1920, 1080):
                    fr = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
                try:
                    p.stdin.write(fr.tobytes())
                except (BrokenPipeError, OSError):
                    broken_pipe = True          # ffmpeg died: its own message is on stderr, the exit code is checked below
                    break
                if on_progress and (k % 5 == 0 or k == n - 1):
                    on_progress((k + 1) / n)
            ok = not broken_pipe
        finally:
            try:
                p.stdin.close()
            except OSError:
                pass
            rc = p.wait()
            if not ok or rc != 0:
                out_path.unlink(missing_ok=True)       # never leave a partial clip behind
        if rc != 0 or broken_pipe:
            raise RuntimeError("ffmpeg failed with exit code %d" % rc)
        if on_progress:
            on_progress(1.0)
        return out_path


def even_size(width: int):
    w = max(2, int(width) // 2 * 2)
    h = max(2, int(round(w * 9 / 16)) // 2 * 2)
    return w, h


def resize_frame(f: np.ndarray, width: int) -> np.ndarray:
    if width == f.shape[1]:
        return f
    h = int(round(width * f.shape[0] / f.shape[1]))
    return cv2.resize(f, (width, h), interpolation=cv2.INTER_AREA)
