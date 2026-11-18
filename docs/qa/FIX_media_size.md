# FIX: an imported picture's recorded size is the size of the stored file (worker mediafix)

Brief: `.scratch/agy_tasks/mediafix/TASK.md`. No request was sent to Wikimedia by me or by any test (every test uses fake openers;
the safety switch `BTI_NO_REAL_MODELS=1` is on in the snapshot).

## 1. What was wrong (verified in the code at commit a049001)

| Where (HEAD) | What it did |
|---|---|
| `bti/media/api.py` 137-139 | `w, h = (meta.get("width") or 0, ...)`: the asset was recorded with the size the SOURCE API reports for its original, and the stored file was measured only when the metadata had no size. |
| `bti/media/sources/commons.py` 161-175, 28-34 | A Commons original over 25 MP with a side over 6000 px (or over 40 MB) asked the API for `iiurlwidth = _scaled_width(...)`, a width computed from "longest side 6000" (4833 for 6703 x 8322; 6000 for a 4000 x 4000 heavy PNG). Wikimedia serves only its standard widths, so a 3840 px file came back and was stored, but `api.py` recorded 6703 x 8322. |
| `bti/media/sources/commons.py` 115, 129 | Search cards and `fetch_meta` asked for `iiurlwidth=320`, which is also not a standard width (330 is). |
| `bti/media/http.py` 25, 83-92 | `_RETRY` contained 429 and 503: every refused request was sent 4 times (waits 2, 4, 8 s, or `Retry-After` up to 60 s). Nothing remembered that a host had said "wait". |
| `bti/picks/service.py` 35-39 | A 429 became `source_unreachable` ("busy or not answering"): no wait time, not distinguishable from a dead source. |
| `bti/picks/doc.py` 112-113, 211-215 | `normalize` kept the declared width/height; `load` returned them as they were. Nothing compared them with the file. |

Consumers that use the DECLARED size (so they disagree with the drawn pixels when it is wrong), re-read now: `picks.js` 681, 694-695;
`picks_logic.js` 108-114 (`cropStyle`); `bti/picks/service.py` `check_regions` (417); `bti/draft/spec.py` 183; `bti/draft/compile.py`
128-134 (the saved storyboard's own `assets` override the picks' ones) and ~150, ~692 (`assets` copied into the storyboard);
`bti/draft/defaults.py` 48; `bti/identity/apply.py` 224-226; `bti/engine/base.py` 151 `asset_size()`. Consumers that use the STORED
pixels: `Ctx.image()` (base.py 135), `vfx.Img` (175-187: `cv2.imread`, which applies the EXIF turn), `draft/workspace.py` 155, 160, 250.
Every large Commons picture was affected the same way. Pixabay was too: `largeImageURL` is at most 1280 px but `imageWidth` is the
original's. Pexels when the `original` URL is missing and `large2x` is used. OSM maps whose cache file is not 2400 x 1350.

## 2. What each change does

**One rule, one measuring step** (`bti/media/api.py`, `assets.py`, `imageinfo.py`, `clips.py`)
- `imageinfo.drawn_size(path)`: the pixels the engine draws and the page shows: `image_size` plus the EXIF quarter turn of a JPEG
  (orientation 5-8), because OpenCV and browsers turn such a file. A test checks this against `cv2.imread` on the server.
- `api.stored_image_size(path)`: `drawn_size`, refuses (`ImageDamaged`, `image_unreadable`) a file with no readable size.
- `import_candidate` (Commons, Met, Pexels, Pixabay, OSM, book images) and `add_upload` call it on the STORED file. Videos and
  clips use the probe of the stored file (`clips.import_clip` now probes the copy in `media/`, not the cache file; a failed probe
  removes the copy).
- `assets.build_asset(..., original_size=)` records the source's own claim as `original_width` / `original_height` (only when
  positive), so credits can still say what the source offers. `bti/picks/doc.py` `_asset()` keeps these two keys (it dropped every
  unknown asset key before). The storyboard validator has no rule against extra asset keys (checked at `engine/storyboard.py` 570-610).
- Importing an item again whose `media/sources.json` record has a wrong size measures the file, fixes the record and the index,
  with no download.

**Standard widths** (`bti/media/sources/commons.py`)
- `THUMB_STEPS = (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)`. `CARD_THUMB_WIDTH = 330` replaces 320.
- `rendition_width(w, h)`: the largest step that is smaller than the original and gives a rendition that is not "too big" by the
  app's own two limits (longest side <= 6000 px OR <= 25 MP). 6703 x 8322 gives 3840 (3840 x 4767); 5000 x 8000 gives 3840
  (3840 x 6144 = 23.6 MP); 3000 x 3000 (heavy bytes) gives 1920; no size known gives 3840; nothing fits gives None (original is downloaded).
