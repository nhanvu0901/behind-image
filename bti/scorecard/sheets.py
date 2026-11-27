"""Contact sheets for the scorecard: 5x4 tiles at 480 px, one frame per shot when its marks are visible."""
from __future__ import annotations

import io
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from bti.output import fsutil, words
from bti.output import sheets as out_sheets

from .audio import is_media_file

COLS = 5
ROWS = 4
TILE_W = 480
TILE_H = 270
HEAD_H = 44
MARK_OFFSET_S = 1.3
POINTING_TECHNIQUES = frozenset({"HI-01", "X-HI-01", "AN-01"})
MARK_TECHNIQUES = frozenset({"HI-01", "X-HI-01", "AN-01", "X-ANN-01", "X-ANN-02", "DOC-01", "KEY-01", "NUM-01"})


def shot_sample_time(shot: dict, t0: float, t1: float) -> float:
    """Return `first_mark_start + 1.3s` clamped inside `[t0, t1]`, else the shot midpoint."""
    dur = max(0.0, float(t1) - float(t0))
    if dur <= 0.0:
        return float(t0)
    overlays = [o for o in (shot.get("overlays") or []) if isinstance(o, dict)]
    pointing_starts: list[float] = []
    other_starts: list[float] = []
    for o in overlays:
        tid = o.get("technique")
        if tid not in MARK_TECHNIQUES:
            continue
        ot0 = o.get("_t0")
        if not isinstance(ot0, (int, float)):
            continue
        if tid in POINTING_TECHNIQUES:
            pointing_starts.append(float(ot0))
        else:
            other_starts.append(float(ot0))
    candidates = pointing_starts or other_starts
    if not candidates:
        return (float(t0) + float(t1)) / 2.0
    eps = min(0.05, dur * 0.1)
    t = min(candidates) + MARK_OFFSET_S
    return max(float(t0) + eps, min(float(t1) - eps, t))


def _resolve_shots(project_dir: Path, engine_project: Any = None) -> list[dict]:
    if engine_project is not None:
        res = engine_project.resolve()
        return [s for s in (res.get("shots") or []) if isinstance(s, dict)]
    try:
        from bti.engine.api import open_project
        eng = open_project(Path(project_dir))
        res = eng.resolve()
        return [s for s in (res.get("shots") or []) if isinstance(s, dict)]
    except Exception:           # noqa: BLE001
        pass
    sb = json.loads((Path(project_dir) / "storyboard.json").read_text(encoding="utf-8"))
    from bti.output import times as out_times
    trel = sb.get("timing") if isinstance(sb.get("timing"), str) and sb.get("timing") else "timing.json"
    timing = json.loads((Path(project_dir) / trel).read_text(encoding="utf-8"))
    spans = out_times.shot_times(Path(project_dir), sb, timing)
    out = []
    for s, (t0, t1) in zip(sb.get("shots") or [], spans):
        if isinstance(s, dict) and t0 is not None and t1 is not None:
            sc = dict(s)
            sc["_t0"] = t0
            sc["_t1"] = t1
            out.append(sc)
    return out


def _cut_tile_ffmpeg(ffmpeg: list[str], video_path: Path, t: float, tmp_path: Path, env: dict | None = None) -> bool:
    cmd = [str(c) for c in ffmpeg] + [
        "-v", "error", "-nostdin", "-y",
        "-ss", "%.3f" % max(0.0, t),
        "-i", str(video_path),
        "-frames:v", "1",
        "-s", "%dx%d" % (TILE_W, TILE_H),
        "-q:v", "3",
        str(tmp_path),
    ]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120.0, env=env)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and tmp_path.is_file() and tmp_path.stat().st_size > 0


