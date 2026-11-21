"""Video by URL and moment discovery: You.com YouTube search, metadata + timing signals,
licence gate (strict or advisory), section download, silent H.264 30 fps, contact sheet.

Adapted from comic-book-pipeline/stages/clip_fetch.py (read-only source): _ytdlp_cmd,
ytdlp_section_args, _kill_tree, _run_capture, DownloadTimeout, _ytdlp_error, normalize,
sheet_times, contact_sheet, parse_search_results, youtube_search, gather_candidates,
parse_vtt, heatmap_peaks, find_moments, score_video, moment_search.
Changes: no `config` import, no direct `.env` parsing (uses bti.script.env.get_key),
no writes outside the project (cache is `<project>/cache/clips/`), muted normalized clips
(-an), and `strict_licence` option (True by default; False records advisory flag in credit).

The module imports fine without yt-dlp; `ToolMissing` is raised on use.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
from .errors import LicenceRejected, MediaError, RealModelsOff
from .licence import check_licence, flag_for_text
from .safety import refuse_if_real_models_off
from .youcom import YouComClient
from bti.fsio import atomic_replace

_YT_PATTERNS = [
    re.compile(r"^(?:https?://)?(?:(?:www|m|music)\.)?youtube\.com/watch\?(?:[a-zA-Z0-9_.~:+-]+=?[a-zA-Z0-9_.~:+-]*&)*v=([A-Za-z0-9_-]{11})(?:&[a-zA-Z0-9_.~:+-]+=?[a-zA-Z0-9_.~:+-]*)*(?:#[a-zA-Z0-9_.~:+-]*)?$", re.I),
    re.compile(r"^(?:https?://)?(?:(?:www|m|music)\.)?youtube\.com/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})(?:\?[a-zA-Z0-9_.~:+-]+=?[a-zA-Z0-9_.~:+-]*)*(?:#[a-zA-Z0-9_.~:+-]*)?$", re.I),
    re.compile(r"^(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_-]{11})(?:\?[a-zA-Z0-9_.~:+-]+=?[a-zA-Z0-9_.~:+-]*)*(?:#[a-zA-Z0-9_.~:+-]*)?$", re.I),
]
_CUE = re.compile(r"(?:(\d+):)?(\d\d):(\d\d)[.,](\d+)\s+-->\s+(?:(\d+):)?(\d\d):(\d\d)[.,](\d+)")
_SUB_LANGS = ("en", "en-US", "en-GB", "en-orig")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "had", "has",
    "have", "he", "her", "his", "in", "into", "is", "it", "its", "of", "on", "or", "she",
    "that", "the", "their", "them", "there", "they", "this", "to", "was", "were", "who",
    "with", "you", "your", "painting", "work", "detail", "scene", "clip", "video",
}
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


def has_ytdlp() -> bool:
    try:
        _ytdlp_cmd()
        return True
    except ToolMissing:
        return False


def tool_status() -> dict:
    """Return whether tools needed for video clips are available, or a stable error code."""
    try:
        _ytdlp_cmd()
        _ffmpeg()
        return {"available": True, "code": None}
    except ToolMissing:
        return {"available": False, "code": "tool_missing"}



def _kill_tree(proc: subprocess.Popen) -> None:
    kill_tree(proc, grace=0)


def _run_capture(cmd: list[str], *, timeout: float | None) -> subprocess.CompletedProcess:
    """subprocess with a real timeout that kills the whole process tree. The only place that starts yt-dlp (the default of
    every `runner` argument): refused under the A7 safety switch."""
    refuse_if_real_models_off("yt-dlp")
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


# --------------------------------------------------------------------------- metadata + moment search

def video_id(url: str) -> str | None:
    """The 11-character YouTube id of a watch/shorts/embed/live/youtu.be URL, else None."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or url.startswith("-"):
        return None
    for pat in _YT_PATTERNS:
        m = pat.fullmatch(url)
        if m:
            return m.group(1)
    return None


def safe_youtube_url(url: str) -> str:
    """Validate and normalize a YouTube URL to canonical 'https://www.youtube.com/watch?v=<id>'.
    Raises ValueError on hostile or unsupported URLs."""
    vid = video_id(url)
    if not vid:
        raise ValueError("not a supported YouTube URL")
    return f"https://www.youtube.com/watch?v={vid}"