- A `thumburl` equal to the original's URL is no longer treated as a rendition (the 60 MB cap check then applies).
- Where I read the list: MediaWiki's own pages "Common thumbnail sizes" (mediawiki.org/wiki/Common_thumbnail_sizes) and
  "Manual:$wgThumbnailSteps", through WEB SEARCH excerpts of them (two searches, same list both times). I did NOT fetch those pages
  or anything else on a Wikimedia domain, because the brief forbids any request to Wikimedia. The same excerpts say Wikimedia
  throttles non-standard thumbnail sizes (HTTP 429 "use thumbnail steps"; Phabricator T402792) and that the API rounds up to a step.
  This matches the incident (4833 and 320 were non-standard) but I could not test it against the real service. Please re-check the
  list against the page when convenient.

**Repair of existing data, no network** (`assets.reconcile_sizes`, called by `bti/picks/doc.py` `load`)
- For every image asset whose file exists inside the project and whose header-read pixel size differs from the declared one:
  `width`/`height` become the stored size, every region of that asset is scaled (x, rx by stored w / declared w; y, ry by stored h /
  declared h; integers stay integers), and the old declared size is kept as `original_width/height` when the record has none.
  Missing or unreadable files, videos, paths outside the project (`..`, absolute) and records that already agree are left alone.
  A declared size of 0 is filled in without touching regions. Sizes are cached per (path, mtime, bytes), so `load` stays cheap.
- It happens IN MEMORY on every load (deterministic, idempotent) and reaches the disk with the next write of the document
  (any save, `PUT regions`, an import, the approval). Reading writes nothing. A test proves load -> save -> load gives the same
  document and revision.
- Side effect to know: the repaired document has another revision. A page that was open before gets `stale` (409) once and
  reloads. If the picks were already approved, the approval no longer stands ("Cần duyệt lại: chọn hình đã đổi sau khi duyệt");
  approving again writes the repair. I chose not to re-stamp the approval silently.

**Polite client** (`bti/media/http.py`, `bti/picks/service.py`, `errmsg.js`)
- HTTP 429 and 503: with a `Retry-After` of at most 5 s (`SHORT_RETRY_AFTER`) the request waits that long and tries ONCE more.
  Otherwise (no `Retry-After`, a longer one, a second refusal) it raises `MediaHTTPError` at once, with `retry_after` (seconds, None
  when unknown) and `rate_limited` (429, or 503 with a time). A 503 with no time is not retried either but is not called a rate limit.
  500, 502, 504 and timeouts keep the old backoff (2, 4, 8 s, 4 tries).
- Added beyond the brief (small, remove `_COOLDOWN` and `_cooldown_check` to drop it): when a source gave a wait time, that host
  gets no request until the time has passed (monotonic clock, capped at 1 h); a second click inside the wait fails at once without
  a request. A refusal with no time starts no cooldown.
- The picks API answers `503 {code: "source_rate_limited", retry_after: <seconds|null>, retryable: true}` for import routes, and a
  search error entry `{source, code, message, retry_after}`. Other codes are unchanged (`source_unreachable` for 502, 504, 503 without a time).
- Page text (`errmsg.js`, block "worker mediafix"): `sourceLimitText(body)`: "Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng N phút."
  (N = seconds rounded up to whole minutes, at least 1) or "Nguồn ảnh đang giới hạn lượt tải. Thử lại sau." when unknown. It is wired
  through `BY_CODE_HTTP`, so `describeHttp`, `describeError` and `stageErrorText` all use it. It is deliberately NOT in
  `STAGE_CODES.picks`: `picks.js` `fail()` (line 25) prefers that table over `describeError`, which would lose the minutes.
