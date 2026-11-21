# FIX c1state: one answer for "where is this project, what may I call", and errors that say how to fix them

Worker `c1state`, branch `wt/c1state`. Document for agents: `docs/AGENT_API.md` (generated parts by `python -m bti.editor.hints`).

## What was built

* `GET /api/projects/{pid}/state` (`bti/editor/state_api.py`): the page's steps (from `pipeline_api.compute`), every call that can be
  made now with its real route and an example body, running jobs, and the problems of a damaged project. Nothing on the page changed.
* An error body for the whole API that always has `code`, `fix`, `retry` (`bti/editor/hints.py`: one table `code -> {fix, retry}`),
  plus `field` where a request field is wrong and `current_rev` where a revision is stale. Only keys were added.
* `docs/AGENT_API.md` with generated tables of the action ids, the words of `needs` and the codes; a test fails when they are stale.

## Table of action ids

The id is `<resource>.<verb>` (the resource the route works on, as `picks.approve` and `storyboard.ops` in the brief; the page's step 5
is `edit`, its actions are `draft.*`, `proposal.*`, `storyboard.*`, `identity.*`). Every action also carries `step`. A step whose state
is `locked` lists no action; the gate ahead of it is listed with `ready: false` and `needs`.

| id | route | listed / ready when |
|---|---|---|
| `outline.generate` | `POST /api/projects/{pid}/outline/generate` | A project made from a book. Ready unless a model job of the project is running or the agent cannot run. Advances while there is no outline. |
| `outline.import` | `POST /api/projects/{pid}/outline/import` | A project made from a book. Always ready; the caller supplies the outline text (`fill`). |
| `outline.approve` | `POST /api/projects/{pid}/outline/approve` | While the outline is not approved. Needs an outline. Gate. Advances. |
| `narration.generate` | `POST /api/projects/{pid}/narration/generate` | Needs the approved outline; refused while beats are locked unless forced; ready unless a model job is running or the agent cannot run. Advances while there is no narration. |
| `narration.import` | `POST /api/projects/{pid}/narration/import` | Needs an outline; the caller supplies the narration text (`fill`). |
| `narration.ops` | `POST /api/projects/{pid}/narration/ops` | Needs a narration; the caller supplies the typed operations (`fill`). |
| `narration.approve` | `POST /api/projects/{pid}/narration/approve` | While the narration is not approved. Needs a narration and the approved outline. Gate. Advances. |
| `outline.cancel`, `narration.cancel` | `POST /api/jobs/{job_id}/cancel` | While an outline (narration) job of the project runs. |
| `voice.generate` | `POST /api/projects/{pid}/voice/generate` | Once the narration is approved. Ready unless a voice job runs. Advances while the voice is not made or out of date; when it is done the body is `{"scope": "all"}`. Cost: machine time, about 1 hour. |
| `voice.cancel` | `POST /api/longjobs/{job_id}/cancel` | While a voice job runs. |
| `picks.search` | `POST /api/projects/{pid}/picks/search` | Once the picks step is open. Always ready; the body searches the painting's title. |
| `picks.import` | `POST /api/projects/{pid}/picks/import` | Once the picks step is open; the caller supplies source and source_id (`fill`). |
| `picks.import_book_image` | `POST /api/projects/{pid}/picks/import-book-image` | Once the picks step is open; the caller supplies source_id (`fill`). |
| `picks.import_clip` | `POST /api/projects/{pid}/picks/import-clip` | Once the picks step is open. Ready unless a picks job runs; the caller supplies url, start, end (`fill`). Cost: machine time, about 1 minute. |
| `picks.suggest` | `POST /api/projects/{pid}/picks/suggest` | Paid (`auto_ok: false`). Needs the approved narration and suggestions switched on. |
| `picks.put` | `PUT /api/projects/{pid}/picks` | Once the picks step is open; the caller supplies the document (`fill`). |
| `picks.approve` | `POST /api/projects/{pid}/picks/approve` | While the picks are not approved. Needs the approved narration, picks, a main painting, no other error. Gate. Advances. |
| `picks.ops` | `POST /api/projects/{pid}/picks/ops` | Only when the running app has the route (looked up in the router at request time). |
| `picks.cancel` | `POST /api/longjobs/{job_id}/cancel` | While a suggestion or clip job runs. |
| `draft.start` | `POST /api/projects/{pid}/draft/start` | Once step 5 is open. Needs voice, approved picks, no draft job, a usable agent. Advances while there is no draft (or it is out of date) and no storyboard. Cost: model, about 20 minutes. |
| `proposal.apply` | `POST /api/projects/{pid}/proposals/{prop_id}/apply` | While the project has no storyboard and a draft proposal exists. Advances when the draft is up to date. |
| `storyboard.restore` | `POST /api/projects/{pid}/storyboard/restore` | Only when storyboard.json is unreadable. Ready when history/ has a good copy. The repair: listed first. |
| `storyboard.validate` | `GET /api/projects/{pid}` | While the storyboard is readable; `issues` of the answer are the validation. |
| `storyboard.approve` | `POST /api/projects/{pid}/approve` | While the storyboard is not approved (or was edited after). Gate. Advances. |
| `storyboard.preview` | `POST /api/projects/{pid}/preview` | While the storyboard is readable; a job of a few seconds. |
| `storyboard.put` | `PUT /api/projects/{pid}/storyboard` | While the storyboard is readable; the caller supplies the document (`fill`). |
| `storyboard.ops` | `POST /api/projects/{pid}/storyboard/ops` | Only when the running app has the route. |
| `draft.edit` | `POST /api/projects/{pid}/draft/edit` | While the storyboard is readable; ready unless a draft job runs or the agent cannot run; the caller supplies instruction and scope (`fill`). |
| `identity.set` | `PUT /api/projects/{pid}/identity` | While the storyboard is readable; the caller supplies the style (`fill`). |
| `draft.cancel` | `POST /api/longjobs/{job_id}/cancel` | While a draft job runs. |
| `export.start` | `POST /api/projects/{pid}/export/start` | Once the storyboard is approved. Ready unless an export runs, or the audio mix or timing is missing. Advances until a video is exported. Cost: machine time, about 25 minutes. |
| `export.cancel` | `POST /api/longjobs/{job_id}/cancel` | While an export job runs. |

All four gates (`outline.approve`, `narration.approve`, `picks.approve`, `storyboard.approve`) have `auto_ok: true`. Only `picks.suggest` has
`auto_ok: false`.

## Codes added, per file

