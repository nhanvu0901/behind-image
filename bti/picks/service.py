"""Operations of step 4. Pure functions of a project folder; the HTTP layer is `bti.editor.picks_api`.

Lock use: the network and the file work (search, download, rendering) run with NO lock; only the final read-modify-write of
picks.json holds `doc.Held` (the picks lock plus a check that the project still exists).
"""
from __future__ import annotations

from pathlib import Path

from bti.media import contentbox as _contentbox          # panelbox: the painted area of a picture
from bti.media import licence as _lic

from . import context, doc
from .errors import PicksError

SOURCES = ("commons", "met", "pexels", "pixabay", "osm", "web")      # the sources a picture can be imported from (`web`: an address found by the web search)
KEYED_SOURCES = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}
SEARCH_ONLY = ("wikipedia",)       # free, asked for candidates only: what it offers are Commons files, imported as `commons`
PAID_SOURCES = ("web",)            # the You.com web search: never in a default search, and searched only for a caller that says `allow_paid` (the automatic job)
MIN_SHORT_SIDE = 1200
_media = None            # tests replace this with a module-like object; None means `bti.media.api`


def media():
    if _media is not None:
        return _media
    from bti.media import api
    return api


def _boxed(pdir: Path, res):
    """panelbox: a picture that came in (`{asset_key, asset}`) gets the program's finding of its painted area, `content_box` (`bti.media.contentbox`), before it is
    added to the picks. A video, a file that does not read as a picture, or a fake of a test leaves the asset as it is."""
    a = res.get("asset") if isinstance(res, dict) else None
    if isinstance(a, dict) and a.get("kind") == "image":
        try:
            _contentbox.ensure(a, pdir)
        except Exception:       # noqa: BLE001 - the box is an extra: a picture is never refused for it
            pass
    return res


def _translate(e: BaseException) -> PicksError:
    """Map what the media facade raises to an error the page can show. Nothing here is about the licence: it is advisory."""
    n = type(e).__name__
    if n == "ToolMissing":
        return PicksError(503, str(e)[:200], "tool_missing")
    if n == "DownloadTimeout":
        return PicksError(504, str(e)[:200], "video_timeout", retryable=True)
    if n == "MediaHTTPError":
        st = getattr(e, "status", None)
        if getattr(e, "rate_limited", False):
            # the source said "too many requests": its own code, and the wait it asked for (seconds, null when it gave none)
            return PicksError(503, "the image source limits downloads: wait before trying again (HTTP %s)" % st, "source_rate_limited",
                              retryable=True, retry_after=getattr(e, "retry_after", None))
        if st in (429, 502, 503, 504, None):
            return PicksError(503, "the image source is busy or not answering (HTTP %s)" % (st or "?"), "source_unreachable", retryable=True)
        return PicksError(502, "the image source answered with an error (HTTP %s)" % st, "source_error")
    if n == "MediaError":
        return PicksError(502, str(e)[:240], "video_fetch_failed")
    if n == "NotFound":
        return PicksError(404, str(e)[:200], "not_found")
    if isinstance(e, ValueError):
        code = getattr(e, "code", None) or "invalid"
        return PicksError(422, str(e)[:200], code)
    return PicksError(502, "the image source failed (%s)" % n, "source_error")


