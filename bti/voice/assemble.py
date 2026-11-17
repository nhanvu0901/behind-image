"""Assembly (a light job): chunks in order with silences, tempo, an optional quiet pad, two-pass loudness, AAC.

Ported from the benchmark's `audio_job2.py`. The arithmetic (`layout`) is pure and tested alone; the sound work needs numpy
and ffmpeg. Every chunk's exact start and end in the final audio is returned in `spans`."""
from __future__ import annotations

import json
import os
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import files
from .errors import VoiceError

SR = 48000
SRC_SR = 24000


def layout(durations: list[float], gaps: list[float], tail: float, sr: int = SR) -> dict:
    """Place chunks on the timeline. `durations` are the final lengths (tempo already applied), `gaps` the silence before each.
    Positions are whole samples so that spans add up exactly. Returns {spans: [(start, end)], total_samples, duration}."""
    pos = 0
    spans = []
    for d, g in zip(durations, gaps):
        pos += int(round(g * sr))
        n = int(round(d * sr))
        spans.append((pos, pos + n))
        pos += n
    total = pos + int(round(tail * sr))
    return {"spans": [(a / sr, b / sr) for a, b in spans], "sample_spans": spans, "total_samples": total, "duration": total / sr}


def _run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    kw = {}
    try:
        from bti.proc import group_kwargs
        kw = group_kwargs()
    except Exception:       # a missing helper never stops the voice
        kw = {}
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, **kw)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VoiceError("voice_assemble_failed", f"ffmpeg did not run: {type(e).__name__}", 500)


def decode_chunk(path: Path, tempo: float) -> np.ndarray:
    """A chunk WAV as float32 mono at 48 kHz, with the tempo applied (ffmpeg `atempo`)."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)]
    if abs(tempo - 1.0) > 1e-6:
        cmd += ["-af", "atempo=%.4f" % tempo]
    cmd += ["-ar", str(SR), "-ac", "1", "-f", "s16le", "-"]
    r = _run(cmd, 300)
    if r.returncode != 0:
        raise VoiceError("voice_assemble_failed", "ffmpeg could not read %s: %s" % (path.name, r.stderr.decode("utf-8", "replace")[-200:]), 500)
    return np.frombuffer(r.stdout, dtype="<i2").astype(np.float32) / 32768.0


def _box(x: np.ndarray, n: int) -> np.ndarray:
    x = x.astype(np.float64)
    c = np.cumsum(np.concatenate([np.zeros(n // 2 + 1), x, np.zeros(n - n // 2 - 1)]))
    return ((c[n:n + len(x)] - c[:len(x)]) / n).astype(np.float32)


def make_pad(total: int, seconds: float, chord_seconds: float = 10.0) -> np.ndarray:
    """The quiet pad: Am-F-C-G drones of detuned sines with a slow LFO and a faint room tone, synthesised here (no sample is used).
    Returns (2, total) float32, RMS about 0.05."""
    t = np.arange(total, dtype=np.float64) / SR
    chords = [(110.0, 130.81, 164.81), (87.31, 130.81, 174.61), (130.81, 164.81, 196.0), (98.0, 146.83, 196.0)]
    pad = np.zeros((2, total), np.float32)
    for ch in range(2):
        for ci in range(int(seconds / chord_seconds) + 3):
            c0 = ci * chord_seconds - 1.5
            c1 = c0 + chord_seconds + 3.0
            i0, i1 = max(0, int(c0 * SR)), min(total, int(c1 * SR))
            if i1 <= i0:
                continue
            tt = t[i0:i1]
            env = np.clip(np.minimum((tt - c0) / 3.0, (c1 - tt) / 3.0), 0, 1) ** 1.5
            sig = np.zeros_like(tt)
            for f in chords[ci % 4]:
                for det, amp in ((0.0, 1.0), (0.37 if ch else -0.37, 0.7)):
                    sig += (amp * np.sin(2 * np.pi * (f + det) * tt) + .25 * amp * np.sin(2 * np.pi * 2 * (f + det) * tt)
                            + .08 * amp * np.sin(2 * np.pi * 3 * (f + det) * tt))
            pad[ch, i0:i1] += (sig * env).astype(np.float32)
    pad *= (0.75 + 0.25 * np.sin(2 * np.pi * t / 11.0))[None, :].astype(np.float32)
    rng = np.random.RandomState(3)
    nz = np.stack([_box(rng.normal(0, 1, total).astype(np.float32), 400) for _ in range(2)])
    pad = pad / (np.sqrt((pad ** 2).mean()) + 1e-9) * 0.05 + nz / (np.sqrt((nz ** 2).mean()) + 1e-9) * 0.006
    fin = min(int(2.0 * SR), total // 2)
    if fin > 0:
        pad[:, :fin] *= np.linspace(0, 1, fin)
        pad[:, -fin:] *= np.linspace(1, 0, fin)
    return pad.astype(np.float32)


def mix_with_pad(voice: np.ndarray, level_db: float, duck: float, seconds: float, chord_seconds: float = 10.0) -> np.ndarray:
    """Stereo mix (2, N): the voice on both channels plus the pad `level_db` under the voice RMS, ducked while speech is active."""
    loud = voice[np.abs(voice) > 0.01]
    vr = float(np.sqrt((loud ** 2).mean())) if loud.size else 0.1
    pad = make_pad(len(voice), seconds, chord_seconds)
    active = _box((np.abs(voice) > 0.02).astype(np.float32), int(.4 * SR))
    ducking = 1 - duck * np.clip(active * 3, 0, 1)
    mus = pad / (np.sqrt((pad ** 2).mean()) + 1e-9) * vr * 10 ** (level_db / 20) * ducking[None, :]
    return np.clip(np.stack([voice, voice]) + mus, -1, 1)


def write_wav(path: Path, data: np.ndarray) -> None:
    """`data`: (N,) mono or (2, N) float32 in [-1, 1]; written as 48 kHz 16-bit PCM."""
    ch = 1 if data.ndim == 1 else data.shape[0]
    frames = data if ch == 1 else data.T
    tmp = path.with_name(path.name + ".part")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(ch)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((np.clip(frames, -1, 1) * 32767).astype("<i2").tobytes())
    os.replace(tmp, path)


def parse_loudnorm(stderr: str) -> dict | None:
    """The JSON block that ffmpeg's loudnorm prints at the end of its output; None when it is not there."""
    try:
        return json.loads(stderr[stderr.rindex("{"):stderr.rindex("}") + 1])
    except ValueError:
        return None