Existing codes were kept as they were. Added `code=` on every `ApiError` of the files below (no detail text, key or status changed):

* `app.py`: `project_not_found`, `storyboard_not_found`, `storyboard_corrupt` (with a `fix` of its own when history/ has no copy),
  `validation_failed`, `save_refused`, `field_required`, `field_invalid`, `base_rev_required`, `stale_revision` (+ `current_rev`),
  `style_not_found`, `not_found`, `route_not_found`, `nothing_to_restore`, `no_history_copy`, `history_file_not_found`,
  `history_file_unreadable`, `unknown_technique`, `storyboard_has_errors`, `storyboard_incomplete`, `shot_not_found`, `no_audio_file`,
  `preview_too_long`, `preview_too_many_frames`, `job_not_found`, `asset_not_found`, `licence_rejected`, `unsupported_file_type`,
  `file_too_large`, `proposal_not_found`, `proposal_corrupt`, `proposal_malformed`, `proposal_has_errors`, `thumbnail_failed`. The four
  `stale` raises of the proposal apply got `current_rev`. Handlers: `DataError` -> `storyboard_unusable`, `timing_unusable`,
  `style_unusable`, `data_unusable`; `DocumentCorrupt` -> `document_corrupt`; `LibraryDataError` -> `library_data_corrupt`; `ProjectGone` and
  a deleted folder -> `project_not_found`; `UnicodeEncodeError` -> `bad_text_character`; framework 404/405 -> `route_not_found`,
  `method_not_allowed`; a request the framework refuses -> `request_invalid` (+ `fields`); the catch-all -> `internal_error`; `RenderError`
  keeps `render_failed`.
* `script_api.py`: `project_not_found`, `field_invalid`, `stale_revision`, `model_required`, `unknown_model`, `model_unavailable`,
  `model_invalid`, `model_job_busy`, `job_not_found`, `prompt_error`, `outline_unreadable`, `narration_unreadable`, `document_invalid`,
  `no_outline`, `no_narration`, `outline_has_errors`, `narration_has_errors`, `unknown_chapter`, `locked_beats`, `op_invalid`; the outline
  gate refusals now carry the gate's own code (`outline_missing`, `outline_not_approved`, `outline_stale`).
* `voice_api.py`: `project_not_found`, `body_invalid`. `picks_api.py`: `project_not_found`, `field_required`, `field_invalid`,
  `unsupported_file_type`, `file_too_large`; a `PicksError` without a code gets `picks_error`. `draft_api.py`: `project_not_found`,
  `body_invalid`, `turn_not_found`, `turn_frame_not_found`, `shot_not_found`, `save_refused`, `edit_running`; a stale edit now carries
  `current_rev`. `export_api.py`: `project_not_found`, `export_file_not_found`. `identity_api.py`: `base_rev_required`, `stale_revision`.
* `pipeline_api.py` (only `code=`): `project_not_found`, `project_protected`, `project_is_symlink`, `invalid_project_path`,
  `delete_not_confirmed`, `script_job_running`, `preview_running`. `proposals.py`: `unknown_change_ids`, `accept_invalid`.
* `library_api.py`: `book_not_found`, `book_not_catalogued`, `book_pdf_missing`, `work_not_found`, `page_not_in_work`, `page_not_found`,
  `image_not_in_work`, `image_extract_failed`, `artwork_not_found`, `dossier_not_found`, `source_not_found`, `source_text_missing`,
  `library_file_unreadable`, `merge_refused`, `split_refused`, `project_create_refused`, `project_source_missing`, `field_required`,
  `field_invalid`.
* `agent_api.py`, `settings_api.py`, `jobs.py`: nothing to add (their raises had codes, or there are none).
* `hints.py` (codes the handlers and the net give by status when an error carries none): `bad_request`, `forbidden`, `not_found`,
  `method_not_allowed`, `conflict`, `too_large`, `too_deep`, `unsupported_media`, `range_not_satisfiable`, `field_invalid`, `internal_error`,
  `source_error`, `source_unavailable`, `source_timeout`. The table has a hint for every code literal in `bti/` (a test scans for them) and
  for the codes made at run time (the draft, export and voice sentence tables, the suggestion codes, `<what>_missing`, ...).

## Codes with no Vietnamese sentence on the page (for the owner of `errmsg.js`)

**Resolved by the Follow-up at the end of this file** (the sentences are in `errmsg.js` now); the list below is what was found first.

Found by running the page's own `describeHttp` (`bti/editor/static/js/errmsg.js`) on each new code with a sample of its detail: these get
only the generic sentence of their status, nothing specific. (Before this build the same errors got the same generic sentence: nothing
got worse.)

`route_not_found`, `method_not_allowed`, `request_invalid`, `bad_text_character`, `bad_request`, `forbidden`, `conflict`, `source_unavailable`,
`source_timeout`, `not_found` (only the picks stage has a sentence for it, by stage), `history_file_unreadable`, `history_file_not_found`,
`no_history_copy`, `nothing_to_restore`, `storyboard_incomplete`, `proposal_has_errors`, `licence_rejected`, `model_unavailable`,
`model_invalid`, `prompt_error`, `outline_unreadable`, `narration_unreadable`, `document_invalid`, `outline_has_errors`,
`narration_has_errors`, `locked_beats`, `op_invalid`, `body_invalid`, `turn_not_found`, `turn_frame_not_found`, `export_file_not_found`,
`library_file_unreadable`, `merge_refused`, `split_refused`, `project_create_refused`, `project_source_missing`, `accept_invalid`,
`unknown_change_ids`, `picks_error`.

## Whole-body assertions of existing tests that I changed (all in `tests/editor`)

Each said that an error has NO `code`; the error now has a code (the added key), so each now says it is not the code it must not be:

1. `tests/editor/test_agent_routes.py::test_a_request_that_names_a_model_keeps_working_as_today`: `"code" not in r.json()` became
   `r.json()["code"] != "agent_unavailable"`.
2. `tests/editor/test_media_adapter_limit.py::test_the_search_route_answers_with_the_code_and_the_wait`: `"code" not in r.json()` became
   `r.json()["code"] != "source_rate_limited"`.
3. `tests/editor/test_round2_fixes.py::test_depth_limit_is_one_shared_check_before_the_routes`, two lines: `"code" not in ok.json()` became
   `ok.json()["code"] != "too_deep"`; `or "code" not in r.json()` became `or r.json()["code"] != "too_deep"`.

No other existing test needed a change.

## Decisions where the brief was silent

