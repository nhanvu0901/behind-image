"""Adapter for the media facade (design 8.2, 8.3).

`bti.media.api` is imported lazily per app start. Without it, a fixed
candidate list and local placeholder images are used, and no network call is
made.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .common import ApiError, read_json, safe_join
from .engine_adapter import import_facade


class LicenceRejected(Exception):
    pass


ALLOWED = ("pd", "public domain", "cc0", "cc by", "cc-by", "cc by-sa", "cc-by-sa")
_CANDS = [
    ("commons", "File:Stub_Portrait_1.jpg", "Portrait of a man (stub)", "Stub Artist", "PD", True, 3000, 4000),
    ("commons", "File:Stub_Landscape_1.jpg", "Winter landscape (stub)", "Stub Painter", "CC BY-SA 4.0", True, 4000, 2600),
    ("commons", "File:Stub_Interior_1.jpg", "Interior with mirror (stub)", "Stub Master", "CC0", True, 2400, 3200),
    ("commons", "File:Stub_Detail_1.jpg", "Detail of hands (stub)", "Stub Photographer", "CC BY 4.0", True, 2000, 2000),
    ("met", "stub-met-1001", "Stub Madonna", "Stub Anonymous", "CC0", True, 3200, 4200),
    ("commons", "File:Stub_NC_1.jpg", "Photo with NC licence (stub)", "Stub Photographer", "CC BY-NC 4.0", False, 2000, 1500),
    ("commons", "File:Stub_Unknown_1.jpg", "Unknown licence (stub)", "unknown", "", False, 1600, 1200),
    ("commons", "File:Stub_Map_1.png", "Old map (stub)", "Stub Cartographer", "PD", True, 3600, 2400),
]


def _licence_ok(lic: str) -> tuple[bool, str, str]:
    """(on the allow list?, licence name, why not). Advisory: it only decides the flag, nothing is refused."""
    name = (lic or "").strip()
    low = name.lower()
    if not low:
        return False, "", "licence missing"
    if re.search(r"\b(nc|nd)\b|non-?commercial|no-?deriv|fair use", low):
        return False, name, f"licence {name} is restricted (NC, ND or fair use)"
    if low.startswith(ALLOWED) or low == "pd":
        return True, name, "allowed"
    return False, name, f"licence {name!r} is not on the allow list"


def _flag(lic: str, w: int = 0, h: int = 0) -> str | None:
    """The advisory flag of an asset, like `bti.media.licence`: rejected | unknown | small | None."""
    ok, name, reason = _licence_ok(lic)
    if not ok:
        flag = "unknown" if not name else "rejected"
    elif min(w, h) and min(w, h) < 1200:
        flag = "small"
    else:
        flag = None
    return flag


def _placeholder(path: Path, label: str, w: int = 1200, h: int = 1600) -> None:
    img = Image.new("RGB", (w, h), (150, 140, 120))
    d = ImageDraw.Draw(img)
    d.rectangle([w // 10, h // 10, w - w // 10, h - h // 10], outline=(60, 50, 40), width=8)
    d.text((w // 8, h // 2), label, fill=(30, 25, 20))
    path.parent.mkdir(exist_ok=True)           # media/ only: never the project folder
    img.save(path, "JPEG", quality=80)


def _translate(e: Exception) -> Exception:
    """Map exceptions of the real facade to what the HTTP layer understands."""
    n = type(e).__name__
    if n == "LicenceRejected":
        return LicenceRejected(str(e))
    if isinstance(e, (ApiError, FileNotFoundError)):       # FileNotFoundError: the project was deleted meanwhile (404 by the app)
        return e
    if isinstance(e, ValueError):
        code = getattr(e, "code", None)
        return ApiError(422, str(e)[:300], **({"code": code, "reason": str(e)[:300]} if code else {}))
    if n == "ImageTooSmall":
        return ApiError(422, str(e)[:300], reason=str(e)[:300])
    if n == "MediaHTTPError":
        st = getattr(e, "status", None)
        if getattr(e, "rate_limited", False):
            # the source said "too many requests": the page names the wait it asked for (seconds; null when it gave none),
            # the same code and body as bti.picks.service, so the same sentence is shown (errmsg.js `sourceLimitText`)
            return ApiError(503, "the image source limits downloads: wait before trying again (HTTP %s)" % st, code="source_rate_limited",
                            retryable=True, retry_after=getattr(e, "retry_after", None))
        if st in (429, 503, 502, 504, None):
            return ApiError(503, "Nguồn ảnh đang giới hạn tốc độ hoặc không phản hồi (HTTP %s). Hãy thử lại sau vài giây." % (st or "?"),
                            retryable=True, retry_after=10)
        return ApiError(502, f"media source error (HTTP {st}): {e}"[:300])
    if n == "NotFound":
        return ApiError(404, str(e)[:300])
    return ApiError(502, f"media facade failed: {n}: {e}"[:300])


class MediaAdapter:
    def __init__(self, projects_root: Path, module: Any = "auto"):
        self.projects_root = Path(projects_root)
        if module == "auto":
            module = import_facade("bti.media.api")
        if module is not None and not all(hasattr(module, n) for n in ("search", "import_candidate", "add_upload")):
            module = None
        self.module = module
        self.mode = "real" if module is not None else "stub"

    def health(self) -> dict:
        return {"media": self.mode}

    # ----- search -----
    def search(self, q: str, source: str, kind: str, limit: int) -> list[dict]:
        if self.module is not None:
            try:
                return list(self.module.search(q, source=source, kind=kind, limit=limit))
            except Exception as e:  # noqa: BLE001
                raise _translate(e)
        out = []
        for src, sid, title, author, lic, ok, w, h in _CANDS:
            if source and source != "all" and src != source:
                continue
            _, _, reason = _licence_ok(lic)
            out.append({"source": src, "source_id": sid, "title": title,
                        "thumb_url": f"/api/media/stub-thumb/{re.sub(r'[^A-Za-z0-9]', '_', sid)}.jpg",
                        "page_url": f"https://example.invalid/{sid}", "width": w, "height": h,
                        "mime": "image/png" if sid.endswith(".png") else "image/jpeg", "author": author,
                        "licence": lic, "licence_ok": ok, "licence_reason": reason, "flag": _flag(lic, w, h)})
        return out[:limit]

    # ----- import / upload -----
    def _next_key(self, project_dir: Path) -> str:
        used: set[str] = set()
        try:
            used = set((read_json(project_dir / "storyboard.json").get("assets") or {}).keys())
        except Exception:
            pass
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if c not in used:
                return c
        n = 1
        while f"A{n}" in used:
            n += 1
        return f"A{n}"

    def import_candidate(self, project_dir: Path, source: str, source_id: str) -> dict:
        if self.module is not None:
            try:
                return self.module.import_candidate(project_dir, source, source_id, require_root=True)
            except Exception as e:  # noqa: BLE001
                raise _translate(e)
        cand = next((c for c in _CANDS if c[0] == source and c[1] == source_id), None)
        if cand is None:
            raise ApiError(404, "unknown candidate")
        _, _, title, author, lic, _, w, h = cand
        ok, name, reason = _licence_ok(lic)         # advisory: a restricted or unknown licence is flagged, never refused
        key = self._next_key(project_dir)
        fname = f"media/stub_{re.sub(r'[^A-Za-z0-9]', '_', source_id)}.jpg"
        _placeholder(project_dir / fname, title, 1200, round(1200 * h / w))
        asset = {"file": fname, "kind": "image", "title": title, "artist": author, "year": "",
                 "width": 1200, "height": round(1200 * h / w),
                 "credit": {"source": source, "source_url": f"https://example.invalid/{source_id}",
                            "author": author, "licence": name, "licence_url": "", "flag": _flag(lic, 1200, round(1200 * h / w))}, "regions": {}}
        return {"asset_key": key, "asset": asset}

    def add_upload(self, project_dir: Path, file_path: Path, meta: dict) -> dict:
        if self.module is not None:
            try:
                return self.module.add_upload(project_dir, file_path, meta, require_root=True)
            except Exception as e:  # noqa: BLE001
                raise _translate(e)
        ok, name, reason = _licence_ok(meta.get("licence", ""))         # advisory: no licence, source or author is required
        ext_in = file_path.suffix.lower()
        if ext_in in {".mp4", ".webm", ".mov", ".m4v"}:
            from bti.media import clips
            key = self._next_key(project_dir)
            dest = safe_join(project_dir, "media") / f"upload_{key}.mp4"
            dest.parent.mkdir(exist_ok=True)
            try:
                clips.normalize(file_path, dest, strip_audio=True)
            except clips.MediaError as exc:
                if isinstance(exc, clips.ToolMissing):
                    shutil.copyfile(file_path, dest)
                else:
                    raise ApiError(422, f"video cannot be processed: {exc}", code="video_unreadable", reason="video cannot be processed")
            p2 = clips.probe_video(dest)
            w, h, dur = p2["width"], p2["height"], p2["duration"]
            asset = {"file": f"media/{dest.name}", "kind": "video", "title": meta.get("title") or "", "artist": meta.get("artist") or "",
                     "year": meta.get("year") or "", "width": w, "height": h,
                     "credit": {"source": "upload", "source_url": meta.get("source_url") or "", "author": meta.get("author") or "",
                                "licence": name, "licence_url": "", "flag": _flag(meta.get("licence", ""), 0, 0)}, "regions": {}}
            if dur:
                asset["duration"] = dur
            return {"asset_key": key, "asset": asset}
        try:
            with Image.open(file_path) as im:
                w, h = im.size
                fmt = (im.format or "JPEG").lower()
        except Exception:
            raise ApiError(422, "file is not a readable image", code="image_unreadable", reason="file is not a readable image")
        ext = {"jpeg": "jpg", "png": "png", "webp": "webp"}.get(fmt)
        if ext is None:
            raise ApiError(422, f"unsupported image format {fmt}")
        key = self._next_key(project_dir)
        rel = f"media/upload_{key}.{ext}"
        dest = safe_join(project_dir, "media") / f"upload_{key}.{ext}"
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(file_path, dest)
        asset = {"file": rel, "kind": "image", "title": meta.get("title") or "", "artist": meta.get("artist") or "",
                 "year": meta.get("year") or "", "width": w, "height": h,
                 "credit": {"source": "upload", "source_url": meta.get("source_url") or "", "author": meta.get("author") or "",
                            "licence": name, "licence_url": "", "flag": _flag(meta.get("licence", ""), w, h)}, "regions": {}}
        return {"asset_key": key, "asset": asset}

    def stub_thumb(self, name: str) -> bytes:
        import io
        img = Image.new("RGB", (320, 240), (130, 125, 110))
        ImageDraw.Draw(img).text((12, 110), name[:40], fill=(20, 20, 20))
        b = io.BytesIO()
        img.save(b, "JPEG", quality=70)
        return b.getvalue()
