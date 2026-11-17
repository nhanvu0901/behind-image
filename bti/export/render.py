"""One render part = the engine's command line as a child process, with its progress read; and the join of the parts.

Every program is reached through `Tools` (the command prefixes and the engine command builder), so tests put a small fake
script in their place and nothing needs a GPU, a model or minutes of compute.
"""
from __future__ import annotations

import os
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from bti.script.store import make_parent

from . import check
from .errors import ExportError
from .mux import concat_list, join_command
from .plan import PartSpec, part_filename
from .settings import REPO_ROOT, Settings


def engine_command(project_dir: Path, spec: PartSpec, out: Path, settings: Settings) -> list[str]:
    """`python -m bti.engine render <project> --t0 .. --t1 .. --quality final ...` (final = 1920 px, 30 fps, crf 15)."""
    return [sys.executable, "-m", "bti.engine", "render", str(project_dir), "--t0", "%.6f" % spec.t0, "--t1", "%.6f" % spec.t1,
            "--quality", "final", "--width", str(settings.width), "--fps", str(spec.fps), "--threads", str(settings.render_threads), "-o", str(out)]


@dataclass
class Tools:
    ffmpeg: list[str]
    ffprobe: list[str]
    engine: Callable[[Path, PartSpec, Path, Settings], list[str]] = engine_command
    cwd: Path = field(default_factory=lambda: REPO_ROOT)
    env: dict | None = None

    @classmethod
    def from_settings(cls, s: Settings) -> "Tools":
        return cls(ffmpeg=[s.ffmpeg], ffprobe=[s.ffprobe])


_PROGRESS = re.compile(r"progress\s+(\d+(?:\.\d+)?)\s*%")


def parse_progress(line: str) -> float | None:
    """0..1 from a line like `progress 35%`; None for any other line."""
    m = _PROGRESS.search(line or "")
    return min(1.0, float(m.group(1)) / 100.0) if m else None


def render_part(ctx, tools: Tools, settings: Settings, project_dir: Path, spec: PartSpec, key: str, parts_dir: Path) -> dict:
    """Renders one part unless a file for this key exists. Returns `{"file": name, "skipped": bool, "frames": n}`; a cancelled
    part removes its partial file and returns `{"cancelled": True}`."""
    name = part_filename(spec, key)
    final = parts_dir / name
    if final.is_file() and final.stat().st_size > 0:
        ctx.log("%s exists for this storyboard; not rendered again" % name)
        ctx.progress(1.0, "Đã có sẵn")
        return {"file": name, "skipped": True, "frames": spec.frames}
    make_parent(parts_dir / "x", 3)           # cache/export/parts; never re-creates a deleted project folder
    tmp = parts_dir / (name[:-4] + ".partial.mp4")
    tmp.unlink(missing_ok=True)
    tail: deque[str] = deque(maxlen=6)

    def on_line(line: str) -> None:
        p = parse_progress(line)
        if p is not None:
            ctx.progress(p)
        elif line.strip():
            tail.append(line.strip()[:200])

    cmd = tools.engine(project_dir, spec, tmp, settings)
    rc = ctx.run_process(cmd, cwd=str(tools.cwd), env=tools.env, on_line=on_line)
    if ctx.cancelled():
        tmp.unlink(missing_ok=True)
        return {"cancelled": True}
    if rc != 0:
        tmp.unlink(missing_ok=True)
        raise ExportError("render_failed", "the render of part %d stopped (exit code %s): %s" % (spec.index + 1, rc, " | ".join(tail)[-300:]),
                          status=500, part=spec.index + 1)
    try:
        frames = check.probe(tools.ffprobe, tmp)["video"]["frames"]
    except (check.ToolError, TypeError):
        frames = None
    if frames != spec.frames:
        tmp.unlink(missing_ok=True)
        raise ExportError("frames_mismatch", "part %d has %s frames, expected %d" % (spec.index + 1, frames, spec.frames), status=500, part=spec.index + 1)
    os.replace(tmp, final)
    ctx.progress(1.0)
    return {"file": name, "skipped": False, "frames": frames}


def join_parts(ctx, tools: Tools, files: list[Path], out: Path, expected_frames: int, workdir: Path) -> dict:
    """Stream-copy join; the frame count of the result must be the planned one."""
    make_parent(workdir / "x", 2)           # cache/export
    lst = workdir / "join.txt"
    lst.write_text(concat_list(files), encoding="utf-8")
    tmp = out.with_name(out.stem + ".partial" + out.suffix)
    tmp.unlink(missing_ok=True)
    tail: deque[str] = deque(maxlen=4)
    rc = ctx.run_process(join_command(tools.ffmpeg, lst, tmp), cwd=str(workdir), env=tools.env, on_line=lambda ln: tail.append(ln.strip()[:200]) if ln.strip() else None)
    if ctx.cancelled():
        tmp.unlink(missing_ok=True)
        return {"cancelled": True}
    if rc != 0:
        tmp.unlink(missing_ok=True)
        raise ExportError("join_failed", "joining the parts failed: " + " | ".join(tail)[-200:], status=500)
    try:
        frames = check.probe(tools.ffprobe, tmp)["video"]["frames"]
    except (check.ToolError, TypeError) as e:
        tmp.unlink(missing_ok=True)
        raise ExportError("join_failed", "the joined video cannot be read: %s" % e, status=500)
    if frames != expected_frames:
        tmp.unlink(missing_ok=True)
        raise ExportError("frames_mismatch", "the joined video has %s frames, expected %d" % (frames, expected_frames), status=500, frames=frames, expected=expected_frames)
    os.replace(tmp, out)
    return {"frames": frames}
