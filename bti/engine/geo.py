"""Geography for `MAP-01`: Web Mercator views and the bundled Natural Earth data (`style/gae/geo/`, see its README).

A view is a centre (longitude, latitude) and a ground width in kilometres at the centre's latitude; the frame is 1920 x 1080.
Web Mercator: x = (lon - lon0) * s, y = -(merc(lat) - merc(lat0)) * s, with merc(lat) = ln tan(pi/4 + lat/2) and s the pixels per
radian of longitude, s = W * R * cos(lat0) / width_km (R = 6371 km).  Everything here is pure; the bundle is read once per process
and cached (no network, no environment variable beyond the style folder the registry already knows).
"""
from __future__ import annotations

import json
import math
import threading
import zipfile
from pathlib import Path

import numpy as np

from . import registry as R

EARTH_KM = 6371.0
FRAME_W, FRAME_H = 1920, 1080
LAT_LIMIT = 85.0511287798
MIN_WIDTH_KM, MAX_WIDTH_KM = 50.0, 20000.0
NARROW_KM = 1500.0               # views narrower than this use the 1:10m outlines (contract section 6)


def merc(lat_deg):
    """Mercator ordinate (radians) of a latitude in degrees (scalar or array); the latitude is held to the Web Mercator limit."""
    lat = np.clip(np.asarray(lat_deg, np.float64), -LAT_LIMIT, LAT_LIMIT)
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def inv_merc(y):
    """Latitude in degrees of a Mercator ordinate."""
    return np.degrees(2 * np.arctan(np.exp(np.asarray(y, np.float64))) - np.pi / 2)


class View:
    """A map view: where the centre is and how large it is. `s` is pixels per radian of longitude on a frame `w` px wide."""

    __slots__ = ("lon0", "lat0", "my0", "width_km", "s", "w", "h")

    def __init__(self, lon0: float, lat0: float, width_km: float, w: int = FRAME_W, h: int = FRAME_H):
        self.lon0, self.lat0, self.width_km, self.w, self.h = float(lon0), float(lat0), float(width_km), w, h
        self.my0 = float(merc(lat0))
        self.s = w * EARTH_KM * math.cos(math.radians(self.lat0)) / self.width_km

    @classmethod
    def from_scale(cls, lon0: float, my0: float, s: float, w: int = FRAME_W, h: int = FRAME_H) -> "View":
        """A view from its Mercator centre and its scale (what an eased push produces between two views)."""
        lat0 = float(inv_merc(my0))
        return cls(lon0, lat0, w * EARTH_KM * math.cos(math.radians(lat0)) / s, w, h)

    def to_px(self, lon, lat, dx: float = 0.0, dy: float = 0.0):
        """Canvas pixels (x, y) of longitude and latitude in degrees (scalars or arrays), plus an offset."""
        x = self.w / 2 + np.radians(np.asarray(lon, np.float64) - self.lon0) * self.s + dx
        y = self.h / 2 - (merc(lat) - self.my0) * self.s + dy
        return x, y

    def to_lonlat(self, x, y):
        lon = self.lon0 + np.degrees((np.asarray(x, np.float64) - self.w / 2) / self.s)
        lat = inv_merc(self.my0 - (np.asarray(y, np.float64) - self.h / 2) / self.s)
        return lon, lat

    def km_per_px(self) -> float:
        return self.width_km / self.w


def fit(points, margin_pct: float, w: int = FRAME_W, h: int = FRAME_H, default_width_km: float = 600.0) -> View:
    """The view that keeps every (lon, lat) of `points` inside the middle of the frame: `margin_pct` percent of the frame on every side,
    so the points' box fills at most (100 - 2 * margin) percent of the width and of the height. The centre is the middle of the box
    in Mercator space. A single place (or places on one spot) gets `default_width_km`. The width is held to the bounds of the technique."""
    pts = np.asarray(points, np.float64).reshape(-1, 2)
    lon = np.radians(pts[:, 0])
    my = merc(pts[:, 1])
    dx, dy = float(lon.max() - lon.min()), float(my.max() - my.min())
    lon0, my0 = float(np.degrees((lon.max() + lon.min()) / 2)), float((my.max() + my.min()) / 2)
    lat0 = float(inv_merc(my0))
    room = max(1e-6, 1.0 - 2.0 * margin_pct / 100.0)
    if dx < 1e-9 and dy < 1e-9:
        width = default_width_km
    else:
        s = room * min(w / dx if dx > 1e-12 else math.inf, h / dy if dy > 1e-12 else math.inf)
        width = w * EARTH_KM * math.cos(math.radians(lat0)) / s
    return View(lon0, lat0, float(min(MAX_WIDTH_KM, max(MIN_WIDTH_KM, width))), w, h)


