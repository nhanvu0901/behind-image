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
from .vfx import ramp, to_u8

DEFAULT_END_FADE_S = 1.6


class CompiledShot:
    def __init__(self, shot, base: BaseRenderer, overlays, transition):
        self.shot, self.base, self.overlays, self.transition = shot, base, overlays, transition
        self.t0, self.t1 = shot["_t0"], shot["_t1"]

    def render(self, t):
        f = self.base.render(t)
        if self.overlays:
            view = self.base.view(t)
            for o in self.overlays:
                f = o.apply(f, t, view)
        return f


class Scene:
    def __init__(self, project_dir: Path, sb: dict, timing, bundle: R.StyleBundle):
        self.ctx = Ctx(project_dir, sb, timing, bundle)
        self.sb = sb
        self.end_t = sb["end"]["_t"]
        self.end_fade_s = float(sb["end"].get("fade_s", DEFAULT_END_FADE_S))
        self.shots: list[CompiledShot] = []
        for s in sb["shots"]:
            tid = s["technique"]
            cls, kind = R.RENDERERS[tid]
            base = cls(tid, s, self.ctx)
            ovs = []
            for o in s.get("overlays") or []:
                ocls, _ = R.RENDERERS[o["technique"]]
                ovs.append(ocls(o["technique"], o, base, self.ctx))
            tr = None
            if s.get("transition_in"):
                tcls, _ = R.RENDERERS[s["transition_in"]["technique"]]
                tr = tcls(s["transition_in"]["technique"], s["transition_in"], self.ctx)
            self.shots.append(CompiledShot(s, base, ovs, tr))
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
            f = tr.blend(self.shots[i - 1].render(t), f, p)
        if self.end_fade_s > 0:
            fade = 1 - ramp(t, self.end_t - self.end_fade_s, self.end_fade_s, "inout_sine")
            if fade < 1:
                f = f * fade
        return f

    def frame_at(self, t: float, width: int = 1920) -> np.ndarray:
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
        i0, i1 = int(round(t0 * fps)), int(round(t1 * fps))
        n = max(1, i1 - i0)
        try:
            for k, i in enumerate(range(i0, i1)):
                fr = self.frame_at(i / fps, 1920)
                if (w, h) != (1920, 1080):
                    fr = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
                p.stdin.write(fr.tobytes())
                if on_progress and (k % 5 == 0 or k == n - 1):
                    on_progress((k + 1) / n)
        finally:
            p.stdin.close()
            rc = p.wait()
        if rc != 0:
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
