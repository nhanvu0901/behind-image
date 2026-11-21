"""The two pictures made for people: the sheet of the regions drawn on the main painting, and the contact sheets of the video (one labelled frame per shot).

Both need Pillow; the contact sheets also need ffmpeg (one call per shot, four at a time, `-ss` before `-i`, so a frame costs a short seek and not a decode of the whole video). A sheet is
written whole or not at all. A frame that cannot be cut leaves a grey tile that says so; when no frame can be cut at all the sheets are not made and `SheetError` says why."""
from __future__ import annotations

import io
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from . import fsutil, words

COLORS = [(231, 76, 60), (46, 134, 222), (39, 174, 96), (243, 156, 18), (142, 68, 173), (22, 160, 133), (211, 84, 0), (52, 73, 94), (214, 48, 130), (127, 140, 141)]
STYLE_FONTS = Path(__file__).resolve().parents[2] / "style" / "gae" / "fonts"
FONT_FILES = [str(STYLE_FONTS / "EBGaramond-Medium.ttf"), str(STYLE_FONTS / "EBGaramond-Regular.ttf"), r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
_FONT_CACHE: dict[int, object] = {}


TMP_PREFIX = ".frames-"          # the scratch folder of the cut frames (made inside the output folder; `publish.sync` removes one a crash left behind)


class SheetError(Exception):
    pass


def _ink(font, text: str) -> bytes:
    from PIL import Image, ImageDraw
    im = Image.new("L", (160, 80), 0)
    ImageDraw.Draw(im).text((8, 8), text, font=font, fill=255)
    return im.tobytes()


def _has_vietnamese(font) -> bool:
    """True when the font draws the Vietnamese letters (their picture is not the picture of a character no font has)."""
    try:
        missing = _ink(font, "\uffff")
        return all(_ink(font, ch) != missing for ch in "ẫạờ")
    except Exception:       # noqa: BLE001
        return False


def font(size: int):
    """A font that has the Vietnamese letters, as large as asked; the first of the candidates that does (the bundled EB Garamond, then the system's Arial)."""
    from PIL import ImageFont
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    chosen = None
    for p in FONT_FILES:
        if not os.path.isfile(p):
            continue
        try:
            f = ImageFont.truetype(p, size)
        except OSError:
            continue
        if _has_vietnamese(f):
            chosen = f
            break
        chosen = chosen or f
    _FONT_CACHE[size] = chosen or ImageFont.load_default()
    return _FONT_CACHE[size]


def _fit(draw, text: str, fnt, width: int) -> str:
    if draw.textlength(text, font=fnt) <= width:
        return text
    while len(text) > 1 and draw.textlength(text + "…", font=fnt) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(draw, text: str, fnt, width: int, lines: int = 2) -> list[str]:
    """Greedy word wrap into at most `lines` lines; what does not fit ends the last line with an ellipsis."""
    out: list[str] = []
    cur = ""
    for w in str(text).split():
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= width or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = _fit(draw, out[-1] + " …", fnt, width)
    return [_fit(draw, ln, fnt, width) for ln in out]


def _jpeg(im, quality: int = 82) -> bytes:
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------ the regions sheet
def regions_sheet(image_path: Path, regions: dict, out_path: Path, title: str = "", max_side: int = 1500) -> int:
    """Draw every region (an ellipse `x, y, rx, ry` in the picture's own pixels, or a point when it has no radius) on the main painting, numbered, with the legend beside it. -> the number of regions drawn."""
    from PIL import Image, ImageDraw
    im = Image.open(image_path)
    im.load()
    im = im.convert("RGB")
    W, H = im.size
    s = min(1.0, max_side / max(W, H))
    pic = im.resize((max(1, int(W * s)), max(1, int(H * s))), Image.LANCZOS)
    items = [(k, r) for k, r in regions.items() if isinstance(r, dict) and isinstance(r.get("x"), (int, float)) and isinstance(r.get("y"), (int, float))]
    d = ImageDraw.Draw(pic, "RGBA")
    badge = font(max(18, int(pic.size[1] / 70)))
    for i, (_k, r) in enumerate(items):
        col = COLORS[i % len(COLORS)]
        cx, cy = r["x"] * s, r["y"] * s
        rx = float(r["rx"]) * s if isinstance(r.get("rx"), (int, float)) and r["rx"] > 0 else None
        ry = float(r["ry"]) * s if isinstance(r.get("ry"), (int, float)) and r["ry"] > 0 else rx
        if rx:
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=col + (255,), width=4, fill=col + (16,))
            ty = cy - ry
        else:
            d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=col + (255,), width=4, fill=col + (90,))
            ty = cy - 14
        tag = str(i + 1)
        tw = d.textlength(tag, font=badge)
        bx, by = min(max(cx - tw / 2 - 5, 0), pic.size[0] - tw - 10), min(max(ty - badge.size - 8, 0), pic.size[1] - badge.size - 8)
        d.rectangle([bx, by, bx + tw + 10, by + badge.size + 6], fill=col + (235,))
        d.text((bx + 5, by + 1), tag, font=badge, fill=(255, 255, 255, 255))
    lw = 700
    sheet = Image.new("RGB", (pic.size[0] + lw, max(pic.size[1], 90 + 36 * len(items))), (250, 248, 244))
    sheet.paste(pic, (0, 0))
    g = ImageDraw.Draw(sheet)
    head, body = font(30), font(24)
    g.text((pic.size[0] + 20, 16), _fit(g, title or "Các vùng trên tranh chính", head, lw - 40), font=head, fill=(40, 40, 40))
    g.text((pic.size[0] + 20, 54), "%d vùng đã vẽ" % len(items), font=body, fill=(110, 110, 110))
    for i, (k, r) in enumerate(items):
        col = COLORS[i % len(COLORS)]
        y = 96 + i * 36
        g.rectangle([pic.size[0] + 20, y + 3, pic.size[0] + 44, y + 27], fill=col)
        g.text((pic.size[0] + 26, y + 2), str(i + 1), font=font(18), fill=(255, 255, 255))
        label = (r.get("label") or "").strip() or str(k)
        g.text((pic.size[0] + 54, y), _fit(g, "%s" % label, body, lw - 70), font=body, fill=(40, 40, 40))
    fsutil.write_bytes(out_path, _jpeg(sheet, 86))
    return len(items)


