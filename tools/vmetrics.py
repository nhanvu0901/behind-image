#!/usr/bin/env python3
"""vmetrics.py - re-runnable video forensics for vertical Shorts.

Usage
  python3 vmetrics.py <folder | a.mp4 b.mp4 ...> --out <dir> --label <name>
        [--srt-dir DIR ...] [--manifest manifest.csv] [--scene-thr 0.30]
        [--no-normalize] [--no-sheets]

Writes into --out:
  <id>.json                 all metrics + 0.5 s time series for one video
  metrics_<label>.csv       one row per video (scalar metrics only)
  hook_<id>.jpg             frames at 0.0 0.5 1.0 1.5 2.0 3.0 s
  sheet_<id>.jpg            one frame every 2 s (also sheet_<id>_pN.jpg pages
                            of 40 tiles when the video is long, for viewing)
  end_<id>.jpg              last 3 s (dur-3,-2,-1,-0.3) + the t=0 frame, to judge loops / end cards
  hooks_all_<label>.jpg     t=0.0 and t=1.0 of every video in one grid

PARITY NOTE (read before comparing two folders)
  The competitor files are YouTube 360x640 ~200 kbit/s H.264 downloads. A master
  render at 1080x1920 and 8+ Mbit/s is sharper and less blocky, which changes
  scene scores, frame differences and the blur estimate. By default every input
  whose height is above 640 is first transcoded to 360x640, H.264 ~220 kbit/s,
  AAC 128k (a "YouTube-360p-like" proxy) and ALL measurements run on that proxy.
  Original resolution / fps / bitrate are still reported from the source file.
  Best parity is still to analyse YouTube downloads of both sets.
  Use --no-normalize to measure the source file as it is.

All image analysis additionally runs at fixed working sizes (scene detection
360x640, motion 72x128 gray @15 fps, blur grid 360x640 gray) so the numbers do
not depend on source fps or resolution.
"""
import argparse
import csv
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

MOTION_FPS = 15          # frame-difference sampling rate
MOTION_W, MOTION_H = 72, 128
WORK_W, WORK_H = 360, 640
MIN_SHOT_GAP = 0.25      # s; two detections closer than this count as one cut
HOOK_TIMES = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
SHEET_STEP = 2.0
# Blur/letterbox tile classification thresholds (on 360x640 gray, 0-255):
BLACK_MEAN, BLACK_STD = 18.0, 6.0     # tile is "black padding"
SHARP_LAPVAR = 60.0                   # Laplacian variance >= this -> "sharp"


# --------------------------------------------------------------------------- utils
def run(cmd, binary=False):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"failed: {' '.join(cmd)}\n{p.stderr.decode(errors='replace')[-2000:]}")
    return p.stdout if binary else (p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace"))


def r3(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 3)


def probe(path):
    out, _ = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)

    def frac(s):
        try:
            n, m = s.split("/")
            return float(n) / float(m) if float(m) else None
        except Exception:
            return None
    return {
        "duration_s": float(d["format"]["duration"]),
        "width": int(v["width"]) if v else None,
        "height": int(v["height"]) if v else None,
        "fps": r3(frac(v.get("avg_frame_rate", "0/0"))) if v else None,
        "bitrate_kbps": r3(int(d["format"].get("bit_rate", 0)) / 1000),
        "video_bitrate_kbps": r3(int(v.get("bit_rate", 0)) / 1000) if v and v.get("bit_rate") else None,
        "audio_bitrate_kbps": r3(int(a.get("bit_rate", 0)) / 1000) if a and a.get("bit_rate") else None,
        "video_codec": v.get("codec_name") if v else None,
        "has_audio": a is not None,
    }


def normalized_proxy(path, tmpdir):
    """YouTube-360p-like proxy for files taller than 640 px (see PARITY NOTE)."""
    out = Path(tmpdir) / (Path(path).stem + "_360p.mp4")
    run([FFMPEG, "-v", "error", "-y", "-i", str(path),
         "-vf", f"scale={WORK_W}:{WORK_H}:force_original_aspect_ratio=decrease,"
                f"pad={WORK_W}:{WORK_H}:(ow-iw)/2:(oh-ih)/2",
         "-c:v", "libx264", "-b:v", "220k", "-maxrate", "300k", "-bufsize", "600k",
         "-preset", "medium", "-c:a", "aac", "-b:a", "128k", str(out)])
    return out