def _jpeg_bytes(im, quality: int = 84) -> bytes:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def render_sheets(
    project_dir: Path,
    out_dir: Path,
    *,
    video_path: Path | None = None,
    tools: Any = None,
    engine_project: Any = None,
    title: str = "",
) -> tuple[list[dict], str]:
    """Render 5x4 contact sheets (480 px tiles) into `out_dir`. Returns `(sheet_entries, source_kind)`."""
    from PIL import Image, ImageDraw
    pdir = Path(project_dir)
    out_dir = Path(out_dir)
    fsutil.ensure_dir(out_dir)
    shots = _resolve_shots(pdir, engine_project=engine_project)
    if not shots:
        return [], "none"

    items: list[dict] = []
    for n, s in enumerate(shots, 1):
        t0, t1 = s.get("_t0"), s.get("_t1")
        if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)) or t1 <= t0:
            continue
        t = shot_sample_time(s, float(t0), float(t1))
        items.append({"n": n, "id": str(s.get("id") or f"s{n:04d}"), "t": t, "t0": float(t0)})
    if not items:
        return [], "none"

    use_video = is_media_file(video_path)
    tiles: dict[int, Image.Image] = {}
    source = "video" if use_video else "engine"

    if use_video:
        if tools is None:
            from bti.export import render as export_render
            from bti.export.settings import load_settings
            tools = export_render.Tools.from_settings(load_settings())
        ffmpeg = list(tools.ffmpeg)
        env = getattr(tools, "env", None)
        tmp = Path(tempfile.mkdtemp(prefix=".scorecard-frames-", dir=str(out_dir)))
        try:
            def grab(it: dict):
                p = tmp / ("t%04d.jpg" % it["n"])
                ok = _cut_tile_ffmpeg(ffmpeg, Path(video_path), it["t"], p, env=env)
                return it["n"], (p if ok else None)

            with ThreadPoolExecutor(max_workers=4) as ex:
                for n, p in ex.map(grab, items):
                    if p is not None:
                        try:
                            with Image.open(p) as fr:
                                fr = fr.convert("RGB")
                                if fr.size != (TILE_W, TILE_H):
                                    fr = fr.resize((TILE_W, TILE_H), Image.LANCZOS)
                                tiles[n] = fr.copy()
                        except Exception:       # noqa: BLE001
                            pass
        finally:
            for p in list(tmp.glob("*")):
                try:
                    p.unlink()
                except OSError:
                    pass
            try:
                tmp.rmdir()
            except OSError:
                pass
    else:
        eng = engine_project
        if eng is None:
            from bti.engine.api import open_project
            eng = open_project(pdir)
        for it in items:
            try:
                bgr = eng.frame_at(it["t"], TILE_W)
                if bgr is not None and getattr(bgr, "ndim", 0) == 3:
                    rgb = bgr[:, :, ::-1]
                    im = Image.fromarray(rgb.astype("uint8"), mode="RGB")
                    if im.size != (TILE_W, TILE_H):
                        im = im.resize((TILE_W, TILE_H), Image.LANCZOS)
                    tiles[it["n"]] = im
            except Exception:       # noqa: BLE001
                pass

    if not tiles:
        return [], source

    per = COLS * ROWS
    pages = [items[i:i + per] for i in range(0, len(items), per)]
    badge_font = out_sheets.font(20)
    head_font = out_sheets.font(24)
    entries: list[dict] = []
    keep: set[str] = set()
    heading_title = title or pdir.name

    for pi, page in enumerate(pages, 1):
        rows_here = -(-len(page) // COLS)
        sheet = Image.new("RGB", (COLS * TILE_W, HEAD_H + rows_here * TILE_H), (24, 24, 24))
        g = ImageDraw.Draw(sheet, "RGBA")
        header = "%s — cảnh %d–%d (trang %d/%d)" % (heading_title, page[0]["n"], page[-1]["n"], pi, len(pages))
        g.text((14, 9), out_sheets._fit(g, header, head_font, COLS * TILE_W - 28), font=head_font, fill=(235, 232, 224, 255))
        for idx, it in enumerate(page):
            x = (idx % COLS) * TILE_W
            y = HEAD_H + (idx // COLS) * TILE_H
            fr = tiles.get(it["n"])
            if fr is not None:
                sheet.paste(fr, (x, y))
            else:
                g.rectangle([x + 1, y + 1, x + TILE_W - 2, y + TILE_H - 2], fill=(64, 64, 64))
                g.text((x + 16, y + TILE_H // 2 - 12), "không lấy được khung hình", font=badge_font, fill=(200, 200, 200, 255))
            badge = "#%d · %s" % (it["n"], words.clock(it["t"]))
            bw = int(g.textlength(badge, font=badge_font)) + 16
            g.rectangle([x + 6, y + 6, x + 6 + bw, y + 34], fill=(15, 15, 15, 210))
            g.text((x + 14, y + 8), badge, font=badge_font, fill=(255, 255, 255, 255))
            g.rectangle([x, y, x + TILE_W - 1, y + TILE_H - 1], outline=(48, 48, 48, 255), width=1)
        name = "sheet_%02d.jpg" % pi
        fsutil.write_bytes(out_dir / name, _jpeg_bytes(sheet, 84))
        keep.add(name)
        entries.append({"name": name, "shots": [page[0]["n"], page[-1]["n"]], "count": len(page)})

    fsutil.keep_only(out_dir, keep, suffixes=(".jpg",))
    return entries, source
