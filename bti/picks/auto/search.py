"""Part 2 of the automatic picks job: find candidates for every picture the plan asks for. Code only: no model, and never the paid
suggestion service (`bti.picks.suggest`) - this module does not import it.

What each wanted picture asks, and of which source (the free sources the app already has; a source that needs a key is asked only
when the key is set):

    context  work / portrait / document   Wikimedia Commons, The Met
             photo / place                Wikimedia Commons, Pexels, Pixabay (stock photographs)
             other                        Wikimedia Commons, The Met, Pexels, Pixabay
    map                                   OpenStreetMap (one place, by name)
    clip                                  Pexels, Pixabay and Wikimedia Commons, as VIDEO (the pictures of the same sources, searched as video)

The first query of a want (the plan's `search`) goes to every source of its kind; the alternatives (`alt`) are tried only while fewer
than three candidates were found. The pictures in the owner's books are not searched (a book has no captions to search): the ones that
have a size worth showing are given to the choosing step as one numbered set (B1, B2 ...) that any want may pick from.

A source that answers "too many requests" is left alone for the time it states (`bti.media.http` already keeps a host quiet for that
time; this module also remembers it for the run and reports it): the wants that depended on it are marked `limited` (not found for now,
with the wait) and the job goes on. Nothing in here sleeps. The time spent is capped (`SEARCH_SECONDS`); a want the cap leaves unsearched
is `pending` and a resumed run searches it.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

from bti.picks import context, service
from bti.script import env

from . import images, store

SEARCH_SECONDS = 10 * 60
PER_WANT = 6                 # candidates kept per wanted picture
FIRST_LIMIT = 6              # results asked of a source for the first query
MORE_LIMIT = 4               # ... for an alternative query
ENOUGH = 3                   # alternatives are tried only while fewer candidates than this were found
DEFAULT_WAIT = 60            # seconds a "too many requests" without a time is honoured for
THUMB_SIDE = 640
THUMB_BYTES = 4_000_000
MAX_BOOK_PICTURES = 24
MIN_BOOK_SIDE = 250
KEYED = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}
SOURCES_BY_KIND = {
    "work": ("commons", "met"), "portrait": ("commons", "met"), "document": ("commons", "met"),
    "photo": ("commons", "pexels", "pixabay"), "place": ("commons", "pexels", "pixabay"),
    "other": ("commons", "met", "pexels", "pixabay"),
}
CLIP_SOURCES = ("pexels", "pixabay", "commons")
SOURCE_VI = {"commons": "Wikimedia Commons", "met": "Bảo tàng Metropolitan", "pexels": "Pexels", "pixabay": "Pixabay",
             "osm": "OpenStreetMap", "book": "sách của dự án"}


def sources_for(want: dict) -> list[str]:
    """The sources a wanted picture is asked of, keyless first; those that need a key are left out when the key is not set."""
    if want["type"] == "map":
        names: tuple = ("osm",)
    elif want["type"] == "clip":
        names = CLIP_SOURCES
    else:
        names = SOURCES_BY_KIND.get(want.get("kind") or "other", SOURCES_BY_KIND["other"])
    return [s for s in names if s not in KEYED or env.has_key(KEYED[s])]


def queries_for(want: dict) -> list[str]:
    if want["type"] == "map":
        return [want["place"]]
    return [want["search"]] + [a for a in want.get("alt", [])]


def new_state() -> dict:
    return {"schema": store.SCHEMA, "wants": {}, "limited": {}, "books": None}


def _new_want(w: dict) -> dict:
    return {"id": w["id"], "beat": w["beat"], "n": w["n"], "type": w["type"], "kind": w.get("kind"), "what": w.get("what") or w.get("place") or "",
            "queries": queries_for(w), "status": "pending", "code": None, "source": None, "seconds": None, "detail": "", "candidates": []}


def todo(state: dict) -> list[str]:
    """The wants a (resumed) search still has to do: never searched, or left unsearched by the time cap, or limited by a source."""
    return [wid for wid, w in state["wants"].items() if w["status"] in ("pending", "limited")]


# ---------------------------------------------------------------------------------------------------------------- thumbnails
def default_fetch_thumb(pdir: Path, cand: dict, limited: dict | None = None, clock: Callable[[], float] = time.time) -> str | None:
    """The thumbnail of a candidate, as a path relative to the project folder (None when it cannot be had). Downloaded once; kept in the cache."""
    from bti.media import http
    dest = store.thumb_path(pdir, cand["source"], cand["source_id"])
    rel = dest.relative_to(pdir).as_posix()
    if dest.is_file() and dest.stat().st_size > 0:
        return rel
    url = str(cand.get("thumb_url") or "")
    if not url:
        return None
    raw = dest.with_suffix(".raw")
    try:
        if os.path.isfile(url):                                  # a map the app drew earlier is a local file
            images.save_scaled(Path(url), dest, THUMB_SIDE, 85)
            return rel
        if not url.lower().startswith(("https://", "http://")):
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        http.download_file(url, raw, max_bytes=THUMB_BYTES)
        images.save_scaled(raw, dest, THUMB_SIDE, 85)
        return rel
    except http.MediaHTTPError as e:
        if getattr(e, "rate_limited", False) and limited is not None:
            limited[cand["source"]] = clock() + (e.retry_after or DEFAULT_WAIT)
        return None
    except Exception:       # noqa: BLE001 - a thumbnail that cannot be had or read only costs that candidate
        return None
    finally:
        try:
            raw.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------------------------- one wanted picture
def _card(item: dict, query: str) -> dict:
    mime = str(item.get("mime") or "")
    return {"source": item.get("source"), "source_id": item.get("source_id"), "title": str(item.get("title") or "")[:160],
            "author": str(item.get("author") or "")[:80], "licence": str(item.get("licence") or "")[:60], "flag": item.get("flag"),
            "width": int(item.get("width") or 0), "height": int(item.get("height") or 0), "page_url": str(item.get("page_url") or "")[:300],
            "thumb_url": str(item.get("thumb_url") or ""), "media": "video" if mime.startswith("video/") or item.get("kind") == "video" else "image",
            "query": query, "thumb": None}


def _interleave(by_source: dict, limit: int) -> list[dict]:
    """The first `limit` candidates, taking one from each source in turn so that no source fills the sheet alone."""
    out, i = [], 0
    names = list(by_source)
    while len(out) < limit and any(i < len(v) for v in by_source.values()):
        for s in names:
            if i < len(by_source[s]) and len(out) < limit:
                out.append(by_source[s][i])
        i += 1
    return out


def search_want(pdir: Path, want: dict, state: dict, *, main_key: str, search, fetch_thumb, clock, cancelled) -> None:
    """Fill `state["wants"][id]` for one wanted picture. Never raises for a source's failure."""
    w = state["wants"][want["id"]]
    limited = state["limited"]
    kind = "video" if want["type"] == "clip" else "image"
    by_source: dict[str, list] = {}
    seen: set = set()
    skipped: dict[str, float] = {}          # source -> seconds left of its wait
    failed: list[str] = []
    for qi, q in enumerate(w["queries"]):
        if qi > 0 and sum(len(v) for v in by_source.values()) >= ENOUGH:
            break
        for src in sources_for(want):
            if cancelled():
                return
            until = limited.get(src, 0)
            if until > clock():
                skipped[src] = max(skipped.get(src, 0), until - clock())
                continue
            r = search(pdir, q, None, [src], FIRST_LIMIT if qi == 0 else MORE_LIMIT, kind=kind)
            for e in r.get("errors") or []:
                if e.get("code") == "source_rate_limited":
                    wait = e.get("retry_after") or DEFAULT_WAIT
                    limited[src] = clock() + wait
                    skipped[src] = max(skipped.get(src, 0), wait)
                elif e.get("code") != "source_no_key":
                    failed.append(src)
            for it in r.get("items") or []:
                ident = (it.get("source"), it.get("source_id"))
                if ident in seen or not it.get("source_id"):
                    continue
                seen.add(ident)
                if it.get("imported") and it.get("imported") == main_key:
                    continue                                    # the main painting itself is never a context picture
                by_source.setdefault(src, []).append(_card(it, q))
    chosen = _interleave(by_source, PER_WANT)
    for c in chosen:
        if cancelled():
            return
        if want["type"] == "map":
            c["thumb"] = fetch_thumb(pdir, c, limited, clock) if c.get("thumb_url") and os.path.isfile(str(c["thumb_url"])) else None
        else:
            c["thumb"] = fetch_thumb(pdir, c, limited, clock)
    if want["type"] != "map":
        with_thumb = [c for c in chosen if c["thumb"]]
        no_thumb = len(chosen) - len(with_thumb)
        chosen = with_thumb
    else:
        no_thumb = 0
    for n, c in enumerate(chosen, 1):
        c["n"] = n
    w["candidates"] = chosen
    w["detail"] = ""
    if chosen:
        w.update({"status": "found", "code": None, "source": None, "seconds": None})
    elif skipped and not by_source:
        src, secs = max(skipped.items(), key=lambda kv: kv[1])
        w.update({"status": "limited", "code": "source_limited", "source": SOURCE_VI.get(src, src), "seconds": int(secs)})
    elif no_thumb:
        w.update({"status": "none", "code": "no_thumbs", "source": None, "seconds": None})
    elif failed and not by_source:
        w.update({"status": "none", "code": "search_failed", "source": SOURCE_VI.get(failed[0], failed[0]), "seconds": None})
    else:
        w.update({"status": "none", "code": "no_candidates", "source": None, "seconds": None})


