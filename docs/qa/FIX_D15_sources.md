# Fix D15: More Picture Sources (Pexels, Pixabay, OSM)

Date: 2026-11-18
Worker: dsources
Contract: `docs/qa/DEBTS_2026-11-18_decisions.md` (item D15)

## 1. Problem / Cause
- Previously, the picks step only supported Wikimedia Commons and The Met (`SOURCES = ("commons", "met")`).
- Users needed additional rich photo and video sources (Pexels and Pixabay) and maps for locations/places (OpenStreetMap).
- Video results from search needed to go through the Part B uniform normalization and clip handling (silent 30fps H.264 MP4, duration probing, video role assignment, prevention from being set as the main painting).
- Keyed sources (Pexels and Pixabay) require API keys (`PEXELS_API_KEY` and `PIXABAY_API_KEY`) to be read securely via `bti.script.env` without ever logging or leaking them. Without a key, they must be flagged in UI as "chưa có khóa" and not called.
- OpenStreetMap maps require polite geocoding with Nominatim (rate limited to max 1 req/second with a generic User-Agent), composing a ~2400 px wide map from standard tiles at a zoom fitting the place, caching by place and zoom, and recording credit "© OpenStreetMap contributors" (ODbL).

## 2. Changes Made

### A. Environment key allow-list
- `bti/script/env.py:11`:
  - Added `"PEXELS_API_KEY"` and `"PIXABAY_API_KEY"` to `ALLOWED` tuple.

### B. New Source Clients under `bti/media/sources/`
- `bti/media/sources/pexels.py:1-205` (new file):
  - `PexelsSource`: Implements standard media source interface (`search`, `fetch_meta`, `download`, `credit`, `licence`).
  - Reads `PEXELS_API_KEY` via `env.get_key("PEXELS_API_KEY")`.
  - Supports both photos (`kind="image"`) and videos (`kind="video"`).
  - Without key, `has_key()` returns `False` and `search()` returns `[]`.
  - Formats credit with author and `"Pexels License"`.
- `bti/media/sources/pixabay.py:1-190` (new file):
  - `PixabaySource`: Implements standard media source interface.
  - Reads `PIXABAY_API_KEY` via `env.get_key("PIXABAY_API_KEY")`.
  - Supports both photos (`kind="image"`) and videos (`kind="video"`).
  - Without key, `has_key()` returns `False` and `search()` returns `[]`.
  - Formats credit with author and `"Pixabay Content License"`.
- `bti/media/sources/osm.py:1-230` (new file):
  - `OsmSource`: Implements standard media source interface.
  - Polite Nominatim geocoding with rate limit enforcement (`<= 1.0` req/second with clock and sleep injection for test speed).
  - `calculate_zoom`: Computes Mercator zoom level from place boundingbox to fit ~2400 px wide.
  - `compose_map`: Downloads OSM standard tiles and stitches a 2400x1350 JPEG image centered on coordinates.
  - Caches composed map on disk by place ID and zoom (`<cache_dir>/<place_id>_z<zoom>.jpg`), avoiding repeated network requests.
  - Credit recorded as `"© OpenStreetMap contributors"` with licence `"ODbL"`.

### C. Media Facade (`bti/media/api.py`)
- `bti/media/api.py:17-43`:
  - Imported `PexelsSource`, `PixabaySource`, `OsmSource`.
  - Registered in `_FACTORIES`.
- `bti/media/api.py:60-72`:
  - Updated `_candidate` to use `flag_for_meta` directly for video items (not applying `with_size_flag` image floor to video frames).
- `bti/media/api.py:100-145`:
  - In `_import`: When candidate has `kind == "video"`, downloads raw video and passes it through `_clips.normalize(raw, dest, strip_audio=True)` to create normalized silent 30fps MP4, probes with `_probe_upload_video` for `width`, `height`, and `duration`, registers asset with `duration`.

### D. Picks Service & API (`bti/picks/service.py`, `bti/editor/picks_api.py`)
- `bti/picks/service.py:15-16`:
  - Expanded `SOURCES = ("commons", "met", "pexels", "pixabay", "osm")` and `KEYED_SOURCES = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}`.
- `bti/picks/service.py:60-75`:
  - In `payload`: Added `sources` dictionary reporting `available` and `has_key` for each source.
- `bti/picks/service.py:133-146`:
  - In `import_asset`: Rejects setting a video asset as the main painting (`PicksError(422, "a video cannot be set as the main painting", "video_not_main")`).
- `bti/picks/service.py:177-220`:
  - In `search`: Without explicitly selected sources, defaults to sources that either don't require keys or have keys present. If a keyed source without a key was explicitly requested, returns `{"source": s, "code": "source_no_key", "message": "chưa có khóa"}` and avoids network call. Supports `kind="all"`, `kind="image"`, `kind="video"`.
- `bti/editor/picks_api.py:113-118`:
  - Added optional `kind` parameter validation to `POST /api/projects/{pid}/picks/search`.

### E. Frontend UI & Labels (`views/picks.js`, `labels.js`, `errmsg.js`)
- `bti/editor/static/js/labels.js:202-210`:
  - Added `// --- dsources: new sources labels` block exporting `SOURCE_LABELS`.
- `bti/editor/static/js/errmsg.js:191-193, 239-250`:
  - Added `// --- dsources` blocks for `source_no_key` in `STAGE_CODES.picks` and missing draft turn codes in `STAGE_CODES.draft`.
- `bti/editor/static/js/views/picks.js:15-32, 260-350`:
  - Offered checkboxes for all 5 sources (`commons`, `met`, `pexels`, `pixabay`, `osm`).
  - Sources lacking API keys are labeled with `(chưa có khóa)` and their checkboxes are disabled.
  - Video candidate cards display `Video` badge, omit the "Làm tranh chính" button, and have "Thêm video vào dòng" button.
  - Source error banners translate source names cleanly via `SOURCE_LABELS` with no raw text display.

## 3. Neighbouring Cases Covered
- Video candidate import prevents setting video as main painting (422 `video_not_main`).
- Re-importing an existing asset (image or video) returns existing asset key without duplicate downloading.
- Key missing state gracefully handles both absence from environment and explicit request in API.
- OSM rate limiting handles consecutive calls with fractional delays.
- OSM tile stitching handles tiles spanning boundary wrapping and edge clipping.
- OSM disk cache re-use avoids redownloading tiles for duplicate place & zoom requests.

## 4. Tests and Counts
1. **Windows server snapshot tests (`tools/deploy/snapshot_test.sh dsources`)**:
   - `tests/media`: **142 passed**, 0 failed, 0 skipped in 0.89s (including `test_pexels.py`, `test_pixabay.py`, `test_osm.py`, `test_api.py`).
   - `tests/picks`: **60 passed**, 0 failed, 0 skipped in 11.74s (including `test_new_sources.py`, `test_api.py`, `test_doc.py`, `test_suggest_state.py`).
2. **Mac JavaScript unit tests (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs`)**:
   - **188 passed**, 0 failed, 0 skipped in 686ms.

## 5. Other Workers, Objections & Open Points
- **Needs another worker**: None.
- **Objections**: None.
- **Left open**: None. Everything specified in contract D15 is implemented and verified.
