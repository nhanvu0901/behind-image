# Round 2 backend test report

Tester: independent backend tester, 2026-11-16. Mock model only, temp copies of `projects/` and `library/`, no network.
Tests: `tests/deep/test_round2_*.py` (each bug has a test that asserts the correct behaviour and FAILS while the bug exists).
"Confirmed" = reproduced at least twice (once by hand script, once by the added test).

## Bugs

### R2B-001 (major) Narration approval revives after the outline is changed and approved again
- Steps: new project, outline generate (mock), approve, narration generate (mock), approve narration. `PUT /outline` with one chapter removed (`chapters.pop(2)`), then `POST /outline/approve` with the new rev.
- Expected: the narration was written from another outline (its `source.outline_sha1` no longer matches, and it holds chapter `c03` the outline does not have): `approved` false / `stale` true, stage not `script`.
- Actual: `GET /narration` -> `approved: true, stale: false`, issue `unknown_chapter` only at level `warning`; `GET /pipeline` -> `stage: "script"`, step script `done`. `POST /narration/approve` on that orphan-chapter narration also returns 200. The B-015 fix ties the narration approval only to "outline is approved now", not to "this is the outline it was written from".
- Cause: `bti/script/store.py:310` `Narration.approved_fresh` (and `bti/editor/script_api.py:46` `narr_payload`, `bti/script/stage.py:12`) compare only the narration sha and the current outline approval.
- Test: `tests/deep/test_round2_flow.py::test_R2B_001_narration_approval_does_not_survive_a_changed_outline`. Confirmed (hand script + test).

### R2B-002 (major) Stage says `approved` while the storyboard approval is stale
- Steps: approve a storyboard (`POST /approve {rev}`), then `PUT /storyboard` with any change (the server keeps the old `approvals`).
- Expected: the stage falls back to `storyboard` (the step already says "Duyệt cũ: storyboard đã sửa sau khi duyệt").
- Actual: `GET /pipeline` -> `stage: "approved"` and step `edit` detail "Duyệt cũ..."; `GET /api/projects` row `stage: "approved"`. The two disagree.
- Cause: `bti/library/projects.py:116-119` `infer_stage` treats any `approvals.storyboard` as approved without comparing `rev` (the step code in `bti/editor/pipeline_api.py:_storyboard_state` does compare).
- Test: `test_R2B_002_stage_agrees_with_stale_storyboard_approval`. Confirmed.

### R2B-003 (minor) Engine CLI reports success for impossible ranges and values
- Steps (on a copy of `technique_lab`): `python -m bti.engine render <dir> --t0 5 --t1 2 -o a.mp4` ; `still <dir> nan -o n.png` (also `-3`, `inf`) ; `render ... --fps 0` and `--width 0`.
- Expected: non-zero exit and a message (the HTTP API refuses all of these: `t1 > t0`, finite `t >= 0`, `fps` 1..30, width range).
- Actual: all exit 0. The backwards range writes a 1-frame 640x360 MP4 (ffprobe: nb_frames 1) and prints "wrote ..."; `nan` writes a PNG after a numpy "invalid value in cast" warning; `--fps 0` / `--width 0` are treated as "not given" (`a.fps or ...`) and a 15 fps 640 px video is written. A start far past the end (`--t0 9999 --t1 10000`) also writes 5 frames, exit 0 (seen once, the API allows this for stills, so only reported as a note).
- Cause: `bti/engine/__main__.py:30-48` no argument checks; `a.width or ...` / `a.fps or ...` turn 0 into the default.
- Tests: `tests/deep/test_round2_cli.py::test_R2B_003_render_backwards_range_is_refused`, `..._still_with_nan_or_negative_time_is_refused`, `..._render_with_zero_fps_or_width_is_refused`. Confirmed (hand run + test).

