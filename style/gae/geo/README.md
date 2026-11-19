# Geography bundle of `MAP-01`

What the atlas map draws, taken from Natural Earth (https://www.naturalearthdata.com), stored compactly in the repository and read once per
process (`bti/engine/geo.py`). Nothing is downloaded while a frame is drawn. Nothing else is bundled: no raster, no relief, no rivers or lakes, no
borders between countries, no cities. Contract: `docs/design/2026-11-18-explainer-components.md` section 6.

## Licence

Natural Earth's terms of use (https://www.naturalearthdata.com/about/terms-of-use/), read on 2026-11-18:

> All versions of Natural Earth raster + vector map data found on this website are in the public domain. You may use the maps in any manner,
> including modifying the content and design, electronic dissemination, and offset printing. The primary authors, Tom Patterson and Nathaniel
> Vaughn Kelso, and all other contributors renounce all financial claim to the maps and invites you to use them for personal, educational, and
> commercial purposes. No permission is needed to use Natural Earth. Crediting the authors is unnecessary.

The terms add that anyone who wishes to cite the data may write "Made with Natural Earth".

## Sources (the downloads, from Natural Earth's own distribution on naciscdn.org)

| Download | URL | Natural Earth version | Bytes | sha256 | Used for |
|---|---|---|---|---|---|
| `ne_10m_land.zip` | https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip | 5.1.1 | 3269070 | `e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc` | land and coastline, 1:10m |
| `ne_50m_land.zip` | https://naciscdn.org/naturalearth/50m/physical/ne_50m_land.zip | 4.1.0 | 457183 | `0b8e670cf80dce9cbebe2a193bc44ba5602758c22e1fa603980553646d7ff162` | land and coastline, 1:50m |
| `ne_50m_admin_0_countries.zip` | https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip | 5.1.1 | 799734 | `5fed433373581fa648920435f937d95f2d3c0200e067409c6478dcdf1b853139` | countries with ISO codes, 1:50m |
| `ne_50m_geography_marine_polys.zip` | https://naciscdn.org/naturalearth/50m/physical/ne_50m_geography_marine_polys.zip | 5.1.0 | 700610 | `9e460b9fe2566d3f466d69096348953f5348bab63ce1328c94c3072b9f48eef1` | sea and ocean names |

The zip files are not kept in the repository (public domain, free to fetch again). `tools/geo/build_bundle.py --downloads DIR --fetch` downloads them
into `DIR` and rebuilds the bundle; the same downloads always give byte-identical files (zip entries carry a fixed date), so the hashes below can be checked.

## Stored files (2,071,791 bytes in all)

| File | Bytes | sha256 (as stored) | Content |
|---|---|---|---|
| `land_50m.npz` | 254697 | `c933b25e8c1e7287ec6d9df5ac22e957b67c7504d9b8389f3f22b7ef59296236` | rings 1422, vertices 59239 |
| `land_10m.npz` | 1359537 | `798ee3bdedb8824656259fdb466a4da577e1802b1ffb632b2afb411e5e8da2b0` | rings 6838, vertices 439317 |
| `countries_50m.npz` | 413130 | `20917462d9b4962db93cc1710e3d25c700ef793af4ca2d239e8c3f5fe6ed0eb2` | rings 1629, vertices 97832, countries 237 |
| `seas.json` | 44427 | `718e57af6d0ec2765aa99e8d88ae9f746477d087c5478912c8302bd5252d839b` | names 113 |

`manifest.json` holds the same numbers (a test compares them with the files and with this README).

### Format

`*.npz` are zip files of `.npy` arrays, readable with `numpy.load`: `q` (the quantisation, 1e4 steps per degree), `off` (where each ring starts in the
vertex arrays), `start` (the first vertex of each ring, int32), `step` (the other vertices as steps from the previous one, int16 or int32), `hole` (a
ring that cuts a hole), `aux` (countries: the index of the country in `iso` and `name`), `coast` (land: per vertex, 1 when the edge to the next vertex is a
coast and not a cut of the world). Rings are in draw order: the biggest first, so a hole is always drawn after the ring that contains it.
Longitudes are -180 to 180; latitudes are held to the Web Mercator limit (85.0511 degrees), which only touches Antarctica.

* `land_50m.npz`, `land_10m.npz`: the land polygons at 1:50m and 1:10m. `MAP-01` draws the finer one for views narrower than 1,500 km. The coastline
  (hairline, water lines, shade) is made from the same rings, minus the edges that only cut the world at the antimeridian and at the southern limit, so the
  line can never disagree with the fill. The separately distributed coastline downloads are not bundled: the 1:10m coastline is version 5.0.0-pre9 and the
  1:10m land is version 5.1.1, which would differ at the coast.
* `countries_50m.npz`: the countries at 1:50m with their ISO 3166-1 alpha-2 codes (`ISO_A2_EH`, which gives France and Norway their codes; territories
  without a code are left out) and their names; `region_iso` of the technique reads it.
* `seas.json`: 113 names of oceans, seas, gulfs, bays, straits and channels (Natural Earth marine polygons, scale rank 0 to 4),
  each with a position (longitude, latitude), its rank, its extent in km and its outline (`poly`: the outlines of the sea simplified to 0.3 degree, flat lists of integers
  in tenths of a degree; the engine uses them only to keep a sea's name inside its own sea). The position is the pole of inaccessibility of the polygon, except for the
  seas listed in `LABEL_AT` of the build script, which have hand-placed positions (the four of the approved mock-up, and the other seas a plate names).

## What is not in it

Lakes, rivers, relief, borders between countries, populated places, historical borders. A view narrower than about 60 km shows 1:10m outlines, which are
coarse at that scale: the engine cuts the corners of outlines whose segments are longer than 8 px (`maps.chaikin`), it does not add detail.
