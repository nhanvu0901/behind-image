"""The report card (design section 8, item 5): what the finished file really is, measured with ffprobe and ffmpeg.

`probe` and `measure_loudness` run the programs; `parse_*` and `report_card` are pure and tested without them.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

LOUDNESS_TARGET = -15.0          # integrated, LUFS (the voice stage's target)
LOUDNESS_TOLERANCE = 1.5
PEAK_LIMIT = -1.0                # dBTP; the voice stage aims for -1.5


class ToolError(Exception):
    """ffprobe or ffmpeg failed or printed something that cannot be read."""


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ToolError("%s: %s" % (Path(cmd[-1]).name, type(e).__name__))


def probe(ffprobe: list[str], path, timeout: float = 120) -> dict:
    """`{duration, size, video: {codec, width, height, fps, frames}, audio: {codec, ...}|None, subtitle: {codec}|None, chapters: [..]}`.
    The frame count is the number of packets of the video stream (one packet is one frame in H.264 without field coding)."""
    cmd = [*ffprobe, "-v", "error", "-count_packets", "-show_format", "-show_streams", "-show_chapters", "-of", "json", str(path)]
    r = _run(cmd, timeout)
    if r.returncode != 0:
        raise ToolError("ffprobe failed: " + r.stderr.decode("utf-8", "replace")[-200:])
    try:
        return parse_probe(json.loads(r.stdout.decode("utf-8", "replace")))
    except ValueError as e:
        raise ToolError("ffprobe printed something that is not JSON") from e


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_probe(doc: dict) -> dict:
    fmt = doc.get("format") or {}
    streams = doc.get("streams") or []

    def first(kind):
        return next((s for s in streams if s.get("codec_type") == kind), None)

    v, a, s = first("video"), first("audio"), first("subtitle")
    out = {"duration": _num(fmt.get("duration")), "size": int(_num(fmt.get("size"))), "video": None, "audio": None, "subtitle": None,
           "chapters": [{"start": _num(c.get("start_time")), "end": _num(c.get("end_time")), "title": (c.get("tags") or {}).get("title", "")} for c in doc.get("chapters") or []]}
    if v:
        num, _, den = str(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").partition("/")
        fps = _num(num) / (_num(den, 1.0) or 1.0)
        frames = v.get("nb_read_packets") or v.get("nb_frames")
        out["video"] = {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"), "fps": round(fps, 3),
                        "frames": int(_num(frames)) if frames is not None else None, "duration": _num(v.get("duration"), out["duration"])}
    if a:
        out["audio"] = {"codec": a.get("codec_name"), "sample_rate": int(_num(a.get("sample_rate"))), "channels": a.get("channels"), "duration": _num(a.get("duration"), out["duration"])}
    if s:
        out["subtitle"] = {"codec": s.get("codec_name"), "language": (s.get("tags") or {}).get("language")}
    return out


def parse_loudness(text: str) -> dict:
    """Reads the summary that `ffmpeg -af ebur128=peak=true` prints at the end: `{lufs, lra, true_peak}` (None when absent)."""
    tail = text[text.rfind("Summary:"):] if "Summary:" in text else text
    def grab(rx):
        m = re.search(rx, tail)
        return float(m.group(1)) if m else None
    return {"lufs": grab(r"\bI:\s+(-?[\d.]+)\s+LUFS"), "lra": grab(r"\bLRA:\s+(-?[\d.]+)\s+LU\b"),
            "true_peak": grab(r"Peak:\s+(-?[\d.]+)\s+dBFS")}


def measure_loudness(ffmpeg: list[str], path, timeout: float = 600) -> dict:
    cmd = [*ffmpeg, "-nostats", "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:a:0", "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]
    r = _run(cmd, timeout)
    if r.returncode != 0:
        raise ToolError("ffmpeg could not measure the loudness")
    m = parse_loudness(r.stderr.decode("utf-8", "replace"))
    if m["lufs"] is None:
        raise ToolError("the loudness summary is missing")
    return m


def _item(key, ok, value, expected=None, level="fail", note=""):
    return {"key": key, "status": "ok" if ok else level, "value": value, "expected": expected, "note": note}


def report_card(info: dict, loud: dict | None, *, expected_frames: int, expected_duration: float, cues: int, fps: int = 30, audio_duration: float | None = None, merged_chapters: int = 0) -> list[dict]:
    """The report card: a list of `{key, status: ok|warn|fail, value, expected, note}`.

    Keys: audio_length (the mix against the video, 0.5 s allowed), chapters_merged, duration, frames, loudness, true_peak, audio, subtitles, cues, chapters, size, video."""
    v, a, s = info.get("video"), info.get("audio"), info.get("subtitle")
    items = []
    items.append(_item("video", bool(v and v.get("codec") == "h264"), (v or {}).get("codec"), "h264"))
    dur = info.get("duration") or 0.0
    items.append(_item("duration", abs(dur - expected_duration) <= 0.5, round(dur, 2), round(expected_duration, 2)))
    frames = (v or {}).get("frames")
    items.append(_item("frames", frames == expected_frames, frames, expected_frames,
                       note="" if frames is None or frames == expected_frames else "%+d" % (frames - expected_frames)))
    items.append(_item("audio", bool(a), (a or {}).get("codec")))
    if audio_duration is not None:
        items.append(_item("audio_length", abs(audio_duration - expected_duration) <= 0.5, round(audio_duration, 2), round(expected_duration, 2),
                           note="%+.2f" % (audio_duration - expected_duration)))
    if loud is None:
        items.append(_item("loudness", False, None, LOUDNESS_TARGET, "warn"))
        items.append(_item("true_peak", False, None, PEAK_LIMIT, "warn"))
    else:
        lu, tp = loud.get("lufs"), loud.get("true_peak")
        items.append(_item("loudness", lu is not None and abs(lu - LOUDNESS_TARGET) <= LOUDNESS_TOLERANCE, lu, LOUDNESS_TARGET, "warn"))
        items.append(_item("true_peak", tp is not None and tp <= PEAK_LIMIT, tp, PEAK_LIMIT, "warn"))
    items.append(_item("subtitles", bool(s) and s.get("codec") == "mov_text", (s or {}).get("codec"), "mov_text"))
    items.append(_item("cues", cues > 0, cues))
    ch = info.get("chapters") or []
    items.append(_item("chapters", len(ch) >= 2, len(ch), None, "warn"))
    items.append(_item("chapters_merged", merged_chapters == 0, merged_chapters, 0, "warn"))
    size = info.get("size") or 0
    items.append(_item("size", size > 0, size))
    return items


def worst(items: list[dict]) -> str:
    st = {i["status"] for i in items}
    return "fail" if "fail" in st else "warn" if "warn" in st else "ok"
