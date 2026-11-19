"""Rebuild the geography bundle `style/gae/geo/` from Natural Earth's own downloads (public domain).

    python tools/geo/build_bundle.py --downloads DIR            # DIR holds the six zip files (see SOURCES)
    python tools/geo/build_bundle.py --downloads DIR --fetch    # download them first (naciscdn.org, Natural Earth's own host)

Needs numpy and OpenCV only (the shapefile and dbf readers below are the standard library). Output (all deterministic: the same
downloads give byte-identical files, so the sha256 in `style/gae/geo/README.md` can be checked):

    land_50m.npz, land_10m.npz     land rings, quantised to 1e-4 degree, delta coded, sorted by area (draw order: big first)
    countries_50m.npz              country rings with an index into the ISO 3166-1 alpha-2 / name tables
    seas.json                      sea and ocean names with a position, a rank and an extent in km
    manifest.json                  url, version and sha256 of each download, sha256 and size of each stored file

The coastline is not stored apart: the engine strokes the rings of the land file (minus the edges that only cut the world at the
antimeridian and at -90 degrees, which `coast` marks), so the hairline can never disagree with the fill, whatever versions the
separate coastline downloads carry.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

import cv2
import numpy as np

BASE = "https://naciscdn.org/naturalearth/"
SOURCES = {          # stored name -> (path below BASE, what it is used for)
    "ne_10m_land": ("10m/physical/ne_10m_land.zip", "land and coastline, 1:10m"),
    "ne_50m_land": ("50m/physical/ne_50m_land.zip", "land and coastline, 1:50m"),
    "ne_50m_admin_0_countries": ("50m/cultural/ne_50m_admin_0_countries.zip", "countries with ISO codes, 1:50m"),
    "ne_50m_geography_marine_polys": ("50m/physical/ne_50m_geography_marine_polys.zip", "sea and ocean names"),
}
Q = 1e4                      # quantisation: 1e-4 degree (11 m)
LAT_MAX = 85.0511287798      # the Web Mercator limit
USER_AGENT = "naturalearth-bundle-builder/1.0"

# Hand placed label positions (lon, lat) for the seas whose pole of inaccessibility is not where a plate would print the name.
# The first four are the places of the approved mock-up (docs/design/mock/2026-11-18-explainer/prep_geo.py).
LABEL_AT = {
    "North Sea": (3.0, 55.6), "Bay of Biscay": (-4.6, 45.3), "Mediterranean Sea": (5.0, 40.6), "Adriatic Sea": (15.0, 43.2),
    "Baltic Sea": (19.5, 58.3), "Black Sea": (34.0, 43.3), "Norwegian Sea": (3.0, 66.0), "Tyrrhenian Sea": (12.0, 39.6),
    "Aegean Sea": (25.0, 38.6), "Ionian Sea": (18.8, 37.6), "English Channel": (-1.6, 50.2), "Irish Sea": (-4.9, 53.8),
    "Red Sea": (38.4, 20.5), "Caspian Sea": (50.5, 42.0), "Barents Sea": (40.0, 74.0), "Arabian Sea": (65.0, 15.0),
    "North Atlantic Ocean": (-38.0, 33.0), "South Atlantic Ocean": (-15.0, -20.0), "North Pacific Ocean": (-160.0, 30.0),
    "South Pacific Ocean": (-130.0, -25.0), "Indian Ocean": (78.0, -20.0), "Arctic Ocean": (-5.0, 84.0), "Southern Ocean": (60.0, -62.0),
    "Persian Gulf": (51.5, 27.0), "Gulf of Mexico": (-90.5, 25.0), "Caribbean Sea": (-75.0, 15.0), "Balearic Sea": (2.5, 40.0),
    "Gulf of Bothnia": (20.0, 62.5), "Gulf of Finland": (26.0, 59.9), "White Sea": (38.0, 66.0), "Sargasso Sea": (-60.0, 28.0),
}
KEEP_CLASSES = {"ocean", "sea", "gulf", "bay", "strait", "channel", "sound"}
MAX_RANK = 4


# ----------------------------------------------------------------------------- readers (standard library)
def read_zip(path: Path, stem: str):
    """(shp bytes, dbf bytes, version text) of the zip `path`, whose members are named `stem`.*"""
    with zipfile.ZipFile(path) as z:
        return z.read(stem + ".shp"), z.read(stem + ".dbf"), z.read(stem + ".VERSION.txt").decode("ascii").strip()


def read_shp(data: bytes):
    """Polygon records of a shapefile: a list of (record number, [rings as float64 arrays (n, 2)]). Rings keep the file's order."""
    out, pos, n = [], 100, len(data)
    shape_type = struct.unpack("<i", data[32:36])[0]
    if shape_type not in (3, 5):
        raise ValueError("shape type %d is not a polyline or polygon" % shape_type)
    while pos + 8 <= n:
        rec_no, words = struct.unpack(">ii", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + words * 2]
        pos += 8 + words * 2
        st = struct.unpack("<i", body[:4])[0]
        if st == 0:
            continue
        n_parts, n_pts = struct.unpack("<ii", body[36:44])
        parts = np.frombuffer(body, "<i4", n_parts, 44)
        pts = np.frombuffer(body, "<f8", n_pts * 2, 44 + 4 * n_parts).reshape(n_pts, 2)
        bounds = list(parts) + [n_pts]
        out.append((rec_no, [pts[bounds[i]:bounds[i + 1]].copy() for i in range(n_parts)]))
    return out


