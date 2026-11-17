# BUILD: the storyboard draft (DRAFT agent)

Written 2026-11-16. Contract: `docs/design/2026-11-16-stages-3-4-6-and-draft-design.md` sections 7 and 7.4.

## What exists

| File | What |
|---|---|
| `bti/draft/inputs.py` | `DraftInputs`, `load_inputs(project_dir, chapters)`, `normalize_timing` (ids and ranges for chapters and beats), picks helpers, hashes, `DraftError(code, message)`. |
| `bti/draft/spec.py` | The spec `bti.draft/1`: shape check with messages that name chapter and shot (counted from 1) and say what to write; `out/regions.json` check. |
| `bti/draft/compile.py` | Spec to full `bti.storyboard/1` (design 7.2): ids kept on a re-draft, start anchors, tiling, engine defaults (camera keys aimed at a region), overlays with ends clamped to the shot, chapter cards and title card in the silences, locked shots carried through, asset merge (storyboard wins; agent regions added), validate and draw check, issues in the spec's terms, `degrade` (replace broken shots by a push-in, drop broken overlays, `auto` for a missing chapter), narration-on-screen refusal, shorts-only refusal, pacing warnings, edit-mode scope check. |
| `bti/draft/decompile.py` | The reverse: saved storyboard to specs by chapter (`inputs/current/`), `scope_violations` (7.4). |
| `bti/draft/engine.py` | `DraftProject` (engine `Project` for an unsaved document) and `scaled_images` (workspace copies are downscaled; this stretches them back to the declared source size so source-pixel coordinates hold). |
| `bti/draft/workspace.py` | `build` (copies only, downscaled images, `techniques.md` generated, `TASK.md` rendered from the template, wrappers `check`/`defaults`/`still` (`.cmd` on Windows)), `read_out` (only `out/`, refuses links), `workspace_compile`. |
| `bti/draft/techniques_md.py` | The generated `inputs/techniques.md` (71 techniques, intent index, usage class, slots, params). |
| `bti/draft/check.py`, `defaults.py`, `still.py` | The three helper commands (`python -m bti.draft.check|defaults|still`). |
| `bti/draft/providers/auto.py` | The no-model drafter. |
| `bti/draft/providers/agy.py` | The agent run: command line, stream-json on stdin, events read, time limit, cancel by killing the tree, one run at a time, env whitelist, repair turns, tamper marking. |
| `bti/draft/guard.py` | Tamper check. Watched: comic repo `git status --short` (key `comic_repo` of `config/server.json`; skipped when absent); the repo's `bti/ style/ config/ prompts/ skills/` (any difference, `__pycache__` ignored); in the project, files that existed before under `media/ audio/ source/` plus `timing.json` and `project.json` (change or deletion). New files and everything the app writes (`storyboard.json`, `picks.json`, `cache/`, `history/`, `proposals/`, `script/`, `voice/`, `export/`) are not looked at. |
| `bti/draft/run.py` | The job (three parts: prepare, agent, compile), `start`, `state`, `overview`, `readiness`. |
| `bti/editor/draft_api.py` | `router`: `GET /api/projects/{pid}/draft`, `GET .../draft/models`, `POST .../draft/start`. |
| `bti/editor/static/js/draftpanel.js` | `mountDraftPanel(container, {pid, scope, onProposal})`. |
| `skills/storyboard_draft/TASK.template.md` | The agent's instructions (modes draft and edit). |
| `tests/draft/` | 88 tests. |

## Tests (run on the Windows server only)

`tools/deploy/remote_test.sh tests/draft -q`: **88 passed** in 79 s (full folder, after the last change). Files: `test_spec_inputs` 14, `test_compile` 25, `test_decompile` 5, `test_auto` 5, `test_workspace` 10, `test_agy` 15, `test_run` 10, `test_api` 4. Slowest: the real arnolfini `auto` draft with the draw check (26 s).

Real data used: `projects/arnolfini` (copied to a temp folder: media, timing, storyboard). Faked: the `agy` program (`tests/draft/fake_agy.py`, speaks the same stream), nothing else. The long-job runner is the real `bti.longjob`.

