# Round 2: decisions for the fixes

Written by the analyst on 2026-11-16, after `docs/qa/ROUND2_backend.md`. This file is the contract for the fix agents. Where it differs from an older document, this file wins; the fix agents then update the sentence in the design document they touch.

One principle for every item: **fix the class, not the reported input.** Round 1 fixes were sometimes too narrow (B-015 led to R2B-001, B-016 to R2B-005, B-002 to R2B-016). For each bug, ask what the neighbouring inputs are and cover them with a test.

## Who owns what

| Agent | Owns (may edit) | Bugs |
|---|---|---|
| Engine fixer | `bti/engine/**`, `style/gae/**`, `tests/engine/**`, `tests/deep/test_round2_engine.py`, `tests/deep/test_round2_cli.py`, `tests/deep/test_bugs_storyboard.py` (B-028 only), `bti/engine/README.md` | R2B-003, 004, 012 (engine part), 015, 016, and the engine half of 006 |
| API fixer | `bti/editor/*.py`, `bti/script/**`, `bti/library/**`, `bti/media/**`, `tests/editor/**`, `tests/script/**`, `tests/library/**`, `tests/media/**`, the other `tests/deep/` files | R2B-001, 002, 005, 007, 008, 009, 010, 011, 013, 014, the API half of 006 and 012 |

Neither agent edits `bti/editor/static/**` (a UI fixer does that later). Neither edits a file the other owns; if a change is needed there, write it down in your fix report under "Needs the other agent".

## The interface between the two agents

So both can work at once, these names are fixed now.

1. `bti.engine.errors.RenderError(DataError)` with fields `message`, `shot` (shot id or `None`), `overlay` (overlay id or `None`), `technique` (id or `None`), and `what = "render"`. The engine raises it from `Project.frame_at` and `Project.render_range` when a technique fails while drawing because of the storyboard's values. A real engine bug with valid values may still raise something else.
2. `Project.draw_check(storyboard: dict | None = None, width: int = 320) -> list[dict]`. It draws one small frame at the middle of every shot, and one inside every overlay's time span (times closer than one frame are drawn once). It never raises for a technique failure. It returns issues shaped like the ones from `validate`:
   `{"level": "error", "code": "undrawable", "path": "shots[12]" | "shots[12].overlays[1]", "shot": "s0013", "message": "..."}`.
   It must not change the project's draft state (`use_draft`) as seen by the caller.
3. Registry, new optional keys on a param (engine fixer adds them to `style/gae/techniques.json` and enforces them in `registry.validate_params`; `GET /api/style/...` passes them through unchanged):
   - `pattern` (string params only): a regular expression that the whole value must match.
   - `pattern_hint`: one Vietnamese sentence that says what to type, for the form. Example for `LAY-08.tiles`: `"Số cột x số hàng, ví dụ 4x2"`.
   - `min_items`, `max_items` (params of type `points` and `lines`).
4. The API fixer maps `RenderError` to **422** `{"detail": ..., "code": "render_failed", "shot": ..., "overlay": ..., "technique": ...}` on `/frame`, `/thumb` and as the job error of `/preview`. Never 500.
5. `POST /api/projects/{pid}/approve` runs `validate` first (as today) and then `draw_check`. Any `undrawable` issue refuses the approval with the same answer shape that the "incomplete" refusal uses today, with those issues listed.

## Decisions, bug by bug

**R2B-001. A narration approval belongs to one outline.**
- The narration approval record stores two hashes: the narration's and the approved outline's at that moment.
- The approval is fresh only when both still match and the outline approval is fresh. An old approval record without the outline hash is not fresh.
- `stale` on the narration means "the outline changed after this narration was written" (`source.outline_sha1` differs). It is information; it does not block saving.
- Approving a narration is refused while its chapter ids differ from the outline's: a chapter the outline does not have, or an outline chapter with no narration. Both become errors for approval (saving stays allowed, in line with "incomplete is not invalid"). The refusal lists them.
- After the owner fixes that and approves again, the new record holds the current outline hash. So a small outline edit costs one re-approval, never a rewrite.
- The stage is `script` only with a fresh narration approval.

**R2B-002. One function decides whether a storyboard approval is fresh.** `infer_stage` and the pipeline step state both call it. An approval whose `rev` is not the current revision gives stage `storyboard`. Check the same for every other place that reads `approvals` (home list, library project index).