def read_dbf(data: bytes):
    """Rows of a dbf file as a list of dicts of stripped strings."""
    nrec, hlen, rlen = struct.unpack("<xxxxIHH", data[:12])
    fields, p = [], 32
    while data[p] != 0x0D:
        fields.append((data[p:p + 11].split(b"\0")[0].decode("ascii"), data[p + 16]))
        p += 32
    rows = []
    for i in range(nrec):
        rec, off, d = data[hlen + i * rlen:hlen + (i + 1) * rlen], 1, {}
        for name, ln in fields:
            d[name] = rec[off:off + ln].decode("utf-8", "replace").replace("\0", "").strip()      # fields are space or NUL padded
            off += ln
        rows.append(d)
    return rows


# ----------------------------------------------------------------------------- rings
def signed_area(r: np.ndarray) -> float:
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))


def quantise(r: np.ndarray) -> np.ndarray:
    """Ring as int32 (lon, lat) in 1e-4 degree, latitude held to the Mercator limit, consecutive duplicates removed, closed once."""
    q = np.empty(r.shape, np.int64)
    q[:, 0] = np.rint(r[:, 0] * Q)
    q[:, 1] = np.rint(np.clip(r[:, 1], -LAT_MAX, LAT_MAX) * Q)
    keep = np.ones(len(q), bool)
    keep[1:] = np.any(q[1:] != q[:-1], axis=1)
    q = q[keep]
    if len(q) > 1 and np.all(q[0] == q[-1]):
        q = q[:-1]                                  # stored open; the loader closes it
    return q.astype(np.int32)


def pack(rings, extra: dict | None = None) -> bytes:
    """Deterministic .npz bytes. `rings`: list of dicts {xy: int32 (n, 2), hole: bool, aux: int} in draw order."""
    off = np.zeros(len(rings) + 1, np.int64)
    for i, r in enumerate(rings):
        off[i + 1] = off[i] + len(r["xy"])
    xy = np.concatenate([r["xy"] for r in rings]).astype(np.int64)
    d = np.diff(xy, axis=0, prepend=xy[:1] * 0)
    d[off[:-1]] = xy[off[:-1]]                                  # each ring starts with its absolute position
    # a ring start can exceed int16: keep the starts apart (int32) and the steps in the smallest type that holds them
    starts = d[off[:-1]].astype(np.int32)
    steps = d.copy()
    steps[off[:-1]] = 0
    step_t = np.int16 if np.abs(steps).max() < 32768 else np.int32
    arrays = {
        "q": np.array([Q], np.float64), "off": off.astype(np.int32), "start": starts, "step": steps.astype(step_t),
        "hole": np.array([r["hole"] for r in rings], np.uint8), "aux": np.array([r.get("aux", 0) for r in rings], np.int16),
    }
    if any("coast" in r for r in rings):
        arrays["coast"] = np.concatenate([r["coast"] for r in rings]).astype(np.uint8)       # per vertex: 1 = the edge to the next vertex is coast
    arrays.update(extra or {})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(arrays):
            b = io.BytesIO()
            np.lib.format.write_array(b, np.ascontiguousarray(arrays[name]), allow_pickle=False)
            zi = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type, zi.external_attr = zipfile.ZIP_DEFLATED, 0o600 << 16
            z.writestr(zi, b.getvalue(), compresslevel=9)
    return buf.getvalue()


