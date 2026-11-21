# Round 2: API fixes (answer to ROUND2_backend.md, API half)

Fixer: API, 2026-11-16. Mock model only, no network, no `agy`. Nothing committed. Regression tests: `tests/editor/test_round2_fixes.py` (39 cases) and one in `tests/script/test_antigravity.py`.

## Lock order (R2B-005), written in `bti/script/store.py` at the lock definitions
1. `store.script_lock(project)`  2. `common.save_lock(project)` (storyboard, now one per project instead of one global)  3. `ENGINE_LOCK`.
Who takes what: script routes and the model job (finishing a chapter) take 1. Storyboard routes (save, approve, restore, regions, proposals apply) take 2, then 3 inside. DELETE takes 1 then 2 (2 s each, else 409 `project_busy`, nothing removed). Previews hold their own render lock only. Nothing holds 3 and asks for 1 or 2. Every lock site was read: `script_api.py` (7 routes, via `hold(d)`), `generate.py` (2), `app.py` (5 routes via `slock(pid)`), `pipeline_api.py` delete.

## R2B-001 narration approval belongs to one outline: fixed
- Cause: approval compared only the narration hash and the current outline approval.
- Change: `store.py` `_approval` keeps `outline_sha1`; `approve()` records the outline's hash; new `narration_approval(n, o)` (the one decision) and `chapter_diff`. Used by `stage.py`, `pipeline_api._script_state`, `script_api.narr_payload`. `validate.py`: `unknown_chapter` is now an `error` (approval refused with `chapter_diff` in the 422; saving allowed). An old record without `outline_sha1` never stands.
- Fields the page can read in `GET /narration` (and PUT/ops/import/approve results): `approved` (the approval stands), `approval_reason` (`narration_edited` | `outline_not_approved` | `outline_changed` | null: why a recorded approval does not stand), `stale` (the outline changed after the narration was written, `source.outline_sha1` differs; information only), `outline_rev` (now), `approved_outline_rev` (the one the approval was given against, null when not approved), `chapter_diff {not_in_outline: [ids], missing_in_narration: [ids]}`. Pipeline step `script` detail says "Dàn ý đã đổi sau khi duyệt lời dẫn" for `outline_changed`.
- Tests: deep `test_R2B_001...`; editor `test_approval_record_holds_both_hashes...`, `test_old_record_without...`, `test_small_outline_edit_costs_one_reapproval...`, `test_approval_is_refused_for_chapters_that_differ...`.

## R2B-002 one function for the storyboard approval: fixed
`common.storyboard_approval(sb)` -> `none|fresh|stale`. Called by `library/projects.infer_stage` (home list, library index, `stage_of`) and `pipeline_api._storyboard_state`. Stale gives stage `storyboard`. No other place reads `approvals` (grep). Tests: deep `test_R2B_002...`, editor `test_stage_follows_the_storyboard_approval_everywhere`.

## R2B-005 delete and saves: fixed
- Cause: delete took no lock; `write_json_atomic` re-created the folder.
- Change: `DELETE` takes both locks (2 s, else 409 `project_busy`), re-checks existence and jobs under them, renames the folder to `.deleting-<pid>-<id>` in one atomic step (slug free at once, never a ghost), forgets both lock objects and engine caches, then deletes the renamed folder (retry; leftovers swept on the next delete). Writers: `script_api.hold(d)` re-checks existence after taking the lock (404); `make_parent(path, levels)` in `store.py` never creates the project folder (`ProjectGone`, a `FileNotFoundError`, mapped to 404); used by `store.write_*`, `common.write_json_atomic`, job records (`runner.write_record`), previews (`jobs.render_preview`), frame cache, thumbs, uploads dir, waveform cache. Storyboard routes re-check through `saved_storyboard`/`pdir` under the lock. `_any_error` turns a `FileNotFoundError` into 404 when the project folder in the URL is gone.
- Stress: `test_delete_stress_only_200_404_409_and_no_ghost` (12 trials by default; `BTI_STRESS_TRIALS=200` for the long run). Result of the 200-trial run: see "Results" below.
- Left open: a media import/upload that is already past its checks when the delete renames the folder can still write `media/` through `bti.media` (the module makes its own folders; its standalone tests need that). Two waiters on an old lock object could in theory both write if the slug is re-created within microseconds.

