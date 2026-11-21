# Backend fixes (answer to BUGS_backend.md)

Fixer: backend, 2026-11-16. Mock model only, no network, no `agy`. Nothing committed.

## Result

- 28 of 29 bugs fixed and verified by the tester's own test. 1 (B-016) is fixed in the product, but the tester's test cannot pass as written (see below).
- `tests/deep`: 142 passed, 1 failed (`test_B016`, contradictory test). Baseline was 48 failed, 95 passed.
- Normal suites: `tests/script tests/editor tests/library` 383 passed; `tests/media` 90 passed; `tests/engine` (.venv-engine) 190 passed; `node --test tests/editor_frontend` 99 passed.
- Regression tests added: `tests/editor/test_backend_fixes.py` (86 cases, real engine + mock model), `tests/engine/test_backend_fixes.py`, `tests/media/test_upload_readable.py`.
- Two fuzz runs (not kept as tests): 1333 wrong-typed bodies over 40 routes, and 980 single-field type mutations of a storyboard sent to validate, frame, preview and PUT. No 500, and every answer is JSON (or a JPEG). They found two more holes (a shot without a `start` anchor; `end.fade_s: null`), both fixed.

## Table

| Id | Severity | Root cause (one line) | Fix (one line) | Files | Test passes |
|---|---|---|---|---|---|
| B-001 | blocker | `validate` never checked `style`; the style was loaded after the write | `Project.validate` loads the style named by the document and reports an `error` on `style`; the document is validated before anything is written | engine/api.py, registry.py, errors.py | yes |
| B-002 | major | anchors and canvas read with `float()`/`.get` without type checks | `Timing.resolve` checks every number; `validate` type-checks canvas, shots, slots, overlays, ids, techniques; `validate` itself never raises (a structure it cannot read becomes an error issue) | engine/timing.py, storyboard.py, registry.py | yes |
| B-003 | blocker | `timing`, `audio`, `assets.*.file` not confined, `timing` not checked; save could write what cannot be opened | `safe_rel` (relative, no `..`, no backslash, resolved inside the project); `timing` must load and be well formed; asset files must exist, be inside the project and decode; every check runs before the write | engine/storyboard.py, api.py, timing.py | yes (3 params + 2 params) |
| B-004 | major | render errors surfaced as 500 with a Python message | invalid draft: `/preview` is refused up front (422 + issues); a failing `/frame` becomes 422 + issues when the draft has errors | editor/app.py, frames.py | yes |
| B-005 | major | PIL cannot measure multi-line text | `merged_params` collapses line breaks in `string` params and `lines` items | engine/registry.py | yes |
| B-006 | minor | overlay required slots never checked | `missing_of` checks required slots of shots and overlays; reported as `warn`+`incomplete` by the coordinator's rule 2 (test adjusted, see below) | engine/storyboard.py, scene.py | yes (adjusted) |
| B-007 | minor | STATIC-08 / X-ANN-03 defaults had neither `at` nor `screen` | default `screen = [960, 900]` when the context has no region; validation warns when a label has neither | engine/techniques/labels.py, storyboard.py | yes |
| B-008 | major | `body.get("outline") or {}` | `store.doc_problem` shape check; 422 without the document or with a wrong shape | script/store.py, editor/script_api.py | yes |
| B-009 | major | check and start of a job not atomic | `ScriptJobs.start(exclusive=True)` checks and registers under one lock; 409 for the others | script/runner.py, editor/script_api.py | yes |
| B-010 | minor | `apply_op` coerced with `str()`/`int()` | every field type-checked, nothing coerced; non-object op, non-list `ops` give 422 | script/ops.py, editor/script_api.py | yes |
| B-011 | minor | `save_options` ignored bad values | `check_options` refuses with the allowed range (422), nothing written | script/brief.py, editor/script_api.py | yes |
| B-012 | minor | `finish("error")` left chapters `running`/`pending` | in flight becomes `failed`, not reached becomes `skipped` | script/runner.py | yes |
| B-013 | major | import replaced locked beats | 409 with the locked ids and the paste kept, unless `force` | editor/script_api.py | yes |
| B-014 | minor | lone surrogate fails at write; strict UTF-8 read of the paste | global `UnicodeEncodeError` handler (422); `read_paste` replaces undecodable bytes; storyboard text is encoded before any write | editor/app.py, script/store.py, engine/storyboard.py | yes |
| B-015 | minor | narration approval ignored the outline approval | approval counts only while the outline is approved: `approved`/`stale` of `/narration`, pipeline step and stage | editor/script_api.py, pipeline_api.py, script/stage.py | yes |
| B-016 | major | delete knew nothing about jobs | delete refused (409 + `job_id`) while a script job or a preview of the project runs; one shared job registry | editor/pipeline_api.py, app.py | no, see "Not fixed" (own test in tests/editor passes) |
| B-017 | minor | hard-coded `PROTECTED` names | `"protected": true` in project.json, set for `arnolfini` and `technique_lab`; test adjusted | editor/pipeline_api.py, projects/*/project.json | yes (adjusted) |
| B-018 | major | proposals assumed well-shaped `assets`/`shots` | `proposals.shape_problem`; 422 for the bad file, the list skips it | editor/proposals.py, app.py | yes |
| B-019 | major | upload only checked the extension | `readable_problem` (non-empty, verifies, decodes completely) in the app and in `bti.media.api.add_upload`; validate flags unreadable files and width/height <= 0 | media/imageinfo.py, api.py, editor/app.py, engine/storyboard.py | yes |
| B-020 | minor | corrupt storyboard.json: bare 500, no way back | 409 JSON `{corrupt, restore_from}` for every reader; `POST .../storyboard/restore` brings back the newest good copy from history/ (damaged file moved aside) | editor/app.py, engine/storyboard.py | yes |
| B-021 | minor | history/ never pruned | newest 50 kept | engine/storyboard.py | yes |
| B-022 | major | cache key = storyboard revision only | key = storyboard + timing file + style files + asset files; used for cache file names and ETag; new `render_key` | editor/app.py, frames.py | yes |
| B-023 | minor | missing/corrupt timing: bare 500 | `DataError` -> 409 JSON `{detail, data_error:"timing"}`; `/validate` reports an issue on `timing` | engine/timing.py, errors.py, editor/app.py | yes |
| B-024 | minor | bad sizes in the `/defaults` context | sizes that are not positive finite numbers fall back to the saved storyboard | editor/app.py, engine/api.py | yes |
| B-025 | major | preview held `ENGINE_LOCK` for the whole render | previews run on a second engine instance with its own lock; the lock is never held; limit 30 s and 900 frames; tests | editor/engine_adapter.py, jobs.py, app.py | yes |
| B-026 | minor | `int(x or default)` | strict integer fields: `fps` 1..30, `width` 160..1280, 0 refused | editor/app.py | yes |
| B-027 | minor | jobs only in memory | records in `projects/<pid>/cache/jobs/<id>.json`; after a restart a job in flight reports `error`, `error_kind: "interrupted"` and the reason | script/runner.py, editor/jobs.py, script_api.py | yes |
| B-028 | minor | TR-03 blended the whole box in float and temporaries; two shots per frame all along the 3.2 s transition | per-wing strips with `cv2.blendLinear`, in-place box, cross-fade only outside the box; in-place backdrop blend in `compose_matte` (all techniques gain) | engine/techniques/transitions_extra.py, vfx.py | yes (borderline on a loaded machine: 2.0x vs limit 2.2x) |
| B-029 | minor | frame count from two rounded ends | `n = round((t1-t0)*fps)` | engine/scene.py | yes |

## Coordinator rules implemented

1. **Overlays have `slots`.** Existing projects already used `slots` on overlays (`technique_lab`, `lab_*`), so no old form needed a reader. Overlay slot names, asset keys and kinds are now validated. Section 6 of the editor-engine design has the sentence. `/defaults` returns `slots`. The exporter does not exist yet, so nothing to change there.
2. **Incomplete is not invalid.** Validation: `level: "warn"`, `code: "incomplete"`, path to the slots/params, message `incomplete: required slot 'mask' of HI-03 is not set`. Save allowed. `POST /approve` is refused (422, `incomplete: true`, `issues`, message lists them). Engine: an incomplete shot draws a neutral placeholder (technique id and what is missing); an incomplete overlay or transition is skipped. A required parameter without value is the same (previously an error).
3. **`/defaults` never fills a slot with the wrong kind**: only an `image` slot from the context image; `video` and `mask` slots only when the context names, for that slot, an asset of exactly that kind.
   Kind rules (an error when broken): `image` slot takes `image`; `mask*` slot takes `mask`; `video` slot takes `video` or `image` (the lab projects put a still in `LAY-04`'s `inset`; kept so they still load).

Tests of `tests/deep` adjusted to the rules (only these two, nothing weakened):
- `test_B006`: now expects a `warn` with `code: "incomplete"` naming `mask`, and no `error` (rule 2). Before: an `error`.
- `test_B017`: now expects the owner's rule: a clone of `technique_lab` (carries the flag) is 403; a `lab_*` project is deletable (200).

Normal-suite tests adjusted: `tests/editor/test_pipeline_api.py` (PROTECTED constant replaced by flag tests), `tests/editor/test_api.py` (immutable cache needs `render_key`), `tests/script/test_jobs.py` (B-012: chapter states `failed`/`skipped`).

## Siblings found and fixed

- Same "write a document that cannot be re-opened" family: `audio`, `assets.*.file`, overlay `slots.*.asset`, `params` of type `asset`, `canvas`, `end.fade_s`, `regions`, asset `width`/`height`, NaN and infinity (a NaN could be saved as `NaN`, now refused; `json.dumps(allow_nan=False)`), lone surrogates (encoded before the first write, so no stray history copy). `project` different from the folder name is a warning (clones of a project legitimately differ).
- Missing type checks: shots/overlays/slots/ids/techniques of the wrong type, missing `start` anchor, non-list `shots`/`overlays`; unhashable `technique` values (`spec()` returns None for a non-string).
- Same "coerced instead of refused" family as B-008/B-010/B-011: `text` and `notes` of import/generate must be strings; `chapters` must be a list of strings; `ops` must be a non-empty list.
- Same unhandled exception family: `UnicodeEncodeError` (any endpoint), any other exception (JSON 500 `internal error (<Type>)`, traceback in the log, no Python message), `DocumentCorrupt` (corrupt outline/narration file: 409 JSON; also used by pipeline and stage), `DataError`.
- The engine adapter used to cache a stub project forever when opening failed; damaged data (`DataError`) is no longer a reason to switch to the stub.
- Delete of a project forgets the cached engine objects (`forget_project`), previews too.
- Orphan risk of B-016 for previews as well as script jobs.

## API behaviour changes (for the front-end fixer)

- **Model required.** `POST /outline/generate` and `POST /narration/generate` without a non-empty string `model`: **400** `{detail: "model is required..."}`. Unknown model still 404.
- **`GET /api/projects/{pid}`** and the PUT result have a new field **`render_key`**. Frame and thumb URLs should use `rev=<render_key>` to be `immutable`; any other `rev` value (including the storyboard `rev`) is `private, no-cache` and revalidated by `ETag` (304 on `If-None-Match`). The ETag changes when timing, style or media change.
- **409 with `{detail, data_error}`** (new) when a document the project needs is unusable: `data_error: "timing"` (missing, corrupt, wrong shape), `"storyboard"`, `"script"` (outline/narration file), `"style"`. Previously a bare 500. Storyboard file corrupt: 409 `{detail, corrupt: true, restore_from: "<history file>" | null}` for every route that reads it.
- **`POST /api/projects/{pid}/storyboard/restore`** (new), body `{file?}`: brings the newest good copy from `history/` back when `storyboard.json` is unreadable or missing; the damaged file is moved to `storyboard.json.corrupt-<time>`. Returns `{restored_from, quarantined, rev}`. 409 when the file is healthy, 404 when no copy exists.
- **Validation issues** may carry `code: "incomplete"` (level `warn`). New error paths: `style`, `timing`, `audio`, `assets.K.file`, `assets.K.width|height`, `shots[i].start` (required), `*.slots.<name>` (kind and unknown asset).
- **`POST /approve`**: 422 also for incomplete items: `{detail: "cannot approve while items are incomplete: ...", issues, incomplete: true}`.
- **`POST /defaults`** returns `{params, slots}`. `context.assets[k].kind` is honoured; the saved storyboard's kinds are the fallback. Bad sizes no longer 500.
- **`POST /frame`** (draft): 422 `{detail, issues}` when the draft cannot be drawn and has errors (was 500). An incomplete shot answers 200 with a placeholder picture.
- **`POST /preview`**: 422 + `issues` for a document with errors; `width` 160..1280, `fps` 1..30 as integers (0, strings, booleans refused); at most **30 s** and **900 frames** (seconds x fps); previews never block stills or opening a project.
- **Script**:
  - `PUT /outline` and `PUT /narration` need the document in the right shape (`chapters` list of objects with string ids, beats of the right types): 422 `{detail}` naming the field.
  - `POST /narration/ops`: `ops` must be a non-empty list; each op an object with typed fields (422, nothing coerced).
  - `PUT /brief/options`: 422 with the allowed range (`target_words` 300..20000, `wps` 0.5..6, `include_low` list of strings, `notes` string up to 4000).
  - `POST /narration/import`: 409 `{detail, locked: ["c01:b0001", ...], kept: true}` when it would replace locked beats; send `force: true` to replace them. The pasted text is kept in `last_paste`.
  - `GET /narration`: `approved` is false and `stale` true when the outline approval was dropped; the pipeline step `script` is `current` then.
  - A job's chapters: `failed` for the one in flight and `skipped` for those not reached when the job ends in error.
  - 409 for a second start (`job_id` of the running one): now reliable under simultaneous requests.
- **Jobs survive a restart.** `GET /api/jobs/{id}` answers for jobs of an earlier run; one that was queued or running is reported `state: "error"`, `error_kind: "interrupted"`, with the reason. `GET /script/jobs` lists the jobs of this run only.
- **`DELETE /api/projects/{pid}`**: protection is the `protected` flag of `project.json` (403, `protected: true`; `GET /pipeline` shows `protected`); 409 while a script job (`job_id`) or a preview of the project is running. `lab_*`, `demo_*` and `arnolfini_edit` are deletable.
- **`POST /assets/upload`**: 422 for a file that is empty, truncated, damaged or not an image (nothing stored).
- **Proposals**: a malformed file is 422 on its own routes and skipped in the list.
- **Text**: any string with a lone surrogate is 422 `{detail}` on every route; a line break in a one-line text param is drawn as a space.
- **History**: the newest 50 copies are kept.
- Projects `arnolfini` and `technique_lab` now have a `project.json` (`protected`, `imported`); `imported: true` keeps them "imported" in the pipeline (no script steps).

## Not fixed, and why

- **B-016, the tester's test cannot pass as written.** It starts a slow job, calls delete, then asserts that delete answered 409 **and** that `projects/<pid>` does not exist afterwards. The folder was cloned by the fixture, and a refused delete (the fix, as the bug report asks) leaves it in place, so the second condition is always false. The product behaves as the report's "expected" says (409, no orphan, nothing re-created). Equivalent proof, passing: `tests/editor/test_backend_fixes.py::test_delete_is_refused_while_a_job_runs` (409 with `job_id`, folder intact, delete works after cancel). I left the deep test untouched, as instructed.
- **B-028 is a threshold test.** TR-03 went from about 3x the median to about 1.7-2.0x on a quiet or loaded machine; the limit is 2.2x. Before the last speed-ups it flipped between pass and fail on a loaded machine; after them it passed in the last full `tests/deep` run and in 3 of 3 isolated runs, but it measures wall time, so a very loaded machine can still flip it. TR-03's reference transition lasts 3.2 s, so every frame of that preview renders two shots; that cost is inherent.
- The stub engine (`engine_stub.py`, used only when the real engine cannot be imported) was not given the new checks (style, timing, slots, incomplete). Only the real engine is in production use.
- `project` different from the folder name stays a warning, not an error (clones of a project legitimately differ).
- No exporter exists yet, so "the exporter produces `slots`" has nothing to change; `/defaults` does.
- Live media search/import and any real model were not touched (rules).

## Update: B-016 test corrected (coordinator's authority)
`test_B016` now asserts: delete is 409 while the job runs; the folder and its `project.json` are intact after the job ends; a second delete succeeds and the folder stays gone. B-016 test now passes: yes.

## Round 2 (from the front-end fixers)

**U1-001, search ignored "đ".** `catalogue.norm` dropped every letter that does not decompose (đ, ø, ł, ß...) and every non-ASCII script. New shared module `bti/textfold.py` (`fold`, `squash`, `tokens`, `norm`): NFKD, accents of any script removed, đ/Đ/ð to d, ø to o, ł to l, ß to ss, æ to ae, letters and digits of any script kept. Used by the library search (query and indexed text alike, so a search matches with or without accents), `projects.slug`, the engine's word-anchor `timing.norm`, the script stage (`parse._norm`, detail-heading keys in the brief, the source-overlap tokeniser) and media `slugify`. Artwork matching: `catalogue.regroup` on a copy of `library/` before and after gives byte-identical `artworks.json` (297 artworks, 33 multi-book) and an identical directory tree. Tests: `tests/library/test_textfold.py`, `test_search_with_d_bar_is_not_an_empty_search` in `tests/editor/test_library_api.py`. The e2e runner takes no id and needs headless Chrome; I did not run it, the same API call is the test above (`q=đ` now equals `q=d`, fewer than all artworks).

**A model job overwrote saves made while it ran.** One lock per project (`store.script_lock`) is held by every save, op, approval and import, and by a job when it finishes a chapter. A narration job now re-reads the document under that lock, replaces only the chapter it wrote, keeps everything else as on disk, renumbers a new beat id that the owner's edits took in the meantime, and uses the merged document for the next chapter's prompt. A beat locked while the job ran (and not locked when it started) is never overwritten: that chapter is left as the owner saved it and reported as skipped. A cancel keeps the owner's last save plus the chapters already finished. An outline job writes the whole outline, so if the outline file changed since the job began it is not written over: the job ends `error` with `error_kind: "conflict"` and the model's outline goes to the outline paste box. Tests: five in `tests/editor/test_backend_fixes.py` (save to another chapter survives; lock during a job respected; cancel; no id collision; outline conflict).

API changes of round 2:
- A narration job's `result` is `{written: [chapter ids], skipped: [{chapter, beats: [ids], reason}], rev}`; `rev` is the revision after the last write. The chapter of a skipped one has `state: "skipped"`.
- An outline job can end `state: "error"`, `error_kind: "conflict"` (outline edited while the model ran; text kept in `last_paste`).

**Proposals list shape.** `GET /api/projects/{pid}/proposals` now returns `{items: [...], skipped: [{file, reason}]}` (was a plain list); a file that cannot be read (bad JSON, wrong shape, bad name) is named with a short reason. Design doc section 9 updated; tests in `tests/editor/test_proposals.py` adjusted to `items` and a new test in `tests/editor/test_backend_fixes.py`. Front-end check: `bti/editor/static/js/proposals.js` reads `res.items`, but it reads `res.skipped` with `Number(...)`; with an array that is NaN, so the "N files could not be read" banner will NOT show until it uses `res.skipped.length` (and can list `file` and `reason`). I do not touch `static/`; the front-end fixer needs to change that one line.
