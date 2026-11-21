"""Cuts the timeline into render parts at shot boundaries. Pure: numbers in, numbers out.

The engine draws frame i at t = i / fps for i in range(round(t0 * fps), round(t1 * fps)) (half-open), so parts that share a
frame boundary are frame-exact and gap-free, and the sum of their frame counts is `round(end * fps)`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PartSpec:
    index: int          # 0-based
    f0: int             # first frame (inclusive)
    f1: int             # last frame (exclusive)
    fps: int

    @property
    def frames(self) -> int:
        return self.f1 - self.f0

    @property
    def t0(self) -> float:
        return self.f0 / self.fps

    @property
    def t1(self) -> float:
        return self.f1 / self.fps

    @property
    def seconds(self) -> float:
        return self.frames / self.fps


def total_frames(end: float, fps: int = 30) -> int:
    return int(round(end * fps))


def plan_parts(shot_starts, end: float, fps: int = 30, target: float = 60.0) -> list[PartSpec]:
    """Parts of about `target` seconds, each cut at a shot start. A part is never shorter than half of `target` nor longer
    than one and a half times it, except the whole video when it is shorter: when no shot starts near the wanted cut (one
    very long shot) the cut is made at the wanted frame instead."""
    total = total_frames(end, fps)
    if total <= 0 or fps <= 0 or target <= 0:
        raise ValueError("nothing to render")
    want_len = max(1, int(round(target * fps)))
    cuts = sorted({int(round(float(t) * fps)) for t in shot_starts if isinstance(t, (int, float)) and 0 < round(float(t) * fps) < total})
    edges = [0]
    start = 0
    while total - start > want_len * 3 // 2:
        want = start + want_len
        cand = [c for c in cuts if start + want_len // 2 <= c <= start + want_len * 3 // 2]
        cut = min(cand, key=lambda c: (abs(c - want), c)) if cand else want
        edges.append(cut)
        start = cut
    edges.append(total)
    return [PartSpec(i, a, b, fps) for i, (a, b) in enumerate(zip(edges, edges[1:]))]


def part_key(source, spec: PartSpec, width: int = 1920, quality: str = "final", **kw) -> str:
    """Identifies the file of one part. A storyboard dict hashes only what decides frames inside `spec`; a plain revision string hashes that string with range, size and quality."""
    if isinstance(source, dict):
        from . import partkey
        return partkey.part_key(source, spec, width=width, quality=quality, **kw)
    raw = json.dumps([source, spec.f0, spec.f1, spec.fps, width, quality], separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def part_filename(spec: PartSpec, key: str) -> str:
    return "part_%02d_%s.mp4" % (spec.index + 1, key)


def estimate_seconds(duration: float, render_speed: float = 2.0) -> int:
    """Compute time of the whole render, in seconds (`render_speed` = minutes of compute per minute of video)."""
    return int(round(max(0.0, duration) * render_speed))