### R2B-004 (minor) Engine CLI shows Python tracebacks for ordinary user errors
- Steps: `validate <missing dir>` -> `FileNotFoundError` traceback (exit 1); `still <dir> 1 --width 0` -> OpenCV assertion traceback; `-o out.txt` -> "could not find a writer" traceback; `-o /nonexistent_root/x.png` -> `OSError` traceback; `render --threads -2` -> ffmpeg error then `BrokenPipeError` traceback.
- Expected: one-line message on stderr, exit code 1 or 2 (argparse style), no traceback.
- Cause: `bti/engine/__main__.py:23-48` has no `try/except` around `open_project`, `frame_at`, `imwrite`, `render_range`; `bti/engine/scene.py:130` writes to a dead ffmpeg pipe.
- Test: `test_R2B_004_cli_errors_are_messages_not_tracebacks`. Confirmed.

### R2B-005 (major) DELETE during a save answers 500 or leaves a ghost folder; saves answer 500 on a vanishing project
- Steps (stress, no special tools): project with an outline; three threads loop `PUT /outline` (fresh `base_rev` each time); after 150 ms `DELETE /api/projects/<pid>?confirm=<pid>`; stop the writers after 300 ms. 12 trials by hand: delete answered 500 in 5 of 12 (`OSError: [Errno 66] Directory not empty` from `shutil.rmtree`), and the folder was left as `projects/<pid>/script/outline.json` only (no `project.json`, no `source/`). In 2 trials a `PUT /outline` answered 500 (`FileNotFoundError: .../source/payne_gae_004.txt` from the brief builder reading a folder that is being deleted).
- Expected: delete waits for / refuses while a save holds the project (409), or wins cleanly (200) and every later write is 404; never 500, never a ghost folder.
- Actual: as above. B-016 fixed only "a job is running"; a save in flight is not seen. The ghost folder is not listed by `/api/projects` (no `project.json`) but it occupies the slug (`create` -> 409 "already exists"; check) and holds an outline.
- Cause: `bti/editor/pipeline_api.py:197-218` `delete_project` takes neither `store.script_lock(d)` nor the storyboard `save_lock`; `bti/script/store.py:56-62` `write_json_atomic` does `path.parent.mkdir(parents=True)` which re-creates the deleted folder.
- Test: `tests/deep/test_round2_concurrency.py::test_R2B_005_delete_during_saves_is_clean`. Confirmed (hand run 5/12, test).

### R2B-006 (minor) A deeply nested storyboard gives 500 (RecursionError)
- Steps: `POST /api/projects/<pid>/validate` (also `/frame`, `/preview`, `PUT /storyboard`) with `{"storyboard": {"a":{"a":{ ... 2000 levels }}}}`.
- Expected: 422 (or 413) with a message; nothing written. Actual: 500 `{"detail":"internal error (RecursionError)..."}` on all four routes (nothing is written, `rev` unchanged). JSON is valid, the recursion is in the product's own walkers.
- Cause: recursive `strip_derived` in `bti/editor/common.py:94` and `bti/engine/storyboard.py:35` (also `canonical`), reached before any shape check; no depth limit.
- Test: `tests/deep/test_round2_input.py::test_R2B_006_deeply_nested_storyboard_is_422_not_500`. Confirmed (hand fuzz + test).

### R2B-007 (minor) `POST /api/library/projects` answers 500 for lists of non-strings
- Steps: body `{"work_ids": [[]]}` or `[{}]`; or `{"artwork_key": "<valid>", "exclude": [[]]}` / `[{}]`.
- Expected 422 `{detail}`. Actual: 500 `internal error (TypeError)` (`unhashable type`). Nothing is created.
- Cause: `bti/library/projects.py:50` `set(exclude)` and `:55` `set(work_ids)` on unchecked items (`parse_work_id` only runs later); `bti/editor/library_api.py:289-303` checks only that `exclude` is a list.
- Test: `test_R2B_007_create_project_with_wrong_typed_lists_is_422` (4 of 5 cases fail; `[1]` already answers 422). Confirmed.

### R2B-008 (minor) Integers beyond float range give 500 (OverflowError)
- Steps: `POST .../frame {"t": 10**400, "storyboard": {}}`; `POST .../preview {"t0": 0, "t1": 10**400}` (and `t0` huge); `GET .../frame?t=1000...0` (400 digits) behaves the same through the query parser only if it reaches `float()`.
- Expected 422 "t out of range". Actual 500 `internal error (OverflowError)`. NaN and Infinity literals are correctly 422.
- Cause: `bti/editor/frames.py:32` catches `(TypeError, ValueError)` but not `OverflowError`; `bti/editor/app.py:539` `float(body.get("t0"))` same.
- Test: `test_R2B_008_huge_integers_are_422_not_500`. Confirmed.