* **Action id = `<resource>.<verb>`**, following the brief's own examples (`picks.approve`, `picks.ops`, `storyboard.ops`; the gates are
  named outline, narration, picks, storyboard as in the design's `bti approve <project> <gate>`). `steps[].step` uses the page's ids
  (`edit` for step 5); each action has `step` so the two map.
* **`state` has the three words of the brief** (`done`, `current`, `locked`); `page_state` keeps the page's word (`available` maps to
  `current`; `waiting` and `no_data` map to `locked`). Extra keys: top-level `current`, step `label`, `page_state`, `problem`.
* **Extra keys on an action** (additions only): `step`, `advances` (ready and moves the project forward: a walker takes the first ready
  action with it), `follow` (the GET that follows a job), `fill` + `body_template` (for a call whose body the caller must supply: `body` is
  then null, never a body that would be refused), `job_id` (cancel actions). The list is sorted: repair first, then `advances`, then
  other ready calls, then gated ones.
* **Locked steps list no action**; "the gate ahead" is the gate of an open step that is not ready (for example `picks.approve`,
  `needs: ["main_asset"]`). A `waiting` step (output exists, an earlier document is being redone) lists its actions with the blocker as
  a need (`narration_approved`, ...), as the page makes it read-only.
* **Redo calls stay listed on a done step** (`outline.generate`, `voice.generate` with scope all, `export.start`), with `advances: false`.
* **`auto_ok`**: true for everything except the paid `picks.suggest`.
* **`cost`**: `kind: model` for a draft, outline, narration or edit (an agent works, not this machine); `machine_time` for the voice, the
  export and a clip cut.
* **`jobs[].started`** is an ISO 8601 time from the job's creation time; `jobs[]` also has `path` and `cancel`. A preview job is listed
  but has no cancel (the app has none). The preview registry is read through its private `_jobs` (a public listing is in "Needs another
  worker").
* **Damage**: a corrupt `storyboard.json` -> `problems` + the step's `problem` + `storyboard.restore` first (not ready when history/ has no
  copy: `needs: ["history_copy"]`); a missing timing file -> `voice.generate` first as the repair; an unreadable `project.json` -> every
  step locked, no action, `problems[0].code == "project_file_damaged"`; unreadable script or picks files -> `problems` and
  `documents_readable` in `needs` of the calls on them. The route never answers 5xx for a damaged project.
* **Ops routes**: found by asking the app's router whether it answers `POST` for the concrete path (`Match.FULL`, the static catch-all
  excluded). `app.routes` alone is not enough: this FastAPI (0.141 here, 0.163 on the server) keeps included routers as lazy objects
  without paths. The test adds fake routes (even with another parameter name) and removes one again.
* **The net**: besides the handlers there is `ErrorHintMiddleware` (outermost), because three families of error bodies are not made by a
  handler: the long-job routes (`bti/longjob/api.py` returns its own JSON), the 8 MB and nesting limits (`common.py`), and files I may
  not edit. It completes a JSON error body that lacks `code`, `fix` or `retry` and passes every other response through byte for byte.
* **Raises in files I may not edit** (`common.py` 16, `frames.py` 5, `audio.py` 2, `media_adapter.py` 7, `engine_stub.py` 4) carry no
  `code=`: the handlers give them `code` by status (`field_invalid`, `not_found`, ...) and the field name when the sentence starts with
  it (`"width must be an integer"` -> `field: "width"`). The scan test lists these files as the only ones allowed to have code-less
  raises.
* **`retry`**: `no` = what the call names does not exist or the machine cannot do it; `after_fix` = change the request or project;
  `later` = busy, rate limited, a service did not answer. An unknown code gets the generic hint of its status.
* **`stale`/`stale_revision`**: both codes exist (old and new); `current_rev` is copied from `rev` where that is already there, and added
  by hand for the draft edit and the proposal apply.
* **Not JSON, not covered**: `416` file-range answers and the files themselves have no JSON body.

## Tests (`tests/state`, new)

* `test_state.py`: the exact list of action ids at 9 stages (new, outline waiting, narration approved, voiced, picks approved, proposal
  waiting, drafted, storyboard approved, exported), the steps against `/pipeline`, the shape of every action, costs and agents, every
  action's method and path against a real route, every example body accepted by its route (ready: 2xx; `fill` actions: the empty
  template is refused with the new error keys), a running long job and a running model job listed and cancelled, a corrupt storyboard
  (with and without a good copy), a missing timing file, a damaged `project.json`, damaged script files, the ops routes appearing only
  with the routes, an imported project, an edited narration making later steps wait, the old routes' answers unchanged.
* `test_errors.py`: the scan (every `code` literal in `bti/` has a hint; no `ApiError(` without a code in the files edited; every hint is
  one English sentence with a retry word; every route a fix names exists), `complete()` unit cases, one refused call per router with
  `code`, `fix`, `retry`, the stale revision with `current_rev` (storyboard, narration, picks, agent, proposal, draft edit), a named field,
  the framework's 404, 405 and 422, every kind of handled error and the catch-all (probe routes), the net on the long-job routes and on
  the body limits.
* `test_docs.py`: the generated parts are not stale; every id, need and code is in the document; the example in the document has the
  keys of the real answer.

Stood in for (their own suites cover them): the voice and export state (`stage_states`) and the draft's readiness read from timing.json;
the starters of the voice, draft, export and preview and the picture search (no heavy or paid work in any test); the mock agent.

## Test summary lines (as printed, snapshot `c1state` on the server)

```
tests/state       206 passed, 1 warning in 166.57s (0:02:46)
tests/editor      478 passed, 1 warning in 281.58s (0:04:41)
tests/picks       88 passed, 1 warning in 10.38s
tests/draft       330 passed, 1 warning in 174.07s (0:02:54)
tests/script      243 passed, 7 skipped in 33.32s
tests/export      78 passed, 2 skipped, 1 warning in 19.83s
tests/voice       79 passed, 1 skipped, 1 warning in 69.63s (0:01:09)
tests/longjob     69 passed, 1 skipped, 1 warning in 7.78s
tests/settings    44 passed, 1 warning in 4.81s
tests/identity    77 passed in 1.22s
```

The skipped tests are the ones the suites skip on their own (server-marked, missing tools); none is mine. `tests/state` and
`tests/editor` were run last, on the final tree; the other eight folders ran one edit earlier (a single `picks_error` line in the
hint table, which none of them reads).

## What I could not verify

* The state route was never called against the owner's real projects or the running app (port 8560): only fixtures. A real voice,
  draft or export was never started (their starters are replaced in the tests), and no model or agent was called.
