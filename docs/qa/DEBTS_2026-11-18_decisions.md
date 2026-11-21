# Old debts: decisions for the fixes (group D)

Written by the analyst on 2026-11-18. The owner asked for groups B and D of the open list to be done. Group B is specified in
`docs/qa/REVIEW_2026-11-17_decisions.md`. This file is the contract for group D. Same principle: **fix the class, not the reported
case**, with a test that fails before the fix. The testing rules at the end of `REVIEW_2026-11-17_decisions.md` apply to every
worker (Python tests on the Windows server through `tools/deploy/snapshot_test.sh`, never in the server's main folder, never on
the Mac; no real model, voice, render, paid call or download in a test).

## Who owns what

| Worker | Items | Owns (may edit) |
|---|---|---|
| d-engine | D16 | `bti/engine/**`, `bti/editor/engine_adapter.py`, the approve route's draw-check call in `bti/editor/app.py` (those lines only), `tests/engine/**`, `tests/editor/test_round3_approve_lock.py` |
| d-voice | D17 | `bti/voice/**`, `config/voice.json`, `tests/voice/**` |
| d-data | D19, D21 | `bti/library/**`, `tests/library/**`, `bti/media/sources/commons.py`, `bti/media/http.py`, `tests/media/test_commons*.py`, `tests/media/test_http*.py` |
| d-script (after A-core) | D18, D20 | `bti/script/brief.py`, `validate.py`, `bti/editor/script_api.py`, `prompts/**`, `bti/editor/static/js/views/script.js`, `tests/script/**`, the script parts of `tests/editor/**` and `tests/e2e/**` |
| d-sources (after b-clips) | D15 | new files under `bti/media/sources/`, `bti/media/api.py`, `bti/picks/service.py`, `bti/editor/picks_api.py`, `views/picks.js`, `bti/script/env.py` (the list of allowed key names only), `tests/media/**`, `tests/picks/**` |
| d-camera (last) | D22 | `bti/editor/static/js/preview.js`, `edit.js`, `coords.js`, `formui.js`, `tests/editor_frontend/**`, `tests/e2e/storyboard/**` |

`labels.js` and `errmsg.js` are shared: add entries only inside a block of your own that starts with a comment naming your worker,
re-read the file right before each edit, keep each edit small.

## D16. Approving a storyboard is slow on the server (23 s for 82 shots)
A measurement on the server (`tools/deploy/probe_parallel.py`, `docs/WINDOWS.md`) drew the same 300 samples with a thread pool in
5 to 7 s, byte-identical to the serial frames. Make that the real behaviour.
- Audit every piece of shared mutable state a frame draw touches (`scene.py`, `vfx.py`, `helpers.py`, the image pyramid, font and
  media-check caches, anything module-level) and make each one safe for concurrent draws: a lock around filling a cache entry, no
  shared scratch buffers. Write the audit as a table in your report.