### R2B-009 (minor) A path segment longer than the file system limit gives 500 (OSError)
- Steps: `GET /api/projects/<pid>/files/<300 x "a">`; `GET /style/gae/previews/<300 x a>`; `GET /api/library/artworks/<300 x a>`; `GET /<300 x a>` (the SPA catch-all).
- Expected 404. Actual 500 `internal error (OSError)` (ENAMETOOLONG from `Path.is_file()`/`resolve()`).
- Cause: `bti/editor/common.py:safe_join` (`target.resolve()`), `bti/editor/app.py:744` catch-all, `library_api.py:227` artwork lookup; no length check before touching the file system.
- Test: `test_R2B_009_overlong_path_segment_is_404_not_500`. Confirmed.

### R2B-010 (major) `PUT /narration` accepts duplicate beat ids and coerces `role` / `card`
- Steps: take a narration with approved outline, send it back with `chapters[0].beats[1].id = chapters[0].beats[0].id` and `chapters[1].beats[0].id` the same; also `chapters[2].role = "bogus"`, `chapters[2].card = "yes"`.
- Expected: 422 naming the field (the B-010 rule: nothing coerced; ids are the key of locks, facts and ops). Actual: 200, `issues` has no warning at all, `role` is saved as `chapter`, `card` as `true`; `POST /narration/ops {"op":"drop","beat":"b0001"}` then removes only the first match and the other beats keep the same id; `POST /narration/approve` on that document answers 200.
- Cause: `bti/script/store.py:322-376` `doc_problem` checks chapter ids for duplicates but not beat ids (within or across chapters), `role` against `ROLES`, or `card` for bool; `Narration.from_dict` (store.py:244) then coerces.
- Tests: `tests/deep/test_round2_flow.py::test_R2B_010_put_narration_refuses_duplicate_beat_ids`, `::test_R2B_010_put_narration_does_not_coerce_role_or_card`. Confirmed (hand script + tests).

### R2B-011 (cosmetic) An upload without a title is titled with the server's temp file name
- Steps: `POST /assets/upload` with file `my_picture.png`, form `title=""`. Expected: title from the uploaded name (`my_picture`). Actual: `asset.title` and the key are `tmppu36v303` (the temp file made by the endpoint).
- Cause: `bti/editor/app.py:645-662` hands the temp path to `bti/media/api.py:107` (`title = meta.get("title") or file_path.stem`); the original `file.filename` is never passed on.
- Test: `tests/deep/test_round2_input.py::test_R2B_011_upload_without_title_uses_the_file_name_not_the_temp_name`. Confirmed (twice).

### R2B-012 (major) `validate` accepts parameter values the engine cannot draw: the draft saves, approves, and then every frame is 500
- Found by a sweep: for each of the 71 techniques, take `/defaults`, set ONE param (type-checked by the registry as `point`, `points` or `string`) to a wrong but well-typed value (`"x"`, `"#zzz"`, `"a\nb"`, `[]`), then `POST /validate`, then `POST /frame`. 9300 mutations; 68 gave "no error" from validate and `500 render failed` from frame (21 distinct technique/param pairs, the list is in the test).
  - `point` given a string that is not a region (STATIC-06 `from_point`/`to_point`/`control_point`; LAY-06 `strip_start`/`strip_step`; DIA-01 `axes_origin`/`axes_end`/`ray_origin`; DIA-06 `room_center`/`room_label_pos`/`uv_label_pos`): `ValueError: invalid literal for int()`.
  - a `point` region name that does not exist on a SHOT technique (DIA-01/02/04/05 `focus`, `figure_focus`): `KeyError: region 'x' is not defined on asset`. The overlay branch of validate checks this, the shot branch does not.
  - `string` params that really carry a number or a keyword (CMP-02 `stage_blur`/`stage_grey`/`stage_gain`, CMP-03 `versions`, LAY-08 `tiles` as "NxM"): `ValueError: could not convert string to float` / `unknown treatment` / `not enough values to unpack`.
  - `points: []` for DIA-02 `to_quad`: OpenCV assertion.
  Removing any one param (766 cases) and the defaults of all 71 (plain, required-only, no params, slots emptied) were all fine.
