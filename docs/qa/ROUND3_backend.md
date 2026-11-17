# Round 3 backend and engine test report

Tester: independent backend/engine tester, 2026-11-16. Mock model only, temp copies of `projects/` and `library/`, no network.
Tests: `tests/deep/test_round3_*.py` (each bug has a test that asserts the correct behaviour and FAILS while the bug exists).
"Confirmed" = reproduced at least twice (a hand script and the test, or two hand runs).
Machine load average during the work: 2 to 5 (another agent drives a browser).

Disclosure: once, by mistake, `GET /api/models` ran in a scratch script before I had stubbed the CLI, so the real `agy models` (a list command, no prompt) ran one time (2 s). No model was called. All later scripts set `BTI_AGY_BIN=""`.

## Bugs

### R3B-001 (major) `draw_check` in `POST /approve` holds the global `ENGINE_LOCK` for the whole check; every other project's state request waits
- Steps (temp copy): `POST /api/projects/arnolfini/approve {rev}` in a thread; meanwhile `GET /api/projects/technique_lab` (any other project, or the same one).
- Expected: approval cost does not stall other requests of the server (round 2 task D: "must not block other requests while it runs").
- Actual: arnolfini (82 shots): approve 6.7 s, the concurrent `GET /api/projects/technique_lab` answered after 6.16 s. A project of 263 shots (technique_lab shots repeated, no validate errors): approve 35.7 s, `GET /api/projects/arnolfini` answered after 35.4 s. `GET /api/projects` (the list), `/pipeline`, `/thumb` and validate of a draft did not wait. Before `464bf85` approve held the lock for the validate only (milliseconds): regression.
- Cause: `bti/editor/app.py:489-490` `with ENGINE_LOCK: drawn = p.draw_check(saved)` (the whole pass under one process-wide RLock; `GET /api/projects/{pid}` needs the same lock at `app.py:190`).
- Regression from `464bf85`. Test: `test_R3B_001_approve_does_not_block_other_projects`.

(R3B-001 note: at 21:25 a fix had already landed in `bti/editor/app.py`; its test passed on the later run. Not re-tested after that.)
Same cause: while the check runs the storyboard lock of the approved project is also held, so a save of that project waits the whole time (35 s on 263 shots).

### R3B-002 (major) The depth middleware's scan is quadratic: one request body of 160 KB blocks the whole server for a minute
- Steps: `DepthLimitMiddleware.too_deep(b'"' + b'\\"' * N)`; or `POST` any JSON route with `Content-Type: application/json` and that body.
- Expected: linear time (a 2 MB legitimate body scans in 0.035 s; an unterminated quote in 0.1 s).
- Actual: 20 KB 0.88 s, 40 KB 3.5 s, 80 KB 14.4 s, 160 KB 59 s (4x per doubling). The scan runs inside the async middleware, so it blocks the event loop: every other request waits. A 2 MB body would hold the server for hours. Confirmed twice (direct timing in a script at four sizes, and the test).
- Cause: `bti/editor/common.py:140` `_TOKEN = rb'"(?:[^"\\]|\\.)*"|[\[\]{}]'`: an unterminated string that contains many `\"` makes every later `"` start a new full-length failing match. Also the scan is synchronous in `__call__` (line 174).
- Regression from `464bf85` (new middleware). Test: `test_R3B_002_depth_scan_is_linear_on_an_unterminated_escaped_string`.

### R3B-003 (major) A storyboard.json of the wrong shape inside (`shots` a string, `shots` a list of strings, `overlays` a string) makes `GET /api/projects/{pid}` and `/thumb` answer 500
- Steps: write `{"...": ..., "shots": "no"}` (or `"shots": ["a"]`, or `shots[0].overlays = "x"`) into a project's storyboard.json; `GET /api/projects/<pid>`.
- Expected: 409 `data_error` naming the file (R2B-014), like `[1]` at the top level (which does answer 409 with a restore hint).
- Actual: 500 `internal error (AttributeError)`; the list `GET /api/projects` and `/frame` (422) are fine. Found with a table of 22 field mutations; all other mutations answered 200/404/422.
- Cause: `bti/engine/storyboard.py:191` and `:207` (`resolve` calls `.get` on a non-dict shot / overlays list), reached from `bti/engine/api.py:105` via `bti/editor/app.py:247` `state`. `SB.load` / `check_readable` check only the top-level object.
- Older than `464bf85` (R2B-014 "every field" left half done). Tests: `test_R3B_003_storyboard_file_of_the_wrong_shape_is_not_a_500` (3 cases). Confirmed (hand table + test).