def _ytdlp_flags() -> list[str]:
    flags = ["--skip-download", "--no-playlist"]
    if shutil.which("node"):
        flags.extend(["--js-runtimes", "node"])
    return flags


def video_metadata(url: str, *, timeout: int = META_TIMEOUT) -> dict:
    """yt-dlp info dict, no download. Raises when the info cannot be read."""
    canon_url = safe_youtube_url(url)
    cmd = [*_ytdlp_cmd(), *_ytdlp_flags(), "--dump-single-json", "--", canon_url]
    res = _run_capture(cmd, timeout=timeout)
    try:
        return json.loads(res.stdout or "")
    except ValueError:
        raise MediaError(f"no metadata ({' '.join((res.stderr or '').split())[-160:] or 'private, removed or blocked?'})") from None


def video_metadata_with_cues(url: str, work_dir: Path | None = None, *, timeout: int = META_TIMEOUT) -> tuple[dict, list]:
    """(yt-dlp info dict, subtitle cues) WITHOUT downloading the video. Subtitles are fetched
    best-effort only when English captions exist (HTTP 429 on captions never fails the video)."""
    canon_url = safe_youtube_url(url)
    info = video_metadata(canon_url, timeout=timeout)
    langs = [lg for lg in _SUB_LANGS
             if lg in (info.get("subtitles") or {}) or lg in (info.get("automatic_captions") or {})]
    cues: list = []
    if langs:
        td_ctx = tempfile.TemporaryDirectory() if work_dir is None else None
        target_dir = Path(td_ctx.name) if td_ctx else Path(work_dir)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            cmd = [*_ytdlp_cmd(), *_ytdlp_flags(), "--write-subs", "--write-auto-subs",
                   "--sub-langs", langs[0], "--sub-format", "vtt",
                   "-o", str(target_dir / "%(id)s.%(ext)s"), "--", canon_url]
            try:
                _run_capture(cmd, timeout=min(timeout, 45))
            except RealModelsOff:
                raise
            except Exception:
                pass
            vtts = sorted(target_dir.glob("*.vtt"))
            if vtts:
                cues = parse_vtt(vtts[0].read_text(encoding="utf-8", errors="replace"))
        finally:
            if td_ctx is not None:
                td_ctx.cleanup()
    return info, cues


def _ydc_key() -> str:
    key = os.environ.get("YDC_API_KEY", "").strip()
    if key:
        return key
    try:
        from bti.script.env import get_key
        return (get_key("YDC_API_KEY") or "").strip()
    except Exception:
        return ""


def parse_search_results(payload: dict) -> list[dict]:
    """You.com Search payload -> [{"title","url","snippet","is_video"}], deduped by video id."""
    results = payload.get("results") if isinstance(payload, dict) else None
    rows: list = []
    if isinstance(results, dict):
        for key in ("web", "news"):
            if isinstance(results.get(key), list):
                rows.extend(results[key])
    elif isinstance(results, list):
        rows = results
    out, seen = [], set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url") or "").strip()
        vid = video_id(url)
        key = vid or url
        if not url or key in seen:
            continue
        seen.add(key)
        snips = r.get("snippets") or []
        snippet = str(r.get("description") or (snips[0] if snips else "") or "")
        out.append({"title": str(r.get("title") or ""), "url": url,
                    "snippet": " ".join(snippet.split())[:200],
                    "is_video": bool(vid)})
    return out


def youtube_search(query: str, *, client: YouComClient | None = None) -> list[dict]:
    """Paid You.com Web Search restricted to youtube.com. Raises MediaError on an API error."""
    key = _ydc_key() if client is None else getattr(client, "api_key", "")
    client = client or YouComClient(api_key=key, timeout=60)
    call = client.search(query, {"include_domains": ["youtube.com"]})
    if not call.ok:
        raise MediaError(f"You.com search failed: {call.error}")
    return parse_search_results(call.payload)


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {_stem(w) for w in words if len(w) > 1 and w not in _STOP}


