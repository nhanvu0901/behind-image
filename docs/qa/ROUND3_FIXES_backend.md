# Round 3 fixes, backend

## R3B-001 `POST /approve` held `ENGINE_LOCK` for the whole draw check
- Cause: `app.py` ran `p.draw_check(saved)` inside `with ENGINE_LOCK` (6 s on 82 shots), and `GET /api/projects/{pid}` needs the same lock.
- Change:
  - `bti/engine/api.py` `Project.draw_check_iter` (new generator): the draft is swapped in only to compile the scene (inside step one, restored before it yields). The samples are drawn from the compiled scene, which does not read the draft, so no draft state is left set between steps. It yields after the compile and after every sample, and returns the issues. `draw_check` is now a wrapper that drains it (same result, same draft restore).
  - `bti/editor/engine_adapter.py` `draw_check_stepwise`: takes `ENGINE_LOCK` for one `next()` at a time, then sleeps 1 ms with the lock free. The pause is needed because an `RLock` is not fair: without it the approving thread re-took the lock before a waiter woke (measured: a concurrent GET still waited 3.6 s with no pause).
  - `bti/editor/app.py` approve now calls `draw_check_stepwise`. The project stays protected by `slock(pid)` for the whole approval, so a save of the same project is still refused or waits as before.
  - `bti/editor/engine_stub.py`: `draw_check_iter` (no-op) for the stub.
- Other `ENGINE_LOCK` holders audited: `state`, `save_result`, `commit` (validate, then save), `post_validate`, `post_defaults`, `get_thumb` (`resolve`), `guarded`, `render_jpeg` (one frame), `load_style`, `project()`/`preview_project()` (open). Each holds it for one short operation, never in a loop. Previews use a second engine instance with its own lock and never take `ENGINE_LOCK`. Nothing else needed changing.
- Numbers (arnolfini, 82 shots, one 301-step run): approval alone 6.0 s; approval with another project polled every 0.15 s: 6.5 s (+8%). `GET /api/projects/technique_lab` during it: median about 0.045 s, worst 0.7 s (the 0.9 s compile step of the scene, which is one step). A `/frame` of another project: median under 0.05 s. Longest step otherwise 0.23 s.
- Tests: `tests/editor/test_round3_approve_lock.py` (own timing test on arnolfini, median of several GET and /frame under 0.5 s). `tests/editor/test_round2_fixes.py::test_approve_runs_draw_check_and_lists_the_undrawable_items` now patches `draw_check_iter` instead of `draw_check` (the approve path uses the iterator; minimal change). The tester's `test_R3B_001_approve_does_not_block_other_projects` is not in the checkout yet, so I did not run it.
- Open: the compile step (about 0.9 s on arnolfini) is still one hold of the lock.




## Batch 2

