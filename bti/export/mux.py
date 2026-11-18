"""Build ffmpeg commands to join video and mux audio and chapter metadata."""
from __future__ import annotations

import re


def _q(path) -> str:
    """A path inside a concat list file: single-quoted, with `'` written as `'\\''`."""
    return "'" + str(path).replace("\\", "/").replace("'", "'\\''") + "'"


def concat_list(files) -> str:
    return "".join("file %s\n" % _q(f) for f in files)


def join_command(ffmpeg: list[str], list_file, out) -> list[str]:
    """Parts have the same encoding, so they join without re-encoding."""
    return [*ffmpeg, "-y", "-v", "error", "-nostdin", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)]


def pretty_chapter(name: str) -> str:
    """`COLD_OPEN` -> `Cold Open`; a name that already has lower-case letters is kept."""
    n = re.sub(r"\s+", " ", str(name or "").replace("_", " ")).strip()
    if n and n == n.upper():
        n = n.title()
    return n


def chapter_marks(chapters, duration: float) -> list[dict]:
    """`[{title, start, end}]` in seconds from `timing.chapters`: the first mark starts at 0 (players and YouTube need that),
    every mark ends where the next starts, the last at `duration`. Chapters are sorted and cut to the video."""
    rows = []
    for c in chapters or []:
        if isinstance(c, dict) and isinstance(c.get("start"), (int, float)):
            rows.append((float(c["start"]), pretty_chapter(c.get("name") or c.get("title") or "")))
    rows = sorted((s, t) for s, t in rows if 0 <= s < duration)
    if not rows:
        return []
    rows[0] = (0.0, rows[0][1])
    out = []
    for k, (s, t) in enumerate(rows):
        e = rows[k + 1][0] if k + 1 < len(rows) else duration
        if e > s:
            out.append({"title": t or "Chapter %d" % (k + 1), "start": s, "end": e})
    return out


def _meta(s: str) -> str:
    """Escapes a value for an ffmetadata file."""
    return re.sub(r"([=;#\\\n])", lambda m: "\\n" if m.group(1) == "\n" else "\\" + m.group(1), str(s))


def ffmetadata(chapters, title: str = "") -> str:
    """The text of an ffmetadata file with the chapter marks (milliseconds)."""
    out = [";FFMETADATA1"]
    if title:
        out.append("title=" + _meta(title))
    for c in chapters:
        out += ["[CHAPTER]", "TIMEBASE=1/1000", "START=%d" % round(c["start"] * 1000), "END=%d" % round(c["end"] * 1000), "title=" + _meta(c["title"])]
    return "\n".join(out) + "\n"


def mux_command(ffmpeg: list[str], video, audio, meta, out, duration: float, *, audio_copy: bool = True, language: str = "eng") -> list[str]:
    """Copy video, add audio and chapter marks, and enable fast start."""
    cmd = [*ffmpeg, "-y", "-v", "error", "-nostdin",
           "-i", str(video), "-i", str(audio), "-i", str(meta),
           "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "2", "-map_chapters", "2",
           "-c:v", "copy"]
    cmd += ["-c:a", "copy"] if audio_copy else ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-metadata:s:a:0", "language=" + language,
            "-movflags", "+faststart", "-t", "%.3f" % duration, str(out)]
    return cmd


MIN_CHAPTER = 10.0


def merge_short(marks, min_len: float = MIN_CHAPTER):
    """`(marks, merged)`: a mark shorter than `min_len` joins the previous mark (the first one joins the next), because the
    platform ignores a chapter list that has such a mark. Used for `chapters.txt` and the description only."""
    out = [dict(m) for m in marks]
    merged = 0
    k = 0
    while k < len(out) and len(out) > 1:
        m = out[k]
        if m["end"] - m["start"] < min_len:
            if k > 0:
                out[k - 1]["end"] = m["end"]
                del out[k]
            else:
                out[1]["start"] = m["start"]
                del out[0]
            merged += 1
            k = max(0, k - 1) if k else 0
        else:
            k += 1
    return out, merged
