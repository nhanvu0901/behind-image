# Round 2 engine fixes

Engine fixer, 2026-11-16. Mock model only, no network. Nothing committed. Files edited: `bti/engine/**`, `style/gae/techniques.json`,
`style/gae/techniques.schema.json`, `tests/engine/**`, `tests/deep/test_round2_engine.py`, `tests/deep/test_bugs_storyboard.py` (B-028 only).

## Interface delivered (first)
- `bti.engine.errors.RenderError(DataError)`: `message`, `shot`, `overlay`, `technique`, `what="render"`, plus an extra `path` (`shots[3]`, `shots[3].overlays[1]`, `shots[3].transition_in`).
- `Project.draw_check(storyboard=None, width=320)` (`bti/engine/api.py`): one frame in the middle of every shot, of every overlay span and of every transition (frames closer than 1/15 s are drawn once). Issues: `{"level":"error","code":"undrawable","path","shot","message","args":{shot,technique,overlay}}`. Never raises for a technique failure; restores the caller's draft. A full pass over `technique_lab` (71 shots, 190 frames) takes about 9 s cold.
- Registry keys `pattern`, `pattern_hint` (Vietnamese), `min_items`, `max_items`, enforced in `registry.validate_params`; one more key, `numeric_only` (see R2B-012).
- Shared limits: `bti/engine/limits.py`.