- Consequence (hand run, CMP-03 `versions: "x"`): `PUT /storyboard` 200, `GET /frame` 500, `GET /thumb/<shot>` 500, `POST /approve` 200 (stage becomes `approved`), previews of that range fail. An approved storyboard that cannot be drawn.
- Expected: validate reports an `error` on the param path (or `warn incomplete`, with a placeholder), so save/approve are refused or the engine draws a placeholder; never a 500.
- Cause: `bti/engine/registry.py:validate_params` only checks the JSON type of `point`/`points`/`string` values, not format, region existence on shots, or minimum length; `bti/engine/storyboard.py:470-480` checks regions only in the overlay branch.
- Test: `tests/deep/test_round2_engine.py::test_R2B_012_validate_accepts_only_what_can_be_drawn[*]` (21 cases, all fail). Confirmed (sweep + hand run + tests).

### R2B-013 (minor) Outline accepts chapter ids the narration step cannot use; the narration job then fails after spending model calls
- Steps: `PUT /outline` with `chapters[0].id` = `"c 1"`, `"C01"`, `"é"`, `"../../x"` or `"c01\n## x"`; `POST /outline/approve`; `POST /narration/generate {"model":"mock"}`.
- Expected: 422 at `PUT /outline` (the id must look like `c<digits>`, the only form `bti/script/parse.py:21 CH_ID_RE` can read back). Actual: PUT 200, approve 200, generate 200, then the job ends `error` ("Chapter c 1 failed validation twice (The script could not be placed...") after the second attempt, i.e. two real model calls wasted per bad id with a real model. `c1` works.
- Cause: `bti/script/store.py:322` `doc_problem` requires only a non-empty string for a chapter id.
- Test: `tests/deep/test_round2_flow.py::test_R2B_013_outline_chapter_id_must_be_readable_by_the_narration_parser`. Confirmed (hand run, 5 ids).

### R2B-014 (major) A damaged file in one project answers 500 for the whole home list, the library list, or the script endpoints
- Steps: write into a project folder (valid JSON, wrong shape, or bytes that are not UTF-8): `project.json` = `[1]` / `null` / `3`; `script/brief_options.json` = `[1]` / `3`; `source/payne_gae_004.txt` = `\xff\xfe...`.
- Expected: that project reports a problem (409 `{detail, data_error}` like timing/storyboard now do; skipped or flagged in the lists); other projects and the lists keep working.
- Actual: `GET /api/projects` -> 500 `internal error (AttributeError)` for ALL projects, and `GET /api/library/artworks` and `GET /api/library/artworks/<key>` -> 500 for everyone (project index reads every `project.json`); `brief_options.json` = `[1]` -> 500 on `/brief`, `/outline`, `/narration`, `/prompt`, `PUT /brief/options`, `outline/generate`, `narration/approve`; a non-UTF-8 source text -> 500 `UnicodeDecodeError` on `/brief`, `/outline`, `/narration`, `/prompt`. (Empty, truncated, binary or text `project.json` and corrupt outline/narration/storyboard/timing are handled; 33 distinct 500s over 8 files x 6 corruptions in the sweep.)
- Cause: `bti/editor/app.py:314` (`pj.get` after a `try` that only guards the read), `bti/editor/library_api.py:61` `project_index`, `bti/script/brief.py:88-93` `load_options`, `bti/script/brief.py:77` `_resolve_dossier` (strict UTF-8 read of source text).
- Tests: `tests/deep/test_round2_input.py::test_R2B_014_one_project_json_of_the_wrong_shape_does_not_break_the_lists[*]`, `::test_R2B_014_damaged_script_inputs_are_409_not_500[*]`. Confirmed.