# ---------------------------------------------------------------- the page's whole state
def payload(pdir: Path, pid: str, suggest_info: dict | None = None) -> dict:
    d = doc.load(pdir)
    cur = d if d is not None else doc.empty()
    nv = context.narration_view(pdir)
    rev = doc.revision(cur)
    ap = doc.approval_state(cur, nv["rev"], nv["approved"])
    iss = doc.issues(cur, pdir, nv["beat_ids"] if nv["present"] else None)
    ident = context.identity(pdir)
    det = context.details(pdir)
    from bti.media import clips
    from bti.script import env
    vtools = clips.tool_status()
    sources_info = {
        "commons": {"available": True, "has_key": True},
        "met": {"available": True, "has_key": True},
        "pexels": {"available": env.has_key("PEXELS_API_KEY"), "has_key": env.has_key("PEXELS_API_KEY")},
        "pixabay": {"available": env.has_key("PIXABAY_API_KEY"), "has_key": env.has_key("PIXABAY_API_KEY")},
        "osm": {"available": True, "has_key": True},
    }
    return {"project": pid, "exists": d is not None, "picks": cur, "rev": rev, "approved": ap["approved"], "approval_reason": ap["reason"],
            "issues": iss, "outside": doc.outside_summary(cur, nv["beat_ids"] if nv["present"] else None),
            "narration": nv, "identity": ident, "details": det,
            "default_main_query": " ".join(x for x in (ident["title"], ident["artist"]) if x),
            "suggest": suggest_info or {"available": False},
            "video_tools": vtools,
            "sources": sources_info}



# ---------------------------------------------------------------- saving the owner's edits
def put(pdir: Path, raw: dict, base_rev) -> str:
    """Replace the beats, the main painting and the editable fields of the assets (title, artist, year, regions); the asset
    keys that are not in `raw` are removed from the picks (their files stay in media/). An asset cannot be INVENTED here
    (no file is created by a save): its file, size and credit are what is on disk. Returns the new revision."""
    problem = doc.doc_problem(raw)
    if problem:
        raise PicksError(422, problem, "invalid")
    with doc.Held(pdir):
        cur = doc.load(pdir)
        cur_rev = doc.revision(cur) if cur is not None else None
        if cur is not None and base_rev != cur_rev:
            raise PicksError(409, "the file changed since you loaded it; reload before saving", "stale", rev=cur_rev)
        old = cur or doc.empty()
        new = doc.normalize(raw)
        assets = {}
        for k in raw.get("assets") or {}:
            if k not in old["assets"]:
                raise PicksError(422, f"asset {k} is not in the picks: add pictures with the import routes", "unknown_asset", asset=k)
            keep = dict(old["assets"][k])
            nk = new["assets"].get(k, {})
            for f in ("title", "artist", "year"):
                keep[f] = nk.get(f, keep[f])
            keep["regions"] = nk.get("regions", {})
            assets[k] = keep
        new["assets"] = assets
        for bid, b in new["beats"].items():                   # what the agent knows of a line (`kinds`, `missing`) stays unless this save sends new ones
            raw_b = (raw.get("beats") or {}).get(bid) or {}
            for key in ("kinds", "missing"):
                if key not in raw_b and old["beats"].get(bid, {}).get(key):
                    b[key] = old["beats"][bid][key]
        main = raw.get("main_asset")
        if main is not None and main not in assets:
            raise PicksError(422, f"main_asset {str(main)[:40]} is not one of the assets", "unknown_asset")
        new["main_asset"] = main
        new["approval"] = old["approval"]
        return doc.save(pdir, new)


# ---------------------------------------------------------------- adding pictures
def register_into(d: dict, key: str, asset: dict, as_main: bool) -> dict:
    """The in-memory half of `_register`: add an imported asset to the picks document `d` (kept as it is when the key is already
    there) and, when asked, make it the main one. Returns the asset as it is in `d`. Nothing is read or written."""
    if key not in d["assets"]:
        a = dict(asset)
        a["regions"] = dict(a.get("regions") or {})
        credit = dict(a.get("credit") or {})
        if "flag" not in credit:             # an asset imported before the flag existed
            lf = _lic.flag_for_text(credit.get("licence"))
            credit["flag"] = lf if a.get("kind") == "video" else _lic.with_size_flag(lf, a.get("width", 0), a.get("height", 0), MIN_SHORT_SIDE)
        a["credit"] = credit
        d["assets"][key] = a
    if as_main:
        d["main_asset"] = key
    return d["assets"][key]


