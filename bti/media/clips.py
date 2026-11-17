"""Video by URL: metadata, licence gate, section download, H.264 30 fps, contact sheet.

Adapted from comic-book-pipeline/stages/clip_fetch.py (read-only source): _ytdlp_cmd,
ytdlp_section_args, _kill_tree, _run_capture, DownloadTimeout, _ytdlp_error, normalize,
sheet_times, contact_sheet. Changes: no `config` import, no `.env` reading, no writes
outside the project (cache is `<project>/cache/clips/`), 16:9 friendly normalisation,
and a licence gate in front of every download.

The module imports fine without yt-dlp; `ToolMissing` is raised on use.
Only a licence of Creative Commons (or public domain) passes. The standard YouTube
licence is rejected.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import assets as _assets
from ..proc import group_kwargs, kill_tree
from .errors import LicenceRejected, MediaError
from .licence import check_licence

_YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")
SECTION_TIMEOUT = float(os.getenv("CLIP_SECTION_TIMEOUT", "180"))
META_TIMEOUT = 120


class ToolMissing(MediaError):
    """yt-dlp or ffmpeg is not installed."""


class DownloadTimeout(MediaError):
    """A yt-dlp/ffmpeg run that did not finish in time (and was killed)."""


# --------------------------------------------------------------------------- tools

def _ytdlp_cmd() -> list[str]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import importlib.util
        if importlib.util.find_spec("yt_dlp"):
            return [sys.executable, "-m", "yt_dlp"]
    except (ImportError, ValueError):
        pass
    raise ToolMissing("yt-dlp is not installed (pip install yt-dlp); clips need it")


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise ToolMissing("ffmpeg is not installed or not on PATH")
    return exe


def _ffprobe() -> str:
    exe = shutil.which("ffprobe")
    if not exe:
        raise ToolMissing("ffprobe is not installed or not on PATH")
    return exe


def _kill_tree(proc: subprocess.Popen) -> None:
    kill_tree(proc, grace=0)


def _run_capture(cmd: list[str], *, timeout: float | None) -> subprocess.CompletedProcess:
    """subprocess with a real timeout that kills the whole process tree."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", **group_kwargs())
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise DownloadTimeout(f"no result after {timeout:.0f}s, killed")
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _ytdlp_error(res) -> str:
    text = (res.stderr or "") + "\n" + (res.stdout or "")
    errs = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("ERROR")]
    msg = " | ".join(errs)[-400:] or " ".join(text.split())[-400:]
    if "older than 90 days" in text and ("ffmpeg exited" in text or "403" in text):
        msg += " (this yt-dlp is outdated: pip install -U yt-dlp)"
    return msg


# --------------------------------------------------------------------------- metadata + gate

def video_id(url: str) -> str | None:
    m = _YT_ID.search(url or "")
    return m.group(1) if m else None


def video_metadata(url: str, *, timeout: int = META_TIMEOUT) -> dict:
    """yt-dlp info dict, no download. Raises when the info cannot be read."""
    cmd = [*_ytdlp_cmd(), "--skip-download", "--no-playlist", "--dump-single-json", url]
    res = _run_capture(cmd, timeout=timeout)
    try:
        return json.loads(res.stdout or "")
    except ValueError:
        raise MediaError(f"no metadata ({' '.join((res.stderr or '').split())[-160:] or 'private, removed or blocked?'})") from None


def clip_licence(info: dict) -> tuple[bool, str, str]:
    """Gate yt-dlp metadata: the `license` field must say Creative Commons (or PD).
    A missing field or the standard YouTube licence is rejected."""
    return check_licence({"license": (info or {}).get("license") or ""})


# --------------------------------------------------------------------------- download + normalise

def ytdlp_section_args(url: str, out_dir: Path, *, start: float, end: float,
                       max_height: int = 1080) -> list[str]:
    if end <= start:
        raise ValueError("end must be after start")
    fmt = f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b"
    return [*_ytdlp_cmd(), "--no-playlist", "-f", fmt,
            "--download-sections", f"*{start:.2f}-{end:.2f}", "--force-keyframes-at-cuts",
            "--force-overwrites", "--merge-output-format", "mp4", "--write-info-json",
            "--no-progress", "-o", str(Path(out_dir) / f"%(id)s_sec_{start:.1f}_{end:.1f}.%(ext)s"),
            "--print", "after_move:filepath", url]


