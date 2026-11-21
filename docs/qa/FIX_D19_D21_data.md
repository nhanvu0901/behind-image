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
None.


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


## D19 Follow-up (TASK2): titles, artists, years, aliases

Second pass by a new worker on 2026-11-18. The first pass of this follow-up (earlier worker, uncommitted) was read first; what was kept
and what was redone is listed at the end.

### 1. Title casing after an apostrophe: fixed
`catalogue.title_case_words` re-cases a title only when it is ALL UPPER or all lower case; any other title is returned as written
("The Artist’s Studio", "Merda d’Artista" are untouched). Small words (a, an, the, of, and, in, on, at, to, with, after, du, de, la, le)
stay lower case except as the first word, a letter after an apostrophe is never capitalised ("Artist’s", "Velázquez’s"). One addition to
the rule: the first word after a dash, after "word:" and after a plate number ("Mode: 1, The ...") counts as a first word, so
"Rain, Steam and Speed – The Great Western Railway". Where a heading in capitals differs from the outline title only in case, the
outline's casing is kept (`pick_fields`), and a hyphen broken at a line end ("Master- Stroke") is joined.

### 2. A worse value replacing a better one: fixed by a trust order and `library/overrides/artists.json`
- Every work records where each of its fields came from (`field_src`: override, clean or outline). `catalogue.regroup` takes each field
  of an artwork from its most trusted work: override > clean text of a digital normal-trust book > clean text of a scanned normal-trust
  book > PDF outline > any low-trust book (`catalogue.source_rank`; ties go to book order). A low-trust book (Grovier) gives only its
  year from the clean text; its titles and names stay as in its outline.
- `library/overrides/artists.json` is `{canonical name: [variants]}`. Lookup ignores case, accents, hyphens and apostrophes, so
  "Eugene", "Eugéne" and "EUGÈNE" all give "Eugène Delacroix". It holds the 11 names you gave plus the ones below. "After X" is
  split off into `attribution: "after"` (Cornelis van Dalem, The Legend of the Baker of Eeklo). The file lives only in
  `library/overrides/` (the copy inside the code package `bti/library/overrides/` was a mistake and was removed).
- A name that is in no file and is written in capitals gets particles in lower case (`name_case`): "Leonardo da Vinci", not "Da Vinci".

Artists that had more than one spelling in the catalogue, and the form chosen (every one now has a single spelling; the check was
"same normalised name" and "same last name"):

| Chosen | Variants that occurred | Why |
|---|---|---|
| Hieronymus Bosch | Hieronymous Bosch | typo |
| Pieter Bruegel the Elder | Bruegel the Elder | your list |
| Eugène Delacroix | Eugene / Eugéne Delacroix | your list |
| Caravaggio | Michelangelo da Caravaggio | your list |
| Diego Velázquez | Diego Velazquez | your list |
| Salvador Dalí | Salvador Dali | your list |
| Édouard Manet, Jean-François Millet, Pierre-Auguste Renoir, Georgia O’Keeffe | accent, hyphen and apostrophe variants | your list |
| Cornelis van Dalem | Cornelis Van Dalem, After Cornelis Van Dalem | your list, "after" is an attribution |
| Rembrandt van Rijn | Rembrandt | the clean text of Hodge and Hagen says "Rembrandt van Rijn"; keys keep the word `rembrandt` (`key_name`, owner decision) |
| Jan van Eyck, Rogier van der Weyden, Hugo van der Goes, Hilma af Klint | "Van", "Af" with a capital | the lower-case particle is the form of the clean text and of most entries |
| Francisco de Goya | Francisco Goya | the clean text of every book that names him says "de Goya" |
| Georges Seurat | Georges-Pierre Seurat | the clean text of Hodge, Hagen and Grovier says "Georges Seurat" |
| Giovanni Battista Tiepolo | Giambattista Tiepolo | the clean text of Hodge and Hagen says "Giovanni Battista"; only the Hagen outline said "Giambattista" (2 entries against 1 before: check) |
| Tintoretto | Jacopo Tintoretto | the clean text of Hodge, Hagen and Grovier says "Tintoretto" |
| Johannes Vermeer | Jan Vermeer | the clean text of Payne, Hodge and Grovier says "Johannes Vermeer" |
| Paolo Veronese | Paolo Caliari (Veronese) | the clean text of Hodge and Hagen says "Paolo Veronese" |
| Vincent van Gogh | Vincent Van Gogh | owner decision; keys unchanged (`gogh-...`) |
| Zhang Zeduan | Zhang Zeduan (Attrib.) | owner decision: `attribution: "attributed"`, key word `zhang` |
| Joan Miró (not a double spelling: a single wrong one) | Joan Miré | one entry had "Miré", an obvious typo; fixed and listed because it changes a key |

`artists.json` entries may be `{"variants": [...], "key_name": "word"}`: `key_name` is the first word of the artwork keys of that artist
(`catalogue.artist_key_word`); without it the last word of the name is used. Used for Rembrandt (`rembrandt`) and Zhang Zeduan (`zhang`).
Left alone: other names whose last word is a weak key (giotto di Bondone -> `bondone-`, Piero della Francesca -> `francesca-`, Joseph Wright of
Derby -> `derby-`, Hildegard of Bingen, Apollodorus of Damascus, "The Limburg Brothers", "Master of the Transfiguration of the Virgin"): changing them
would change old keys; give them a `key_name` if wanted. Titles keep the "St" / "St." of their most trusted source. Gentileschi's "Judith Slaying
Holofernes" takes its year (1612–1613) from the most trusted source (Brooke-Hitching, digital); Hodge says c. 1620, so the two books may describe two
versions of the painting: the owner may want to look.