def moment_queries(desc: str, extra: list[str] | tuple = ()) -> list[str]:
    """Phased queries for art-history / documentary footage, deduped in order."""
    out: list[str] = []
    for q in (desc, f"{desc} documentary", f"{desc} art history", *extra):
        q = " ".join(str(q).split())
        if q and q not in out:
            out.append(q)
    return out


def gather_candidates(queries: list[str], *, search=None, log=None) -> list[dict]:
    """Run queries, dedup videos by id with query consensus (`hits`) and `best_rank`."""
    search_fn = youtube_search if search is None else search
    by_id: dict[str, dict] = {}
    errors: list[str] = []
    for q in queries:
        try:
            rows = search_fn(q)
        except RealModelsOff:                     # never turned into a plain "search failed"
            raise
        except Exception as exc:
            errors.append(str(exc))
            if log:
                log(f"[moment] query failed ({exc}): {q}")
            continue
        for rank, r in enumerate(r for r in rows if r.get("is_video")):
            vid = video_id(r["url"])
            if not vid:
                continue
            c = by_id.setdefault(vid, {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                                       "title": r.get("title", ""), "snippet": r.get("snippet", ""),
                                       "hits": 0, "best_rank": rank})
            c["hits"] += 1
            c["best_rank"] = min(c["best_rank"], rank)
    if not by_id and errors and len(errors) == len(queries):
        raise MediaError(errors[0])
    return sorted(by_id.values(), key=lambda c: (-c["hits"], c["best_rank"]))


def parse_vtt(text: str) -> list[tuple[float, float, str]]:
    """WebVTT -> [(start, end, text)], tags stripped, consecutive repeats collapsed."""
    def _t(h, m, s, frac):
        return int(h or 0) * 3600 + int(m) * 60 + int(s) + float(f"0.{frac}")
    cues: list[tuple[float, float, str]] = []
    lines = (text or "").splitlines()
    i = 0
    while i < len(lines):
        m = _CUE.search(lines[i])
        if not m:
            i += 1
            continue
        a, b = _t(*m.groups()[:4]), _t(*m.groups()[4:])
        i += 1
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(re.sub(r"<[^>]+>", "", lines[i]).strip())
            i += 1
        txt = " ".join(x for x in body if x)
        if txt and not (cues and cues[-1][2] == txt):
            cues.append((a, b, txt))
    return cues


def heatmap_peaks(heatmap: list | None, duration: float, *, k: int = 3,
                  min_value: float = 0.35, min_gap: float = 8.0) -> list[tuple[float, float]]:
    """[(centre_seconds, value)] of up to k local maxima of YouTube's 'most replayed' graph."""
    segs = [(float(h["start_time"]), float(h["end_time"]), float(h["value"]))
            for h in heatmap or [] if isinstance(h, dict) and "value" in h]
    head = max(3.0, 0.02 * (duration or 0))
    peaks = []
    for i, (a, b, v) in enumerate(segs):
        if a < head or v < min_value:
            continue
        prev = segs[i - 1][2] if i else -1.0
        nxt = segs[i + 1][2] if i + 1 < len(segs) else -1.0
        if v >= prev and v >= nxt:
            peaks.append(((a + b) / 2, v))
    chosen: list[tuple[float, float]] = []
    for c, v in sorted(peaks, key=lambda p: -p[1]):
        if all(abs(c - c2) >= min_gap for c2, _ in chosen):
            chosen.append((round(c, 1), round(v, 2)))
        if len(chosen) == k:
            break
    return chosen


