"""Prepare the geography of the map mock-ups from Natural Earth (public domain): land, borders, Belgium, relief, a globe mask.
Frame 1920x1080, Web Mercator, start view 3,800 km wide centred 6.86 E 47.66 N (the numbers of research report R10, part 3)."""
import json, math, os, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, MultiPolygon, LineString, box, shape
from shapely.ops import unary_union

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
GEO = HERE / "geo"
OUT = HERE / "site"
OUT.mkdir(exist_ok=True)

LON0, LAT0 = 6.86, 47.66
R_KM = 6371.0
W, H = 1920, 1080
S = W / (3800.0 / (R_KM * math.cos(math.radians(LAT0))))        # px per radian of longitude at the start view
MX, MY = 0.30, 0.45                                               # margin around the frame, as a fraction of it (room for push and tilt)
X0, X1, Y0, Y1 = -MX * W, (1 + MX) * W, -MY * H, (1 + 0.25) * H


def merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def px(lon, lat):
    return (W / 2 + math.radians(lon - LON0) * S, H / 2 - (merc(lat) - merc(LAT0)) * S)


def inv(x, y):
    lon = LON0 + math.degrees((x - W / 2) / S)
    m = merc(LAT0) - (y - H / 2) / S
    lat = math.degrees(2 * math.atan(math.exp(m)) - math.pi / 2)
    return lon, lat


LON_A, LAT_B = inv(X0, Y1)
LON_B, LAT_A = inv(X1, Y0)
BBOX = box(LON_A - 1, LAT_B - 1, LON_B + 1, min(LAT_A + 1, 84))
print("view box lon %.1f..%.1f lat %.1f..%.1f, scale %.1f px/rad" % (LON_A, LON_B, LAT_B, LAT_A, S))


def topo_arcs(t):
    sc, tr = t["transform"]["scale"], t["transform"]["translate"]
    out = []
    for arc in t["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        out.append(pts)
    return out


def ring(arcs, idxs):
    pts = []
    for i in idxs:
        a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        pts.extend(a if not pts else a[1:])
    return pts


def geom_polys(arcs, g):
    polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
    out = []
    for p in polys:
        rings = [ring(arcs, r) for r in p]
        if len(rings[0]) >= 4:
            try:
                poly = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 4])
                if not poly.is_valid:
                    poly = poly.buffer(0)
                out.append(poly)
            except Exception:
                pass
    return out


def path_of(geom, tol=0.45, close=True):
    """SVG path data in frame pixels of a lon/lat geometry (already clipped)."""
    parts = []
    def one(coords, closed):
        pts = [px(lon, lat) for lon, lat in coords]
        ls = LineString(pts).simplify(tol, preserve_topology=False)
        c = list(ls.coords)
        if len(c) < (4 if closed else 2):
            return
        parts.append("M" + "L".join("%.1f,%.1f" % p for p in (c[:-1] if closed else c)) + ("Z" if closed else ""))
    def walk(g):
        if g.is_empty:
            return
        if g.geom_type == "Polygon":
            one(g.exterior.coords, True)
            for i in g.interiors:
                one(i.coords, True)
        elif g.geom_type == "LineString":
            one(g.coords, False)
        elif hasattr(g, "geoms"):
            for x in g.geoms:
                walk(x)
    walk(geom)
    return "".join(parts)


land_t = json.load(open(GEO / "land-50m.json"))
la = topo_arcs(land_t)
land = []
for g in land_t["objects"]["land"]["geometries"]:
    land.extend(geom_polys(la, g))
land_clip = unary_union([p.intersection(BBOX) for p in land if p.intersects(BBOX)])
LAND = path_of(land_clip)

ct = json.load(open(GEO / "countries-50m.json"))
ca = topo_arcs(ct)
use = {}
def count(a):
    if isinstance(a, int):
        k = a if a >= 0 else ~a
        use[k] = use.get(k, 0) + 1
    else:
        for x in a:
            count(x)
belgium = None
for g in ct["objects"]["countries"]["geometries"]:
    count(g.get("arcs", []))
    if str(g.get("id")) == "056":
        belgium = unary_union(geom_polys(ca, g))
lines = []
for k, n in use.items():
    if n >= 2:
        ls = LineString(ca[k])
        if ls.intersects(BBOX):
            lines.append(ls.intersection(BBOX))
BORDERS = path_of(unary_union(lines), tol=0.5, close=False)
BELGIUM = path_of(belgium)