# --------------------------------------------------------------------------- cuts
def scene_scores(path):
    """Per-frame ffmpeg 'scene' score (0-1) on a 360x640 decode."""
    _, err = run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
                  f"scale={WORK_W}:{WORK_H},select='gte(scene,0)',metadata=print:key=lavfi.scene_score",
                  "-f", "null", "-"])
    times, scores, t = [], [], None
    for line in err.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([\d.]+)", line)
        if m and t is not None:
            times.append(t)
            scores.append(float(m.group(1)))
    return np.array(times), np.array(scores)


def cuts_from_scores(times, scores, thr):
    cuts = []
    for t, s in zip(times, scores):
        if s >= thr and t > 0.05:
            if cuts and t - cuts[-1] < MIN_SHOT_GAP:
                continue
            cuts.append(float(t))
    return cuts


def cut_stats(cuts, dur):
    bounds = [0.0] + cuts + [dur]
    shots = [b - a for a, b in zip(bounds[:-1], bounds[1:]) if b - a > 0]
    return {
        "n_cuts": len(cuts),
        "cuts_per_10s": r3(len(cuts) / dur * 10),
        "mean_shot_s": r3(statistics.mean(shots)) if shots else None,
        "median_shot_s": r3(statistics.median(shots)) if shots else None,
        "max_shot_s": r3(max(shots)) if shots else None,
        "first_cut_s": r3(cuts[0]) if cuts else None,
        "cuts_first_5s": sum(1 for c in cuts if c < 5.0),
        "cuts_first_3s": sum(1 for c in cuts if c < 3.0),
    }


# --------------------------------------------------------------------------- motion
def motion_series(path):
    """Mean |frame_t - frame_{t-1}| on a 72x128 gray decode at 15 fps (0-255)."""
    raw = run([FFMPEG, "-v", "error", "-i", str(path), "-an", "-vf",
               f"fps={MOTION_FPS},scale={MOTION_W}:{MOTION_H}:flags=area,format=gray",
               "-f", "rawvideo", "-pix_fmt", "gray", "-"], binary=True)
    fr = np.frombuffer(raw, np.uint8).reshape(-1, MOTION_H, MOTION_W).astype(np.float32)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    t = (np.arange(1, len(fr)) / MOTION_FPS)
    # Apparent speed. Raw |diff| is ~ speed x edge density, so high-contrast line
    # art moving 0.3 px/frame already scores ~10. Dividing by the mean gradient
    # magnitude of the two frames gives ~displacement in px per frame (brightness
    # constancy: |dI| ~ |grad I . v|), expressed here as % of frame WIDTH per
    # second. Valid for smooth motion only; on cuts/whips it is meaningless, so
    # stats use it within shots. Calibrated on synthetic clips (see V_competitors.md).
    mid = (fr[1:] + fr[:-1]) / 2
    gx = np.abs(np.diff(mid, axis=2)).mean(axis=(1, 2))
    gy = np.abs(np.diff(mid, axis=1)).mean(axis=(1, 2))
    grad = (gx + gy) / 2 + 1e-3
    speed = np.clip(d / grad, 0, 20) * MOTION_FPS / MOTION_W * 100
    # Visual loop: best Pearson correlation between the first decoded frame and any
    # frame of the last 1.0 s. ~1 = the video ends on (or returns to) its opening image.
    f0 = fr[0].ravel() - fr[0].mean()
    tail = fr[-MOTION_FPS:]
    cors = [float(np.dot(f0, (x.ravel() - x.mean())) / (np.linalg.norm(f0) * np.linalg.norm(x.ravel() - x.mean()) + 1e-6)) for x in tail]
    motion_series.loop_corr = max(cors) if cors else None
    return t, d, speed