## R2B-003, R2B-004: engine command line (fixed)
- Cause: no argument checks; `a.width or default` turned 0 into "not given"; no error handling around project, frame and file writes; `render_range` wrote to a dead ffmpeg pipe.
- Change: `bti/engine/__main__.py` (rewritten: usage errors exit 2 with one line, run-time errors exit 1 with one line, traceback only with `--debug`, accepted before or after the sub-command; all tests of numbers use `is None`); `bti/engine/scene.py` `render_range` (a broken pipe becomes `RuntimeError("ffmpeg failed ...")`, the partial file is deleted on any failure); `bti/engine/limits.py`.
- Rules: t, `--t0`, `--t1` finite and >= 0; `--t1 > --t0`; start at or past the end of the storyboard is an error for `still` and `render`; `--width` 64..1920 (same as `/frame`; the preview's 160..1280 is in `limits.py` too); `--fps` 1..30; `--threads` 0 = automatic (the default and the old meaning of "not given") or 1..64. A bad output type (`-o x.txt`), an unwritable folder, a missing project, a corrupt storyboard: one line, exit 1.
- Neighbours covered: `--quality final` defaults (1920, 30) applied only when the flag is None; `still` removes a half-written file; `validate` of a missing folder.
- Tests: `tests/deep/test_round2_cli.py` (4, pass). Open: none.

## R2B-006 (engine half): depth (fixed)
- `strip_derived` and `canonical` check depth first with an iterative walk (`storyboard.check_depth`, limit 64) and raise `DataError`; the walk itself never recurses on the input. Test: `tests/engine/test_draw_check.py::test_deep_documents_raise_data_error_not_recursion_error`.

## R2B-012: whatever validate accepts, the engine can draw (fixed)
- Cause: validate checked only the JSON type of `point`, `points`, `string` values, regions only on overlays, and nothing about format, counts or sizes.
- Changes:
  - `registry.check_problem` (new, `check_value` is a wrapper): `pattern` (string, text; every item of lines; line breaks collapsed first, as the renderer sees the value), `min_items`/`max_items` (points, lines), `numeric_only` (point, points), box must lie inside the 1920x1080 canvas and be >= 16 px (a fraction box [0.2,0.2,0.8,0.8] drew a 0x0 view), point coordinates within +-1e6, camera cx/cy within +-1e6 and zoom <= 1000, colour uses `fullmatch` (`"#aabbcc
"` used to pass).
  - `storyboard._validate`: a region name in a `point`/`points` value must exist on the asset in use, for shots as well as overlays (`check_regions`; items with no image yet stay "incomplete", not an error).
  - Registry data (`style/gae/techniques.json`, all 71 techniques read, all 4 string-like and 12 param types swept):
    - `numeric_only: true` on 20 params whose renderer reads numbers, not regions: LAY-06 strip_start, strip_step; AN-03 origins; AN-04 places, control; AN-06 shape_points; STATIC-06 from_point, to_point, control_point; DIA-01 axes_origin, axes_end, ray_origin; DIA-02 from_quad, to_quad; DIA-06 room_center, room_label_pos, uv_label_pos; SHORT-02 to_quad; X-ANN-05 points; X-CMP-01 swap_focus.
    - `pattern` + Vietnamese `pattern_hint`: CMP-02 stage_blur, stage_grey, stage_gain; CMP-03 versions (keyword list, 2..5); LAY-08 tiles (1..8 x 1..8); SHORT-01..05 frame_aspect (fixed list of ratios); DIA-03 layers; DIA-04 pieces; DIA-05 stages (kinds listed); HI-02 slide_from (directions listed, 1..12 items).
    - `min_items = max_items = 4`: DIA-02 from_quad, to_quad; SHORT-02 to_quad.
    - `line_px` min 1 (was 0, OpenCV refuses a line of thickness 0): CMP-05, X-CMP-02.
    - `style/gae/techniques.schema.json` allows the new keys.
  - Renderers made tolerant where the value is legal but a companion is not there yet: AN-04 `background: image` without a `map` slot draws the procedural map (was an exception); DIA-04 leaves out a piece whose region name the image does not define. Test `test_map_annotations_draw_on_the_chosen_background` changed (see below).
  - `aspect_wh` falls back to 9:16 for a ratio outside 1:4..4:1 (see R2B-017).
- Second line of defence: any failure while drawing is a `RenderError` (shot id, overlay id, technique id) from `frame_at` and `render_range` (`scene.render_error`, `CompiledShot.render/blend`); a shot that cannot even be built no longer hides the others (it raises when it is drawn). `draw_check` for approval.
- Permanent test: `tests/engine/test_validate_draw_sweep.py`: 71 techniques x every param x 12 types (number, enum, bool, string, text, color, point, points, lines, box, camera, asset: the registry has no technique with an `asset` param, so that type is exercised only through its value list and `check_problem`), every param one odd value at a time; validate no error implies the frame is drawn. **Marked slow** (about 4 minutes). Run: `.venv-engine/bin/python -m pytest tests/engine/test_validate_draw_sweep.py -q`; everything else: `-m "not slow"`. It has a memory watchdog (see R2B-017).
- Deliberate limit of the sweep: values at the edge of a declared number range are not probed (two in-range pixel values, such as a panel width and an x offset, can still overflow the canvas together). That case surfaces as `RenderError` and is caught at approval by `draw_check`. A first sweep that did probe the edges found hundreds of such combinations (CMP-02 alone 72).
- Also the sweep found, and these are fixed: camera zoom 1e9 or cx 1e12 (`rectangle` error), TR-03 box [0,0,1,1], DIA-01/02/06 fraction boxes, LAY-08/CMP-03/CMP-02 strings, DIA-03/04/05 lines.
- Tests that prove it: the 21 `tests/deep/test_round2_engine.py::test_R2B_012_*` cases (pass) and the sweep. Open: none known.

## R2B-015 (and B-028): TR-03 cost (fixed in the test; no engine change)
- Profile (warm, one frame inside the 3.2 s transition, 1080p): whole frame 32.5 ms = previous shot 11.3 ms + current shot 12.9 ms + blend 8.7 ms. The two shot renders are the inherent part; the blend is already strip-wise from round 1. I found no clear saving (the blend is 27 percent and is memory bound), so no engine change, as the contract asks.
- Both timing tests are replaced by `tests/deep/test_round2_engine.py::test_TR03_preview_is_faster_than_it_plays_and_not_an_outlier` (warm-up, best of three, five references). Numbers from the last run: TR-03 **1.49 s** for the 3 s preview (limit 3.0 s), reference warm median **0.64 s** (LAY-01 0.54, CAM-03 0.85, HI-01 0.65, X-TR-01 0.64, X-CARD-02 0.34), ratio **2.32** (limit 3.0). Earlier runs by the tester: 1.49-1.61 s, ratio 2.3-2.5.

- The test is now robust against machine load: up to three attempts, it stops at the first that meets both limits and on failure lists every attempt with `os.getloadavg()`. It carries the `timing` marker (registered in `tests/deep/conftest.py`); skip with `-m "not timing"`.
- The limits (3.0 s and 3.0x) and the engine are unchanged.

## R2B-016: validate checks every field of the document (fixed)
Added checks (all `error` unless noted): `canvas.fps` number 1..60; `canvas.w/h` positive numbers; `project`, `title` strings; `approvals` an object; shot and overlay `locked` boolean; `source` a string (not import/agent/human: **warn**, because the lab projects carry other labels); `note` string; `intent` string (unknown: warn, as before); shot start >= 0 (resolved time); overlay `id` a non-empty string; camera key `at.rel` 0..1; asset `title`/`artist`/`year` text or number, `credit` an object of strings, region `rx`/`ry` numbers >= 0, region `label` string; every param value (see R2B-012). Tests: `test_R2B_016_*` (pass), `tests/engine/test_issue_codes.py` (broken documents).
Open: `approvals.storyboard` content and `timing` are the editor's and the timing loader's business.

## R2B-017 (major): validate accepts a value that makes the engine allocate 24 GB (fixed)
- Cause: SHORT-02 `frame_aspect` is a free string; `"0:1"` gives a panel 2 px wide, and `vertical_panel` blurs an ambient fill `W * ph / pw` = 1 036 800 rows tall (24 GB of float32). Found by the sweep, which then ran the machine into swap.
- Fix, three layers: (1) registry: `frame_aspect` has a pattern listing the ratios, and every number param has both `min` and `max` (checked: 0 of 492 lack one); `aspect_wh` falls back to 9:16 outside 1:4..4:1. (2) `bti/engine/guard.py`: `cv2.resize`, `warpAffine` and `warpPerspective` are wrapped and, only while a frame is being drawn (`with guard.limited()` in `Scene.frame_at`), refuse a destination over 64 MP (see R2B-018; the first limit, 4 canvases, was too small) with `BufferTooLarge`, before allocating; `Img.view` and `text_layer` check their size too. The scene turns it into a `RenderError` that names the shot. The check is off outside drawing so media import and tools are not limited (the benchmark scripts resize to 4386x6000). (3) the sweep test: a background thread ends the process when its peak memory has grown by 2 GB, and says which mutation it was running.
- Tests: `tests/engine/test_guard.py` (extreme aspects refused by the registry, `aspect_wh` fallback, wrappers refuse before allocating and are off outside drawing, `RenderError` names shot and technique). Before the fix `"0:1"` was accepted by validate and drew with 24 GB (observed once, by the sweep); now validate refuses it. The sweep is clean (72 passed, peak memory never over the 2 GB growth limit).
- Known limit: numpy allocations that do not go through cv2 resize/warp (`np.zeros`, `np.mgrid` with a size from a param) are protected by the registry bounds, not by the guard.

## R2B-018 (major): the buffer guard refused a legitimate shot of the reference project (fixed)
- Cause: the R2B-017 limit (4 canvases, 8.3 MP) was a guess. The source image of `arnolfini` shot s0014 (2478 x 3721 px, 9.2 MP) is resized to build its pyramid, and that request was refused, so `draw_check` (and approval) failed on the finished video. The 276 engine tests had no test that drew the real projects.
- Evidence (instrumented guard; `arnolfini` 82 shots and `technique_lab` 71 shots at start, middle and end of every shot and inside every overlay: 693 frames; plus 984 draws of every number param of every technique at its registry min and max; nothing was refused at 64 MP):

| call site | largest request |
|---|---|
| `vfx.py:344` anti-aliased mask (at a registry maximum) | 15.4 MP (3924 x 3924) |
| `vfx.py:125` source pyramid (size of the file) | 9.2 MP (2478 x 3721) |
| `helpers.py:183` ambient fill of a 9:16 short | 6.6 MP (1920 x 3410) |
| `transitions_extra.py:93` | 3.0 MP |
| all full-canvas buffers (`vfx.py` view, text layer, warps; `_t2_common`, `highlights_extra`, `footage`) | 2.1 MP |
| `_t4_common`, `compare`, `layouts_grid`, `shorts` and the rest | under 0.9 MP |

- Limit chosen: **64 MP** (`guard.MAX_PIXELS = 64_000_000`): more than 4x the largest storyboard-driven request (15.4 MP). A float32 BGR buffer of 64 MP is about 770 MB. The R2B-017 case asked for 1920 x 1 036 800 = 2000 MP and is still refused. The separate per-side limit was dropped (the evidence has no side over 3924 px and the pixel limit already stops the long thin buffer).
- A source image's size comes from the file, not from the storyboard (a scan can be 100 MP), so building its pyramid now runs under `guard.unlimited()`.
- `draw_check` samples start, middle and end of every shot (just inside it, `min(0.05 s, duration / 10)`), each overlay span (start-inside is not needed: the overlay's middle) and each transition; times closer than one frame are drawn once. Time on this Mac (loaded by other agents): `arnolfini` 82 shots 6.3 s cold, 4.2 s with a warm scene cache (the single-sample version was 3.9 s); `technique_lab` 71 shots 10.4 s cold, 9.3 s warm (it has 3 overlays and 1 transition per many shots). Under the 8 s target for the reference project, so no thread pool.
- Data: `projects/technique_lab/storyboard.json`: 11 items had `"source": "lab"` (the request said 12) and one `"source": "manual"`; all changed to `agent` and `human`; no generator in `tools/` or `bti/` writes `lab` (the hits are cache keys and test labels in `labels.py`, `build_v2.py`, `tests/editor/test_backend_fixes.py`). `lab_annot`, `lab_diagrams`, `lab_text` still carry such labels on their shots, which validate warns about (`unknown_source`), not refuses; I did not edit them (outside the permission given).
- Tests: `tests/engine/test_real_projects_draw.py` (`draw_check` of `arnolfini`, `arnolfini_edit`, `technique_lab` is empty, skipped with a reason when the media folder is absent; the real sizes are admitted and the 2000 MP case refused; the three sample times). Sweep re-run: clean, memory watchdog on.

## R2U-002: issue codes (done)
Every issue from `validate` (engine) has `code` and `args`; `bti.engine.storyboard.ISSUE_CODES` lists all 99 codes. Test `tests/engine/test_issue_codes.py`: an AST scan that every code literal in `storyboard.py` and `registry.py` is in the table (and the reverse), and validate over 37 broken documents. `message` stays English. Value problems of a param carry `args.param` and `args.technique` besides their own keys.

## Needs the other agent
- `bti/editor/app.py` (preview limits `MAX_PREVIEW_S`, `MAX_PREVIEW_FRAMES`, `int_field(... 160, 1280 ...)`, `fps 1..30`) and `bti/editor/frames.py` (`clean_width` 64..1920) should import `bti.engine.limits` (`PREVIEW_MAX_SECONDS`, `PREVIEW_MAX_FRAMES`, `PREVIEW_WIDTH_MIN/MAX`, `FPS_MIN/MAX`, `FRAME_WIDTH_MIN/MAX`) so the two never drift. The values are the same today.
- Map `RenderError` to 422 `render_failed` (`shot`, `overlay`, `technique`) and run `draw_check` at approval, as in the contract. A `RenderError` can also come out of `/defaults`-independent paths such as `/thumb`.
- The `draw_check` issues and every `validate` issue now have `code` and `args`; the editor should pass them through unchanged (the new `DataError` from `strip_derived` for depth > 64 is a `DataError` with `what="storyboard"`).
- Design document: the sentence about registry params (section 7) and the validate rules (section 6) were not edited by me (not in my file list); the new keys are in `bti/engine/README.md` and the schema.

## Tests changed and why
- `tests/deep/test_round2_engine.py`: `test_R2B_015_...` replaced by `test_TR03_preview_is_faster_than_it_plays_and_not_an_outlier` (contract).
- `tests/deep/test_bugs_storyboard.py`: `test_B028_tr03_preview_is_not_an_outlier` removed (replaced by the test above; contract).
- `tests/engine/test_t2_annot_highlight.py::test_map_annotations_draw_on_the_chosen_background`: AN-04 `background: image` without a `map` slot expected an exception; it now draws the procedural map (validate must not accept what cannot be drawn, and the slot is not an error by "incomplete is not invalid"). The assertion is now that it equals the procedural frame.
- `tests/engine/conftest.py`: registers the `slow` marker.

## Consequences for the page
- Every validate issue has `code` and `args`; the table is below. Unknown codes should fall back to a general sentence naming the shot and the field.
- Strings with a `pattern` show `pattern_hint` (already Vietnamese) under the field; the same hint is the `message` of the issue with code `param_bad_form` (and `args.hint`). Points with `numeric_only` must not offer a region picker. `min_items`/`max_items` bound the number of items the list editor lets the owner add (DIA-02 and SHORT-02 quads: exactly 4).
- New value rules the form should mirror: box inside the canvas and at least 16 px; point coordinates within +-1e6; camera zoom up to 1000; `line_px` from 1; `canvas.fps` 1..60; shot start >= 0.
- A frame, thumb or preview can fail with a `RenderError` (shot, overlay, technique, `path`) even when validate is clean (two in-range values that overflow the canvas together); approval catches it with `draw_check`.

| code | meaning and `args` keys |
|---|---|
| `undrawable` | A technique cannot draw this shot, overlay or transition with the values it has (found by drawing a frame). args: shot, technique, overlay. |
| `incomplete` | A required slot or parameter is not set yet; saving is allowed, approval is not. args: what (slot|param), name, technique. |
| `not_an_object` | The storyboard document is not a JSON object. args: none. |
| `unreadable_structure` | The document has a structure the checks cannot read. args: error. |
| `wrong_schema` | `schema` is not the supported schema id. args: schema. |
| `canvas_not_object` | `canvas` is not an object. args: none. |
| `canvas_size` | canvas.w or canvas.h is not a positive number. args: field. |
| `canvas_fps` | canvas.fps is not a number in range. args: min, max. |
| `canvas_not_1080p` | The canvas is not 1920x1080 (warning). args: none. |
| `not_a_string` | A field that must be text is not. args: field. |
| `approvals_not_object` | `approvals` is not an object. args: none. |
| `project_name_differs` | `project` differs from the folder name (warning). args: project, folder. |
| `audio_invalid` | `audio` is not a file path. args: none. |
| `audio_outside_project` | `audio` points outside the project folder. args: file. |
| `audio_missing` | The audio file does not exist (warning). args: file. |
| `assets_not_object` | `assets` is not an object. args: none. |
| `asset_not_object` | An asset is not an object. args: none. |
| `asset_kind` | An asset's kind is not image, video or mask. args: none. |
| `asset_file_required` | An asset has no file. args: none. |
| `asset_file_outside_project` | An asset file path leaves the project. args: file. |
| `asset_file_missing` | An asset file does not exist. args: file. |
| `asset_file_unreadable` | An asset file is not a readable image. args: file. |
| `credit_not_object` | An asset's credit is not an object. args: none. |
| `asset_size` | An asset width/height is not a positive number. args: field. |
| `regions_not_object` | An asset's regions are not an object. args: none. |
| `region_xy` | A region has no numeric x and y. args: region. |
| `region_radius` | A region rx/ry is not a number >= 0. args: region, field. |
| `slots_not_object` | `slots` is not an object. args: none. |
| `unknown_slot` | A slot name the technique does not have. args: slot, technique, allowed. |
| `asset_undefined` | An asset key that is not in `assets`. args: asset. |
| `slot_asset_kind` | The asset in a slot has the wrong kind. args: slot, asset, takes, got. |
| `slot_not_object` | A slot value is not an object. args: slot. |
| `locked_not_bool` | `locked` is not true/false. args: none. |
| `unknown_source` | `source` is not import, agent or human (warning). args: source. |
| `unknown_intent` | `intent` is not in the fixed list (warning). args: intent. |
| `region_undefined` | A region name that the asset does not define. args: region, asset, param. |
| `end_required` | The `end` anchor is missing. args: none. |
| `anchor_invalid` | An anchor cannot be resolved (bad form, word index out of range, rel without a shot). args: none. |
| `end_fade` | end.fade_s is not a number >= 0. args: none. |
| `shots_not_list` | `shots` is not a list. args: none. |
| `no_shots` | The storyboard has no shot. args: none. |
| `start_required` | A start anchor is missing. args: none. |
| `rel_anchor_not_allowed` | A `rel` anchor is used outside a camera key. args: none. |
| `start_negative` | A shot starts before 0 s. args: start. |
| `first_shot_late` | The first shot starts after 0 s (warning). args: start. |
| `shot_not_object` | A shot is not an object. args: none. |
| `id_required` | A shot or overlay id is missing or empty. args: none. |
| `duplicate_shot_id` | Two shots share an id. args: id. |
| `stale_anchor` | A word anchor's text no longer matches the word at its index. args: none. |
| `shot_too_short` | A shot is shorter than the minimum. args: min, got. |
| `shots_out_of_order` | Shots are not in time order. args: none. |
| `unknown_technique` | The technique id is not in the registry. args: technique. |
| `wrong_technique_kind` | The technique has the wrong kind for its place. args: technique, kind, needs. |
| `technique_unavailable` | The technique exists but the engine cannot draw it yet. args: technique. |
| `camera_keys_order` | Camera keys are not in strictly increasing time order. args: none. |
| `camera_rel_range` | A camera key `rel` is outside 0..1. args: none. |
| `unknown_ease` | A camera key has an unknown ease name. args: ease. |
| `transition_dur` | A transition `dur` is not a number >= 0. args: none. |
| `transition_too_long` | A transition is longer than its shot. args: dur, shot_dur. |
| `first_shot_transition` | The first shot has a transition but nothing to come from (warning). args: none. |
| `overlays_not_list` | `overlays` is not a list. args: none. |
| `overlay_not_object` | An overlay is not an object. args: none. |
| `duplicate_overlay_id` | Two overlays of a shot share an id. args: id. |
| `label_without_position` | A label has neither `at` nor `screen` (warning). args: none. |
| `overlay_dur` | An overlay `dur` is not a number > 0. args: none. |
| `overlay_outside_shot` | An overlay starts or ends outside its shot. args: start|end, shot_start, shot_end. |
| `overlay_ends_before_start` | An overlay ends before it starts. args: none. |
| `end_before_last_start` | `end` is not after the last shot start. args: none. |
| `end_after_audio` | `end` is after the audio/timing duration (warning). args: end, duration. |
| `style_unusable` | The style id is unknown or unreadable. args: style. |
| `timing_unusable` | The timing file is missing, outside the project or malformed. args: file. |
| `params_not_object` | `params` is not an object. args: none. |
| `unknown_param` | A parameter the technique does not have. args: param, technique, allowed. |
| `param_null` | null where a value is required. args: param, technique. |
| `param_not_number` | A number parameter holds something else. args: param, technique. |
| `param_below_min` | A number is below the minimum. args: param, technique, min. |
| `param_above_max` | A number is above the maximum. args: param, technique, max. |
| `param_not_in_values` | The value is not one of the allowed values. args: param, technique, values. |
| `param_not_bool` | A true/false parameter holds something else. args: param, technique. |
| `param_not_string` | A text parameter holds something else. args: param, technique. |
| `param_bad_form` | A text value does not have the required form. args: param, technique, pattern, hint (Vietnamese sentence), index (line number for lists). |
| `param_bad_color` | Not a #rrggbb colour. args: param, technique. |
| `param_not_points` | A points parameter is not a list. args: param, technique. |
| `param_not_lines` | A lines parameter is not a list of strings. args: param, technique. |
| `param_item_count` | A list has too few or too many items. args: param, technique, min, max, got. |
| `param_bad_box` | A box is not [x0, y0, x1, y1]. args: param, technique. |
| `param_box_range` | A box leaves the canvas or is too small. args: param, technique, w, h, min_px. |
| `param_not_asset` | Not an asset key. args: param, technique. |
| `point_bad_form` | A point is neither a region name nor [x, y]. args: param, technique, index (in lists). |
| `point_empty_region` | An empty region name. args: param, technique, index. |
| `point_out_of_range` | A coordinate is absurdly large. args: param, technique, limit, index. |
| `point_numeric_only` | A region name where only [x, y] is accepted. args: param, technique, index. |
| `camera_empty` | The camera has no keys. args: param, technique. |
| `camera_key_not_object` | A camera key is not an object. args: param, technique, index. |
| `camera_key_missing_field` | A camera key lacks at, cx, cy or zoom. args: param, technique, index, field. |
| `camera_key_numbers` | A camera key cx/cy/zoom is not a number or zoom <= 0. args: param, technique, index. |
| `camera_key_range` | A camera key cx/cy/zoom is out of range. args: param, technique, index, limit, zoom_max. |
| `camera_key_anchor` | A camera key `at` is not an anchor. args: param, technique, index. |