def _register(pdir: Path, key: str, asset: dict, as_main: bool) -> dict:
    """Add an imported asset to the picks (kept as it is when the key is already there) and, when asked, make it the main one."""
    with doc.Held(pdir):
        d = doc.load_or_new(pdir)
        register_into(d, key, asset, as_main)
        doc.save(pdir, d)
        return d["assets"][key]


def _fetch_source(pdir: Path, source: str, source_id: str) -> dict:
    """The download half of `import_asset`: the checks and the errors of that route."""
    if source not in SOURCES:
        raise PicksError(422, f"unknown source {source[:30]!r}", "unknown_source")
    try:
        return _boxed(pdir, media().import_candidate(pdir, source, source_id, require_root=True))
    except PicksError:
        raise
    except FileNotFoundError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)


def _fetch_book(pdir: Path, source_id: str) -> dict:
    """The download half of `import_book`: the checks and the errors of that route."""
    if not context.book_source_allowed(pdir, source_id):
        raise PicksError(404, "this picture is not part of the project's books", "not_found")
    try:
        return _boxed(pdir, media().import_candidate(pdir, "book", source_id, require_root=True))
    except FileNotFoundError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)


def fetch_asset(pdir: Path, source: str, source_id: str) -> dict:
    """Bring a found picture into media/ and return what the media facade returns (`{asset_key, asset}`); nothing is written to
    picks.json. `source` is one of SOURCES, or "book" for a picture of the project's books. This is the download half of
    `import_asset` and `import_book` with the same checks and the same `PicksError`s; a batch of operations
    (`bti.ops`) calls it before it takes the picks lock."""
    return _fetch_book(pdir, source_id) if source == "book" else _fetch_source(pdir, source, source_id)


def import_asset(pdir: Path, source: str, source_id: str, as_main: bool = False) -> dict:
    """Download a candidate (Commons, Met, Pexels, Pixabay, OSM) into media/ and add it to the picks. Never refused for its licence or its size:
    the asset's `credit.flag` says what is doubtful. Returns `{asset_key, asset}`."""
    res = _fetch_source(pdir, source, source_id)
    if as_main and res.get("asset", {}).get("kind") == "video":
        raise PicksError(422, "a video cannot be set as the main painting", "video_not_main")
    asset = _register(pdir, res["asset_key"], res["asset"], as_main)
    return {"asset_key": res["asset_key"], "asset": asset}


def import_book(pdir: Path, source_id: str, as_main: bool = False) -> dict:
    """Import a picture of one of the project's books (a page, or an image of the PDF)."""
    res = _fetch_book(pdir, source_id)
    asset = _register(pdir, res["asset_key"], res["asset"], as_main)
    return {"asset_key": res["asset_key"], "asset": asset}


def upload(pdir: Path, file_path: Path, meta: dict, as_main: bool = False) -> dict:
    try:
        res = _boxed(pdir, media().add_upload(pdir, file_path, meta, require_root=True))
    except FileNotFoundError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)
    asset = _register(pdir, res["asset_key"], res["asset"], as_main)
    return {"asset_key": res["asset_key"], "asset": asset}