* `agent.usable` comes from `bti.agents.model_availability`, which the app caches for ten minutes: on a cold cache the first state call
  may run `agy models` (the same list `GET /api/agents` runs). The tests use a mock agent and the availability of a mock model.
* `picks.ops` and `storyboard.ops` appear only with the other worker's routes; both cases were tested with fake routes, not with the
  real ones. Their `fill` fields (`ops`, `base_rev`) follow the design document, not the other worker's final contract.
* FastAPI differs between this Mac (0.141) and the server (0.163); the tests ran on the server only, the generator
  `python -m bti.editor.hints` on the Mac.
* One thing went wrong in the process: a first chain of suite runs that I believed had stopped kept running in the same snapshot while
  I started the same chain again, so two runs shared `snap-c1state` for a few minutes. Both finished with the same results as listed
  above. Also, access to the worktree was refused by macOS for stretches of the session (EPERM); nothing was lost.

## Needs another worker

* (Done in the Follow-up) `bti/editor/static/js/errmsg.js`: Vietnamese sentences for the codes listed above.
* `bti/editor/common.py`, `frames.py`, `audio.py`, `media_adapter.py`, `engine_stub.py`: add `code=` (and `field=`) to the 34 raises
  that have none (the handlers cover them meanwhile); then the scan test can drop `NOT_EDITED`.
* `bti/editor/jobs.py`: a public method to list the running preview jobs of a project (the state route reads `_jobs`), and a cancel for
  previews.
* The worker of the `ops` routes: use `stale_revision` with `rev` (the handlers add `current_rev`), `code` on every refusal, and
  `field`/`fields` for a wrong operation, so `bti` can print the fix.

## Follow-up: Vietnamese sentences for every new code (`errmsg.js`)

The Node test `stages_words.test.mjs` ("every code of the stage packages has a Vietnamese sentence") failed on twelve codes I introduced
(`project_not_found`, `body_invalid`, `field_required`, `field_invalid`, `unsupported_file_type`, `file_too_large`, `turn_not_found`,
`save_refused`, `turn_frame_not_found`, `shot_not_found`, `edit_running`, `export_file_not_found`). Fixed in
`bti/editor/static/js/errmsg.js`, in two blocks marked `worker c1state`:

1. **`STAGE_CODES.api`** (a new table, after `settings`): one sentence for every code of mine a person can meet and that had only the
   general sentence of its status (or a sentence that did not say what to do). It is a stage table, so `UNIQUE_CODES`, the Node tests and
   `describeHttp` see it like the others.
2. **A block right after `BY_CODE_HTTP`**: decides which sentence a code shows.
   * An older sentence made from the server's own text is exact (it names the beat, the shot, the field), so it **stays** when the text has
     one; the code's sentence answers when the text has none (`c1stateTextSentence`).
   * Always the code's own sentence (`C1STATE_OWN`): `route_not_found`, `method_not_allowed`, `request_invalid`, `body_invalid` (only a program
     meets them: one shared plain sentence), and `file_too_large`, `unsupported_file_type`, `preview_too_long`, `preview_too_many_frames`,
     `proposal_not_found`, `proposal_corrupt`, `proposal_malformed`, `no_audio_file`, `model_unavailable` (the code is certain, and the older
     sentence only said what was wrong, not what to do).
   * `bad_request`, `forbidden`, `conflict`, `unsupported_media` use the sentence of their status (`BY_STATUS`: it is already right).
   * **A regression I would have caused and avoided.** Four codes I added already existed in another stage's table (`stale_revision` and
     `unknown_chapter` in the draft table, `unknown_model` in settings, `storyboard_corrupt` in the draft table). `describeHttp` looks the code up
     before it reads the text, so the narration's stale save would have read "Storyboard đã đổi ..." and the unknown chapter of the outline would
     have lost its chapter list. They keep the exact text-based sentence first (`stale_revision` still says "Bản này đã đổi ở nơi khác ...").
     A script comparing, for every raise site of mine, the sentence before and after found no other sentence that got worse.
   * Not touched: the sentences that come from `data_error` (`document_corrupt`, `library_data_corrupt`, `storyboard_unusable`, `timing_unusable`,
     `style_unusable`, `data_unusable`, `library_file_unreadable` all carry `data_error`, so the page already says "Tệp ... bị hỏng"), and `internal_error`
     ("Máy chủ gặp lỗi bất ngờ."), `not_found` (the 404 sentence).

The sentences follow the voice of the page: short, no technical word, no exclamation mark, what happened and what to do. Checked by the
existing tests (every sentence Vietnamese, no id in it).

### Every code and the sentence the owner sees

Column 2 is what `describeHttp` returns for a typical refusal of that code (the text the server sends with it). Column 3 is the sentence
of the code itself, used when the server's text has no exact sentence; "same" means it is the one in column 2.

