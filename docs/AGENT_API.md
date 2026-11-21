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
     "body": {"provider": "agy", "note": null}, "ready": true, "needs": [], "gate": false, "auto_ok": true, "long_job": true,
     "uses_model": true, "agent": {"id": "gemini", "label": "Gemini 3.8 Flash", "usable": true, "reason": null},
     "cost": {"kind": "model", "about": "about 20 minutes"}, "advances": true, "follow": "GET /api/longjobs/{job_id}"},
    {"id": "picks.import", "step": "picks", "label": "Nhập hình", "method": "POST", "path": "/api/projects/arn/picks/import",
     "body": null, "ready": true, "needs": [], "gate": false, "auto_ok": true, "long_job": false, "uses_model": false, "agent": null,
     "cost": null, "advances": false, "fill": ["source", "source_id"], "body_template": {"source": null, "source_id": null, "as_main": false}}
  ],
  "jobs": [],
  "problems": [],
  "auto": {"enabled": false, "gates": {"outline": true, "narration": true, "picks": true, "storyboard": true},
           "spend": {"model": true, "machine_time": true, "paid": false}},
  "approvals": {"outline": {"by": "human", "at": "2026-11-18T10:00:00+0700", "stands": true},
                "narration": {"by": "cli:bti", "at": "2026-11-18T10:20:00+0700", "stands": true}, "picks": {"by": "human", "at": "2026-11-18T11:00:00+0700", "stands": true},
                "storyboard": null},
  "title": {"state": "done", "text": "The Saint Who Was Also an Advertisement", "by": "agent:claude:claude-opus-5-5@high", "at": "2026-11-20T10:00:00+0700", "source": "agent", "candidates": 6, "stale": false}
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
| `fill`, `body_template` | when the caller supplies content: the fields to supply, and a template with the values the state knows (for example the current `base_rev`) filled in. `body` is then null, except on `picks.ops` and `storyboard.ops` (below) |
| `ready`, `needs` | `ready` is true when the call can be made now. Otherwise `needs` lists what is missing, as words from the table in section 3 |
| `advances` | true when the call is ready and moves the project to its next state; a caller that walks the list takes the first ready action with `advances: true` |
| `gate` | the call approves a gate (`outline.approve`, `narration.approve`, `picks.approve`, `storyboard.approve`) |
| `auto_ok` | an agent (an actor that is not `human`) may make this call now, by the owner's `auto` document (section "Automatic running" below): for a gate, automatic running is on and the gate is allowed (so `false` by default); for a call with a `cost`, that kind of spending is allowed (`model` and `machine_time` by default, `paid` never: `picks.suggest` is always `false`); `true` for every other call |
| `long_job`, `follow` | the call answers with a `job_id`; `follow` is the GET that follows it. Cancel it with the `*.cancel` action that appears in this list while the job runs |
| `uses_model`, `agent` | the call runs a model; `agent` is `{id, label, usable, reason}`: which agent would run it (`bti.agents`: the step's choice, the project's agent, the machine's default) and whether it can run on this machine. `usable: false` adds `agent_usable` to `needs`; `reason` is the Vietnamese sentence |
| `cost` | `null`, or `{kind, about}` with `kind` one of `machine_time` (the server is busy: voice about 1 hour, export about 25 minutes), `model` (an agent works: a draft about 20 minutes) or `paid` (it costs money). A caller that must not spend time or money stops and asks when `cost` is not null |
| `job_id` | only on a cancel action: the job it stops |

`storyboard.validate` is `GET /api/projects/{pid}`: its answer carries `issues`, the validation of the saved storyboard (the approve
call refuses while errors remain).

The typed operations (section 6) are listed whenever their step is open: `picks.ops` and `storyboard.ops` carry a `body` that is a **dry run**
(`dry_run: true`, nothing is written) of the first example of the operations registry (`GET /api/ops/schema`; the example is the registry's own, not
written for the state), with the current `base_rev` and an `actor` made from the project's agent; `fill: ["ops"]` and `body_template` give the real
call. The registry's examples are written for the operations' test project: on another project the dry run may be refused with a typed error
(`unknown_asset`, `unknown_shot`, ...), which is how an agent learns the ids of the project. `changes.list` appears once the change log has a batch;
`changes.undo` names the newest batch that can be undone now (its copies are kept, nothing undid it, nothing it changed was changed since).

### `jobs`

The jobs of this project that are queued, waiting or running, from the three registries (model jobs of the script step, long jobs, previews):
`{id, kind, state, progress, started, path, cancel}`. `kind` is `outline`, `narration`, `voice`, `draft`, `export`, `picks`, `auto` (an automatic run, section 9) or `preview`;
`started` is an ISO 8601 time; `path` is the GET that follows the job; `cancel` is the POST that stops it (null for a preview).

### `problems`

Damage the state found, each `{code, step, detail, fix}`; the codes are in the table of section 4 and `fix` names the call to make. A project
whose data is damaged still answers: the step carries the code in `problem`, and the first action is the repair the API offers
(`storyboard.restore` for a corrupt `storyboard.json`; `voice.generate` when the timing file is missing). A project whose own file
`project.json` cannot be read answers with every step locked, no action, and `problems[0].code == "project_file_damaged"`.

When the app has an output folder (section 10) and writing it failed, the answer carries one more key, `warnings`: `[{code, detail, sentence}]` (`code` is `output_failed`,
`output_part_failed` or `output_sheets_failed`; `sentence` is Vietnamese). The key is absent when there is nothing to say. The action `output.build` is listed when the app has an output
folder and the project is not a reference project.

### Automatic running and who approved

By default every gate is approved by the owner on the page. The owner may turn automatic running on for one project and say which gates an
agent may approve; the rule is the server's, not the command's. The state answer carries the owner's settings and the record of every approval:

* `auto`: `{enabled, gates: {outline, narration, picks, storyboard}, spend: {model, machine_time, paid}}`, the project's `auto.json` (a project that has
  none has the defaults: nothing enabled, every gate allowed once enabled, `model` and `machine_time` spending allowed, `paid` never).
* `approvals`: for each gate `null` (never approved, or the approval was dropped by an edit) or `{by, at, stands}`: who approved (`human`,
  `agent:<model id>` or `cli:<name>`; `null` for an approval made before it was recorded), when, and whether it still stands (false: the document
  changed after it, or an earlier gate was undone).

```
GET /api/projects/{pid}/auto   -> {"schema": "bti.auto/1", "rev": "...", "enabled": false, "gates": {...}, "spend": {...}, "warnings": []}
PUT /api/projects/{pid}/auto   {"base_rev": "<rev>", "enabled": true, "gates": {"storyboard": false}, "spend": {"machine_time": false}}   -> the same answer
```

`PUT` changes only the keys it names (`gates` and `spend` only the names they list); `409 stale` for an old `base_rev` (with `current_rev`),
`422 invalid_field` (with `fields`) for an unknown name or a value that is not true or false, and for `spend.paid: true` (an agent never spends money:
the value stays false, whatever a file says). Only the owner changes it: a `PUT` with an `actor` that is not `human` is `403 auto_needs_human`.

The four approval routes (`POST .../outline/approve`, `.../narration/approve`, `.../picks/approve` and `POST .../approve` for the storyboard) take an optional
`actor` in the body: `human` (the default: the page sends none), `agent:<model id>` or `cli:<name>`; anything else is `422 invalid_field`. An actor that is not
`human` may approve only when the project's `auto` is `enabled` and allows that gate; otherwise `403 gate_needs_human` (with `gate`, `actor`, `reason`: `auto_off` or
`gate_not_allowed`, and `auto`), before anything is read or written, and `fix` says the owner approves on the page or turns automatic running on. The actor is
stored with the approval (`approval.by` in `script/outline.json`, `script/narration.json` and `picks.json`; `approvals.storyboard.by` in `storyboard.json`). The one paid call
(`POST .../picks/suggest`) is refused to any actor that is not `human` (`403 spend_needs_human`). The `actor` is what the caller says it is: the rule keeps an honest
agent from approving or spending what the owner did not allow, it is not an authentication. The `bti` command always sends `cli:<name>` (see `AGENTS.md`).

### Walking a project

