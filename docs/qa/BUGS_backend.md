# Backend QA findings

Tester: independent backend/engine pass, 2026-11-16. Server under test: own copy on port 8563 (`.scratch/deeptest/serve.py`, data copies of `projects/` and `library/` in `.scratch/deeptest/`; the library paths were pointed at the copy, so merge and split were tested on the copy). Mock model only. Scripts and logs: `.scratch/deeptest/`.
Run the automated checks: `.venv/bin/python -m pytest tests/deep -p no:cacheprovider -q` (about 100 s, temporary copies, no network). Every bug below has a test `test_B0NN_*` that fails today (48 failing cases in total); the sweep and "sound" tests pass.

## Counts (29 findings)

| Severity | Count | Ids |
|---|---|---|
| blocker | 2 | B-001, B-003 |
| major | 11 | B-002, 004, 005, 008, 009, 013, 016, 018, 019, 022, 025 |
| minor | 16 | B-006, 007, 010, 011, 012, 014, 015, 017, 020, 021, 023, 024, 026, 027, 028, 029 |

| Area | Count | Ids |
|---|---|---|
| storyboard save / validation | 6 | B-001, 002, 003, 004, 020, 021 |
| render / stills / previews / cache | 9 | B-005, 022, 023, 024, 025, 026, 028, 029, B-004 (shared) |
| techniques / defaults | 2 | B-006, 007 |
| script stage | 9 | B-008, 009, 010, 011, 012, 013, 014, 015, 027 |
| projects / proposals / media | 4 | B-016, 017, 018, 019 |
| library | 0 | none found |

## Technique sweep (71 of 71 covered)
All 71 techniques: `/defaults` (with and without context), draft, validate, three stills across the span, no defaults failing validation, none over 150 ms warm at 640 px (worst TR-03 129 ms), no blank frame except X-CARD-01 (text leaves at 1.7 s, rest of the shot is black, by design). 3 s previews for all 71 (every transition and card): all render; slow outlier TR-03 (B-028), frame-count outlier X-LAY-01 (B-029). Techniques that need attention: STATIC-08 and X-ANN-03 (defaults place nothing, B-007), HI-03 (required `mask` slot not enforced, B-006). So 66 of 71 are clean, 5 have a finding (STATIC-08, X-ANN-03, HI-03, TR-03, X-LAY-01). The sweep's own warnings for AN-01, AN-02, X-ANN-04 and "required slots not filled" for overlays were artefacts of how the sweep samples (checked by hand), not bugs.

## Incident to disclose
While testing `GET /prompt` and `generate` I sent `POST /outline/generate {}` with no `model`; the server then uses the default model, which is `agy:gemini-4-argon-medium`. The job ran about 6 s before I cancelled it (state `cancelled`). That is one accidental start of an agy job against the scratch project `qa-multi`; I do not know whether the CLI process had actually received a prompt. All other calls named `mock`. Observation (not logged as a bug): omitting `model` silently starts the default external model.