def find_moments(desc: str, info: dict, cues: list | None = None, *, k: int = 3) -> list[dict]:
    """Up to k candidate windows in one video from chapters, subtitle cues, and replay heatmap."""
    q = _terms(desc)
    locate = q - _terms(info.get("title") or "")
    need = 1 if len(q) <= 2 else 2

    def hit(text: str) -> set[str]:
        if not q:
            return set()
        shared = q & _terms(text)
        ok = bool(shared & locate) if locate else len(shared) >= need
        return shared if ok else set()

    dur = float(info.get("duration") or 0)
    out: list[dict] = []
    for ch in info.get("chapters") or []:
        shared = hit(ch.get("title", ""))
        if shared:
            a = float(ch.get("start_time") or 0)
            b = min(float(ch.get("end_time") or a + 10), a + 10)
            out.append({"start": round(a, 1), "end": round(b, 1), "strength": 0.6 + 0.1 * len(shared),
                        "why": {"code": "chapter", "title": ch.get("title", "")}})
    for a, b, txt in cues or []:
        shared = hit(txt)
        if shared:
            out.append({"start": round(max(0.0, a - 1), 1), "end": round(min(dur or b + 2, b + 2), 1),
                        "strength": 0.5 + 0.1 * len(shared), "why": {"code": "subtitle", "text": txt[:70]}})
    for c, v in heatmap_peaks(info.get("heatmap"), dur):
        out.append({"start": round(max(0.0, c - 3), 1), "end": round(min(dur or c + 3, c + 3), 1),
                    "strength": v, "why": {"code": "replayed", "value": round(v, 2)}})
    out.sort(key=lambda m: -m["strength"])
    picked: list[dict] = []
    for m in out:
        if all(m["end"] <= p["start"] or m["start"] >= p["end"] for p in picked):
            picked.append(m)
        if len(picked) == k:
            break
    return sorted(picked, key=lambda m: m["start"])


def score_video(desc: str, cand: dict, info: dict, moments: list[dict], n_queries: int) -> dict:
    """Heuristic ranking combining description match, query consensus, timing signal, duration and resolution."""
    q = _terms(desc) or {""}
    title = _terms(info.get("title") or cand.get("title", ""))
    body = _terms(" ".join([info.get("description") or cand.get("snippet", ""),
                            " ".join(info.get("tags") or [])]))
    match = 0.7 * len(q & title) / len(q) + 0.3 * len(q & (title | body)) / len(q)
    consensus = cand.get("hits", 1) / max(1, n_queries)
    timing = min(1.0, max((m["strength"] for m in moments), default=0.0))
    dur = float(info.get("duration") or 0)
    length_fit = 1.0 if 30 <= dur <= 600 else (0.5 if dur and dur <= 1200 else 0.0)
    res = 1.0 if (info.get("height") or 0) >= 720 else 0.0
    score = 0.45 * match + 0.25 * consensus + 0.15 * timing + 0.1 * length_fit + 0.05 * res
    return {"score": round(score, 3), "match": round(match, 2),
            "consensus": f"{cand.get('hits', 1)}/{n_queries}", "timing": round(timing, 2)}


def _candidate_row(desc: str, cand: dict, info: dict, cues: list, n_queries: int) -> dict:
    vid = info.get("id") or cand.get("id") or ""
    moments = find_moments(desc, info, cues)
    ok, lic_name, _reason = clip_licence(info)
    raw_lic = str(info.get("license") or "").strip()
    lic_label = lic_name or raw_lic or "Standard YouTube License"
    flag = None if ok else flag_for_text(lic_label)
    row = {
        "id": vid,
        "url": info.get("webpage_url") or cand.get("url") or f"https://www.youtube.com/watch?v={vid}",
        "title": info.get("title") or cand.get("title") or vid,
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration": round(float(info.get("duration") or 0), 1),
        "height": info.get("height"),
        "width": info.get("width"),
        "subtitles": bool(cues),
        "vertical": bool(info.get("width") and info.get("height") and info["height"] > info["width"]),
        "thumb_url": info.get("thumbnail") or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""),
        "embeddable": info.get("playable_in_embed", True) is not False,
        "licence": lic_label,
        "licence_ok": ok,
        "flag": flag,
        "moments": moments,
    }
    row.update(score_video(desc, cand, info, moments, n_queries))
    return row


def inspect_video_url(url: str, desc: str = "", *, metadata=None) -> dict:
    """Inspect a pasted YouTube URL via yt-dlp (free, no You.com call). Returns one candidate row."""
    canon_url = safe_youtube_url(url)
    vid = video_id(canon_url)
    meta_fn = video_metadata_with_cues if metadata is None else metadata
    with tempfile.TemporaryDirectory() as td:
        info, cues = meta_fn(canon_url, Path(td))
    cand = {"id": vid, "url": canon_url, "title": info.get("title") or "", "snippet": "", "hits": 1}
    return _candidate_row(desc, cand, info, cues, 1)


