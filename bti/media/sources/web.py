"""The web (paid: the You.com search) as a source of picture candidates.

A search of the web answers with pages: for each its address, title, a few words about it (`description`, `snippets`), the page as markdown
(`contents.markdown`, with the page's pictures as `![alt](address)`) and often the page's lead picture (`original_thumbnail_url`). A real answer
is in `tests/media/fixtures/ydc_search_sample.json`. This module turns the best five pages into picture candidates:

  * a page of Wikipedia is resolved as `bti.media.sources.wikipedia` does it (the article's lead image and its own pictures, which are Wikimedia
    Commons files); a page of Wikimedia Commons gives that file; a page of the Met gives that object (through the Met source). These candidates
    keep the source that knows them (`commons`, `met`) and its data, download and credit.
  * any other page gives its lead picture and up to four pictures of its markdown. The candidate is `source` "web"; its `source_id` carries the
    picture's address and the page's address (`<picture address> <page address>`, at most 300 characters: what the import needs to know); its
    `title` is the page's title, its `author` the site's name, its `snippet` the words about the picture; the licence is unknown (flag `unknown`).

Never offered: pictures of stock agencies and print shops that carry watermarks (a list of hosts, `config/picks.json` `web_blocked_hosts`, added
to the built-in list below), data addresses, SVG, GIF, and the furniture of a page (icons, logos, flags, buttons, tracking pixels). A picture whose
address says it is a small thumbnail is not offered; one that turns out smaller than 600 px on its long side after its (thumbnail) download is dropped
by the search (`bti.picks.auto.search`).

Safety: the search is PAID, so it runs only inside `ticket()` (the automatic picks job takes one while its owner's switch `auto_web_search` is on) and
a call outside it is refused (`web_off`); without a key it is refused (`web_no_key`); with `BTI_NO_REAL_MODELS=1` the client refuses itself. The
download of a picture takes only a public address (no address that names a private or local machine, also after a redirect), an image content type
(not SVG), at most 25 MB, the generic User-Agent of `bti.media.http` and a time-out.
"""
from __future__ import annotations

import contextlib
import contextvars
import html
import ipaddress
import json
import re
import socket
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urljoin, urlparse, urlsplit, urlunsplit

from bti.fsio import atomic_replace
from .. import http
from ..errors import MediaError, NotFound, RealModelsOff
from ..imageinfo import image_size

MAX_BYTES = 25 * 1024 * 1024
TIMEOUT = 30
PAGES = 5                           # the best pages of an answer
MARKDOWN_PICTURES = 4               # pictures taken from one page's markdown (besides its lead picture)
MIN_LONG_SIDE = 600                 # px; checked after the download (the search does it with the thumbnail)
ID_MAX = 300                        # the longest `source_id` an import accepts
SNIPPET_CHARS = 200
SEARCH_TIMEOUT = 60                 # seconds one You.com search may take (the client's own default is for long research)

# Hosts whose pictures carry watermarks (stock agencies, print shops). A host matches itself and every sub-domain. The owner's list in
# config/picks.json (`web_blocked_hosts`) is added to this one.
DEFAULT_BLOCKED = (
    "gettyimages.com", "gettyimages.co.uk", "gettyimages.ca", "gettyimages.de", "gettyimages.fr", "alamy.com", "alamy.de", "alamyimages.fr",
    "shutterstock.com", "istockphoto.com", "stock.adobe.com", "depositphotos.com", "dreamstime.com", "123rf.com", "bridgemanimages.com",
    "bridgemanart.com", "akg-images.com", "akg-images.co.uk", "meisterdrucke.com", "meisterdrucke.uk", "meisterdrucke.ie", "meisterdrucke.us",
    "meisterdrucke.de", "meisterdrucke.fr", "meisterdrucke.es", "meisterdrucke.it", "fineartamerica.com", "pixels.com", "art.com", "allposters.com",
    "posterlounge.com", "posterlounge.co.uk", "1st-art-gallery.com", "1st-artwork.com", "artprintsonline.com", "maryevans.com", "topfoto.co.uk",
    "agefotostock.com", "granger.com", "scalarchives.com", "photo12.com", "redbubble.com", "etsy.com", "ebay.com", "pinterest.com", "pinimg.com",
    "overstockart.com", "artisoo.com", "wahooart.com", "reproduction-gallery.com", "paintingstar.com", "artcanvas.com")

