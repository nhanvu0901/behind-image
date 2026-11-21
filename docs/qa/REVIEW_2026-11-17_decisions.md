# Decisions after the review of 2026-11-17

Written by the analyst on 2026-11-17. It is the contract for the workers that fix what `docs/qa/REVIEW_2026-11-17_other_agent.md`
found, and for three things the owner agreed to on 2026-11-17:

1. An instruction to the agent **changes the storyboard directly**; every change is listed in plain Vietnamese and can be undone.
2. A **fast path** (one model call, no file tools) beside the slow agentic path, because a two-shot change took 9.5 minutes.
3. Models are a **setting the owner can change**; the default is Gemini 3.8 Flash (High) through the Antigravity CLI.

Where this file differs from section 7.4 of `docs/design/2026-11-16-stages-3-4-6-and-draft-design.md`, this file wins; the worker
updates 7.4 to match. Not in this contract (still being designed with the owner): an agent for the picks step, a prompt box in the
picks step, and a simpler layout of the picks and storyboard pages.

One principle for every item: **fix the class, not the reported case**, and prove it with a test that fails before the fix.

## Who owns what

| Worker | Owns (may edit) |
|---|---|
| T0 tools | `tools/deploy/snapshot_*.sh` and helpers it adds under `tools/deploy/`, the section "Snapshot tests" of `docs/WINDOWS.md` |
| A-core | `bti/draft/**`, `bti/editor/draft_api.py`, `bti/settings.py` (new), `bti/editor/settings_api.py` (new), `config/agents.json` (new), `skills/storyboard_edit/**` (new), `skills/storyboard_draft/**`, `tests/draft/**`, `tests/settings/**` (new); the smallest needed changes in `bti/script/providers/**`, `bti/script/models.py`, `bti/editor/app.py` (router registration), `bti/editor/proposals.py`, every `conftest.py` (the safety switch) |
| B clips | `bti/media/clips.py`, `bti/media/api.py`, `bti/media/assets.py`, `bti/picks/**`, `bti/editor/picks_api.py`, `bti/editor/media_adapter.py`, `bti/editor/static/js/views/picks.js`, `views/picks_logic.js`, `static/css/picks.css`, `requirements.txt`, `tests/media/**`, `tests/picks/**` |
| A-page (starts after A-core) | `bti/editor/static/js/promptedit.js`, `draftpanel.js`, `proposals.js`, `views/storyboard.js` (the hooks only), `views/script.js` (model default only), a new settings dialog module, `static/css/edit.css`, `tests/editor_frontend/**`, `tests/e2e/**`, `docs/APP_GUIDE.md` |

`bti/editor/static/js/labels.js` and `errmsg.js` are shared: add entries only inside a block of your own marked with a comment
(`// --- draft and edit` or `// --- picks and clips`), re-read the file right before each edit, and keep each edit small.

## Part A: editing the storyboard by instruction (step 5)