def motion_stats(t, d, cuts, speed=None):
    # "within-shot" excludes frame pairs within 1/15 s of a detected cut, so it
    # measures camera/art motion (Ken Burns, video clips, shakes) not edits.
    near_cut = np.zeros_like(d, dtype=bool)
    for c in cuts:
        near_cut |= np.abs(t - c) <= 1.5 / MOTION_FPS
    win = d[~near_cut] if (~near_cut).any() else d
    first3 = t <= 3.0
    first3_in = first3 & ~near_cut
    sp = {}
    if speed is not None:
        sw = speed[~near_cut] if (~near_cut).any() else speed
        sp = {
            "speed_pct_w_per_s_median": r3(np.median(sw)),
            "speed_pct_w_per_s_0_3s": r3(np.median(speed[first3_in])) if first3_in.any() else None,
            # share of time the picture moves faster than 20 % of frame width / s
            # (whips, fast pans, shakes, animation); slow Ken Burns stays well below
            "fast_motion_frac": r3((sw > 20).mean()),
        }
    return {
        **sp,
        "motion_mean_all": r3(d.mean()),
        "motion_mean_0_3s": r3(d[first3].mean()) if first3.any() else None,
        "motion_within_shot_all": r3(win.mean()),
        "motion_within_shot_0_3s": r3(d[first3_in].mean()) if first3_in.any() else None,
        "motion_median_all": r3(np.median(d)),
        # share of 1/15 s steps where the picture is practically frozen
        # (apparent speed < 1 % of frame width per second, or no pixel change)
        "static_frac_all": r3(((d < 0.5) | (speed < 1.0)).mean()) if speed is not None else r3((d < 0.5).mean()),
        "static_frac_0_3s": (r3(((d[first3] < 0.5) | (speed[first3] < 1.0)).mean()) if speed is not None
                             else r3((d[first3] < 0.5).mean())) if first3.any() else None,
    }


# --------------------------------------------------------------------------- block matching
BM_W, BM_H, BM_B, BM_S, BM_LAG = 108, 192, 12, 12, 3   # 15 fps decode, compare frames 0.2 s apart


def block_motion(path):
    """Integer block matching between frames 0.2 s apart (108x192 gray, 12x12 blocks,
    search +-12 px). Returns per-pair: median block displacement as % frame width / s
    (quantum 4.6 %/s, cap ~55 %/s) and the share of textured blocks that NO shift
    explains (best SAD > 0.6 x block std). Pans/zooms are explained by a shift; a cut
    or a whip/glitch transition to a new image is not. Used for (a) a second, noise-
    robust speed estimate and (b) detecting image changes that ffmpeg's scene score
    misses (blur-whip transitions)."""
    raw = run([FFMPEG, "-v", "error", "-i", str(path), "-an", "-vf",
               f"fps={MOTION_FPS},scale={BM_W}:{BM_H}:flags=area,format=gray",
               "-f", "rawvideo", "-pix_fmt", "gray", "-"], binary=True)
    fr = np.frombuffer(raw, np.uint8).reshape(-1, BM_H, BM_W).astype(np.float32)
    S, B = BM_S, BM_B
    ts, sp, un = [], [], []
    for i in range(0, len(fr) - BM_LAG, BM_LAG):
        a, b = fr[i], fr[i + BM_LAG]
        ac = a[S:BM_H - S, S:BM_W - S]
        ny, nx = ac.shape[0] // B, ac.shape[1] // B
        ac = ac[:ny * B, :nx * B]
        best = np.full((ny, nx), np.inf)
        bd = np.zeros((ny, nx))
        for dy in range(-S, S + 1):
            for dx in range(-S, S + 1):
                bc = b[S + dy:S + dy + ny * B, S + dx:S + dx + nx * B]
                sad = np.abs(ac - bc).reshape(ny, B, nx, B).mean(axis=(1, 3))
                m = sad < best
                best[m] = sad[m]
                bd[m] = math.hypot(dx, dy)
        sd = ac.reshape(ny, B, nx, B).std(axis=(1, 3))
        ok = sd > 6
        ts.append((i + BM_LAG / 2) / MOTION_FPS)
        if ok.sum() < 6:
            sp.append(np.nan)
            un.append(np.nan)
            continue
        sp.append(np.median(bd[ok]) * MOTION_FPS / BM_LAG / BM_W * 100)
        un.append(float(np.mean(best[ok] / (sd[ok] + 1e-3) > 0.6)))
    return np.array(ts), np.array(sp), np.array(un)