_ICON = re.compile(
    r"(?<![a-z])(icon|icons|logo|logos|sprite|sprites|avatar|favicon|button|badge|spacer|pixel|tracking|loader|spinner|share|facebook|twitter|"
    r"pinterest|instagram|whatsapp|flag|flags|placeholder|advert|newsletter)(?![a-z])", re.I)
_TINY = [re.compile(r"[-_/](\d{2,4})x(\d{2,4})(?=[._/\-?]|$)"), re.compile(r"/full/!?(\d{2,4}),(\d{2,4})/")]
_TINY_PARAM = re.compile(r"[?&](?:w|width)=(\d{1,4})(?:&|$)")
_IMG_MD = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_BAD_EXT = (".svg", ".svgz", ".gif", ".ico", ".pdf", ".mp4", ".webm", ".mp3", ".js", ".css", ".html", ".htm")
_GOOD_TYPES = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/tiff": ".tif"}

_TICKET: contextvars.ContextVar = contextvars.ContextVar("bti_web_ticket", default=False)


class WebError(MediaError, ValueError):
    """A refusal of the web source with a `code` (the shape both HTTP layers already turn into an error with that code)."""
    code = "web_error"


class WebOff(WebError):
    code = "web_off"

    def __init__(self):
        super().__init__("the web search is paid: it runs only inside the automatic choice of pictures, with the owner's switch on")


class WebNoKey(WebError):
    code = "web_no_key"

    def __init__(self):
        super().__init__("YDC_API_KEY is not set: the web search cannot run")


class NotAnImage(WebError):
    code = "not_an_image"


class UnsafeURL(WebError):
    code = "unsafe_url"


@contextlib.contextmanager
def ticket():
    """The permission to make a paid web search, held only by the code that checked the owner's switch (the automatic picks job)."""
    token = _TICKET.set(True)
    try:
        yield
    finally:
        _TICKET.reset(token)


def has_ticket() -> bool:
    return bool(_TICKET.get())


# ---------------------------------------------------------------------------------------------------------------- addresses
def blocked_hosts(extra: Any = None) -> tuple[str, ...]:
    """The hosts whose pictures are never offered: the built-in list, the owner's (`config/picks.json`) and `extra`."""
    out = list(DEFAULT_BLOCKED)
    try:
        cfg = json.loads((Path(__file__).resolve().parents[3] / "config" / "picks.json").read_text(encoding="utf-8"))
        more = cfg.get("web_blocked_hosts") if isinstance(cfg, dict) else None
        out += [str(h).strip().lower() for h in more or [] if str(h).strip()]
    except (OSError, ValueError):
        pass
    out += [str(h).strip().lower() for h in extra or [] if str(h).strip()]
    return tuple(dict.fromkeys(out))


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def host_blocked(host: str, blocked: tuple[str, ...]) -> str | None:
    """The entry of `blocked` that `host` is (or is a sub-domain of), else None."""
    h = (host or "").lower().rstrip(".")
    return next((b for b in blocked if h == b or h.endswith("." + b)), None)


def site_name(host: str) -> str:
    return re.sub(r"^(www\d?|m)\.", "", (host or "").lower())


def absolute(url: str, base: str) -> str:
    """`url` made absolute against `base` ("//host/x" and "/x" resolved), with HTML entities read ("&amp;" -> "&")."""
    u = html.unescape(str(url or "")).strip()
    if not u or u.lower().startswith(("data:", "blob:", "javascript:", "mailto:")):
        return ""
    return urljoin(base, u) if base else u


def tiny_hint(url: str) -> bool:
    """Does the address say that this is a small thumbnail (`-300x300.jpg`, `/full/!80,50/`, `?width=120`)?"""
    for rx in _TINY:
        m = rx.search(url)
        if m and max(int(m.group(1)), int(m.group(2))) < 500:
            return True
    m = _TINY_PARAM.search(url)
    return bool(m and int(m.group(1)) < 500)