# ---------------------------------------------------------------- search
def search(pdir: Path, query: str, beat: str | None = None, sources=None, limit: int = 18, kind: str = "image", *, allow_paid: bool = False) -> dict:
    """Candidates from Commons, Met, Pexels, Pixabay, OSM (and, asked for by name, Wikipedia; the paid `web` only with `allow_paid`, which only the
    automatic picks job says). With no `query`, the first query of `beat` (its `show` words).
    Each source that fails is reported in `errors`; the others still answer. Candidates already imported say so (`imported`)."""
    query = (query or "").strip()
    if not query and beat:
        nv = context.narration_view(pdir)
        b = next((x for c in nv["chapters"] for x in c["beats"] if x["id"] == beat), None)
        if b is None:
            raise PicksError(404, "beat not found", "not_found")
        query = context.default_query(b["show"], context.details(pdir), context.identity(pdir))
    if not query:
        raise PicksError(422, "query is required", "query_required")
    from bti.script import env
    if sources is not None:
        srcs = [s for s in sources if (s in SOURCES or s in SEARCH_ONLY) and (s not in PAID_SOURCES or allow_paid)]
    else:
        srcs = [s for s in SOURCES if s not in PAID_SOURCES and (s not in KEYED_SOURCES or env.has_key(KEYED_SOURCES[s]))]
    limit = max(1, min(int(limit), 40))
    items, errors = [], []
    seen = set()
    for s in srcs:
        if s in KEYED_SOURCES and not env.has_key(KEYED_SOURCES[s]):
            errors.append({"source": s, "code": "source_no_key", "message": "chưa có khóa"})
            continue
        try:
            if kind == "all":
                found = media().search(query, source=s, kind="image", limit=limit)
                if s in ("pexels", "pixabay", "commons"):
                    try:
                        vfound = media().search(query, source=s, kind="video", limit=limit)
                        found = (found + vfound)[:limit]
                    except Exception:
                        pass
            else:
                found = media().search(query, source=s, kind=kind if kind in ("image", "video") else "image", limit=limit)
        except Exception as e:      # noqa: BLE001
            pe = _translate(e)
            errors.append({"source": s, "code": pe.code, "message": pe.detail,
                           **({"retry_after": pe.extra.get("retry_after")} if pe.code == "source_rate_limited" else {})})
            continue
        for c in found:
            ident = (c.get("source"), c.get("source_id"))
            if ident not in seen:
                seen.add(ident)
                items.append(c)
    from bti.media import assets as _assets
    idx = _assets.load_index(pdir)["items"]
    for c in items:
        hit = idx.get(f"{c.get('source')}:{c.get('source_id')}")
        c["imported"] = hit["key"] if hit else None
    return {"query": query, "items": items, "errors": errors}


# ---------------------------------------------------------------- video search & clip import
MAX_CLIP_S = 120.0
MIN_CLIP_S = 0.5


def video_search(pdir: Path, query: str = "", beat: str | None = None, url: str = "",
                 confirm_paid: bool = False, limit: int = 6, *, search_fn=None, metadata_fn=None) -> dict:
    """Find candidate YouTube moments either by inspecting a pasted URL (`url`, free yt-dlp metadata)
    or via You.com Search (`confirm_paid=True` required)."""
    from bti.media import clips

    url = (url or "").strip()
    query = (query or "").strip()
    if not query and beat:
        nv = context.narration_view(pdir)
        b = next((x for c in nv["chapters"] for x in c["beats"] if x["id"] == beat), None)
        if b is None:
            raise PicksError(404, "beat not found", "not_found")
        query = context.default_query(b["show"], context.details(pdir), context.identity(pdir))
    if not url and query and clips.video_id(query):
        url, query = query, ""
    if url:
        try:
            url = clips.safe_youtube_url(url)
        except ValueError:
            raise PicksError(422, "not a supported YouTube URL", "video_bad_url")
        try:
            row = media().inspect_video_url(url, desc=query, metadata=metadata_fn)
        except FileNotFoundError:
            raise
        except PicksError:
            raise
        except Exception as e:      # noqa: BLE001
            raise _translate(e)
        return {"query": query, "url": url, "paid": False, "items": [row]}
    if not confirm_paid:
        raise PicksError(422, "confirm_paid must be true before calling You.com search", "confirm_required")
    if not query:
        raise PicksError(422, "query is required", "query_required")
    if search_fn is None and not clips._ydc_key():
        raise PicksError(503, "YDC_API_KEY is not set", "youcom_key_missing")
    lim = max(1, min(int(limit), 12))
    try:
        rows = media().moment_search(query, limit=lim, search=search_fn, metadata=metadata_fn)
    except FileNotFoundError:
        raise
    except PicksError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)
    return {"query": query, "url": "", "paid": True, "items": rows}


