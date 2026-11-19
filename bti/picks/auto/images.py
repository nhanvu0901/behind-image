"""The picture work of the automatic picks job: scaled copies for the agent to look at, crops of the main painting, contact sheets of
candidates. OpenCV reads and writes the pictures (it has no pixel limit of its own that matters here); Pillow draws the numbers on a
contact sheet. Both are imported when a function runs, so importing this module costs nothing."""
from __future__ import annotations

from pathlib import Path

from . import shapes

VIEW_SIDE = 1568           # the copy the agent looks at: at most this many pixels on the long side
LARGE_SIDE = 3600          # the copy the crop helper cuts from
CROP_SIDE = 900            # a crop is shown at most this big
TILE = (460, 340)          # one tile of a contact sheet
SHEET_COLS = 3


class ImageError(Exception):
    pass


def _cv2():
    import cv2
    return cv2


def read(path: Path):
    cv2 = _cv2()
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise ImageError("%s cannot be read as a picture" % Path(path).name)
    return im


def write_jpeg(im, dest: Path, quality: int = 88) -> None:
    cv2 = _cv2()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(dest), im, [cv2.IMWRITE_JPEG_QUALITY, quality]):
        raise ImageError("%s cannot be written" % dest.name)


def scaled(im, max_side: int):
    cv2 = _cv2()
    h, w = im.shape[:2]
    k = min(1.0, max_side / float(max(w, h)))
    if k >= 1.0:
        return im
    return cv2.resize(im, (max(1, int(round(w * k))), max(1, int(round(h * k)))), interpolation=cv2.INTER_AREA)


def save_scaled(src: Path, dest: Path, max_side: int, quality: int = 88) -> tuple[int, int, int, int]:
    """Write a copy of `src` no larger than `max_side`; -> (source width, source height, copy width, copy height)."""
    im = read(src)
    out = scaled(im, max_side)
    write_jpeg(out, dest, quality)
    return im.shape[1], im.shape[0], out.shape[1], out.shape[0]


def crop(src: Path, box: list[float], dest: Path, max_side: int = CROP_SIDE) -> tuple[int, int, int, int, int, int]:
    """Cut `box` (fractions of the picture) out of `src` and write it; -> (x0, y0, x1, y1 in pixels of `src`, shown width, shown height)."""
    im = read(src)
    h, w = im.shape[:2]
    x0, y0, x1, y1 = shapes.crop_pixels(box, w, h)
    piece = scaled(im[y0:y1, x0:x1], max_side)
    write_jpeg(piece, dest, 90)
    return x0, y0, x1, y1, piece.shape[1], piece.shape[0]


def grid(src: Path, dest: Path, step: float = 0.1) -> None:
    """A copy of the picture with a labelled grid (0.1 steps) so that a position can be read off as a fraction."""
    cv2 = _cv2()
    im = read(src).copy()
    h, w = im.shape[:2]
    n = int(round(1 / step))
    for i in range(1, n):
        x, y = int(round(i * step * w)), int(round(i * step * h))
        cv2.line(im, (x, 0), (x, h - 1), (0, 255, 255), 1)
        cv2.line(im, (0, y), (w - 1, y), (0, 255, 255), 1)
        label = "%.1f" % (i * step)
        for pos in ((x + 3, 16), (3, y - 4)):
            cv2.putText(im, label, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(im, label, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    write_jpeg(im, dest, 88)


# ---------------------------------------------------------------------------------------------------------------- contact sheets
def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                         # an old Pillow has one size only
        return ImageFont.load_default()


def contact_sheet(tiles: list[tuple[str, Path | None]], dest: Path, *, cols: int = SHEET_COLS, tile: tuple[int, int] = TILE) -> None:
    """One picture of numbered thumbnails. `tiles`: [(number text, thumbnail path or None)]. A thumbnail that cannot be read shows a grey
    tile that says so (the number stays, so the numbers on the sheet and in the list never drift apart)."""
    from PIL import Image, ImageDraw
    if not tiles:
        raise ImageError("a contact sheet needs at least one tile")
    cols = max(1, min(cols, len(tiles)))
    rows = -(-len(tiles) // cols)
    gap = 8
    W, H = cols * tile[0] + (cols + 1) * gap, rows * tile[1] + (rows + 1) * gap
    sheet = Image.new("RGB", (W, H), (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    big, small = _font(34), _font(18)
    for k, (num, path) in enumerate(tiles):
        r, c = divmod(k, cols)
        x0, y0 = gap + c * (tile[0] + gap), gap + r * (tile[1] + gap)
        ok = False
        if path is not None:
            try:
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    im.thumbnail(tile)
                    sheet.paste(im, (x0 + (tile[0] - im.width) // 2, y0 + (tile[1] - im.height) // 2))
                    ok = True
            except Exception:           # noqa: BLE001 - a thumbnail that does not open is a grey tile, not a failure of the job
                ok = False
        if not ok:
            draw.rectangle([x0, y0, x0 + tile[0] - 1, y0 + tile[1] - 1], fill=(90, 90, 90))
            draw.text((x0 + tile[0] // 2 - 70, y0 + tile[1] // 2 - 10), "no preview", fill=(230, 230, 230), font=small)
        label = str(num)
        bw = 24 + 22 * len(label)
        draw.rectangle([x0, y0, x0 + bw, y0 + 46], fill=(0, 0, 0))
        draw.text((x0 + 12, y0 + 4), label, fill=(255, 255, 0), font=big)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, format="JPEG", quality=85)