def moment_search(desc: str, *, limit: int = 6, extra_queries: list[str] | tuple = (),
                  search=None, metadata=None, log=None) -> list[dict]:
    """You.com YouTube search + parallel yt-dlp metadata/moment extraction, best first."""
    queries = moment_queries(desc, extra_queries)
    cands = gather_candidates(queries, search=search, log=log)[:max(1, min(int(limit), 12))]
    meta_fn = video_metadata_with_cues if metadata is None else metadata

    def one(c):
        try:
            with tempfile.TemporaryDirectory() as td:
                info, cues = meta_fn(c["url"], Path(td))
        except RealModelsOff:                     # not a row that failed: nothing may run at all
            raise
        except Exception as exc:
            return {**c, "error": str(exc)[:200]}
        return _candidate_row(desc, c, info, cues, len(queries))

    if not cands:
        return []
    with ThreadPoolExecutor(max_workers=min(4, len(cands))) as pool:
        rows = list(pool.map(one, cands))
    ok_rows = sorted((r for r in rows if "error" not in r), key=lambda r: -r["score"])
    return ok_rows + [r for r in rows if "error" in r]


def clip_licence(info: dict) -> tuple[bool, str, str]:
    """Gate yt-dlp metadata: the `license` field must say Creative Commons (or PD).
    A missing field or the standard YouTube licence is rejected."""
    return check_licence({"license": (info or {}).get("license") or ""})


# --------------------------------------------------------------------------- download + normalise

def ytdlp_section_args(url: str, out_dir: Path, *, start: float, end: float,
                       max_height: int = 1080) -> list[str]:
    if end <= start:
        raise ValueError("end must be after start")
    canon_url = safe_youtube_url(url)
    fmt = f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b"
    args = [*_ytdlp_cmd(), "--no-playlist", "-f", fmt,
            "--download-sections", f"*{start:.2f}-{end:.2f}", "--force-keyframes-at-cuts",
            "--force-overwrites", "--merge-output-format", "mp4", "--write-info-json",
            "--no-progress", "-o", str(Path(out_dir) / f"%(id)s_sec_{start:.1f}_{end:.1f}.%(ext)s"),
            "--print", "after_move:filepath", "--", canon_url]
    return args


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


def normalize(src: Path, out: Path, *, max_short_side: int = 1080, strip_audio: bool = True) -> Path:
    """H.264 yuv420p, constant 30 fps, short side <= max_short_side, muted by default (-an)."""
    info = probe_video(src)
    w, h = info["width"], info["height"]
    k = min(1.0, max_short_side / min(w, h))
    tw, th = max(2, int(round(w * k / 2)) * 2), max(2, int(round(h * k / 2)) * 2)
    tmp = out.with_name(out.stem + ".part.mp4")
    audio_args = ["-an"] if strip_audio else ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k"]
    cmd = [_ffmpeg(), "-y", "-i", str(src), "-map", "0:v:0",
           "-vf", f"fps=30,scale={tw}:{th}:flags=lanczos,setsar=1,format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           *audio_args, "-movflags", "+faststart", str(tmp)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise MediaError(f"transcode failed: {(res.stderr or '')[-600:]}")
    atomic_replace(tmp, out)
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
                  sheet: bool = True, max_height: int = 1080, strict_licence: bool = True,
                  runner=None) -> dict:
    """Check licence (raising LicenceRejected if `strict_licence=True`, else recording advisory `credit.flag`),
    download one section, normalise (silent 30fps H.264), contact sheet. Everything lands in `<project>/cache/clips/`."""
    canon_url = safe_youtube_url(url)
    run_fn = _run_capture if runner is None else runner
    info = info or video_metadata(canon_url)
    ok, name, reason = clip_licence(info)
    if not ok and strict_licence:
        raise LicenceRejected(reason, name)
    lic_name = name or str(info.get("license") or "Standard YouTube License").strip()
    cache = Path(project_dir) / "cache" / "clips"
    raw_dir = cache / "src"
    raw_dir.mkdir(parents=True, exist_ok=True)
    vid = info.get("id") or video_id(canon_url) or "clip"
    out = cache / f"{vid}_{start:.1f}_{end:.1f}.mp4"
    if not out.is_file():
        res = run_fn(ytdlp_section_args(canon_url, raw_dir, start=start, end=end, max_height=max_height),
                     timeout=SECTION_TIMEOUT)
        lines = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip()]
        raw = Path(lines[-1]) if lines else None
        if res.returncode != 0 or raw is None or not raw.is_file():
            raise MediaError(f"yt-dlp failed (exit {res.returncode}): {_ytdlp_error(res)}")
        normalize(raw, out)
        if raw != out:
            raw.unlink(missing_ok=True)
        for jf in raw_dir.glob("*.info.json"):
            jf.unlink(missing_ok=True)
    sheet_path = contact_sheet(out, cache / f"{out.stem}_sheet.jpg") if sheet else None
    credit: dict = {"source": "youtube" if "youtu" in url else "web",
                    "source_url": info.get("webpage_url") or url,
                    "author": info.get("channel") or info.get("uploader") or "unknown",
                    "licence": lic_name, "licence_url": ""}
    if not ok:
        credit["flag"] = flag_for_text(lic_name) or "rejected"
    else:
        credit["flag"] = None
    return {"id": vid, "file": str(out), "sheet": str(sheet_path) if sheet_path else "",
            "info": {k: info.get(k) for k in ("id", "title", "channel", "duration", "license")},
            "licence": lic_name, "credit": credit}