### R3B-004 (minor) `project.json` with `"sources": 5` makes `GET /pipeline` answer 500
- Steps: set `sources` to an integer in a library-made project's project.json; `GET /api/projects/<pid>/pipeline`. (`/outline`, `/narration`, `/brief` answer 409 correctly; list and `/api/pipeline` fine.)
- Cause: `bti/editor/pipeline_api.py:162` `len(pj.get("sources") or [])`. Older (R2B-014 half done). Test: `test_R3B_004_project_json_sources_not_a_list_is_not_a_500`. Confirmed (hand + test).

### R3B-005 (minor) A file that exists but cannot be read (mode 000) gives 500 in three more places
- Steps: `chmod 000` on `source/*.txt` -> `GET /outline`, `/narration`, `/brief` 500 (PermissionError); on `script/last_paste.txt` -> `GET /narration` 500; on `proposals/<id>.json` -> `GET /proposals/<id>` 500. The same `chmod 000` on outline.json, narration.json, dossier.json, project.json is a proper 409.
- Expected: 409 naming the file (R2B-014: "a file that is there but unreadable is a named 409").
- Cause: `bti/script/store.py:119` `read_text_strict` (only `UnicodeDecodeError` mapped), `store.read_paste` (`:627`), `app.py` proposals loader (`:740-750`) with no `OSError` guard.
- Older (R2B-014 half done). Test: `test_R3B_005_unreadable_file_is_409_not_500` (4 cases; the proposals case is covered by the same cause, no separate test). Confirmed (full table of 14 files x 10 damage forms, then the test).
- Also seen: every damaged file was repaired by writing the original back and the endpoints recovered at once (no cache remembers damage), and the list endpoints (`/api/projects`, `/api/pipeline`, `/api/library/*`) never changed.

### R3B-006 (minor) A directory in place of `script/narration.json` or `outline.json`: reads say "no document" (200), the save answers 500
- Steps: replace script/narration.json by a folder; `GET /narration` 200 (empty), `PUT /narration` 500 `IsADirectoryError`; for outline.json also the outline job ends `error: IsADirectoryError ...` with the path. A symlink loop in the same place is read as absent and the next save replaces it (fine).
- Expected: 409 `data_error` on both, as for an unreadable file. Cause: `bti/script/store.py` `_load` treats "not a file" as absent while `write_json_atomic` (`os.replace`) fails. Test: `test_R3B_006_a_directory_in_place_of_a_script_file_is_not_a_500_on_save`. Confirmed (hand + test).

### R3B-007 (major) After the outline's chapters are reordered the narration can be approved in the old order without any word
- Steps: mock outline, approve, mock narration, approve narration. `PUT /outline` swapping chapters 2 and 3, approve the outline, `POST /narration/approve` with the narration's rev.
- Expected: approval refused, or the order follows the outline, or an issue says the order differs ("a narration approval belongs to one outline": the order is part of the outline).
- Actual: 200; narration order c01,c02,c03 while the approved outline is c01,c03,c02; `issues` has no warning; stage `script`. Any later step that reads the narration in file order produces a video with chapters in the wrong order. There is no API operation to move a chapter (only a whole-document PUT). Confirmed twice (two scripts, then the test).
- Cause: `bti/script/validate.py` `validate_narration` and `store.chapter_diff` compare ids as sets only. Regression from `464bf85`: no (the set check is new, the order was never checked), but R2B-001 left it open. Test: `test_R3B_007_reordered_outline_chapters_do_not_leave_a_silently_approved_narration_in_the_old_order`.
- Also seen (information, not filed): `stale` stays true after the owner re-approved against the new outline (it means "written from another outline"), so the page must not show it when `approved` is true.

