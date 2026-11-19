# FIX: Commons imports take standard-width renditions; an OpenStreetMap import never draws a default city or serves a wrong cached map (worker mediafix3)

Brief: `.scratch/agy_tasks/mediafix3/TASK.md`. Background: `docs/qa/FIX_media_size.md`, `docs/qa/FIX_size_follow.md`. Line numbers are the
files at commit 92bd7fd (before this work) unless said otherwise. The real requests I made are in 1.5 and 2.4.

---------------------------------------------------------------------------------------------------------------------------------

## Part 1. Commons: renditions at standard widths instead of originals

### 1.1 Cause (found in the code first)

`bti/media/sources/commons.py` `download` (lines 185-203 at 92bd7fd) asked the API for a rendition only when the original was
"too big": longest side over 6000 px AND over 25 MP, or over 40 MB. Every other image (a 3048 x 4000 painting is 12 MP and 2 MB) went
to `http.download_file(meta["url"], ...)`, the original on `upload.wikimedia.org`, which Wikimedia has refused to this server for hours
(HTTP 429, `Retry-After: 120`; a HEAD of the same address answers 200). The renditions Wikimedia serves normally (the `thumburl` of the
API, standard widths `THUMB_STEPS`) were never used for them. The polite client (`bti/media/http.py`: one short retry, the host
cooldown, the wait time reported) worked as designed: it stopped, but nothing it could do would have produced the file.

### 1.2 The rule as built (`bti/media/sources/commons.py`)

`rendition_target(w, h, size)` decides; `CommonsSource.download` follows it.