def change_events(ts, un, hi=0.5, lo=0.25):
    ev, armed = [], True
    for t, v in zip(ts, un):
        if np.isnan(v):
            continue
        if armed and v > hi:
            ev.append(float(t))
            armed = False
        elif not armed and v < lo:
            armed = True
    return ev


def merge_events(a, b, gap=0.5):
    out = []
    for t in sorted(a + b):
        if not out or t - out[-1] >= gap:
            out.append(t)
    return out


# --------------------------------------------------------------------------- audio
def ebur128(path, ss=None, t=None):
    cmd = [FFMPEG, "-hide_banner", "-nostats"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    if t is not None:
        cmd += ["-t", str(t)]
    cmd += ["-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]
    _, err = run(cmd)
    summ = err[err.rfind("Summary:"):]
    def grab(pat):
        m = re.search(pat, summ)
        return float(m.group(1)) if m else None
    return {"I": grab(r"I:\s+(-?[\d.]+|-inf) LUFS"),
            "LRA": grab(r"LRA:\s+(-?[\d.]+) LU"),
            "TP": grab(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS")}


def audio_envelope(path, sr=16000, win=0.02):
    raw = run([FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr),
               "-f", "f32le", "-"], binary=True)
    x = np.frombuffer(raw, np.float32)
    n = int(sr * win)
    m = len(x) // n
    if m == 0:
        return np.array([]), np.array([])
    rms = np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    return np.arange(m) * win, db


def audio_onset_stats(et, edb):
    if len(edb) == 0:
        return {}
    first = lambda thr: next((float(t) for t, v in zip(et, edb) if v > thr), None)
    head = edb[et < 0.1]
    gaps = edb < -45  # silence-ish windows
    return {
        "rms_db_first_100ms": r3(10 * np.log10(np.mean(10 ** (head / 10)))) if len(head) else None,
        "audio_starts_at_0": bool(len(head) and head.max() > -45.0),
        "first_sound_s": r3(first(-40.0)),
        "silent_frac": r3(gaps.mean()),
        # Level floor: 5th percentile of 20 ms RMS. Voice-only tracks drop to
        # < -50 dBFS in pauses; a continuous music/SFX bed keeps the floor high.
        # floor_gap_db = median - p05 (small gap = always something playing).
        "rms_db_p05": r3(np.percentile(edb, 5)),
        "rms_db_p50": r3(np.percentile(edb, 50)),
        "floor_gap_db": r3(np.percentile(edb, 50) - np.percentile(edb, 5)),
    }


# --------------------------------------------------------------------------- srt
def parse_srt(p):
    txt = Path(p).read_text(encoding="utf-8", errors="replace")
    cues = []
    for block in re.split(r"\n\s*\n", txt.strip()):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", block)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        text = " ".join(block[m.end():].split())
        cues.append((s, e, text))
    return cues


def srt_stats(cues, dur):
    if not cues:
        return {}
    words = sum(len(c[2].split()) for c in cues)
    span = cues[-1][1] - cues[0][0]
    w3 = 0.0
    for s, e, tx in cues:  # words spoken before 3 s, prorated inside a cue
        if s < 3.0 and e > s:
            w3 += len(tx.split()) * (min(e, 3.0) - s) / (e - s)
    full = " ".join(c[2] for c in cues)
    m = re.match(r"(.+?[.?!])(\s|$)", full)
    return {
        "srt_words": words,
        "srt_first_cue_s": r3(cues[0][0]),
        "srt_last_cue_end_s": r3(cues[-1][1]),
        "words_per_s_speech": r3(words / span) if span > 0 else None,
        "words_per_s_duration": r3(words / dur),
        "words_first_3s": r3(w3),
        "speech_cover_frac": r3(sum(e - s for s, e, _ in cues) / dur),
        "hook_sentence": (m.group(1) if m else full[:200]).strip(),
    }


# --------------------------------------------------------------------------- frames
def grab_frame(path, t, w=WORK_W, h=WORK_H, gray=False):
    pix = "gray" if gray else "rgb24"
    raw = run([FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
               "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", pix, "-"], binary=True)
    c = 1 if gray else 3
    if len(raw) < w * h * c:  # past the end: back off
        if t > 0.2:
            return grab_frame(path, t - 0.2, w, h, gray)
        return None
    a = np.frombuffer(raw[: w * h * c], np.uint8)
    return a.reshape(h, w) if gray else a.reshape(h, w, 3)


def laplacian_var_tiles(g, rows=16, cols=6):
    """Classify tiles of a 360x640 gray frame as sharp / blurred / black.

    METHOD: 4-neighbour Laplacian (high-pass) on the gray frame; per tile we take
    its variance. Real line art, text and photographed detail have strong edges
    -> high variance. A Gaussian-blurred "contain" background or a flat fill has
    almost no high-frequency energy -> low variance. Near-black, low-std tiles are
    counted as black bars.
    LIMITS: (1) flat but real art (sky, a flat-coloured wall, a dark night panel)
    reads as "blurred" -> underestimates art; (2) a sharp caption, sticker,
    mascot or watermark on top of a blurred band makes that tile "sharp" ->
    overestimates art; (3) heavy compression smears fine detail, so the absolute
    threshold is only valid at the same proxy quality (see PARITY NOTE); (4) a
    tile grid of 6x16 only resolves padding thicker than ~40 px of 640.
    Treat the number as +-10 percentage points; confirm on the sheets by eye.
    """
    g = g.astype(np.float32)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    H, W = lap.shape
    th, tw = H // rows, W // cols
    lab = np.empty((rows, cols), dtype="<U5")
    for r in range(rows):
        for c in range(cols):
            tile_g = g[1 + r * th: 1 + (r + 1) * th, 1 + c * tw: 1 + (c + 1) * tw]
            tile_l = lap[r * th:(r + 1) * th, c * tw:(c + 1) * tw]
            if tile_g.mean() < BLACK_MEAN and tile_g.std() < BLACK_STD:
                lab[r, c] = "black"
            elif tile_l.var() >= SHARP_LAPVAR:
                lab[r, c] = "sharp"
            else:
                lab[r, c] = "blur"
    return lab


def _frame_stats(f):
    g = (0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2])
    lab = laplacian_var_tiles(g)
    fx = f.astype(np.float32) / 255
    mx, mn = fx.max(axis=2), fx.min(axis=2)
    return {"sharp": (lab == "sharp").mean(), "blur": (lab == "blur").mean(), "black": (lab == "black").mean(),
            "rows": ((lab == "sharp").mean(axis=1) >= 0.5).mean(),
            "sat": float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0).mean()),
            "con": float(g.std()), "lum": float(g.mean())}