## Tested and found sound
- Revision rule: stale base_rev 409, missing/wrong-typed 422, invalid document 422 with issues, derived `_` keys never stored, no-op save writes nothing, approvals server-owned and tied to rev, forged approvals ignored.
- Concurrent saves: 12 simultaneous PUT with one base_rev gives exactly one 200; approve vs put race consistent.
- Atomic save: 8 rounds of SIGKILL of the server during saves from 3 writers: file always intact, no temp leftovers.
- Storyboard edge cases: min shot length 0.2 (0.1 refused), overlay at start/end/outside, dup ids, zero/negative/str dur, anchors (stale text, index -1, past end, first/last word), unknown asset, missing media, empty shots, 500 shots (validate 11 ms, still 100 ms), non-ASCII/zalgo/html/NUL text, transition on first shot (warn), two transitions in a row, transition longer than shot.
- Path traversal in every path parameter (17 payloads x 25 routes, raw sockets for encoded forms), symlinked project folders (inside and escaping), inner symlink files: no leak, no 500.
- Library: all 6 books, 340 works, 297 artworks with dossiers and source texts load; 178 page images (60 works) decode; embedded images; covers; odd ids; project creation from one/many/low-trust-only sources, existing slug (409), 19 hostile slugs; merge and split (on the copy) and merge-back.
- Script: parsers with 17 hostile inputs (binary, 300k words, regex bomb, CRLF, fences, empty) answer quickly; failed paste kept and restored; beat ops at all boundaries, atomic multi-op, ids never reused; approval drops after every kind of edit; cancel at four phases; model errors (rate limit, validation) surfaced.
- Pipeline step states for imported, selected, script, approved projects; delete confirmation, protected projects, symlink refusal.
- Proposals: add/remove/change, locked shot and overlay blocked, stale flag, unknown ids 422, invalid JSON/empty files quarantined.
- Licence gate on 38 strings (NC/ND/fair use/unknown refused).
- Restart: approvals, kept paste, frame cache and preview files persist.
- Performance: open 82-shot project 45-65 ms; warm still 17-55 ms median at 960 px across 7 projects; 10 s preview 2.9 s (640x15) and 5.4 s (1280x30); server RSS peaked 1.6 GB while rendering from every project and fell back to 395 MB (LRU caps hold); preview cache pruned to 20, frame cache to 1500 files.

## Not tested and why
- Live media search/import: no network use at all (I did not spend any of the 3 Wikimedia queries); only the licence gate was tested, offline. Real `import` download paths, ImageTooSmall and rate-limit 503 mapping are untested.
- Any real model (`agy`, OpenRouter): forbidden; provider timeouts, real-model rate limits and the "offer next model" flow untested beyond the mock (see Incident).
- Hard job timeout (1800 s), memory growth over hours, behaviour under real parallel multi-user load.
- 82-shot warm-time claim after reboot (disk cache cold); the one 374 ms p95 on lab_diagrams at 960 px was not reproduced (all shots 17-28 ms on retry), so it is not reported.
- A "connection reset by peer" seen twice right after a 500 on a reused keep-alive connection was not reproducible and is not reported.
- Beats/outline `PUT` validation of every field type; the voice and picks stages (not built); export.
- Window of the last full `tests/deep` run: results of the final run after the lifespan fix were still being collected when I stopped; an earlier run gave 48 failed (all bug tests), 95 passed.

## Findings

### B-001 (blocker) PUT storyboard with an unknown `style` is saved to disk and bricks the project
Steps: `PUT /api/projects/{pid}/storyboard` with a valid document whose `style` is `"nope"` and the current `base_rev`.
Observed: validation reports no issue; the file is written (`storyboard.json` now has `"style": "nope"`), then the response is `500 Internal Server Error` (FileNotFoundError `style/nope/style.json`). Afterwards `GET /api/projects/{pid}` and every frame request return 500, and a new PUT also fails, so the page cannot open or repair the project.
Expected: 422 with an issue on `style` (the contract says only registry styles exist) and nothing written.
Suspected cause: `bti/engine/storyboard.py::validate` does not check that `style` exists; the style is loaded after the write.

### B-002 (major) `/validate` and PUT crash with 500 on wrongly typed anchor and canvas fields
Steps: `POST /api/projects/{pid}/validate` with a draft where a shot/overlay `start` is `{"t": "abc"}`, or `{"w": N, "off": "a", "text": "..."}`, or `"canvas": "x"`.
Observed: `500 Internal Server Error` (`ValueError: could not convert string to float`; `AttributeError: 'str' object has no attribute 'get'` at `bti/engine/storyboard.py:181`). PUT goes through the same validation, so it is also a 500, and the frame endpoint resets the connection for `canvas: "x"`.
Expected: 200 with `error` issues (validate), 422 (PUT).