def import_video_clip(pdir: Path, url: str, start: float, end: float, *, title: str = "",
                      beat_id: str | None = None, role: str = "video", note: str = "",
                      clip_importer=None) -> dict:
    """Download [start, end] of a YouTube video (silent 30fps MP4, advisory licence flag)
    outside the lock, then register it in picks.json (and optionally attach it to `beat_id`)."""
    from bti.media import clips

    url = (url or "").strip()
    try:
        url = clips.safe_youtube_url(url)
    except ValueError:
        raise PicksError(422, "not a supported YouTube URL", "video_bad_url")
    try:
        s_val = float(start)
        e_val = float(end)
    except (TypeError, ValueError):
        raise PicksError(422, "start and end must be numbers", "video_bad_range")
    import math
    span = e_val - s_val
    if not (math.isfinite(s_val) and math.isfinite(e_val)) or s_val < 0 or not (MIN_CLIP_S <= span <= MAX_CLIP_S):
        raise PicksError(422, f"clip range must be between {MIN_CLIP_S:g} and {MAX_CLIP_S:g} seconds", "video_bad_range")
    if beat_id is not None and not doc.BEAT_ID_RE.fullmatch(beat_id):
        raise PicksError(422, f"invalid beat id {beat_id!r}", "invalid")
    imp = clip_importer or (lambda *a, **k: media().import_clip(*a, **k))
    try:
        res = imp(pdir, url, s_val, e_val, strict_licence=False, require_root=True)
    except FileNotFoundError:
        raise
    except PicksError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)
    asset = dict(res["asset"])
    if title.strip():
        asset["title"] = title.strip()[:120]
    key = res["asset_key"]
    saved = _register(pdir, key, asset, False)
    if beat_id:
        with doc.Held(pdir):
            d = doc.load_or_new(pdir)
            b = d["beats"].setdefault(beat_id, {"items": [], "status": "todo", "note": ""})
            use_role = role if role in doc.ROLES else "video"
            b["items"].append({"asset": key, "region": None, "role": use_role, "note": str(note or "")[:400]})
            b["status"] = "picked"
            doc.save(pdir, d)
            saved = d["assets"].get(key, saved)
    return {"asset_key": key, "asset": saved}


def start_clip_job(pdir: Path, pid: str, url: str, start: float, end: float, *, title: str = "",
                   beat_id: str | None = None, role: str = "video", note: str = "",
                   clip_importer=None) -> dict:
    """Start cutting a YouTube clip as a long job (kind='picks'). Returns {'job_id': ...}."""
    from bti.media import clips
    import math

    url = (url or "").strip()
    try:
        canon_url = clips.safe_youtube_url(url)
    except ValueError:
        raise PicksError(422, "not a supported YouTube URL", "video_bad_url")
    try:
        s_val = float(start)
        e_val = float(end)
    except (TypeError, ValueError):
        raise PicksError(422, "start and end must be numbers", "video_bad_range")
    span = e_val - s_val
    if not (math.isfinite(s_val) and math.isfinite(e_val)) or s_val < 0 or not (MIN_CLIP_S <= span <= MAX_CLIP_S):
        raise PicksError(422, f"clip range must be between {MIN_CLIP_S:g} and {MAX_CLIP_S:g} seconds", "video_bad_range")
    if beat_id is not None and not doc.BEAT_ID_RE.fullmatch(beat_id):
        raise PicksError(422, f"invalid beat id {beat_id!r}", "invalid")

    try:
        import bti.longjob as lj
    except ImportError:
        raise PicksError(503, "the long-job runner is not available yet", "longjob_missing")

    def run_clip(c):
        if c.cancelled():
            return None
        c.progress(0.1, "Đang tải đoạn video...")
        try:
            res = import_video_clip(
                pdir, canon_url, s_val, e_val, title=title, beat_id=beat_id, role=role, note=note,
                clip_importer=clip_importer,
            )
        except Exception as e:
            if c.cancelled():
                return None
            pe = _translate(e)
            raise lj.PartError(pe.code or "video_failed", pe.detail)
        if c.cancelled():
            return None
        c.progress(1.0, "Đã cắt xong đoạn video.")
        return res

    vid = clips.video_id(canon_url) or "clip"
    part = lj.Part(
        key=f"clip-{vid}-{s_val:.1f}-{e_val:.1f}",
        title=f"Cắt clip {s_val:.1f}–{e_val:.1f}s",
        run=run_clip,
        heavy=False,
        est_seconds=60,
    )
    try:
        job = lj.manager.start(
            kind="picks",
            pid=pid,
            project_dir=pdir,
            parts=[part],
            meta={
                "action": "clip",
                "url": canon_url,
                "start": s_val,
                "end": e_val,
                "title": title,
                "beat_id": beat_id,
                "role": role,
                "note": note,
            },
        )
    except getattr(lj, "Busy", ()) as e:
        raise PicksError(409, "a picks job is already running for this project", "busy",
                         job_id=(getattr(e, "job", None) or {}).get("id"))
    jid = job["id"] if isinstance(job, dict) else getattr(job, "id", str(job))
    return {"job_id": jid}