def probe_video(path: Path) -> dict:
    res = subprocess.run([_ffprobe(), "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    try:
        d = json.loads(res.stdout)
        st = d["streams"][0]
        return {"width": int(st["width"]), "height": int(st["height"]),
                "duration": float(d["format"]["duration"])}
    except (ValueError, KeyError, IndexError):
        raise MediaError(f"cannot probe {path}") from None


def normalize(src: Path, out: Path, *, max_short_side: int = 1080) -> Path:
    """H.264 yuv420p, constant 30 fps, short side <= max_short_side, AAC if audio exists."""
    info = probe_video(src)
    w, h = info["width"], info["height"]
    k = min(1.0, max_short_side / min(w, h))
    tw, th = max(2, int(round(w * k / 2)) * 2), max(2, int(round(h * k / 2)) * 2)
    tmp = out.with_name(out.stem + ".part.mp4")
    cmd = [_ffmpeg(), "-y", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?",
           "-vf", f"fps=30,scale={tw}:{th}:flags=lanczos,setsar=1,format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise MediaError(f"transcode failed: {(res.stderr or '')[-600:]}")
    tmp.replace(out)
    return out


def sheet_times(duration: float, *, every: float, start: float = 0.0, end: float | None = None,
                max_frames: int = 120) -> tuple[list[float], float]:
    end = duration if end is None else min(end, duration)
    span = max(0.0, end - start)
    step = max(every, 0.04)
    if span / step + 1 > max_frames:
        step = span / max_frames
    n = int(math.floor(span / step + 1e-9)) + 1
    return [round(start + k * step, 3) for k in range(n) if start + k * step < duration], step


def contact_sheet(video: Path, out: Path, *, every: float = 2.0, cols: int = 6, thumb_w: int = 320) -> Path:
    """Grid of frames every `every` seconds, each labelled with its time (PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    info = probe_video(video)
    times, step = sheet_times(info["duration"], every=every)
    if not times:
        raise MediaError(f"nothing to sample in {video}")
    with tempfile.TemporaryDirectory() as td:
        cmd = [_ffmpeg(), "-y", "-v", "error", "-i", str(video),
               "-vf", f"fps=1/{step:.4f},scale={thumb_w}:-2",
               "-frames:v", str(len(times)), str(Path(td) / "f_%04d.png")]
        res = subprocess.run(cmd, capture_output=True, text=True)
        frames = sorted(Path(td).glob("f_*.png"))
        if res.returncode != 0 or not frames:
            raise MediaError(f"contact sheet frames failed: {(res.stderr or '')[-400:]}")
        thumbs = [Image.open(f).convert("RGB") for f in frames]
    try:
        font = ImageFont.load_default(size=16)
    except TypeError:
        font = ImageFont.load_default()
    th = thumbs[0].height
    label_h, pad, head_h = 24, 6, 30
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (pad + cols * (thumb_w + pad), head_h + rows * (th + label_h + pad)), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 8), f"{video.name} every {step:.2f}s ({info['width']}x{info['height']}, "
              f"{info['duration']:.1f}s)", fill=(255, 255, 255), font=font)
    for k, (img, t) in enumerate(zip(thumbs, times)):
        r, c = divmod(k, cols)
        x, y = pad + c * (thumb_w + pad), head_h + r * (th + label_h + pad)
        sheet.paste(img, (x, y))
        draw.text((x + 2, y + th + 3), f"{t:.2f}s", fill=(255, 220, 0), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


# --------------------------------------------------------------------------- pipeline

def fetch_section(project_dir: Path, url: str, start: float, end: float, *, info: dict | None = None,
                  sheet: bool = True, max_height: int = 1080) -> dict:
    """Gate, download one section, normalise, contact sheet. Everything lands in
    `<project>/cache/clips/`. Returns {id, file, sheet, info, licence, credit}.
    Raises LicenceRejected BEFORE any download."""
    info = info or video_metadata(url)
    ok, name, reason = clip_licence(info)
    if not ok:
        raise LicenceRejected(reason, name)
    cache = Path(project_dir) / "cache" / "clips"
    raw_dir = cache / "src"
    raw_dir.mkdir(parents=True, exist_ok=True)
    vid = info.get("id") or video_id(url) or "clip"
    out = cache / f"{vid}_{start:.1f}_{end:.1f}.mp4"
    if not out.is_file():
        res = _run_capture(ytdlp_section_args(url, raw_dir, start=start, end=end, max_height=max_height),
                           timeout=SECTION_TIMEOUT)
        lines = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip()]
        raw = Path(lines[-1]) if lines else None
        if res.returncode != 0 or raw is None or not raw.is_file():
            raise MediaError(f"yt-dlp failed (exit {res.returncode}): {_ytdlp_error(res)}")
        normalize(raw, out)
    sheet_path = contact_sheet(out, cache / f"{out.stem}_sheet.jpg") if sheet else None
    credit = {"source": "youtube" if "youtu" in url else "web",
              "source_url": info.get("webpage_url") or url,
              "author": info.get("channel") or info.get("uploader") or "unknown",
              "licence": name, "licence_url": ""}
    return {"id": vid, "file": str(out), "sheet": str(sheet_path) if sheet_path else "",
            "info": {k: info.get(k) for k in ("id", "title", "channel", "duration", "license")},
            "licence": name, "credit": credit}


def import_clip(project_dir: Path, url: str, start: float, end: float, *, info: dict | None = None) -> dict:
    """Fetch a section and return `{"asset_key", "asset"}` like api.import_candidate."""
    project_dir = Path(project_dir)
    r = fetch_section(project_dir, url, start, end, info=info)
    p = probe_video(Path(r["file"]))
    ident = f"clip:{r['id']}:{start:.1f}-{end:.1f}"
    idx = _assets.load_index(project_dir)
    key = _assets.make_key(r["info"].get("title") or r["id"], ident, _assets.taken_keys(project_dir, idx))
    dest = _assets.media_dir(project_dir) / f"{key}.mp4"
    shutil.copyfile(r["file"], dest)
    asset = _assets.build_asset(f"media/{dest.name}", "video", r["info"].get("title") or "",
                                r["credit"]["author"], "", p["width"], p["height"], r["credit"])
    _assets.register(project_dir, ident, key, asset)
    return {"asset_key": key, "asset": asset}
