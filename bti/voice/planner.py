"""Synthesis planner: which chunks still need speaking, grouped into parts that fit the heavy slot.

A part holds about `part_chars` characters of spoken text (4,000 is about 20 minutes of compute at the measured 4.1 seconds of
compute per second of audio, with the model load inside each part). Parts keep the narration order; a chunk is never split."""
from __future__ import annotations

from pathlib import Path

from . import files
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


def group_parts(chunks: list[Chunk], part_chars: int = 4000) -> list[list[Chunk]]:
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
        # a short tail joins the last part when the result stays within a quarter over the size, else it is a part of its own
        if parts and size < part_chars * 0.25 and sum(len(c.spoken) for c in parts[-1]) + size <= part_chars * 1.25:
            parts[-1].extend(cur)
        else:
            parts.append(cur)
    return parts


def estimate_seconds(chars: int, cfg: dict) -> int:
    """Compute seconds for `chars` characters of spoken text."""
    e = cfg["estimate"]
    audio = chars / float(e["chars_per_audio_second"])
    return int(audio * float(e["compute_per_audio_second"]) + float(e["load_seconds"]))


def estimate_audio_seconds(chars: int, cfg: dict) -> float:
    return chars / float(cfg["estimate"]["chars_per_audio_second"])
