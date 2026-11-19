# Agent API: where a project stands, what to call next, what an error asks for

For an agent in a terminal that runs a project through the HTTP API of the app (default `http://127.0.0.1:8560`). Two things are
here: one call that answers "where is this project, what blocks it, what may I call now", and an error body that always says what to
change and whether to try again. Design: `docs/design/2026-11-18-agent-first-design.html` (parts "Trạng thái và việc tiếp theo" and
"Lỗi nói rõ cách sửa").

The parts between `GENERATED` markers are written by `python -m bti.editor.hints` from the code (the catalogue in
`bti/editor/state_api.py`, the table in `bti/editor/hints.py`); a test fails when they are stale. Everything else is written by hand.

## 1. `GET /api/projects/{pid}/state`

One answer, built on the same computation as the page's step bar (`GET /api/projects/{pid}/pipeline`), so the page and an agent
never disagree. It reads files only: it never calls a model, never starts a job, and never fails for a damaged project.

```json
{
  "project": "arn",
  "stage": "picked",
  "current": "edit",
  "steps": [
    {"step": "artwork", "label": "Tác phẩm", "state": "done", "page_state": "done", "detail": "2 nguồn sách", "blocked_by": null, "problem": null},
    {"step": "script", "label": "Kịch bản", "state": "done", "page_state": "done", "detail": "Lời dẫn đã duyệt", "blocked_by": null, "problem": null},
    {"step": "voice", "label": "Giọng đọc", "state": "done", "page_state": "done", "detail": "Giọng đọc đã xong.", "blocked_by": null, "problem": null},
    {"step": "picks", "label": "Chọn hình", "state": "done", "page_state": "done", "detail": "Đã duyệt: 0/6 dòng có hình.", "blocked_by": null, "problem": null},
    {"step": "edit", "label": "Dựng hình", "state": "current", "page_state": "current", "detail": "Dựng bản nháp storyboard từ giọng đọc và hình đã chọn", "blocked_by": null, "problem": null},
    {"step": "export", "label": "Xuất video", "state": "locked", "page_state": "locked", "detail": "Cần duyệt storyboard ở bước Dựng hình trước khi xuất video.", "blocked_by": "edit", "problem": null}
  ],
  "next_actions": [
    {"id": "draft.start", "step": "edit", "label": "Dựng bản nháp", "method": "POST", "path": "/api/projects/arn/draft/start",
     "body": {"provider": "agy"}, "ready": true, "needs": [], "gate": false, "auto_ok": true, "long_job": true,
     "uses_model": true, "agent": {"id": "gemini", "label": "Gemini 3.8 Flash", "usable": true, "reason": null},
     "cost": {"kind": "model", "about": "about 20 minutes"}, "advances": true, "follow": "GET /api/longjobs/{job_id}"},
    {"id": "picks.import", "step": "picks", "label": "Nhập hình", "method": "POST", "path": "/api/projects/arn/picks/import",
     "body": null, "ready": true, "needs": [], "gate": false, "auto_ok": true, "long_job": false, "uses_model": false, "agent": null,
     "cost": null, "advances": false, "fill": ["source", "source_id"], "body_template": {"source": null, "source_id": null, "as_main": false}}
  ],
  "jobs": [],
  "problems": []
}
```

### Steps

`steps` is the page's list, in the page's order (`artwork`, `script`, `voice`, `picks`, `edit`, `export`; the storyboard step is called
`edit` here, as everywhere in `/pipeline`). `state` is one of three words; `page_state` keeps the page's own word so nothing is lost:

| `state` | `page_state` | meaning |
|---|---|---|
| `done` | `done` | the step is finished |
| `current` | `current`, `available` | the step can be worked on now (`current` is the one the page highlights, it is also the top-level `current`; steps 3 and 4 may both be open) |
| `locked` | `locked`, `waiting`, `no_data` | the step cannot be worked on: it waits for an earlier step (`blocked_by` names the first one that is not done; `waiting` means it has output but an earlier document is being redone), or the project has no data for it (`no_data`: imported from an earlier edit) |

`detail` is the sentence the page's step bar shows (Vietnamese). `problem` is the code of a problem of the project's data that this step
carries (see `problems`), else null.

### `next_actions`

Every call that can be made now, for the current step and for every step that is already open, in this order: the repair of a damaged
project first, then the calls that move the project forward (`advances`), then the other calls that are ready, then the ones that are
gated ahead (`ready: false`). Within a group the order is the order of the steps. An action whose step is locked is not listed; the gate
ahead of it is (for example `picks.approve` with `needs: ["main_asset"]`).