# ---------------------------------------------------------------------------------------------------------------- the part
def run(pdir: Path, plan: dict, state: dict | None, wants: list[dict], *, main_key: str, cancelled: Callable[[], bool],
        progress: Callable[[float, str], None], save: Callable[[dict], None], search=None, fetch_thumb=None,
        clock: Callable[[], float] = time.time, budget_s: float = SEARCH_SECONDS) -> dict:
    """Search every wanted picture that is not done yet. `state` is the saved state of an earlier (cancelled) run, or None. `save(state)`
    is called after every want, so a cancel loses at most the want in hand. Returns the state."""
    st = state or new_state()
    st.setdefault("limited", {})
    for w in wants:
        if w["id"] not in st["wants"]:
            st["wants"][w["id"]] = _new_want(w)
    search = search or service.search
    fetch_thumb = fetch_thumb or default_fetch_thumb
    by_id = {w["id"]: w for w in wants}
    pending = [wid for wid in by_id if st["wants"][wid]["status"] in ("pending", "limited")]
    t0 = clock()
    done = 0
    for wid in pending:
        if cancelled():
            break
        if clock() - t0 > budget_s:
            for rest in pending[done:]:
                st["wants"][rest].update({"status": "pending", "code": "time_up"})
            break
        w = by_id[wid]
        progress(done / max(1, len(pending)), "Đang tìm hình %d/%d: %s" % (done + 1, len(pending), (w.get("what") or w.get("place") or "")[:60]))
        search_want(pdir, w, st, main_key=main_key, search=search, fetch_thumb=fetch_thumb, clock=clock, cancelled=cancelled)
        if cancelled():
            break
        done += 1
        save(st)
    save(st)
    return st