def framing_stats(path, dur):
    """Framing/colour on one frame per second (whole video) and on 7 frames in 0-3 s.
    (v2: was 12 evenly spaced frames, which under-sampled short letterboxed stretches.)"""
    raw = run([FFMPEG, "-v", "error", "-i", str(path), "-an", "-vf", f"fps=1,scale={WORK_W}:{WORK_H}",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], binary=True)
    frs = np.frombuffer(raw, np.uint8).reshape(-1, WORK_H, WORK_W, 3)
    st = [_frame_stats(f) for f in frs]
    hook = [_frame_stats(f) for f in (grab_frame(path, t) for t in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)) if f is not None]
    med = lambda a: r3(statistics.median(a)) if a else None
    col = lambda L, k: [x[k] for x in L]
    sharp = col(st, "sharp")
    return {
        "sharp_frac_med": med(sharp),
        "blur_frac_med": med(col(st, "blur")),
        "black_frac_med": med(col(st, "black")),
        "sharp_rows_frac_med": med(col(st, "rows")),
        "sharp_frac_min": r3(min(sharp)) if sharp else None,
        # share of seconds where less than 70 % of the frame is sharp art (letterbox/blur/black padding)
        "padded_time_frac": r3(np.mean(np.array(sharp) < 0.7)) if sharp else None,
        "sharp_frac_0_3s": med(col(hook, "sharp")),
        "luma_mean_0_3s": med(col(hook, "lum")),
        "saturation_0_3s": med(col(hook, "sat")),
        # share of seconds that are dark (mean luma < 50 of 255)
        "dark_time_frac": r3(np.mean(np.array(col(st, "lum")) < 50)) if st else None,
        "saturation_med": med(col(st, "sat")),
        "contrast_std_med": med(col(st, "con")),
        "luma_mean_med": med(col(st, "lum")),
        "framing_sharp_per_second": [r3(x) for x in sharp],
    }


