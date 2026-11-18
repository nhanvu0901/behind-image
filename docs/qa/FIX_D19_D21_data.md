# Fix Report: D19 & D21 (Data Worker)

## D19. Library: about 26 artworks have a wrong title, artist or year

### Cause
Previously, `catalogue.build()` took titles, artists, and years exclusively from `parse.PARSERS[bid](d)`, which parsed the PDF outline (TOC or Index of Artworks). As a result:
1. OCR errors and typos in the printed book outlines (e.g. Turner's chapter heading "Rail, Steam and Speed" instead of "Rain, Steam and Speed – The Great Western Railway" in Payne, or "Due de Berry" in Hagen, or OCR corrupted "Marriage A-la-~Mode: I") were retained in the catalogue.
2. Missing or mangled accents in artist names and titles (e.g. "Velazquez", "Delacroix", "Millet", "Manet", "Fétes Venitiennes", "Bathers at Asniéres") were not corrected despite being properly restored in the clean text files.
3. Grovier's TOC has no years for any of its 57 artworks; however, clean text metadata on each artwork's first page contains the year in `[meta] (<year>)`.
4. Artwork keys in `artworks.json` could shift if title corrections modified the slug, which would break existing projects referencing old keys.

### What was changed
1. `bti/library/catalogue.py`:
   - Added `title_case_words(s: str) -> str` to handle title-casing while properly handling hyphens, apostrophes, accents, and minor words.
   - Added `extract_clean_meta(bid: str, w: dict) -> dict[str, str | None]` to extract `title`, `artist`, `year`, and `headline` from the first page (`page_a` or `page_a+1` if page a is a plate) of clean text for each work.
   - In `catalogue.build()`: Updated the raw work dict with `extract_clean_meta` before applying `overrides`. Precedence is: overrides > clean text > PDF outline.
   - In `catalogue.regroup()`: Scanned `config.PROJECTS_DIR` for existing projects with `artwork_key`. Pinned any artwork group matching a project's sources to that project's `artwork_key`. When a title change would produce a new key, preserved the old key and recorded the new key under `"alias"`.
2. `bti/library/parse.py`:
   - Updated `clean(s: str)` to strip lone surrogates (`[\ud800-\udfff]`) produced by PyMuPDF in `brookehitching_mad` TOC.
3. `tests/library/test_library.py`:
   - Added `test_d19_clean_text_metadata_precedence` and `test_d19_artwork_key_preserved_with_alias`.
4. Rebuilt Mac library (`library/books/*/works.json`, `library/artworks.json`, `library/dossiers/`) after backing up `library/artworks.json` and `library/dossiers/` to `.scratch/ddata_backup/`.
5. Generated `docs/qa/D19_library_changes.md` detailing every changed entry before and after.

### Neighbouring cases covered
- Plate pages before body text in Hodge and Hagen (e.g. page a has no `#` or `[meta]`, header is on page a+1).
- Unparsed/missing years in Grovier: populated for all 56 works from clean text `[meta]` lines.
- Project key preservation when a single work is split or merged (used overlap-based project pinning).
- Dash normalization in years (`–` and `—` normalized to `-`).
- Accented names (e.g., `Diego Velázquez`, `Salvador Dalí`, `Jean-François Millet`, `Édouard Manet`).

### Tests and counts
- Snapshot tests run on Windows server via `tools/deploy/snapshot_test.sh ddata -- tests/library`.
- Result: **53 passed** in 3.60s (0 failed, 0 skipped).

### Numbers requested by contract
- Total artworks: 297.
- Total changed artworks: 73 (including 26 substantive title/artist/key corrections, 29 Grovier singleton year additions, and dash/accent normalization).
- Full before/after table written to `docs/qa/D19_library_changes.md`.

### Objections / Left open
None. Existing projects (`arnolfini-from-books` with `eyck-the-arnolfini-portrait`) preserved keys intact.


## D21. Large files from Wikimedia Commons time out on the server (503)

### Cause
1. Commons originals over 25 megapixels or 40 MB were downloaded directly without requesting scaled renderings from MediaWiki's imageinfo API. Downloading massive files (50-100+ MB) from Commons caused 503 gateway timeouts or connection drops on the server.
2. `bti/media/http.py` `open_url` caught `TimeoutError` and immediately raised `MediaHTTPError` without retrying. Timeouts and rate limits need retry backoff.
3. `_retry_after` only parsed numeric floats; if the server sent an HTTP date string per RFC 7231 (`Wed, 21 Oct 2026 07:28:00 GMT`), it returned `None`.
4. The previous `MAX_IMAGE_BYTES` cap was 150 MB instead of the specified 60 MB, and when exceeded, it raised a generic `MediaHTTPError` that was not mapped to a structured code (`too_large`) the frontend page can explain.

### What was changed
1. `bti/media/http.py`:
   - Line 31: Added `FileTooLarge(ValueError, MediaHTTPError)` with `code="too_large"` and `status=413`. Inherits from both `ValueError` (so `bti.picks.service._translate` maps it to `PicksError(422, ..., "too_large")`) and `MediaHTTPError` (for backward compatibility).
   - Line 39: Enhanced `_retry_after` using `email.utils.parsedate_to_datetime` to parse HTTP-date headers in addition to integer/float seconds, returning the delta in seconds or `None`.
   - Line 56: Added `_is_timeout(exc)` helper detecting `TimeoutError`, `socket.timeout`, and `urllib.error.URLError` with timeout reasons.
   - Line 67: Updated `open_url` to catch timeouts and retry up to `tries` attempts with growing backoff (`BASE_DELAY * 2 ** (attempt - 1)`: 2s, 4s, 8s; capped by `MAX_WAIT = 60s`).
   - Line 132 & 139: In `download_file`, raised `FileTooLarge` when `Content-Length > max_bytes` or streamed `total > max_bytes`.
2. `bti/media/sources/commons.py`:
   - Line 19: Updated `MAX_IMAGE_BYTES = 60 * 1024 * 1024` (60 MB cap). Added `MAX_ORIGINAL_PIXELS = 25_000_000`, `MAX_ORIGINAL_BYTES = 40 * 1024 * 1024`, and `SCALED_LONGEST_SIDE = 6000`.
   - Line 28: Added `_scaled_width(w, h, longest=6000)` to calculate proportional `iiurlwidth` for Commons API rendering (handling landscape, square, and portrait aspect ratios).
   - Line 161: In `download()`: If `kind == "image"` and (`(max(w, h) > 6000 and w * h > 25_000_000)` or `size > 40 * 1024 * 1024`), queries Commons API with `titles=...`, `prop="imageinfo"`, `iiprop="url|size|mime"`, `iiurlwidth=...` to obtain `thumburl`, and downloads the scaled rendering instead of the massive original.
   - Line 178: If not scaled and declared `meta["size"] > cap`, raises `FileTooLarge` up front.
   - Line 180: Streams download to disk via `http.download_file`, which downloads to `.part` and atomically replaces to final destination via `bti/fsio.atomic_replace`.
3. `tests/media/test_http.py`:
   - Added 6 unit tests covering `FileTooLarge` inheritance/attributes, timeout retries (4 attempts with delays `[2.0, 4.0, 8.0]`), timeout recovery on 2nd attempt, urllib timeout detection, `Retry-After` numeric seconds, and `Retry-After` HTTP date strings.
4. `tests/media/test_commons.py`:
   - Added 4 integration tests covering:
     - Landscape large image (> 25 MP) scaling request with `iiurlwidth=6000`.
     - Portrait large image (> 25 MP) target width calculation with `iiurlwidth=3750`.
     - Heavy file (> 40 MB) scaling request.
     - Image exceeding 60 MB after scaling refused with `FileTooLarge(code="too_large")` and disk file cleaned up.

### Neighbouring cases covered
- Portrait images (`h > w`): target width properly derived from `round(w * 6000 / h)` so that longest side is 6000 px.
- Landscape and square images (`w >= h`): target width capped at 6000 px.
- Files <= 6000 px on longest side but heavy in bytes (> 40 MB TIFF/PNG): Commons thumbnail requested to receive web JPEG.
- Preserving original download for normal-sized images (<= 25 MP and <= 40 MB) without unnecessary API calls.
- Temp `.part` files cleaned up on any download error or size refusal.
- Generic User-Agent (`behind-the-image-media/0.1 (art documentary research tool)`) preserved without personal information.

### Tests and counts
- Snapshot tests run on Windows server via `tools/deploy/snapshot_test.sh ddata -- tests/library tests/media`.
- Exact count: **176 passed** (53 in `tests/library`, 123 in `tests/media`) in 4.02s.

### Numbers requested by contract
- Max original megapixels before scaling: 25 MP (25,000,000 pixels).
- Max original file size before scaling: 40 MB (41,943,040 bytes).
- Scaled rendering longest side: 6000 px.
- Retry attempts on 429/502/503/timeouts: up to 4 tries (initial + 3 retries) with delays 2s, 4s, 8s (capped at 60s).
- Hard cap for image downloads: 60 MB (62,914,560 bytes).
- Error code on exceeding 60 MB: `too_large` (HTTP status 413 / 422).

### Needs another worker
None for D19 and D21.

### Objections / Left open
None.