Round trip (`test_round_trip_of_the_real_arnolfini_storyboard`): decompile, compile in edit mode with an empty scope: every shot of the real storyboard (ids, anchors, slots, params, overlays, locked, source, note) comes back equal. Not exact by construction: an anchor `{"t": ...}` is described as nearest word plus offset in the spec but the compiler copies the saved anchor, so it comes back as `t`; cards are not part of the specs (carried through in edit mode); in a plain re-draft (not edit mode) cards are regenerated from the voice's silences and may differ from hand-tuned ones (ids are kept by time).

## Decisions and deviations

- `timing.json` chapters and beats may lack ids (the real arnolfini file does): ids `c01...` and `b0001...` are made in order. `card` of a chapter may be true/false or `{start, end}`.
- `lead` of a timing chapter (`{kind: title|card|plain, start, end}`, from the voice) decides the cards when present: `card` puts X-CARD-01 (2.8 s) ending at `lead.end`; `title` puts the title card X-CARD-02 (2.9 s) before it (and a chapter card too when the chapter's `card` flag is set; at the very start of the video the first card begins at 0); `plain` places none; the chapter's first shot starts at `lead.end`. Without `lead` the length rule below applies. A card whose saved shot is `locked` is never regenerated.
- Card without `lead`: X-CARD-01 of 2.8 s ending at the chapter start (needs at least 1.0 s of silence, else a warning and no card); a title card X-CARD-02 of 2.9 s before it only when the silence is 5.9 s or more (the voice contract's 3.0 s never leaves room: the title card appears only if the voice agent leaves more).
- Spec additions beyond section 7.1 (all optional): shot `off`, `transition_in`, `id`; overlay `dur`, `off`; `locked`, `in_scope`, `start_s`, `end_s` are read-only info in `inputs/current/`.
- `end_word` of an overlay means "until that word has been spoken" (its end time).
- A shot starting inside a locked shot is dropped; a continuation shot starts where the locked shot ends so that the locked shot keeps its length.
- Heavy slot not used (the model works, not this machine). The agent part is one part with a 30 minute limit including repair turns; the part limit of the long-job runner is 35.
- `agy` now runs through `ctx.run_process` (`stdin=`, `on_start=`, `separate_stderr=`): cancel, the 35-minute part limit and the tree kill are the job's. `bti/proc.py` is still used in two places the runner cannot cover: (1) the draft's own 30-minute limit, which kills the tree with `kill_tree(handle._proc)` and keeps the partial result (a `handle.kill()` in `ProcessHandle` would remove the private access); (2) `DefaultRunner` in `providers/agy.py`, a copy of the runner's interface for runs outside a job (tests). The tamper check reads `comic_repo` through `load_config()`.
- Objection to the contract: none that changes behaviour. Two remarks: (1) the tamper check cannot tell a storyboard saved by the owner during the run from a change by the agent; the panel should say "do not edit while the agent works" (not done yet); (2) `base_rev` for a project without a storyboard is `null`, and the proposals route must accept that.

## Needs another agent

1. **CORE, `bti/editor/app.py`**: `from .draft_api import router as draft_router; app.include_router(draft_router)`. The router reads the projects folder from `app.state.projects_root`.
2. **CORE, `bti/editor/proposals.py`**: `apply` with `accept: "all"` on a project without `storyboard.json` adopts the proposal's `storyboard` as the first `storyboard.json` (base_rev is `null` then; `stale` must be false for that case). Also a proposal file carries extra keys (`made_from`, `issues_left`, `degraded`, `stats`, `notes`, `scope`): the list route should show `summary` and may show `len(issues_left)`.
3. **CORE, storyboard view**: a container element for the panel: `import { mountDraftPanel } from '../draftpanel.js'; const off = mountDraftPanel(el, { pid, scope, onProposal: (id) => openProposals(onApplied, id) });` (`scope` is the view's lifecycle scope; the panel unmounts with it, `off()` also works). When the project has no storyboard, step 5 should show the panel instead of the empty editor.
4. **CORE, `pipeline_api.py`**: `from bti.draft import state` gives `{"state": none|running|stale|done, "detail": Vietnamese}`.
5. **CORE, `config/server.json`**: optional key `comic_repo` in the platform block (path of the comic repository): `guard.comic_repo_status()` compares `git status --short` before and after a run when it is set.
6. (done by CORE: `STAGE_CODES`/`labels.js`; `stages_words.test.mjs` passes, nothing outstanding.) Earlier note: **errmsg.js** error codes (the job error is shown through `jobErrorText`, which shows a Vietnamese `error` as it is; these codes come with Vietnamese sentences already, so no entry is strictly needed). For the routes (`{detail, code}` answers, English detail): `draft_not_ready`, `agy_missing`, `scope_needs_storyboard`, `bad_provider`, `bad_model`, `bad_chapters`, `unknown_chapter`, `busy`, `picks_missing`, `timing_missing`, `picks_no_main`.
7. **labels.js**: the panel keeps its Vietnamese words in the `TEXT` table at the top of `draftpanel.js`; move them into `labels.js` when convenient (title "Bản nháp storyboard", "Dựng bản nháp", "Dựng tự động (không dùng agent)", "Mô hình", "Dừng", "Mở đề xuất", and the rest of the table).
8. **longjob** (optional): a `stdin` option on `ctx.run_process`.
9. **css**: the panel uses classes `draft-panel`, `row`, `chip ok|partial`, `banner warn`, `hint` of the existing style sheet; nothing new is needed, but `.draft-panel .row {display:flex; gap:8px; align-items:center}` would help.

## Where the edit mode (7.4) plugs in

Built: `decompile.py` (specs of the saved storyboard with `in_scope`/`locked`), the compiler's scope check (`DraftInputs.edit_shots`, `CompileResult.violations`, issue codes `edit_outside_scope`, `edit_locked_changed`), verbatim carry-through of unchanged shots (same id), kept cards, `workspace.build(inputs, instruction=..., scope_words=...)` (writes `INSTRUCTION.md`, `inputs/current/` with marks), the template's `edit` mode. Not built (as asked): the route `draft/edit`, the thread, the prompt box. To add: in `run.py` a `start_edit(pid, project_dir, instruction, scope, model)` that calls `load_inputs(project_dir, chapters_of_shots(...))`, sets `inp.edit_shots`, builds the workspace with `instruction=`, runs the same three parts, and in the compile part refuses (PartError) when `res.violations` is not empty instead of degrading (`compile_specs(..., degrade=False)` first; the proposal is written only when `violations == []`). Follow-up in the same conversation: `agy.run(..., prompt=...)` already takes the prompt; keep `conversation_id` from `AgyResult` and pass `--conversation` (see `_Proc` respawn).

## For the live test (everything about the real `agy` that was assumed)

Command run (cwd = workspace): `agy --dangerously-skip-permissions --model <slug> --input-format stream-json --output-format stream-json`, stdin one line `{"event":"user","message":{"content":"Read TASK.md in this folder and do the task."}}`.

Unverified assumptions:
1. No `-p` flag is needed with `--input-format stream-json` (the stash's provider did the same, never verified live).
2. Events: `init` (with `conversation_id` at top level or inside `result`), many `step_update` with `step_update.step_index`, `.state`, `.step_type`, and one `result` per turn with `status` `SUCCESS|ERROR|CANCELED`, `response`, `conversation_id`, `error`. If the real names differ, progress shows 0 steps and a missing `result` becomes the error `agy_no_result`: check `cache/draft/<run>/events.jsonl` (the raw transcript is kept).
3. The process stays alive after a turn and reads the next line from stdin (repair turns on the same conversation). If it exits after each turn, the provider restarts it with `--conversation <id>`; whether that flag continues the conversation, and whether the model keeps its files/state, is unknown.
4. The agent can read PNG/JPEG files (`images/*.jpg`) with its file tool; if not, the draft works from `assets.json` and `beats.json` only (worse regions). Look at what the transcript shows.
5. The agent can run the helper commands (`.\check.cmd`, `.\still.cmd`) in its terminal tool on Windows (PowerShell or cmd). The wrappers set `PYTHONPATH` and `PYTHONUTF8` themselves and use the absolute Python of the app (`sys.executable`), so they need nothing from the environment. If its shell refuses `.cmd`, the task template says to continue without them.
6. `--dangerously-skip-permissions` also covers writing in the workspace and running the wrappers; `--settings` keys are not used.
7. `--print-timeout` is not passed (our own limit of 30 minutes kills the tree). Unknown whether the program has an internal per-turn limit.
8. The environment whitelist (stash list plus `BTI_PYTHON`, `PYTHONUTF8`) is enough for the program to find its sign-in. The sign-in lives in the owner's desktop session: the app must run there.
9. A run writes 2 to 10 files in `out/` and takes unknown minutes; the first real run decides the repair limits and whether the model should do chapters one at a time (`chapters` in `POST draft/start`).
10. `agy --help` contains `--input-format`, `--dangerously-skip-permissions` and `--model` (checked before every first run; the run is refused with `agy_config` otherwise).
11. The model slug default `gemini-pro-orchestrator-g1-pro` exists on the server (it is in the Mac's `agy models`).

What to look at after the first real run: `last_run.json` (status, steps, turns, elapsed), `events.jsonl`, the copy of `out/`, `notes.md`, the proposal's `issues_left` and `degraded` (what the compiler had to fix), and whether the project folder was reported `tampered` by something harmless (an owner's save during the run).


### The first real run, step by step (for the coordinator)

Project and scope: a project that has an approved `picks.json` and a `timing.json` from the voice step (not arnolfini: it has no picks). Start with ONE chapter, the smallest one (a re-draft of one chapter needs an existing storyboard, so for a project without one the first run is the whole video: then first run `provider: "auto"` once, apply that proposal in step 5 to get a storyboard, and run the real agent on one chapter of it).

1. Make sure the app runs in the owner's desktop session where `agy` is signed in (`agy models` must list `gemini-pro-orchestrator-g1-pro`; this is checked by `GET /api/projects/<pid>/draft/models`, `error` must be null).
2. Open `GET http://127.0.0.1:8560/api/projects/<pid>/draft`: `ready.ok` must be true. Do not save, edit or upload to `media/`, `audio/`, `timing.json` or `project.json` during the run (saving the storyboard or picks is allowed).
3. Start: `POST /api/projects/<pid>/draft/start` with body `{"provider": "agy", "chapters": ["c02"]}` (omit `chapters` for the whole video; add `"model": "<slug>"` to change the model). The answer is `{"job_id": ...}`.
4. Watch: `GET /api/longjobs/<job_id>` every few seconds: parts `prepare`, `agent`, `compile`; the `agent` note reads "Bước N, <last action>; đã viết k/n chương".
5. Transcript: `projects/<pid>/cache/draft/<run id>/events.jsonl` (every raw event line, written as it arrives: `Get-Content -Wait` it); the copy of `out/` is next to it in `out/`; `projects/<pid>/cache/draft/last_run.json` has the status. The workspace itself is a folder `bti-draft-*` in the system temp directory; it is deleted on success and kept on failure or tampering (look in it: `TASK.md`, `out/`, `look/`).
6. Look first at: the first 20 lines of `events.jsonl` (are the event names the assumed ones? `init`, `step_update`, `result`), then whether `out/` got files, then `last_run.json` (`status`, `steps`, `turns`), then the proposal `proposals/draft_<run id>.json`: `issues_left`, `degraded` and `notes`. Open it in step 5 through the "Đề xuất" box.
7. Stop: `POST /api/longjobs/<job_id>/cancel` (kills the whole `agy` process tree within seconds; nothing is written). If the app itself is gone, end the `agy.exe` process whose parent is the app's python (your own process only; see docs/WINDOWS.md) and remove the `bti-draft-*` temp folder.
8. A result `tampered` means a watched file changed during the run: the job error names it; fix or restore it, then rerun. Typical harmless cause: an upload replaced an existing file in `media/`.
