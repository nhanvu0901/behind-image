"""Synthesis planner: which chunks still need speaking, grouped into parts that fit the heavy slot.

The planner sizes a part from an estimate `load_seconds + characters * seconds_per_character` and targets 18 minutes;
no part may be planned over 25. Defaults: load_seconds: 120, seconds_per_character: 0.55 (from the real run),
overridden by the rolling median of the last 20 parts from `run/voice_stats.json`."""
from __future__ import annotations

from pathlib import Path

from . import files
from . import stats as stats_mod
from .chunks import Chunk
from .providers.chatterbox import wav_seconds


def is_cached(pdir: Path, chunk: Chunk, since: float | None = None) -> bool:
    """The chunk has a valid audio file (and, when `since` is given, one written at or after that time)."""
    p = files.chunk_path(pdir, chunk.id)
    if wav_seconds(p) is None:
        return False
    if since is not None:
        try:
            return p.stat().st_mtime >= since
        except OSError:
            return False
    return True


def missing(pdir: Path, chunks: list[Chunk], force_ids: set[str] | None = None, since: float | None = None) -> list[Chunk]:
    """The chunks to speak: those without audio, plus the forced ones that have not been redone since `since`."""
    out = []
    for c in chunks:
        if force_ids is not None and c.id in force_ids:
            if not is_cached(pdir, c, since):
                out.append(c)
        elif not is_cached(pdir, c):
            out.append(c)
    return out


def group_parts(chunks: list[Chunk], cfg: dict | int | None = None, *, stats: dict | None = None,
                target_seconds: float | None = None, max_seconds: float | None = None,
                part_chars: int | None = None) -> list[list[Chunk]]:
    """Group chunks into synthesis parts.
    Sizing targets 18 minutes of compute per part and caps every planned part at 25 minutes.
    If `part_chars` or an integer `cfg` is explicitly provided, character-based grouping is used."""
    if isinstance(cfg, (int, float)):
        part_chars = int(cfg)

    if part_chars is not None:
        parts: list[list[Chunk]] = []
        cur: list[Chunk] = []
        size = 0
        for c in chunks:
            cur.append(c)
            size += len(c.spoken)
            if size >= part_chars:
                parts.append(cur)
                cur, size = [], 0
        if cur:
            if parts and size < part_chars * 0.25 and sum(len(c.spoken) for c in parts[-1]) + size <= part_chars * 1.25:
                parts[-1].extend(cur)
            else:
                parts.append(cur)
        return parts

    cfg_dict = cfg if isinstance(cfg, dict) else {}
    load_s, spc = stats_mod.get_effective_estimate(cfg_dict, stats)
    t_sec = float(target_seconds or (cfg_dict.get("target_minutes", 18) * 60))
    m_sec = float(max_seconds or (cfg_dict.get("max_part_minutes", 25) * 60))

    def part_est(part_chunks: list[Chunk]) -> float:
        return load_s + sum(len(c.spoken) for c in part_chunks) * spc

    parts = []
    cur = []

    for c in chunks:
        if not cur:
            cur.append(c)
            continue
        est_with_c = part_est(cur + [c])
        cur_est = part_est(cur)
        if est_with_c <= t_sec:
            cur.append(c)
        elif cur_est < t_sec and est_with_c <= m_sec:
            cur.append(c)
            parts.append(cur)
            cur = []
        else:
            parts.append(cur)
            cur = [c]

    if cur:
        if parts:
            merged = parts[-1] + cur
            merged_est = part_est(merged)
            tail_cost = sum(len(c.spoken) for c in cur) * spc
            if merged_est <= m_sec and tail_cost < t_sec * 0.25:
                parts[-1].extend(cur)
            else:
                parts.append(cur)
        else:
            parts.append(cur)
    return parts


def estimate_seconds(chars: int, cfg: dict | None = None, stats: dict | None = None) -> int:
    """Compute seconds for `chars` characters of spoken text."""
    if chars <= 0:
        return 0
    load_s, spc = stats_mod.get_effective_estimate(cfg, stats)
    return int(round(load_s + chars * spc))


def estimate_audio_seconds(chars: int, cfg: dict) -> float:
    e = cfg.get("estimate") or {}
    chars_per_sec = float(e.get("chars_per_audio_second", 15.0))
    return chars / chars_per_sec
