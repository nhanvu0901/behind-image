"""Operations of step 4. Pure functions of a project folder; the HTTP layer is `bti.editor.picks_api`.

Lock use: the network and the file work (search, download, rendering) run with NO lock; only the final read-modify-write of
picks.json holds `doc.Held` (the picks lock plus a check that the project still exists).
"""
from __future__ import annotations

from pathlib import Path

from bti.media import licence as _lic

from . import context, doc
from .errors import PicksError

SOURCES = ("commons", "met")
MIN_SHORT_SIDE = 1200
_media = None            # tests replace this with a module-like object; None means `bti.media.api`


def media():
    if _media is not None:
        return _media
    from bti.media import api
    return api


def _translate(e: BaseException) -> PicksError:
    """Map what the media facade raises to an error the page can show. Nothing here is about the licence: it is advisory."""
    n = type(e).__name__
    if n == "MediaHTTPError":
        st = getattr(e, "status", None)
        if st in (429, 502, 503, 504, None):
            return PicksError(503, "the image source is busy or not answering (HTTP %s)" % (st or "?"), "source_unreachable", retryable=True)
        return PicksError(502, "the image source answered with an error (HTTP %s)" % st, "source_error")
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
    return {"project": pid, "exists": d is not None, "picks": cur, "rev": rev, "approved": ap["approved"], "approval_reason": ap["reason"],
            "issues": iss, "narration": nv, "identity": ident, "details": det,
            "default_main_query": " ".join(x for x in (ident["title"], ident["artist"]) if x),
            "suggest": suggest_info or {"available": False}}


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
        main = raw.get("main_asset")
        if main is not None and main not in assets:
            raise PicksError(422, f"main_asset {str(main)[:40]} is not one of the assets", "unknown_asset")
        new["main_asset"] = main
        new["approval"] = old["approval"]
        return doc.save(pdir, new)


# ---------------------------------------------------------------- adding pictures
def _register(pdir: Path, key: str, asset: dict, as_main: bool) -> dict:
    """Add an imported asset to the picks (kept as it is when the key is already there) and, when asked, make it the main one."""
    with doc.Held(pdir):
        d = doc.load_or_new(pdir)
        if key not in d["assets"]:
            a = dict(asset)
            a["regions"] = dict(a.get("regions") or {})
            credit = dict(a.get("credit") or {})
            if "flag" not in credit:             # an asset imported before the flag existed
                credit["flag"] = _lic.with_size_flag(_lic.flag_for_text(credit.get("licence")), a.get("width", 0), a.get("height", 0), MIN_SHORT_SIDE)
            a["credit"] = credit
            d["assets"][key] = a
        if as_main:
            d["main_asset"] = key
        doc.save(pdir, d)
        return d["assets"][key]


def import_asset(pdir: Path, source: str, source_id: str, as_main: bool = False) -> dict:
    """Download a candidate (Commons, Met) into media/ and add it to the picks. Never refused for its licence or its size:
    the asset's `credit.flag` says what is doubtful. Returns `{asset_key, asset}`."""
    if source not in SOURCES:
        raise PicksError(422, f"unknown source {source[:30]!r}", "unknown_source")
    try:
        res = media().import_candidate(pdir, source, source_id, require_root=True)
    except PicksError:
        raise
    except FileNotFoundError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)
    asset = _register(pdir, res["asset_key"], res["asset"], as_main)
    return {"asset_key": res["asset_key"], "asset": asset}


def import_book(pdir: Path, source_id: str, as_main: bool = False) -> dict:
    """Import a picture of one of the project's books (a page, or an image of the PDF)."""
    if not context.book_source_allowed(pdir, source_id):
        raise PicksError(404, "this picture is not part of the project's books", "not_found")
    try:
        res = media().import_candidate(pdir, "book", source_id, require_root=True)
    except FileNotFoundError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)
    asset = _register(pdir, res["asset_key"], res["asset"], as_main)
    return {"asset_key": res["asset_key"], "asset": asset}


def upload(pdir: Path, file_path: Path, meta: dict, as_main: bool = False) -> dict:
    try:
        res = media().add_upload(pdir, file_path, meta, require_root=True)
    except FileNotFoundError:
        raise
    except Exception as e:      # noqa: BLE001
        raise _translate(e)
    asset = _register(pdir, res["asset_key"], res["asset"], as_main)
    return {"asset_key": res["asset_key"], "asset": asset}


# ---------------------------------------------------------------- search
def search(pdir: Path, query: str, beat: str | None = None, sources=None, limit: int = 18) -> dict:
    """Candidates from Commons and the Met. With no `query`, the first query of `beat` (its `show` words). Each source that fails
    is reported in `errors`; the others still answer. Candidates already imported say so (`imported`)."""
    query = (query or "").strip()
    if not query and beat:
        nv = context.narration_view(pdir)
        b = next((x for c in nv["chapters"] for x in c["beats"] if x["id"] == beat), None)
        if b is None:
            raise PicksError(404, "beat not found", "not_found")
        query = context.default_query(b["show"], context.details(pdir), context.identity(pdir))
    if not query:
        raise PicksError(422, "query is required", "query_required")
    srcs = [s for s in (sources or SOURCES) if s in SOURCES] or list(SOURCES)
    limit = max(1, min(int(limit), 40))
    items, errors = [], []
    seen = set()
    for s in srcs:
        try:
            found = media().search(query, source=s, kind="image", limit=limit)
        except Exception as e:      # noqa: BLE001
            pe = _translate(e)
            errors.append({"source": s, "code": pe.code, "message": pe.detail})
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
def approve(pdir: Path, rev) -> dict:
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
            return doc.stamp_approval(pdir, rev, nv["rev"])
        except doc.StaleRevision as e:
            raise PicksError(409, "the file changed since you loaded it; reload before approving", "stale", rev=str(e))
