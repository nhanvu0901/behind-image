"""Wikipedia (free, no key): look a thing up and offer the pictures of its article.

For a wanted picture of something that is not in the painting (a person, a building, an object, an event) the best first place to look is the
encyclopedia article about it: its lead image and the pictures inside the article are chosen by people who know the subject. This source asks
the MediaWiki API of English Wikipedia (or of the language the caller names) for the best pages of a search, and offers as candidates, page by
page, the page's lead image and the article's own pictures.

Every candidate is a Wikimedia Commons file and is handed to the existing `commons` source for what it knows: the metadata cards here are the
ones `bti.media.sources.commons.parse_page` makes, with `source` = "commons", so the download, the rendition rule, the licence and the credit
are Commons' own and nothing about licences or sizes is written twice. Pictures that are only on Wikipedia (non-free, "fair use") are not on
Commons and are therefore never offered. Four extra fields tell the choosing session where a card came from: `page_title` (the article),
`site` ("Wikipedia"), `snippet` (what the article says in a few words) and `via` ("wikipedia").

What is not offered: icons, flags, coats of arms, logos, locator maps, audio stand-ins and everything that is not a bitmap (SVG, audio, video),
anything under 600 px on its long side and strips that are more than four times longer than they are high.

The service's rules are kept: a generic User-Agent (never a person's name, an e-mail address or this project's name), at most one request a
second (this source paces itself, also across calls), and a "too many requests" answer is honoured by `bti.media.http` (a short wait once,
else a refusal that carries the wait and a pause for that host).
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Callable
from urllib.parse import quote, unquote, urlencode

from .. import http
from ..errors import NotFound
from . import commons

USER_AGENT = "ImageResearch/1.0 (art documentary research; generic client)"
API_URL = "https://{lang}.wikipedia.org/w/api.php"
MIN_INTERVAL = 1.0                  # seconds between two requests of this source
PAGES = 3                           # the best pages of a search
MIN_LONG_SIDE = 600                 # px: a smaller picture is an icon or a thumbnail
MAX_ASPECT = 4.0                    # a strip longer than this is a banner, not a picture
PER_PAGE = 16                       # file names looked at per page (Commons answers up to 50 in one request)
CARD_WIDTH = 500                    # one of Wikimedia's thumbnail steps (commons.THUMB_STEPS)
SNIPPET_CHARS = 200
BITMAP_MIMES = ("image/jpeg", "image/png", "image/webp", "image/tiff")
PAGE_ORDER = (0, 1, 0, 2, 0, 1, 0, 2)    # which page gives the next candidate: the best page twice as often

_BAD_EXT = (".svg", ".gif", ".ogg", ".oga", ".ogv", ".webm", ".mp3", ".wav", ".flac", ".pdf", ".djvu", ".mid", ".midi", ".opus", ".stl")
# the names of the files every article carries as furniture, and of the kinds of picture that never show a subject
_JUNK = re.compile(
    r"flag[ _]of|coat[ _]of[ _]arms|(?<![a-z])blason|(?<![a-z])wappen|(?<![a-z])logo(?![a-z])|commons[-_ ]logo|(?<![a-z])wiki(media|pedia|source|quote|tionary|data|books|news|versity|voyage)|"
    r"(?<![a-z])ambox|locator|location[ _]map|locmap|blank[ _]map|red[ _]pog|searchtool|disambig|(?<![a-z])stub(?![a-z])|nuvola|padlock|"
    r"(?<![a-z])speaker[ _]icon|loudspeaker|(?<![a-z])cscr|(?<![a-z])ooui|(?<![a-z])oojs|pictogram|(?<![a-z])cc[-_ ](by|zero|0)|creative[ _]commons|"
    r"question[ _]book|(?<![a-z])edit[-_ ]clear|(?<![a-z])symbol[ _](support|oppose|keep|delete|comment)|folder[ _]hexagonal|(?<![a-z])increase2|(?<![a-z])decrease2|(?<![a-z])steady2", re.I)


def real_open(req, timeout=None):
    """The real transport of this source. Besides the A7 switch (`BTI_NO_REAL_MODELS`), it refuses while a test is running (pytest sets
    `PYTEST_CURRENT_TEST`) unless the proof script says otherwise: a test that takes the A7 switch down for a fake program (some do) must still never
    reach Wikipedia by accident."""
    import os
    import urllib.request
    from ..safety import refuse_if_real_models_off
    refuse_if_real_models_off("request to Wikipedia")
    if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("BTI_REAL_NETWORK_PROOF") != "1":
        from ..errors import RealModelsOff
        raise RealModelsOff("request to Wikipedia from a test")
    return urllib.request.urlopen(req, timeout=timeout)


def junk_name(title: str) -> bool:
    """Is this `File:` name one of the files that are never a picture of a subject (furniture of the article, icons, flags, maps of where a
    place lies, audio, vector drawings)? The name is all there is to go on before the file's data is asked for."""
    name = unquote(str(title or "")).split(":", 1)[-1].strip().lower()
    return (not name) or name.endswith(_BAD_EXT) or bool(_JUNK.search(name))