| Original | What is downloaded |
|---|---|
| width at least 1920 px, and some standard width W (1920 or 3840) is not wider than the original and keeps the picture within the app's limits (longest side <= 6000 px OR <= 25 MP, the same two limits as before) | the **rendition of the largest such W**: 3048 x 4000 gives 1920 (1920 x 2520); 3870 x 3042 gives 3840; 6703 x 8322 gives 3840 (as today); 5000 x 8000 gives 3840; 2400 x 1800 gives 1920 |
| narrower than 1920 px | the **original**. If the source refuses it with "too many requests" the **largest standard width below the original** is asked for instead (one API call and one download of the rendition), but only when that rendition's short side passes the size floor given to `download` (`min_short_side`); otherwise the refusal is raised as before (`MediaHTTPError`, `rate_limited`, `retry_after`; the pages show `source_rate_limited` with the wait). Any failure of that second attempt also raises the ORIGINAL refusal, so the wait time shown is the one the source gave for the original |
| exactly a standard width (1920 x 1080, 3840 x 2160) | the **original** (no API call: the rendition would be the original, and MediaWiki answers the original's own address for it). Refused as "too many requests" it falls back like a narrow original (1280 for a 1920 wide one) |
| heavy (over 40 MB) or over 25 MP with a side over 6000, and no width of 1920 or more fits (for example 2500 x 30000, or a 1300 x 1250 file of 48 MB) | as before: the largest standard width below the original (1280 for both examples) |
| unknown size | the original, unless the declared bytes exceed 40 MB (then 3840, as before) |
| `thumburl` of the API equal to the original's address, or no `thumburl` | not a rendition: the original is downloaded (the 60 MB cap check applies, as before) |
| a file that is not an image (`kind` video or other: webm, ogv, pdf ...) | never a rendition, always the original, as before |

Size floor (`min_short_side`, default 1200 px; the facade passes 0 and only flags): checked **before any request, on the file that will be
stored** (the rendition's size, `expected_size`), not on the original. 3048 x 4000 passes a floor of 1920 and fails 1921, with nothing
requested. Consequence of reading the brief literally, to be aware of: an original just over the floor whose standard rendition falls
under it (2000 x 1200 gives 1920 x 1152) is judged on 1152: with a floor of 1200 `download` refuses it with `ImageTooSmall` ("1920x1152 px
would be stored (the original is 2000x1200)"), and through the facade (floor 0, flag only) the asset gets the "Ảnh nhỏ" flag.

Other decisions I had to make (each has a test):
- **Hosts and cooldown.** `bti/media/http.py` keys the "wait" cooldown by hostname (`_COOLDOWN[host]`) for every source: nothing
  Wikimedia-specific, and not on purpose "one host". The refusal of the original (`upload.wikimedia.org`) therefore does not put the
  rendition host (`thumb.wikimedia.org`, as measured; the MediaWiki API host is a third one) into cooldown, and the other way round. I left
  it as it is. If the API ever answered a rendition address on the SAME host as the refused original, the cooldown (a host that said "wait"
  gets nothing) would hold the fallback back and the original refusal is what is reported; a test documents that.
- **No new retries.** The original is asked for at most as often as before (one request for `Retry-After` over 5 s, two for a short one:
  waited once, then stop); the fallback is one different address, once.
- **The old `rendition_width` and its table are unchanged** (still "strictly smaller than the original"); `rendition_target` calls it for the
  heavy/too-big cases.
- **Format of a rendition.** A rendition can be another format than its original (Wikimedia gives a JPEG for a TIFF and a PNG for an SVG:
  `...tif.jpg`, `...svg.png`). The facade named the file after the ORIGINAL's extension, so a JPEG would have been stored as `x.tif`
  (served as `image/tiff`, which browsers do not show). `download` now writes beside `dest` with the extension of the rendition's own
  address when it differs (jpg/jpeg and tif/tiff count as equal) and returns that path; `api._import` uses the returned path. I could not
  check the exact real name Wikimedia gives a TIFF rendition (not requested), the rule only looks at the extension of the address it gets.
- **Search cards.** `api.search` now asks the source for `stored_size(meta)` (Commons only; other sources unchanged) and the card's
  `width`/`height` and "small" flag are those of the file an import will store (1920 x 2520), not of the original (3048 x 4000). Before this
  the card said a size the stored file does not have, and the card of an already imported item still said so after the import.
- **Old-index hole, same family**: none for Commons (the index holds the measured asset).

### 1.3 What the page shows (checked, no page change needed)

`picks.js` shows the size in two places: an asset card of the project (`L.sizeText(a.width, a.height)`, line 128: the asset record, which is
the stored file's pixels since `FIX_media_size.md`) and a search card (`L.sizeText(c.width, c.height)`, line 299: the candidate, which is now
the stored size for Commons). A test through the real routes shows card (before the import) = asset (after) = the file's own pixels
(`tests/picks/test_media_sources.py::test_a_commons_import_stores_the_rendition_and_the_card_shows_the_stored_size`). The older "Hình" tab
of the storyboard (`media.js` line 66) reads the asset's width/height too. A browser was not opened.

### 1.4 Tests

New (fakes only, no request leaves a test):
- `tests/media/test_commons_rendition.py` (61 tests): the `rendition_target` table (3048 x 4000 to 1920; 3870 x 3042, 6703 x 8322, 5000 x 8000 to 3840;
  2400 x 1800 and 1921 x 1200 to 1920; 1920 x 1080 and 3840 x 2160 exact: the original; 1919 wide, 1800 x 2400, 1500 x 1300, 1280 x 720: the
  original; heavy narrow 1300 x 1250 and heavy exact 3840 x 2160; 2500 x 30000; unknown sizes) and the limits for every size; `expected_size`;
  the owner's file end to end (the original answers 429, the original is never requested, only `iiurlwidth=1920` and its rendition);
  the width asked for per size; narrow and exact-width originals with no API call; `thumburl` equal to the original or missing; video, pdf and
  ogg never get a rendition; the floor on the stored size (1920 passes, 1921 fails, nothing requested; 2000 x 1200 refused as 1920 x 1152;
  an 800 x 600 original refused with no request); the 429 fallback (largest width below, once; floor failing; no address; fallback refused
  too reports the ORIGINAL's 120 s; no wait time; only a rate limit triggers it; a refused rendition is not retried as the original);
  the polite client unchanged (`Retry-After: 3`: waited once, original asked twice and never more); the host cooldown (only
  `upload.wikimedia.org` is held, a rendition and another file's rendition are served meanwhile, an original inside the wait is not even
  sent; a rendition on the same host waits too); a TIFF original comes as `.jpg`; and through the facade: stored size and original size
  recorded (1920 x 2520 / 3048 x 4000, `stored_image_size` agrees, no second download), the "small" flag judged on the stored file, the
  search card's size equals the asset's after the import, a narrow card keeps its own size, a `.tif` stored as `.jpg`, a refusal leaves nothing
  in `media/`.
- `tests/picks/test_media_sources.py` (2 of its 4 tests are Commons): through the real routes, card (before) = asset (after) = the file's pixels
  = the page's `picks.assets[...]` entry, and a refused original with no way round is `503 source_rate_limited, retry_after 120`.
Existing tests changed because they encoded the old behaviour (each marked CHANGED): `tests/media/test_api.py` fixture `commons_net` and
`tests/picks/test_api.py` `commons_net` (the 4386 x 6000 Arnolfini is now fetched as the rendition its API answer names, so that address is
served), `tests/media/test_commons.py::test_download_size_cap` (a 3000 x 3000 original is now a rendition, so the up-front cap check moved
to a 1500 x 1500 file).

**Fail without the fix** (the HEAD versions of `commons.py`, `osm.py`, `api.py`, `errors.py` put back for one run, then restored): of the
two new media files, 71 of 89 fail (44 of 61 here, 27 of 28 for OSM); the 17 Commons tests that still pass are the "unchanged rule" guards (a
narrow or exact-width original is the original, a video is never scaled, the fallback with no way round re-raises the 429, a 403/404/500 is not
a rate limit, 6703 x 8322 and 5000 x 8000 already gave 3840, the floor of an 800 x 600 file). In `tests/picks/test_media_sources.py` 3 of 4 fail
(the passing one is the unchanged 429 answer).

### 1.5 Real requests (4 of the 4 allowed, from my snapshot `mediafix3` on the server, User-Agent `behind-the-image-media/0.1 (art documentary research tool)`)

Script `.scratch/mediafix3/real_commons.py`, output `.scratch/mediafix3/real_commons.out`. One API call (a search with `iiurlwidth=1920`
for "Edvard Munch Self-Portrait with Cigarette NG.M.00470", 50 results, which gives the rendition address of every result at once) and
then the real `CommonsSource.download` for three public-domain files; the app's own rendition-address lookups for those three were answered
from that one real API answer, so the budget held. Gaps between real requests: at least 32 s. No original was requested.

| # | Request | Answer |
|---|---|---|
| 1 | `GET commons.wikimedia.org/w/api.php?...generator=search...iiurlwidth=1920` | HTTP 200 JSON, 10 files, 836 ms |
| 2 | `GET thumb.wikimedia.org/.../1920px-Edvard_Munch_-_Self-Portrait_with_Cigarette_-_NG.M.00470_...jpg?utm_source=...` (the owner's file, original 3048 x 4000) | HTTP 200 `image/jpeg`, 2 008 814 bytes, 255 ms; stored 1920 x 2520 JPEG = `expected_size` |
| 3 | `GET thumb.wikimedia.org/.../1920px-Munch_SelfBurningCigarette.jpg` (3058 x 4000) | HTTP 200, 1 940 316 bytes; stored 1920 x 2511 = `expected_size` |
| 4 | `GET thumb.wikimedia.org/.../1920px-Edvard_munch,_autoritratto_con_sigaretta,_1895,_01.jpg` (3296 x 3968) | HTTP 200, 971 365 bytes; stored 1920 x 2311 = `expected_size` |

No refusal. What it shows: the API returns the rendition on `thumb.wikimedia.org` (the original on `upload.wikimedia.org`), the address
carries a query string (`?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail`, on the original's too), the
rendition is served 200 with the app's User-Agent, its pixel size equals the one the app computed beforehand, and all three files are
public domain. The three downloaded renditions are in my snapshot folder `run\snap-mediafix3\run_check_mediafix3\` on the server (not
deleted: removing a folder is the coordinator's call, `tools/deploy/snapshot_rm.sh mediafix3` removes the whole snapshot).

### 1.6 What I could not verify

- The real refusal of an original (forbidden by the brief), so the narrow-original fallback was tested with fakes only, never against the
  real 429; the same for the real name of a TIFF's or an SVG's rendition (`...tif.jpg`, `...svg.png`): the rule reads only the extension of the
  address the API gives.
- Browsers: the cards were checked through the routes and by reading `picks.js`, not in a mounted page.
- A search for a file whose original is 3840 or wider (rendition 3840, several MB): only the 1920 case was requested for real.
- Pixabay and Pexels cards still show the size their API reports for the original (their stored file is smaller); that is another source's
  rule and was not part of this brief.


---------------------------------------------------------------------------------------------------------------------------------

## Part 2. OpenStreetMap: an import after a restart drew the wrong city

### 2.1 Cause (found in the code first)

`bti/media/sources/osm.py` (92bd7fd):
- `search` (line 139+) put the place's coordinates (`_lat`, `_lon`, zoom) only in the meta it returned and in the in-memory table
  `self._meta_cache[sid]`; the source id given to the page was `place_id:zoom` (line 160), with no coordinates.
- The page and both import routes pass ONLY `source` and `source_id` from a card to the import (`picks.js` line 267 `{source, source_id, as_main}`;
  `picks_api.import_picks` 126; the older tab `media_adapter.import_candidate`), and the facade then calls `fetch_meta(source_id)`.
  After a restart (or in another process) `_meta_cache` is empty, so `fetch_meta` (line 188-215) rebuilt a meta from the id alone, with
  `_zoom` but **no `_lat`/`_lon`**.
- `download` (line 242-246): `if lat is None or lon is None: lat, lon = 51.0543, 3.7174` (the centre of Ghent) and then drew that map and
  saved it as `.cache/osm/<place_id>_z<zoom>.jpg` (line 236, 248). The cache name had no coordinates, so every later import of that place and
  zoom was served that file (line 238-240): the wrong city, for good, and the same wrong file for any other place that got the same name.
- Smaller causes of the same kind: `compose_map` skipped a tile that failed (`except Exception: pass`) and the map was cached with grey
  holes (and a tile server that had said "wait" was still asked for the other ~60 tiles); the place id of Nominatim is not a stable
  identity (it changes when Nominatim reloads its data), so it must not be the only key of a cache.

### 2.2 The rule as built

**How the import finds its place.** The coordinates travel in the source id. A search result's `source_id` is now
`place_id:zoom:lat:lon[:name]` (for example `297322:12:59.91333:10.73897:Oslo`; lat/lon rounded to 5 decimals, about 1 m; the name is the short
place name, percent-encoded, at most 40 characters and 150 once encoded so the id stays under the route's 300). The page and the routes already
pass the id unchanged, so **no page, route or adapter change was needed**; `fetch_meta` rebuilds the whole meta (title, page URL, centre, zoom)
from the id alone with no memory of a search (`parse_source_id`). I chose this over a lookup by OpenStreetMap id because it costs no request
at import, works whatever Nominatim does, needs no second field in the import request, and the id is already the item's identity in the
project's index; a lookup would be one more call to a server with a 1 request/second rule, would fail when Nominatim is down, and would have
had to carry `osm_type`/`osm_id` in the id anyway.

**No default centre, anywhere.** The Ghent coordinates are gone (a test scans every `.py` and `.js` under `bti/` for them). A map that cannot
be placed is the error `MapPlaceUnknown` (`bti/media/errors.py`): a `ValueError` with `code = "map_place_unknown"`, so both HTTP layers answer
**422 with that code**, and the page shows (errmsg.js, block "worker mediafix3"): "Không biết bản đồ này ở đâu nên không vẽ được. Hãy tìm lại
địa điểm rồi chọn lại." It is raised for: the old id form `place_id:zoom`, an empty id, a coordinate that is not a finite number, latitude
beyond +-85.0511 (the tile grid) or longitude beyond 180, a zoom outside 0..19, a place id with path characters. Nothing is requested and
nothing is written. A search result whose place cannot be drawn is not offered at all.

**The old index records.** `OsmSource.check_id` runs in the facade BEFORE the project's index is consulted, so a record kept under an old-form
id (which could be the wrong city) is not returned for that id either: a stale page that sends it gets the error above, not the old file.

**The cache can never serve a wrong map.** The cache file is `osm_2400x1350_z<zoom>_<lat>_<lon>.jpg` with the 5-decimal centre: its name is the
proof of what it was drawn for (I chose the name over a record beside the file: one file, nothing to get out of step). A file under any other
name is never looked at, so **the wrong file on the server's disk (`.cache/osm/<place_id>_z<zoom>.jpg`) is disarmed without deleting it**:
the same place is drawn again under its new name. Two places, two zooms or two centres 1 m apart or more never share a file. An empty file is
drawn again. A map is cached only when **every** tile arrived: the first tile that fails (refused, not an image) ends the map with its
error, so no grey-holed map is cached and a tile server that said "wait" is not asked for the rest (`compose_map` no longer swallows errors).

**Usage rules kept**: Nominatim <= 1 request/second and the generic User-Agent (the search only; an import no longer needs Nominatim at all),
one map per request, the same tile URLs and the same polite client (`bti.media.http`). The default cache folder is still `.cache/osm` relative to
the app's working folder (unchanged).

### 2.3 Tests

New (fakes only; the OSM fakes answer Nominatim and serve 256 px tiles, and record every URL):
- `tests/media/test_osm_place.py` (28 tests): a search result's id carries the coordinates and a source that never searched rebuilds the
  identical meta; **the incident**: search for Oslo in one source, import by id in a new source ("restart"): the tiles requested are those of
  Oslo's window and none is near Ghent, through the source and through the facade (asset title "Bản đồ Oslo", credit URL of Oslo, a second import
  of the same id costs no request); ids of a long Unicode name and the worst case (every character 9 long once encoded) stay under 300; a place
  that cannot be drawn (latitude 89.9, no coordinates, no result) is not offered; 13 kinds of id without a usable place (old form, empty, `nan`,
  `inf`, latitude 95, longitude 181, zoom 99 or -1 or 12.5, `../../x`, too few parts) give an exception with `code == "map_place_unknown"` from
  `fetch_meta` and from `download` (also for the meta the old `fetch_meta` produced) with no request and nothing written; the facade with an old-form
  id leaves nothing in the project, and **an index record kept under an old-form id is not returned**; no `51.0543` / `3.7174` in any `.py` or
  `.js` under `bti/`; the cache: the same centre and zoom is served (also for a centre that rounds to the same 5 decimals), another zoom, another
  centre 0.01 degree away and another place are drawn again and kept in four different files; **the wrong file the old code left
  (`<place_id>_z<zoom>.jpg`) is never served, the place is drawn again and the old file is still there**; an empty cache file is drawn again; a
  refused tile (429, `Retry-After: 120`) ends the map after the third request with the wait reported and no cache file, and a tile that is not an
  image does too.
- `tests/picks/test_media_sources.py` (2 OSM tests): through the real routes, search, "restart", import by the card's id: 200, title, 2400 x 1350,
  the tiles of Oslo, no Nominatim call; an old-form id is `422` with `code map_place_unknown`, no request, nothing in `media/`, no `picks.json`.
- `tests/editor/test_media_adapter_map.py` (2 tests): the older Hình-tab import route answers the same 422 and code.
- `tests/picks/sourcelimit.test.mjs` (1 test added): the Vietnamese sentence through `describeHttp`, `describeError` and `stageErrorText`.
Existing tests changed because they encoded the old behaviour (each marked CHANGED): `tests/media/test_safety_switch.py` (the cached-map case
and the facade id: the id carries its place, the cache file is named for it), `tests/media/test_stored_size.py::test_osm_map_is_measured_not_trusted`
(same).

Fail without the fix: see 1.4 (27 of the 28 OSM tests fail on the HEAD code, the one that passes counts requests of an unchanged search+download;
3 of 4 route tests; `tests/editor/test_media_adapter_map.py` was not run on the old code, it imports `MapPlaceUnknown`, which did not exist).

### 2.4 Real import (1 import, from my snapshot `mediafix3` on the server)

Script `.scratch/mediafix3/real_osm.py`, output `.scratch/mediafix3/real_osm.out`. One Nominatim search "Oslo"; then the import BY ID from a new
`OsmSource` that had never searched (a restart), through `api.import_candidate`, into a folder inside my snapshot; tiles paced 0.25 s apart by
the script (the code under test sends none of its own pause).
- Search: `GET nominatim.openstreetmap.org/search?q=Oslo&format=json&limit=1&addressdetails=1`: id `163704828:11:59.91333:10.73897:Oslo`,
  title "Bản đồ Oslo", zoom 11.
- Import: 60 tile requests to `tile.openstreetmap.org` in 69.7 s, all HTTP 200 (61 answers counting the search); tiles z=11, x 1080..1089, y 593..598
  around the centre tile (1085.1, 595.7) of Oslo: all inside the window. Asset `ban_do_oslo`, 2400 x 1350, credit "(c) OpenStreetMap contributors", ODbL,
  `https://www.openstreetmap.org/#map=11/59.9133/10.7390`. Cache file `osm_2400x1350_z11_59.91333_10.73897.jpg`.
- A second import of the same id: same asset, 0 requests. A third source asking for the same place and zoom: served from the cache, 0 requests.
- **The picture** (copied to the Mac as `.scratch/mediafix3/oslo_real.jpg` and looked at): it shows Oslo and the Oslofjord, with the labels
  Oslo, Lillestrøm, Sandvika, Asker, Drammen, Ski, Tyrifjorden, Østmarka, Nesoddtangen and Øyeren; it is not Ghent.
- Total real requests to OpenStreetMap: 1 Nominatim + 60 tiles.

### 2.5 Existing data and what I could not verify

- The owner's project has an asset titled as Oslo that is a map of Ghent, under the index key `osm:<place_id>:<zoom>`, and the server's
  `.cache/osm/<place_id>_z<zoom>.jpg` holds the same wrong picture. I did not read or touch either. After this change: the cache file is
  never looked at again (new names); a new search gives new-form ids, so importing Oslo again draws the right map as a NEW asset; the old
  asset stays in the picks until the owner removes it (nothing here replaces or deletes it). Clicking a card from a search page opened before the
  deploy (old-form id) gives the sentence above instead of the old asset.
- Not verified: the real page in a browser; a restart of the real app (the restart was simulated by a new source object, which is exactly
  what the cause was: no memory of the search); Nominatim answers for places other than Oslo; any real tile failure (tested with fakes).
- The default cache folder `.cache/osm` is relative to the app's working folder; I left that as it is.

---------------------------------------------------------------------------------------------------------------------------------

## Summary lines, exactly as printed (snapshot `mediafix3`; the JavaScript on the Mac)

```
tests/media   : ============================= 363 passed in 6.70s =============================
tests/picks   : ======================= 92 passed, 1 warning in 10.54s ========================
tests/editor  : ================= 480 passed, 1 warning in 410.23s (0:06:50) ==================
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
              : ℹ tests 311 / ℹ pass 310 / ℹ fail 0 / ℹ skipped 1
```
The skipped node test is the existing `ISSUE_CODES` template check, which needs `.venv/bin/python` (not on the Mac); it was skipped before my change.
Before my files the same commands gave tests/media 274, tests/picks 88, tests/editor 478, node 310; the counts above include my 89 + 4 + 2 + 1 new tests.

## Files changed

`bti/media/sources/commons.py`, `bti/media/sources/osm.py`, `bti/media/api.py` (search card size, `check_id` hook, path returned by `download`),
`bti/media/errors.py` (`MapPlaceUnknown`), `bti/editor/static/js/errmsg.js` (one sentence, block "worker mediafix3"), `docs/APP_GUIDE.md` (the
picture-size sentence of the "Chọn hình" part), tests listed above. Not changed: `picks.js`, `picks_api.py`, `media_adapter.py`, `bti/picks/service.py`
(the id carries everything and both layers already pass a `ValueError` with a `code` on).

## Needs another worker

Nothing blocks. Suggestions: the owner (or a worker with project access) removes the Ghent map from the Oslo project and imports Oslo again;
Pixabay/Pexels cards could show the stored size the way Commons cards now do (`stored_size` hook in `bti.media.api.search`).