def junk_picture(url: str) -> str | None:
    """Why a picture address is not a picture of the subject (None when it may be one)."""
    path = unquote(urlparse(url).path).lower()
    if path.endswith(_BAD_EXT):
        return "not a bitmap (%s)" % (Path(path).suffix or "no extension")
    if _ICON.search(path.rsplit("/", 1)[-1]):
        return "looks like page furniture (icon, logo, button ...)"
    if tiny_hint(url):
        return "an address that names a small thumbnail"
    return None


def title_of(url: str, fallback: str = "") -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", unquote(urlparse(url).path).rsplit("/", 1)[-1])
    stem = re.sub(r"[-_+]+", " ", stem).strip()
    return stem[:120] if re.search(r"[A-Za-z]{3}", stem) else fallback


def make_id(image_url: str, page_url: str) -> str | None:
    """`<picture address> <page address>` within 300 characters, or None when even the picture's address alone is too long. The page address
    is shortened (its query and fragment, then everything but its host) before the picture's own address is touched."""
    img = image_url
    if len(img) > ID_MAX:
        sp = urlsplit(img)
        img = urlunsplit((sp.scheme, sp.netloc, sp.path, "", ""))
        if len(img) > ID_MAX:
            return None
    for page in (page_url, urlunsplit(urlsplit(page_url)[:3] + ("", "")), urlunsplit(urlsplit(page_url)[:2] + ("/", "", ""))):
        if page and len(img) + 1 + len(page) <= ID_MAX:
            return img + " " + page
    return img


def parse_id(source_id: str) -> tuple[str, str]:
    """`(picture address, page address)` of a `source_id` made by `make_id`; the page address is "" when the id has none."""
    parts = str(source_id or "").strip().split(None, 1)
    return (parts[0] if parts else ""), (parts[1].strip() if len(parts) > 1 else "")


def _public_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def check_public_url(url: str, *, resolve: bool = False) -> None:
    """Refuse an address that is not http(s) or that names a private, loopback or link-local machine (an IP written out, `localhost`, and with
    `resolve` also a name that resolves to one). Raises `UnsafeURL`."""
    sp = urlsplit(url)
    host = (sp.hostname or "").lower()
    if sp.scheme not in ("http", "https") or not host:
        raise UnsafeURL("only http and https addresses are fetched")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan", ".home")):
        raise UnsafeURL("an address of a local machine is not fetched")
    try:
        ipaddress.ip_address(host)
        literal = True
    except ValueError:
        literal = False
    if literal:
        if not _public_ip(host):
            raise UnsafeURL("an address of a private or local machine is not fetched")
        return
    if resolve:
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            raise UnsafeURL("the address cannot be resolved")
        if not infos or not all(_public_ip(i[4][0]) for i in infos):
            raise UnsafeURL("an address that leads to a private or local machine is not fetched")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Every hop of a redirect must be a public address too."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(urljoin(req.full_url, newurl), resolve=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _real_open(req, timeout=None):
    """The real transport of a picture download: refused while real requests are off (A7), public addresses only (also after redirects)."""
    import os
    from ..safety import refuse_if_real_models_off
    refuse_if_real_models_off("download from %s" % host_of(req.full_url))
    if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("BTI_REAL_NETWORK_PROOF") != "1":      # a test must never reach a web page by accident
        raise RealModelsOff("download from a test")
    check_public_url(req.full_url, resolve=True)
    return urllib.request.build_opener(_CheckedRedirect).open(req, timeout=timeout)


def sniff_ext(head: bytes) -> str | None:
    """The extension of the image format that `head` (the first bytes of a file) is, among the formats the app stores; None for anything else."""
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tif"
    return None