```
loop:
  s = GET /api/projects/{pid}/state
  a = first of s.next_actions with ready and advances
  none -> stop: read s.steps and s.problems (a step that is current with nothing to advance waits for content: see `fill`)
  not a.auto_ok (a gate the owner did not allow an agent to approve, or a spend the owner did not allow), or a.cost not null and the owner has not agreed -> stop and ask
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
| `title.generate` | script | `POST /api/projects/{pid}/title/generate` |  | yes | script.title | model: about 1 minute | A project made from a book. Needs the approved narration, no other agent job running on the project (the pictures agent, a prompt-box turn, a draft, a title job) and a usable agent. An agent reads the narration and writes the title by the skill; the first of its candidates becomes the title in use (the storyboard, the export's description and the output folder use it). Advances while the title is not written (`none`) or the narration changed after it was written (`stale`) and the project has no storyboard yet (a title written later changes the storyboard and so its approval: that is for the owner to ask); a title a person or an operator set is never stale and is replaced only by this call made by hand. The automatic run takes it by itself (nobody approves a title), before the voice. Optional body field `note` (text, at most 600 characters, `--set note=...`): the owner's wish for this title in their words. |
| `title.set` | script | `PUT /api/projects/{pid}/title` |  |  |  |  | A project made from a book. Always ready; the caller supplies `text` (`--set text=...`: one line of at most 60 characters; the banned phrases are not looked for), or sends `option` (the number, from 1, of a candidate of GET .../title) in a body of its own. Never stale afterwards. When the project has a storyboard the channel identity is applied again with the title in the same call: its revision changes and its approval stops standing (the answer says so). While the storyboard does not fit the voice (`storyboard_off_voice`) the title is stored all the same, the storyboard is left as it is and the answer says it takes the title when `storyboard.retime` has fitted it to the voice. |
| `title.cancel` | script | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While a title job of the project runs. |
| `voice.generate` | voice | `POST /api/projects/{pid}/voice/generate` |  | yes |  | machine_time: about 1 hour | Once the narration is approved. Ready unless a voice job runs. Advances while the voice is not made or is out of date; when it is done the body re-reads everything. |
| `voice.cancel` | voice | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While a voice job of the project runs. |
| `picks.search` | picks | `POST /api/projects/{pid}/picks/search` |  |  |  |  | Once the picks step is open. Always ready; the body searches the painting's title when the project knows it. |
| `picks.import` | picks | `POST /api/projects/{pid}/picks/import` |  |  |  |  | Once the picks step is open. The caller supplies a source and source_id from a search (`fill`). |
| `picks.import_book_image` | picks | `POST /api/projects/{pid}/picks/import-book-image` |  |  |  |  | Once the picks step is open. The caller supplies a source_id from GET .../picks/book-images (`fill`). |
| `picks.import_clip` | picks | `POST /api/projects/{pid}/picks/import-clip` |  | yes |  | machine_time: about 1 minute | Once the picks step is open. Ready unless a picks job runs. The caller supplies the link and the range (`fill`). |
| `picks.suggest` | picks | `POST /api/projects/{pid}/picks/suggest` |  | yes |  | paid: You.com calls, charged per beat (auto_ok false) | Once the picks step is open. Paid: `auto_ok` is false, the owner must agree. Needs the approved narration and suggestions switched on. |
| `picks.put` | picks | `PUT /api/projects/{pid}/picks` |  |  |  |  | Once the picks step is open. The caller supplies the picks document (`fill`). |
| `picks.auto` | picks | `POST /api/projects/{pid}/picks/auto` |  | yes | picks | model: about 20 minutes | Once the picks step is open. Needs the approved narration, a main painting and a usable agent; refused while the picks are approved unless `redo` is true, and while another long job of the project runs (the agent's choice, a prompt-box turn or a draft: one at a time; an automatic run goes on: only the run itself, as the `actor` `agent:auto`, takes it, any other caller is refused with `agent_job_running`). It never approves and never calls the paid suggestion service. Advances while no line has pictures yet. |
| `picks.retry_missing` | picks | `POST /api/projects/{pid}/picks/retry-missing` |  | yes |  |  | Listed only while a line of the picks says that a picture the agent chose could not be downloaded (`missing` with the code `import_limited`: the source limited the downloads; a `web_budget` is not retried here). No model and no search: for each such line it reads what the agent chose in the saved files of the last run of picks.auto (cache/picks_auto: plan, search, choice, and the second choice when there is one), imports that picture (at most one request a second to a host, and a refusal of "too many requests" is waited for), and writes the line again the way picks.auto would have written it: the plan's pictures in the plan's order, the agent's reason as the note of the new picture, `missing` without what it fixed, one batch of the change log for the line (undoable). A line that was changed after the agent wrote it is left alone. Ready while such lines exist and the saved files are there (`picks_saved_files` otherwise), the picks are open, and no agent job runs. It advances once for the lines it has not looked at since the last run of picks.auto: the automatic run takes it once, before the pictures gate; a line still limited after that stays listed (call it again later by hand). Optional body field `beats` (a list of line ids) limits it to those lines. Writing drops the approval of the picks, as every edit does. |
| `picks.tighten` | picks | `POST /api/projects/{pid}/picks/tighten` |  | yes | picks | model: about 5 minutes | Listed only while the main painting has non-tight regions (`tight` not true). Runs a second-look session on 1,024-px gridded full-resolution cut-outs of those regions (confirmed on clean 6-per-sheet check images) and updates ONLY the main painting's regions in one undoable batch; never changes any beat's chosen pictures. Optional body field `regions` (a list of region names, or null for all non-tight regions) limits which regions are measured. Needs the picks step open, a usable agent and no agent job running; writing drops the approval of the picks, as every edit does. Never advances (`advances` is false: manual action, not part of automatic running). |
| `picks.edit` | picks | `POST /api/projects/{pid}/picks/edit` |  | yes | picks | model: about 30 seconds | Once the picks step is open. Ready unless the agent cannot run, another long job of the project runs (a prompt-box turn, a draft or the agent's choice of pictures: one at a time) or an automatic run goes on. The caller supplies the instruction and the scope (`fill`): {"beats": [ids]}, {"chapter": id} or {"all": true}. One call, typed picks operations (never an import), one batch in the change log; a request that needs a new picture ends as `escalate`, and then POST .../picks/auto with those lines does the work. |
| `picks.ops` | picks | `POST /api/projects/{pid}/picks/ops` |  |  |  |  | Once the picks step is open. `body` is a dry run (it writes nothing) of the registry's first example operation; send your own operations with `fill`. See docs/OPS.md. |
| `picks.approve` | picks | `POST /api/projects/{pid}/picks/approve` | yes |  |  |  | While the picks are not approved. Needs the approved narration, picks with a main painting and no errors. Advances. |
| `picks.cancel` | picks | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While a picks job (suggestions, a clip or the agent's choice of pictures) of the project runs. |
| `draft.start` | edit | `POST /api/projects/{pid}/draft/start` |  | yes | draft | model: about 20 minutes | Once step 5 is open. Needs the voice and the approved picks, no draft job running, the pictures agent not working (one agent run at a time) and a usable agent. Advances while there is no draft (or it is out of date) and no storyboard. Optional body field `note` (text, at most 600 characters, `--set note=...`): the owner's wish for this draft (for example "fewer close-ups"), put into the agent's task file; leave it out when the owner gave none. |
| `proposal.apply` | edit | `POST /api/projects/{pid}/proposals/{prop_id}/apply` |  |  |  |  | While the project has no storyboard and a draft proposal exists. Advances when the draft is up to date. |
| `storyboard.restore` | edit | `POST /api/projects/{pid}/storyboard/restore` |  |  |  |  | Only when storyboard.json is unreadable. Ready when history/ has a good copy. It is the repair: listed first. |
| `storyboard.validate` | edit | `GET /api/projects/{pid}` |  |  |  |  | While the storyboard is readable. Always ready; the answer's `issues` are the validation of the saved storyboard. |
| `storyboard.retime` | edit | `POST /api/projects/{pid}/storyboard/retime` |  |  |  |  | While the storyboard is readable, the voice is done and the storyboard does not fit it (a card, the channel-name beat or the end of the video sits where an earlier voice put it; the opening shot is missing or no longer needed): listed only then. No model and no cost. Moves them to where the voice puts them, puts the opening shot in or takes it out, and applies the identity style again with the project's title (`title.json`) on the channel-name beat; no shot of the model or the owner is changed except the start of the shot after the opening shot. One batch in the change log (undoable: `bti undo` gives back the whole document the batch changed, the shots, the end of the video and the identity). Advances when something can be moved; approving the storyboard and the export are refused (`storyboard_off_voice`) until it is done. |
| `storyboard.approve` | edit | `POST /api/projects/{pid}/approve` | yes |  |  |  | While the storyboard is not approved (or was edited after). The route refuses while validation errors remain: call storyboard.validate first, and while the storyboard does not fit the voice (`storyboard_off_voice`: call storyboard.retime). Advances. |
| `storyboard.preview` | edit | `POST /api/projects/{pid}/preview` |  | yes |  |  | While the storyboard is readable. Ready; renders a short clip (a job of a few seconds). |
| `storyboard.put` | edit | `PUT /api/projects/{pid}/storyboard` |  |  |  |  | While the storyboard is readable. The caller supplies the document (`fill`); base_rev is the current rev. |
| `storyboard.ops` | edit | `POST /api/projects/{pid}/storyboard/ops` |  |  |  |  | While the storyboard is readable. `body` is a dry run (it writes nothing) of the registry's first example operation; send your own operations with `fill`. See docs/OPS.md. |
| `changes.list` | edit | `GET /api/projects/{pid}/changes` |  |  |  |  | Once the change log holds a batch (of the picks or the storyboard). Always ready. `step` is the step of the newest batch's document. |
| `changes.undo` | edit | `POST /api/projects/{pid}/changes/{batch}/undo` |  |  |  |  | The newest batch that can be undone now: it still has its copies, nothing undid it, and nothing it changed was changed since. `step` is the step of its document. |
| `draft.edit` | edit | `POST /api/projects/{pid}/draft/edit` |  | yes | edit.fast | model: from about 30 seconds to about 20 minutes | While the storyboard is readable. Ready unless a draft job runs, the pictures agent is working (one agent run at a time), an automatic run goes on or the agent cannot run. The caller supplies the instruction and the scope (`fill`). |
| `identity.set` | edit | `PUT /api/projects/{pid}/identity` |  |  |  |  | While the storyboard is readable. The caller supplies the style (`fill`); GET .../identity lists them. Optional body field `video_title` (`--set video_title=...`): the video's title shown under the channel name, one line of at most 90 characters (an empty text takes it away); with a title the style may also be left out of a direct call to the route. Refused with `storyboard_off_voice` while the storyboard does not fit the voice (call storyboard.retime first; title.set stores a title in that case all the same). |
| `draft.cancel` | edit | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While a draft job of the project runs. |
| `export.start` | export | `POST /api/projects/{pid}/export/start` |  | yes |  | machine_time: about 25 minutes | Once the storyboard is approved. Ready unless an export runs, or the audio mix or timing is missing. Advances until a video is exported. Renders in ~60-second parts keyed by what each part shows; kept parts from the last export are reused, so a small edit costs only its changed parts. |
| `export.cancel` | export | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While an export job of the project runs. |
| `auto.run` | export | `POST /api/projects/{pid}/auto/run` |  | yes |  | machine_time: the sum of what it may start from where the project stands | Listed while automatic running is on for the project and no video is exported yet. Ready unless a job of the project runs (an automatic run included). Takes `until` (a step id) and `max_steps`; walks the project forward with the first allowed advancing action of this answer, until it is exported, or stops with a reason (see docs/AGENT_API.md, "Chạy tự động"). `cost` is the sum of what it may start: only the kinds the owner allowed. |
| `auto.cancel` | export | `POST /api/longjobs/{job_id}/cancel` |  |  |  |  | While an automatic run of the project goes on. |
| `output.build` | export | `POST /api/projects/{pid}/output/build` |  |  |  |  | Listed when the app has an output folder (`output/<artwork key>/`) and the project is not a reference project. Always ready: fills (or refills) the folder from the project as it stands (the video, the readable documents, the log, the index); the body `{"clean": true}` also removes the working folder's caches when the export stands. A project of the same painting as the folder's last project takes it over. |
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
| `picks_saved_files` | The saved files of the last run of the agent's choice of pictures (cache/picks_auto: plan, search, choice) are not in the project, so what the agent chose cannot be read again. | Call picks.auto for these lines (with redo true): it chooses again. |
| `storyboard` | The project has no storyboard yet. | Run draft.start, then proposal.apply. |
| `storyboard_readable` | storyboard.json cannot be read. | Call storyboard.restore. |
| `storyboard_approved` | The storyboard is not approved, or it was edited after it was approved. | Call storyboard.approve. |
| `history_copy` | There is no good copy of the storyboard in history/. | Make a new draft: draft.start. |
| `audio_mix` | The audio mix the storyboard names is missing. | Call voice.generate. |
| `timing` | timing.json is missing. | Call voice.generate. |
| `no_running_job` | A job of the same kind is already running for this project; for the agent's work (picks.auto, picks.edit, draft.start, draft.edit) any other agent job of the project counts: the agent's choice of pictures, a prompt-box turn or a draft run one at a time; the two prompt boxes (picks.edit, draft.edit) also wait while an automatic run goes on. | Wait for it (see `jobs`), or cancel it with the matching *.cancel action. |
| `agent_usable` | The agent that would run cannot run on this machine (see `agent.reason`). | Choose another agent: PUT /api/projects/{pid}/agent, GET /api/agents lists them. |
| `suggest_enabled` | Picture suggestions are switched off on this machine. | Use picks.search instead. |
| `locked_beats` | Some beats of the narration are locked and would be replaced. | Unlock them, or send {"force": true} (the body shown does). |
| `draft_proposal` | There is no draft proposal to apply. | Call draft.start and wait for its job. |
| `storyboard_fits_voice` | The storyboard does not fit the voice: the cards, the channel-name beat or the end of the video sit where an earlier voice put them. | Call storyboard.retime (it moves them, and puts the opening shot in or takes it out), then ask for the state again. |
| `title_done` | The video's title is not written yet (or the narration changed after it was written), and an agent can write it. | Call title.generate and wait for its job, or set a title yourself with title.set. |
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
422 {"code": "invalid_field", "detail": "width must be an integer", "fields": [{"path": "width", "problem": "width must be an integer"}],
     "fix": "Correct the fields listed in `fields` and send the call again.", "retry": "after_fix"}
```

| key | meaning |
|---|---|
| `code` | stable snake_case word, one vocabulary for the whole API including the operations (`invalid_field`, `invalid_request`, `stale_revision`, `storyboard_not_found`, ...). An error that has no specific code gets one from its status (`not_found`, `invalid_field`, `conflict`, `internal_error`, ...) |
| `detail` | the sentence for a person, as before (a list for a request the framework refused) |
| `fix` | one English imperative sentence an agent can act on; it names the call to make when there is one. `{pid}` is the project's id when the call is a project route |
| `retry` | `no`: the same call can never work (what it names does not exist, the machine cannot do it); `after_fix`: change the request or the project as `fix` says, then call; `later`: the same call may work in a moment (something is busy, a service is not answering) |
| `fields` | the request fields that are wrong, when there are some (a 422): `[{path, problem, allowed?}]`, the form the operations use (`path` is `width`, or `ops[1].params.region` inside a batch). A raise that names one field gets it here; a request the framework refuses (`code: invalid_request`) lists every field |
| `current_rev` | on a stale revision (`stale`, `stale_revision`): the revision to start again from. `rev` (as before) carries the same value where it was already there |