| code | sentence shown for a typical refusal | sentence of the code when the text has none |
|---|---|---|
| `accept_invalid` | Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy. | same |
| `artwork_not_found` | Không có tác phẩm này trong thư viện. | (sentence that was already on the page) |
| `asset_not_found` | Không tìm thấy hình này. | same |
| `bad_request` | Máy chủ không hiểu yêu cầu này. | (sentence that was already on the page) |
| `bad_text_character` | Văn bản có ký tự lạ nên chưa lưu được. Hãy xóa ký tự đó rồi gửi lại. | same |
| `base_rev_required` | Thiếu mã phiên bản của bản đang sửa. Hãy tải lại trang. | same |
| `body_invalid` | Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy. | same |
| `book_not_catalogued` | Sách này chưa có trong danh mục thư viện. Cần dựng lại danh mục (python -m bti.library build). | (sentence that was already on the page) |
| `book_not_found` | Không có sách này. | (sentence that was already on the page) |
| `book_pdf_missing` | Thiếu tệp PDF của sách. | (sentence that was already on the page) |
| `conflict` | Việc này xung đột với trạng thái hiện tại của dữ liệu. | (sentence that was already on the page) |
| `data_unusable` | Dữ liệu của dự án không dùng được. | (sentence that was already on the page) |
| `delete_not_confirmed` | Gõ đúng mã dự án để xác nhận xóa. | (sentence that was already on the page) |
| `document_corrupt` | Tệp project.json của dự án bị hỏng hoặc sai dạng. | (sentence that was already on the page) |
| `document_invalid` | Dữ liệu gửi lên sai cấu trúc nên chưa lưu được. Hãy tải lại trang rồi sửa lại. | same |
| `dossier_not_found` | Tác phẩm này chưa có hồ sơ. | (sentence that was already on the page) |
| `edit_running` | Không thể xóa lịch sử khi đang có yêu cầu sửa đang chạy. Hãy hủy tác vụ trước. | Đang có một yêu cầu sửa chạy nên chưa xóa được lịch sử. Hãy hủy tác vụ trước. |
| `export_file_not_found` | Không tìm thấy tệp này trong thư mục xuất. Có thể nó đã bị xóa. | same |
| `field_invalid` | Thông số xem thử không hợp lệ. | Dữ liệu gửi lên không hợp lệ. |
| `field_required` | Thiếu mã phiên bản của bản đang sửa. Hãy tải lại trang. | Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy. |
| `file_too_large` | Tệp quá lớn (tối đa 80 MB). Chọn tệp nhỏ hơn. | same |
| `forbidden` | Máy chủ không cho làm việc này. | (sentence that was already on the page) |
| `history_file_not_found` | Không thấy bản lưu này trong lịch sử của dự án. Chọn bản khác. | same |
| `history_file_unreadable` | Bản lưu này trong lịch sử không đọc được. Chọn bản khác. | same |
| `image_extract_failed` | Không tạo được ảnh nhỏ từ tệp này. | (sentence that was already on the page) |
| `image_not_in_work` | Hình này không có trong mục đã chọn. | (sentence that was already on the page) |
| `internal_error` | Máy chủ gặp lỗi bất ngờ. Xem "chi tiết". | (sentence that was already on the page) |
| `invalid_project_path` | Đường dẫn dự án không hợp lệ. | (sentence that was already on the page) |
| `job_not_found` | Không tìm thấy tác vụ này (có thể máy chủ đã khởi động lại). | same |
| `library_data_corrupt` | Một tệp của thư viện sách bị hỏng. | (sentence that was already on the page) |
| `library_file_unreadable` | Một tệp của thư viện sách bị hỏng. | (sentence that was already on the page) |
| `licence_rejected` | Hình này không ghi giấy phép. Vẫn dùng được; hãy ghi nguồn khi đăng. | Giấy phép của ảnh này không được chấp nhận. Chọn ảnh khác. |
| `locked_beats` | Có dòng đang khóa sẽ bị viết lại (c01:b0001). Mở khóa các dòng đó hoặc chọn viết lại cả dòng khóa. | Có dòng đang khóa sẽ bị viết lại. Mở khóa các dòng đó hoặc chọn viết lại cả dòng khóa. |
| `merge_refused` | Không gộp một tác phẩm với chính nó. | Không gộp được hai tác phẩm này. Hãy chọn hai tác phẩm khác nhau. |
| `method_not_allowed` | Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy. | same |
| `model_invalid` | Tên mô hình gửi lên không hợp lệ. Chọn một mô hình ở ô trên thanh công cụ rồi thử lại. | same |
| `model_job_busy` | Dự án này đang có một tác vụ mô hình chạy. Chờ nó xong hoặc bấm Hủy. | (sentence that was already on the page) |
| `model_required` | Chưa chọn mô hình. Chọn một mô hình ở ô trên thanh công cụ rồi thử lại. | (sentence that was already on the page) |
| `model_unavailable` | Mô hình này chưa dùng được trên máy này (thiếu khóa hoặc chưa cài). Chọn mô hình khác. | same |
| `narration_has_errors` | Lời dẫn còn lỗi nên chưa duyệt được. Xem hộp "Kiểm tra". | same |
| `narration_unreadable` | Không xếp được lời dẫn từ văn bản đã dán. Chưa có gì bị ghi đè. | same |
| `no_audio_file` | Dự án chưa có tệp âm thanh. Hãy làm bước "Giọng đọc" trước. | same |
| `no_history_copy` | Trong lịch sử của dự án không còn bản storyboard nào đọc được. Hãy dựng bản nháp mới ở bước "Dựng hình". | same |
| `no_narration` | Chưa có lời dẫn. | (sentence that was already on the page) |
| `no_outline` | Chưa có dàn ý để duyệt. | (sentence that was already on the page) |
| `not_found` | Không tìm thấy mục này. | (sentence that was already on the page) |
| `nothing_to_restore` | Storyboard vẫn đọc được bình thường nên không có gì để khôi phục. | same |
| `op_invalid` | Dòng b0001 đang khóa, không sửa được. Bỏ khóa trước. | Thao tác này không làm được ở trạng thái hiện tại. Hãy tải lại rồi làm lại. |
| `outline_has_errors` | Dàn ý còn lỗi nên chưa duyệt được. Xem hộp "Kiểm tra". | same |
| `outline_unreadable` | Không đọc được dàn ý từ văn bản đã dán. Chưa có gì bị ghi đè. | same |
| `page_not_found` | Trang này không có trong mục đã chọn. | (sentence that was already on the page) |
| `page_not_in_work` | Trang này không có trong mục đã chọn. | (sentence that was already on the page) |
| `picks_error` | Phần chọn hình gặp lỗi. Thử lại, hoặc xem "chi tiết". | same |
| `preview_running` | Dự án đang dựng xem thử. Chờ xong rồi mới xóa được. | (sentence that was already on the page) |
| `preview_too_long` | Đoạn xem thử quá dài. Chọn đoạn ngắn hơn. | same |
| `preview_too_many_frames` | Đoạn xem thử có quá nhiều khung hình. Chọn đoạn ngắn hơn. | same |
| `project_create_refused` | Đã có dự án tên "x". Hãy chọn tên khác. | Chưa tạo được dự án. Kiểm tra tên thư mục và các mục sách đã chọn rồi thử lại. |
| `project_is_symlink` | Thư mục dự án là liên kết tượng trưng, từ chối xóa. | (sentence that was already on the page) |
| `project_not_found` | Không có dự án này. | same |
| `project_protected` | Dự án này được bảo vệ, không xóa được. | (sentence that was already on the page) |
| `project_source_missing` | Thiếu tệp nguồn của tác phẩm này trong thư viện. Hãy báo cho người quản lý máy. | same |
| `prompt_error` | Chưa tạo được lời nhắc từ dàn ý và lời dẫn hiện có. Kiểm tra hai phần đó rồi thử lại. | same |
| `proposal_corrupt` | Tệp đề xuất này bị hỏng nên đã được cất đi. Hãy dựng bản nháp mới. | same |
| `proposal_has_errors` | Storyboard trong đề xuất còn lỗi nên chưa nhận được. Hãy dựng bản nháp mới. | same |
| `proposal_malformed` | Đề xuất này sai cấu trúc nên không dùng được. Hãy dựng bản nháp mới. | same |
| `proposal_not_found` | Không tìm thấy đề xuất này. | same |
| `request_invalid` | Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy. | same |
| `route_not_found` | Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy. | same |
| `save_refused` | Storyboard còn lỗi nên chưa lưu hoặc duyệt được. Xem danh sách lỗi. | same |
| `script_job_running` | Dự án đang có một tác vụ mô hình chạy. Hủy nó (hoặc chờ nó xong) rồi mới xóa được. | (sentence that was already on the page) |
| `shot_not_found` | Không tìm thấy cảnh này. | same |
| `source_not_found` | Không tìm thấy nguồn hoặc văn bản của nguồn này. | (sentence that was already on the page) |
| `source_text_missing` | Không tìm thấy nguồn hoặc văn bản của nguồn này. | (sentence that was already on the page) |
| `source_timeout` | Nguồn bên ngoài trả lời quá chậm. Thử lại sau. | same |
| `source_unavailable` | Nguồn bên ngoài đang bận hoặc không trả lời. Thử lại sau vài giây. | same |
| `split_refused` | Tác phẩm này chỉ có một nguồn nên không tách được. | Không tách được mục này ra khỏi tác phẩm. |
| `stale_revision` | Bản này đã đổi ở nơi khác (tab khác hoặc tác vụ nền) kể từ lúc bạn mở. Hãy tải lại phần này rồi sửa lại. | (sentence that was already on the page) |
| `storyboard_corrupt` | Tệp storyboard.json bị hỏng. | (sentence that was already on the page) |
| `storyboard_has_errors` | Storyboard còn lỗi nên chưa lưu hoặc duyệt được. Xem danh sách lỗi. | Storyboard còn lỗi nên chưa làm tiếp được. Xem danh sách lỗi, sửa rồi thử lại. |
| `storyboard_incomplete` | Còn cảnh chưa đủ hình hoặc đoạn phim nên chưa duyệt được. Xem danh sách lỗi để biết cảnh nào. | same |
| `storyboard_not_found` | Dự án chưa có storyboard. | same |
| `storyboard_unusable` | Tệp storyboard của dự án bị hỏng hoặc thiếu. | (sentence that was already on the page) |
| `style_not_found` | Không có kiểu (style) này. | same |
| `style_unusable` | Không đọc được kiểu (style) mà dự án dùng. | (sentence that was already on the page) |
| `thumbnail_failed` | Không tạo được ảnh nhỏ từ tệp này. | same |
| `timing_unusable` | Tệp thời gian (timing) của dự án bị thiếu hoặc hỏng. | (sentence that was already on the page) |
| `turn_frame_not_found` | Không có ảnh của cảnh này cho lượt sửa. Bản lưu của lượt đó có thể không còn. | same |
| `turn_not_found` | Không tìm thấy lượt sửa này. | same |
| `unknown_change_ids` | Có thay đổi không còn trong đề xuất. Mở lại đề xuất rồi chọn lại. | same |
| `unknown_chapter` | Chương không có trong dàn ý: c9. | (sentence that was already on the page) |
| `unknown_model` | Không có mô hình này trong danh sách. | (sentence that was already on the page) |
| `unknown_technique` | Kỹ thuật không có trong danh sách. | same |
| `unsupported_file_type` | Loại tệp này chưa hỗ trợ. Chọn ảnh (jpg, png, webp) hoặc video (mp4, mov, webm, m4v). | same |
| `unsupported_media` | Máy chủ không xử lý được loại tệp này. | (sentence that was already on the page) |
| `validation_failed` | Storyboard còn lỗi nên chưa lưu hoặc duyệt được. Xem danh sách lỗi. | same |
| `work_not_found` | Không có mục sách này. | (sentence that was already on the page) |