## R2B-006 depth limit: fixed (API half)
`common.DepthLimitMiddleware` (pure ASGI, added in `create_app`): for POST/PUT/PATCH with a JSON content type, an iterative byte scan (strings skipped) answers 422 `{detail, code: "too_deep"}` for nesting over 40, before any route or walker. Test: `test_depth_limit_is_one_shared_check_before_the_routes`, deep `test_R2B_006`.

## R2B-007, 008, 009, 011 input at the edge: fixed
Helpers in `common.py`: `finite_number(v, name, lo, hi, integer=, default=)` (bool, string, NaN, inf, huge ints, range), `string_list`, `text_field`, `id_field`, `segment_ok`, `safe_join` (segment length, any OSError/RuntimeError -> 404). `frames.clean_t/clean_width` and the preview's `int_field` use `finite_number` (messages kept so the page's error map still matches). Routes gone through: `/frame` GET+POST, `/thumb`, `/preview` (t0, t1, width, fps), `/waveform` (query bins checked), `/files/{path}`, `/style/{style}/previews/{file}`, SPA catch-all, `POST /api/library/projects` (work_ids, exclude, slug, artwork_key; also in `create_project`), `/api/library/artworks/{key}`, `.../source/{name}`, `/narration/generate` chapters, outline/narration `rev` and `text` fields, `PUT regions`. `create_project` now makes its folder exclusively (two creates of one slug: 409, never 500). Upload without title: `title_from_filename` (stem of the client name, cleaned) in `app.py`; `bti.media.api.add_upload` also accepts `meta.original_name`. Tests: editor `test_every_number_route...`, `test_library_create_lists_are_checked`, `test_long_segments_are_404_everywhere`, `test_upload_without_a_title...`, helper unit tests; deep R2B-007/008/009/011.