- User-Agent sent today (`http.USER_AGENT`, every request including downloads and the OSM geocoder): `behind-the-image-media/0.1 (art
  documentary research tool)`. It names the client plainly, has no name, email or URL: unchanged. (Wikimedia's UA policy asks for a
  contact; the owner's rule forbids personal details, so I did not add one. I cannot say whether that played a part in the 429.)

## 3. Tests (server snapshot `mediafix`; the JavaScript on the Mac)

```
tests/media   : 274 passed in 1.68s
tests/picks   : 88 passed, 1 warning in 8.29s
tests/editor  : 435 passed, 1 warning in 199.46s (0:03:19)
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
              : ℹ tests 267 / ℹ pass 267 / ℹ fail 0
```
New: `tests/media/test_stored_size.py` (the incident end to end; Commons, Pexels, Pixabay, Met, OSM, book, upload, EXIF-turned JPEG
checked against `cv2.imread`, video and clip probe the stored file, re-import repairs the index with no request, `reconcile_sizes`
cases), `tests/media/test_http.py` (429 with 3 s / twice / 7 s / 600 s / no time, 503 with a date and without, 5xx backoff kept,
cooldown, silly `Retry-After`, download leaves nothing, User-Agent), `tests/media/test_commons.py` (the list, `rendition_width`
table and limits, card width 330), `tests/picks/test_size_repair.py` (load repair with and without regions, idempotence, save
persists, missing/damaged/video, page state and region check in the stored space, approval after repair, `_translate` table, 429 on
import and search through the real routes with one request, cooldown, the large-original import), `tests/picks/sourcelimit.test.mjs`.
Existing tests changed because they encoded the bug (each marked CHANGED): `test_api.py::test_import_writes_file_and_entry` (asset
size is the file's, original kept), `tests/picks/test_api.py::test_regions` (region inside the 1300 x 1250 file, not the 4386 x 6000
original), `test_commons.py` backoff tests (429 is no longer retried four times) and the three rendition tests (3840).

## 4. Existing data

- Affected: any asset whose recorded size differs from its file. Certain: Commons images over 25 MP with a side over 6000 px or over
  40 MB (the owner's `scream` main painting: recorded 6703 x 8322, file 3840 x 4767). Likely: Pixabay imports (declared original,
  stored <= 1280 px), Pexels imports that fell back to `large2x`, OSM maps from an odd cache file. Not affected: uploads, book images, Met (no size in the API).
- Repaired in `picks.json`: automatically at the next load (in memory) and written with the next save/approval, as described above.
  Regions already drawn on such an asset are scaled with it (the scream's would be multiplied by about 0.573).
- Repaired in `media/sources.json`: when the item is imported again (no download).
- Reference projects (my snapshot copies, not the owner's): a read-only scan with `reconcile_sizes` found no asset with a wrong
  size; only two assets (`lab_diagrams` M, `technique_lab` diag_M) have no declared size and would be filled in at 1097 x 1500.
- NOT checked: the owner's real projects on the server (the brief says never the server's main folder), so I cannot list which of
  them carry a wrong size beyond what the code logic says.
- Storyboards: a `storyboard.json` compiled earlier holds its own copy of `assets` (width, height, regions: `draft/compile.py`
  ~692) and the compiler even prefers the saved storyboard's assets over the picks' (128-134). So an existing storyboard built on a
  wrong-size asset carries the wrong size AND camera keys / region points in the wrong space. Nothing repairs that without the
  changes in section 5. For `scream` there is no storyboard yet (step 4). For any other project: after the picks are repaired,
  re-run the draft (step 5) rather than patch camera keys by hand.

## 5. Needs another worker (files I was told not to touch)

1. `bti/draft/inputs.py` `load_inputs` (~282-286, `fill_sizes` at 184): the draft reads `picks.json` raw from disk and fills only a MISSING
   size, so a wrong size that is not yet persisted reaches `compile.py` / `defaults.py` / `spec.py` (regions too). Add
   `from bti.media import assets; assets.reconcile_sizes(picks["assets"], project_dir)` and the same for `current["assets"]` (the saved
   storyboard's own copies, which `compile._merge_assets` lets override the picks). `fill_sizes` becomes unnecessary (reconcile fills a missing size).
2. `bti/engine/storyboard.py` (load/validate): the same call on `sb["assets"]` at load so `Ctx.asset_size()` (base.py 151) never sees a size
   that disagrees with the file; plus a warning issue (for example `asset_size_mismatch`) when it had to correct one, because camera keys
   authored in the old space are NOT rescaled by `reconcile_sizes` (only regions are).
3. `bti/identity/apply.py` 224-226 and `bti/editor/identity_api.py` 47 read `picks.json` raw (`width`/`height` of the main painting):
   read through `bti.picks.doc.load` or call `reconcile_sizes` on the asset first.
4. `bti/editor/static/js/views/picks.js` 336: the search banner shows `ERR[e.code] || 'không tìm được.'`, so a limited source shows no
   reason. Use `e.code === 'source_rate_limited' ? sourceLimitText(e) : (ERR[e.code] || 'không tìm được.')` (`sourceLimitText` is exported by `errmsg.js`).
   The import toast already shows the minutes (through `errorToast` -> `describeError`).
5. `bti/editor/media_adapter.py` 80-90 (`_translate`, the older storyboard "Hình" tab import): it maps every 429/503 to a fixed Vietnamese
   sentence with `retry_after=10`. Use `e.rate_limited` / `e.retry_after` and answer `code: "source_rate_limited"` with the real wait,
   so the same sentence is shown. Its import already records the measured size (it goes through `api.import_candidate`).