def prune_clips_cache(project_dir: Path, max_bytes: int = 500 * 1024 * 1024) -> int:
    """Cap <project_dir>/cache/clips at max_bytes, removing oldest files first.
    Returns the number of bytes freed."""
    cache = Path(project_dir) / "cache" / "clips"
    if not cache.is_dir():
        return 0
    files = []
    total = 0
    for p in cache.rglob("*"):
        if p.is_file():
            try:
                st = p.stat()
                files.append((st.st_mtime, st.st_size, p))
                total += st.st_size
            except OSError:
                pass
    if total <= max_bytes:
        return 0
    files.sort(key=lambda x: x[0])
    freed = 0
    for _, sz, p in files:
        if total - freed <= max_bytes:
            break
        try:
            p.unlink(missing_ok=True)
            freed += sz
        except OSError:
            pass
    return freed


def import_clip(project_dir: Path, url: str, start: float, end: float, *, info: dict | None = None,
                strict_licence: bool = True, require_root: bool = False, runner=None) -> dict:
    """Fetch a section and return `{"asset_key", "asset"}` like api.import_candidate."""
    project_dir = Path(project_dir)
    if require_root and not project_dir.is_dir():
        raise FileNotFoundError(f"project folder {project_dir.name!r} does not exist")
    r = fetch_section(project_dir, url, start, end, info=info, strict_licence=strict_licence, runner=runner)
    ident = f"clip:{r['id']}:{start:.1f}-{end:.1f}"
    idx = _assets.load_index(project_dir)
    hit = idx["items"].get(ident)
    if hit and (project_dir / hit["asset"]["file"]).is_file():
        return {"asset_key": hit["key"], "asset": hit["asset"]}
    key = _assets.make_key(r["info"].get("title") or r["id"], ident, _assets.taken_keys(project_dir, idx))
    dest = _assets.media_dir(project_dir, require_root) / f"{key}.mp4"
    shutil.copyfile(r["file"], dest)
    try:
        p = probe_video(dest)        # the size is that of the STORED file (the same rule as images: see api.stored_image_size)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    Path(r["file"]).unlink(missing_ok=True)
    if r.get("sheet"):
        Path(r["sheet"]).unlink(missing_ok=True)
    prune_clips_cache(project_dir, max_bytes=500 * 1024 * 1024)
    asset = _assets.build_asset(f"media/{dest.name}", "video", r["info"].get("title") or "",
                                r["credit"]["author"], "", p["width"], p["height"], r["credit"],
                                duration=p.get("duration"))
    _assets.register(project_dir, ident, key, asset, require_root)
    return {"asset_key": key, "asset": asset}