### R3U-002 chapter differences can be resolved through the API
- `bti/script/ops.py`: `drop_chapter` (422 for an unknown id; refused while a beat is locked, like `drop`) and `add_chapter` (only an outline chapter the narration lacks, at the outline's position, outline title, no beats; else 422); `apply_op(n, op, outline)`. `bti/editor/script_api.py` passes the outline; request/answer shape, `base_rev` and locking are those of the other operations.
- `validate.py`: `empty_chapter` (error, `args.chapter`) for an outline chapter present with no beat that has text; `chapter_missing` is now only for an absent chapter (test_validate updated).
- `store.chapter_diff` is extended (same dict): `not_in_outline`, `missing_in_narration` (absent), new `empty_in_narration`, new `order` (R3B-007).
- Neighbours: an emptied chapter the outline lacks is removed by `drop_chapter`; a model job for `chapters: ["c04"]` works when the chapter is absent or empty; stage, `GET /pipeline` and the list agree after each step. Tests: `tests/editor/test_round2_fixes.py` (`test_drop_chapter_*`, `test_an_emptied_chapter_*`, `test_locked_beat_*`, `test_add_chapter_*`).

### R3U-003 and `args.index`
- `args.asset` now on: asset_not_object, asset_kind, asset_file_required, asset_file_outside_project, asset_file_missing, asset_file_unreadable, credit_not_object, asset_size, regions_not_object, region_xy, region_radius, not_a_string (when the field belongs to an asset), plus the ones that already had it (asset_undefined, slot_asset_kind, region_undefined). `undrawable` carries `args.asset` (null when not about an asset): `RenderError.asset` is set from the asset key tagged on the load failure (`base.tag_asset` in `Ctx.asset`/`image`, `helpers._mask_img`, `video_frame`), also in the `render_failed` body, the preview job record and `GET /api/jobs/{id}` (`asset`). `param_not_asset` has no key (the value is not one) and is unchanged.
- `args.index` (+ `param`) now on camera keys: camera_keys_order, camera_rel_range, unknown_ease, stale_anchor and anchor_invalid when about a camera key (the camera_key_* codes already had it). The ISSUE_CODES args text was updated; tests: `tests/engine/test_issue_codes.py`, `test_draw_check.py`.

## Batch 3

### R3B-002 depth scan
- `bti/editor/common.py` `DepthLimitMiddleware`: whole strings are matched with possessive quantifiers (no backtracking), removed, the remaining brackets counted with `itertools.accumulate`; text after an unterminated string is not scanned. The async path works in chunks of about 256 KB and yields to the event loop between them (longest step 9 ms). Body over 8 MB (`MAX_JSON_BODY_BYTES`) is 413 `too_large` before parsing.
- Timings: 160 KB hostile body (the tester's shape) 1.4 ms (was 59 s); 8 MB hostile 0.13 s total in many small steps; legitimate 2.7 MB storyboard 66 ms (about 48 ms per 2 MB); event loop never stalled more than 9 ms.
- Other scanners, found by a timing fuzz of parse_script, parse_outline, paragraph_listing, markup_in, fold, tokens, sentences on 20 hostile shapes: `HEAD_RE` was cubic on a run of spaces (now a function, same groups), `FINAL_RE`/`OUTLINE_RE` were quadratic on blank lines (`[\W_]` ate newlines), `WORDCOUNT_LINE` and the `hook`/`facts`/`chapters` label patterns had `\s*:?\s*` (quadratic), the stage-direction markup pattern was quadratic on `(pause(pause...` (bounded to 200 characters). `textfold` and the path helpers use no backtracking patterns. Tests: `tests/editor/test_round3_scanners.py`.

### R3B-012, R3B-013 model list
- `antigravity.list_models` decodes bytes leniently, drops slugs with control characters, `..` or separators, lists a duplicate once. `models.agy_models` never raises, holds no lock while the CLI runs (single flight by an event; waiters hold nothing), caches every failure for a minute. `models.resolve(id)` (used by `model_for` and `get_model`): a non-Antigravity model never calls the CLI; `<agy id>:<slug>` is checked against the list only while it is fresh, otherwise the spec is built from the slug and a wrong slug fails when the job runs.

### R3B-007 order
- `chapter_diff.order` (true when the chapters both documents share are in different order), validation error `chapter_order`, operation `{"op": "order_like_outline"}` (chapters the outline lacks keep their relative place at the end). Saving stays allowed. Test: `test_chapter_order_*`.

### R3B-003 to 006 one loader
- `store.read_file_text` (one reader: missing, folder, permission, not UTF-8, short reason without a path, nothing cached) under `read_object`, `read_text_strict` (a missing source is now a 409 too), `read_paste` (still lenient on bad bytes, but an unreadable file is 409). A folder in place of `narration.json`/`outline.json` is 409 on read and save. Proposals, `check_readable`, library catalogue/dossier text, `pipeline_api` (`sources` not a list: 409 `data_error: "project"`) all answer 409 naming the file. `check_readable` now also checks the shape of `shots` and `overlays` (cached per file version), so a wrong type is a 409 with the restore hint even before the engine's own check. Works again after repair with no restart (tested).
- Not routed through the helper: `bti/engine/**` (other agent), `bti/media/_io.py` and the model JSON files (already guarded, only config).

### R3B-010 (editor half), R3B-011
- `ApiError.detail`, the DataError/RenderError/DocumentCorrupt/Library handlers and job errors are scrubbed of absolute paths (`common.scrub_paths`); render and audio 500s no longer carry exception text (the raw exception goes to the log).
- Upload: `confirm_alive` runs before the 422 about an unreadable image, so a delete that won the race answers 404.

## Needs the other agent
- R3B-010 engine half: `scene.render_error` still builds `"<Type>: <message>"` and the wrong exception name for an unreadable mask or video; the editor now only removes paths.
- R3B-003 engine half: `SB.resolve` should raise `DataError` for wrong types inside `shots`/`overlays` (the editor already answers 409 for a stored file of that shape).

## Consequences for the page
- `POST .../narration/ops`: new ops `drop_chapter {chapter}`, `add_chapter {chapter}`, `order_like_outline`.
- `chapter_diff` (in `GET /narration` and in the 422 of `/narration/approve`): `not_in_outline`, `missing_in_narration`, `empty_in_narration`, `order` (bool). Issues: `empty_chapter` and `chapter_order` (new codes, labels needed), `chapter_missing` now means "absent". The page must not show `stale` when `approved` is true.
- Storyboard issues: `args.asset`, `args.index` (with `args.param`); `undrawable.args.asset`; `asset` in `render_failed` bodies and job records.
- 413 `{code: "too_large"}` for a JSON body over 8 MB.

## Batch 4 (follow-ups from the engine report)

### Wrong shapes through every route
- The engine's `check_shape` DataError is answered 409 `data_error` by the existing handlers (paths scrubbed); `check_readable` (cached per file version) also catches the stored file with the restore hint. `tests/editor/test_round3_shapes.py` feeds the engine fixer's 25 mutations (imported from `tests/engine/test_round3_engine.py`) to GET project, `/thumb`, `/frame`, `/pipeline`, `/validate`, `/proposals`, `/approve` and the home list: 404/409 (never 500), the list stays 200, and the project works again after repair without a restart. No route needed a code change beyond the earlier ones.

### Damaged uploads and imports
- `bti/media/imageinfo.py` `image_problem(path) -> (code, reason)`: `image_empty`, `image_unreadable`, `image_truncated` (header reads but the pixels do not decode). I kept an equivalent of the engine's `media_problem` in `bti/media` instead of importing the engine, because `bti.media` must not depend on the engine (layering: media is a lower facade); the rule is the same (header AND full decode). `ImageDamaged(ValueError)` carries the code.
- `POST /assets/upload` answers 422 `{detail, code, reason}`; `add_upload` and `import_candidate` raise `ImageDamaged` (the import deletes the downloaded file first), so `media/` and `cache/uploads` stay clean (tested for empty, garbage, truncated JPEG, truncated PNG, and a truncated download).

### Consequences for the page
- Upload/import refusals carry `code` (`image_empty`, `image_unreadable`, `image_truncated`) next to `detail`/`reason`; labels may be added.

## R3B-014 a save between the POST and the job thread was taken as the job's own base
- Cause: `bti/script/generate.py:62` (`run_outline`) read `start_rev` (and `run_narration` its `start_locked`, line ~125) when the job THREAD began, not when the owner's request ran. A save that landed in that gap became the "base" and the job overwrote it without a conflict. Round 3 made the start of a job faster (no model list), which exposed it.
- Change: `outline_generate` and `narration_generate` (`bti/editor/script_api.py`) now fix the base inside the request before the job id is returned (`base_rev` of outline.json; `base_locked`, the beats locked at that moment) and pass it as data (`run_outline(..., base_rev=)`, `run_narration(..., base_locked=)`); the thread never re-reads it to decide about conflicts. The narration job's per-chapter rule already re-reads the CURRENT document under the lock on purpose. These two are the only jobs that write a document (imports are synchronous, under the script lock).
- Tests (no timing: the job thread is held at its first step until the test releases it): `test_an_outline_saved_between_the_post_and_the_job_thread_is_a_conflict` x30, `test_a_beat_locked_between_the_post_and_the_job_thread_is_not_overwritten`, and the old test `test_an_outline_saved_during_the_outline_job_is_not_overwritten` x30, in one pytest process.