# ---------------------------------------------------------------- regions
def check_regions(regions, asset: dict) -> dict:
    """Validate regions drawn on an image. Pixels of the source image; the centre must lie inside it."""
    if not isinstance(regions, dict):
        raise PicksError(422, "regions (object) is required", "invalid")
    w, h = int(asset.get("width") or 0), int(asset.get("height") or 0)
    out = {}
    for name, r in regions.items():
        if not isinstance(name, str) or not doc.REGION_RE.fullmatch(name):
            raise PicksError(422, f"region name {str(name)[:40]!r} is not valid", "region_name", region=str(name)[:40])
        rr = doc._region(r)
        if rr is None:
            raise PicksError(422, f"region {name!r} needs numeric x and y", "region_shape", region=name)
        if (w and not 0 <= rr["x"] <= w) or (h and not 0 <= rr["y"] <= h):
            raise PicksError(422, f"region {name!r} is outside the picture", "region_outside", region=name)
        if len(rr["label"]) > 80:
            raise PicksError(422, f"the label of region {name!r} is too long", "region_shape", region=name)
        out[name] = rr
    if len(out) > 60:
        raise PicksError(422, "too many regions", "invalid")
    return out


def set_regions(pdir: Path, key: str, regions, base_rev=None) -> str:
    with doc.Held(pdir):
        d = doc.load(pdir)
        if d is None or key not in d["assets"]:
            raise PicksError(404, "asset not found", "not_found")
        cur_rev = doc.revision(d)
        if base_rev is not None and base_rev != cur_rev:
            raise PicksError(409, "the file changed since you loaded it; reload before saving", "stale", rev=cur_rev)
        d["assets"][key]["regions"] = check_regions(regions, d["assets"][key])
        return doc.save(pdir, d)


# ---------------------------------------------------------------- approval
def approve(pdir: Path, rev, by: str | None = None) -> dict:
    if not isinstance(rev, str) or not rev:
        raise PicksError(422, "rev (string) is required", "invalid")
    with doc.Held(pdir):
        d = doc.load(pdir)
        if d is None:
            raise PicksError(404, "no picks to approve", "no_picks")
        nv = context.narration_view(pdir)
        if not nv["approved"]:
            raise PicksError(409, "the narration is not approved (or changed): approve it first", "narration_not_approved")
        errs = doc.blocking(doc.issues(d, pdir, nv["beat_ids"]))
        if errs:
            raise PicksError(422, "the picks have errors: " + "; ".join(e["message"] for e in errs), "picks_have_errors", issues=errs)
        try:
            return doc.stamp_approval(pdir, rev, nv["rev"], by)       # c5cli: `by` is who approved
        except doc.StaleRevision as e:
            raise PicksError(409, "the file changed since you loaded it; reload before approving", "stale", rev=str(e))