### 3. Years: fixed (`parse.parse_year`, `parse.print_year`)
`parse_year` returns `{from, to, circa, era}` (era `AD`, `BC` or `BC-AD`) or None; `print_year` prints `1434`, `c. 1562–1566`,
`c. 900 BC`, `645–635 BC`, `27 BC–AD 68` (an AD year below 1000 is printed `AD 113`, numbers of 10,000 and more with a comma,
`38,000–33,000 BC`). `parse.normalise_year` gives `(year, year_raw)`. A BC span written ascending ("27-68 B.C.") is read as 27 BC to AD 68.
`year_num` (used for matching and rights) still guesses a number from text that is not a year. In the Mac library every `year` now
parses and prints to itself (checked on all works and artworks). 263 artworks have a year, 20 have only `year_raw`, 14 have neither (the
12 ArtCurious chapters, "Betty", the Abramović chapter). The 20 that are not years:
after 1066 (Bayeux Tapestry), after 1475 (The Conjurer), after 1630 (The Fortune Teller), after 1660 (The Chancellor Séguier),
"About 60 B.C. - 50 years ago" (Villa of the Mysteries), "approximately 800 years" (Book of Kells), "approximately 1,000 years"
(Travelers among Mountains and Streams), and 13 centuries (late second century, twelfth-thirteenth centuries, early thirteenth,
thirteenth-nineteenth, fourteenth, fifteenth-seventeenth, sixteenth-eighteenth, seventeenth, seventeenth-twentieth, eighteenth, nineteenth,
nineteenth-twentieth, twentieth). Decision for you: centuries and "after 1475" used to sit in `year` and now do not, as you asked; if the
page should show them, show `year_raw` when `year` is empty.

### 4. Aliases: done
`regroup` compares the previous `library/artworks.json` with the new one and records every key that disappeared as an alias of the
artwork that took over its works (`library/overrides/aliases.json`, `{old: current}`, also `aliases: [...]` inside the entry). An alias
follows its artwork if the key changes again; a current key is never shadowed by an alias. `catalogue.load_artworks()` returns an
`ArtworksDict`: `d[old_key]` and `d.get(old_key)` give the current artwork, `old_key in d`, iteration and `len` see current keys only (so
merge, split and dossier clean-up are not confused). New: `catalogue.resolve_key(key)`, `catalogue.get_artwork(key)`;
`dossiers.load(old_key)` opens the dossier of the current key. Ten keys changed against the pre-D19 catalogue (all recorded):
bosch-the-conjuror, dali-the-temptation-of-saint-anthony, hogarth-marriage-a-la-mode-i, menzel-steel-mill, mire-the-hunter-catalan-landscape,
rijn-the-night-watch, rijn-self-portrait-with-two-circles (now `rembrandt-...`), attrib-along-the-river-during-the (now `zhang-...`), turner-rail-steam-and-speed, velazquez-venus-at-her-mirror.
`eyck-the-arnolfini-portrait` and `munch-the-scream` are unchanged (`PINNED_KEYS`; `regroup` reports `pinned_missing` if one ever
disappears). Keys of artworks that a project in `projects/` already uses are still pinned to the project's key.

### Rebuild
`python -m bti.library build` and `python -m bti.library dossiers` on the Mac, starting from the backed-up catalogue so that the aliases
cover the whole change since before D19. 297 artworks (same groups of works), 164 differ from the backup (210 changed fields), 33 are
in two or more books. Full table: `docs/qa/D19_library_changes.md`.

### Tests
`tools/deploy/snapshot_test.sh ddata -- tests/library -q` on the Windows server: 140 passed, 0 failed, 0 skipped (`tests/library`); `tests/editor/test_library_api.py` 14 passed; `node --test tests/editor_frontend/*.test.mjs` 199 passed on the Mac. All new tests build a
temporary library, so they do not depend on the server's (older) catalogue. Only `test_protected_keys_in_the_built_library` reads the real
one (it checks the two protected keys, which the old and the new catalogue share).

### What was kept and what was redone from the first pass of this follow-up
Kept: the idea of `parse_year` / `print_year` and the `attribution` split in `parse_madman`; the seed list of `artists.json` (extended);
the project pinning of keys (D19 first pass); `ArtworksDict` as the answer to "look-up by alias" (reshaped). Redone: title casing
(capital after an apostrophe, small words, subtitles); the year parser (it had a hard-coded 27/68 case and accepted "after" as no-year only);
the trust order (it ranked books, not sources, and did not know about overrides or `field_src`); canonical artists (no lookup by
normalised name, no upper-case names); aliases (they were built from a hard-coded read of `.scratch/ddata_backup/`, and `in` / iteration
counted aliases, which would have kept stale dossiers); the copy of the data files inside `bti/library/overrides/` (removed); the tests
(they depended on the Mac's built library); the changes table. First-pass keys such as `pollock-one-number-31-1950` are gone: the key
of that artwork is unchanged now.

### Editor changes (owner-approved, small)
`bti/editor/library_api.py`: `/artworks/<old key>` and its `/source/...` answer with the current key (test `test_artwork_by_old_key_answers_with_the_current_key`);
the work and artwork rows carry `year_raw`. `bti/editor/static/js/views/library.js`: five places show `year_raw` when `year` is empty (works table,
work page, artworks table, artwork page, merge list). `views/artwork.js` is the project page (its `p.year` is the project's own) and was not touched.