### B-003 (blocker) A `timing` path to a missing file is saved and bricks the project; `audio`/`timing` paths are not confined to the project
Steps: `PUT /api/projects/{pid}/storyboard` with `"timing": "../../x.json"` (valid otherwise), current `base_rev`.
Observed: `500`, but `storyboard.json` on disk already holds the bad value. `GET /api/projects/{pid}` then returns 500 (FileNotFoundError on `projects/<pid>/../../x.json`) and so does the frame endpoint. Same family as B-001. Also accepted without an issue, and stored: `"audio": "../../../etc/hosts"` (the audio endpoint then 404s, harmless) and `assets.A.file` set to `"/etc/hosts"` or `"media/../../arnolfini/storyboard.json"` (validate returns no issue; the renderer reads a file outside the project and the frame is a 500 `AttributeError: 'NoneType' object has no attribute 'shape'`). `"project": "other"` (not the folder name) is accepted too.
Expected: 422 with an issue on `timing`, `audio` and `assets.*.file` ("must be a file inside the project"); nothing written; the contract says every path must stay inside the project.
Suspected cause: `bti/engine/storyboard.py::validate` checks existence of `assets.*.file` only relative to the project dir without refusing `..` or absolute paths, and does not check `timing` at all; `Project.save` writes before the timing is read.

### B-004 (major) A draft that names a missing or unknown asset, or has no shots, makes the still endpoint answer 500 with a Python message
Steps: `POST /api/projects/{pid}/frame` with `{t, width, storyboard}` where a shot slot uses asset `"ZZZ"`, or `assets.A.file` is `media/nope.jpg`, or `shots: []`.
Observed: `500 {"detail":"render failed: KeyError: \"asset 'ZZZ' is not defined\""}`, `... AttributeError: 'NoneType' object has no attribute 'shape'`, `... IndexError: list index out of range`. `validate` for the same drafts does give proper issues.
The same drafts sent to `POST /preview` give a job that ends `error` with `KeyError: 'end'`, `KeyError: "asset 'ZZZ' is not defined"` or the `'NoneType'...shape` message.
Expected: a 4xx (422) carrying the validation issues, since the page debounces drafts while a user is part-way through an edit; 500 means "server bug".

### B-005 (major) A text parameter with a line break makes the still a 500
Steps: take a shot with an `X-ANN-01`/`X-ANN-03` overlay; set `params.text` to `"a\nb\n\nc"`; `POST /frame` at a time inside the overlay.
Observed: `500 {"detail":"render failed: ValueError: can't measure length of multiline text"}`; `validate` says OK.
Expected: the text is drawn on one line (newline collapsed) or validate reports an error. A user pressing Enter in the text box breaks the preview.

### B-006 (minor) Overlay-owned required slots are not enforced: HI-03 without `mask` validates clean and renders nothing
Steps: add an overlay `HI-03` with defaults (`/defaults` gives only the 4 numeric params) and no `slots.mask` to a shot with an image. `POST /validate`: no issues. `POST /frame` inside the overlay: identical to the frame without the overlay (mean diff 0.0).
Expected: `required slot 'mask' is missing` as for base techniques (every base technique reports its missing required slots correctly; I checked all 39).

### B-007 (minor) STATIC-08 and X-ANN-03 defaults place the label nowhere
Steps: `POST /defaults {technique: "STATIC-08"}` (also `X-ANN-03`) with a shot context. Result `{"text":"CANDLE","at":null,"screen":null,...}`. Adding it as an overlay validates clean and draws nothing (frame diff 0.0 at 3 times).
Expected: a default position (for example the screen point of the label strip) or a validation warning that neither `at` nor `screen` is set.

### B-008 (major) `PUT /outline` and `PUT /narration` without the document key silently wipe the saved script
Steps: with an outline of 6 chapters, `PUT /api/projects/{pid}/outline` body `{"base_rev": "<current rev>"}` (no `outline` key); same for `PUT /narration` `{"base_rev": ...}`, or `{"narration": {}}`.
Observed: `200`; `GET` then shows 0 chapters. The previous text is only left in the one-deep `narration.prev.json`/`outline.prev.json`, which the next save overwrites.
Expected: 422 `narration (object) is required`, as `PUT /storyboard` does for `storyboard`; and a structurally invalid document (`{"chapters": "x"}`, `{}`) should be refused.
Suspected cause: `script_api.py`: `store.Outline.from_dict(body.get("outline") or {})` and the same for narration.