**R2B-003, R2B-004. Engine command line.**
- Same limits as the HTTP API, from shared constants, not copied numbers: `t1 > t0`, times finite and `>= 0`, `fps` 1 to 30, width in the API's range, threads `>= 1` (or 0 for auto, if that is the current meaning; say which in the README).
- `0` is a value, not "not given": use `is None` tests.
- A start past the end of the storyboard is an error for `render` and for `still`.
- Usage errors: one line on stderr, exit code 2. Run-time errors (missing project, unreadable storyboard, cannot write the output, ffmpeg failed): one line on stderr, exit code 1. No Python traceback unless `--debug` is given. No partial output file left behind after a failure.

**R2B-005. Delete and saves exclude each other.**
- `DELETE` takes the project's script lock and its storyboard save lock (always in the same order as every other code path that takes both, to avoid a deadlock). If it cannot get them within about 2 seconds it answers 409 with a clear message, and nothing is removed.
- Every writer checks, after it has the lock, that the project still exists; if not it answers 404.
- A write helper never creates a project folder. `write_json_atomic` may create a missing sub-folder only inside an existing project.
- After a delete no folder is left, the slug is free, and the lock objects for that project are dropped.
- Acceptance: the stress in the report, 200 trials, gives only 200, 404 or 409, never 500, and never a ghost folder.

**R2B-006. Depth limit.** A request body nested deeper than 40 levels is 422, checked at one shared place before any product code walks it (API fixer; the check itself must not recurse). The engine's own walkers (`strip_derived`, `canonical`) must not raise `RecursionError` either: over 64 levels they raise `DataError` (engine fixer).

**R2B-007, 008, 009, 011. Input at the edge.**
- One shared helper per kind of value (finite number in a range, list of strings, id, path segment), used by every route, so the next route gets it for free.
- `OverflowError` is treated like `ValueError`. A path segment over 255 bytes is 404 without touching the file system; any `OSError` from a look-up is 404, not 500.
- An upload without a title takes the stem of the uploaded file's own name (cleaned); never the temp name.

**R2B-010, R2B-013. Ids and enums are checked, never coerced.**
- Chapter ids must match the pattern the parser reads back (`CH_ID_RE`; share the constant). Beat ids likewise, with their own pattern. Checked at `PUT`, at import, and on the model's output.
- Beat ids are unique in the whole narration; chapter ids are unique in the outline and in the narration.
- `role` must be one of `ROLES`; `card` must be a boolean. A wrong value is 422 naming the field. The same strictness for every other enum and boolean in the outline and narration documents.