### R2B-015 (minor) TR-03 is still about 2.3-2.5x the warm cost of the reference techniques
See "B-028 numbers" below. When every technique is measured warm (best of 3 after one warm-up) TR-03 needs 1.49-1.7 s for the 3 s / 640 px / 15 fps preview, the median of the five references 0.64-0.65 s: ratio 2.29-2.48 in 5 of 5 runs, over the 2.2 limit decided in round 1. `test_B028` passes because its references are measured once, cold (their median is then 0.86-1.07 s).
- Cause: `bti/engine/techniques/transitions_extra.py` (TR-03 renders two shots for the whole 3.2 s transition; FIXES says inherent).
- Test: `tests/deep/test_round2_engine.py::test_R2B_015_tr03_preview_is_not_an_outlier_when_the_references_are_warm` (fails 2.33x seen once more inside the test). If the owner accepts that TR-03 is simply heavier, the right fix is to change the limit, not the engine. Confirmed (6 runs).

### R2B-016 (minor) `validate` lets nonsense fields through
- `canvas.fps = 0` (`fps` is never looked at; `w`/`h` other than 1920x1080 do warn), `shots[1].locked = "yes"` (a string where a boolean is the rule, and the page, proposals and the lock rule read it as truthy), and `shots[0].start = {"t": -3.0}` give no error and no warning. The same document saves.
- Expected: at least an `error` for `fps <= 0`, non-bool `locked`, negative start (B-002 family: "type-check every field").
- Cause: `bti/engine/storyboard.py:299-307` checks only `w`/`h` of the canvas (warn), never `fps`; `locked` is never checked; a negative start is only compared with the previous shot (`:432`).
- Test: `tests/deep/test_round2_engine.py::test_R2B_016_validate_checks_basic_fields_of_the_document`. Confirmed.

## B-028 numbers (task G)
Procedure: `.scratch/round2_backend/g.py` reproduces `test_B028_tr03_preview_is_not_an_outlier` on a fresh clone of `technique_lab` per run (same helpers, in-process TestClient, mock-free engine), then repeats the measurements warm. Seconds per 3 s preview at 640 px, 15 fps. Load average 2.2-9.3 (the browser agent was running), so absolute numbers are noisy.

| run | LAY-01 | CAM-03 | HI-01 | X-TR-01 | X-CARD-02 | median | TR-03 (x2) | test ratio | warm median | TR-03 warm best of 3 | warm ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.92 | 0.86 | 0.66 | 1.02 | 0.34 | 0.86 | 1.60, 1.50 | 1.74 | 0.65 | 1.49 | 2.29 |
| 1 | 1.10 | 0.86 | 0.66 | 1.02 | 0.34 | 0.86 | 1.61, 1.61 | 1.87 | 0.65 | 1.50 | 2.31 |
| 2 | 0.97 | 0.87 | 0.65 | 0.99 | 0.33 | 0.87 | 1.61, 1.61 | 1.85 | 0.65 | 1.61 | 2.48 |
| 3 | 1.21 | 1.18 | 0.76 | 1.07 | 0.34 | 1.07 | 1.71, 1.61 | 1.50 | 0.65 | 1.61 | 2.48 |
| 4 | 0.98 | 0.87 | 0.66 | 0.98 | 0.33 | 0.87 | 1.60, 1.49 | 1.71 | 0.65 | 1.61 | 2.29 |

Verdict: both. TR-03 IS slower than twice the others once everything is warm (1.5-1.6 s against 0.65 s, 2.3-2.5x). The test passes (1.5-1.9x in all five runs) only because each reference is timed ONCE and its first timing includes cold-cache cost (LAY-01 1.0-1.9 s cold against 0.54 s warm), which raises the median it compares against. The test therefore measures "TR-03 against a cold median", and flips whenever the references happen to be warm, as in a full-suite run where earlier tests already loaded the images and the process caches. It is a noisy test around a real, small excess; not a one-off.