### B-009 (major) Two model jobs can be started at once for one project
Steps: send 6 simultaneous `POST /api/projects/{pid}/outline/generate {"model":"mock"}`.
Observed: more than one request returns 200 (two job ids appear in `GET /script/jobs`, both ran to `done`; the later one overwrites the outline). The contract/handler intends "409 another model job is running".
Suspected cause: `script_api.start_job` checks `jobs.running(pid)` and then calls `jobs.start(...)` with no lock between the two.

### B-010 (minor) Beat operations coerce wrong types instead of refusing; non-object ops give 500
Steps: `POST /narration/ops` with `{"op":"insert","chapter":"c01","text":["a"]}` stores text `"['a']"`; `"facts":"f01"` stores `['f','0','1']`. `ops: ["x"]`-style bodies, `ops: "x"`, or an op that is not an object (`1`, `null`) give `500`.
Expected: 422 `bad operation`.

### B-011 (minor) `PUT /brief/options` silently ignores out-of-range or wrongly typed values and crashes on `include_low: 5`
Steps: `{"target_words": 5}`, `99999999`, `"x"`, `{"wps": 0}`, `-1`: all `200` with the old value returned and no message. `{"include_low": "abc"}` is stored as `["a","b","c"]`. `{"include_low": 5}` is `500`.
Expected: 422 with the allowed range (target 300..20000, wps 0.5..6), so the page can tell the owner the value was refused.

### B-012 (minor) A chapter left in state `running` after the job failed
Steps: `POST /narration/generate {"model":"mock","force":true,"notes":"[mock:ratelimit]"}`; wait for `state: "error"`.
Observed: `chapters` of the job still shows `c01: "running"`, `c02..: "pending"`. (With `[mock:alwaysbad c02]` the failed chapter is correctly `failed`.)
Expected: the chapter that was in flight is marked `failed` and the rest `skipped`/`cancelled`, so the progress list does not show a live spinner on a dead job.

### B-013 (major) `POST /narration/import` replaces locked beats; `generate` refuses to
Steps: lock a beat (`PUT /narration` with `locked: true`), then `POST /narration/import` with a full pasted script.
Observed: `200`; the locked beat is gone (all beats replaced, new ids). `POST /narration/generate` for the same chapters answers `409 locked beats would be replaced`.
Expected: the same protection (409 with the locked ids unless `force`), or locked beats kept. Locks exist so a re-run does not destroy the owner's work.

### B-014 (minor) Lone UTF-16 surrogate in pasted text gives 500; a non-UTF-8 `last_paste.txt` makes `GET /narration` 500
Steps: `POST /narration/import` with JSON `{"text":"## c01 COLD OPEN\n\ud800 broken"}` gives `500` (UnicodeEncodeError when the text is written), also on the failing-paste path so nothing is kept. Separately, a `script/last_paste.txt` that is not valid UTF-8 (copy damage) makes `GET /narration` return 500 (`GET /outline` is fine because it reads its own file).
Expected: 422 for the first; replace undecodable bytes for the second.

### B-015 (minor) Narration stays `approved: true` and the pipeline stays "script done" after the outline approval is dropped
Steps: approve outline and narration; `PUT /outline` with any edit (the outline approval drops).
Observed: `GET /narration` has `approved: true, stale: false` yet its own issues carry the error `outline_not_approved`; `GET /pipeline` still shows step `script` = `done`; `POST /narration/approve` is refused with 422 for the same reason.
Expected: the narration approval counts as stale (design section 1: "later stages refuse to run on a stale approval"), so `approved` is false and the step is `current`.

### B-016 (major) Deleting a project that has a running model job succeeds, then the job re-creates the folder
Steps: `POST /api/projects/{pid}/outline/generate {"model":"mock","notes":"[mock:slow]"}`; 0.5 s later `DELETE /api/projects/{pid}?confirm={pid}`; wait for the job to end.
Observed: `200 {"deleted": ...}`; ten seconds later `projects/{pid}/script/outline.json` exists again (an orphan folder with no `project.json`, invisible in the list but occupying the slug, so the next create with that slug fails with 409 `already exists`... or continues to write into it).
Expected: 409 "a job is running; cancel it first", or the job is cancelled before the folder goes.
Suspected cause: `pipeline_api.delete_project` has no knowledge of `ScriptJobs`/preview jobs.