# --------------------------------------------------------------------------- sheets
def font(size):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def tile(path, t, w, h, label, fsize):
    f = grab_frame(path, t, w, h)
    im = Image.fromarray(f) if f is not None else Image.new("RGB", (w, h), (60, 0, 0))
    d = ImageDraw.Draw(im)
    fnt = font(fsize)
    bb = d.textbbox((0, 0), label, font=fnt)
    d.rectangle([0, 0, bb[2] + 8, bb[3] + 6], fill=(0, 0, 0))
    d.text((4, 2), label, font=fnt, fill=(255, 255, 0))
    return im


def grid(tiles, cols, gap=4, bg=(40, 40, 40)):
    w, h = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    out = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), bg)
    for i, im in enumerate(tiles):
        r, c = divmod(i, cols)
        out.paste(im, (gap + c * (w + gap), gap + r * (h + gap)))
    return out


def make_sheets(path, vid, dur, outdir):
    hook = [tile(path, t, 270, 480, f"{vid} t={t:.1f}s", 16) for t in HOOK_TIMES]
    grid(hook, len(hook)).save(outdir / f"hook_{vid}.jpg", quality=88)
    ends = [max(0.0, dur - x) for x in (3.0, 2.0, 1.0, 0.3)]  # not closer than 0.3 s: seeking past
    # the last video frame can return a frame from the START (seen on a YouTube file)
    endt = [tile(path, t, 270, 480, f"{vid} end t={t:.1f}s", 16) for t in ends]
    endt.append(tile(path, 0.0, 270, 480, f"{vid} FIRST t=0.0 (loop?)", 16))
    grid(endt, len(endt)).save(outdir / f"end_{vid}.jpg", quality=88)
    ts = [i * SHEET_STEP for i in range(int(dur // SHEET_STEP) + 1) if i * SHEET_STEP < dur - 0.3]
    tiles = [tile(path, t, 180, 320, f"{vid} {t:.0f}s", 13) for t in ts]
    grid(tiles, 10).save(outdir / f"sheet_{vid}.jpg", quality=85)
    if len(tiles) > 40:
        for p in range(math.ceil(len(tiles) / 40)):
            grid(tiles[p * 40:(p + 1) * 40], 10).save(outdir / f"sheet_{vid}_p{p + 1}.jpg", quality=85)


# --------------------------------------------------------------------------- main
def find_srt(mp4, srt_dirs):
    vid = mp4.stem
    cands = [mp4.with_suffix(".srt"), mp4.parent.parent / "transcripts" / f"{vid}.srt"]
    cands += [Path(d) / f"{vid}.srt" for d in srt_dirs]
    return next((c for c in cands if c.exists()), None)


def load_manifest(p):
    if not p:
        return {}
    rows = {}
    with open(p, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("id"):
                rows[r["id"]] = r
    return rows


def analyse(mp4, args, man, tmpdir, outdir):
    vid = mp4.stem
    src = probe(mp4)
    work = mp4
    normalized = False
    if args.normalize and src["height"] and src["height"] > WORK_H:
        work = normalized_proxy(mp4, tmpdir)
        normalized = True
    dur = src["duration_s"]
    res = {"id": vid, "label": args.label, "file": str(mp4), "analysed_proxy_360p": normalized}
    res.update({k: (r3(v) if isinstance(v, float) else v) for k, v in src.items()})
    meta = man.get(vid, {})
    for k in ("channel", "title", "view_count", "upload_date"):
        if meta.get(k):
            res[k] = meta[k]

    times, scores = scene_scores(work)
    cuts = cuts_from_scores(times, scores, args.scene_thr)
    res["scene_threshold"] = args.scene_thr
    res.update(cut_stats(cuts, dur))
    # sensitivity: cut counts at neighbouring thresholds
    for thr in (0.2, 0.4):
        res[f"n_cuts_thr{int(thr * 100)}"] = len(cuts_from_scores(times, scores, thr))
    res["cut_times"] = [r3(c) for c in cuts]

    mt, md, msp = motion_series(work)
    res.update(motion_stats(mt, md, cuts, msp))
    bt, bsp, bun = block_motion(work)
    ok3 = bt <= 3.0
    res["speed_bm_median"] = r3(np.nanmedian(bsp)) if np.isfinite(bsp).any() else None
    res["speed_bm_0_3s"] = r3(np.nanmedian(bsp[ok3])) if np.isfinite(bsp[ok3]).any() else None
    res["speed_bm_still_frac"] = r3(np.nanmean(bsp < 1.0)) if np.isfinite(bsp).any() else None
    # IMAGE CHANGES = ffmpeg scene cuts UNION motion-compensated change events (whips,
    # glitch or slide transitions that the scene score misses); events < 0.5 s apart merge.
    # A scene cut is kept only if block matching cannot explain it by motion (fast pans
    # create false scene cuts: a synthetic 50 %/s pan gave 10 "cuts" in 4 s).
    def unexplained_near(c):
        w = np.abs(bt - c) <= 0.25
        v = bun[w][np.isfinite(bun[w])]
        return True if len(v) == 0 else v.max() > 0.35
    real_cuts = [c for c in cuts if unexplained_near(c)]
    res["n_cuts_motion_explained"] = len(cuts) - len(real_cuts)
    chg = merge_events(real_cuts, change_events(bt, bun))
    st = cut_stats(chg, dur)
    res.update({"image_changes": st["n_cuts"], "image_changes_per_10s": st["cuts_per_10s"],
                "median_image_hold_s": st["median_shot_s"], "first_image_change_s": st["first_cut_s"],
                "image_changes_first_3s": st["cuts_first_3s"], "image_changes_first_5s": st["cuts_first_5s"]})
    res["image_change_times"] = [r3(c) for c in chg]

    if src["has_audio"]:
        full, head, rest = ebur128(work), ebur128(work, t=2), ebur128(work, ss=2)
        res.update({"lufs_I": full["I"], "lra_LU": full["LRA"], "true_peak_dbtp": full["TP"],
                    "lufs_first_2s": head["I"], "lufs_after_2s": rest["I"]})
        if head["I"] is not None and rest["I"] is not None:
            res["lufs_first2_minus_rest"] = r3(head["I"] - rest["I"])
        et, edb = audio_envelope(work)
        res.update(audio_onset_stats(et, edb))
    srt = find_srt(mp4, args.srt_dir)
    res["srt_path"] = str(srt) if srt else None
    if srt:
        res.update(srt_stats(parse_srt(srt), dur))
    res.update(framing_stats(work, dur))
    res["loop_first_last_corr"] = r3(motion_series.loop_corr)

    # 0.5 s time series for later plots
    def series(t, v, step=0.5, agg=np.mean):
        n = int(math.ceil(dur / step))
        return [r3(agg(v[(t >= i * step) & (t < (i + 1) * step)])) if ((t >= i * step) & (t < (i + 1) * step)).any() else None for i in range(n)]
    res["series_step_s"] = 0.5
    res["series_motion"] = series(mt, md)
    res["series_speed"] = series(mt, msp, agg=np.median)
    res["series_unexplained_change"] = series(bt[np.isfinite(bun)], bun[np.isfinite(bun)])
    if src["has_audio"]:
        res["series_rms_db"] = series(et, edb)

    if not args.no_sheets:
        make_sheets(work, vid, dur, outdir)
    return res


SCALAR_ORDER = ["label", "channel", "id", "title", "view_count", "upload_date", "duration_s", "width", "height",
                "fps", "bitrate_kbps", "analysed_proxy_360p", "scene_threshold", "n_cuts", "n_cuts_thr20",
                "n_cuts_thr40", "cuts_per_10s", "mean_shot_s", "median_shot_s", "max_shot_s", "first_cut_s",
                "cuts_first_3s", "cuts_first_5s", "n_cuts_motion_explained", "image_changes", "image_changes_per_10s", "median_image_hold_s",
                "first_image_change_s", "image_changes_first_3s", "image_changes_first_5s", "speed_bm_0_3s",
                "speed_bm_median", "speed_bm_still_frac", "motion_mean_0_3s", "motion_mean_all", "motion_within_shot_0_3s",
                "motion_within_shot_all", "motion_median_all", "speed_pct_w_per_s_0_3s", "speed_pct_w_per_s_median", "fast_motion_frac", "static_frac_0_3s", "static_frac_all", "lufs_I",
                "lra_LU", "true_peak_dbtp", "lufs_first_2s", "lufs_after_2s", "lufs_first2_minus_rest",
                "rms_db_first_100ms", "audio_starts_at_0", "first_sound_s", "silent_frac", "rms_db_p05", "rms_db_p50", "floor_gap_db", "srt_words",
                "srt_first_cue_s", "words_per_s_speech", "words_per_s_duration", "words_first_3s",
                "speech_cover_frac", "sharp_frac_med", "blur_frac_med", "black_frac_med", "sharp_rows_frac_med",
                "sharp_frac_min", "padded_time_frac", "sharp_frac_0_3s", "luma_mean_0_3s", "saturation_0_3s",
                "dark_time_frac", "loop_first_last_corr", "saturation_med", "contrast_std_med", "luma_mean_med", "hook_sentence"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="folder(s) (searched recursively for *.mp4) or mp4 files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--srt-dir", action="append", default=[], help="extra folder(s) holding <id>.srt")
    ap.add_argument("--manifest", help="CSV with an 'id' column (+ channel,title,view_count,upload_date)")
    ap.add_argument("--scene-thr", type=float, default=0.30, help="ffmpeg scene score threshold (0-1)")
    ap.add_argument("--no-normalize", dest="normalize", action="store_false")
    ap.add_argument("--no-sheets", action="store_true")
    args = ap.parse_args()

    files = []
    for i in args.inputs:
        p = Path(i)
        files += sorted(p.rglob("*.mp4")) if p.is_dir() else [p]
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    man = load_manifest(args.manifest)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            print(f"[vmetrics] {f}", file=sys.stderr)
            try:
                res = analyse(f, args, man, tmp, outdir)
            except Exception as e:  # keep going, record the error
                print(f"  ERROR {e}", file=sys.stderr)
                continue
            (outdir / f"{res['id']}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
            rows.append(res)
        if rows and not args.no_sheets:
            tiles = []
            for r in rows:
                src = Path(r["file"])
                work = src
                if r["analysed_proxy_360p"]:
                    work = normalized_proxy(src, tmp)
                tag = r["id"] + (f" {int(r['view_count']):,}v" if str(r.get("view_count", "")).isdigit() else "")
                tiles += [tile(work, 0.0, 216, 384, f"{tag} t=0.0", 13), tile(work, 1.0, 216, 384, f"{r['id']} t=1.0", 13)]
            grid(tiles, 10).save(outdir / f"hooks_all_{args.label}.jpg", quality=88)
    with open(outdir / f"metrics_{args.label}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SCALAR_ORDER, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[vmetrics] {len(rows)} videos -> {outdir}", file=sys.stderr)


if __name__ == "__main__":
    main()
