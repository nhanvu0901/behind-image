# Round 3 engine fixes

Engine fixer, 2026-11-16. No model call, no network. Nothing committed. Files edited: `bti/engine/**` (`storyboard.py`, `vfx.py`, `base.py`, `helpers.py`, `scene.py`, `api.py`, `techniques/layout.py`, `layouts_grid.py`, `compare.py`), `tests/engine/test_validate_draw_sweep.py`, new `tests/engine/test_round3_engine.py`, this file.

## R3B-003 (engine half): wrong types inside storyboard.json
- Cause: `SB.load` checked only the top-level object; `resolve` (and the scene) then called `.get` on a shot that is a string, on an `overlays` that is a string, and iterated a camera param that is a number.
- Change: `bti/engine/storyboard.py:87` `check_shape(doc)` (+ `_check_item`, `:117`) raises `DataError("storyboard.json is corrupt: shots[3].overlays must be a list", what="storyboard")` for a wrong TYPE at: top level, `canvas`, `end`, `approvals`, `assets` (and each asset, its `regions`, each region), `shots` (list), each shot, `start` / `end` / `params` / `slots` / each slot value of a shot or overlay, `overlays` (list) and each overlay, `transition_in` and its `params`, the `at` of a camera key. It is called from `load` (`:145`), so `open_project` and `Project._reload_if_changed` raise `DataError`, and from `resolve` (`:243`), so `Project.resolve`, `_scene`, `frame_at`, `render_range`, `draw_check` are covered (`draw_check` turns it into one `undrawable` issue). `resolve` also stops iterating a camera param that is not a list.
- `strip_derived` and `canonical` are generic walkers that never fail on a type (already so); `validate` never raises by contract and reports `shots_not_list`, `shot_not_object`, `overlays_not_list`, `slots_not_object`, `params_not_object`, `start_required`... for the same inputs, so editing drafts keep their 422 with issues. Only the loader and `resolve` raise.
- Missing keys and bad values are not this function's business (validate reports them): a shot without `start` still loads.
- Tests: `tests/engine/test_round3_engine.py::test_wrong_types_inside_are_a_data_error_never_an_attribute_error` (25 mutations: loader, `open_project`, `resolve` raise `DataError`; `canonical`, `strip_derived`, `validate` do not raise), `test_draw_check_of_a_wrong_shaped_draft_is_an_issue_not_an_exception`; `tests/deep/test_round3_backend.py::test_R3B_003_*` (3 cases) pass.

## R3B-008: bounds that validate accepts and the engine cannot draw
- Cause: the techniques wrote `f[y:y+h, x:x+w] = panel` with a box that leaves the canvas (shape mismatch, or a wrap-around for a negative start); the strip of X-ANN-01/02 got a negative height when `strip_y_bottom_pct < strip_y_top_pct`.
- Decision: the technique copes (a bound of the registry is something the editor offers on a slider; a panel half off the canvas is a legitimate look, so no bound is tightened). Nothing is clipped silently in the registry.
- Change: `bti/engine/vfx.py:357` `put(frame, x, y, img, alpha=None)` draws an image clipped to the canvas (outside part dropped, a box completely outside draws nothing, negative x/y safe, optional alpha blend). Used in LAY-01 (`techniques/layout.py`, replaces its own right-panel clipping), LAY-02/LAY-03/LAY-07 tiles (`layouts_grid.py`), CMP-01..04 and X-CMP-01 (`compare.py`). `vfx.py:270` `label_layer` returns a transparent 1x1 layer when the strip height is below 1 px (X-ANN-01/02: bottom edge above the top edge draws no strip).

| technique | param | old bound | new bound |
|---|---|---|---|
| LAY-01 | panel_w_px, panel_h_px, panel_y_px, left_x_px (max) | unchanged | technique fixed (clipped) |
| LAY-02 | tile_w_px, tile_h_px, margin_x_px, margin_y_px, gap_x_px, gap_y_px (max) | unchanged | technique fixed |
| LAY-03 | columns, col_w_px, col_h_px, gap_px, y_px (max) | unchanged | technique fixed |
| CMP-01, CMP-04, X-CMP-01 | panel_w/h/y, left_x, right_x (max) | unchanged | technique fixed |
| CMP-02 | stage_size_px, stage_pitch_px, stage_y_px (max) | unchanged | technique fixed |
| CMP-03 | panel_w/h/y, x0_px, pitch_px (max) | unchanged | technique fixed |
| X-ANN-01, X-ANN-02 | strip_y_top_pct (max), strip_y_bottom_pct (min) | unchanged | technique fixed (no strip drawn) |