## Tried and found sound
- Journey on a fresh project from a library artwork (`bosch-the-garden-of-earthly-delights`): create, brief, prompt, outline generate (mock), approve, narration generate (mock), ops (split, merge, drop, insert, move), approve; `GET /pipeline` matched the files at each step (stage `selected` -> `outlined` -> `script`); order errors answered correctly (narration generate / approve before outline: 409/404; approve with wrong, missing or stale rev: 409 with the current rev; outline edit drops outline and narration approval and the stage returns to `selected`). Exceptions: R2B-001, R2B-010, R2B-013.
- Storyboard step on a clone of `arnolfini`: open, validate, save, approve, stale approve (409), frame, thumb, proposals list/get/apply (`accept` of every wrong type is 422; `all`, `[]` fine), preview job (`done`). Exception: R2B-002 (stage after edit).
- Parallel: 8 saves with one `base_rev` (1x 200, 7x 409, one history file); 6 simultaneous creates of one slug (1x 200, 5x 409); 4 creates of different slugs; 6 ops with one `base_rev` (1x 200, no duplicate beat id); two narration jobs on one project (200 + 409); one job on each of two projects; cancel of a running job, a second cancel (200), unknown job (404); polling `zzz`, `..%2f..`, `%00`, 5000 chars (404); a new job after cancel; delete during a running job (409, also right after cancel while the thread winds down; folder intact). Exception: R2B-005 (delete during saves).
- Restart (real server on port 8571, temp roots, hard `kill`): a running outline job is reported `error`/`interrupted` with the reason, the project's files unchanged, no `.tmp` left, no stale lock, a new job starts at once, narration and approvals unchanged. The server was stopped; port 8560 was never touched. A preview job in flight is not covered by `/script/jobs`; by the code (`bti/editor/jobs.py:get`), `GET /api/jobs/<id>` for it gives `error`/`interrupted` the same way (read, not run).
- Broken input, 874 requests (19 nasty values x 46 write routes: None, bool, 0, -1, 1e308, 10**30, "", NUL, lone surrogate, control and bidi characters, 300 KB string, empty list/dict, nested list, `../`, absolute path, `__proto__`, 2000-deep dict, 50-item list): no write on any refused request, no leftover `.tmp`, nothing outside the project (a canary file next to `projects/` untouched). 500s found: R2B-006, 007, 008, 009.
- Path parameters (22 id forms x 26 routes): `..`, encoded `%2f`, `%2e%2e`, backslash, NUL, absolute, newline, 300 characters, unicode, `con`: all 404/422 except the 300-character case (R2B-009). `files/` traversals all 404.
- NaN / Infinity literals, not-JSON, list/string/number/empty bodies, duplicate keys, BOM: 422 or 200 as appropriate, no 500 (huge integers: R2B-008).
- Upload: traversal file name, NUL, 400-character name, unicode, no extension, double extension, HTML as `.png`, SVG, empty licence, 100 KB title: nothing written outside `media/`, no temp file left, keys unique. Exception: R2B-011.
- Corrupt files (6 corruptions x 8 files per project): empty, truncated, binary and text content of `project.json`, outline, narration, options, dossier: handled; wrong-shape JSON and non-UTF-8: R2B-014.
- 71 techniques: `/defaults` -> validate -> frame for plain defaults, required-only, no params, slots emptied, and each of the 766 params removed one at a time: 0 errors, 0 non-200 frames. 9300 single-param mutations: validate holes only in R2B-012; every mutation validate rejected gave 422 on the frame, never 500.
- Storyboard shape cases through validate/frame/preview (31): zero shots, one shot, end before start, zero-length shot, unordered shots, word anchor past the end / negative / float / mismatching text, overlay before its shot, overlay duration huge, bad technique, overlay technique as shot, missing asset, duplicate shot id, transition longer than the shot, camera zoom 0 / negative: refused with an error, a 422 for frame and preview, no 500. Exceptions: R2B-016.
- Engine CLI: `validate` of the real `technique_lab` copy (exit code), `still`/`render` on a 1 s range (valid), output paths. Exceptions: R2B-003, R2B-004.
- Restore of a corrupt storyboard and history pruning (60 approves in 2 s gave 6 history copies; the 3 earlier real versions survived).

## Not tested, and why
- Real model providers and the network (rules). Media search and import (network).
- Steps 3, 4 and 6 (placeholders). A narration job killed half way (only the outline job was killed) and a power-loss half write: writes are `mkstemp` + `os.replace`, read in code only.
- Machine-wide timing: loaded by the browser agent (load average 2-9); see the B-028 section.