Test summary (Node, from the worktree, as printed):

```
ℹ tests 302
ℹ suites 0
ℹ pass 301
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 0
```

The command was `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs`. The one
skipped test is `tests/editor_frontend/sbissues.test.mjs:135` ("every code in bti.engine.storyboard.ISSUE_CODES has a Vietnamese template"): it
needs `.venv/bin/python` to import the engine's issue codes, which the worktree does not have (Python runs on the server only). It is skipped
by the test itself and does not touch my files.

Not verified: no browser was opened, so no sentence was looked at on a real page; they were checked by `describeHttp` in Node. The sentence a
refusal shows when its text is not the one I sampled (a refusal with a different detail than the raise site's) follows the rules above; the
raise sites whose detail is built at run time (`model_unavailable`, `project_create_refused`, `merge_refused`, `split_refused`) were sampled with
a realistic text, not the real one.

## Join: the state and hints build joined with the operations, media, trust and follow-up builds (worker `c1state`, worktree `wt/join`)

### One vocabulary of errors

Where the two builds named one situation twice, one name was kept and applied on both sides and in both generated documents (`docs/AGENT_API.md`,
`docs/OPS.md`):

| Situation | Kept | Gone | Why |
|---|---|---|---|
| the project has no storyboard | `storyboard_not_found` | `document_missing` (operations) | says which document; every storyboard route answers it (app, frames, validate, the operations); the same family as `project_not_found`, `shot_not_found`, `batch_not_found` |
| a field of the request is wrong or missing | `invalid_field` | `field_invalid`, `field_required` (mine) | the operations' name, used in their ~460 tests and the registry; a missing field is a wrong field with the problem "is required" |
| the request body or envelope is not valid (not an object, `base_rev` missing, a body the framework refuses) | `invalid_request` | `request_invalid`, `body_invalid`, `base_rev_required` (mine) | the operations' name, same reason |
| the wrong field(s) | `fields: [{path, problem, allowed?}]` | `field` (mine) | the form of the design document and of the operations. A raise site still names one field with `field="x"`; `hints.complete` turns it into `fields` (nothing else in the body changes), so the answer has only `fields` |
| the revision to start again from | `current_rev` (both already used it) | nothing | `rev` stays only where it already was (an old key); the two builds agree |
| a stale revision | `stale_revision` and `stale` both stay | nothing | `stale` is the page's own word (picks, agent, proposals: `errmsg.js` keys on it); both have the same sentence (`STALE_FIX` is the operations' sentence) and the same `current_rev` |

