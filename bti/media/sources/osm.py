"""OpenStreetMap map source.

Geocodes places via Nominatim (polite rate limit <= 1 req/sec),
composes a map image ~2400 px wide from standard OSM tiles at a zoom
that shows the place, records credit "© OpenStreetMap contributors" (ODbL).
Low volume by design: one map per request, cached by centre and zoom.

The source id of a map carries everything that is needed to draw it: `place_id:zoom:lat:lon[:name]` (the coordinates the search
returned, rounded to 5 decimals; the name is the short place name, percent-encoded). The import request holds nothing else, so
`fetch_meta` rebuilds the place from the id alone, with no memory of an earlier search (the app can restart between the two).
A map is never drawn for a place that is not known: an id without usable coordinates is `MapPlaceUnknown`. There is no default
centre. A cached map is found by its file name, which holds the zoom and the rounded centre it was drawn for, so a file can
only be served for the place it was drawn for.
"""
from __future__ import annotations

import io
import math
import re
import shutil
import time
from pathlib import Path
from typing import Callable
from urllib.parse import quote, unquote, urlencode

from PIL import Image

from .. import http
from ..errors import ImageTooSmall, MapPlaceUnknown, NotFound
from ..imageinfo import image_size
from ..licence import check_licence

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_DETAILS = "https://nominatim.openstreetmap.org/details"
TILE_URL_TEMPLATE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
MAP_WIDTH = 2400
MAP_HEIGHT = 1350
OSM_AUTHOR = "© OpenStreetMap contributors"
OSM_LICENCE = "ODbL"
OSM_LICENCE_URL = "https://www.openstreetmap.org/copyright"

_last_nominatim = [0.0]


def calculate_zoom(boundingbox: list[str] | tuple[str, ...]) -> int:
    """Calculate an appropriate zoom level so that the boundingbox fits nicely in ~2400 px."""
    try:
        s, n, w, e = float(boundingbox[0]), float(boundingbox[1]), float(boundingbox[2]), float(boundingbox[3])
    except (IndexError, TypeError, ValueError):
        return 12
    span = max(abs(n - s), abs(e - w))
    if span <= 0.0001:
        return 14
    # 1800 / span gives roughly the scale where span degrees occupies ~5 tiles
    raw_z = math.log2(max(1.0, 1800.0 / span))
    return max(2, min(int(math.floor(raw_z)), 18))


