"""Part 2 of the automatic picks job: find candidates for every picture the plan asks for. Code only: no model, and never the paid
suggestion service (`bti.picks.suggest`) - this module does not import it.

What each wanted picture asks, and of which source (the free sources the app already has; a source that needs a key is asked only
when the key is set):

    context  (every kind)                 FIRST Wikipedia (free): the thing is looked up by its `entity` (else by `search`) and the pictures of
                                          the best three articles are offered (they are Wikimedia Commons files)
             work / portrait / document   Wikimedia Commons, The Met
             object                       Wikimedia Commons, The Met (as work)
             photo / place                Wikimedia Commons, Pexels, Pixabay (stock photographs)
             event / other                event: as other, without the Met; other: Wikimedia Commons, The Met, Pexels, Pixabay
    map                                   OpenStreetMap (one place, by name)
    clip                                  Pexels, Pixabay and Wikimedia Commons, as VIDEO (the pictures of the same sources, searched as video)

The first query of a want (the plan's `search`) goes to every source of its kind; the alternatives (`alt`) are tried only while fewer
than three candidates were found. The pictures in the owner's books are not searched (a book has no captions to search): the ones that
have a size worth showing are given to the choosing step as one numbered set (B1, B2 ...) that any want may pick from.

The web (the owner's switch `auto_web_search`, see `bti.picks.websettings`; PAID, the You.com search): when the switch is on,
every context want of a line of kind outside or compare gets ONE web search of its `search` in round one, whatever the
free sources brought, while the budget lasts (and any other context want with fewer than three candidates). After the choosing session
`bti.picks.auto.webround` searches again, for the wants the session answered null and for those that had no candidate (round two). Every web
search is counted against `auto_web_search_max`; a want that could not be searched because the count was used up gets the code `web_budget`.
With the switch off nothing here calls the web, and a Wikipedia search is the only addition to what the free sources do.

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
from urllib.parse import urlparse

from bti.picks import context, service
from bti.script import env

from . import images, store

SEARCH_SECONDS = 10 * 60
PER_WANT = 6                 # candidates kept per wanted picture
PER_WANT_WEB = 8             # ... when Wikipedia or the web gave some: the choosing session looks at up to eight (Wikipedia and web ones first)
SPARE_WEB = 4                # extra Wikipedia or web candidates whose thumbnails are tried when some of the first ones cannot be had
FIRST_LIMIT = 6              # results asked of a source for the first query
MORE_LIMIT = 4               # ... for an alternative query
WIKI_LIMIT = 12              # results asked of Wikipedia (the pictures of its best three articles; the extra ones are spares for thumbnails that cannot be had)
WEB_LIMIT = 12               # ... of the web search (pictures of its best five pages)
WEB_MIN_SIDE = 600           # a web picture whose long side turns out smaller than this is no candidate
WEB_THUMB_BYTES = 8_000_000
WEB_NOT_SPENT = ("web_no_key", "real_models_off", "web_off")      # a refusal before anything was sent: not a search, not counted
WIKIMEDIA_PACE = 1.0         # seconds between two thumbnail downloads from a Wikimedia host (its rule: no more than about one request a second)
ENOUGH = 3                   # alternatives are tried only while fewer candidates than this were found
DEFAULT_WAIT = 60            # seconds a "too many requests" without a time is honoured for
THUMB_SIDE = 640
THUMB_BYTES = 4_000_000
MAX_BOOK_PICTURES = 24
MIN_BOOK_SIDE = 250
KEYED = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}
SOURCES_BY_KIND = {
    "work": ("commons", "met"), "portrait": ("commons", "met"), "document": ("commons", "met"), "object": ("commons", "met"),
    "photo": ("commons", "pexels", "pixabay"), "place": ("commons", "pexels", "pixabay"), "event": ("commons", "pexels", "pixabay"),
    "other": ("commons", "met", "pexels", "pixabay"),
}
CLIP_SOURCES = ("pexels", "pixabay", "commons")
SOURCE_VI = {"commons": "Wikimedia Commons", "met": "Bảo tàng Metropolitan", "pexels": "Pexels", "pixabay": "Pixabay",
             "osm": "OpenStreetMap", "book": "sách của dự án", "wikipedia": "Wikipedia", "web": "tìm kiếm trên web"}


def sources_for(want: dict) -> list[str]:
    """The sources a wanted picture is asked of, keyless first; those that need a key are left out when the key is not set.
    Pexels and Pixabay are never searched for a want with period: "then"."""
    if want["type"] == "map":
        names: tuple = ("osm",)
    elif want["type"] == "clip":
        names = CLIP_SOURCES
    else:
        names = SOURCES_BY_KIND.get(want.get("kind") or "other", SOURCES_BY_KIND["other"])
        if want.get("period") == "then":
            names = tuple(s for s in names if s not in ("pexels", "pixabay"))
    return [s for s in names if s not in KEYED or env.has_key(KEYED[s])]


def place_of(want: dict) -> str:
    """The place a map want is searched by: its `place`, else the first of its `places` (a journey names two or more; one map of the first is enough, the
    storyboard draws its own atlas map from the names)."""
    places = want.get("places") if isinstance(want.get("places"), list) else []
    return str(want.get("place") or (places[0] if places else "") or "")


def queries_for(want: dict) -> list[str]:
    if want["type"] == "map":
        return [place_of(want)]
    return [want["search"]] + [a for a in want.get("alt", [])]


def new_state() -> dict:
    return {"schema": store.SCHEMA, "wants": {}, "limited": {}, "books": None}


def entity_of(want: dict) -> str:
    """The name under which an encyclopedia knows the thing a context want is about (`entity` of the plan; empty in a plan that has none)."""
    return " ".join(str(want.get("entity") or "").split())


def _new_want(w: dict) -> dict:
    return {"id": w["id"], "beat": w["beat"], "n": w["n"], "type": w["type"], "kind": w.get("kind"), "what": w.get("what") or place_of(w),
            "queries": queries_for(w), "entity": entity_of(w), "period": w.get("period") or "then", "kinds": list(w.get("kinds") or []),
            "places": list(w.get("places") or []), "wider": list(w.get("wider") or []),
            "status": "pending", "code": None, "source": None, "seconds": None, "detail": "", "candidates": []}


class Web:
    """What a run may spend on the paid web search, and what it has spent: `on` (the owner's switch when the run started), `max` (searches for the
    run), `spent` (searches made, counted by `count`), `stopped` (a code, once the web cannot be used for the rest of the run: no key, real requests
    off), `search` (the seam: `search(pdir, query, limit) -> {"items", "errors"}`; the default asks `bti.picks.service.search` for the source `web`
    with the permission only this job holds). It is kept in the search state (`state["web"]`) so that a resumed run goes on counting."""

    def __init__(self, on: bool = False, max: int = 0, search=None, spent: int = 0, stopped: str | None = None):
        self.on, self.max, self.spent, self.stopped = bool(on), int(max), int(spent), stopped
        self.search = search or default_web_search

    @classmethod
    def from_state(cls, st: dict, on: bool, max: int, search=None) -> "Web":
        """The web of a run: the owner's switch as it is now, and the count of what an earlier attempt of the same run already spent."""
        prev = st.get("web") if isinstance(st.get("web"), dict) else {}
        return cls(on, max, search, spent=int(prev.get("searches") or 0), stopped=prev.get("stopped") if on else None)

    def usable(self) -> bool:
        return self.on and not self.stopped

    def left(self) -> int:
        return max(0, self.max - self.spent)

    def public(self) -> dict:
        return {"on": self.on, "max": self.max, "searches": self.spent, "stopped": self.stopped}