**One source of the sentences.** The operations' table (`bti/ops/errors.py`) is read by `bti/editor/hints.py` (`HINTS[code] = {retry, fix}` for every
code of `ERRORS`), and an operations error takes its `fix` and `retry` from the same table, so the two cannot drift. `tests/state/test_errors.py::
test_the_operations_table_and_the_hints_are_one_source` checks both directions. For the codes the two builds shared, the entry of my table was removed
and the operations' sentence was reworded where it was too specific to the batch routes, so that it is also right for the other routes that send the
code: `invalid_request`, `invalid_field`, `unknown_asset`, `unknown_technique`, `unknown_source`, `video_not_main`, `stale_revision`,
`validation_failed`, `project_not_found`, `storyboard_not_found`, `document_corrupt`, `not_found`, `source_rate_limited`, `source_unreachable`,
`source_error`. Where the retry word differed, the operations' table won, except where it was wrong for what the sentence asks: `document_corrupt`
(restore a copy, then call again) is `after_fix`, not `no`; `source_error` and `not_found` are `after_fix`. `docs/OPS.md` was regenerated (`python -m bti.ops.doc`).

**New hints** (the 25 codes that were not in the table): the operations' own, `invalid_request`, `invalid_field`, `unknown_op`, `unknown_shot`,
`unknown_overlay`, `unknown_beat`, `unknown_region`, `unknown_param`, `unknown_slot`, `wrong_technique_kind`, `technique_unavailable`,
`slot_kind_mismatch`, `unknown_ref`, `duplicate_ref`, `shot_too_short`, `not_consecutive`, `span_mismatch`, `locked`, `out_of_scope`, `batch_not_found`,
`import_failed`; and `claude_outdated`, `map_place_unknown`, `audio_decode_failed`, `image_too_small`. (`undo_conflict` and `undo_unavailable` already had one.)
The scan (`code_literals`) now also reads the first argument of the operations' `OpError` (not the other `OpError` of `bti/script/ops.py`).

### The state answer and the real operations

* `picks.ops` and `storyboard.ops` are listed whenever their step is open (the route lookup at request time was removed: the routes are part of the app).
  Their `body` is a **dry run** (`dry_run: true`) of the first example of the operations registry (`registry.defs(doc)`: set_main, set_technique), with
  the current `base_rev` and `actor = "agent:<model of the project's agent>"`; `fill: ["ops"]` and `body_template` give the real call. Decision: the
  registry's examples are written for the operations' fixture project, so a body that writes would be wrong on another project; a dry run writes nothing.
  Tested on the fixture project (accepted: 200, `dry_run`, `batch: null`, the folder byte-identical) in `tests/state/test_ops_state.py`; on the other
  fixtures of `tests/state` the route answers 200 or a typed error of the operations, which is stated in the test.
* New actions `changes.list` (`GET /api/projects/{pid}/changes`, listed once the log holds a batch) and `changes.undo` (`POST .../changes/{batch}/undo`
  for the **newest batch that can be undone now**: it has its copies, nothing undid it and nothing it changed was changed since: the same check the undo
  route makes first, `bti.ops.undo.find_conflicts`; body `{base_rev, actor, note}`). Both carry the `step` of the document of the batch (`picks` or `edit`).
  Tests: the first batch makes both appear; the undo works; the undone batch is not offered again; a page save of the same line makes the older batch the
  target; no undo is offered when nothing can be undone.
* Exact lists of the nine stages in `tests/state/test_state.py` now have `picks.ops` after `picks.put` and `storyboard.ops` after `storyboard.put`.

### Refusals of the files I did not own, and the preview jobs (from my own "needs another worker")

* `code=` (and `field=` where the sentence names one; `fields=` for the two of `t0` and `t1`) on the 34 refusals of `common.py` (`not_found`, `invalid_field`),
  `frames.py` (`invalid_field`, `render_failed`, `project_not_found`), `audio.py` (`audio_decode_failed`), `media_adapter.py` (`source_unreachable`,
  `source_error`, `not_found`, `image_too_small`, `unsupported_file_type`, `invalid_field` for a ValueError without a code) and `engine_stub.py`
  (`style_not_found`, `unknown_technique`, `validation_failed`). Only keys were added; no status and no `detail` changed. The exception list of the scan
  test is gone: **every `ApiError(` of `bti/editor` has a code** (a `**` expansion counts).
* `bti/editor/jobs.py`: `JobManager.active(pid)` lists the project's queued or running preview jobs (`{id, state, progress, created}`); the state answer uses
  it instead of the private table.

### Vietnamese sentences for the operations' codes (`errmsg.js`, one block marked `worker join`)

A new table `STAGE_CODES.ops` (read by `describeHttp` after the same loop that serves the other new codes; a stage table with the same code, such as the draft's
`undo_conflict`, is untouched for the views that read it through `stageErrorText`). The same voice as the other sentences: short, no technical word, no
exclamation mark, what could not be done and what to say or choose instead. As the page shows them:

| code | sentence |
|---|---|
| `unknown_op` | Yêu cầu sửa này dùng một thao tác không có nên chưa làm. Hãy nói lại yêu cầu. |
| `unknown_shot` | Không có cảnh này trong storyboard. Chọn lại cảnh cần sửa. |
| `unknown_overlay` | Cảnh này không có lớp phủ đó. Chọn lại lớp phủ cần sửa. |
| `unknown_beat` | Không có đoạn lời dẫn này. Chọn lại đoạn cần sửa. |
| `unknown_asset` | Không có hình này trong dự án. Chọn hình khác, hoặc nhập hình trước. |
| `unknown_region` | Hình này không có vùng đó. Thêm vùng trước, hoặc chọn vùng khác. |
| `unknown_param` | Kỹ thuật này không có thông số đó. Chọn thông số khác. |
| `unknown_slot` | Kỹ thuật này không có chỗ đặt hình đó. Chọn chỗ khác. |
| `wrong_technique_kind` | Kỹ thuật này không dùng được ở chỗ này: cảnh và lớp phủ dùng hai loại kỹ thuật khác nhau. Chọn kỹ thuật khác. |
| `technique_unavailable` | Kỹ thuật này chưa dựng được. Chọn kỹ thuật khác. |
| `slot_kind_mismatch` | Hình này không hợp với chỗ đặt: chỗ đó cần loại khác (ảnh, video hoặc mặt nạ). Chọn hình khác. |
| `unknown_ref` | Yêu cầu nhắc tới một thứ chưa được tạo ở bước trước. Hãy nói lại yêu cầu. |
| `duplicate_ref` | Yêu cầu đặt hai thứ mới cùng một tên. Hãy nói lại yêu cầu. |
| `shot_too_short` | Chỗ cắt này làm một cảnh ngắn hơn 0,2 giây. Chọn thời điểm khác. |
| `not_consecutive` | Các cảnh được chọn không nằm kề nhau. Chọn các cảnh liền nhau. |
| `span_mismatch` | Các cảnh mới không khớp với khoảng thời gian của các cảnh bị thay. Hãy nói lại yêu cầu. |
| `locked` | Cảnh hoặc lớp phủ này đang khóa nên không sửa được. Mở khóa trước. |
| `out_of_scope` | Yêu cầu này chạm tới phần ngoài phạm vi bạn đã chọn nên chưa làm. Chọn phạm vi rộng hơn, hoặc nói cụ thể hơn. |
| `undo_conflict` | Không hoàn tác được vì có phần đã bị sửa tiếp sau lần sửa này. Hoàn tác các lần sửa sau trước, hoặc để nguyên phần đó. |
| `undo_unavailable` | Không hoàn tác được lần sửa này vì bản lưu của nó đã bị xóa bớt. Hãy sửa lại bằng một yêu cầu mới. |
| `batch_not_found` | Không tìm thấy lần sửa này trong lịch sử thay đổi. |
| `import_failed` | Không nhập được hình này vào dự án. Chọn hình khác hoặc nguồn khác. |
| `audio_decode_failed` | Không đọc được tệp âm thanh của dự án. Hãy làm lại bước "Giọng đọc". |
| `image_too_small` | Ảnh này quá nhỏ để dùng. Chọn ảnh lớn hơn. |
| `invalid_request` | Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy. |
| `invalid_field` | Thông số xem thử không hợp lệ. |

