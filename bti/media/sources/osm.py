"""OpenStreetMap map source.

Geocodes places via Nominatim (polite rate limit <= 1 req/sec),
composes a map image ~2400 px wide from standard OSM tiles at a zoom
that shows the place, records credit "© OpenStreetMap contributors" (ODbL).
Low volume by design: one map per request, cached by place and zoom.
"""
from __future__ import annotations

import io
import math
import shutil
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from PIL import Image

from .. import http
from ..errors import ImageTooSmall, NotFound, RealModelsOff
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
        self._meta_cache: dict[str, dict] = {}

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
                try:
                    tb = self._tile_data(z, norm_tx, ty)
                    tile_img = Image.open(io.BytesIO(tb)).convert("RGB")
                    px_pos = int(round(tx * 256.0 - x0))
                    py_pos = int(round(ty * 256.0 - y0))
                    canvas.paste(tile_img, (px_pos, py_pos))
                except RealModelsOff:       # a refusal must not end as a grey map that is then cached
                    raise
                except Exception:
                    pass

        tmp = dest.with_name(dest.name + ".part.jpg")
        canvas.save(tmp, format="JPEG", quality=90)
        from bti.fsio import atomic_replace
        atomic_replace(tmp, dest)
        return dest

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
        pid = str(h.get("place_id") or f"{lat:.3f}_{lon:.3f}")
        bb = h.get("boundingbox") or []
        z = calculate_zoom(bb)
        dname = (h.get("display_name") or query).strip()
        short_name = dname.split(",")[0].strip() or query
        title = f"Bản đồ {short_name}"
        sid = f"{pid}:{z}"

        cache_path = self.cache_dir / f"{pid}_z{z}.jpg"
        meta = {
            "source": "osm",
            "source_id": sid,
            "title": title,
            "page_url": f"https://www.openstreetmap.org/#map={z}/{lat:.4f}/{lon:.4f}",
            "url": str(cache_path) if cache_path.is_file() else f"https://www.openstreetmap.org/#map={z}/{lat:.4f}/{lon:.4f}",
            "thumb_url": str(cache_path) if cache_path.is_file() else "",
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
            "size": cache_path.stat().st_size if cache_path.is_file() else 0,
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
        self._meta_cache[sid] = meta
        return [meta]

    def fetch_meta(self, source_id: str) -> dict:
        sid = str(source_id).strip()
        if sid in self._meta_cache:
            return self._meta_cache[sid]
        # Parse place_id:zoom
        pid, _, z_str = sid.partition(":")
        z = int(z_str) if z_str.isdigit() else 12
        cache_path = self.cache_dir / f"{pid}_z{z}.jpg"
        meta = {
            "source": "osm",
            "source_id": sid,
            "title": f"Bản đồ OpenStreetMap ({pid})",
            "page_url": "https://www.openstreetmap.org",
            "url": str(cache_path) if cache_path.is_file() else "https://www.openstreetmap.org",
            "thumb_url": str(cache_path) if cache_path.is_file() else "",
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
            "size": cache_path.stat().st_size if cache_path.is_file() else 0,
            "mime": "image/jpeg",
            "kind": "image",
            "author": OSM_AUTHOR,
            "artist": OSM_AUTHOR,
            "licence": OSM_LICENCE,
            "licence_url": OSM_LICENCE_URL,
            "_zoom": z,
            "_place_id": pid,
        }
        return meta

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

    def download(self, meta: dict, dest: Path, *, min_short_side: int = 0,
                 max_bytes: int = 100 * 1024 * 1024) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        sid = meta.get("source_id", "")
        pid = str(meta.get("_place_id") or sid.partition(":")[0] or "osm")
        z = int(meta.get("_zoom") or (sid.partition(":")[2] if ":" in sid else 12) or 12)
        cache_path = self.cache_dir / f"{pid}_z{z}.jpg"

        if cache_path.is_file() and cache_path.stat().st_size > 0:
            shutil.copyfile(cache_path, dest)
            return dest

        lat = meta.get("_lat")
        lon = meta.get("_lon")
        if lat is None or lon is None:
            # If not in meta, try search or default to center of world
            lat, lon = 51.0543, 3.7174

        self.compose_map(float(lat), float(lon), z, cache_path)
        shutil.copyfile(cache_path, dest)

        if min_short_side:
            w, h = image_size(dest)
            if w and h and min(w, h) < min_short_side:
                dest.unlink(missing_ok=True)
                raise ImageTooSmall(f"osm {sid}: {w}x{h} px, below {min_short_side}")
        return dest