## R2B-010, 013 ids and enums: fixed
`store.doc_problem` (PUT, import, and the parsers via `parse.py` which now run it on what they built, so a model's output is checked too): chapter id `c\d{1,6}` (`CHAPTER_ID_RE`, shared with `parse.CH_ID_RE` through `CHAPTER_ID_SRC`), beat id `b\d{1,8}`, unique in the whole narration, chapter ids unique per document; `role` in `ROLES`, `card` and `locked` booleans, `certainty` in `CERTAINTY`, fact/hook strings and lists, `hook_choice`, `project/title/language`, all numbers finite. Nothing coerced. Tests: `test_chapter_and_beat_ids_enums_and_flags_are_checked`, `test_outline_enums_and_numbers_are_checked`, deep R2B-010/013.

## R2B-012 API half: fixed
`RenderError` -> 422 `{detail, code: "render_failed", shot, overlay, technique}` on `/frame` GET and POST, `/thumb` (app handler plus `guarded`, which adds `issues` when the draft has errors) and as preview job error (`error`, `error_code`, `shot`, `overlay`, `technique` in `GET /api/jobs/{id}`). `POST /approve` runs `draw_check` after validate and the incomplete check; `undrawable` issues refuse with 422 `{detail, issues (all + undrawable), undrawable: true, code: "undrawable"}`. The stub engine got a no-op `draw_check`. Tests: `test_render_error_is_422...`, `test_approve_runs_draw_check...`. Engine half (registry patterns, sweep) is the other agent's.

## R2B-014 one damaged project: fixed
Rule: a file that is there but unreadable or of the wrong shape is a named 409, never a silent default and never a 500; lists skip or flag.
Files gone through (every JSON or text file a list, index or script route reads): `project.json` (home list row with `data_error`, `stage: null`; library index skips; pipeline/script routes 409 `data_error: "project"`), `storyboard.json` (already), `timing.json` (list, try), `script/outline.json`, `narration.json` (`DocumentCorrupt`, already), `script/brief_options.json` (409 `script`; `PUT /brief/options` replaces a damaged file, so the owner can repair it), `source/dossier.json` and `project.json` field shapes (409 `source` / `project`), `source/*.txt` not UTF-8 (409 `source`, strict, no replacement), `library/books/*/book.json`, `overrides/books.json` (409 `library`), library `dossier.json` of an artwork (that row falls back to the catalogue with `data_error`; the detail route is 409 `library`), `artworks.json`, source text endpoint, `media/index.json` (wrong shape set aside, new index), proposals (round 1), job records (already tolerant), history copies (already). Any other exception inside one folder of `GET /api/projects` becomes that folder's `data_error` row. `build_brief` turns a wrong-typed field deep in a data file into 409 `project`. New `data_error` values: `project`, `source`, `library`. Tests: `test_damaged_project_json_is_a_row_not_a_500`, `test_damaged_script_inputs_are_409_naming_the_file`, `test_damaged_outline_or_media_index...`, `test_damaged_dossier_in_the_library...`, deep R2B-014.

## Model list (analyst's addition)
`GET /api/models`: the expanded `agy models` list is cached 10 minutes in the process, `?refresh=1` forces a call; the CLI call has an 8 s limit (`antigravity.LIST_TIMEOUT_S`); on failure or timeout the answer is 200 with the configured entries and the antigravity entry has `agy: {ok: false, reason: "timeout"|"config"|"auth"|...}` plus `enabled: false` and `message`; failure cached 1 minute (`FAIL_SECONDS`). Two requests at once make one call (the cache lock is held during the call). Every antigravity entry carries `agy: {ok, reason}`. Test: `test_models_list_is_cached_single_flight_and_failure_is_a_field` (patched `list_models`, no real CLI).

## Residual 1: media writes against a deleted project: fixed
- `bti.media` got `require_root` (default False, so the stand-alone tests keep their behaviour): `import_candidate(..., require_root=)`, `add_upload(..., require_root=)`, `assets.media_dir/save_index/register(..., require_root)`, `_io.write_json_atomic(parents=)`, and a context variable `http.NO_NEW_PARENTS` that makes `download_file` skip `mkdir(parents=True)`. With it the project folder must exist, only `media/` is made, and a project deleted meanwhile gives `FileNotFoundError` (404). A failed upload removes the file it copied. The editor adapter always passes `require_root=True`; the stub path creates only `media/`.
- The editor routes (`assets/import`, `assets/upload`) hold no lock during the network or transfer work. Afterwards `confirm_alive(d)` takes script lock then storyboard lock, checks the project exists, and if not drops the lock objects and answers 404 (what was written went away with the renamed folder; nothing can re-create it).
- Test: `test_upload_and_import_racing_a_delete_answer_404_and_leave_nothing` (a slowed media call, delete in between; asserts 404, no folder, no trash, slug free). 50 trials run (`BTI_MEDIA_TRIALS=50`): 50 passed. Plus `test_media_facade_default_still_creates_folders_and_require_root_never_does`.
- Test fakes in `tests/editor/test_api.py::test_real_media_exceptions_are_translated` now accept `**kw` (the adapter passes `require_root`).

## Residual 2: damaged project.json and `protected`: fixed
`DELETE` with a project.json that exists but is unreadable or not an object: 409 `{detail (names the folder, says project.json is damaged), data_error: "project", code: "project_file_damaged"}`, nothing removed. Tests for `[1]`, `null`, truncated JSON and non-UTF-8. A MISSING project.json is not damaged: such projects (imported ones, lab clones) are deletable today and existing tests rely on it, so delete is allowed (`test_delete_without_a_project_file_is_allowed`). Objection to the analyst's wording ("a missing file" refused): refusing would make every project without project.json undeletable.

## Needs the other agent
`POST /approve` on a clone of `projects/arnolfini` is now refused 422 `undrawable` because the engine's `draw_check` reports `shots[13]` (s0014, X-LAY-01): "a resized picture of 2478 x 3721 px is larger than the engine allows (8294400 px)". The reference project was approvable before, so either the engine limit or `draw_check` is wrong for a picture that draws fine in `/frame`. It fails `tests/deep/test_round2_flow.py::test_R2B_002...`, `tests/deep/test_sound.py::test_approval_is_server_owned_and_tied_to_rev` and my `test_stage_follows_the_storyboard_approval_everywhere`. Nothing for me to change in my files.

## (earlier) Needs the other agent
Nothing missing: `RenderError`, `draw_check` exist and are used. Issues from `validate` are passed through unchanged (new `code`/`args` keys survive).

## Tests changed and why
- `tests/script/test_validate.py::test_warning_unknown_fact_and_no_show_and_unknown_chapter` renamed `test_unknown_fact_and_no_show_are_warnings_unknown_chapter_is_an_error`: the contract (R2B-001) makes `unknown_chapter` an error. The last assertion (`not blocking or words_under`) was replaced by the `unknown_chapter` error check.
- No round-2 test was changed.

## Consequences for the page
- Home list: rows may be `{id, title: <folder>, data_error, stage: null}` (damaged); show as damaged, no link into the project steps.
- Script page: read `approval_reason`, `stale`, `chapter_diff`, `approved_outline_rev` (above) to explain why a narration is no longer approved; the 422 of narration approve carries `chapter_diff`. The badge "duyệt đã cũ" currently shows for `stale && !approved`; `stale` now means "outline changed since written", so use `approval_reason` for the badge. New issue level: `unknown_chapter` is `error`.
- 409 `data_error` values `project`, `source`, `library` (errmsg map).
- 422 `code: "too_deep"`, 409 `code: "project_busy"` on delete (retry), 422 `code: "undrawable"` with `undrawable: true` on approve (list `issues` with code `undrawable`), 422 `render_failed` on `/frame` and `/thumb`, preview job fields `error_code`, `shot`, `overlay`, `technique`.
- `GET /api/models` antigravity entries have `agy: {ok, reason}`; `?refresh=1` re-queries; do not call it on every visit.
- Artwork rows may have `data_error`.

## Consequences for the page (additions)
- DELETE can answer 409 `code: "project_file_damaged"` with `data_error: "project"`: tell the owner to repair or remove the folder by hand.
- Import and upload can answer 404 `project not found` when the project is deleted while they run.

## Results
- `tests/script tests/editor tests/library`: 441 passed. `tests/media`: 90 passed.
- `tests/deep`: 188 passed, 7 failed, all in `tests/deep/test_round2_engine.py` (engine fixer's: `test_R2B_012...[LAY-08-tiles, DIA-02-to_quad, CMP-02-stage_blur, stage_grey, stage_gain, CMP-03-versions]` need the registry patterns, `test_R2B_015` TR-03 timing). All the API-owned round 2 tests pass.
- Delete stress, 200 trials (`BTI_STRESS_TRIALS=200`): passed; only 200 or 409 for delete, only 200/404/409 for saves, no 500, no ghost folder, slug free, no trash left.

## Shared limits
- `bti/editor/app.py` and `frames.py` import `bti.engine.limits` for `/frame`, `/thumb` (width) and `/preview` (width, fps, seconds, frames); the local numbers are gone. The only editor-owned number is `frames.T_MAX_SECONDS = 86400` (the engine's limits file has no time range).
- Test `test_http_limits_are_the_engine_limits` checks `frames.limits is bti.engine.limits` and that each limit's edge is refused over HTTP.
