"""Post-export audio measurements: programme loudness and pause level vs speech."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from bti.export import check, render
from bti.export.settings import load_settings

SAMPLE_RATE = 8000
SPEECH_MERGE_GAP_S = 0.15
MIN_PAUSE_S = 0.50
PAUSE_EDGE_TRIM_S = 0.15
MIN_MEDIA_BYTES = 256


def is_media_file(path: Path | None) -> bool:
    """True when `path` looks like a real media file rather than a small JSON test stub."""
    if path is None or not Path(path).is_file():
        return False
    try:
        if Path(path).stat().st_size <= MIN_MEDIA_BYTES:
            return False
        with open(path, "rb") as fh:
            head = fh.read(32).lstrip()
        return not head.startswith(b"{")
    except OSError:
        return False


def find_exported_video(project_dir: Path) -> tuple[Path | None, dict | None]:
    """Return `(video_path, manifest)` for an export matching storyboard/timing (allowing music-only drift), else `(None, manifest)`."""
    from bti.export import run as export_run
    pdir = Path(project_dir)
    m = export_run.read_manifest(pdir)
    if m is None:
        return None, None
    stale = export_run.stale_reason(pdir, m)
    if stale not in (None, "music"):
        return None, m
    names = m.get("files") if isinstance(m.get("files"), dict) else {}
    vname = names.get("video") or (pdir.name + ".mp4")
    vpath = pdir / "export" / str(vname)
    return (vpath if is_media_file(vpath) else None), m


def _speech_segments(words: list[dict], duration: float) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    for w in words:
        if not isinstance(w, dict):
            continue
        s, e = w.get("s"), w.get("e")
        if isinstance(s, (int, float)) and isinstance(e, (int, float)) and e > s:
            spans.append((max(0.0, float(s)), min(duration, float(e))))
    if not spans:
        return []
    spans.sort()
    merged: list[tuple[float, float]] = [spans[0]]
    for s, e in spans[1:]:
        ps, pe = merged[-1]
        if s - pe <= SPEECH_MERGE_GAP_S:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def _pause_segments(speech: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    """Return trimmed pause windows `[a, b]` between speech segments (at least `MIN_PAUSE_S`)."""
    if len(speech) < 2:
        return []
    pauses: list[tuple[float, float]] = []
    for (_, e0), (s1, _) in zip(speech, speech[1:]):
        if s1 - e0 >= MIN_PAUSE_S:
            a = e0 + PAUSE_EDGE_TRIM_S
            b = s1 - PAUSE_EDGE_TRIM_S
            if b > a:
                pauses.append((a, b))
    return pauses


def _rms_db(arr: np.ndarray) -> float | None:
    if arr.size == 0:
        return None
    rms = float(np.sqrt(np.mean(np.square(arr, dtype=np.float64))))
    return round(20.0 * math.log10(max(rms, 1e-7)), 1)


def compute_pause_vs_speech(samples: np.ndarray, sr: int, words: list[dict], duration: float | None = None) -> dict | None:
    """Measure speech RMS dBFS vs pause RMS dBFS from mono float32 samples and word timings."""
    if samples.size == 0 or not words or sr <= 0:
        return None
    total_dur = float(duration) if duration and duration > 0 else (samples.size / float(sr))
    speech = _speech_segments(words, total_dur)
    pauses = _pause_segments(speech, total_dur)
    if not speech or not pauses:
        return None
    n = samples.size
    speech_mask = np.zeros(n, dtype=bool)
    pause_mask = np.zeros(n, dtype=bool)
    for s, e in speech:
        i0, i1 = max(0, int(round(s * sr))), min(n, int(round(e * sr)))
        if i1 > i0:
            speech_mask[i0:i1] = True
    for s, e in pauses:
        i0, i1 = max(0, int(round(s * sr))), min(n, int(round(e * sr)))
        if i1 > i0:
            pause_mask[i0:i1] = True
    speech_db = _rms_db(samples[speech_mask])
    pause_db = _rms_db(samples[pause_mask])
    if speech_db is None or pause_db is None:
        return None
    per_pause: list[float] = []
    for s, e in pauses:
        i0, i1 = max(0, int(round(s * sr))), min(n, int(round(e * sr)))
        db = _rms_db(samples[i0:i1])
        if db is not None:
            per_pause.append(db)
    pause_s = round(sum(b - a for a, b in pauses), 2)
    return {
        "speech_db": speech_db,
        "pause_db": pause_db,
        "diff_db": round(speech_db - pause_db, 1),
        "pause_median_db": round(float(np.median(per_pause)), 1) if per_pause else pause_db,
        "pause_count": len(pauses),
        "pause_seconds": pause_s,
    }


def _decode_mono_f32(ffmpeg: list[str], video_path: Path, sr: int = SAMPLE_RATE, env: dict | None = None, timeout: float = 300.0) -> np.ndarray | None:
    cmd = [str(c) for c in ffmpeg] + [
        "-v", "error", "-nostdin", "-i", str(video_path),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "pipe:1",
    ]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    usable = len(r.stdout) - (len(r.stdout) % 4)
    if usable <= 0:
        return None
    return np.frombuffer(r.stdout[:usable], dtype=np.float32)


def measure_export_audio(video_path: Path | None, timing: dict | None, *, tools: Any = None, loudness: dict | None = None) -> dict:
    """Measure loudness and pause-vs-speech level for a real exported video file."""
    loud = dict(loudness) if isinstance(loudness, dict) and loudness.get("lufs") is not None else None
    if not is_media_file(video_path):
        return {"loudness": loud, "pause_vs_speech": None}
    if tools is None:
        tools = render.Tools.from_settings(load_settings())
    ffmpeg = list(tools.ffmpeg)
    env = getattr(tools, "env", None)
    if loud is None:
        try:
            loud = check.measure_loudness(ffmpeg, video_path)
        except check.ToolError:
            loud = None
    words = (timing or {}).get("words") if isinstance(timing, dict) else None
    dur = (timing or {}).get("duration") if isinstance(timing, dict) else None
    pvs = None
    if isinstance(words, list) and words:
        samples = _decode_mono_f32(ffmpeg, Path(video_path), SAMPLE_RATE, env=env)
        if samples is not None:
            pvs = compute_pause_vs_speech(samples, SAMPLE_RATE, words, float(dur) if isinstance(dur, (int, float)) else None)
    return {"loudness": loud, "pause_vs_speech": pvs}
