"""Voice synthesis statistics and rolling median tracking (`run/voice_stats.json`).

Stores the measured `load_seconds` and `seconds_per_character` of the last 20 parts on this machine
and provides rolling median estimates for the planner."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from bti.fsio import atomic_replace
from bti.script import store

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATS_PATH = REPO_ROOT / "run" / "voice_stats.json"


def load_stats(path: Path | None = None) -> dict:
    """Load the voice statistics file; returns `{load_seconds, seconds_per_character, parts}` or `{}`."""
    p = Path(path) if path else DEFAULT_STATS_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "parts" in data and isinstance(data["parts"], list):
            return data
    except (OSError, ValueError):
        pass
    return {}


def record_part_stats(load_seconds: float, seconds_per_character: float,
                      path: Path | None = None, max_parts: int = 20) -> dict:
    """Record measurements from a synthesis part and update the rolling median over the last `max_parts`."""
    p = Path(path) if path else DEFAULT_STATS_PATH
    current = load_stats(p)
    parts = list(current.get("parts") or [])
    new_entry = {
        "load_seconds": round(float(load_seconds), 3),
        "seconds_per_character": round(float(seconds_per_character), 4),
        "at": store.now_iso(),
    }
    parts.append(new_entry)
    if len(parts) > max_parts:
        parts = parts[-max_parts:]

    median_load = statistics.median([entry["load_seconds"] for entry in parts])
    median_spc = statistics.median([entry["seconds_per_character"] for entry in parts])

    doc = {
        "load_seconds": round(float(median_load), 3),
        "seconds_per_character": round(float(median_spc), 4),
        "parts": parts,
    }

    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.stem + f".tmp_{time.time_ns()}.json")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    atomic_replace(tmp, p)
    return doc


def get_effective_estimate(cfg: dict | None = None, stats: dict | None = None,
                           stats_path: Path | None = None) -> tuple[float, float]:
    """Return `(load_seconds, seconds_per_character)`.
    Uses explicit `stats` if given, else loads from `stats_path` (or `cfg["stats_path"]`),
    else falls back to `cfg["estimate"]` (defaults 120.0s load and 0.55 s/char)."""
    if stats and "load_seconds" in stats and "seconds_per_character" in stats:
        return float(stats["load_seconds"]), float(stats["seconds_per_character"])

    sp = stats_path or (Path(cfg["stats_path"]) if cfg and "stats_path" in cfg and cfg["stats_path"] else None)
    st = load_stats(sp)
    if st and "load_seconds" in st and "seconds_per_character" in st:
        return float(st["load_seconds"]), float(st["seconds_per_character"])

    e = (cfg or {}).get("estimate") or {}
    load_s = float(e.get("load_seconds", 120.0))
    spc = float(e.get("seconds_per_character", 0.55))
    return load_s, spc