- `Project.draw_check` and `draw_check_iter` take `threads` (default from `config/server.json`, key `check_threads`, 8 on the
  server, 4 elsewhere). The scene for the check is compiled once; the samples are drawn by a pool that does not hold the editor's
  process-wide engine lock, so other requests are served meanwhile (the rule of R3B-001 stays: an approval never blocks another
  project's requests for more than about half a second).
- Tests: for `projects/arnolfini` and `projects/technique_lab`, every sample frame from the pooled check is byte-identical to the
  serial one (marked `slow` if over a minute); an undrawable shot is still reported for the right shot; cancellation and an
  exception in one sample do not leave threads behind; `tests/editor/test_round3_approve_lock.py` still passes.
- Report the numbers on the server: approval of the 82-shot project before and after, and the answer time of another project's
  request during it.

## D17. Voice: parts run over the server's 30-minute rule; the true peak is too high
Measured on the real run (87 sentences, 14 min 24 s of speech): 104 minutes of compute in three parts of 31, 37 and 30 minutes;
true peak -1.06 dBTP where the design asks for under -1.5.
- The planner sizes a part from an estimate `load_seconds + characters * seconds_per_character` and targets **18 minutes**; no part
  may be planned over 25. Defaults in `config/voice.json`: `load_seconds: 120`, `seconds_per_character: 0.55` (from the real run).
  After every real part the measured values are stored (`run/voice_stats.json`, a rolling median of the last 20 parts on this
  machine) and used instead of the defaults. A part that still runs past 28 minutes finishes the sentence it is on, stops cleanly,
  and the rest goes to a new part (never killed mid-sentence, never a failed job).
- Assembly: after loudness normalisation a true-peak limiter holds the mix at or under -1.5 dBTP; the manifest records the measured
  integrated loudness and true peak; a mix over -1.5 is an error of the assembly step, not a warning.
- Tests with the fake provider and an injected clock for the planner (sizes, the 25-minute cap, learning from stats, the clean stop);
  a real ffmpeg measurement of a short assembled mix for the peak (this is light and allowed).

## D18. Step 2: any book can be left out as a source
Today only a machine-translated book can be ticked in; a trusted book cannot be ticked out.
- Brief options gain `exclude` (book ids, work ids or source codes). An excluded source is not in the brief; the paragraph ids of
  the other sources do not change. At least one source must stay (422 with a code otherwise).
- A fact of the outline that cites an excluded source: issue `source_excluded` (warning) naming the fact; a fact whose every source
  is excluded: error for approval. Changing the options never deletes anything.
- Page: in the "Nguồn" column every source has the same control, "Dùng sách này làm nguồn", ticked or not; the reason a
  machine-translated book starts unticked stays visible. The script page also takes its preselected model from the settings route
  of A-core (`GET /api/settings/models`, roles `script.outline` and `script.narration`).

## D19. Library: about 26 artworks have a wrong title, artist or year
- The catalogue takes title, artist and year from the cleaned text of the work's first page (`# ` heading and `[meta]` lines, see
  `docs/design/2026-11-16-clean-text-format.md`) when present, then from the PDF outline; `library/overrides/` still wins.
- **Artwork keys must not change** for artworks that have a project (`artwork_key` in `projects/*/project.json`); where a corrected
  title would change a key, keep the old key and record the alias.
- Do the rebuild on the Mac's library only. Write the full before and after of every changed entry to
  `docs/qa/D19_library_changes.md`; the analyst decides when the server's library is rebuilt. Tests with small fixtures.

## D20. The model's narration sentences are too long (median 23 words)
- `prompts/script.md` and `prompts/rules_voice.md`: a target the model can follow (most sentences 8 to 18 words, none over 28, one
  idea per sentence, written for the ear), with two short examples of a long sentence split in two.
- Validation of a narration: `long_sentence` (warning) per beat with sentences over 28 words, and a summary line with the median
  sentence length of the script. The page shows them with the other issues. No model is called by the worker; the analyst measures
  the effect with one real chapter afterwards.

## D21. Large files from Wikimedia Commons time out on the server (503)
- Never download an original over 25 megapixels or 40 MB: ask Commons for a scaled rendering (`iiurlwidth`, longest side 6000 px)
  and download that. Stream to disk through `bti/fsio.atomic_replace`. Retry 429, 502, 503 and time-outs up to four times with a
  growing pause and `Retry-After` when sent. A descriptive, generic User-Agent with no personal details (Commons asks for one).
  A file over 60 MB after all that is refused with a code the page can explain.
- Tests with a fake HTTP layer for each case; no network.

## D15. More picture sources
- `pexels` and `pixabay` (photos and videos): clients behind the existing source interface, keys `PEXELS_API_KEY` and
  `PIXABAY_API_KEY` read through `bti/script/env.py` (add the two names to its allow-list; never print a key). Without a key the
  source is listed as "chưa có khóa" and is not called. Results carry author, licence and page link like the other sources.
- `osm` (a map of a place): geocode the place name with Nominatim (at most one request a second, generic User-Agent), compose one
  picture about 2400 px wide from standard tiles at a zoom that shows the place, record the credit "© OpenStreetMap contributors"
  (ODbL). Low volume by design: one map per request, cached by place and zoom.
- The picks search tab offers the new sources; a video result goes through the clip import of part B. Tests with fixtures only.

## D22. Camera with several keys can only be edited by number fields
- In the preview's source view each camera key of the selected shot is a frame that can be dragged (centre) and resized by a corner
  (zoom), for every technique with a `camera` parameter, including LAY-01. Each drag is one undo step and updates the number fields.
- This comes last: the owner plans to use the instruction box instead of manual tools.

## Not in this contract
D13 (a new visual identity) needs the channel's name and a look chosen by the owner. D14 (the Shorts tool) gets its own design.