def coast_flags(q: np.ndarray) -> np.ndarray:
    """Per vertex of the open ring `q` (int32): 1 when the edge to the next vertex (cyclic) is a coast, 0 when it only cuts the
    world (both ends on the antimeridian, or both at the southern limit)."""
    n = len(q)
    nxt = np.roll(q, -1, axis=0)
    lim = int(round(180 * Q)) - 2
    cut = ((np.abs(q[:, 0]) >= lim) & (np.abs(nxt[:, 0]) >= lim) & (np.sign(q[:, 0]) == np.sign(nxt[:, 0]))) \
        | ((q[:, 1] <= -int(LAT_MAX * Q) + 2) & (nxt[:, 1] <= -int(LAT_MAX * Q) + 2))
    return (~cut).astype(np.uint8) if n else np.zeros(0, np.uint8)


def build_land(shp: bytes):
    items = []
    for _rec, rings in read_shp(shp):
        for r in rings:
            if len(r) < 4:
                continue
            a = signed_area(r)                                  # shapefile: clockwise = outer ring (negative area), counter-clockwise = hole
            q = quantise(r)
            if len(q) < 3:
                continue
            items.append((abs(a), a > 0, q))
    items.sort(key=lambda t: -t[0])                             # a ring that contains another is always bigger: big first draws holes right
    return [{"xy": q, "hole": hole, "coast": coast_flags(q)} for _a, hole, q in items]


def build_countries(shp: bytes, dbf: bytes):
    rows = read_dbf(dbf)
    recs = {n + 1: row for n, row in enumerate(rows)}
    iso, names, index = [], [], {}
    items = []
    for rec_no, rings in read_shp(shp):
        row = recs[rec_no]
        code = row.get("ISO_A2_EH", "") if row.get("ISO_A2_EH", "-99") not in ("-99", "") else row.get("ISO_A2", "")
        if code in ("-99", ""):
            continue                                            # disputed or unassigned territories carry no code
        if code not in index:
            index[code] = len(iso)
            iso.append(code)
            names.append(row.get("NAME", code))
        for r in rings:
            if len(r) < 4:
                continue
            a = signed_area(r)
            q = quantise(r)
            if len(q) >= 3:
                items.append((abs(a), a > 0, q, index[code]))
    items.sort(key=lambda t: -t[0])
    rings = [{"xy": q, "hole": hole, "aux": ci} for _a, hole, q, ci in items]
    return rings, {"iso": np.array(iso, "U2"), "name": np.array(names, "U60")}


def pole(rings, step=0.25):
    """Pole of inaccessibility of a polygon (outer rings and holes, degrees) on a grid of `step` degrees: the cell furthest from an edge."""
    pts = np.concatenate(rings)
    x0, y0 = pts[:, 0].min(), pts[:, 1].min()
    w, h = int(math.ceil((pts[:, 0].max() - x0) / step)) + 3, int(math.ceil((pts[:, 1].max() - y0) / step)) + 3
    m = np.zeros((h, w), np.uint8)
    for r in rings:
        p = np.rint((r - [x0, y0]) / step + 1).astype(np.int32)
        cv2.fillPoly(m, [p], 255) if signed_area(r) <= 0 else cv2.fillPoly(m, [p], 0)
    d = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    j, i = np.unravel_index(int(np.argmax(d)), d.shape)
    return float(x0 + (i - 1 + 0.5) * step), float(y0 + (j - 1 + 0.5) * step)