### R3B-008 (minor) Registry bounds that validate accepts and the engine cannot draw: 42 single-parameter values at a registry min/max in 10 techniques
- Steps: for every number param of the 71 techniques, one at a time, set the registry `min`, `max` and default on the technique_lab reference (all other params at their defaults), `POST /validate` then `POST /frame`. Zero false refusals (every min, max, default is accepted). But 42 values validate with no error and `/frame` answers 422 `render_failed`: LAY-01 panel_w_px, panel_h_px, panel_y_px, left_x_px (max); LAY-02 tile_w_px, tile_h_px, margin_x_px, margin_y_px, gap_x_px, gap_y_px; LAY-03 columns, col_w_px, col_h_px, gap_px, y_px; CMP-01 and CMP-04 panel_w/h/y, left_x, right_x; CMP-02 stage_size_px, stage_pitch_px, stage_y_px; CMP-03 panel_w/h/y, x0_px, pitch_px; X-CMP-01 (as CMP-01); X-ANN-01/02 strip_y_top_pct max, strip_y_bottom_pct min. Also 9 params have `default: null` with a min and max (HI-01 rx, ry; X-HI-01 rx, ry, hold_s; AN-01 radius; AN-05 frame_zoom; X-ANN-04 per_group_draw_s; X-ANN-05 marker_count): not a bug, noted.
- Expected: R2B-012 "whatever validate accepts, the engine can draw"; the engine fixer's own note says combinations of two in-range pixel values are left to `draw_check`. Here a single slider at its declared maximum is enough, so the editor shows a 422 frame with no validate issue until approval. The registry range is wider than the canvas allows with the other defaults.
- Fix direction: narrow `max` to what fits with defaults, or add a cross-check in validate (box/panel/tile must lie inside the canvas).
- Not a regression (older). Test: `test_R3B_008_a_value_at_the_registry_bound_is_refused_by_validate_or_drawn` (9 representative cases). Confirmed (full sweep 984 draws, then the test).

### R3B-009 (minor) A truncated JPEG draws a 200 frame, validates clean and can be approved
- Steps: cut `media/arn__arnolfini_commons.jpg` of a technique_lab copy to a third; `GET /frame` in shot s0001: 200 (lower part grey), validate has no error, `POST /approve` of a one-shot project: 200. libjpeg only prints "Premature end of JPEG file" on stderr. A zero-byte, garbage, mode 000, directory, missing and symlink-loop file, for an image, a mask and a video, are all 422 (frame, thumb, approve) and one line with exit 1 on the CLI; a zero-byte or truncated video: approve refuses (undrawable), preview job error; fine.
- Expected: refusal naming the shot (round 2 task D). Cause: `bti/engine` image loader (`cv2.imread`) does not treat a partial decode as failure. Test: `test_R3B_009_a_truncated_image_is_not_silently_drawn`. Confirmed twice (hand run: frame and approve; test).

### R3B-010 (cosmetic) `render_failed` messages show the raw exception and the absolute server path, and name the wrong exception
- Steps: zero-byte or garbage image in a shot: `GET /frame` 422 `detail`: "shot s0001 (CAM-01) cannot be drawn: AssertionError: /private/.../media/x.jpg". For an existing but unreadable mask or video the text says `FileNotFoundError` although the file exists. The same text is the CLI line and the preview job `error`.
- Expected: a sentence about the file ("the image of shot s0001 cannot be read"), no server path. Cause: `bti/engine/scene.py` `render_error` puts `f"{type(e).__name__}: {e}"` into the message. Test: `test_R3B_010_render_failed_message_does_not_leak_the_server_path_or_a_wrong_exception_name`. Confirmed (21 runs of the damage table, then the test).
- Also seen: OpenCV/libpng/ffmpeg print their own warnings on the CLI's stderr before the one-line message (2-3 extra lines); they come from the libraries.

