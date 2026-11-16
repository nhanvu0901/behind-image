"""Waveform peaks and audio helpers.

The decode and peak math follows stages/mascot/timeline.py of the comic
pipeline (waveform_png): ffmpeg to mono 8 kHz s16le, per-bin maximum,
normalised by the 99th percentile. Rewritten here to return JSON peaks.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .common import ApiError, file_signature, read_json, write_json_atomic

SR = 8000


def decode_mono(path: Path) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR),
           "-f", "s16le", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ApiError(500, f"audio decode failed: {e}")
    if r.returncode != 0:
        raise ApiError(500, "audio decode failed: " + r.stderr.decode("utf-8", "replace")[-200:])
    return np.frombuffer(r.stdout, dtype="<i2")


def peaks_for(samples: np.ndarray, bins: int) -> list[float]:
    if samples.size == 0:
        return [0.0] * bins
    a = np.abs(samples.astype(np.int32)).astype(np.float32)
    edges = np.linspace(0, a.size, bins + 1).astype(np.int64)
    peaks = np.zeros(bins, dtype=np.float32)
    for i in range(bins):
        lo, hi = edges[i], max(edges[i + 1], edges[i] + 1)
        seg = a[lo:hi]
        if seg.size:
            peaks[i] = seg.max()
    ref = float(np.percentile(peaks, 99))
    if ref <= 0:
        return [0.0] * bins
    return [round(float(v), 3) for v in np.clip(peaks / ref, 0.0, 1.0)]


def waveform(audio: Path, cache_dir: Path, bins: int) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cp = cache_dir / f"wave_{file_signature(audio)}_{bins}.json"
    if cp.is_file():
        try:
            return read_json(cp)
        except Exception:
            cp.unlink(missing_ok=True)
    samples = decode_mono(audio)
    out = {"duration": round(samples.size / SR, 3), "peaks": peaks_for(samples, bins)}
    write_json_atomic(cp, out)
    return out