def build_seas(shp: bytes, dbf: bytes):
    rows = read_dbf(dbf)
    out, seen = [], set()
    for rec_no, rings in read_shp(shp):
        row = rows[rec_no - 1]
        cls, rank = row.get("featurecla", ""), int(row.get("scalerank") or 9)
        raw = row.get("name", "")
        name = (raw.title() if raw.isupper() else raw) if cls == "ocean" else (row.get("name_en") or raw)       # the two Atlantics and Pacifics keep their own names
        if cls not in KEEP_CLASSES or rank > MAX_RANK or not name or name in seen:
            continue
        seen.add(name)
        allp = np.concatenate(rings)
        lat_mid = float(np.clip(allp[:, 1].mean(), -80, 80))
        lons = allp[:, 0] % 360.0 if np.ptp(allp[:, 0]) > 180 else allp[:, 0]        # a sea that crosses the antimeridian is measured on the 0..360 circle
        ext_x = np.ptp(lons) * 111.32 * math.cos(math.radians(lat_mid))
        ext_y = (allp[:, 1].max() - allp[:, 1].min()) * 110.57
        ext = float(max(ext_x, ext_y))
        lon, lat = LABEL_AT[name] if name in LABEL_AT else pole(rings)
        nm = {"Gulf of Saint Lawrence": "Gulf of St. Lawrence"}.get(name.strip(), name.strip())
        out.append({"name": nm, "lon": round(lon, 2), "lat": round(lat, 2), "rank": rank, "extent_km": int(round(ext, -1))})
    out.sort(key=lambda s: (s["rank"], -s["extent_km"], s["name"]))
    return out


# ----------------------------------------------------------------------------- main
def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for stem, (rel, _what) in SOURCES.items():
        req = urllib.request.Request(BASE + rel, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as r:
            (dest / (stem + ".zip")).write_bytes(r.read())
        print("downloaded", BASE + rel)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--downloads", required=True, type=Path, help="folder with the Natural Earth zip files")
    ap.add_argument("--fetch", action="store_true", help="download the zip files into --downloads first")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "style" / "gae" / "geo")
    a = ap.parse_args(argv)
    if a.fetch:
        fetch(a.downloads)
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = {"source": "Natural Earth (public domain)", "sources": [], "files": []}
    data = {}
    for stem, (rel, what) in SOURCES.items():
        zp = a.downloads / (stem + ".zip")
        shp, dbf, version = read_zip(zp, stem)
        data[stem] = (shp, dbf)
        manifest["sources"].append({"name": stem + ".zip", "url": BASE + rel, "version": version, "bytes": zp.stat().st_size,
                                    "sha256": sha256(zp.read_bytes()), "used_for": what})
    files = {}
    for res in ("50m", "10m"):
        rings = build_land(data["ne_%s_land" % res][0])
        files["land_%s.npz" % res] = (pack(rings), {"rings": len(rings), "vertices": int(sum(len(r["xy"]) for r in rings))})
    crings, extra = build_countries(*data["ne_50m_admin_0_countries"])
    files["countries_50m.npz"] = (pack(crings, extra), {"rings": len(crings), "vertices": int(sum(len(r["xy"]) for r in crings)), "countries": len(extra["iso"])})
    seas = build_seas(*data["ne_50m_geography_marine_polys"])
    files["seas.json"] = (json.dumps({"note": "Sea and ocean names, English, from Natural Earth marine polygons; position lon, lat in degrees; "
                                      "extent_km: the longer side of the sea's bounding box; rank: Natural Earth scalerank (0 = ocean).",
                                      "seas": seas}, ensure_ascii=False, indent=0, separators=(",", ":")).encode("utf-8") + b"\n", {"names": len(seas)})
    for name, (blob, info) in files.items():
        (a.out / name).write_bytes(blob)
        manifest["files"].append(dict({"name": name, "bytes": len(blob), "sha256": sha256(blob)}, **info))
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    total = sum(f["bytes"] for f in manifest["files"])
    for f in manifest["files"]:
        print("%-20s %9d bytes  %s  %s" % (f["name"], f["bytes"], f["sha256"], {k: v for k, v in f.items() if k not in ("name", "bytes", "sha256")}))
    print("total", total, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