### A1. E0, the blocker: cards in a chapter's lead silence
`bti/draft/compile.py:189-191` keeps an existing chapter card in edit mode only when its time is `<= chapter start`. Cards sit in
the silence after the chapter's `start` and before its first word (`lead`). Keep every card whose time is before the chapter's
first spoken word (`lead.end` when the timing has `lead`, else the first word's start).
- Test, no model: take a real storyboard and timing with `lead` (copy `storyboard.json` and `timing.json` of the server project
  `arnolfini-live` into `tests/draft/fixtures/arnolfini_live/`; they are small text files, no media), decompile it, hand the specs
  back unchanged, compile in edit mode: **zero violations for every chapter scope and for every single-shot scope**. The reviewer's
  script `.scratch/review_20261117/viol3.py` shows the failing case.

### A2. Two paths behind one route
`POST /api/projects/{pid}/draft/edit {instruction, scope: {shots?|chapter?|all?}, model?, mode?: "auto"|"fast"|"deep", base_rev?}`.
- `mode` default `auto`: **fast** when the resolved scope has at most 12 shots, else **deep**. The fast path may answer `escalate`;
  in `auto` the server then runs the deep path in the same turn and the turn says so.
- Validate the request (scope, instruction, model) before looking for the `agy` program (E9).
- Write the turn to the thread before the job starts (E13).

**Fast path** (new, `bti/draft/fastedit.py`): one call through the existing single-turn provider layer (`bti/script/providers`,
model id such as `agy:gemini-3.8-flash-high`, or `mock` in tests). No workspace, no tools.
- Prompt (template in `skills/storyboard_edit/FAST.template.md`): the instruction; the last three turns of the thread (instruction
  and summary); the scope's shots as draft specs (from `decompile`), each with its beat text, start and length; one read-only
  neighbour shot on each side; the assets used in the scope and the main asset with their regions (name, label, box in source
  pixels); the compact technique catalogue (`techniques_md`); the pacing numbers; the rules below.
- The model answers with one JSON object and nothing else:
  ```json
  {"result": "edit" | "cannot" | "escalate",
   "summary": "một câu tiếng Việt, không có mã nội bộ",
   "shots": [ "the full replacement list for the scope, same format as the draft spec shots, with id kept for shots that continue an existing one" ],
   "regions": [{"asset": "A", "name": "DOG", "label": "Con chó", "x": 0, "y": 0, "rx": 0, "ry": 0}],
   "changes": [{"shot": "id or position in the replacement list", "what": "một câu tiếng Việt"}],
   "reason": "for cannot or escalate: một câu tiếng Việt"}
  ```
  `cannot`: the request needs something the project does not have (a new picture, a change to the narration or the voice); nothing
  changes and `reason` tells the owner what to do. `escalate`: the request needs looking at the picture (a detail with no region)
  or restructuring more than the scope; the deep path does it.
- Server: tolerant extraction of the JSON object, shape check with messages a model can act on, then the existing edit compiler
  with the scope (no change outside the scope, none to a locked shot, time range of the scope tiled exactly), `validate`, and a draw
  check of the changed shots only. On any issue: **one** repair call with the issue list; then apply or fail.
- Rules in the prompt: change only what the instruction asks; keep everything else in the scope as it is; never put narration text
  on screen; `summary` and every `what` in plain Vietnamese without shot ids or parameter names (technique ids are allowed).

**Deep path**: the existing agentic run, with these changes: up to two repair turns when the result has errors or scope violations
(as the draft has); the agent's output is kept under the turn's folder even when refused (E0b); the task text tells the agent to
stop as soon as the checker passes (E7); the model comes from the settings (A6); the same Vietnamese `summary` and `changes` are
required in `out/notes.json`; when a previous deep turn of the same project left a conversation id less than two hours old, continue
that conversation, otherwise copy the last three turns into `INSTRUCTION.md` (E6). No checkbox for this.

### A3. Direct apply, with a three-way merge
When a result compiles with no error and no violation, the server applies it at once; no proposal to accept.
- Base = the saved storyboard when the job started; current = the saved storyboard now.
- If current equals base: write the result. If not: merge per shot on the server (a pure, tested function with the same rules as
  `static/js/sbmerge.js`): a shot the result changed, added or removed that is unchanged between base and current is taken from the
  result; all other shots come from current. If a shot the result touches was also changed in current, or the shot list inside the
  scope's time range changed in current: no automatic apply; the turn becomes `needs_choice` and
  `POST /draft/edit/{turn_id}/resolve {action: "overwrite" | "discard"}` settles it.
- The write goes through the same path as a storyboard save (validation, history copy, new revision). Changed shots get
  `source: "agent"`. Approvals are left alone (they become stale as after any edit).
- The turn records: `before_rev`, `after_rev`, `path` (`fast` or `deep`, and `escalated`), `seconds`, `model`, `summary`,
  `changes: [{shot_id, number, start, op: "changed"|"added"|"removed", what}]`, and under
  `cache/draft/turns/<turn_id>/` the full storyboard before and after (keep the last 20 turns; older ones lose undo and say so).
- Statuses: `running`, `applied`, `no_change`, `needs_choice`, `failed`, `cancelled`, `undone`.

### A4. Undo
`POST /draft/edit/{turn_id}/undo {force?: bool}`: when the shots the turn touched are still as the turn left them, put their
versions from before the turn back (one more revision); status `undone`. When some were changed since: 409 `undo_conflict` with
those shots listed; `force: true` restores them anyway. The editor's own undo history starts fresh after an apply, as it does after
a two-tab merge (`Store.rebase(..., {fresh})`).

### A5. What the page shows (A-page)
- One box under the preview: the text field, the scope in words ("2 cảnh đang chọn", "Chương: The Merchant And His Brand",
  "Cả video"; never a raw id), the send button. No model dropdown here (the setting decides; a small link opens the settings).
- A turn card: the owner's instruction; while running, a Vietnamese progress line (part names and states through `labels.js`; for
  the fast path "Đang nghĩ…", "Đang kiểm tra…"); then the `summary`, and for each change: the shot's number and time, the `what`
  sentence, a thumbnail before and after (`GET /draft/edit/{turn_id}/frames/{shot_id}/{before|after}.jpg`, 320 px wide, drawn on
  demand from the stored storyboards). Buttons: "Xem thử" (the existing preview clip of the changed range), "Hoàn tác".
  `needs_choice`: the two choices in words. `failed`: one Vietnamese sentence by error code and "Thử lại". The model's raw notes
  and English text are only under "chi tiết" (E3). Times in 24-hour form (E10).