### B-017 (minor) `lab_*`, `demo_*` and `arnolfini_edit` projects are not protected from `DELETE`
Steps: `DELETE /api/projects/lab_annot?confirm=lab_annot` gives `200`. Only `arnolfini` and `technique_lab` are in `PROTECTED`. The library refuses to create slugs starting with `lab_`/`demo_` precisely because they are reference material. (Owner call; reported because the two rules disagree.)

### B-018 (major) One malformed proposal file breaks the whole proposals list (and its own GET/apply) with 500
Steps: put `projects/{pid}/proposals/bad4.json` = `{"storyboard":{"shots":"x","assets":[1],"end":5}}` (a valid JSON object with a wrong-typed `storyboard`), then `GET /proposals`, `GET /proposals/bad4`, `POST /proposals/bad4/apply {"accept":"all"}`.
Observed: all three are `500`; the listing fails for every proposal in the folder, so the human cannot reach the good ones either. (Invalid JSON, `[]`, `{"storyboard":"x"}` are handled: quarantined, 404/422 and skipped from the list.)
Expected: 422 for the bad file; the list skips it.
Suspected cause: `proposals.diff` assumes `assets` is a dict and `shots` a list of dicts; `list_proposals` only swallows `ApiError`.

### B-019 (major) Upload accepts a file that is not an image; the asset then breaks every still that uses it
Steps: `POST /api/projects/{pid}/assets/upload` multipart with `file=("a.png", b"not an image")` (also a 0-byte file and a truncated PNG), valid licence fields.
Observed: `200 {"asset_key":"t_a39e","asset":{... "width":0,"height":0 ...}}`; the junk file is kept in `media/`. Adding that asset to a storyboard passes `validate` with no issue and `PUT` saves it. Then `POST /frame` of a shot that uses it is `500 render failed: AssertionError: .../media/t_a39e.png`, and `GET /files/media/...?w=100` is 415.
Expected: 422 "the file is not a readable image" at upload (the licence gate already refuses bad uploads with 422), and `validate` should flag `width`/`height` of 0.

### B-020 (minor) A corrupt `storyboard.json` gives bare 500s and no way back, although `history/` holds the previous copies
Steps: replace `projects/{pid}/storyboard.json` with a truncated file, an empty file, `[1,2]`, `null` or a UTF-8 BOM copy.
Observed: `GET /api/projects/{pid}`, `/frame`, `/assets`, `/thumb`, `/audio`, `/waveform` and `PUT /storyboard` are `500` (for `[1,2]` and `null` the body is just `Internal Server Error`; the others say `storyboard.json is corrupt: ...`). `GET /api/projects` marks the project `error: "storyboard unreadable"` (good) and `/pipeline` stays 200. Nothing is quarantined and no endpoint offers the newest valid file from `history/` (compare proposals, which are quarantined).
Expected: a clear 4xx/5xx JSON with the id of the last good history file, or an automatic quarantine plus restore. Rare in practice because saves are atomic (see "found sound").

### B-021 (minor) `history/` grows without bound
Observed: every changing save adds a full copy of the storyboard (about 150 KB for the 82-shot project; 32 saves = 3 MB) and nothing prunes them. A long edit session or a client that autosaves will fill the disk slowly.
Expected: keep the last N (for example 50) plus one per day, or document the limit.

### B-022 (major) Cached stills and thumbnails ignore changes to `timing.json` (and to media files)
Steps: open `arnolfini` copy, `GET /frame?t=38.58&width=320` (hash A). Shift every word and beat in `timing.json` by +6 s (what a re-voiced audio does). `GET /api/projects/{pid}` now reports shot 3 at 44.28 s instead of 38.28 s and the same `rev`. `GET /frame?t=38.58&width=320` returns the identical old JPEG (same hash, same ETag, `immutable` when `rev=` is sent); width 321 renders new content, so only the cache is at fault.
Expected: the cache key includes the timing file (and the asset files) signature, or the resolved document. The voice stage will rewrite `timing.json`, after which the timeline and the still would disagree until someone saves the storyboard.
Suspected cause: `app.py::current_rev` and `frames.cached_jpeg` key on `compute_rev(storyboard)` only, which strips derived data and excludes timing.