def _num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def normalise(src_wav: Path, out_m4a: Path, loud: dict, bitrate: str) -> dict:
    """Two-pass loudnorm of `src_wav` into an AAC file; returns the measured loudness of the result {i, tp, lra}."""
    ln = "loudnorm=I=%s:TP=%s:LRA=%s" % (loud["i"], loud["tp"], loud["lra"])
    r1 = _run(["ffmpeg", "-y", "-hide_banner", "-nostdin", "-i", str(src_wav), "-af", ln + ":print_format=json", "-f", "null", "-"])
    j = parse_loudnorm(r1.stderr.decode("utf-8", "replace"))
    vals = [_num((j or {}).get(k)) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")]
    af = None
    if r1.returncode == 0 and j and all(v is not None for v in vals):
        af = ln + ":measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true" % (
            j["input_i"], j["input_tp"], j["input_lra"], j["input_thresh"], j["target_offset"])
    tmp = out_m4a.with_name(out_m4a.stem + ".part.m4a")
    cmd = ["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(src_wav)]
    if af:
        cmd += ["-af", af]
    cmd += ["-ar", str(SR), "-ac", "2", "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", str(tmp)]
    r2 = _run(cmd)
    if r2.returncode != 0:
        raise VoiceError("voice_assemble_failed", "ffmpeg could not write the mix: " + r2.stderr.decode("utf-8", "replace")[-200:], 500)
    os.replace(tmp, out_m4a)
    return measure(out_m4a)


def measure(path: Path) -> dict:
    r = _run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    j = parse_loudnorm(r.stderr.decode("utf-8", "replace")) or {}
    return {"i": _num(j.get("input_i")), "tp": _num(j.get("input_tp")), "lra": _num(j.get("input_lra"))}


def assemble(pdir: Path, chunks, settings: dict, cfg: dict, workdir: Path, ctx=None, decode=decode_chunk) -> dict:
    """Make `audio/voice.wav` and `audio/mix.m4a` from the cached chunks. `decode(path, tempo)` returns float32 mono 48 kHz
    (injectable for tests). Returns {duration, spans: [{id, start, end}], loudness, mix_bytes}."""
    tempo = float(settings["tempo"])
    missing = [c for c in chunks if not files.chunk_path(pdir, c.id).is_file()]
    if missing:
        raise VoiceError("voice_chunks_missing", "%d sentence(s) have no audio yet" % len(missing),
                         sentences=[c.spoken[:120] for c in missing[:10]])
    arrays = []
    for k, c in enumerate(chunks):
        if ctx is not None and ctx.cancelled():
            raise VoiceError("cancelled", "cancelled", 499)
        arrays.append(decode(files.chunk_path(pdir, c.id), tempo))
        if ctx is not None and k % 10 == 0:
            ctx.progress(0.6 * k / max(len(chunks), 1), "đọc câu %d/%d" % (k + 1, len(chunks)))
    lay = layout([len(a) / SR for a in arrays], [c.gap for c in chunks], float(cfg["silence"]["tail"]))
    voice = np.zeros(lay["total_samples"], np.float32)
    fade = int(cfg["fade_ms"] / 1000 * SR)
    for a, (s, e) in zip(arrays, lay["sample_spans"]):
        seg = a[: e - s].copy()
        f = min(fade, len(seg) // 2)
        if f > 0:
            seg[:f] *= np.linspace(0, 1, f, dtype=np.float32)
            seg[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
        voice[s:s + len(seg)] += seg
    del arrays
    out_dir = files.mix_path(pdir).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    write_wav(files.dry_path(pdir), voice)
    if ctx is not None:
        ctx.progress(0.7, "trộn nhạc nền" if settings["pad"] else "chuẩn hóa âm lượng")
    if settings["pad"]:
        p = cfg["pad"]
        mix = mix_with_pad(voice, float(p["level_db"]), float(p["duck"]), lay["duration"], float(p["chord_seconds"]))
    else:
        mix = np.stack([voice, voice])
    pre = workdir / "mix_pre.wav"
    write_wav(pre, mix)
    del mix
    if ctx is not None:
        ctx.progress(0.85, "chuẩn hóa âm lượng")
    loud = normalise(pre, files.mix_path(pdir), cfg["loudness"], cfg["aac_bitrate"])
    try:
        pre.unlink()
    except OSError:
        pass
    return {"duration": lay["duration"], "loudness": loud, "mix_bytes": files.mix_path(pdir).stat().st_size,
            "spans": [{"index": k, "id": c.id, "start": round(s, 4), "end": round(e, 4)} for k, (c, (s, e)) in enumerate(zip(chunks, lay["spans"]))]}