| key | meaning |
|---|---|
| `id` | `<resource>.<verb>`: the resource the route works on (the id of step 5 is `storyboard`, `draft` or `proposal`, as the route says), then the verb. Stable; every id is in the table in section 2 |
| `step` | the pipeline step it belongs to (`steps[].step`) |
| `label` | Vietnamese, as the page's button says |
| `method`, `path` | the real route, with this project's id (and the job or proposal id) filled in. Call it exactly as written |
| `body` | an example JSON body that is valid as it stands, or `null`: then the call has no body, or the caller must supply one and `fill` lists its fields |
| `fill`, `body_template` | only when `body` is null and the caller supplies content: the fields to supply, and a template with the values the state knows (for example the current `base_rev`) filled in |
| `ready`, `needs` | `ready` is true when the call can be made now. Otherwise `needs` lists what is missing, as words from the table in section 3 |
| `advances` | true when the call is ready and moves the project to its next state; a caller that walks the list takes the first ready action with `advances: true` |
| `gate` | the call approves a gate (`outline.approve`, `narration.approve`, `picks.approve`, `storyboard.approve`) |
| `auto_ok` | an agent may make this call when the owner has turned automatic running on. Every gate is `true` (owner's decision of 2026-11-18). `false` only for a paid call (`picks.suggest`): the owner must agree |
| `long_job`, `follow` | the call answers with a `job_id`; `follow` is the GET that follows it. Cancel it with the `*.cancel` action that appears in this list while the job runs |
| `uses_model`, `agent` | the call runs a model; `agent` is `{id, label, usable, reason}`: which agent would run it (`bti.agents`: the step's choice, the project's agent, the machine's default) and whether it can run on this machine. `usable: false` adds `agent_usable` to `needs`; `reason` is the Vietnamese sentence |
| `cost` | `null`, or `{kind, about}` with `kind` one of `machine_time` (the server is busy: voice about 1 hour, export about 25 minutes), `model` (an agent works: a draft about 20 minutes) or `paid` (it costs money). A caller that must not spend time or money stops and asks when `cost` is not null |
| `job_id` | only on a cancel action: the job it stops |

`storyboard.validate` is `GET /api/projects/{pid}`: its answer carries `issues`, the validation of the saved storyboard (the approve
call refuses while errors remain). The two typed-operation calls `picks.ops` and `storyboard.ops` are listed only when the running app
has those routes, so the answer is right before and after they are added.

### `jobs`

The jobs of this project that are queued, waiting or running, from the three registries (model jobs of the script step, long jobs, previews):
`{id, kind, state, progress, started, path, cancel}`. `kind` is `outline`, `narration`, `voice`, `draft`, `export`, `picks` or `preview`;
`started` is an ISO 8601 time; `path` is the GET that follows the job; `cancel` is the POST that stops it (null for a preview).

### `problems`

Damage the state found, each `{code, step, detail, fix}`; the codes are in the table of section 4 and `fix` names the call to make. A project
whose data is damaged still answers: the step carries the code in `problem`, and the first action is the repair the API offers
(`storyboard.restore` for a corrupt `storyboard.json`; `voice.generate` when the timing file is missing). A project whose own file
`project.json` cannot be read answers with every step locked, no action, and `problems[0].code == "project_file_damaged"`.

### Walking a project

```
loop:
  s = GET /api/projects/{pid}/state
  a = first of s.next_actions with ready and advances
  none -> stop: read s.steps and s.problems (a step that is current with nothing to advance waits for content: see `fill`)
  a.gate and not owner allows automatic running, or a.cost not null and the owner has not agreed -> stop and ask
  call a.method a.path with a.body; if it answers a job_id, poll a.follow until the job is done, then loop
```

## 2. The action ids

<!-- BEGIN GENERATED: actions -->
| id | step | route | gate | long job | model | cost | when it is listed, and when it is ready |
|---|---|---|---|---|---|---|---|
| `outline.generate` | script | `POST /api/projects/{pid}/outline/generate` |  | yes | script.outline | model: a few minutes | A project made from a book. Ready unless a model job of the project is running or the agent cannot run. Advances while there is no outline. |
| `outline.import` | script | `POST /api/projects/{pid}/outline/import` |  |  |  |  | A project made from a book. Always ready; the caller supplies the outline text (`fill`). |
| `outline.approve` | script | `POST /api/projects/{pid}/outline/approve` | yes |  |  |  | While the outline is not approved. Needs an outline. Advances. |
| `narration.generate` | script | `POST /api/projects/{pid}/narration/generate` |  | yes | script.narration | model: a few minutes | A project made from a book. Needs the approved outline; refused while beats are locked unless forced; ready unless a model job is running or the agent cannot run. Advances while there is no narration. |
| `narration.import` | script | `POST /api/projects/{pid}/narration/import` |  |  |  |  | A project made from a book. Needs an outline; the caller supplies the narration text (`fill`). |
| `narration.ops` | script | `POST /api/projects/{pid}/narration/ops` |  |  |  |  | Needs a narration; the caller supplies the typed operations (`fill`). |
| `narration.approve` | script | `POST /api/projects/{pid}/narration/approve` | yes |  |  |  | While the narration is not approved. Needs a narration and the approved outline. Advances. |
| `outline.cancel` | script | `POST /api/jobs/{job_id}/cancel` |  |  |  |  | While an outline job of the project runs. |
| `narration.cancel` | script | `POST /api/jobs/{job_id}/cancel` |  |  |  |  | While a narration job of the project runs. |
| `voice.generate` | voice | `POST /api/projects/{pid}/voice/generate` |  | yes |  | machine_time: about 1 hour | Once the narration is approved. Ready unless a voice job runs. Advances while the voice is not made or is out of date; when it is done the body re-reads everything. |
| `voice.cancel` | voice | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While a voice job of the project runs. |
| `picks.search` | picks | `POST /api/projects/{pid}/picks/search` |  |  |  |  | Once the picks step is open. Always ready; the body searches the painting's title when the project knows it. |
| `picks.import` | picks | `POST /api/projects/{pid}/picks/import` |  |  |  |  | Once the picks step is open. The caller supplies a source and source_id from a search (`fill`). |
| `picks.import_book_image` | picks | `POST /api/projects/{pid}/picks/import-book-image` |  |  |  |  | Once the picks step is open. The caller supplies a source_id from GET .../picks/book-images (`fill`). |
| `picks.import_clip` | picks | `POST /api/projects/{pid}/picks/import-clip` |  | yes |  | machine_time: about 1 minute | Once the picks step is open. Ready unless a picks job runs. The caller supplies the link and the range (`fill`). |
| `picks.suggest` | picks | `POST /api/projects/{pid}/picks/suggest` |  | yes |  | paid: You.com calls, charged per beat (auto_ok false) | Once the picks step is open. Paid: `auto_ok` is false, the owner must agree. Needs the approved narration and suggestions switched on. |
| `picks.put` | picks | `PUT /api/projects/{pid}/picks` |  |  |  |  | Once the picks step is open. The caller supplies the picks document (`fill`). |
| `picks.approve` | picks | `POST /api/projects/{pid}/picks/approve` | yes |  |  |  | While the picks are not approved. Needs the approved narration, picks with a main painting and no errors. Advances. |
| `picks.ops` | picks | `POST /api/projects/{pid}/picks/ops` |  |  |  |  | Only when the running app has the route. Once the picks step is open; the caller supplies the operations (`fill`). |
| `picks.cancel` | picks | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While a picks job (suggestions or a clip) of the project runs. |
| `draft.start` | edit | `POST /api/projects/{pid}/draft/start` |  | yes | draft | model: about 20 minutes | Once step 5 is open. Needs the voice and the approved picks, no draft job running and a usable agent. Advances while there is no draft (or it is out of date) and no storyboard. |
| `proposal.apply` | edit | `POST /api/projects/{pid}/proposals/{prop_id}/apply` |  |  |  |  | While the project has no storyboard and a draft proposal exists. Advances when the draft is up to date. |
| `storyboard.restore` | edit | `POST /api/projects/{pid}/storyboard/restore` |  |  |  |  | Only when storyboard.json is unreadable. Ready when history/ has a good copy. It is the repair: listed first. |
| `storyboard.validate` | edit | `GET /api/projects/{pid}` |  |  |  |  | While the storyboard is readable. Always ready; the answer's `issues` are the validation of the saved storyboard. |
| `storyboard.approve` | edit | `POST /api/projects/{pid}/approve` | yes |  |  |  | While the storyboard is not approved (or was edited after). The route refuses while validation errors remain: call storyboard.validate first. Advances. |
| `storyboard.preview` | edit | `POST /api/projects/{pid}/preview` |  | yes |  |  | While the storyboard is readable. Ready; renders a short clip (a job of a few seconds). |
| `storyboard.put` | edit | `PUT /api/projects/{pid}/storyboard` |  |  |  |  | While the storyboard is readable. The caller supplies the document (`fill`); base_rev is the current rev. |
| `storyboard.ops` | edit | `POST /api/projects/{pid}/storyboard/ops` |  |  |  |  | Only when the running app has the route. While the storyboard is readable; the caller supplies the operations (`fill`). |
| `draft.edit` | edit | `POST /api/projects/{pid}/draft/edit` |  | yes | edit.fast | model: from about 30 seconds to about 20 minutes | While the storyboard is readable. Ready unless a draft job runs or the agent cannot run. The caller supplies the instruction and the scope (`fill`). |
| `identity.set` | edit | `PUT /api/projects/{pid}/identity` |  |  |  |  | While the storyboard is readable. The caller supplies the style (`fill`); GET .../identity lists them. |
| `draft.cancel` | edit | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While a draft job of the project runs. |
| `export.start` | export | `POST /api/projects/{pid}/export/start` |  | yes |  | machine_time: about 25 minutes | Once the storyboard is approved. Ready unless an export runs, or the audio mix or timing is missing. Advances until a video is exported. |
| `export.cancel` | export | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While an export job of the project runs. |
<!-- END GENERATED: actions -->

## 3. The words of `needs`

<!-- BEGIN GENERATED: needs -->
| need | meaning | how to meet it |
|---|---|---|
| `book_data` | The project has no book data (it was imported from an earlier edit). | Nothing: the script steps do not apply to this project. |
| `documents_readable` | A document of the step cannot be read (see `problems`). | Repair the file named in `problems`, then ask for the state again. |
| `outline` | There is no outline yet. | Make one: outline.generate or outline.import. |
| `outline_approved` | The outline is not approved, or it changed after it was approved. | Call outline.approve. |
| `narration` | There is no narration yet. | Write one: narration.generate or narration.import. |
| `narration_approved` | The narration is not approved, or it changed after it was approved. | Call narration.approve. |
| `voice_done` | The voice is not made (or is out of date). | Call voice.generate and wait for its job. |
| `picks` | There are no picks yet. | Import the main painting: picks.import (as_main) or picks.import_book_image. |
| `main_asset` | No main painting is chosen in the picks. | Import a picture with as_main true (picks.import), or send picks.put with main_asset. |
| `picks_errors` | The picks have errors other than the main painting (a missing file, an unknown asset or region). | Read `issues` of GET /api/projects/{pid}/picks and fix them. |
| `picks_approved` | The picks are not approved, or they changed after they were approved. | Call picks.approve. |
| `storyboard` | The project has no storyboard yet. | Run draft.start, then proposal.apply. |
| `storyboard_readable` | storyboard.json cannot be read. | Call storyboard.restore. |
| `storyboard_approved` | The storyboard is not approved, or it was edited after it was approved. | Call storyboard.approve. |
| `history_copy` | There is no good copy of the storyboard in history/. | Make a new draft: draft.start. |
| `audio_mix` | The audio mix the storyboard names is missing. | Call voice.generate. |
| `timing` | timing.json is missing. | Call voice.generate. |
| `no_running_job` | A job of the same kind is already running for this project. | Wait for it (see `jobs`), or cancel it with the matching *.cancel action. |
| `agent_usable` | The agent that would run cannot run on this machine (see `agent.reason`). | Choose another agent: PUT /api/projects/{pid}/agent, GET /api/agents lists them. |
| `suggest_enabled` | Picture suggestions are switched off on this machine. | Use picks.search instead. |
| `locked_beats` | Some beats of the narration are locked and would be replaced. | Unlock them, or send {"force": true} (the body shown does). |
| `draft_proposal` | There is no draft proposal to apply. | Call draft.start and wait for its job. |
<!-- END GENERATED: needs -->

## 4. The error body

Every error the API returns has these keys; the ones that were there before are unchanged (`detail` is still a sentence for a person, and
the status code of a refusal does not change):

```json
409 {"code": "stale_revision",
     "detail": "base_rev does not match the saved revision",
     "fix": "GET the document again, apply your change to the revision in `current_rev` (the answer of that GET carries `rev`), then send the call again with it as base_rev.",
     "retry": "after_fix",
     "rev": "9f3c...", "current_rev": "9f3c..."}
422 {"code": "field_invalid", "detail": "width must be an integer", "field": "width",
     "fix": "Correct the request field that `field` (or `detail`) names, as `detail` says, and send the call again.", "retry": "after_fix"}
```

| key | meaning |
|---|---|
| `code` | stable snake_case word. An error that has no specific code gets one from its status (`not_found`, `field_invalid`, `conflict`, `internal_error`, ...) |
| `detail` | the sentence for a person, as before (a list for a request the framework refused) |
| `fix` | one English imperative sentence an agent can act on; it names the call to make when there is one. `{pid}` is the project's id when the call is a project route |
| `retry` | `no`: the same call can never work (what it names does not exist, the machine cannot do it); `after_fix`: change the request or the project as `fix` says, then call; `later`: the same call may work in a moment (something is busy, a service is not answering) |
| `field` | the request field that is wrong, when one is (a 422). `fields: [{path, problem}]` lists them for a request the framework refused (`code: request_invalid`) |
| `current_rev` | on a stale revision (`stale`, `stale_revision`): the revision to start again from. `rev` (as before) carries the same value where it was already there |

Other keys an error already carried stay (`issues`, `rev`, `locked`, `job_id`, `allowed`, `restore_from`, `data_error`, ...). An error that
carries its own `fix` keeps it. Not JSON, and so not covered: a file download that cannot be satisfied (`416 Range Not Satisfiable` has no body)
and the files and images the API serves.

## 5. The table of codes

Includes the codes of failed jobs (`error_code` of a long-job record), which a caller reads from the job, not from an HTTP error.

<!-- BEGIN GENERATED: codes -->
| code | retry | fix |
|---|---|---|
| `accept_all_required` | after_fix | This project has no storyboard yet: call apply again with {"accept": "all"}. |
| `accept_invalid` | after_fix | Send accept as "all" or as a list of change ids. |
| `agent_unavailable` | after_fix | The agent cannot run on this machine: choose another agent (PUT /api/projects/{pid}/agent, GET /api/agents lists them). |
| `agentic_role_needs_agy` | after_fix | Choose an agy or Claude Code model for this role (it works with files and tools). |
| `agy_auth` | after_fix | Ask the owner to sign agy in once on the server, then call again. |
| `agy_busy` | later | Another agent run is in progress: call again when it is finished. |
| `agy_config` | no | The agy on this machine cannot be used (too old or not running): choose the other agent or use provider auto. |
| `agy_error` | later | Call again, and if it repeats choose the other agent: agy reported an error. |
| `agy_missing` | no | The agy command is not installed on this machine: choose the other agent (PUT /api/projects/{pid}/agent) or use provider auto. |
| `agy_model` | after_fix | Choose another model or agent: agy does not know this model. |
| `agy_no_result` | later | Call again: agy stopped without an answer. |
| `agy_rate_limit` | later | The agy quota is used up: call again after `retry_after_seconds`, or choose the other agent (PUT /api/projects/{pid}/agent). |
| `agy_timeout` | later | The agent ran past its time limit and was stopped: call again, or work on fewer chapters. |
| `already_undone` | no | This turn was already undone. |
| `approval_stale` | after_fix | The storyboard changed after it was approved: approve it again (POST /api/projects/{pid}/approve), then export. |
| `artwork_not_found` | no | Use an artwork key listed by GET /api/library/artworks. |
| `asset_not_found` | no | Use an asset key that exists in the storyboard (GET /api/projects/{pid}/assets lists them). |
| `at_least_one_source` | after_fix | Keep at least one book source included in the brief options. |
| `bad_action` | after_fix | Send action as "overwrite" or "discard". |
| `bad_chapters` | after_fix | Send `chapters` as a list of chapter ids (at most 100). |
| `bad_model` | after_fix | Send `model` as a plain model id, or leave it out to use the project's agent. |
| `bad_pad` | after_fix | Send `pad` as true or false. |
| `bad_pronounce` | after_fix | Send `pronounce` as an object of written form -> spoken form (at most 500 entries). |
| `bad_provider` | after_fix | Send provider as "agy" or "auto". |
| `bad_request` | after_fix | Read `detail`, correct the request and send it again. |
| `bad_scope` | after_fix | Send scope as "all", "changed" or a list of chunk ids (and reseed as a list of chunk ids). |
| `bad_tempo` | after_fix | Send `tempo` as a number inside the range in `detail`. |
| `bad_text_character` | after_fix | Remove lone surrogate characters from the text you send, then send it again. |
| `base_rev_required` | after_fix | Add `base_rev` (the `rev` of the document you read) to the JSON body and send the call again. |
| `body_invalid` | after_fix | Send a JSON object as the body of this call. |
| `book_not_catalogued` | after_fix | Rebuild the library catalogue (python -m bti.library build), then call again. |
| `book_not_found` | no | Use a book id listed by GET /api/library/books. |
| `book_pdf_missing` | no | The PDF of this book is missing from the server. |
| `busy` | later | A job of this kind is already running for the project: wait for it (GET /api/projects/{pid}/longjobs) or cancel it, then call again. |
| `cancelled` | later | The job was cancelled: start it again to continue; finished parts are kept. |
| `cannot` | no | The project lacks what this request needs (for example a new painting, or a change of narration or voice): do that step first. |
| `claude_auth` | after_fix | Claude Code is not signed in on the server: the owner must run `claude auth login` there, then call again. |
| `claude_config` | no | Claude Code on this machine cannot be used (too old or not running): choose the other agent. |
| `claude_error` | later | Claude Code reported an error: call again; if it repeats choose the other agent. |
| `claude_missing` | no | Claude Code (the claude command) is not installed on the server: choose the other agent (PUT /api/projects/{pid}/agent). |
| `claude_model` | after_fix | Use a Claude Code model id of the form claude:<model>@<effort>, or choose an agent. |
| `claude_no_result` | later | Claude Code stopped without an answer: call again. |
| `claude_rate_limit` | later | The Claude Code quota is used up: call again after `retry_after_seconds`, or choose the other agent. |
| `claude_timeout` | later | The agent ran past its time limit and was stopped: call again, or work on fewer chapters. |
| `compile_empty` | later | No shot could be built from the agent's result: run the draft again. |
| `compile_error` | after_fix | The edit could not be assembled (parameter or syntax errors): send a simpler instruction or a narrower scope. |
| `confirm_required` | after_fix | This call is paid: send confirm_paid: true only when the owner agreed to the cost. |
| `conflict` | after_fix | Read `detail`: the project is in a state that refuses this call. GET /api/projects/{pid}/state shows what to do first. |
| `data_unusable` | after_fix | A data file of the project is missing or damaged: read `detail` for its name and repair it. |
| `delete_not_confirmed` | after_fix | Call DELETE /api/projects/{pid}?confirm={pid}: `confirm` must be the exact project id. |
| `document_corrupt` | after_fix | The project file named in `detail` cannot be read: restore it from a backup or history, or remove it, then call again. |
| `document_invalid` | after_fix | The document has the wrong shape (see `detail`): send a document as GET returns it. |
| `dossier_not_found` | no | This artwork has no dossier yet: rebuild the library (python -m bti.library build). |
| `draft_no_output` | later | The agent wrote no result file: run the draft again (POST /api/projects/{pid}/draft/start). |
| `draft_not_ready` | after_fix | Make the voice (timing.json) and approve the picks first: GET /api/projects/{pid}/state shows which is missing. |
| `draft_tampered` | after_fix | The agent changed files outside its workspace and its result was dropped: check the project, then run the draft again. |
| `edit_bad_scope` | after_fix | Send scope as exactly one of {"shots": [ids]}, {"chapter": id} or {"all": true}, an instruction of 1 to 2000 characters and mode auto, fast or deep. |
| `edit_degraded` | after_fix | The edit was refused because a shot would be degraded or incomplete: narrow the instruction. |
| `edit_empty_instruction` | after_fix | Send `instruction` as a non-empty text. |
| `edit_failed` | later | The edit failed unexpectedly and nothing changed: call again. |
| `edit_needs_agy` | after_fix | Editing by instruction needs an agent (agy or Claude Code), not provider auto: choose an agent. |
| `edit_no_change` | after_fix | The agent changed nothing: restate the instruction more concretely. |
| `edit_no_storyboard` | after_fix | Editing needs an existing storyboard: apply the first draft proposal first. |
| `edit_outside_scope` | after_fix | The agent changed something outside the scope or a locked shot: narrow the instruction to the scope and call again. |
| `edit_running` | later | An edit is running: cancel it (POST /api/longjobs/{job_id}/cancel) or wait, then delete the thread. |
| `escalate` | after_fix | This request needs a closer look at the picture or more than the chosen scope: call again with mode deep. |
| `export_file_not_found` | no | Use a file name listed by GET /api/projects/{pid}/export (`files`). |
| `field_invalid` | after_fix | Correct the request field that `field` (or `detail`) names, as `detail` says, and send the call again. |
| `field_required` | after_fix | Add the field that `field` names to the JSON body and send the call again. |
| `file_too_large` | after_fix | Send a file of a supported kind (jpg, jpeg, png, webp, mp4, webm, mov or m4v) of at most 80 MB. |
| `forbidden` | no | This call is not allowed on this project; read `detail` for the rule. |
| `frames_mismatch` | after_fix | The video has the wrong number of frames: call POST /api/projects/{pid}/export/start again; if it repeats, validate the storyboard. |
| `history_file_not_found` | after_fix | Name a file that exists in the project's history/ folder, or leave `file` out to use the newest good one. |
| `history_file_unreadable` | after_fix | The named history file is not a storyboard: name another file, or leave `file` out. |
| `identity_style_required` | after_fix | Send `style` as an identity style id (GET /api/projects/{pid}/identity lists them). |
| `identity_style_unknown` | after_fix | Use one of the ids in `allowed` as `style`. |
| `image_empty` | after_fix | The image file is empty: send another file. |
| `image_extract_failed` | no | This image cannot be extracted from the book: skip it. |
| `image_not_in_work` | no | Ask for an image listed by GET /api/library/works/{book}/{n}. |
| `image_truncated` | after_fix | The image is cut off: send a complete file. |
| `image_unreadable` | after_fix | The image cannot be read: send a jpg, png or webp that opens. |
| `internal_error` | no | This is a bug of the server, not of your input: do not repeat the call; report `detail`. |
| `interrupted` | later | The server restarted while the job ran: start the same job again; finished parts are kept. |
| `invalid` | after_fix | Correct the request as `detail` says and send it again. |
| `invalid_model` | after_fix | Send each role's model as a non-empty model id string. |
| `invalid_payload` | after_fix | Send the body in the shape of the route: read `detail`, correct it and send again. |
| `invalid_project_path` | no | Use a project id that names a folder directly under the projects folder. |
| `job_not_found` | no | Use the job id the start call answered with; after a server restart only finished jobs are still known. |
| `join_failed` | later | The parts could not be joined: call POST /api/projects/{pid}/export/start again. |
| `library_data_corrupt` | after_fix | A file of the book library is damaged: repair it or rebuild the library (python -m bti.library build), then call again. |
| `library_file_unreadable` | after_fix | A file of the library cannot be read (see `detail`): repair it, then call again. |
| `licence_rejected` | after_fix | The licence of this picture is not accepted: choose another picture. |
| `locked_beats` | after_fix | Unlock the beats named in `locked`, or send {"force": true} to replace them. |
| `longjob_bad_kind` | after_fix | Use a job kind such as voice, draft, export or picks in `kind`, or leave it out. |
| `longjob_missing` | no | The long-job runner is not installed on this server: the job cannot be started. |
| `longjob_not_found` | no | Use the job id the start call answered with (GET /api/projects/{pid}/longjobs lists the jobs of a project). |
| `longjob_running` | later | Cancel the long job (POST /api/longjobs/{job_id}/cancel) or wait until it is finished, then call again. |
| `main_asset_unreadable` | after_fix | The main painting has no readable file: import it again (POST /api/projects/{pid}/picks/import with as_main). |
| `merge_refused` | after_fix | Read `detail`: choose two different artworks that can be merged. |
| `method_not_allowed` | no | Use another HTTP method for this path (the Allow header of the answer lists them). |
| `model_invalid` | after_fix | Send `model` as a model id string, or leave it out to use the project's agent. |
| `model_job_busy` | later | Another model job is running for this project: wait for it (GET /api/jobs/{job_id}) or cancel it (POST /api/jobs/{job_id}/cancel), then call again. |
| `model_required` | after_fix | Name a model in `model` (GET /api/models lists them), or leave `model` out to use the project's agent. |
| `model_unavailable` | after_fix | The model cannot run on this machine (see `missing_env`): choose another model or agent. |
| `mux_failed` | later | Sound and chapters could not be added: call POST /api/projects/{pid}/export/start again. |
| `narration_has_errors` | after_fix | Fix the errors listed in `issues` and `chapter_diff` (PUT /api/projects/{pid}/narration or POST .../narration/ops), then approve again. |
| `narration_missing` | after_fix | There is no narration: write and approve it first (see GET /api/projects/{pid}/state). |
| `narration_not_approved` | after_fix | Approve the narration first: POST /api/projects/{pid}/narration/approve. |
| `narration_unreadable` | after_fix | The pasted narration could not be placed (see `issues`): correct the text and import it again; nothing was overwritten. |
| `no_audio` | after_fix | The audio mix is missing: make the voice again (POST /api/projects/{pid}/voice/generate). |
| `no_audio_file` | after_fix | This project has no audio file yet: make the voice first (POST /api/projects/{pid}/voice/generate). |
| `no_chunk` | after_fix | That sentence has no audio yet: make the voice with POST /api/projects/{pid}/voice/generate. |
| `no_history_copy` | no | There is no good copy in history/: the storyboard cannot be restored; make a new draft with POST /api/projects/{pid}/draft/start. |
| `no_narration` | after_fix | There is no narration: write it with POST /api/projects/{pid}/narration/generate or /narration/import. |
| `no_outline` | after_fix | There is no outline: make it with POST /api/projects/{pid}/outline/generate or /outline/import. |
| `no_picks` | after_fix | There are no picks yet: add the main painting (POST /api/projects/{pid}/picks/import with as_main) first. |
| `no_storyboard` | after_fix | There is no storyboard yet: run the draft and apply its proposal first. |
| `no_timing` | after_fix | Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json is missing or empty. |
| `no_voice` | after_fix | There is no voice mix yet: make it with POST /api/projects/{pid}/voice/generate. |
| `not_approved` | after_fix | Approve the storyboard first: POST /api/projects/{pid}/approve with {"rev": <storyboard rev>}. |
| `not_found` | no | Check the ids and the path in the call: what it names does not exist. List what exists with the matching GET route. |
| `not_needs_choice` | no | This turn is not waiting for a choice: GET /api/projects/{pid}/draft/thread shows its status. |
| `nothing_to_restore` | no | Leave the storyboard as it is: storyboard.json is readable, there is nothing to restore. |
| `nothing_to_say` | after_fix | The narration has no sentence to speak: write it (POST /api/projects/{pid}/narration/generate). |
| `op_invalid` | after_fix | Correct the operation named in `detail` (GET the narration for the current beat and chapter ids), then send the ops again. |
| `options_error` | after_fix | Correct the option named in `detail` and send the options again. |
| `outline_has_errors` | after_fix | Fix the errors listed in `issues` (PUT /api/projects/{pid}/outline), then approve again. |
| `outline_missing` | after_fix | Make the outline first: POST /api/projects/{pid}/outline/generate, then approve it. |
| `outline_not_approved` | after_fix | Approve the outline: POST /api/projects/{pid}/outline/approve with {"rev": <outline rev>}. |
| `outline_stale` | after_fix | The outline changed after it was approved: approve it again (POST /api/projects/{pid}/outline/approve). |
| `outline_unreadable` | after_fix | The pasted outline could not be read (see `issues`): correct the text and import it again; nothing was overwritten. |
| `page_not_found` | no | Ask for a page that exists in the book. |
| `page_not_in_work` | no | Ask for a page inside the page range of this work. |
| `part_missing` | later | A rendered part is missing: call POST /api/projects/{pid}/export/start again; finished parts are kept. |
| `picks_corrupt` | after_fix | Save the picks again (PUT /api/projects/{pid}/picks) or repair picks.json: it cannot be read. |
| `picks_error` | after_fix | Read `detail`, correct the request or the picks, then call again. |
| `picks_have_errors` | after_fix | Fix the errors listed in `issues` (the main painting, missing files, unknown assets or regions), then approve again. |
| `picks_missing` | after_fix | Choose the pictures first (see GET /api/projects/{pid}/picks): picks.json is missing. |
| `picks_no_main` | after_fix | Choose the main painting (POST /api/projects/{pid}/picks/import with as_main), then approve the picks. |
| `picks_shape` | after_fix | Save the picks again (PUT /api/projects/{pid}/picks): picks.json has the wrong shape (see `detail`). |
| `plan_failed` | after_fix | The export could not be planned: GET /api/projects/{pid} shows the storyboard's issues; fix them first. |
| `preview_running` | later | Wait until the preview is finished (GET /api/jobs/{job_id}), then call again. |
| `preview_too_long` | after_fix | Ask for a shorter preview: t1 - t0 must stay within the limit in `detail`. |
| `preview_too_many_frames` | after_fix | Ask for fewer frames: shorten the range (t1 - t0) or lower `fps`. |
| `project_busy` | later | A save of this project is in progress: call again in a moment. |
| `project_create_refused` | after_fix | Read `detail`: change the slug, the artwork or the work ids and call again. |
| `project_file_damaged` | after_fix | Repair or remove the damaged project.json by hand, then call again. |
| `project_gone` | no | The project was removed while the job ran. |
| `project_is_symlink` | no | The project folder is a symbolic link: remove the link by hand; the API will not delete through it. |
| `project_missing` | no | The project folder is missing: use the id of a project that exists. |
| `project_not_found` | no | Use the id of a project that exists: GET /api/projects lists them. |
| `project_protected` | no | This project is protected: do not delete it. |
| `project_source_missing` | after_fix | A source file of the artwork is missing: rebuild the library (python -m bti.library build). |
| `prompt_error` | after_fix | The prompt cannot be built from the current documents: read `detail`. |
| `proposal_corrupt` | after_fix | The proposal file was damaged and has been set aside: make a new proposal. |
| `proposal_has_errors` | after_fix | The proposal's storyboard has errors (see `issues`): make a new proposal, or fix the values and save them with PUT /api/projects/{pid}/storyboard. |
| `proposal_malformed` | after_fix | The proposal's storyboard has the wrong shape: make a new proposal (POST /api/projects/{pid}/draft/start). |
| `proposal_not_found` | no | Use a proposal id from GET /api/projects/{pid}/proposals. |
| `query_required` | after_fix | Send `query` (words to search for) or a `beat`. |
| `range_not_satisfiable` | after_fix | Ask for a byte range inside the file, or send no Range header. |
| `real_models_off` | no | Real model and paid calls are switched off on this machine (BTI_NO_REAL_MODELS): the owner must turn them on. |
| `region_name` | after_fix | Use a region name made of letters, digits, - and _ (see `region` for the bad one). |
| `region_outside` | after_fix | Keep the region inside the picture (x and y between 0 and 1): see `region`. |
| `region_shape` | after_fix | Give the region numeric x and y (and a short label): see `region` for the bad one. |
| `render_failed` | after_fix | Change the values of the shot (and overlay, technique, asset) the answer names, save the storyboard, then render again. |
| `request_invalid` | after_fix | Correct every request field listed in `fields` (their `path` and `problem`) and send the call again. |
| `route_not_found` | no | There is no such route: check the path and the method against docs/AGENT_API.md or GET /openapi.json. |
| `save_refused` | after_fix | The engine refused the document: read `issues`, fix the values they name, then send it again. |
| `scope_needs_storyboard` | after_fix | This needs an existing storyboard: apply the first draft proposal first (POST /api/projects/{pid}/proposals/{id}/apply). |
| `script_job_running` | later | Cancel the model job (POST /api/jobs/{job_id}/cancel) or wait until it is finished, then call again. |
| `shot_not_found` | no | Use a shot id that exists in the storyboard (GET /api/projects/{pid}). |
| `source_error` | later | The picture or video source failed; call again in a minute, or use another source. |
| `source_not_found` | no | Use a source name listed in the artwork's dossier. |
| `source_rate_limited` | later | The source asked to slow down: call again after `retry_after` seconds (a minute when it is null). |
| `source_text_missing` | after_fix | The source text file is missing: rebuild the library (python -m bti.library build). |
| `source_timeout` | later | The service did not answer in time; call again in a minute. |
| `source_unavailable` | later | The service this call needs is not answering; call again in a minute. |
| `source_unreachable` | later | The picture source is busy or not answering: call again in a minute. |
| `spec_invalid` | later | The model answered in the wrong shape even after one repair: call again, or use mode deep. |
| `split_refused` | after_fix | Read `detail`: choose a work that can be split off. |
| `stale` | after_fix | GET the document again, apply your change to the revision in `current_rev` (the answer of that GET carries `rev`), then send the call again with it as base_rev. |
| `stale_revision` | after_fix | GET the document again, apply your change to the revision in `current_rev` (the answer of that GET carries `rev`), then send the call again with it as base_rev. |
| `storyboard_corrupt` | after_fix | Call POST /api/projects/{pid}/storyboard/restore (no body) to bring back the newest good copy from history/, then call again. |
| `storyboard_has_errors` | after_fix | Fix every issue with level `error` in `issues` (GET /api/projects/{pid} lists them), then call again. |
| `storyboard_incomplete` | after_fix | Fill in the items named in the answer (their technique needs a picture, a clip or a mask), then approve again. |
| `storyboard_missing` | after_fix | This project has no storyboard yet: run the draft first (POST /api/projects/{pid}/draft/start). |
| `storyboard_not_found` | after_fix | This project has no storyboard yet: run the draft (POST /api/projects/{pid}/draft/start), then apply its proposal. |
| `storyboard_unreadable` | after_fix | Call POST /api/projects/{pid}/storyboard/restore to bring back the newest good copy: storyboard.json cannot be read. |
| `storyboard_unusable` | after_fix | Repair storyboard.json: POST /api/projects/{pid}/storyboard/restore brings back the newest good copy from history/. |
| `style_not_found` | no | Use a style id that exists under style/ (the storyboard names it in `style`). |
| `style_unusable` | after_fix | The style named by the storyboard is missing or damaged: set `style` in the storyboard to a style that exists under style/. |
| `suggest_bad_answer` | later | The suggestion service gave an unusable answer: call again later. |
| `suggest_failed` | later | The suggestion service failed: call again later, or use POST .../picks/search. |
| `suggest_key_refused` | no | The suggestion service refused the key: use POST /api/projects/{pid}/picks/search instead. |
| `suggest_no_key` | no | The key for suggestions is not set on this machine: search with POST /api/projects/{pid}/picks/search instead. |
| `suggest_off` | no | Suggestions are switched off in config/picks.json: search with POST /api/projects/{pid}/picks/search instead. |
| `suggest_quota` | later | The suggestion service quota is used up: call again later, or use POST .../picks/search. |
| `suggest_timeout` | later | The suggestion service did not answer in time: call again later. |
| `template_missing` | no | The draft task template is missing from this installation: restore skills/storyboard_draft/TASK.template.md. |
| `thumbnail_failed` | no | No thumbnail can be made of this file: use the file itself. |
| `timing_corrupt` | after_fix | Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json cannot be read. |
| `timing_missing` | after_fix | Make the voice first (POST /api/projects/{pid}/voice/generate): timing.json is missing. |
| `timing_shape` | after_fix | Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json has the wrong shape (see `detail`). |
| `timing_unusable` | after_fix | Make the voice again with POST /api/projects/{pid}/voice/generate: timing.json is missing or damaged. |
| `too_deep` | after_fix | Flatten the JSON body to at most 40 levels of nesting. |
| `too_large` | after_fix | Send a smaller JSON body (at most 8 MB). |
| `too_many` | after_fix | Send fewer beat ids in `beats` (the limit is in `detail`). |
| `tool_missing` | no | A tool the clip needs (yt-dlp or ffmpeg) is not installed on this machine. |
| `turn_data_lost` | after_fix | The stored storyboards of this turn are gone: send the instruction again as a new edit. |
| `turn_frame_not_found` | no | Use `when` before or after, and a turn and shot that exist (GET /api/projects/{pid}/draft/thread). |
| `turn_not_applied` | no | Only an applied turn can be undone: GET /api/projects/{pid}/draft/thread shows its status. |
| `turn_not_found` | no | Use a turn id listed by GET /api/projects/{pid}/draft/thread. |
| `undo_conflict` | after_fix | Some shots were changed since this turn (see `conflicts`): call undo again with {"force": true} to override them. |
| `undo_unavailable` | no | The earlier storyboard of this turn is no longer kept (only the last 20 turns are): edit the shots by hand instead. |
| `undrawable` | after_fix | Change the shots named in `issues` so the engine can draw them, then approve again. |
| `unknown_agent` | after_fix | Use one of the agent ids in `allowed` (GET /api/agents lists them). |
| `unknown_asset` | after_fix | Use an asset key that exists in the picks (GET /api/projects/{pid}/picks lists them), or import the picture first. |
| `unknown_change_ids` | after_fix | Use change ids listed by GET /api/projects/{pid}/proposals/{id}, or send accept: "all". |
| `unknown_chapter` | after_fix | Use chapter ids that exist in the outline (GET /api/projects/{pid}/outline). |
| `unknown_model` | after_fix | Use a model id listed by GET /api/models (or GET /api/settings/models). |
| `unknown_role` | after_fix | Use only role names listed by GET /api/settings/models. |
| `unknown_source` | after_fix | Use one of the picture sources the picks page lists (commons, met, pexels, pixabay, osm). |
| `unknown_step` | after_fix | Use a step id that GET /api/projects/{pid}/agent lists under `effective`. |
| `unknown_technique` | after_fix | Use a technique id that exists: GET /api/styles/{style} lists them. |
| `unsupported_file_type` | after_fix | Send a file of a supported kind (jpg, jpeg, png, webp, mp4, webm, mov or m4v) of at most 80 MB. |
| `unsupported_media` | after_fix | Send a file this route can read, or leave the file out. |
| `validation_failed` | after_fix | Fix every issue with level `error` in `issues`, then send the storyboard again. |
| `video_bad_range` | after_fix | Send `start` and `end` as numbers of seconds with a clip length inside the allowed range. |
| `video_bad_url` | after_fix | Send a YouTube link (youtube.com or youtu.be) in `url`. |
| `video_fetch_failed` | later | The video could not be fetched: call again in a minute, or use another link. |
| `video_not_main` | after_fix | Choose a picture, not a video, as the main painting. |
| `video_timeout` | later | The video download took too long: call again, or choose a shorter range. |
| `video_unreadable` | after_fix | The video cannot be read: send another file (mp4, webm, mov or m4v). |
| `voice_align_failed` | later | The word timing could not be made: call POST /api/projects/{pid}/voice/generate again. |
| `voice_assemble_failed` | later | The mix could not be made: call POST /api/projects/{pid}/voice/generate again. |
| `voice_busy` | later | A voice job is already running: wait for it (GET /api/projects/{pid}/longjobs) or cancel it, then call again. |
| `voice_chunks_failed` | later | Some sentences could not be spoken (see `sentences` or the job log): call POST /api/projects/{pid}/voice/generate again. |
| `voice_chunks_missing` | later | A sentence has no audio: call POST /api/projects/{pid}/voice/generate again to read the missing ones. |
| `voice_not_configured` | no | This machine has no voice worker (or aligner) configured: the voice cannot be made here. |
| `voice_worker_failed` | later | The voice worker failed: call POST /api/projects/{pid}/voice/generate again, finished sentences are kept. |
| `work_not_found` | no | Use a work id (book/n) listed by GET /api/library/books/{book}/works. |
| `workspace_invalid` | after_fix | The draft workspace is damaged: run the draft again. |
| `youcom_key_missing` | no | The You.com key is not set on this machine: use the free sources, or paste a YouTube link. |
<!-- END GENERATED: codes -->