### B-023 (minor) A missing or corrupt `timing.json` makes `GET /api/projects/{pid}`, `/validate` and `/thumb` return a bare plain-text 500
Steps: move `projects/{pid}/timing.json` away (or write `{bad`). Observed: `GET /api/projects/{pid}`, `POST /validate`, `GET /thumb/{shot}` are `500 Internal Server Error` (text/plain, 21 bytes); `GET /frame` still answers 200 (from the cache of B-022). Expected: JSON `{"detail": "timing.json is missing"}`, so the page can show it. Missing audio is handled well (404 `no audio file`; previews render without sound).

### B-024 (minor) `/defaults` answers 500 when the context asset size is negative or not a number
Steps: `POST /api/projects/{pid}/defaults {"technique":"CAM-01","context":{"slots":{"image":{"asset":"A"}},"assets":{"A":{"width":-5,"height":"x"}}}}` (also `"width":"x","height":"y"` with CAM-05) gives `500 Internal Server Error`. A size of 0 is tolerated (returns `camera: null`).
Expected: 422, or fall back to the size stored in the storyboard.

### B-025 (major) A long preview freezes every other request that needs the engine
Steps: `POST /preview {"t0":100,"t1":160,"width":1280,"fps":30}` (the largest the endpoint accepts) on the `arnolfini` copy; one second later `POST /frame` (320 px still of a draft).
Observed: the still waited 312 s (machine load average was 10 at the time; the same job needs about 5.4 s per 10 s of video when the machine is quiet, so roughly 30 s minimum). All of `GET /api/projects/{pid}`, `/frame`, `/validate`, `/thumb` queue behind it, so the page cannot redraw, save-validate or open another project meanwhile. After the preview ended, stills took 48 ms.
Expected: the lock is released between frames (or previews use their own engine instance), or the preview limit is lowered; the contract's own speed target is "10 s preview under 6 s", so 60 s at 30 fps is a 30 s outage for the editor.
Suspected cause: `jobs.render_preview` holds `ENGINE_LOCK` for the whole `render_range`; `state()`, `render_jpeg`, `post_validate` use the same lock.

### B-026 (minor) Preview parameters `fps: 0` / `width: 0` are silently replaced by defaults
`{"t0":5,"t1":6,"fps":0}` is accepted (`int(body.get("fps") or 15)`), the validator message says "fps 1..30". Expected 422 like `fps: 31`.

### B-027 (minor) Jobs are lost on restart and a job in flight is dropped without a trace
Steps: start a script job and a preview job, restart the server (SIGTERM). Observed: `GET /api/jobs/{id}` is 404 for both and `GET /script/jobs` is empty; a script job killed mid-run leaves no `error` record, so the page polling it sees "job not found". Preview files stay served. Approvals, the kept failed paste and the frame cache survive restart (good).
Expected: the page can distinguish "server restarted" from "bad id" (for example a persisted job log), or document it.

### B-028 (minor) Transition TR-03 previews are about three times slower than every other technique
Steps: `POST /preview` for the TR-03 reference of `technique_lab` (3 s, 640x360, 15 fps), twice. 5.29 s and 6.33 s; the median of the other 70 techniques is about 2 s (LAY-01: 1.3 s and 1.5 s; next slowest AN-06 4.1 s). Warm still at 640 px is 119-129 ms (all others under 112 ms). At this rate a 10 s TR-03 preview breaks the contract's "under 6 s" target. Load average was 3.6 (reproduced twice; treat the absolute numbers with care on a shared machine).

### B-029 (minor) X-LAY-01 preview has one frame too many
Steps: 3.0 s preview of the X-LAY-01 reference at 15 fps (t0 at the shot start): 46 frames, duration 3.067 s, on two runs. All other 70 techniques give exactly 45 frames and 3.0 s.