- After `applied` the editor takes the new storyboard in: with no unsaved edits it reloads and keeps the selection and the playhead;
  with unsaved edits it goes through the existing rebase merge.
- Every state and error code has a Vietnamese sentence in `labels.js` / `errmsg.js` (E1, E2); the static tests must cover
  `promptedit.js`.
- The thread and the box have room: at 1280x720 the preview keeps at least 300 px of height and a turn card is readable (E11).
  "Xóa lịch sử" asks once (E14). Choosing more shots: clicking shots while "Chọn nhiều cảnh" is on, not a list of 93 rows.
- The proposals box is no longer part of editing by instruction. It stays for the draft of a whole video.

### A6. Models are a setting
- `config/agents.json` (tracked defaults), all `agy:gemini-3.8-flash-high`: roles `script.outline`, `script.narration`, `draft`,
  `edit.fast`, `edit.deep`, `picks` (reserved). The owner's choices live in `run/settings.json` (git-ignored, kept by the deploy),
  written atomically.
- `bti/settings.py`: `model_for(role) -> str`; `GET /api/settings/models` (roles with Vietnamese labels, the value in force, where
  it comes from, the list of available models from the existing cached model list, and whether each value is in that list);
  `PUT /api/settings/models {role: model_id, ...}` (unknown role or model id is 422).
- One id form everywhere: `agy:<slug>`. The agentic roles (`draft`, `edit.deep`) accept only `agy:` models; the draft provider
  strips the prefix. `bti/draft/providers/agy.py` has no default of its own any more (E8).
- Every place that preselects a model (script page, draft panel) takes the setting, not the program's own default.
- A-page: a "Cài đặt" entry in the top bar opens "Mô hình cho từng việc": one dropdown per role and "Dùng một mô hình cho tất cả".

### A7. No real model, by accident, ever again
Twice a test rig started a real model run. One switch: when the environment has `BTI_NO_REAL_MODELS=1`, every real provider
(single-turn Antigravity, OpenRouter, the agentic draft provider, the You.com client, the clip downloader) refuses at once with the
error code `real_models_off`. Every `conftest.py` and every end-to-end launcher (`tests/e2e/stages/launch.py`, the snapshot test
runner) sets it before importing the app. A test proves each provider refuses. Finding out why hiding `agy` from the path did not
work in `tests/e2e/stages` is part of this (E9).

### A8. Small ones
E12: separate "last run" records for a draft and for an edit. E0b: a refusal names the shots in the owner's words ("Cảnh 14 và 15
nằm ngoài phần bạn chọn").

## Part B: video clips in the picks step

- **C1.** Add `yt-dlp` (pinned) to `requirements.txt`. It is installed into the project's own virtual environment on the server by
  the next deploy; the owner asked for the clip feature to work. When the tool is missing the tab says so in a standing notice, not
  in a toast.
- **C2.** A pasted link is reduced to the 11-character video id with an anchored pattern, and the program is always given
  `https://www.youtube.com/watch?v=<id>` after a `--` argument. Tests with hostile strings (leading dashes, spaces, a second URL,
  shell characters, other hosts).
- **C3.** Nothing raw on screen: the reason of a suggested section is a code with arguments (`chapter`, `subtitle`, `replayed`)
  turned into Vietnamese by `labels.js`; errors go through `errmsg.js`; the channel name is data and may be shown as it is.
- **C4.** Cutting a clip is a long job (`bti/longjob`) with progress and cancel; the page follows it and survives a reload.
- **C5.** One copy on disk: the working file under `cache/clips/` is removed after a successful import; the folder is capped at
  500 MB, oldest first.
- **C6.** Both upload routes normalise a video the same way (one function), muted, 30 fps.
- **C7.** The tray card of a clip plays the imported file itself (`<video>`, range requests, muted), so the owner can see what was
  cut. Start and end can be set with two sliders over the clip's length as well as by typing.
- From the review's list of confusing points: the button that searches for money says so on its face; a disabled "Cắt & thêm vào
  dòng" shows its reason in text next to it; the role list of a clip offers only roles that make sense for a video.
- The keyword search uses You.com (paid, behind the existing confirmation). The key is in the project's key file; never print it.

## Part C: export without subtitles

Kept as the other agent left it: no `.srt`, no subtitle track. Remove the dead subtitle reads in `bti/export/check.py`.

## Testing rules for every worker

- Python tests run on the Windows server, never on the Mac, and never in the server's main folder (the owner is using the app
  there): use `tools/deploy/snapshot_test.sh <your name> -- <pytest arguments>` (built by T0; see "Snapshot tests" in
  `docs/WINDOWS.md`). One run at a time per worker; a stage folder per run.
- JavaScript unit tests run on the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs`.
- No real model, voice, render, You.com or download in any test. Real runs are done later by the analyst, counted.
- Never restart or redeploy the server's main app; never write to the project `scream`.