### R3B-011 (cosmetic) An upload that races a delete can answer 422 "the file is not a readable image" instead of 404
- Steps: upload while the project is deleted (1 of 25 trials in a three-way race; the other 24 gave 404). Deterministic form: the folder is renamed between the temp file write and `readable_problem`.
- Expected 404 `project not found`. Cause: `bti/editor/app.py:720-723` checks the temp file, which went away with the folder, before `confirm_alive`. Test: `test_R3B_011_upload_whose_folder_vanishes_while_it_is_checked_answers_404`. Confirmed (race once, deterministic test).

### R3B-012 (major) `GET /api/models` answers 500 when `agy models` prints bytes that are not UTF-8, and the failure is not cached
- Steps (fake `agy` via `BTI_AGY_BIN`): the fake prints `\366\377` to stdout. `GET /api/models` 500 `UnicodeDecodeError`. Every request runs the CLI again (the exception is not a `ProviderError`, so nothing is cached). `get_model` is called by every job start, so every generation job fails too.
- Expected: 200 with the antigravity entry `agy: {ok: false, reason: ...}`, like for text garbage, empty output, tabs only (all answer 200 correctly), and a 100000-row output (200, fine).
- Cause: `bti/script/providers/antigravity.py:~160` `subprocess.run(..., text=True)` with no `errors="replace"`. Test: `test_R3B_012_models_answers_200_when_the_cli_prints_bytes_that_are_not_utf8`. Confirmed (hand + test). Not a regression of 464bf85 in intent, but its test list did not cover it.
- Also seen (cosmetic): duplicate slugs give two entries with the same id (`agy:x`); a NUL or `../` in a slug is put into the id unchanged.

### R3B-013 (minor) Starting a job with the `mock` (or any non-agy) model waits for `agy models`, up to 8 s
- Steps: fake `agy` that sleeps 4 s; cold cache; `POST /outline/generate {"model":"mock"}`: answer after 4.1 s (7.0 s when the CLI hangs; the limit is 8 s). The `_lock` is held during the call, and `model_for` -> `load_models` expands every antigravity entry even though the request names another model.
- Expected: a job with the mock model never calls the CLI. Cause: `bti/script/models.py:51-61` (lock held during the CLI call) and `:80-88`, called from `script_api.py:107-112`. Regression from `464bf85` (the lock and cache are new). Test: `test_R3B_013_starting_a_mock_job_does_not_wait_for_agy_models`. Confirmed twice (two hand runs, test).
- Model cache otherwise sound: four simultaneous requests make one call; a failure is cached 60 s and re-queried after 61 s; `?refresh=1` re-queries and returns the new list; a CLI that hangs with a child holding the pipe is cut at 8.0 s; missing CLI gives `agy: {ok:false, reason:"config"}`.

## Performance note (item H, partly)
Peak resident memory of one `draw_check` of `arnolfini` in a fresh process was 1.7 GB (82 shots, final size not involved). A server that approves a large project grows by that much and keeps it in the image caches. Not filed as a bug (no limit promised), but it is close to the 2 GB guard I was told to use.

## Performance (item H), medians of 5 (3 for the preview), same machine, load average 4 to 6, same library copy for both
| Request | `b1f0d14` (before) | `464bf85` + fixes in progress (after) | Ratio |
|---|---|---|---|
| `GET /api/projects` (9 projects) | 10.6 ms | 10.1 ms | 0.95 |
| `GET /api/library/artworks` (285) | 166 ms | 167 ms | 1.0 |
| `GET /api/projects/arnolfini` (state) | 26.4 ms | 26.6 ms | 1.0 |
| `POST /validate` (82 shots) | 5.0 ms | 7.0 ms | 1.4 (under the 1.5 line) |
| `PUT /storyboard` (82 shots) | 37.0 ms | 41.5 ms | 1.1 |
| `POST /frame` 960 px | 23.4 ms | 26.7 ms | 1.1 |
| 10 s preview, 480 px | 2.48 s | 2.52 s | 1.0 |
No slowdown over 1.5x. The costs that did grow are `POST /approve` (draw_check: 6.7 s on 82 shots, 35.7 s on 263 shots, R3B-001) and the depth scan on hostile bodies (R3B-002). The scan of legitimate bodies is cheap: 50 KB 1 ms, 1.2 MB 35 ms, 2 MB of unterminated quote 0.1 s.