# ------------------------------------------------------------------------------------------------ the contact sheets
def cut_frame(ffmpeg: list[str], video: Path, t: float, out: Path, width: int, env: dict | None = None, timeout: float = 120.0) -> bool:
    cmd = [str(c) for c in ffmpeg] + ["-v", "error", "-nostdin", "-y", "-ss", "%.3f" % max(0.0, t), "-i", str(video), "-frames:v", "1", "-vf", "scale=%d:-2" % width, "-q:v", "4", str(out)]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and out.is_file() and out.stat().st_size > 0


def contact_sheets(video: Path, shots: list[dict], out_dir: Path, ffmpeg: list[str], *, title: str = "", cols: int = 5, rows: int = 4, tile_w: int = 384,
                   env: dict | None = None, progress: Callable[[float], None] | None = None, tmp_root: Path | None = None) -> list[str]:
    """`shots`: [{n, t (seconds into the video), label}]. Writes `contact_sheet_01.jpg`, ... into `out_dir` and removes the older ones that are no longer needed. -> the file names."""
    from PIL import Image, ImageDraw
    if not shots:
        raise SheetError("no shot to cut")
    tile_h = int(round(tile_w * 9 / 16 / 2)) * 2
    strip = 58
    head = 46
    per = cols * rows
    if tmp_root is not None:
        Path(tmp_root).mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=TMP_PREFIX, dir=str(tmp_root) if tmp_root is not None else None))
    frames: dict[int, Path] = {}
    done = [0]

    def one(item: dict):
        p = tmp / ("f%04d.jpg" % item["n"])
        ok = cut_frame(ffmpeg, video, item["t"], p, tile_w, env)
        done[0] += 1
        if progress:
            progress(done[0] / len(shots))
        return item["n"], (p if ok else None)
    try:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for n, p in ex.map(one, shots):
                if p is not None:
                    frames[n] = p
        if not frames:
            raise SheetError("no frame of the video could be cut (is ffmpeg there, and the video whole?)")
        pages = [shots[i:i + per] for i in range(0, len(shots), per)]
        small, mid = font(20), font(26)
        names = []
        for pi, page in enumerate(pages, 1):
            rows_here = -(-len(page) // cols)               # the last page is only as tall as it needs to be
            sheet = Image.new("RGB", (cols * tile_w, head + rows_here * (tile_h + strip)), (250, 248, 244))
            g = ImageDraw.Draw(sheet, "RGBA")
            g.text((12, 8), _fit(g, "%s — cảnh %d đến %d (trang %d/%d)" % (title, page[0]["n"], page[-1]["n"], pi, len(pages)), mid, cols * tile_w - 24), font=mid, fill=(40, 40, 40))
            for k, item in enumerate(page):
                x, y = (k % cols) * tile_w, head + (k // cols) * (tile_h + strip)
                p = frames.get(item["n"])
                if p is not None:
                    try:
                        with Image.open(p) as fr:
                            fr = fr.convert("RGB")
                            fr = fr.resize((tile_w - 4, tile_h)) if fr.size != (tile_w - 4, tile_h) else fr
                            sheet.paste(fr, (x + 2, y))
                    except Exception:       # noqa: BLE001 - one damaged frame is a grey tile
                        p = None
                if p is None:
                    g.rectangle([x + 2, y, x + tile_w - 3, y + tile_h - 1], fill=(205, 205, 205))
                    g.text((x + 14, y + tile_h // 2 - 12), "không lấy được khung hình", font=small, fill=(90, 90, 90))
                badge = str(item["label"][0])
                bw = int(g.textlength(badge, font=small)) + 14
                g.rectangle([x + 2, y, x + 2 + bw, y + 28], fill=(20, 20, 20, 205))
                g.text((x + 9, y + 3), badge, font=small, fill=(255, 255, 255, 255))
                for li, ln in enumerate(_wrap(g, str(item["label"][1]), small, tile_w - 14, 2)):
                    g.text((x + 6, y + tile_h + 4 + li * 24), ln, font=small, fill=(30, 30, 30, 255))
            name = "contact_sheet_%02d.jpg" % pi
            fsutil.write_bytes(Path(out_dir) / name, _jpeg(sheet, 80))
            names.append(name)
        fsutil.keep_only(Path(out_dir), set(names) | {x.name for x in Path(out_dir).iterdir() if not x.name.startswith("contact_sheet_")}, suffixes=(".jpg",))
        return names
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


def label_for(shot_no: int, t0: float | None, sentence: str) -> tuple[str, str]:
    """The two lines under a tile: `12 · 2:37` and the plain sentence of the shot."""
    return ("%d · %s" % (shot_no, words.clock(t0) if t0 is not None else "—"), sentence)