def fetch_image(url: str, dest: Path, *, max_bytes: int = MAX_BYTES, opener: Callable | None = None, sleep: Callable[[float], None] = time.sleep,
                timeout: float = TIMEOUT) -> Path:
    """Download the picture at `url` to `dest` (the extension is replaced by the one of the file's real format) and return the path. Only an
    image content type (not SVG) and a file that really is a JPEG, PNG, WebP or TIFF, at most `max_bytes`. Raises `UnsafeURL`, `NotAnImage`,
    `http.FileTooLarge` or `http.MediaHTTPError`."""
    check_public_url(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    total = 0
    try:
        with http.open_url(url, timeout=timeout, tries=2, sleep=sleep, opener=opener or _real_open,
                           headers={"Accept": "image/jpeg,image/png,image/webp,image/*;q=0.5"}) as r, open(tmp, "wb") as fh:
            headers = getattr(r, "headers", None) or {}
            ctype = str(headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not ctype.startswith("image/") or "svg" in ctype:
                raise NotAnImage("the address does not answer with a picture (%s)" % (ctype or "no content type"))
            declared = headers.get("Content-Length")
            if declared and str(declared).isdigit() and int(declared) > max_bytes:
                raise http.FileTooLarge("the picture is %d bytes, over the %d byte limit" % (int(declared), max_bytes))
            head = b""
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                if not head:
                    head = chunk[:16]
                total += len(chunk)
                if total > max_bytes:
                    raise http.FileTooLarge("the download passed the %d byte limit" % max_bytes)
                fh.write(chunk)
        ext = sniff_ext(head)
        if ext is None:
            raise NotAnImage("the file is not a JPEG, PNG, WebP or TIFF picture")
        final = dest.with_suffix(ext)
        atomic_replace(tmp, final)
        return final
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def to_jpeg(path: Path) -> Path:
    """A WebP picture is stored as a JPEG (the rest of the app reads JPEG, PNG and TIFF); any other file is returned as it is."""
    path = Path(path)
    if path.suffix.lower() != ".webp":
        return path
    try:
        import cv2
        im = cv2.imread(str(path), cv2.IMREAD_COLOR)
        out = path.with_suffix(".jpg")
        if im is not None and cv2.imwrite(str(out), im, [cv2.IMWRITE_JPEG_QUALITY, 92]):
            path.unlink(missing_ok=True)
            return out
    except Exception:       # noqa: BLE001 - the WebP stays
        pass
    return path


# ---------------------------------------------------------------------------------------------------------------- the answer of the search
_NAMESPACE = re.compile(r"^(special|file|image|category|talk|help|wikipedia|template|portal|user|draft|module|mediawiki)(_talk)?:", re.I)


def _wikipedia_title(url: str) -> str | None:
    """The title of the article a Wikipedia address names, None for any other kind of page (a file, a category, a talk page ...)."""
    m = re.match(r"/wiki/([^?#]+)", urlsplit(url).path)
    if not m:
        return None
    t = unquote(m.group(1)).replace("_", " ")
    return None if _NAMESPACE.match(t) else t


def _snippet(result: dict, alt: str = "") -> str:
    """The few words that go with a candidate: the picture's own words (the `alt` text of the markdown image: it often names the very painting or person
    shown) when it has some, else what the page says about itself (`description`, else its first snippet)."""
    alt = " ".join(str(alt or "").split())
    if len(alt) > 3:
        s = alt
    else:
        s = " ".join(str(result.get("description") or "").split())
        if not s and result.get("snippets"):
            s = " ".join(str(result["snippets"][0]).split())
    return s if len(s) <= SNIPPET_CHARS else s[: SNIPPET_CHARS - 1].rstrip() + "…"


class WebSource:
    name = "web"

    def __init__(self, *, client=None, opener: Callable | None = None, sleep: Callable[[float], None] = time.sleep, blocked: Any = None,
                 require_ticket: bool = True, key: Callable[[], str | None] | None = None):
        self._client, self._opener, self._sleep = client, opener, sleep
        self._blocked_extra = blocked
        self.require_ticket = require_ticket
        self._key = key
        self.searches = 0                           # how many requests this source sent to You.com

    # ------------------------------------------------------------------------------------------------------------- the search
    def _make_client(self):
        if self._client is not None:
            return self._client
        from bti.script import env
        from ..youcom import YouComClient
        key = (self._key() if self._key else env.get_key("YDC_API_KEY")) or ""
        if not key:
            raise WebNoKey()
        return YouComClient(api_key=key, timeout=SEARCH_TIMEOUT)

    def _call(self, query: str) -> dict:
        """One You.com search (paid). -> the payload; raises on a refusal or a failed call."""
        client = self._make_client()
        self.searches += 1
        try:
            raw = client.search(query, None)
        except RealModelsOff:
            self.searches -= 1              # nothing left the machine
            raise
        if not raw.ok:
            status = raw.status_code
            if status == 429:
                raise http.MediaHTTPError("You.com says: too many requests", 429, retry_after=60)
            if raw.error and "YDC_API_KEY is not set" in raw.error:
                raise WebNoKey()
            raise http.MediaHTTPError("the You.com search failed (%s)" % (raw.error or "no answer"), status)
        return raw.payload if isinstance(raw.payload, dict) else {}

    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        if kind != "image":
            return []
        if self.require_ticket and not has_ticket():
            raise WebOff()
        query = " ".join(str(query or "").split())
        if not query:
            return []
        payload = self._call(query)
        return self.candidates_from(payload, limit=limit)

    # ------------------------------------------------------------------------------------------------------------- an answer -> candidates
    def candidates_from(self, payload: dict, *, limit: int = 24, report: list | None = None) -> list[dict]:
        """Candidate metas (the shape of `commons.parse_page`, plus `page_title`, `site`, `snippet`, `via`) from the best pages of an answer, in the
        order of the pages. `report`, when given, collects what was left out: `{"page": url, "picture": address | None, "why": sentence}`."""
        blocked = blocked_hosts(self._blocked_extra)
        results = ((payload.get("results") or {}).get("web") if isinstance(payload.get("results"), dict) else None) or []
        out: list[dict] = []
        seen: set = set()

        def drop(page, pic, why):
            if report is not None:
                report.append({"page": page, "picture": pic, "why": why})

        def refusal(u: str, page: str) -> str | None:
            """Why a picture address is not offered (None when it is)."""
            if hit2 := host_blocked(host_of(u), blocked):
                return "the picture's host is a stock agency or print shop (%s)" % hit2
            if why := junk_picture(u):
                return why
            try:
                check_public_url(u)
            except UnsafeURL as e:
                return str(e)
            sid = make_id(u, page)
            if sid is None:
                return "the picture's address is too long to keep"
            return None

        def add(meta: dict) -> None:
            ident = (meta.get("source"), meta.get("source_id"))
            key = ident if meta.get("source") != "web" else ("web", urlsplit(parse_id(meta["source_id"])[0])._replace(query="", fragment="").geturl())
            if key in seen:
                return
            seen.add(key)
            out.append(meta)

        for res in [r for r in results if isinstance(r, dict) and r.get("url")][:PAGES]:
            page = str(res["url"])
            host = host_of(page)
            title = " ".join(str(res.get("title") or "").split()) or site_name(host)
            site = site_name(host)
            hit = host_blocked(host, blocked)
            if hit:
                drop(page, None, "the site is a stock agency or print shop that watermarks its pictures (%s)" % hit)
                continue
            extra = {"page_title": title, "site": site, "via": "web"}
            if self._resolve(res, page, host, title, extra, add, drop, limit):
                continue
            pics: list[tuple[str, str]] = []
            lead = absolute(res.get("original_thumbnail_url") or "", page)
            if lead:
                if why := refusal(lead, page):
                    drop(page, lead, why)
                else:
                    pics.append((lead, ""))
            md = str((res.get("contents") or {}).get("markdown") or "") if isinstance(res.get("contents"), dict) else ""
            taken = 0
            for alt, src in _IMG_MD.findall(md):
                if taken >= MARKDOWN_PICTURES:
                    break
                u = absolute(src, page)
                if not u:
                    drop(page, src[:80], "a data or relative address that cannot be fetched")
                    continue
                if u in [p[0] for p in pics]:
                    continue
                if why := refusal(u, page):
                    drop(page, u, why)
                    continue
                pics.append((u, alt))
                taken += 1
            for u, alt in pics:
                add({"source": "web", "source_id": make_id(u, page), "title": title, "page_url": page, "url": u, "thumb_url": u, "width": 0, "height": 0,
                     "size": 0, "mime": "image/jpeg", "kind": "image", "author": site, "licence": "", "description": "", "page_title": title, "site": site,
                     "snippet": _snippet(res, alt), "via": "web"})
        return out[: max(1, int(limit))]

    def _resolve(self, res: dict, page: str, host: str, title: str, extra: dict, add, drop, limit: int) -> bool:
        """A page of Wikipedia, Wikimedia Commons or the Met is resolved by the source that knows it. -> True when the page was handled."""
        from bti.media import api
        from . import wikipedia
        lang = wikipedia.lang_of(host)
        try:
            if lang:
                art = _wikipedia_title(page)
                if art is None:
                    drop(page, None, "a Wikipedia page that is not an article")
                    return True
                found = api.get_source("wikipedia").page_pictures(art, lang, limit=min(limit, 8))
                if not found:
                    drop(page, None, "the Wikipedia article has no picture worth offering")
                for m in found:
                    add({**m, "via": "web", "snippet": m.get("snippet") or _snippet(res)})
                return True
            if host == "commons.wikimedia.org":
                m = re.match(r"/wiki/(File:[^?#]+)", urlsplit(page).path, re.I)
                if not m:
                    drop(page, None, "a Commons page that is not a file")
                    return True
                meta = api.get_source("commons").fetch_meta(unquote(m.group(1)).replace("_", " "))
                add({**meta, **extra, "snippet": _snippet(res)})
                return True
            mm = re.match(r"/art/collection/search/(\d+)", urlsplit(page).path) if host.endswith("metmuseum.org") else None
            if mm:
                meta = api.get_source("met").fetch_meta(mm.group(1))
                if not meta.get("url") or not meta.get("isPublicDomain"):
                    drop(page, None, "the Met object has no public-domain picture")
                    return True
                add({**meta, **extra, "snippet": _snippet(res)})
                return True
        except NotFound:
            drop(page, None, "the source has no such picture")
            return True
        except (http.MediaHTTPError, OSError) as e:
            drop(page, None, "could not be resolved (%s)" % type(e).__name__)
            return True
        return False

    # ------------------------------------------------------------------------------------------------------------- the source protocol
    def fetch_meta(self, source_id: str) -> dict:
        """The meta of a candidate from its id alone (the picture's address and, after a space, the page's): what an import needs."""
        img, page = parse_id(source_id)
        try:
            check_public_url(img)
        except UnsafeURL as e:
            raise NotFound("web picture %r: %s" % (img[:80], e))
        ext = Path(urlparse(img).path).suffix.lower()
        mime = {".png": "image/png", ".webp": "image/webp", ".tif": "image/tiff", ".tiff": "image/tiff"}.get(ext, "image/jpeg")
        site = site_name(host_of(page or img))
        return {"source": "web", "source_id": source_id, "title": title_of(img, title_of(page, site)) or site, "page_url": page or img, "url": img,
                "thumb_url": img, "width": 0, "height": 0, "size": 0, "mime": mime, "kind": "image", "author": site, "licence": "", "description": "",
                "site": site}

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        from ..licence import check_licence
        return check_licence(meta)

    def credit(self, meta: dict) -> dict:
        return {"source": "web", "source_url": meta.get("page_url", ""), "author": meta.get("author") or "unknown", "licence": "", "licence_url": ""}

    def download(self, meta: dict, dest, *, min_short_side: int = 0, max_bytes: int = MAX_BYTES) -> Path:
        """Download the picture (see `fetch_image`; the file keeps the extension of its real format, a WebP becomes a JPEG) and return its path."""
        url = str(meta.get("url") or "").strip()
        if not url:
            raise NotFound("web picture %r: no address" % str(meta.get("source_id"))[:80])
        got = to_jpeg(fetch_image(url, Path(dest), max_bytes=max_bytes, opener=self._opener, sleep=self._sleep))
        if min_short_side:
            w, h = image_size(got)
            if w and h and min(w, h) < min_short_side:
                from ..errors import ImageTooSmall
                got.unlink(missing_ok=True)
                raise ImageTooSmall("web picture %s: %dx%d px, below %d" % (str(meta.get("source_id"))[:60], w, h, min_short_side))
        return got