**R2B-012. "Whatever validate accepts, the engine can draw."**
- `point`: either two finite numbers or the name of a region that exists on the asset in use. Shots are checked the same way overlays are today.
- `string` params that really carry structure get a `pattern` and a `pattern_hint` in the registry (`CMP-02.stage_blur`, `stage_grey`, `stage_gain`; `CMP-03.versions`; `LAY-08.tiles`; and every other one you find: read each technique's code for `split`, `float(`, `int(` on a string param). Where a keyword list is fixed, the pattern lists the keywords.
- `points` and `lines` get `min_items` / `max_items` where the technique needs a count (`DIA-02.to_quad` is exactly 4).
- These are `error` level, so the save is refused like any other invalid value.
- Second line of defence: any technique failure while drawing becomes `RenderError`, never a bare exception; and approval runs `draw_check`.
- Permanent test: the tester's sweep (every technique, every param, a set of wrong but well-typed values) lives in the test suite, marked slow if needed, and asserts "validate says no error implies the frame is drawn". Extend the sweep to all twelve param types, not only the three the tester tried.

**R2B-014. One damaged project never breaks another.**
- A project whose `project.json` is unreadable or of the wrong shape stays in `GET /api/projects` as a row `{"id": <folder>, "title": <folder>, "data_error": "<what is wrong>", "stage": null}`. The library's project index skips it. Neither list ever answers 500 because of one folder.
- Its own endpoints answer 409 `{detail, data_error}`, as timing and storyboard errors do today.
- Wrong-shape `brief_options.json`: 409 naming the file. A source text that is not UTF-8: 409 naming the file. No silent replacement of characters.
- Apply the rule to every JSON file a list or an index reads, not only the three in the report.

**R2B-015 and the old B-028. TR-03 cost.** TR-03 draws two shots at once for the whole transition, so about twice the cost of one shot is inherent. What matters to the owner is that a preview comes back faster than it plays.
- Spend at most 30 minutes profiling TR-03. Take a clear saving if there is one; do not restructure the technique.
- Replace both timing tests with one that measures everything warm (one warm-up, then the best of three for TR-03 and for each reference) and asserts: TR-03's 3-second preview takes under 3 seconds, and under 3.0 times the warm median of the references. Record the measured numbers in the fix report.

**R2B-016. Validate checks every field of the document.**
- `canvas.fps` is a number from 1 to 60. `locked` is a boolean. A shot start is `>= 0`. Wrong values are errors.
- Then go through the whole storyboard schema in the design document, field by field, and make sure each has a type check and a range check. List in the fix report any field you added a check for.

## Consequences for the page (for the UI fixer, later)

- The home page gets rows with `data_error` and must show them as damaged, not crash.
- Approving a storyboard can take a few seconds and can be refused with `undrawable` issues; they are listed like the "incomplete" ones.
- `/frame` and `/thumb` can answer 422 `render_failed`; the preview shows a Vietnamese message that names the shot.
- String fields with `pattern` show `pattern_hint` under the field.
- The script page explains why a narration is no longer approved when the outline changed, and lists chapter differences when approval is refused.

## Round 2, browser findings (added after `docs/qa/ROUND2_ui.md`)

A third agent, the **UI fixer**, owns `bti/editor/static/**`, `tests/editor_frontend/**`, `tests/e2e/**` and `docs/APP_GUIDE.md`. It edits no Python file.

The four findings share one cause: round 1 made the shell and the script view speak Vietnamese through `errmsg.js` and `labels.js`, and the storyboard view was left out. So the rule is stated once, for the whole app:

> **Nothing the owner reads comes straight from the server or from an exception.** Every error goes through `describeError`. Every validation issue goes through `issueText`. Every enum value, intent, stage and source goes through `labels.js`. A static test fails when a view file shows `.message`, a status number or a raw value to the owner.

**R2U-001. Errors in the storyboard view.** All of `views/storyboard.js`, `proposals.js`, `preview.js`, `media.js`, `actions.js` and every other module use `describeError` / the shared error toast. Add the static test above to `tests/editor_frontend/`.

**R2U-002. Storyboard issues are translated by code.**
- Engine fixer: every issue from `validate` (storyboard and registry) gets a stable `code` (snake_case) and `args` (a small dict with the values a sentence needs: param name, technique id, the limit, the region name). `message` stays, in English, for logs. The engine exports the full set as `bti.engine.storyboard.ISSUE_CODES` (`{code: one-line English meaning}`), and `undrawable` and `incomplete` are in it.
- UI fixer: a Vietnamese template for every code in `errmsg.js`; `issueText` is used wherever the storyboard view lists or counts issues (inspector, the issues tab, the check dialog, tooltips, the approve refusal). An unknown code gives a general Vietnamese sentence that names the shot and the field; the English text is only inside "chi tiết".
- A test reads `ISSUE_CODES` (through a small Python call or a generated JSON file written by a test fixture) and fails when a code has no Vietnamese template. Until the engine fixer has finished, write the templates against the messages you can see and finish the mapping when its report is ready.

**R2U-003. Two tabs on one storyboard.** Same idea as the script view (U1-011), at the size this tool needs.
- A pure function does a three-way merge between the base (the version this tab last loaded or saved), the draft, and the server's version. Units: each shot by id (the whole shot with its overlays), and each other top-level key of the document (regions, assets, canvas and so on).
- A unit changed on one side only is taken from that side. If the list of shots (ids, order, start times) changed on both sides, or one unit changed on both sides, the merge is not automatic.
- Automatic case: merge, validate, save, and tell the owner in one line what came from the other tab. If the merged document has errors, treat it as not automatic.
- Not automatic: a dialog in plain Vietnamese with no status number and no promise of a feature that does not exist. Choices: "Ghi đè bằng bản của tôi" (asks once more; the server keeps the other version in history), "Lấy bản trên máy chủ" (asks once more; the draft is dropped), "Để sau" (keeps the draft unsaved). After any choice the tab is never stuck: saving works again.
- Unit tests for the merge function; the e2e check `R2U-003` must pass.

**R2U-004. Labels.** Vietnamese labels for intents, ease names, `source` (`import`, `agent`, `human`), the library's trust labels, and every enum value of every param in `style/gae/techniques.json`. The raw value stays available as a tooltip. Technique ids such as `CAM-03` stay as they are. A test reads the registry and fails when an enum value or an intent has no label.

**Small items from the same report.**
- Home page: the columns of the project rows line up.
- Backspace deletes the selected shot, as Delete does (a Mac keyboard has no Delete key). Keep it; it can be undone. Write it in `docs/APP_GUIDE.md`.
- The engine and media badges refresh at once after the first request that succeeds following a failure, not after 30 seconds.
- No request for `/audio` or `/waveform` when the project information already says there is no audio. If it does not say so, leave it.
- Garbage typed into a camera field never reaches an SVG attribute as `NaN`.
- Model list (API fixer): `agy models` is not run on every visit to the script step. Cache the list in the server for 10 minutes, keep the time limit, and when the CLI does not answer return the configured entries with a flag the page can show. On the Windows server this command has been seen to hang for more than 25 seconds.