bruges, lucca = px(3.2247, 51.2093), px(10.5027, 43.8429)
via = [px(5.5, 48.8), px(7.6, 46.0)]
grat = {"v": [round(px(lon, 0)[0], 1) for lon in range(-40, 61, 5)], "h": [round(px(0, lat)[1], 1) for lat in range(25, 71, 5)]}
labels = {  # sea and region names for the plate look: [text, x, y]
    "sea": [["NORTH SEA", *px(3.0, 55.6)], ["BAY OF BISCAY", *px(-4.6, 45.3)], ["MEDITERRANEAN SEA", *px(5.0, 40.6)], ["ADRIATIC", *px(15.0, 43.2)]],
}
js = "window.GEO=" + json.dumps({
    "frame": [W, H], "extent": [X0, Y0, X1, Y1], "land": LAND, "borders": BORDERS, "belgium": BELGIUM,
    "bruges": [round(v, 1) for v in bruges], "lucca": [round(v, 1) for v in lucca], "via": [[round(v, 1) for v in p] for p in via],
    "grat": grat, "labels": {k: [[t, round(x, 1), round(y, 1)] for t, x, y in v] for k, v in labels.items()},
    "center": [LON0, LAT0]}, separators=(",", ":")) + ";"
(OUT / "geo.js").write_text(js)
print("geo.js %.0f KB; land %d chars, borders %d, belgium %d; Bruges %s Lucca %s" % (len(js) / 1024, len(LAND), len(BORDERS), len(BELGIUM), bruges, lucca))

# ---- relief: Natural Earth shaded relief (plate carree) -> Mercator, the same extent as the vector data
src = Image.open(GEO / "SR_LR.tif")
sw, sh = src.size
RW = 2160                                                     # stored at 0.75 px per frame px
k = RW / (X1 - X0)
RH = round((Y1 - Y0) * k)
xs = (np.arange(RW) + 0.5) / k + X0
ys = (np.arange(RH) + 0.5) / k + Y0
lon = LON0 + np.degrees((xs - W / 2) / S)
m = merc(LAT0) - (ys - H / 2) / S
lat = np.degrees(2 * np.arctan(np.exp(m)) - math.pi / 2)
sx = ((lon + 180.0) / 360.0 * sw)
sy = ((90.0 - lat) / 180.0 * sh)
x_lo, x_hi = int(max(0, math.floor(sx.min()) - 2)), int(min(sw, math.ceil(sx.max()) + 2))
y_lo, y_hi = int(max(0, math.floor(sy.min()) - 2)), int(min(sh, math.ceil(sy.max()) + 2))
crop = np.asarray(src.crop((x_lo, y_lo, x_hi, y_hi)), dtype=np.float32)
import cv2
mapx = np.tile((sx - x_lo).astype(np.float32), (RH, 1))
mapy = np.tile((sy - y_lo).astype(np.float32)[:, None], (1, RW))
rel = cv2.remap(crop, mapx, mapy, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
lo, hi = np.percentile(rel, 1), np.percentile(rel, 99.5)
rel = np.clip((rel - lo) / (hi - lo), 0, 1)
rel = cv2.GaussianBlur(rel, (0, 0), 0.6)
Image.fromarray((rel * 255).astype(np.uint8)).save(OUT / "relief.jpg", quality=80, optimize=True)
print("relief.jpg", (RW, RH), os.path.getsize(OUT / "relief.jpg") // 1024, "KB; source crop", crop.shape)

# ---- globe mask: equirectangular land, 1 = land (for the orthographic globe of the cut-paper look)
g110 = json.load(open(GEO / "land-110m.json"))
ga = topo_arcs(g110)
MW, MH = 1440, 720
mask = Image.new("L", (MW, MH), 0)
d = ImageDraw.Draw(mask)
for g in g110["objects"]["land"]["geometries"]:
    for p in geom_polys(ga, g):
        polys = p.geoms if hasattr(p, "geoms") else [p]
        for q in polys:
            d.polygon([((lo_ + 180) / 360 * MW, (90 - la_) / 180 * MH) for lo_, la_ in q.exterior.coords], fill=255)
            for i in q.interiors:
                d.polygon([((lo_ + 180) / 360 * MW, (90 - la_) / 180 * MH) for lo_, la_ in i.coords], fill=0)
mask.save(OUT / "landmask.png", optimize=True)
print("landmask.png", os.path.getsize(OUT / "landmask.png") // 1024, "KB")
