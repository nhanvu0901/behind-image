"""Numbers of the export that depend on the machine. They come from `config/server.json` (written by CORE; one block per
platform, "windows" and "default"); a missing file or key falls back to the defaults below, so the module works without it."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "server.json"


@dataclass(frozen=True)
class Settings:
    render_threads: int = 4          # `--threads` of the engine (0 = automatic)
    part_seconds: float = 240.0      # target length of one render part
    render_speed: float = 2.0        # minutes of compute per minute of video (measured on the server, W1)
    fps: int = 30
    width: int = 1920
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    language: str = "eng"            # language tag of the audio track (the narration is English)


def load_settings(path: Path | None = None, platform: str | None = None) -> Settings:
    """`platform` is "windows" or "default" (None: by `os.name`). Unknown or invalid values are ignored."""
    path = Path(path) if path else CONFIG_PATH
    block: dict = {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            plat = platform or ("windows" if os.name == "nt" else "default")
            b = doc.get(plat)
            if not isinstance(b, dict):
                b = doc.get("default")
            block = b if isinstance(b, dict) else {}
    except (OSError, ValueError):
        block = {}
    d = Settings()
    kw = {}
    th = block.get("render_threads")
    if isinstance(th, int) and not isinstance(th, bool) and 0 <= th <= 64:
        kw["render_threads"] = th
    ps = block.get("part_seconds", block.get("part_length"))
    if isinstance(ps, (int, float)) and not isinstance(ps, bool) and 30 <= ps <= 1200:
        kw["part_seconds"] = float(ps)
    sp = block.get("render_speed")
    if isinstance(sp, (int, float)) and not isinstance(sp, bool) and 0.1 <= sp <= 20:
        kw["render_speed"] = float(sp)
    for k in ("ffmpeg", "ffprobe", "language"):
        v = block.get(k)
        if isinstance(v, str) and v.strip():
            kw[k] = v.strip()
    return Settings(**{**d.__dict__, **kw})