(`invalid_request` and `invalid_field` keep the older exact sentence when the server's text has one, for example "Thiếu mã phiên bản của bản đang sửa. Hãy tải lại trang.".
`claude_outdated` and `map_place_unknown` already had a sentence from their workers. The operations' `stale_revision`, `validation_failed`, `unknown_technique`,
`unknown_source`, `video_not_main`, `source_*` and `storyboard_not_found` already had one too.)

`docs/APP_GUIDE.md` (Vietnamese, section 1): two lines saying where an agent finds `docs/AGENT_API.md` and `docs/OPS.md`. `docs/AGENT_API.md`: a new section 6 on the
operations routes that points to `docs/OPS.md`, and the text of sections 2, 4 and 5 updated for the above. The refusal of the size and depth limits on the operations
routes carries `code`, `fix` and `retry` through the middleware: tested on `picks/ops`, `storyboard/ops` and `changes/{batch}/undo` (`too_deep` and `too_large`).

**Left for later, as asked:** the move of `engine_context` (and `default_slots`) out of `bti/editor/app.py` into a neutral module. `bti.ops.facts` still imports it from the
editor package when it is called.

### Existing test assertions changed

* `tests/ops/test_batch.py`: `document_missing` became `storyboard_not_found` (the name kept); the damaged-file test expects `retry == "after_fix"` for
  `document_corrupt` (was `"no"`).
* `tests/editor/test_media_adapter_limit.py` (two assertions on the added code): the answer of a 503 or 502 or 504 without a wait now has `code: "source_unreachable"`
  (`e.extra` was `{retryable, retry_after}`), and a 403 answer has `code: "source_error"` (`e.extra` was `{}`); "not a rate limit" is now stated as `!= "source_rate_limited"`.
* `tests/ops/conftest.py` (fixture, not an assertion): the fake Commons source also serves the rendition named by its API answer, the same one-line change the media worker made in
  `tests/picks/test_api.py`; this was the cause of the six red tests of the `import` operation.
* My own tests of the earlier build were updated for the renames (`tests/state/test_errors.py`, `test_state.py`); new: `tests/state/test_ops_state.py`.

### Files touched

`bti/editor/`: `app.py`, `audio.py`, `common.py`, `draft_api.py`, `engine_stub.py`, `frames.py`, `hints.py`, `identity_api.py`, `jobs.py`, `library_api.py`, `media_adapter.py`,
`ops_api.py`, `picks_api.py`, `script_api.py`, `state_api.py`, `static/js/errmsg.js`, `voice_api.py`; `bti/ops/errors.py`; `docs/AGENT_API.md`, `docs/APP_GUIDE.md`, `docs/OPS.md`,
`docs/qa/FIX_c1_state.md`; `tests/editor/test_media_adapter_limit.py`, `tests/ops/conftest.py`, `tests/ops/test_batch.py`, `tests/state/test_errors.py`, `tests/state/test_state.py`,
`tests/state/test_ops_state.py` (new).

### Test summary lines (snapshot `join` on the server, one folder per run, no `-m slow`; as printed)

```
tests/state       226 passed, 1 warning in 146.11s (0:02:26)
tests/ops         468 passed, 1 warning in 98.17s (0:01:38)
tests/editor      481 passed, 1 warning in 233.17s (0:03:53)
tests/picks       92 passed, 1 warning in 14.92s
tests/draft       341 passed, 1 warning in 142.48s (0:02:22)
tests/script      262 passed, 7 skipped in 33.03s
tests/media       363 passed in 2.77s
tests/library     1 failed, 162 passed, 1 warning in 5.28s     (the known failure: tests/library/test_library.py::test_works_json_shape on the stored library)
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
  ℹ tests 327   ℹ pass 326   ℹ fail 0   ℹ cancelled 0   ℹ skipped 1   ℹ todo 0
```

The one skipped Node test is `tests/editor_frontend/sbissues.test.mjs:135` (it needs `.venv/bin/python`, which the worktree does not have). `tests/editor` was first run with five
failures of `test_media_adapter_limit.py` (the two assertions above); the lines shown are from the run after the change. `tests/ops` ran before the last edit of `tests/state/test_errors.py` and the
`tests/editor` assertion change; none of the three touches code that `tests/ops` reads.

### What I could not verify

* No browser: the new sentences were checked with `describeHttp` in Node (and by the Node test of the tables), not on a page. The instruction box that will show the operations' refusals
  does not exist yet.
* The operations' example bodies are accepted on the operations' fixture project only; on a real project the dry run is likely to be refused with `unknown_*` (stated in the document).
* `changes.undo` predicts the undo with the same conflict check the route makes first; the route can still refuse it for a reason it finds only when it applies the undo (a new error the restored
  document would carry, `undo_conflict` with `issues`). Not exercised.
* Nothing was run against the owner's app on port 8560 or the real sources; the real engine and the fakes of the operations tests were used. A real voice, draft, export or model call was never started.