def ease_view(a: View, b: View, e: float) -> View:
    """The view at eased progress `e` (0..1) of a push from `a` to `b`: the zoom (pixels per radian) and the centre both run linearly
    in `e`, as the approved mock-up's camera does (`scale(lerp(1, k, ease))`)."""
    e = min(1.0, max(0.0, e))
    s = a.s + (b.s - a.s) * e
    lon0 = a.lon0 + (b.lon0 - a.lon0) * e
    my0 = a.my0 + (b.my0 - a.my0) * e
    return View.from_scale(lon0, my0, s, a.w, a.h)


# ----------------------------------------------------------------------------- the bundle
class Rings:
    """One bundled layer: rings in draw order. `lon` is radians, `my` the Mercator ordinate, both float64 over all vertices; ring i
    owns vertices off[i]:off[i+1]. `hole[i]` marks a ring that cuts a hole; `aux[i]` is the country index (countries layer);
    `coast[v]` is 1 when the edge from vertex v to the next one of its ring is a coast (land layers). `box` is (n, 4):
    lon_min, lon_max, my_min, my_max per ring."""

    def __init__(self, path: Path):
        with np.load(path, allow_pickle=False) as z:
            q = float(z["q"][0])
            off = z["off"].astype(np.int64)
            start = z["start"].astype(np.int64)
            step = z["step"].astype(np.int64)
            n_ring = len(off) - 1
            cs = np.cumsum(step, axis=0)
            base = cs[off[:-1]]                                           # the running sum where each ring starts (its own step there is 0)
            xy = cs - np.repeat(base, np.diff(off), axis=0) + np.repeat(start, np.diff(off), axis=0)
            self.off = off
            self.hole = z["hole"].astype(bool)
            self.aux = z["aux"].astype(np.int64)
            self.coast = z["coast"].astype(bool) if "coast" in z.files else None
            self.iso = [str(x) for x in z["iso"]] if "iso" in z.files else None
            self.names = [str(x) for x in z["name"]] if "name" in z.files else None
        deg = xy.astype(np.float64) / q
        self.lon = np.radians(deg[:, 0])
        self.my = merc(deg[:, 1])
        idx = off[:-1]
        self.box = np.stack([np.minimum.reduceat(self.lon, idx), np.maximum.reduceat(self.lon, idx),
                             np.minimum.reduceat(self.my, idx), np.maximum.reduceat(self.my, idx)], axis=1)
        self.n = n_ring
        # rings with an edge that is no coast (it only cuts the world): they are drawn edge by edge
        self.cut = (np.minimum.reduceat(self.coast.astype(np.uint8), idx) == 0) if self.coast is not None else None

    def ring(self, i: int):
        a, b = self.off[i], self.off[i + 1]
        return self.lon[a:b], self.my[a:b]

    def visible(self, lon_lo, lon_hi, my_lo, my_hi, shift: float = 0.0) -> np.ndarray:
        """Indices (ascending: draw order) of the rings whose box meets the world rectangle once the layer is moved by `shift` radians."""
        b = self.box
        m = (b[:, 1] + shift >= lon_lo) & (b[:, 0] + shift <= lon_hi) & (b[:, 3] >= my_lo) & (b[:, 2] <= my_hi)
        return np.nonzero(m)[0]


_LOCK = threading.RLock()
_CACHE: dict = {}


def geo_dir() -> Path:
    return R.STYLE_ROOT / "gae" / "geo"


class GeoDataError(FileNotFoundError):
    """The bundled geography is missing or unreadable."""


def _cached(key, build):
    with _LOCK:
        v = _CACHE.get(key)
        if v is None:
            try:
                v = build()
            except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
                raise GeoDataError("the bundled geography %s is missing or unreadable (%s)" % (key, str(e)[:100]))
            _CACHE[key] = v
        return v


def land(res: str) -> Rings:
    """The land rings at '50m' or '10m' (loaded once)."""
    if res not in ("50m", "10m"):
        raise ValueError("resolution must be 50m or 10m")
    return _cached("land_" + res, lambda: Rings(geo_dir() / ("land_%s.npz" % res)))


def countries() -> Rings:
    return _cached("countries_50m", lambda: Rings(geo_dir() / "countries_50m.npz"))


def seas() -> list:
    """[{name, lon, lat, rank, extent_km}], most important first."""
    return _cached("seas", lambda: json.loads((geo_dir() / "seas.json").read_text(encoding="utf-8"))["seas"])


def iso_codes() -> set:
    """The ISO 3166-1 alpha-2 codes the country layer knows (upper case)."""
    return set(countries().iso)


def country_name(code: str) -> str | None:
    c = countries()
    code = str(code).upper()
    return c.names[c.iso.index(code)] if code in c.iso else None


def level_for(width_km: float) -> str:
    return "10m" if width_km < NARROW_KM else "50m"