def default_web_search(pdir: Path, query: str, limit: int) -> dict:
    """The one way into the paid search: `bti.picks.service.search` for the source `web`, with the ticket of `bti.media.sources.web` (without it the
    source refuses) and `allow_paid` (without it the service leaves the source out)."""
    from bti.media.sources import web as webmod
    with webmod.ticket():
        return service.search(pdir, query, None, ["web"], limit, kind="image", allow_paid=True)


def todo(state: dict) -> list[str]:
    """The wants a (resumed) search still has to do: never searched, or left unsearched by the time cap, or limited by a source."""
    return [wid for wid, w in state["wants"].items() if w["status"] in ("pending", "limited")]


# ---------------------------------------------------------------------------------------------------------------- thumbnails
def pace_wikimedia(url: str, *, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> None:
    """Wait so that two downloads from a Wikimedia host (`upload.wikimedia.org`) are at least `WIKIMEDIA_PACE` seconds apart, whoever asks: Wikipedia's
    candidates are many pictures at once, and the service answers "too many requests" to a client that does not keep to its rule. The clock is the one the
    downloads of the write part keep too (`bti.media.http.pace`: one a second for the whole Wikimedia service, thumbnails and imports alike)."""
    host = (urlparse(url).hostname or "").lower()
    if not host.endswith("wikimedia.org"):
        return
    from bti.media import http
    http.pace(url, sleep=sleep, interval=WIKIMEDIA_PACE, clock=clock)


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
    web_raw = dest.with_name(dest.stem + "_web.raw")
    got = None
    try:
        if os.path.isfile(url):                                  # a map the app drew earlier is a local file
            images.save_scaled(Path(url), dest, THUMB_SIDE, 85)
            return rel
        if not url.lower().startswith(("https://", "http://")):
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        if cand.get("source") == "web":                          # a picture of some web page: a generic client, an image content type only, public addresses only
            from bti.media.sources import web as webmod
            got = webmod.fetch_image(url, web_raw, max_bytes=WEB_THUMB_BYTES)
            sw, sh, _, _ = images.save_scaled(got, dest, THUMB_SIDE, 85)
            cand["width"], cand["height"] = int(sw), int(sh)       # the real size of the picture: the card did not know it
            return rel
        pace_wikimedia(url)
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
        for f in (raw, web_raw, got):
            try:
                if f is not None:
                    Path(f).unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------------------------------------------- one wanted picture
def _card(item: dict, query: str, round_no: int = 1, step: int | None = None) -> dict:
    mime = str(item.get("mime") or "")
    card = {"source": item.get("source"), "source_id": item.get("source_id"), "title": str(item.get("title") or "")[:160],
            "author": str(item.get("author") or "")[:80], "licence": str(item.get("licence") or "")[:60], "flag": item.get("flag"),
            "width": int(item.get("width") or 0), "height": int(item.get("height") or 0), "page_url": str(item.get("page_url") or "")[:300],
            "thumb_url": str(item.get("thumb_url") or ""), "media": "video" if mime.startswith("video/") or item.get("kind") == "video" else "image",
            "query": query, "thumb": None}
    for k, n in (("page_title", 160), ("site", 80), ("snippet", 240), ("via", 20)):             # where it came from: what the choosing step reads
        if item.get(k):
            card[k] = str(item[k])[:n]
    if round_no != 1:
        card["round"] = round_no
    step_val = step if step in (2, 3) else item.get("step")
    if step_val in (2, 3):
        card["step"] = int(step_val)
    return card


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


def wiki_queries(want: dict) -> list[str]:
    """What Wikipedia is asked: the thing's name (`entity`) when the plan gave one, then the plan's `search` (at most two asks; the second only when
    the first found nothing)."""
    out = []
    for q in (entity_of(want), " ".join(str(want.get("search") or "").split())):
        if q and q not in out:
            out.append(q)
    return out[:2]


def _order(by_source: dict) -> dict:
    """Wikipedia's and the web's candidates first (the choosing step reads them first), then the other sources in the order they were asked."""
    first = [k for k in ("wikipedia", "web") if k in by_source]
    return {k: by_source[k] for k in first + [k for k in by_source if k not in first]}


def make_asker(pdir: Path, want: dict, state: dict, *, main_key: str, search, clock, cancelled, round_no: int = 1, seen: set | None = None, wiki_search=None, step: int | None = None):
    """`ask(src, query, limit)` for one wanted picture: one search of one free source, its candidates added to `by_source`. Returns
    `(ask, by_source, seen, skipped, failed)`; `skipped` and `failed` say why a source gave nothing (a wait it asked for, a failure)."""
    limited = state["limited"]
    kind = "video" if want["type"] == "clip" else "image"
    by_source: dict[str, list] = {}
    seen = seen if seen is not None else set()
    skipped: dict[str, float] = {}
    failed: list[str] = []

    def ask(src: str, q: str, limit: int) -> None:
        until = limited.get(src, 0)
        if until > clock():
            skipped[src] = max(skipped.get(src, 0), until - clock())
            return
        r = (wiki_search or search)(pdir, q, None, [src], limit, kind=kind) if src == "wikipedia" else search(pdir, q, None, [src], limit, kind=kind)
        for e in r.get("errors") or []:
            if e.get("code") == "source_rate_limited":
                wait = e.get("retry_after") or DEFAULT_WAIT
                limited[src] = clock() + wait
                skipped[src] = max(skipped.get(src, 0), wait)
            elif e.get("code") != "source_no_key" and src != "wikipedia":             # Wikipedia is an addition: when it does not answer the others still do
                failed.append(src)
        take(src, q, r.get("items") or [])

    def take(src: str, q: str, items: list) -> None:
        for it in items:
            ident = (it.get("source"), it.get("source_id"))
            if ident in seen or not it.get("source_id"):
                continue
            seen.add(ident)
            if it.get("imported") and it.get("imported") == main_key:
                continue                                    # the main painting itself is never a context picture
            by_source.setdefault(src, []).append(_card(it, q, round_no, step=step))
    ask.take = take
    return ask, by_source, seen, skipped, failed


def web_ask(pdir: Path, w: dict, state: dict, web: Web, query: str, *, ask_take, clock, skipped: dict) -> int:
    """ONE paid web search for the wanted picture state `w` (it is counted, and only when something was really sent). -> how many candidates it added
    (-1 when no search was made: the web is not usable, the count is used up (the want gets the code `web_budget`) or the host asked us to wait)."""
    if not web.usable():
        return -1
    if web.left() <= 0:
        w["web_short"] = True
        return -1
    until = state["limited"].get("web", 0)
    if until > clock():
        skipped["web"] = max(skipped.get("web", 0), until - clock())
        return -1
    r = web.search(pdir, query, WEB_LIMIT)
    items = r.get("items") or []
    errors = r.get("errors") or []
    refused = next((e.get("code") for e in errors if e.get("code") in WEB_NOT_SPENT), None)
    if refused and not items:
        web.stopped = refused                               # nothing was sent, so nothing is counted; the web is left alone for the rest of the run
        return -1
    web.spent += 1
    w.setdefault("web", {"queries": []})["queries"].append(query)
    for e in errors:
        if e.get("code") == "source_rate_limited":
            wait = e.get("retry_after") or DEFAULT_WAIT
            state["limited"]["web"] = clock() + wait
            skipped["web"] = max(skipped.get("web", 0), wait)
    ask_take("web", query, items)
    return len(items)


def pick_with_thumbs(pdir: Path, want: dict, pool: list[dict], cap: int, *, fetch_thumb, limited: dict, clock, cancelled) -> tuple[list[dict], int]:
    """Thumbnails for the candidates of `pool` in order; the first `cap` that have one (and, for a web picture, a real size of at least 600 px on its
    long side) are kept. -> (kept, how many had no thumbnail). Wikipedia's and the web's spare candidates are tried when earlier ones fail; the free
    sources' are not (their number stays as it was)."""
    kept, no_thumb = [], 0
    for c in pool:
        if cancelled():
            return kept, no_thumb
        if len(kept) >= cap:
            break
        if want["type"] == "map":
            c["thumb"] = fetch_thumb(pdir, c, limited, clock) if c.get("thumb_url") and os.path.isfile(str(c["thumb_url"])) else None
        else:
            c["thumb"] = fetch_thumb(pdir, c, limited, clock)
        if want["type"] != "map" and not c["thumb"]:
            no_thumb += 1
            continue
        if c["source"] == "web" and c.get("width") and c.get("height") and max(c["width"], c["height"]) < WEB_MIN_SIDE:
            no_thumb += 1                                   # a picture this small is an icon or a thumbnail of another page
            continue
        kept.append(c)
    return kept, no_thumb


def finish_want(w: dict, chosen: list[dict], *, by_source: dict, skipped: dict, failed: list, no_thumb: int) -> None:
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


def search_want(pdir: Path, want: dict, state: dict, *, main_key: str, search, fetch_thumb, clock, cancelled, web: Web | None = None, wiki_search=None) -> None:
    """Fill `state["wants"][id]` for one wanted picture. Never raises for a source's failure. A context want asks Wikipedia first; with the web usable
    (`web`) and fewer than three candidates found, it asks the web once (round one)."""
    w = state["wants"][want["id"]]
    limited = state["limited"]
    ask, by_source, seen, skipped, failed = make_asker(pdir, want, state, main_key=main_key, search=search, clock=clock, cancelled=cancelled,
                                                       wiki_search=wiki_search or service.search)
    if want["type"] == "context":
        for qi, q in enumerate(wiki_queries(want)):
            if qi > 0 and by_source.get("wikipedia"):
                break
            if cancelled():
                return
            ask("wikipedia", q, WIKI_LIMIT)
    for qi, q in enumerate(w["queries"]):
        if qi > 0 and sum(len(v) for v in by_source.values()) >= ENOUGH:
            break
        for src in sources_for(want):
            if cancelled():
                return
            ask(src, q, FIRST_LIMIT if qi == 0 else MORE_LIMIT)
    kinds = set(want.get("kinds") or w.get("kinds") or [])
    is_outside_or_compare = bool(kinds & {"outside", "compare"})
    needs_web = is_outside_or_compare or (sum(len(v) for v in by_source.values()) < ENOUGH)
    if web is not None and want["type"] == "context" and needs_web and w["queries"]:
        if cancelled():
            return
        web_ask(pdir, w, state, web, w["queries"][0], ask_take=ask.take, clock=clock, skipped=skipped)
    by_source = _order(by_source)
    extra = any(k in by_source for k in ("wikipedia", "web"))
    cap = PER_WANT_WEB if extra else PER_WANT
    pool = _interleave(by_source, cap + (SPARE_WEB if extra else 0))
    spare = [c for c in pool[cap:] if c["source"] in ("web",) or c.get("via") in ("wikipedia", "web")]
    pool = pool[:cap] + spare
    chosen, no_thumb = pick_with_thumbs(pdir, want, pool, cap, fetch_thumb=fetch_thumb, limited=limited, clock=clock, cancelled=cancelled)
    if cancelled():
        return
    finish_want(w, chosen, by_source=by_source, skipped=skipped, failed=failed, no_thumb=no_thumb)
    if w.get("web_short") and not chosen:
        w["code"] = "web_budget"


# ---------------------------------------------------------------------------------------------------------------- the part
def run(pdir: Path, plan: dict, state: dict | None, wants: list[dict], *, main_key: str, cancelled: Callable[[], bool],
        progress: Callable[[float, str], None], save: Callable[[dict], None], search=None, fetch_thumb=None,
        clock: Callable[[], float] = time.time, budget_s: float = SEARCH_SECONDS, web: Web | None = None, wiki_search=None) -> dict:
    """Search every wanted picture that is not done yet. `state` is the saved state of an earlier (cancelled) run, or None. `save(state)`
    is called after every want, so a cancel loses at most the want in hand. `web`: the paid web search of this run (`Web`), None when the owner's
    switch is off (nothing paid is then ever called); its count is kept in `state["web"]`. `wiki_search`: the seam of the Wikipedia asks (the same shape
    as `search`, default `bti.picks.service.search`; a test that watches `search` does not see the free Wikipedia step). Returns the state."""
    st = state or new_state()
    st.setdefault("limited", {})
    for w in wants:
        if w["id"] not in st["wants"]:
            st["wants"][w["id"]] = _new_want(w)
    if web is not None:
        st["web"] = web.public()
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
        progress(done / max(1, len(pending)), "Đang tìm hình %d/%d: %s" % (done + 1, len(pending), (w.get("what") or place_of(w))[:60]))
        search_want(pdir, w, st, main_key=main_key, search=search, fetch_thumb=fetch_thumb, clock=clock, cancelled=cancelled, web=web,
                    wiki_search=wiki_search)
        if web is not None:
            st["web"] = web.public()
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