## Tried and found sound
- Item A: every tracked storyboard (8 projects) validates with 0 errors and `draw_check` is empty (arnolfini 6.4 s, technique_lab 11.3 s, one process each). No false refusal anywhere: all 492 number params at registry min, max and default were accepted by validate (only 9 have default null). Every `pattern` accepts its default (lists item by item) and every value used in the tracked projects. Defaults of all 71 techniques validate and draw (the technique_lab sweep, 71 of 71 done). Outline and narration from the mock model pass the new id and enum checks.
- Item B walk (outline approve, narration approve, small edit, chapter removed, chapter added, chapter reordered, partial generation of the new chapter, lock a beat, regenerate over a lock = 409, approve with a lock): `GET /narration`, `/outline`, `/pipeline`, `/api/projects` agreed at every step; every refusal had a way out through the API (drop the chapter by PUT, generate the missing chapter, re-approve). Exception: R3B-007. No project in `projects/` carries an old approval record, so the old-record path was read in code only (an old record is "outline_changed" and costs one click).
- Item C: 12 + 30 + 14 + 14 + 14 random rounds of 2 to 3 concurrent operations on one project (storyboard save, approve, outline/narration PUT, approve, generate, upload, delete, frame, preview) against a real server on port 8581 with 40 s client timeouts: no hang, no 500, no ghost folder, no trash folder; delete gave 200 or 409 with a job really running; the slug could be created and used at once after every delete; 20 + 20 deletes right after a finished or cancelled job were all 200. Only 404 and 409 where a delete won.
- Item D: damaged image, mask and video (missing, zero, truncated, garbage, mode 000, directory, symlink loop) on `/frame` GET and POST, `/thumb`, `/preview` job, `/approve`, and the engine command line: 422 or a one-line error naming the shot, never 500, never a hang (exceptions: R3B-009, R3B-010). `GET /api/projects` and the pipeline list were not blocked by approve.
- Item E: 14 files x 10 damage forms (empty, truncated, list, string, null, latin-1, directory, mode 000, symlink loop, wrong object): list and index endpoints (`/api/projects`, `/api/pipeline`, `/api/library/artworks`, `/api/library/books`, `/api/health`) never changed status; every file was repaired by writing it back and the project worked at once, no restart. 500s only as filed (R3B-003 to 006).
- Item F: see R3B-013 (single flight, failure cached 60 s, `?refresh=1`, hang cut at 8 s, shape stable for missing CLI, auth error, text garbage, empty output, huge output).
- Item G: deep JSON (3000 levels) with content types json, vnd.api+json, `application/JSON`, text/json: 422 `too_deep`; with text/plain, none, form, multipart, octet-stream: 422 (not a dict), never 500; gzip-encoded body 400; empty, `not json`, `\xff\xfe`, `{`, `null`, `1`: 422. A 1.2 MB storyboard and a 50 KB one scan in 35 ms and 1 ms.

## Not tested, and why
- Item G, "a route that was missed by the helpers": only sampled (frame, validate, storyboard, outline, narration ops, library create); I did not walk all 46 write routes again (round 2 did, with 19 nasty values).
- Wrong `Content-Length` over a socket: the test client sets it itself; not tried with a raw socket.
- A 500 KB narration through `PUT /narration` end to end and a 2 MB storyboard through `PUT /storyboard`: only the middleware scan was timed.
- Three-way lock mixes beyond the random pairs and triples above (no 200-trial run); a project with 300 SHORT (2.5 s) shots: the 263-shot project used is made of the 71 lab shots repeated (the engine refused hand-made 2.5 s shots through camera key order).
- `draw_check` at final quality and the buffer guard with the biggest images at `--quality final` width 1920: not run (memory: `draw_check` alone peaks at 1.7 GB, close to my 2 GB limit).
- After "fix agents edit bti/" started (about 21:20), I did not re-test anything; R3B-001's test already passed on the last run.