# ---------------------------------------------------------------------------------------------------------------- the owner's books
def default_book_thumb(pdir: Path, item: dict) -> str | None:
    dest = store.thumb_path(pdir, "book", item["source_id"])
    rel = dest.relative_to(pdir).as_posix()
    if dest.is_file() and dest.stat().st_size > 0:
        return rel
    raw = dest.with_suffix(".raw")
    try:
        from bti.media.sources import bookpage
        book_id, kind, ref = bookpage.parse_id(item["source_id"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        bookpage.default_renderer(book_id, kind, ref, raw)
        images.save_scaled(raw, dest, THUMB_SIDE, 85)
        return rel
    except Exception:       # noqa: BLE001 - no library, no PDF, no PyMuPDF: the picture is simply not offered
        return None
    finally:
        try:
            raw.unlink(missing_ok=True)
        except OSError:
            pass


def collect_books(pdir: Path, main_key: str, *, fetch=None, limit: int = MAX_BOOK_PICTURES) -> list[dict]:
    """The pictures of the project's books that are worth showing, numbered from 1, each with a thumbnail:
    `[{"n", "source_id", "label", "thumb"}]`. The main painting's own picture is left out."""
    fetch = fetch or default_book_thumb
    try:
        from bti.media import assets as massets
        idx = massets.load_index(pdir)["items"]
        listing = context.book_images(pdir)["images"]
    except Exception:       # noqa: BLE001 - a project with no readable library has no book pictures
        return []
    out = []
    for it in listing:
        if len(out) >= limit:
            break
        if min(int(it.get("width") or 0), int(it.get("height") or 0)) < MIN_BOOK_SIDE:
            continue
        hit = idx.get("book:" + it["source_id"])
        if hit and hit.get("key") == main_key:
            continue
        thumb = fetch(pdir, it)
        if thumb:
            out.append({"n": len(out) + 1, "source_id": it["source_id"], "label": it["label"], "thumb": thumb})
    return out