def _short(text: Any, n: int) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def lang_of(host: str) -> str | None:
    """`en` for `en.wikipedia.org` and `en.m.wikipedia.org`, None for another host."""
    m = re.fullmatch(r"([a-z]{2,3}(?:-[a-z]{2,8})?)(?:\.m)?\.wikipedia\.org", (host or "").lower())
    return m.group(1) if m else None


class WikipediaSource:
    name = "wikipedia"

    def __init__(self, *, opener: Callable | None = None, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 lang: str = "en", min_interval: float = MIN_INTERVAL):
        self._opener, self._sleep, self._clock, self.lang = opener, sleep, clock, lang
        self.min_interval = min_interval
        self._last: float | None = None
        self._lock = threading.Lock()
        self.requests = 0                              # how many requests this source has sent (the proof counts them)

    # ------------------------------------------------------------------------------------------------------------- the service
    def _pace(self) -> None:
        """One request a second, whoever asks: the next request waits until a second has passed since the last one."""
        with self._lock:
            now = self._clock()
            if self._last is not None:
                wait = self.min_interval - (now - self._last)
                if wait > 0:
                    self._sleep(wait)
                    now = self._clock()
            self._last = now

    def _get(self, url: str, params: dict) -> dict:
        self._pace()
        self.requests += 1
        full = url + "?" + urlencode(params)
        with http.open_url(full, opener=self._opener or real_open, sleep=self._sleep, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}) as r:
            body = r.read()
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError as exc:
            raise http.MediaHTTPError("the answer of Wikipedia was not JSON") from exc

    def _pages(self, lang: str, *, search: str | None = None, titles: list[str] | None = None) -> list[dict]:
        """The pages (best first) of a search, or the named pages, with their lead image, the files they use and a few words about them."""
        params: dict[str, Any] = {
            "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
            "prop": "pageimages|images|extracts|description", "piprop": "name", "pilimit": "max", "imlimit": "max",
            "exintro": "1", "explaintext": "1", "exsentences": "2", "exlimit": "max"}
        if search is not None:
            params.update({"generator": "search", "gsrsearch": search, "gsrnamespace": "0", "gsrlimit": str(PAGES)})
        else:
            params["titles"] = "|".join((titles or [])[:PAGES])
        data = self._get(API_URL.format(lang=lang), params)
        pages = [p for p in (data.get("query") or {}).get("pages") or [] if isinstance(p, dict) and not p.get("missing") and p.get("title")]
        return sorted(pages, key=lambda p: p.get("index", 0))[:PAGES]

    def _file_metas(self, files: list[str]) -> dict[str, dict]:
        """`File:` title -> the Commons card of that file, for the files that Commons has (one request for all)."""
        if not files:
            return {}
        data = self._get(commons.API_URL, {
            "action": "query", "format": "json", "formatversion": "2", "titles": "|".join(files[:50]), "prop": "imageinfo",
            "iiprop": commons.IIPROP, "iiurlwidth": str(CARD_WIDTH)})
        out = {}
        for page in (data.get("query") or {}).get("pages") or []:
            meta = commons.parse_page(page)
            if meta:
                out[meta["source_id"]] = meta
        return out

    # ------------------------------------------------------------------------------------------------------------- what a page offers
    @staticmethod
    def _page_files(page: dict) -> list[str]:
        """The names of the files worth asking Commons about, lead image first, in the order of the article, without the furniture."""
        names: list[str] = []
        lead = page.get("pageimage")
        if lead:
            names.append("File:" + str(lead).replace("_", " "))
        for im in page.get("images") or []:
            t = str(im.get("title") or "") if isinstance(im, dict) else ""
            if t.lower().startswith("file:"):
                names.append("File:" + t.split(":", 1)[1].replace("_", " "))
        out, seen = [], set()
        for n in names:
            if n in seen or junk_name(n):
                continue
            seen.add(n)
            out.append(n)
        return out[:PER_PAGE]

    @staticmethod
    def usable(meta: dict) -> bool:
        """A bitmap that is big enough to be looked at and is not a banner."""
        w, h = int(meta.get("width") or 0), int(meta.get("height") or 0)
        if meta.get("mime") not in BITMAP_MIMES or max(w, h) < MIN_LONG_SIDE or not min(w, h):
            return False
        return max(w, h) / float(min(w, h)) <= MAX_ASPECT

    def _offer(self, pages: list[dict], lang: str, limit: int) -> list[dict]:
        """The candidates of the pages: each page's pictures in the article's order, the pages mixed so that the best page gives about half."""
        per_page = [self._page_files(p) for p in pages]
        metas = self._file_metas(list(dict.fromkeys(f for fs in per_page for f in fs)))
        lists: list[list[dict]] = []
        for page, files in zip(pages, per_page):
            title = str(page.get("title"))
            snippet = _short(page.get("description") or page.get("extract"), SNIPPET_CHARS)
            cards = []
            for f in files:
                m = metas.get(f)
                if m is None or not self.usable(m):
                    continue
                cards.append({**m, "page_title": title, "site": "Wikipedia" if lang == "en" else "Wikipedia (%s)" % lang, "snippet": snippet,
                              "via": "wikipedia", "article_url": "https://%s.wikipedia.org/wiki/%s" % (lang, quote(title.replace(" ", "_")))})
            lists.append(cards)
        out, seen, pos = [], set(), [0] * len(lists)
        turn = 0
        while len(out) < limit and any(pos[i] < len(lists[i]) for i in range(len(lists))):
            i = PAGE_ORDER[turn % len(PAGE_ORDER)]
            turn += 1
            if i >= len(lists) or pos[i] >= len(lists[i]):
                i = next((j for j in range(len(lists)) if pos[j] < len(lists[j])), None)
                if i is None:
                    break
            card = lists[i][pos[i]]
            pos[i] += 1
            if card["source_id"] not in seen:
                seen.add(card["source_id"])
                out.append(card)
        return out

    # ------------------------------------------------------------------------------------------------------------- the source protocol
    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        """Look `query` up (best three pages) and offer the pictures of those articles. Only images: a video is never offered."""
        query = " ".join(str(query or "").split())
        if kind != "image" or not query:
            return []
        pages = self._pages(self.lang, search=query)
        return self._offer(pages, self.lang, max(1, int(limit))) if pages else []

    def page_pictures(self, title: str, lang: str | None = None, limit: int = 12) -> list[dict]:
        """The pictures of ONE named article (a Wikipedia address found by a web search): its lead image first, then the article's own pictures."""
        lang = lang or self.lang
        pages = self._pages(lang, titles=[str(title).replace("_", " ")])
        return self._offer(pages, lang, max(1, int(limit))) if pages else []

    # what happens to a candidate is Commons' business: its data, its download, its licence and its credit
    def _commons(self):
        from bti.media import api
        return api.get_source("commons")

    def fetch_meta(self, source_id: str) -> dict:
        try:
            return self._commons().fetch_meta(source_id)
        except NotFound:
            raise

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        return self._commons().licence(meta)

    def credit(self, meta: dict) -> dict:
        return self._commons().credit(meta)

    def stored_size(self, meta: dict) -> tuple[int, int]:
        return commons.expected_size(meta)

    def download(self, meta: dict, dest, **kw):
        return self._commons().download(meta, dest, **kw)