def _lat_lon_to_tile(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    # Clamp lat to avoid mercator singularity near poles
    lat_rad = max(-1.4844, min(1.4844, lat_rad))
    y = (1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    return x, y


MAX_LAT = 85.0511                  # the Web Mercator limit of the tiles
MAX_ZOOM = 19
_PID = re.compile(r"[0-9A-Za-z._-]{1,40}")
_NAME_CHARS = 40                   # the most characters of the place name kept in a source id ...
_NAME_ENCODED = 150                # ... and the most characters it may take percent-encoded: the whole id stays under the routes' 300


def _coord(v) -> float | None:
    """`v` as a latitude/longitude rounded to 5 decimals (about 1 m), or None when it is not a finite number."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 5) + 0.0 if math.isfinite(f) else None      # + 0.0: no "-0.00000"


def _zoom(z) -> int | None:
    if isinstance(z, bool):
        return None
    if isinstance(z, str):
        z = z.strip()
        if not re.fullmatch(r"\d{1,2}", z):
            return None
    try:
        zi = int(z)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(z, float) and z != zi:
        return None
    return zi if 0 <= zi <= MAX_ZOOM else None


def valid_place(lat, lon, z) -> tuple[float, float, int] | None:
    """`(lat, lon, zoom)` with the coordinates rounded, or None when they cannot be placed on a map: not finite numbers, a
    latitude beyond the tile grid, a longitude beyond 180, a zoom outside 0..19."""
    la, lo, zi = _coord(lat), _coord(lon), _zoom(z)
    if la is None or lo is None or zi is None or abs(la) > MAX_LAT or abs(lo) > 180.0:
        return None
    return la, lo, zi


def _short_name(name) -> str:
    """The place name as kept in an id: spaces folded, at most `_NAME_CHARS` characters and `_NAME_ENCODED` once encoded."""
    name = " ".join(str(name or "").split())[:_NAME_CHARS]
    while name and len(quote(name, safe="")) > _NAME_ENCODED:
        name = name[:-1]
    return name


def make_source_id(pid, z: int, lat: float, lon: float, name: str = "") -> str:
    """`place_id:zoom:lat:lon[:name]`: what a search result's `source_id` is. The coordinates are the rounded ones."""
    place = valid_place(lat, lon, z)
    if place is None:
        raise MapPlaceUnknown(f"lat {lat!r}, lon {lon!r}, zoom {z!r}")
    la, lo, zi = place
    safe = re.sub(r"[^0-9A-Za-z._-]", "_", str(pid))[:40] or "x"
    sid = f"{safe}:{zi}:{la:.5f}:{lo:.5f}"
    name = _short_name(name)
    return f"{sid}:{quote(name, safe='')}" if name else sid


def parse_source_id(source_id: str) -> dict | None:
    """The place a source id names: `{pid, zoom, lat, lon, name}`, or None when it does not carry usable coordinates (the old
    `place_id:zoom` form, or anything else)."""
    parts = str(source_id or "").strip().split(":", 4)
    if len(parts) < 4 or not _PID.fullmatch(parts[0]) or not re.fullmatch(r"\d{1,2}", parts[1]):
        return None
    place = valid_place(parts[2], parts[3], parts[1])
    if place is None:
        return None
    return {"pid": parts[0], "lat": place[0], "lon": place[1], "zoom": place[2],
            "name": unquote(parts[4]) if len(parts) == 5 else ""}


class OsmSource:
    name = "osm"

    def __init__(self, *, opener: Callable | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic,
                 cache_dir: Path | None = None,
                 nominatim_url: str = NOMINATIM_URL):
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self.nominatim_url = nominatim_url
        self.cache_dir = Path(cache_dir or Path(".cache") / "osm")

    def _rate_limit_nominatim(self):
        now = self._clock()
        elapsed = now - _last_nominatim[0]
        if elapsed < 1.0:
            self._sleep(1.0 - elapsed)
        _last_nominatim[0] = self._clock()

    def _geocode(self, query: str) -> list[dict]:
        self._rate_limit_nominatim()
        params = {"q": query, "format": "json", "limit": 1, "addressdetails": 1}
        url = f"{self.nominatim_url}?{urlencode(params)}"
        hdrs = {"User-Agent": http.USER_AGENT, "Accept": "application/json"}
        with http.open_url(url, headers=hdrs, opener=self._opener, sleep=self._sleep) as r:
            body = r.read()
        import json
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError as exc:
            raise http.MediaHTTPError(f"response was not JSON for {http._short(url)}") from exc

    def _tile_data(self, z: int, x: int, y: int) -> bytes:
        url = TILE_URL_TEMPLATE.format(z=z, x=x, y=y)
        with http.open_url(url, opener=self._opener, sleep=self._sleep) as r:
            return r.read()

    def compose_map(self, lat: float, lon: float, z: int, dest: Path) -> Path:
        """Compose a 2400x1350 image from tiles centered at (lat, lon) at zoom z."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cx, cy = _lat_lon_to_tile(lat, lon, z)
        cpx, cpy = cx * 256.0, cy * 256.0
        x0 = cpx - MAP_WIDTH / 2.0
        y0 = cpy - MAP_HEIGHT / 2.0

        n = 2 ** z
        tx_min = int(math.floor(x0 / 256.0))
        tx_max = int(math.floor((x0 + MAP_WIDTH - 1.0) / 256.0))
        ty_min = int(math.floor(y0 / 256.0))
        ty_max = int(math.floor((y0 + MAP_HEIGHT - 1.0) / 256.0))

        canvas = Image.new("RGB", (MAP_WIDTH, MAP_HEIGHT), (220, 225, 230))
        for ty in range(ty_min, ty_max + 1):
            if not 0 <= ty < n:
                continue
            for tx in range(tx_min, tx_max + 1):
                norm_tx = tx % n
                tb = self._tile_data(z, norm_tx, ty)        # a refusal or a failure stops here: the first one ends the map, so a
                try:                                        # tile server that said "wait" is not asked for the other tiles, and
                    tile_img = Image.open(io.BytesIO(tb)).convert("RGB")      # no grey map with holes is ever cached
                except Exception as exc:
                    raise http.MediaHTTPError(f"tile {z}/{norm_tx}/{ty} is not an image") from exc
                px_pos = int(round(tx * 256.0 - x0))
                py_pos = int(round(ty * 256.0 - y0))
                canvas.paste(tile_img, (px_pos, py_pos))

        tmp = dest.with_name(dest.name + ".part.jpg")
        canvas.save(tmp, format="JPEG", quality=90)
        from bti.fsio import atomic_replace
        atomic_replace(tmp, dest)
        return dest

    def _cache_path(self, lat: float, lon: float, z: int) -> Path:
        """The cache file of the map centred on (lat, lon) at zoom z. Its name IS the proof of what it was drawn for: the map
        size, the zoom and the rounded centre. A file found under any other name (the old `<place_id>_z<zoom>.jpg`, which could
        hold a map of another place) is never served."""
        return self.cache_dir / f"osm_{MAP_WIDTH}x{MAP_HEIGHT}_z{z}_{lat:.5f}_{lon:.5f}.jpg"

    def _meta(self, pid: str, z: int, lat: float, lon: float, name: str, sid: str | None = None) -> dict:
        """The meta of the map of one place. Built only from the id's own parts, so a search and a later `fetch_meta` give the
        same answer in any process. `sid`: the id the caller used, kept as the meta's id (it is the item's identity)."""
        name = _short_name(name)
        cache_path = self._cache_path(lat, lon, z)
        page = f"https://www.openstreetmap.org/#map={z}/{lat:.4f}/{lon:.4f}"
        title = f"Bản đồ {name}" if name else f"Bản đồ OpenStreetMap ({lat:.4f}, {lon:.4f})"
        cached = cache_path.is_file()
        return {
            "source": "osm",
            "source_id": sid or make_source_id(pid, z, lat, lon, name),
            "title": title,
            "page_url": page,
            "url": str(cache_path) if cached else page,
            "thumb_url": str(cache_path) if cached else "",
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
            "size": cache_path.stat().st_size if cached else 0,
            "mime": "image/jpeg",
            "kind": "image",
            "author": OSM_AUTHOR,
            "artist": OSM_AUTHOR,
            "licence": OSM_LICENCE,
            "licence_url": OSM_LICENCE_URL,
            "_lat": lat,
            "_lon": lon,
            "_zoom": z,
            "_place_id": pid,
            "_title": title,
        }

    def search(self, query: str, kind: str = "image", limit: int = 1) -> list[dict]:
        if kind != "image":
            return []
        query = (query or "").strip()
        if not query:
            return []
        hits = self._geocode(query)
        if not hits:
            return []
        h = hits[0]
        try:
            lat = float(h["lat"])
            lon = float(h["lon"])
        except (KeyError, TypeError, ValueError):
            return []
        z = calculate_zoom(h.get("boundingbox") or [])
        place = valid_place(lat, lon, z)
        if place is None:
            return []
        lat, lon, z = place
        pid = str(h.get("place_id") or f"{lat:.3f}_{lon:.3f}")
        dname = (h.get("display_name") or query).strip()
        short_name = dname.split(",")[0].strip() or query
        return [self._meta(pid, z, lat, lon, short_name)]

    def check_id(self, source_id: str) -> None:
        """`MapPlaceUnknown` unless the id carries a usable place. The facade calls it before it looks in the project's index, so a
        record kept under an id of the old form (`place_id:zoom`, which could stand for a map of the wrong city) is not served."""
        if parse_source_id(source_id) is None:
            raise MapPlaceUnknown(f"source id {str(source_id)[:60]!r} has no coordinates")

    def fetch_meta(self, source_id: str) -> dict:
        """The map named by a source id of this source. The id carries the place (`parse_source_id`); one that does not is
        `MapPlaceUnknown`: nothing is guessed and no default place is used."""
        self.check_id(source_id)
        place = parse_source_id(source_id)
        return self._meta(place["pid"], place["zoom"], place["lat"], place["lon"], place["name"], str(source_id).strip())

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        return check_licence(meta)

    def credit(self, meta: dict) -> dict:
        return {
            "source": "osm",
            "source_url": meta.get("page_url", "https://www.openstreetmap.org"),
            "author": OSM_AUTHOR,
            "licence": OSM_LICENCE,
            "licence_url": OSM_LICENCE_URL,
        }

    def _place_of(self, meta: dict) -> tuple[float, float, int]:
        """(lat, lon, zoom) of the map `meta` names: the meta's own coordinates when it has them, else those of its source id.
        `MapPlaceUnknown` when neither says where the map is (never a default place)."""
        place = valid_place(meta.get("_lat"), meta.get("_lon"), meta.get("_zoom"))
        if place is None:
            parsed = parse_source_id(meta.get("source_id", ""))
            place = (parsed["lat"], parsed["lon"], parsed["zoom"]) if parsed else None
        if place is None:
            raise MapPlaceUnknown(f"source id {str(meta.get('source_id', ''))[:60]!r} has no coordinates")
        return place

    def download(self, meta: dict, dest: Path, *, min_short_side: int = 0,
                 max_bytes: int = 100 * 1024 * 1024) -> Path:
        """Write the map of `meta` to `dest`: the cached one when it was drawn for this very centre and zoom, else a new one
        (about 60 tile requests, one map per call), which is cached only when every tile arrived."""
        lat, lon, z = self._place_of(meta)
        sid = meta.get("source_id", "")
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(lat, lon, z)

        if cache_path.is_file() and cache_path.stat().st_size > 0:
            shutil.copyfile(cache_path, dest)
            return dest

        self.compose_map(lat, lon, z, cache_path)
        shutil.copyfile(cache_path, dest)

        if min_short_side:
            w, h = image_size(dest)
            if w and h and min(w, h) < min_short_side:
                dest.unlink(missing_ok=True)
                raise ImageTooSmall(f"osm {sid}: {w}x{h} px, below {min_short_side}")
        return dest