Other keys an error already carried stay (`issues`, `rev`, `locked`, `job_id`, `allowed`, `restore_from`, `data_error`, ...). An error that
carries its own `fix` keeps it. Not JSON, and so not covered: a file download that cannot be satisfied (`416 Range Not Satisfiable` has no body)
and the files and images the API serves.

## 5. The table of codes

Includes the codes of failed jobs (`error_code` of a long-job record), which a caller reads from the job, not from an HTTP error. The codes of the
operations (`bti/ops/errors.py`) are in this table with the very same sentence the operations send: the hint table reads their table, so the two cannot
drift (a test checks it). Where the operations and the rest of the API named one situation twice, one name was kept: `storyboard_not_found` (the
operations' `document_missing` is gone), `invalid_field` and `invalid_request` (the other side's `field_invalid`, `field_required`, `request_invalid`,
`body_invalid`, `base_rev_required` are gone), the key `fields` (the other side's `field` is gone). `stale` (picks, agent, proposals: the page's own
word) and `stale_revision` (storyboard, operations) both stay, with one sentence and the same `current_rev`.

<!-- BEGIN GENERATED: codes -->
| code | retry | fix |
|---|---|---|
| `accept_all_required` | after_fix | This project has no storyboard yet: call apply again with {"accept": "all"}. |
| `accept_invalid` | after_fix | Send accept as "all" or as a list of change ids. |
| `agent_job_running` | later | Another agent job of this project is running (the agent's choice of pictures, a prompt-box turn or a draft): wait for it (GET /api/projects/{pid}/longjobs) or cancel it, then call again. |
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
| `approval_stale` | after_fix | The storyboard changed after it was approved: approve it again (POST /api/projects/{pid}/approve), then export (unchanged ~60 s parts are reused; a small edit only re-renders its changed parts). |
| `artwork_not_found` | no | Use an artwork key listed by GET /api/library/artworks. |
| `asset_not_found` | no | Use an asset key that exists in the storyboard (GET /api/projects/{pid}/assets lists them). |
| `at_least_one_source` | after_fix | Keep at least one book source included in the brief options. |
| `audio_decode_failed` | after_fix | The audio file cannot be decoded: make the voice again (POST /api/projects/{pid}/voice/generate); if it repeats the file is damaged. |
| `auto_needs_human` | no | Ask the owner to change automatic running on the page: an agent may only read it (GET /api/projects/{pid}/auto). |
| `auto_not_enabled` | after_fix | Ask the owner to turn automatic running on for this project (the switch on the page, PUT /api/projects/{pid}/auto), then call again. |
| `auto_run_not_found` | no | Take a run id from GET /api/projects/{pid}/auto/runs. |
| `auto_running` | later | An automatic run of this project is going: follow it (GET /api/longjobs/{job_id}) or stop it (POST /api/longjobs/{job_id}/cancel), then call again. |
| `bad_action` | after_fix | Send action as "overwrite" or "discard". |
| `bad_chapters` | after_fix | Send `chapters` as a list of chapter ids (at most 100). |
| `bad_lead` | after_fix | Send `lead` as a number of seconds from 0.2 to 15 (or null to use the standard one). |
| `bad_model` | after_fix | Send `model` as a plain model id, or leave it out to use the project's agent. |
| `bad_pad` | after_fix | Send `pad` as true or false. |
| `bad_pronounce` | after_fix | Send `pronounce` as an object of written form -> spoken form (at most 500 entries). |
| `bad_provider` | after_fix | Send provider as "agy" or "auto". |
| `bad_request` | after_fix | Read `detail`, correct the request and send it again. |
| `bad_scope` | after_fix | Send scope as "all", "changed" or a list of chunk ids (and reseed as a list of chunk ids). |
| `bad_tempo` | after_fix | Send `tempo` as a number inside the range in `detail`. |
| `bad_text_character` | after_fix | Remove lone surrogate characters from the text you send, then send it again. |
| `bad_title` | after_fix | Send `title` as a number of seconds from 3 to 30 (or null to use the standard one). |
| `batch_not_found` | no | Take a batch id from the list at GET /api/projects/{pid}/changes. |
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
| `claude_outdated` | after_fix | Run `claude update` on the server (the owner does this once), then call again. |
| `claude_rate_limit` | later | The Claude Code quota is used up: call again after `retry_after_seconds`, or choose the other agent. |
| `claude_timeout` | later | The agent ran past its time limit and was stopped: call again, or work on fewer chapters. |
| `compile_empty` | later | No shot could be built from the agent's result: run the draft again. |
| `compile_error` | after_fix | The edit could not be assembled (parameter or syntax errors): send a simpler instruction or a narrower scope. |
| `confirm_required` | after_fix | This call is paid: send confirm_paid: true only when the owner agreed to the cost. |
| `conflict` | after_fix | Read `detail`: the project is in a state that refuses this call. GET /api/projects/{pid}/state shows what to do first. |
| `data_unusable` | after_fix | A data file of the project is missing or damaged: read `detail` for its name and repair it. |
| `delete_not_confirmed` | after_fix | Call DELETE /api/projects/{pid}?confirm={pid}: `confirm` must be the exact project id. |
| `document_corrupt` | after_fix | Restore a good copy of the file `detail` names (the storyboard has POST /api/projects/{pid}/storyboard/restore), then call again. |
| `document_invalid` | after_fix | The document has the wrong shape (see `detail`): send a document as GET returns it. |
| `dossier_not_found` | no | This artwork has no dossier yet: rebuild the library (python -m bti.library build). |
| `draft_no_output` | later | The agent wrote no result file: run the draft again (POST /api/projects/{pid}/draft/start). |
| `draft_not_ready` | after_fix | Make the voice (timing.json) and approve the picks first: GET /api/projects/{pid}/state shows which is missing. |
| `draft_note_invalid` | after_fix | Send `note` as text (the owner's wish for this draft), or leave it out. |
| `draft_note_too_long` | after_fix | Send `note` of at most 600 characters (the owner's wish for this draft), or leave it out. |
| `draft_tampered` | after_fix | The agent changed files outside its workspace and its result was dropped: check the project, then run the draft again. |
| `duplicate_ref` | after_fix | Give every ref in a batch a different name. |
| `edit_bad_scope` | after_fix | Send scope as exactly one of {"shots": [ids]} (step 5), {"beats": [ids]} (step 4), {"chapter": id} or {"all": true}, an instruction of 1 to 2000 characters and, for step 5, mode auto, fast or deep. |
| `edit_degraded` | after_fix | The edit was refused because a shot would be degraded or incomplete: narrow the instruction. |
| `edit_empty_instruction` | after_fix | Send `instruction` as a non-empty text. |
| `edit_failed` | later | The edit failed unexpectedly and nothing changed: call again. |
| `edit_needs_agy` | after_fix | Editing by instruction needs an agent (agy or Claude Code), not provider auto: choose an agent. |
| `edit_no_change` | after_fix | The agent changed nothing: restate the instruction more concretely. |
| `edit_no_storyboard` | after_fix | Editing needs an existing storyboard: apply the first draft proposal first. |
| `edit_outside_scope` | after_fix | The agent changed something outside the scope or a locked shot: narrow the instruction to the scope and call again. |
| `edit_running` | later | An edit is running: cancel it (POST /api/longjobs/{job_id}/cancel) or wait, then delete the thread. |
| `escalate` | after_fix | This request needs a closer look at the picture, more than the chosen scope or a picture the project does not have: on step 5 call again with mode deep, on step 4 search for the picture by hand. |
| `export_file_not_found` | no | Use a file name listed by GET /api/projects/{pid}/export (`files`). |
| `file_too_large` | after_fix | Send a file of a supported kind (jpg, jpeg, png, webp, mp4, webm, mov or m4v) of at most 80 MB. |
| `forbidden` | no | This call is not allowed on this project; read `detail` for the rule. |
| `frames_mismatch` | after_fix | The video has the wrong number of frames: call POST /api/projects/{pid}/export/start again; if it repeats, validate the storyboard. |
| `gate_needs_human` | after_fix | Ask the owner to approve this gate on the page, or to turn automatic running on for this project and allow the gate (the switch on the page, PUT /api/projects/{pid}/auto), then call again. |
| `history_file_not_found` | after_fix | Name a file that exists in the project's history/ folder, or leave `file` out to use the newest good one. |
| `history_file_unreadable` | after_fix | The named history file is not a storyboard: name another file, or leave `file` out. |
| `identity_style_required` | after_fix | Send `style` as an identity style id (GET /api/projects/{pid}/identity lists them). |
| `identity_style_unknown` | after_fix | Use one of the ids in `allowed` as `style`. |
| `image_empty` | after_fix | The image file is empty: send another file. |
| `image_extract_failed` | no | This image cannot be extracted from the book: skip it. |
| `image_not_in_work` | no | Ask for an image listed by GET /api/library/works/{book}/{n}. |
| `image_too_small` | after_fix | Choose a larger picture: its short side is below the smallest size the app stores. |
| `image_truncated` | after_fix | The image is cut off: send a complete file. |
| `image_unreadable` | after_fix | The image cannot be read: send a jpg, png or webp that opens. |
| `import_failed` | no | Check source and source_id, or choose another picture; nothing was written. |
| `internal_error` | no | This is a bug of the server, not of your input: do not repeat the call; report `detail`. |
| `interrupted` | later | The server restarted while the job ran: start the same job again; finished parts are kept. |
| `invalid` | after_fix | Correct the request as `detail` says and send it again. |
| `invalid_field` | after_fix | Correct the fields listed in `fields` and send the call again. |
| `invalid_model` | after_fix | Send each role's model as a non-empty model id string. |
| `invalid_payload` | after_fix | Send the body in the shape of the route: read `detail`, correct it and send again. |
| `invalid_project_path` | no | Use a project id that names a folder directly under the projects folder. |
| `invalid_request` | after_fix | Send a JSON body in the shape this route takes (the operation routes take base_rev, actor and 1 to 200 operations) and correct the fields listed. |
| `job_not_found` | no | Use the job id the start call answered with; after a server restart only finished jobs are still known. |
| `join_failed` | later | The parts could not be joined: call POST /api/projects/{pid}/export/start again. |
| `library_data_corrupt` | after_fix | A file of the book library is damaged: repair it or rebuild the library (python -m bti.library build), then call again. |
| `library_file_unreadable` | after_fix | A file of the library cannot be read (see `detail`): repair it, then call again. |
| `licence_rejected` | after_fix | The licence of this picture is not accepted: choose another picture. |
| `locked` | after_fix | Send unlock for that shot or overlay first, or leave it out of the batch. |
| `locked_beats` | after_fix | Unlock the beats named in `locked`, or send {"force": true} to replace them. |
| `longjob_bad_kind` | after_fix | Use a job kind such as voice, draft, export or picks in `kind`, or leave it out. |
| `longjob_missing` | no | The long-job runner is not installed on this server: the job cannot be started. |
| `longjob_not_found` | no | Use the job id the start call answered with (GET /api/projects/{pid}/longjobs lists the jobs of a project). |
| `longjob_running` | later | Cancel the long job (POST /api/longjobs/{job_id}/cancel) or wait until it is finished, then call again. |
| `main_asset_unreadable` | after_fix | The main painting has no readable file: import it again (POST /api/projects/{pid}/picks/import with as_main). |
| `map_place_unknown` | after_fix | Search for the place again (POST /api/projects/{pid}/picks/search with source osm) and import the result it gives. |
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
| `not_consecutive` | after_fix | Give shots that follow each other in the storyboard, in their order. |
| `not_found` | after_fix | Use an id that exists: for a picture of the project's books take a source_id from GET /api/projects/{pid}/picks/book-images, for anything else list what exists with the matching GET route. |
| `not_needs_choice` | no | This turn is not waiting for a choice: GET /api/projects/{pid}/draft/thread shows its status. |
| `nothing_to_restore` | no | Leave the storyboard as it is: storyboard.json is readable, there is nothing to restore. |
| `nothing_to_say` | after_fix | The narration has no sentence to speak: write it (POST /api/projects/{pid}/narration/generate). |
| `op_invalid` | after_fix | Correct the operation named in `detail` (GET the narration for the current beat and chapter ids), then send the ops again. |
| `options_error` | after_fix | Correct the option named in `detail` and send the options again. |
| `out_of_scope` | after_fix | Remove the operation from the batch, or send the batch with a wider scope. |
| `outline_has_errors` | after_fix | Fix the errors listed in `issues` (PUT /api/projects/{pid}/outline), then approve again. |
| `outline_missing` | after_fix | Make the outline first: POST /api/projects/{pid}/outline/generate, then approve it. |
| `outline_not_approved` | after_fix | Approve the outline: POST /api/projects/{pid}/outline/approve with {"rev": <outline rev>}. |
| `outline_stale` | after_fix | The outline changed after it was approved: approve it again (POST /api/projects/{pid}/outline/approve). |
| `outline_unreadable` | after_fix | The pasted outline could not be read (see `issues`): correct the text and import it again; nothing was overwritten. |
| `output_disabled` | no | This app was started without an output folder: ask the owner to set BTI_OUTPUT_ROOT or to start the app the usual way, then call again. |
| `output_failed` | later | The output folder could not be written (see `detail`): check that the disk has room and the folder is not open elsewhere, then call POST /api/projects/{pid}/output/build again. |
| `output_not_applicable` | no | A reference or imported project has no output folder: use a project made from the library. |
| `page_not_found` | no | Ask for a page that exists in the book. |
| `page_not_in_work` | no | Ask for a page inside the page range of this work. |
| `part_missing` | later | A rendered part is missing: call POST /api/projects/{pid}/export/start again; unchanged ~60 s parts are kept. |
| `picks_approved` | after_fix | The picks are approved: send redo true to let the agent choose again (the approval is dropped and the picks must be approved again). |
| `picks_auto_limit` | later | The agent used up the limits of one session (time and steps): call POST /api/projects/{pid}/picks/auto again; the parts that finished are kept. |
| `picks_auto_no_output` | later | The agent wrote no usable file even after one repair message: call POST /api/projects/{pid}/picks/auto again, or choose the other agent. |
| `picks_auto_stale` | after_fix | The narration or the main painting changed while the agent worked: call POST /api/projects/{pid}/picks/auto again. |
| `picks_auto_tampered` | after_fix | The agent changed files outside its work folder and its result was dropped: check the project, then call POST /api/projects/{pid}/picks/auto again. |
| `picks_corrupt` | after_fix | Save the picks again (PUT /api/projects/{pid}/picks) or repair picks.json: it cannot be read. |
| `picks_error` | after_fix | Read `detail`, correct the request or the picks, then call again. |
| `picks_have_errors` | after_fix | Fix the errors listed in `issues` (the main painting, missing files, unknown assets or regions), then approve again. |
| `picks_missing` | after_fix | Choose the pictures first (see GET /api/projects/{pid}/picks): picks.json is missing. |
| `picks_no_main` | after_fix | Choose the main painting (POST /api/projects/{pid}/picks/import with as_main), then approve the picks. |
| `picks_nothing_to_do` | no | Every line already has pictures: send redo true to choose them again, or name the lines in `beats`. |
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
| `project_not_found` | no | Take the project id from GET /api/projects. |
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
| `retry_no_files` | after_fix | The saved files of the last run (cache/picks_auto: plan, search, choice) are not in the project: call POST /api/projects/{pid}/picks/auto with these lines and redo true; it chooses again. |
| `retry_nothing_to_do` | no | No line of the picks says that a chosen picture could not be downloaded (`missing` with the code import_limited): there is nothing to retry. |
| `route_not_found` | no | There is no such route: check the path and the method against docs/AGENT_API.md or GET /openapi.json. |
| `save_refused` | after_fix | The engine refused the document: read `issues`, fix the values they name, then send it again. |
| `scope_needs_storyboard` | after_fix | This needs an existing storyboard: apply the first draft proposal first (POST /api/projects/{pid}/proposals/{id}/apply). |
| `script_job_running` | later | Cancel the model job (POST /api/jobs/{job_id}/cancel) or wait until it is finished, then call again. |
| `shot_not_found` | no | Use a shot id that exists in the storyboard (GET /api/projects/{pid}). |
| `shot_too_short` | after_fix | Choose a time that leaves every piece at least 0.2 seconds long. |
| `slot_kind_mismatch` | after_fix | Use an asset of the kind the slot takes (allowed lists the kinds). |
| `source_error` | after_fix | Choose another picture or another source, or try again in a minute; nothing was written. |
| `source_not_found` | no | Use a source name listed in the artwork's dossier. |
| `source_rate_limited` | later | Wait `retry_after` seconds (a minute when it is null), then send the call again; nothing was written. |
| `source_text_missing` | after_fix | The source text file is missing: rebuild the library (python -m bti.library build). |
| `source_timeout` | later | The service did not answer in time; call again in a minute. |
| `source_unavailable` | later | The service this call needs is not answering; call again in a minute. |
| `source_unreachable` | later | Send the call again in a minute; nothing was written. |
| `span_mismatch` | after_fix | Make the first new shot start where the replaced run starts and keep every other start inside the run. |
| `spec_invalid` | later | The model answered in the wrong shape, or with operations the server refused, even after one repair: call again with the request said more plainly. |
| `spend_needs_human` | no | Ask the owner to start this paid call on the page: an agent never spends money, whatever the settings of automatic running. |
| `split_refused` | after_fix | Read `detail`: choose a work that can be split off. |
| `stale` | after_fix | Read the document again, apply your change to the revision in `current_rev`, then send the call again with base_rev set to it. |
| `stale_revision` | after_fix | Read the document again, apply your change to the revision in `current_rev`, then send the call again with base_rev set to it. |
| `storyboard_corrupt` | after_fix | Call POST /api/projects/{pid}/storyboard/restore (no body) to bring back the newest good copy from history/, then call again. |
| `storyboard_has_errors` | after_fix | Fix every issue with level `error` in `issues` (GET /api/projects/{pid} lists them), then call again. |
| `storyboard_incomplete` | after_fix | Fill in the items named in the answer (their technique needs a picture, a clip or a mask), then approve again. |
| `storyboard_missing` | after_fix | This project has no storyboard yet: run the draft first (POST /api/projects/{pid}/draft/start). |
| `storyboard_not_found` | after_fix | Make the storyboard first: run the draft (POST /api/projects/{pid}/draft/start) and apply its proposal, then call again. |
| `storyboard_off_voice` | after_fix | The cards, the channel-name beat or the end of the video sit where an earlier voice put them (`problems` lists them): call the action storyboard.retime (POST /api/projects/{pid}/storyboard/retime with {"base_rev": <storyboard rev>}), then call this again. |
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
| `technique_not_offered` | after_fix | Use the technique that `use` names instead (`allowed` lists the ones you are offered, `inputs/techniques.md` of a draft says when to use each). A batch of a person (the page, the actor `human`) may use any technique. |
| `technique_unavailable` | after_fix | Use a technique the engine can draw (engine.available is true in the registry). |
| `template_missing` | no | The draft task template is missing from this installation: restore skills/storyboard_draft/TASK.template.md. |
| `thumbnail_failed` | no | No thumbnail can be made of this file: use the file itself. |
| `tighten_nothing_to_do` | no | Every region on the main painting is already tight (or there are no regions to tighten). |
| `timing_corrupt` | after_fix | Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json cannot be read. |
| `timing_missing` | after_fix | Make the voice first (POST /api/projects/{pid}/voice/generate): timing.json is missing. |
| `timing_shape` | after_fix | Make the voice again (POST /api/projects/{pid}/voice/generate): timing.json has the wrong shape (see `detail`). |
| `timing_unusable` | after_fix | Make the voice again with POST /api/projects/{pid}/voice/generate: timing.json is missing or damaged. |
| `title_choice_needed` | after_fix | Send exactly one of `text` (a title) and `option` (the number of a candidate). |
| `title_invalid` | after_fix | Send `text` as the title: text that is not empty (or `option`: the number, from 1, of a candidate of GET /api/projects/{pid}/title). |
| `title_limit` | later | The agent used up the limits of one run without a usable title: call POST /api/projects/{pid}/title/generate again. |
| `title_no_output` | later | The agent wrote no usable title file even after one repair message: call POST /api/projects/{pid}/title/generate again, or choose the other agent. |
| `title_not_one_line` | after_fix | Send `text` as one line: no line breaks. |
| `title_note_invalid` | after_fix | Send `note` as text, or leave it out. |
| `title_note_too_long` | after_fix | Shorten `note` to at most 600 characters, or leave it out. |
| `title_option_unknown` | after_fix | Send `option` as the number, from 1, of a candidate listed by GET /api/projects/{pid}/title, or send `text` instead. |
| `title_tampered` | after_fix | The agent changed files outside its work folder and its answer was thrown away: check the project, then call POST /api/projects/{pid}/title/generate again. |
| `title_too_long` | after_fix | Shorten `text` to at most 60 characters (GET /api/projects/{pid}/title `limits.person_max_chars`). |
| `too_deep` | after_fix | Flatten the JSON body to at most 40 levels of nesting. |
| `too_large` | after_fix | Send a smaller JSON body (at most 8 MB). |
| `too_many` | after_fix | Send fewer beat ids in `beats` (the limit is in `detail`). |
| `tool_missing` | no | A tool the clip needs (yt-dlp or ffmpeg) is not installed on this machine. |
| `turn_data_lost` | after_fix | The stored storyboards of this turn are gone: send the instruction again as a new edit. |
| `turn_frame_not_found` | no | Use `when` before or after, and a turn and shot that exist (GET /api/projects/{pid}/draft/thread). |
| `turn_not_applied` | no | Only an applied turn can be undone: GET /api/projects/{pid}/draft/thread shows its status. |
| `turn_not_escalated` | after_fix | That turn did not end as `escalate` (or an agent run of it that failed): only such a turn can be handed to the pictures agent; send POST /api/projects/{pid}/picks/auto with the lines instead. |
| `turn_not_found` | no | Use a turn id listed by GET /api/projects/{pid}/draft/thread. |
| `undo_conflict` | after_fix | Undo the later batches first (newest first), or leave the things named in conflicts as they are. |
| `undo_unavailable` | no | Make the change again with new operations: the copies of this batch were removed when the log was pruned. |
| `undrawable` | after_fix | Change the shots named in `issues` so the engine can draw them, then approve again. |
| `unknown_agent` | after_fix | Use one of the agent ids in `allowed` (GET /api/agents lists them). |
| `unknown_asset` | after_fix | Use an asset key from `allowed` (GET /api/projects/{pid}/picks lists the assets too), or import the picture first (an import operation and its $ref, or POST /api/projects/{pid}/picks/import). |
| `unknown_beat` | after_fix | Use a beat id of the approved narration (allowed lists them when there are few). |
| `unknown_change_ids` | after_fix | Use change ids listed by GET /api/projects/{pid}/proposals/{id}, or send accept: "all". |
| `unknown_chapter` | after_fix | Use chapter ids that exist in the outline (GET /api/projects/{pid}/outline). |
| `unknown_model` | after_fix | Use a model id listed by GET /api/models (or GET /api/settings/models). |
| `unknown_op` | after_fix | Use one of the operation names listed in allowed. |
| `unknown_overlay` | after_fix | Use an overlay id of that shot from allowed, or a $ref made by an earlier operation. |
| `unknown_param` | after_fix | Use one of the allowed parameter names of this technique. |
| `unknown_ref` | after_fix | Define the ref on an earlier operation of the batch (import, split_shot, add_overlay) before you use it. |
| `unknown_region` | after_fix | Use one of the allowed region names, or add the region first with set_region. |
| `unknown_role` | after_fix | Use only role names listed by GET /api/settings/models. |
| `unknown_shot` | after_fix | Use a shot id from allowed, or a $ref made by an earlier operation of the batch. |
| `unknown_slot` | after_fix | Use one of the allowed slot names of this technique. |
| `unknown_source` | after_fix | Use one of the picture sources commons, met, pexels, pixabay or osm (an import operation also takes book). |
| `unknown_step` | after_fix | Use a step id that GET /api/projects/{pid}/agent lists under `effective`. |
| `unknown_technique` | after_fix | Use a technique id that exists (`allowed` lists them when there are few; GET /api/styles/{style} lists all of them). |
| `unsupported_file_type` | after_fix | Send a file of a supported kind (jpg, jpeg, png, webp, mp4, webm, mov or m4v) of at most 80 MB. |
| `unsupported_media` | after_fix | Send a file this route can read, or leave the file out. |
| `validation_failed` | after_fix | Correct every issue with level error in `issues` (the operations named by `op_index`, when there is one), then send again; nothing was written. |
| `video_bad_range` | after_fix | Send `start` and `end` as numbers of seconds with a clip length inside the allowed range. |
| `video_bad_url` | after_fix | Send a YouTube link (youtube.com or youtu.be) in `url`. |
| `video_fetch_failed` | later | The video could not be fetched: call again in a minute, or use another link. |
| `video_not_main` | after_fix | Choose an image, not a video, as the main picture. |
| `video_timeout` | later | The video download took too long: call again, or choose a shorter range. |
| `video_title_invalid` | after_fix | Send `video_title` as text: one line of at most 90 characters ("" takes the title away). |
| `video_title_too_long` | after_fix | Shorten `video_title` to one line of at most 90 characters. |
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
| `wrong_technique_kind` | after_fix | Use a technique of the kind that fits: base or card for a shot, overlay for an overlay. |
| `youcom_key_missing` | no | The You.com key is not set on this machine: use the free sources, or paste a YouTube link. |
<!-- END GENERATED: codes -->

## 6. The operations routes

Small named operations for the picks and the storyboard, sent in batches (all or nothing, a dry run, a change log, undo per batch). Everything about
them is in **`docs/OPS.md`** (generated from the registry in `bti/ops/`): the five routes, the batch request, every operation with its schema and
example, the change log, undo and the table of their error codes. The state answer lists them as `picks.ops`, `storyboard.ops`, `changes.list` and
`changes.undo` (section 2). Their refusals have the same error body as every other (section 4): `code`, `detail`, `fix`, `retry`, and `fields` with the
`path` of every wrong field (`ops[1].params.region`), `op_index`, `current_rev`, `issues` or `conflicts` where they apply. A request refused by the size
or depth limit before it reaches a route (`too_large`, `too_deep`) has them too.

## 7. The agent that chooses the pictures (`picks.auto`)

`POST /api/projects/{pid}/picks/auto` starts one long job (kind `picks`, follow it at `GET /api/longjobs/{job_id}`, cancel it with `POST /api/longjobs/{job_id}/cancel`) that
fills step 4 by itself. Body, all optional: `{"beats": [ids] | null, "redo": false, "base_rev": "<rev of GET .../picks>", "model": "<model id, tests only>"}`. It works on the
lines that have no pictures (a line that already has pictures, or that is skipped, is left alone) unless `redo` is true; named `beats` limit it to those lines. Answer:
`{"job_id", "model", "agent", "lines"}`.

Four parts, each a part of the job (`parts[].key`): `plan` (the agent says what each line does, `kinds`, plans what each line needs and proposes boxes on the main painting), `search` (code: the free picture
sources, never the paid suggestion service), `choose` (the agent looks at the candidates and at each box) and `write` (code: the typed operations, in batches whose actor is
`agent:<model id>` and whose note says what the batch is, so that `GET .../changes` lists them and `POST .../changes/{batch}/undo` takes them back). The job never approves.
Starting it again resumes a run that did not finish. Refusals (all with `code`, `fix`, `retry`): `narration_not_approved`, `picks_no_main`, `main_asset_unreadable`, `picks_approved`
(approved picks need `redo`: the approval is dropped when the agent changes anything), `picks_nothing_to_do` (every line already has pictures), `not_found` (a line that is not in
the narration), `stale` (`base_rev`), `busy` (a picks job runs), `agy_missing`, `claude_missing`, `claude_auth`. A failed job carries `error_code`: `picks_auto_no_output`,
`picks_auto_limit`, `picks_auto_tampered`, `picks_auto_stale`, or the runner's own (`agy_rate_limit` and `claude_rate_limit` say when the quota opens again in `meta.retry_at`).

`GET /api/projects/{pid}/picks/auto` answers `{"running": job | null, "last": {"finished", "job_id", "result", "model", "agent"} | null, "reasons": {beat: reason}, "agent", "limits"}`.
The job's `result` (also `last.result`): `lines_total`, `lines_done`, `lines_with_pictures`, `lines_kept` (lines that need nothing new), `lines_without` (`[{beat, no, code, why}]`: lines
nothing was found for and that have no fallback, left as they were: only a line of a plan saved before `kinds` existed), `missing` (every wanted picture that was not found, with `why`), `outside_without`
(the lines about something outside the painting that were written with the painting only), `pictures_imported`, `regions_made`, `regions_dropped`, `clips`, `batches`,
`lines_by_others` (lines the owner filled meanwhile), `stopped` (`"time"` when the write part ran out of time), `sentence` (`Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp.`),
`limits` (the plan session 30 minutes and 120 steps, the choosing session 40 minutes and 220 steps). Each line the agent wrote carries its reason as the line's note (`beats.<id>.note`); `reasons` lists them. The same function is `bti.picks.auto.escalate(pid, pdir, beat_ids, note=...)`.

**What each line does, and what is lost when a picture is not found.** The plan (`cache/picks_auto/plan.json`, `bti.picks.plan/1`; `bti.picks.auto.shapes`, the check `./check` runs in the agent's folder) gives every line `kinds`:
one or two of `detail`, `whole`, `outside`, `compare`, `journey`, `dates`, `figure`, `inscription`, `construction`, `relations`, `idea`, in the order the line speaks, and the check refuses a line whose pictures
are not the ones its kinds need (an `outside` line asks for a picture of the thing itself, a `context` or a `clip` item, and names a line-level `fallback`, a `whole` or `detail` item; a map belongs only to a
`journey` and names two or more `places`; a `compare` asks for a `context` of kind `work` and a part of this painting; the full table is in `skills/picks_auto/PLAN.template.md`). A `context` item has `entity` (the
encyclopedia name) and `period` (`then`, the default, or `now`) and its `kind` may be `object` or `event`; the plan may ask for 60 pictures from elsewhere (`MAX_WANTS`). When a picture asked for is not found (no
candidates, or the choosing session answered null) the line is written with its `fallback` and says what is missing; it is never left unwritten. The picks document stores per beat `kinds` (a list; absent in a document
made before) and `missing` (`[{what, code}]`, at most 10; absent when nothing is missing); the operations `set_picks` and `skip_beat` accept both (an edit of the pictures keeps them unless it sends new ones; `[]` takes
them away; an undo gives them back); `PUT .../picks` keeps them for a beat that does not send them. `GET .../picks` has the warning `outside_no_picture` for every beat whose kinds hold `outside` or `compare` and
whose pictures are all of the main painting (not for a beat the owner settled with `skip`; not for a document without `kinds`) and the summary `outside` (`{"lines": n, "with_picture": n, "without": [beat ids]}`, written out as the keys `lines`, `with_picture`, `without`; lines
settled with `skip` are not counted). The storyboard draft's `inputs/beats.json` carries `kinds` and `missing` for each beat.

**Three-step search for outside lines (`wider`).** A line of kind `outside` is searched in three steps before it falls back to the painting: (1) the exact thing itself; (2) the same kind of thing from the period (a miniature, print or painting of the 15th century showing a similar scene); (3) a real surviving object of that kind in a museum (`kind: "object"`). The plan names the two wider steps in `wider` (`[{"step": 2, "search", "kind", "what"}, {"step": 3, "search", "kind": "object", "what"}]`). Round two searches step 2 first, then step 3, through Wikipedia, the free sources, and the web if on, stopping at the first step with candidates; the candidates carry their `step` (2 or 3). An item chosen at step 2 or 3 carries `"step": 2` or `"step": 3` in `picks.json` and its beat's `missing` is empty; only when all three steps find nothing does the line fall back to the painting and record `missing`. The draft storyboard's beats document carries `step` for each pick item.

### The web search of the pictures agent (the owner's switch `auto_web_search`)

The `search` part asks **Wikipedia first** for every context picture (free, no key: the thing is looked up by its `entity`, else by its `search` words, and the pictures of the best three articles are offered as
Wikimedia Commons files), then the free sources as before, and never the paid suggestion. **One paid thing exists, and it is the owner's to allow:** the web search (You.com). The switch is `GET/PUT /api/settings/web-search`
(`{"auto_web_search": "on" | "off", "auto_web_search_max": 80, "source": "default" | "config" | "owner"}`; the code's default is off; `config/picks.json` sets a machine default and the owner's choice on the settings page,
`run/settings.json` block `picks`, wins). **A PUT whose `actor` is not `human` is 403 `spend_needs_human`: an agent never switches it on.** With it OFF nothing paid is ever called and the job has the four parts above. With it ON
the permission is the owner's standing one: `picks.auto` is started by an agent and by the automatic run exactly as without it, its cost line (`next_actions[].cost.about` of the state answer) says
`about 20 minutes, up to 80 web searches (You.com)`, and the job has **six parts**: `plan`, `search`, `choose`, `web`, `choose2`, `write`.

- `search`: a context picture that has fewer than three candidates after Wikipedia and the free sources gets ONE web search with its `search` words (round one).
- `web` (round two): after the first choosing session every wanted picture it answered null, and every one that had no candidate, gets a web search with its `search` and, when that gives nothing new, with its first
  alternative (a query a want already had is not asked again). `choose2`: ONE more choosing session that sees only the wants that got new candidates (their new candidates only, numbered from 1) and decides only those; the write
  part reads both choices as one. The web's candidates have the licence unknown (`flag` `unknown`); a page of Wikipedia, Wikimedia Commons or the Met found by the web is resolved by that source (known licence); pictures of
  stock agencies and print shops that carry watermarks are never offered (`config/picks.json`, `web_blocked_hosts`, is added to the built-in list).
- Every web search counts against `auto_web_search_max` for the run. A wanted picture that could not be searched because the count was used up has the code `web_budget` (in `lines_without`, `missing`, `search.json`); with the
  key missing or real requests off the web is left alone for the run and nothing is counted (`web.stopped`). The count is in `result.web` = `{"on", "max", "searches", "stopped"}`, in `cache/picks_auto/search.json` and `last.json`,
  and in the closing sentence (`Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp. Đã tìm trên web 12/80 lần.`). `GET .../picks/auto` also answers `web`: what the next run would use.
- The search is refused for any other caller: `POST .../picks/search` with `sources: ["web"]` finds nothing and costs nothing (the source `web` is searched only inside this job); `import` accepts a `web` candidate
  (`source_id` = the picture's address and, after a space, the page's), refusing an address that names a private or local machine (`unsafe_url`) or that is not a picture (`not_an_image`).

### Polite downloads, and finishing a run whose chosen pictures were refused (`picks.retry_missing`)

**Every download of a picture is polite and patient** (`bti.media.http.polite`, taken by `bti.media.api.import_candidate`: the write part of `picks.auto`, the operation `import`, `POST .../picks/import` and the older import of the storyboard page).
At most one request a second goes to a host (the Wikimedia hosts `commons.`, `upload.` and `en.wikipedia.org` count as one: the thumbnails of the search and the downloads share that clock), and when the host answers 429 (or 503 with `Retry-After`) the request is
sent again after the time the host asks, else after 10 s, then 30 s, then 90 s, three times in all, before the refusal is raised as `source_rate_limited`. A host that asks for more than 120 seconds is not waited for (the refusal carries its time at once);
a Commons original that is refused has its rendition to fall back on at once, without waiting. One download can therefore take up to about six minutes before it fails, so a command that sends an `import` should say `--timeout 300` (the default of `bti` is 60 seconds).
The write part of `picks.auto` stops asking a source once one of its pictures is still refused after those tries (the other pictures of that source are listed `import_limited` with the wait the host asked), keeps its limit of 25 minutes (the long-job
runner stops a part at 35) and has an estimate of 5 minutes. A search is not polite: it fails at once and says when to come back, as before.

**`POST /api/projects/{pid}/picks/retry-missing`** (`bti do <project> picks.retry_missing --wait`) finishes such a run. It is a long job of kind `picks` (`meta.action` `retry`) with no model, no cost and no search. Body, all optional:
`{"beats": [ids] | null, "actor": "human" | "agent:<id>" | "cli:<name>"}`; answer `{"job_id", "lines"}`. The action is listed only while a line of the picks says `import_limited` in its `missing` (a `web_budget` is not retried: it needs the paid search, so `picks.auto`);
it is ready when the saved files of the last run (`cache/picks_auto`: `plan.json`, `search.json`, `choice.json`, and `choice2.json` of the web round) are in the project (`picks_saved_files` in `needs` otherwise), and it advances once for the lines it has not looked at
since the last run of `picks.auto` (the automatic run takes it once, before the pictures gate; `cache/picks_auto/retry.json` remembers it). For each such line it reads the candidate the agent chose in the saved files (`pick` `["c", n]`, with `n` counting inside
`search.json`'s `round2.map[want]` for a pick of the second choice, `["b", n]` for a picture of the books: the same reading as the write part), imports it, and writes the line again the way the write part would have written it: the plan's pictures in the plan's order,
the agent's reason as the note of the new picture, `missing` without what it fixed, the line's note without "Chưa tìm được ...", one batch of the change log for the line (the actor the caller names; undoable). A line that was changed after the agent wrote it
is left alone (`line_changed`). Refusals: `retry_nothing_to_do` (409, no line says `import_limited`), `retry_no_files` (409), `invalid_field`, `agent_job_running`, `busy`. The job's `result`: `lines_total`, `lines_fixed` (beat ids), `lines_still_limited` (`[{beat, no, code, why}]`: the
source still refuses: call it again later), `lines_left` (`[{beat, no, code, why}]`: left as they were), `pictures_imported`, `batches`, `sentence` (`Đã tải lại hình cho 5/6 đoạn. 1 chỗ vẫn bị giới hạn lượt tải, thử lại sau.`). Writing drops the approval of the picks, as every edit does.

## 8. The prompt box of step 4 and the hand-over to the pictures agent (`picks.edit`, `picks.auto`)

Step 4 has two ways to let a model work, and they join here. **The prompt box** (`picks.edit`, `POST /api/projects/{pid}/picks/edit`: `{"instruction", "scope": {"beats": [ids]} | {"chapter": id} | {"all": true}, "base_rev"?, "model"?}`)
is one model call that answers typed picks operations: it rearranges, adds and removes pictures and regions the project already has, in one batch of the change log, and cannot import or look. A request that needs a
picture the project does not have ends as an `escalate` turn: nothing was written, `GET .../picks/edit/thread` has the turn with `status` `escalate` and the `reason`. **The pictures agent** (`picks.auto`, section 7) is what does that work: for
those lines, call `POST /api/projects/{pid}/picks/auto` with `{"beats": [those lines]}` (the command: `bti do <project> picks.auto --yes-cost --wait --set beats=[...]`), or hand the turn over as the page does,
`POST /api/projects/{pid}/picks/edit/{turn_id}/escalate` (body optional, `{"model"?}`): it calls `bti.picks.auto.escalate` for exactly the lines of the turn's scope, choosing them again (`redo`), with the owner's request in front of the agent;
the answer is the one of `picks/auto` plus `turn_id`; the turn becomes `running` on that job (`path` `agent`, `job_id`), and when the job ends the thread gives it `status` `applied` with `summary` (the sentence of the result), `batch_changes` (the sentences of the batches the
agent wrote), `result` (`lines_total`, `lines_done`, `lines_without`) or `failed`/`cancelled` with the code (a turn that failed or was stopped can be handed over again). Only a turn that ended as `escalate`, or an agent run of a turn that failed or was stopped, can be handed over
(`turn_not_escalated`). The turn has no batch of its own: every batch the agent wrote is undone one at a time from `GET .../changes` and `POST .../changes/{batch}/undo`.

**One agent run at a time per project.** The agent in a folder (`picks.auto`, a job of kind `picks`), a prompt-box turn of either step and the storyboard draft (jobs of kind `draft`) hold the one agent run: none of them starts while another runs. The state answer says so with
`no_running_job` in `needs` (for `picks.auto`, `picks.edit`, `draft.start`, `draft.edit`), and a route that is called anyway answers 409 `agent_job_running` (`retry` `later`, `job_id` of the job that runs) with a Vietnamese sentence on the page; a second job of the
same kind is the long-job runner's `busy`. Both actions are model calls: they carry `cost` (`model`), `long_job` and `uses_model`, their `auto_ok` is the owner's `spend.model` (section 1, "Automatic running and who approved"), and `bti do` runs them only with `--yes-cost`.

## 9. Automatic run ("Chạy tự động")

One long job that walks a project from wherever it stands to a finished video by the loop of section 1 ("Walking a project"), and writes down every step. It is what the
button "Chạy tự động" of the page starts, and what `bti run` starts. Code: `bti/auto_run/`; design: `docs/design/2026-11-18-agent-first-design.html`, "Cổng duyệt và chạy tự động".

```
POST /api/projects/{pid}/auto/run   {"until": null | "script" | "voice" | "picks" | "edit" | "export", "max_steps": 40, "actor": "human"}   -> {"job_id": "...", "run_id": "..."}
GET  /api/projects/{pid}/auto/runs?limit=10      -> {"items": [one line per run, newest first]}
GET  /api/projects/{pid}/auto/runs/{run_id}      -> the whole record, with one entry per step
```

`until` is the step to stop after (null: the video is exported); `max_steps` (1 to 200) is the most calls one run may make. The run is refused: `409 auto_not_enabled` while the
project's `auto` is off (the owner turns it on, section "Automatic running and who approved"); `409 auto_running` while a run of this project goes on; `409 longjob_running` or
`script_job_running` while another job of the project runs (a preview does not count); `422 invalid_field` for an unknown step or a bad `max_steps`. It is a long job of kind
`auto` (follow it with `GET /api/longjobs/{job_id}`, stop it with `POST /api/longjobs/{job_id}/cancel` or the `auto.cancel` action: the job the run started is stopped too,
and starting again continues, the finished parts are kept). The state answer lists `auto.run` while the switch is on and nothing is exported, with `body` `{until: null, max_steps: 40}`
and a `cost` that is the sum of what it may start from where the project stands, only of the kinds the owner allowed (`kinds` lists them); it is never `advances`, so a caller
that walks the list never takes it.

**One agent job at a time, both ways.** The run takes the pictures agent (`picks.auto`) and the storyboard draft itself, one step after the other, and follows their jobs; the three of them (and the
prompt boxes) hold the one agent run of the project (section 8). While a run goes on, the prompt boxes (`picks.edit`, `draft.edit`) and a hand-started pictures agent are refused like any other busy case:
409 `agent_job_running` (`retry` `later`, `job_id` of the run) and `no_running_job` in `needs` of the two boxes; the one caller that may start `picks.auto` meanwhile is the run itself, which names itself
with the `actor` `agent:auto` (the example body of `picks.auto` has an `actor`, the way the operations' examples do; an actor is what the caller says it is, not an authentication). The other way round, a job
that is not the run's (a prompt-box turn, the pictures agent, a voice...) makes the run stop with `busy_elsewhere` before it takes anything, and `POST .../auto/run` is refused with `longjob_running`. The `cost` of
`auto.run` counts `picks.auto` (a long job with a cost that is not paid) and not `picks.edit` (a person's own request, like `draft.edit`).

### The rule of the loop (five lines)

1. Read `GET .../state`. Stop when the project is exported (or the `until` step is done), when automatic running was turned off, or when a job that is not the run's runs on the project.
2. Take the FIRST action with `ready` and `advances`; never another, no operation batches of its own, no edits. The state answer decides what advancing means: a new step is picked up with no change here.
3. Allowed? A gate only when its `auto_ok` is true; a cost only when its kind is allowed in `spend`; a paid action never; `storyboard.restore` never.
4. Before a gate read its document and apply the quality bar (below); then call the action exactly as the answer describes it, as the actor `agent:auto` (it is put in every body that has an `actor`).
5. If the call answers a job, follow it to its end (a failed job ends the run with the job's code and sentence), then read the state again.

### How a run ends

The result is in the job's `meta.result` (always) and `result`, in the run log and in `GET .../auto/runs`: `{outcome, reason, sentence (Vietnamese), detail, fix (English), step, link,
action, gate, kind, issues, waiting_for, error, tolerated, lines_without_pick, steps_taken, ...}`. A run that fails ends its job as `error` with the failed action's `error_code` and the sentence as `error`; every
other end is `done` (a cancel is the runner's own: `cancelled`). The outcomes are `done`, `needs_owner`, `failed`, `nothing_to_do`, `cancelled` and `limit`.

**The quality bar at the pictures gate.** `asset_flag` (a flagged picture: size or licence) never stops the run: the owner said copyright is not a blocker and a picture from the owner's own books always carries the flag
"unknown"; it goes into the run log with its count (`tolerated` of the step: `[{code, count}]`). `beat_no_pick` (a line of the narration with no picture) stops the run only when MORE than a quarter of the lines
of the narration have none (`bti.auto_run.checks.NO_PICK_LIMIT`, 0.25; the number of lines is `narration.beat_ids` of `GET .../picks`; unknown: it stops); at or below a quarter the run goes on (the storyboard draft shows the main
painting for such lines) and says how many lines have none: in the step's `tolerated`, in the result's `tolerated` (`[{gate, code, count, lines?}]`), in `lines_without_pick` and as one more sentence at the end of `result.sentence`
("Có 3 dòng lời dẫn không có hình riêng: bản nháp dùng tranh chính ở các dòng đó."). `outside_no_picture` (a line about something outside the painting that shows only the main painting, because the picture
of the thing itself was not found) is judged against the lines about something outside the painting, not against all the lines: it stops the run only when MORE than 34% of those lines have it
(`bti.auto_run.checks.OUTSIDE_NO_PICTURE_LIMIT`, 0.34; their number is `outside.lines` of `GET .../picks`; unknown: it stops) and then the result lists them (`issues`, one for each line); at or below 34% the run goes on and says
how many: in the step's `tolerated`, in the result's `tolerated` (`{gate, code, count, lines}`, `lines` being the outside lines), in `lines_outside_without_picture` and as one more sentence at the end of `result.sentence`
("Có 3 dòng nói về thứ ngoài bức tranh mà chưa tìm được hình của thứ đó (trong 10 dòng như vậy): bản nháp dùng tranh chính ở các dòng đó."). Every warning code the picks document and the storyboard can give is in one of the two lists below (a test scans the sources); a warning in
neither stops the run.

<!-- BEGIN GENERATED: autorun -->
| reason | outcome | what it means | what to do |
|---|---|---|---|
| `exported` | done | The project is exported. |  |
| `until_reached` | done | The step {step} is done, as asked. |  |
| `gate_not_allowed` | needs_owner | The {gate} gate waits for the owner: automatic running may not approve it. | Ask the owner to approve the {gate} gate on the page (step {step}), or to allow it in the project's `auto` (PUT /api/projects/{pid}/auto), then run again. |
| `auto_turned_off` | needs_owner | Automatic running was turned off for this project while the run was going. | Ask the owner to turn automatic running on again (the switch on the page), then run again. |
| `spend_not_allowed` | needs_owner | {action} costs {kind} and the owner did not allow an agent to spend that. | Ask the owner to run {action} on the page (step {step}), or to allow {kind} spending in the project's `auto`. |
| `paid_needs_owner` | needs_owner | {action} costs money: an agent never starts it. | Ask the owner to start {action} on the page (step {step}) if they want it. |
| `quality_warning` | needs_owner | The {gate} gate has {count} warning(s) that stop an automatic run: {first_en} | Ask the owner to look at the {gate} document (step {step}) and approve it, or fix it and run again. |
| `quality_error` | needs_owner | The {gate} document has {count} error(s): {first_en} | Ask the owner to fix the errors listed in `issues` (step {step}), then run again. |
| `gate_refused` | needs_owner | The server refused to approve the {gate} gate: {error_code} ({error_detail}). | Ask the owner to fix what the refusal names (step {step}), then run again. |
| `repair_needed` | needs_owner | storyboard.json is unreadable: restoring a copy is the owner's decision, an automatic run does not do it. | Ask the owner to restore the storyboard on the page (step {step}), then run again. |
| `nothing_to_do` | nothing_to_do | No action moves the project forward now: it waits for {waiting_en}. | Meet what `waiting_for` names (step {step}), then run again. |
| `busy_elsewhere` | nothing_to_do | Another job of the project is running ({jobs_en}); an automatic run never starts a second one. | Wait for the job (GET /api/projects/{pid}/longjobs) or cancel it, then run again. |
| `needs_content` | nothing_to_do | {action} needs content that only the owner or the caller can supply (its `fill` fields). | Supply the content (step {step}), then run again. |
| `action_failed` | failed | {action} was refused: {error_code} ({error_detail}). | Read `error`, do what its `fix` says, then run again: finished work is kept. |
| `job_failed` | failed | The job of {action} ended in error: {error_code} ({error_detail}). | Read `error`, do what it says, then run again: finished parts are kept. |
| `unreachable` | failed | The app could not be reached from inside the run: {error_detail}. | Check that the app answers, then run again. |
| `no_progress` | failed | {action} was taken {count} times in a row and the state did not change. | Look at the project (GET /api/projects/{pid}/state) and the run log; do not run again before the cause is known. |
| `internal_error` | failed | The automatic run failed unexpectedly: {error_detail}. | Report it; the run log of the project names the step. |
| `cancelled` | cancelled | The run was cancelled; finished work is kept. | Run again to continue from where the project stands. |
| `job_cancelled_elsewhere` | cancelled | The job of {action} was cancelled or interrupted outside the run. | Run again to continue: finished parts are kept. |
| `step_limit` | limit | The run took {count} actions, the most it may take (`max_steps`). | Run again to continue, or raise `max_steps`. |
| `time_limit` | limit | The run used up its {hours} hours. | Run again to continue. |

| gate | warning that stops the run | why | warnings it lets through |
|---|---|---|---|
| `outline` | `fact_no_source`, `unknown_source_id`, `source_excluded`, `unknown_fact`, `disputed_no_conflict`, `fact_for_owner` | fact_no_source: a fact cites no source paragraph, so nothing in the books backs it; unknown_source_id: a fact cites a paragraph that is not in the brief; source_excluded: a fact leans on a source the owner excluded; unknown_fact: a chapter uses a fact that is not in the fact table; disputed_no_conflict: a disputed fact has no conflict described, so the narration would state it as certain; fact_for_owner: a fact's text holds a remark for the owner or an instruction, and the narration is written from it: it would be spoken | `budget_sum`, `fact_unused`, `no_hook_choice`, `outline_note` |
| `narration` | `words_off_target`, `unknown_fact`, `source_author_named`, `source_talk` | words_off_target: the length is more than 15% away from the target: the video would not be the length that was planned; unknown_fact: a line cites a fact that is not in the outline; source_author_named: a line names the author of a source book, and the voice would say it (the viewer has never heard of the books); source_talk: a line speaks about the sources themselves (the books, a passage, a doubt about a source) or carries a remark meant for the owner, and the voice would read it aloud | `beat_too_long`, `chapter_off_budget`, `long_sentence`, `no_show`, `spoken_chars` |
| `picks` | `beat_no_pick` (only when more than 25% of the lines have it), `beat_unknown`, `outside_no_picture` (only when more than 34% of the lines about something outside the painting have it) | beat_no_pick: more than a quarter of the lines of the narration have no picture (up to a quarter the run goes on: the draft shows the main painting there); beat_unknown: a picture is attached to a line that is not in the narration any more; outside_no_picture: more than 34% of the lines about something outside the painting show only the main painting, because no picture of the thing itself was found (up to 34% the run goes on: the draft shows the main painting there) | `asset_flag`, `content_box_unsure` |
| `storyboard` | `audio_missing`, `asset_size_mismatch`, `first_shot_late`, `label_without_position`, `end_after_audio`, `canvas_not_1080p`, `map_view_coarse`, `identity_technique_mismatch`, `incomplete`, `upright_whole_share`, `highlight_off_frame`, `highlight_too_dark`, `caption_placeholder`, `caption_repeats`, `text_not_in_narration`, `asset_not_in_lines`, `explainer_early`, `device_wrong_kind`, `device_too_little`, `figure_on_wrong_picture`, `name_not_shown`, `small_detail_not_lit`, `highlight_nothing_to_dim`, `text_too_brief`, `outside_on_painting`, `outside_picture_small`, `frame_off_painting`, `camera_off_region`, `thing_arrives_late` | audio_missing: the audio file does not exist; asset_size_mismatch: a picture's recorded size differs from its file: regions and camera keys are in the wrong space; first_shot_late: the first shot does not start at 0 s: the beginning is not covered; label_without_position: a label has no position and is not drawn; end_after_audio: the video would end after the voice; canvas_not_1080p: the canvas is not 1920x1080; map_view_coarse: a map is zoomed in too close: it has no detail there; identity_technique_mismatch: a title or chapter shot does not follow the chosen identity style; incomplete: an item is not filled in yet; upright_whole_share: the main painting is shown small between two black bars for more than 6% of the video (41 of 109 shots in the first real draft): the video looks dark and the same; highlight_off_frame: a spotlight points outside the frame or at its edge: everything else is dimmed and nothing is lit; highlight_too_dark: a spotlight leaves the frame almost black (mean luma under 32 on the 16 to 235 scale): the first export had three such stretches of five seconds; caption_placeholder: a caption on the screen is a placeholder, a note to the reader or only the picture file's artist and year ("UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950"); caption_repeats: a caption on the screen says the same words twice; text_not_in_narration: a place, label, figure or name on the screen is not in the narration: it may be a guess, and the owner's rule is that facts come only from the narration; asset_not_in_lines: a shot shows a picture that no line of the narration has: the owner took it out of every line; explainer_early: a diagram on its own background (map, time axis, tree, two-state picture) fills part of the first half minute: the painting leaves the screen as the viewer arrives; device_wrong_kind: a device (map, time axis, large figure, lit line, perspective lines, tree, two panels) is used on a line whose kind does not call for it: the owner's first video put maps on towns that were only mentioned and a figure over the wrong picture; device_too_little: a device has too little to show (a map with one place, a time axis with one or two dates, a key or a tree with fewer than three entries); figure_on_wrong_picture: a large figure is laid over another picture although the picks of its line hold the picture of the thing counted (the first video laid 42 ships over the saint); name_not_shown: a first-presented person has no on-screen name; small_detail_not_lit: a small named detail in the painting has no visual pointer; highlight_nothing_to_dim: a spotlight covers so much of the frame that little can be darkened; text_too_brief: on-screen text is not fully visible for long enough to read; outside_on_painting: a line about something outside the painting has its picture but shows the painting for most of the line (the picture is on screen for less than 45% of it, 25% when the line has two kinds, or for less than 3.5 seconds): the viewer never sees what the narrator speaks of; outside_picture_small: a picture that is not the painting is drawn smaller than 80% of its default fit: it sits small between black bars; frame_off_painting: a camera key of a shot on the main painting shows more than 1% of the frame outside the painted area of the picture: a band of the museum photograph's black ground, or of the matte past the picture's edge, stands at a side of the frame (the first test video had about a dozen such shots, the close-ups of the mirror); camera_off_region: at the end of a main-painting shot pointing at a region, that region's box extends outside the frame so the viewer cannot see all of it; thing_arrives_late: a named region stays wholly inside the frame for less than 2 seconds and less than 55% of the shot, so the camera arrives too late | `first_shot_transition`, `project_name_differs`, `shot_short`, `unknown_intent`, `unknown_source` |
<!-- END GENERATED: autorun -->

The run log is `projects/<pid>/auto_runs/<run id>.json` (`bti.autorun/1`), rewritten after every step: `{id, job_id, started, ended, until, max_steps, actor, steps: [{n, at, step,
action, method, path, body, status, ok, code, job_id, job_state, note, seconds}], outcome, reason, sentence, result}`. The newest 30 are kept. A run whose process died is reported
from the state of its job (never as `running` for ever). The long-job runner limits one part of a job to 35 minutes, so the job is a row of equal parts of 25 minutes (12 hours in
all) that take the loop over from each other: the `progress` of the job is not the run's; read `meta` (`step`, `step_label`, `n`, `of`, `action`, `child_job`, `steps_taken`).

## 10. The output folder (`output/<artwork key>/`)

One clean folder per painting, made by `bti/output/` and filled as the project moves: `final.mp4` at its root, `README.md`, `state.json` (`bti.output/1`), `INDEX.md` and `index.json` one level up, and the
parts `1_sources/` to `6_export/` and `log/`. The working folder `projects/<pid>/` stays what the app works in; nothing in the app reads a document back from the output folder. The root is `output/` beside
`projects/` (`BTI_OUTPUT_ROOT` moves it); an app made with an explicit projects folder and no `output_root` has none (then the routes below answer `409 output_disabled`).

```
POST /api/projects/{pid}/output/build   {"clean": true|false}  -> {key, folder, written, parts: {part: {rev, out_of_date, reason}}, warnings, clean, takeover}
GET  /api/projects/{pid}/output         -> {enabled, key, folder, state, warnings}      (state = state.json, or null before the folder exists)
```

`output.build` fills (or refills) the folder from the project as it stands; `clean: true` also removes the working folder's caches when the export stands (otherwise only the export itself does). Errors:
`output_disabled`, `output_not_applicable` (a reference or imported project), `output_failed` (the disk). The folder is written, with one line each, by: the last part (`output`) of the voice job and of the export job,
and after every successful change of a project through the API (an approval, a save, an edit: `bti/output/hooks.py`, one background write that never delays the answer). A part whose document changed after it was
published, or whose approval was withdrawn, keeps its old files and is marked `out_of_date` in `state.json` and in the README until it is published again. A second project of the same artwork takes the folder
over (its runs are added to `runs`); an older project never does by itself, only through `output.build`.

The switch `PUT /api/settings/output {"clean_after_export": false}` (`GET` the same path) turns the cleaning after an export off. The cleaning removes the paths listed in `bti/output/clean.py` and nothing else, while keeping the current export's rendered parts under `cache/export/parts/` (~840 MB per ~11-minute video).

The export splits the timeline into ~60-second parts (`part_seconds` in `config/server.json`) cut at shot starts (`bti/export/partkey.py`), keyed by what decides each part's frames (plus `RENDER_VERSION` in `bti/engine/__init__.py` and the style bundle signature), so a small storyboard edit re-renders only the parts whose frames changed and re-muxes the audio. The export manifest, job result, and `output/<key>/state.json` (`video`) report `parts_total`, `parts_rendered`, and `parts_reused`; the export plan also reports `parts_reused` and `parts_to_render`; and the cleaning record reports `kept_parts` and `kept_parts_bytes`.

## 11. The new opening, the video's title and fitting the storyboard to the voice (`storyboard.retime`)

Every video opens with the whole painting before the first word, then the channel name and under it the video's title (`docs/design/2026-11-18-identity-raking-light.md`, section 10). The parts that must be the same in every video are written by the program, never by a model.

```
PUT  /api/projects/{pid}/voice/settings   {"lead": 5.0, "title": 10.2}     seconds; lead 0.2 to 15, title 3 to 30; null takes the project's own value away
GET  /api/projects/{pid}/voice            -> ... "silence": {"lead": 5.0, "title": 10.2, "own": {"lead": true, "title": true}, "default": {"lead": 0.35, "title": 6.2}, "intro": {"lead": 5.0, "title": 10.2}, "range": {...}}
PUT  /api/projects/{pid}/identity         {"video_title": "The Goldsmith Who Sold Time", "base_rev": "..."}   style may be left out (the present one stays); "" takes the title away; 409 `storyboard_off_voice` while the storyboard does not fit the voice (call storyboard.retime first)
POST /api/projects/{pid}/storyboard/retime   {"base_rev": "...", "actor": "cli:name"}  -> {"rev", "changed": [shot ids], "batch": "batch_0007", "report": {...}}
```

- **The two silences.** A project the app creates gets `intro` of `config/voice.json` (5.0 and 10.2 s) written into its `voice/settings.json`; a project without its own values uses `silence.lead` 0.35 and `silence.title` 6.2 exactly as before (its voice state, timing and `assemble_sig` do not change). A change of either value makes the voice `stale` (`mix_settings_changed`: "cần ghép lại"); `voice.generate` with scope `changed` then assembles and aligns again and speaks no sentence again. Errors: `bad_lead`, `bad_title`.
- **The opening shot.** When the first word starts at 3.3 s or later and the video starts with a cold open, the first shot is the program's: `CAM-01` on the main painting, the id `s0000`, `{"t": 0}` to 0.35 s before the first word, the entire painting inside the frame, no overlays of its own (`ID-OPEN-01` and `ID-LABEL-01` sit on it). The model's first shot starts on the first word (`{"w": 0, "off": -0.35}`).
- **The beat.** `ID-BRAND-03` of the style `raking`: 9.1 s with the new silences (`min(B, gap - card - 1.2)`; 5.4 s with the old ones), texts `text` (the channel name), `title` (the video's title; without one, the painting's title) and `subtitle` ("<painting> · <Artist, year>"). A storyboard whose slot is still `ID-BRAND-01` under `raking` is the earlier form of the same style: no `identity_technique_mismatch`, it renders as before and becomes `ID-BRAND-03` when the identity is applied again (the retime does that).
- **`storyboard.retime`** (`Khớp lại với giọng đọc`; no model, no cost). Listed when the storyboard does not fit the voice: the first shot does not start at 0; the opening shot is missing (or present although the first word starts earlier than 3.3 s); the beat does not end where the chapter card starts (the silence ends) or starts before its silence; a chapter card does not end where its silence ends or does not start where the compiler puts it; the number of cards is not the number of chapters that have one; `end` is not the duration of the voice (tolerance 0.05 s; the LENGTH of the beat is not a problem). Ready when the voice is done; `advances` when something can be moved. It moves what is off, puts the opening shot in or takes it out (the next shot then starts 0.35 s before the first word, or at 0), sets `end` and applies the identity style again, with the project's title: the title document (`title.json`) wins over the storyboard's own `identity.video_title`, so a title that `title.set` or `title.generate` stored while the storyboard was off the voice reaches the beat now (`report.video_title` says `{from, to}`). No shot of the model or of the owner is touched except the start of the shot after an inserted or removed opening shot; a locked shot is left and listed in `report.left`; the number of cards is reported, never repaired. The same call twice changes nothing the second time and writes no revision. One batch in the change log (`bti changes`, `bti undo`; the undo gives back the whole document the batch changed: the shots, `end` and `identity`, and names a part that was changed since as a conflict `{"part": "end"}`); the storyboard's approval stops standing by the existing rule.
- **The guard.** `POST /api/projects/{pid}/approve` and `POST /api/projects/{pid}/export/start` refuse with `409 storyboard_off_voice` (`problems` lists them; retry after the fix: call `storyboard.retime`) while the storyboard does not fit the voice. In the state answer `storyboard.approve` and `export.start` then carry the need `storyboard_fits_voice`. The automatic run takes `storyboard.retime` itself before the storyboard gate.
- **To get the new opening on a video made before this change** (what the coordinator does): `PUT .../voice/settings {"lead": 5.0, "title": 10.2}`; `voice.generate` (scope `changed`: no sentence is spoken again) and wait; `storyboard.retime` (`bti do <project> storyboard.retime`; it also writes the project's title onto the beat); then, if the title is not the one in `title.json` yet, `title.set` (or `PUT .../identity {"video_title": "..."}`, which is refused with `storyboard_off_voice` until the retime is done); approve the storyboard again; export.

## 12. The video's title (`title.generate`, `title.set`)

The video's title is the line the channel-name beat shows under the channel's name. After the narration is approved an agent reads it and writes the title by a written skill (`skills/title/TASK.template.md`, the task the agent itself reads; `skills/title/SKILL.md` is the operator's document, `bti doc title`). The project's document is `projects/<pid>/title.json` (schema `bti.title/1`; never edited by hand). It has no gate: nobody approves a title.

```
GET  /api/projects/{pid}/title            -> {rev, state, title, candidates, narration_rev, current_narration_rev, stale, agent, running, history, written, limits, storyboard, problems}
POST /api/projects/{pid}/title/generate   {"note": "...", "model": "...", "actor": "..."} (all optional)  -> {job_id, model, agent}      a long job of kind `title`: GET /api/longjobs/{job_id}
PUT  /api/projects/{pid}/title            {"base_rev": "<rev of GET>", "text": "..." | "option": 2, "actor": "..."}  -> {rev, state, title, candidates, storyboard}
```

- **State.** `none` (no title), `done`, `stale` (an agent's title written from another narration revision than the one now: the narration was changed and approved again). A title set by a person or an operator (`title.source` `person`) is never stale. `title` is the title in use (`text`, `by` = `agent:<model id>` or the actor that set it, `at`, `source` `agent` | `person`, `option`); `candidates` what the agent returned (`text`, `form`, the narration `lines` that make it true, `scores` on `curiosity`, `concrete`, `central`, `clear`, a Vietnamese `why`); `history` the titles in use before (at most 20). The state answer carries `title` {state, text, by, at, source, candidates, stale}.
- **`title.generate`** (kind `title`, role `script.title`, the third role of the agent select of step 2; cost `model`, about a minute). A temporary work folder holds `inputs/narration.json`, `inputs/outline.json` (the thesis and the hook), `inputs/painting.json` and the task rendered from the template; the agent writes `out/title.json`; the program checks it (the same `./check` the agent runs: a title over 60 characters or nine words, a refused phrase of rules 6 and 7, a colon or another second half, brackets, an emoji, a word in capitals, two question marks, a number in digits that no cited line holds, an unknown line id, a reason that is not Vietnamese, fewer than five candidates, two of the same text), sends ONE repair message into the same conversation when it finds errors, and writes the document with the first candidate as the title in use. The limits and the refused phrases are in `bti/title/rules.py`, the one place both the template and the check read. Limits of a session: 10 minutes, 40 steps, one repair round. It holds the project's one agent run: refused with `agent_job_running` while the pictures agent, a prompt-box turn, a draft or an automatic run (other than the caller itself, `actor` `agent:auto`) works, and none of those starts while it runs. Refusals: `narration_not_approved` (409), `title_note_too_long` / `title_note_invalid` (422), `agy_missing`, `claude_missing`, `claude_auth` (409) and the codes of the agent that cannot run. A job that ends without a usable file fails with `title_no_output` (after the repair), `title_limit` or `title_tampered`; nothing is written then.
- **Ready and advancing.** In the state answer `title.generate` is ready when the narration is approved and no other agent job runs; it `advances` while the state is `none` or `stale`. The automatic run takes it by itself, before the voice (the step `script` comes first), never over a person's title (a `done` title does not advance), and stops with `job_failed` when it fails. `draft.start` carries the need `title_done` while the state is `none` or `stale` and an agent could write the title (a project whose title agent cannot run does not wait: the beat then shows the painting's title and the state answer has the warning `title_missing` once a storyboard exists). `title.set` is always ready (`fill` `text`; `--set text=...`); to take a candidate of the agent send `{"base_rev", "option": n}` (`--body FILE`) or give its text.
- **`PUT`.** One of `text` (one line, at most 60 characters; the banned phrases are not looked for: a person may write what they want) and `option` (the number, from 1, of a candidate). `409 stale_revision` (`rev`, `current_rev`) when `base_rev` is not the revision of GET (a project with no title yet has `rev` of the empty document, which GET answers); `422` `title_invalid`, `title_not_one_line`, `title_too_long`, `title_option_unknown`, `title_choice_needed`. A generation asked for by hand replaces a person's title (it goes to `history`).
- **The storyboard.** A full draft compile writes the document's title into the storyboard's `identity` block (it wins over a title carried over). Setting a title by `PUT`, or writing one by the job, while a storyboard exists applies the channel identity again with the new title in the same request (the beat's `title` and `subtitle`): the storyboard's revision changes, its approval stops standing by the existing rule and `storyboard` of the answer (`{rev, changed, approval_was_fresh, sentence}`, or `error` and a sentence when the engine refused: the title is written all the same) says so; the same title again changes nothing. A project with no storyboard answers `storyboard: null`. While the storyboard does not fit the voice (`storyboard_off_voice`: the voice was made again and `storyboard.retime` was not called) nothing is written to it: `storyboard` of the answer is `{rev, changed: [], approval_was_fresh: false, off_voice: true, code: "storyboard_off_voice", problems: <n>, sentence}` and the sentence says the storyboard takes the title after the retime (`storyboard.retime` writes the title document's title onto the beat); the title is stored all the same, and the sentence of the job's result ends with it. `GET .../title` has `storyboard.off_voice` (true while it is off the voice) for the page's strip.
- **The export and the output folder.** The first line of the description is the video's title (the document, else the storyboard's own, else the painting's title as before), then the painting, painter and year. `output/<key>/2_script/title.md` lists the title in use, who chose it, every candidate with its reasons and the earlier titles; `README.md` and `state.json` (`title`) name it.
- **What the coordinator calls on a real project** (`eligius`), in this order: first one real generation to see what the agent proposes, `bti do eligius title.generate --yes-cost --wait` (then `GET /api/projects/eligius/title`: the candidates with their reasons), then the owner's own title, `bti do eligius title.set --set text="The Saint Who Was Also an Advertisement"`: it becomes the title in use (`source` `person`: never stale, never written over by the automatic run) and the agent's candidates stay listed. The other order works too, but a generation asked for by hand replaces the person's title (it goes to `history`), so the owner's title would have to be set again.

The storyboard viewer warnings include `small_detail_not_lit`,
`highlight_nothing_to_dim`, `text_too_brief`, `camera_off_region`, and `thing_arrives_late`. Their `args` identify the
line, shot or overlay and the measured size, frame miss, or reading/arrival time; the draft check
prints their English hints. These warnings stop automatic approval of the
storyboard, as `outside_on_painting` does.

A `voice_assemble_failed` job retains the assembly failure detail in its `error`;
`bti job` shows a fix suited to the failure. True-peak failures list the
measurements after up to five encodes. Each retry increases limiter margin by
the measured overshoot plus 0.3 dB.

For `X-ANN-01` overlays, `params.sub` is an optional smaller second line; leaving it empty retains the original strip. Names and any uncertainty must follow the narration, and picture metadata must follow the record.