No bound of the registry was changed; `style/gae/techniques.json` is untouched.
- Permanent sweep: `tests/engine/test_validate_draw_sweep.py::test_every_numeric_bound_and_default_draws[<tid>]` (one test per technique that has a number param: 61 of 71): for EVERY numeric param, the registry `min`, `max` and default (the other params at `default_params` of the editor, plus the reference configuration's value for params whose default is empty, such as a camera) must validate with no error and draw the middle frame at 160 px. A bound that validate refuses is also a failure. The sweep keeps the memory watchdog (autouse fixture, 2 GB growth limit).

## R3B-009: damaged media is found by validation
- Cause: `image_problem` only ran `PIL.Image.verify()` (header and chunk structure); a JPEG cut off part way still verifies, and OpenCV draws it half grey with only a stderr line. Videos were not checked at all.
- Change: `storyboard.py:298` `media_problem(path, kind)` (+ `_check_media`, `:321`): image and mask: header must read (`asset_file_unreadable`: zero bytes, not an image), then ALL pixel data must decode (`asset_file_truncated`; a JPEG is decoded at 1/8 scale through `draft`, which still reads every byte at a fraction of the cost); video: opens and gives a first frame (`asset_video_unreadable`). `image_problem` stays as a wrapper. The validate branch (asset check, `"asset_file_*"` calls) now also covers `kind: video`. Every issue is an `error` with `args = {file, asset}` and path `assets.<key>.file`. New codes are in `ISSUE_CODES`.
- Cache: `_MEDIA_OK` keyed by (path, mtime_ns, size, kind); a file is decoded once per version (limit 4000 entries, then cleared).
- Timing of `validate` on a copy of `arnolfini` (82 shots, 12 images), median of 15, same process: before (header check only) warm 2.35 ms, after warm 2.36 ms (no change). Cold (first validate after a file changed or a server start): before 18 ms, after 691 ms, once per file version (12 images, 0.64 s to decode).
- A cut PNG has no end marker and fails at the header check (`asset_file_unreadable`), not `asset_file_truncated`; both are errors with `args.asset`.
- Tests: `test_round3_engine.py`: `test_a_damaged_image_is_an_error_with_its_asset` (truncated, zero, garbage), `test_a_damaged_mask_is_an_error`, `test_a_video_that_cannot_be_opened_or_has_no_frame_is_an_error` (zero bytes, garbage, then a real file validates clean), `test_the_media_check_is_cached_by_path_size_and_mtime` (2 decodes, 5 further validates decode nothing, a changed file is decoded once), `test_every_new_code_is_documented`; `tests/engine/test_issue_codes.py` (the static scan: every code is documented and used) passes; `tests/deep/test_round3_backend.py::test_R3B_009_*` passes.

## R3B-010 (engine half): messages for the owner
- Cause: `scene.render_error` built `"%s: %s" % (type(exc).__name__, exc)`: raw exception text, the absolute path inside it, and the wrong class (`cv2.imread` returns None, so a zero-byte image was an `AssertionError`; mask and video raised `FileNotFoundError(path)` for a file that exists).
- Change: `scene.py:34` `_cause_sentence` and `:55` `render_error`: the message is `shot s0001 (CAM-01) cannot be drawn: <one sentence>`, where the sentence is `the image media/a.jpg is missing`, `the image|mask|video media/a.jpg cannot be read (it is empty or damaged)`, `the asset 'K' is not defined`, the guard's own sentence for a buffer over the limit, the region sentence for an undefined region, else `the values of this item cannot be drawn together`. The file, kind and missing/damaged are recorded on the exception by `base.py:93` `tag_asset(exc, key, ctx)` (project-relative path from `assets[key].file`; existence tested only on failure). The original exception stays `__cause__` and is logged (`logging.getLogger("bti.engine").warning("render failed at ...", exc_info=...)`). `api.py` `draw_check` fallbacks (`cannot be compiled`, `cannot be drawn`) also lost their `Type: text` and log instead.
- Tests: `test_round3_engine.py::test_message_of_a_zero_byte_image_is_one_sentence_without_the_server_path` (also asserts `__cause__` and the log record), `test_message_of_a_missing_file_says_missing`, `test_message_of_a_damaged_mask_and_video_names_the_right_kind_and_not_a_missing_file`, `test_a_technique_failure_with_a_raw_exception_shows_no_exception_text`; `tests/deep/test_round3_backend.py::test_R3B_010_*` passes.

## Tests run
- Full sweep file `tests/engine/test_validate_draw_sweep.py` (run once, at the end): 133 passed in 252 s (1 coverage test + 71 odd-value + 61 numeric-bound).
- `tests/engine -m "not slow"`: 251 passed before the last test additions; `tests/engine/test_round3_engine.py`: 39 passed; `tests/engine/test_real_projects_draw.py`: 5 passed; `tests/deep/test_round3_backend.py -k R3B_003/008/009/010`: 14 passed; `tests/deep/test_round2_engine.py`: passed.

## Needs the other agent
- Backend: `DataError` from `SB.load` / `open_project` / `Project.resolve` now also covers every wrong-typed field (message names the field, `what="storyboard"`); route it to 409 `data_error` as for a corrupt file. The shipped route already answers < 500 for the three R3B-003 cases.
- Backend: `RenderError.message` is now English, one sentence, paths relative to the project; `detail` of `render_failed` can pass it on as is.
- Backend: `bti/media` upload check (`readable_problem`) is not changed; it still uses its own header check, so a truncated upload is accepted and found afterwards by validate (`asset_file_truncated`).

## Consequences for the page
New issue codes (level `error`, path `assets.<key>.file`, `args = {file, asset}`):
- `asset_file_truncated`: an image or mask whose picture is cut off.
- `asset_video_unreadable`: a video that cannot be opened or has no frame.
- `asset_file_unreadable` (existing) now also covers a mask or image of zero bytes or a non-image, as before, plus an unreadable file.
The page already has `asset_file_unreadable` in `sbissues.js`; the two new codes need a Vietnamese sentence there (until then the generic fallback applies). `undrawable` issues keep their fields; their `message` is shorter and has no exception class or server path.
