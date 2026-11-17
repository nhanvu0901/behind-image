"""Reads config/server.json: one block per platform ("windows", "default").

Nothing here reads environment variables. A missing or broken file gives the "default" block (no lock folder, no voice
worker, no aligner), so a stage on a laptop falls back to its fake or says the program is not available."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "server.json"


@dataclass(frozen=True)
class VoiceCfg:
    python: str
    worker: str
    reference_voice: str
    exaggeration: float = 0.35
    cfg_weight: float = 0.5
    temperature: float = 0.7
    seed: int = 42


@dataclass(frozen=True)
class AlignerCfg:
    python: str
    model: str = "small.en"
    compute_type: str = "int8"
    beam_size: int = 5


@dataclass(frozen=True)
class ServerConfig:
    platform: str = "default"
    lock_dir: str | None = None
    memory_floor_kb: int = 0
    production_patterns: tuple[str, ...] = ()
    voice: VoiceCfg | None = None
    aligner: AlignerCfg | None = None
    render_threads: int = 4
    part_seconds: int = 240
    raw: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def is_server(self) -> bool:
        """True when the heavy-lock protocol applies (a lock folder is configured)."""
        return bool(self.lock_dir)


def current_platform() -> str:
    return "windows" if os.name == "nt" else "default"


def _int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_block(platform: str, b: dict) -> ServerConfig:
    """Build a ServerConfig from one block. Unknown keys are kept in `raw`, missing ones take the neutral value."""
    if not isinstance(b, dict):
        b = {}
    voice = None
    v = b.get("voice")
    if isinstance(v, dict) and v.get("python") and v.get("worker") and v.get("reference_voice"):
        voice = VoiceCfg(str(v["python"]), str(v["worker"]), str(v["reference_voice"]),
                         _float(v.get("exaggeration"), 0.35), _float(v.get("cfg_weight"), 0.5),
                         _float(v.get("temperature"), 0.7), _int(v.get("seed"), 42))
    aligner = None
    a = b.get("aligner")
    if isinstance(a, dict) and a.get("python"):
        aligner = AlignerCfg(str(a["python"]), str(a.get("model") or "small.en"),
                             str(a.get("compute_type") or "int8"), _int(a.get("beam_size"), 5))
    pats = b.get("production_patterns")
    lock = b.get("lock_dir")
    return ServerConfig(
        platform=platform,
        lock_dir=str(lock) if lock else None,
        memory_floor_kb=max(0, _int(b.get("memory_floor_kb"), 0)),
        production_patterns=tuple(str(p) for p in pats) if isinstance(pats, list) else (),
        voice=voice, aligner=aligner,
        render_threads=max(1, _int(b.get("render_threads"), 4)),
        part_seconds=max(10, _int(b.get("part_seconds"), 240)),
        raw=b)


def load(platform: str | None = None, path: str | Path | None = None) -> ServerConfig:
    """The block for `platform` (default: this machine's) from `path` (default: config/server.json)."""
    platform = platform or current_platform()
    try:
        doc = json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    block = doc.get(platform)
    if not isinstance(block, dict):
        platform, block = "default", doc.get("default")
    return parse_block(platform, block if isinstance(block, dict) else {})
