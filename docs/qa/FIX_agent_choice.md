# The agent select: two agents, one select per step, remembered for the whole pipeline (worker `agentpick`, 2026-11-18)

Contract: `docs/design/2026-11-18-agent-choice.md`. Built on the Claude Code runner of `docs/qa/FIX_claude_runner.md`. No model of any kind was called: not by
the code written here, not by the tests, not by me (no `agy`, no `claude`, no `agy models`, no `claude auth status`). Every test uses the mock provider,
fakes, and a private agent file (`BTI_AGENT_CHOICES_FILE`).

## 1. What was built, per section of the brief

| Brief | Where |
|---|---|
| 1. The choices file, the module, the document, the machine default, the one resolution function | `config/agent_choices.json` (the file of contract section 2, byte for byte); `bti/agents.py` (`load_choices`/`parse_choices`: validated, never raises, a bad entry is dropped and named in `problems`; `model_for_project(project_dir, role, requested=None) -> Resolved(model, agent_id, label, source)`; the project document `agent.json` with `read_project`/`update_project`/`project_view`: atomic write, revision = sha1 of the canonical JSON like the script and picks documents, stale write refused, a lock per project, `levels=0` so a deleted project is never made again; `public_agents()` with the availability of each agent; `set_machine_default`); `bti/settings.py` (`get_machine_agent`/`set_machine_agent` for `run/settings.json` key `agent`, one shared atomic writer; `model_for(role)` is unchanged) |
| 2. Every model call of steps 2 and 5 resolves through it when the request names no model | Outline and narration: `bti/editor/script_api.py` (`job_model`); draft, fast edit, deep edit: `bti/draft/run.py` (`_resolve`, used by `start`, `make_parts`, `make_edit_parts`, `_author`, `overview`, the turn record, the job `meta`); `bti/draft/fastedit.py` (a caller without a model gets the project's agent). The draft now passes the resolved model to `agy.run` (before, `model=None` made `agy.run` fall back to `model_for("draft")`, which would have ignored a project's choice). A request that names a model keeps working exactly as before; a `model` that is not a non-empty string is still 400. The job record, the start answer, the edit turn, `last_run.json` and `GET /draft` carry `agent: {id, label, model, source}` next to the model |
| 3. Routes | `bti/editor/agent_api.py` (`GET /api/agents`, `GET`/`PUT /api/projects/{pid}/agent`), registered in `bti/editor/app.py`; `PUT /api/settings/agent` in `bti/editor/settings_api.py`. Draft routes: `claude_missing` and `claude_auth` are now 409 (were 422); `GET /draft/models` is kept (see section 3) |
| 4. The page | `bti/editor/static/js/agentlogic.js` (pure: what the select shows, where the value comes from, bodies of the PUT, the other agent, the quota sentence and view), `agentpick.js` (the select, `mountAgentPick`, and `quotaNode`, shared by the three places), used in `views/script.js` (replaces `#model-pick`), `draftpanel.js` (replaces its model select and its `GET /draft/models` call), `promptedit.js` (replaces the model link); `settings.js` (the box: "Agent mặc định cho dự án mới" on top, the per-role table under a collapsed "Nâng cao" with the line "Chỉ dùng khi dự án và mặc định đều chưa chọn agent."); source lines of the outline and the narration, the job line of the status bar, the draft job line and the edit card name the agent by its label. Words: `labels.js` (block `agentpick`, `AGENT_LABELS`), `errmsg.js` (block `worker agentpick`), CSS in `shell.css` and `script.css`, `mockapi.js` answers the three routes in `?mock=1` |
| 5. Quota | Step 2 dialog, draft panel and prompt box card each show one sentence that names the agent and the time ("Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút.") and exactly one button, "Chuyển sang Gemini 3.8 Flash và chạy lại", which stores the other agent as this step's choice and runs the same request again (`quotaNode`). Works for `agy_rate_limit` and `claude_rate_limit` (and a script job's `rate_limit`). A script job now carries `retry_after_seconds` and `retry_at` like a draft job and an edit turn |
| 6. `docs/APP_GUIDE.md` | New part "Chọn agent" (section 2), the sentences about the old model selects corrected (sections 5, 5.2, 5.4, 5.4b, 5.7, 7: draft panel, prompt box, "Cài đặt") |
| Part B | `bti/draft/check.py` (`inside_workspace`, `refuse_outside`), `bti/draft/defaults.py`, `bti/draft/still.py`: each of the three refuses, before doing anything, a workspace path or an output path that resolves outside the folder it was started in (symbolic links and `..` resolved, also for a file that does not exist yet; compared the way the file system compares names; another drive is outside): exit status 2 and one sentence on standard error, nothing written. `still` checks `-o` the way it writes it (relative to the workspace argument) and checks the default `look/<chapter>_<n>.jpg` again just before writing (a `look` folder that is a link). The normal calls are untouched (the wrappers of `bti/draft/workspace.py` run `-m bti.draft.*` with the workspace as the current folder) |

Tests added: `tests/settings/test_agents.py` (choices file, every rule of the resolution order and an unknown id falling through, the document, stale write, clearing, bad ids, the machine default, availability), `tests/editor/test_agent_routes.py` (the routes, a job without a model uses the project's agent and says which, a second project is not affected, `agent_unavailable`, the quota answer with its time), `tests/draft/test_agent_choice.py` (draft, fast and deep edit resolve through the agent and report it, 409 for Claude Code codes, quota fields on the turn), `tests/draft/test_helper_confinement.py` (Part B), `tests/editor_frontend/agentlogic.test.mjs`, and the browser check `tests/e2e/agent/agent_select.mjs` (with `tests/e2e/agent/launch_agent.py`).

## 2. Deviations from the contract, and why

1. **`GET /api/agents` and the project GET carry extra fields**: `reason_code` per agent (`not_signed_in`, `not_installed`, `timeout`, `model_not_listed`, ...) and `warnings` (an agent id the file no longer lists, an unreadable `agent.json`, a problem of the choices file). The contract names `warnings` only for the project GET.
2. **`effective[step]` is resolved for the step's first role** (`script.outline`, `picks`, `draft`). Rules 2 to 4 are the same for every role of a step; only rule 5 (the per-role setting under "Nâng cao") can differ between the roles of one step, and the select shows the first.
3. **An agent that cannot run stays choosable.** The contract says the select must let the owner see it; I show it as "Opus 5.5 High (chưa dùng được)", the line under the select gives the reason, and a start is refused by the server with that sentence (409 `agent_unavailable`, or `claude_auth` / `claude_missing` for the draft). I did not disable the option: a project may be set up before the owner signs in on the server.
4. **A model no agent offers** (a per-role setting under "Nâng cao", for example `mock`) resolves with `agent_id: null` and its own label; the select shows it in a disabled first entry "(theo cài đặt nâng cao)" so it never shows an agent that will not run.
5. **`GET /api/projects/{pid}/draft/models` is kept, and the page no longer reads it.** Its shape is unchanged (`default`, `models`, `error`); `default` is now the model the next draft of that project uses (its agent) and `agent` says whose it is. The old list of `agy models` slugs stays useful for a tool that names a model itself. I did not delete it: the brief asked me to decide, and a removed route breaks any outside caller for no gain.
6. **The step 2 dialog "alternatives" (any enabled model, offered after a time-out or a quota) is gone.** It belonged to the model select. After a quota answer the dialog is the quota message; after a time-out there is a toast and the owner runs again. The job record still carries `alternatives` (unused by the page).
7. **"Thử lại" stays on a failed edit card, including a quota card.** It is part of every failed card, not of the quota message; the message itself has exactly one button. After the owner has waited, "Thử lại" runs the same request on the same agent.
8. **The time in the quota sentence** is counted from the moment the answer came for a script job and a draft job (they carry the epoch `finished`), rounded up to whole minutes. An edit turn only knows its start as a clock time of the SERVER's zone (`at`), so there the sentence says what the server counted when the turn failed (a card read much later still says "4 giờ 30 phút"; in the first browser run the zone difference between the Mac and the server made it say 29 minutes, which is what led to this rule).
9. **`bti/draft/providers/agy.py` is not touched.** `run.py` now always passes the resolved model, so the "model lookup" fallback in `agy.build_command` is only reached by a direct caller without a model (it keeps `model_for("draft")`).
10. Section 6 says "Whether an automatic run may switch by itself is decided with build stage C6": nothing switches by itself anywhere.

## 3. Files touched beyond the list in the brief (one line each)

- `bti/script/runner.py`: `Job.agent`, `Job.retry_after_seconds`/`retry_at` in the record, `ScriptJobs.start(..., agent=)`, `JobError(retry_after_seconds=)`. Needed for "the job record says which agent was used" and for the quota time of a script job.
- `bti/script/generate.py`: one line, `call_model` passes the provider error's `retry_after_seconds` on in the `JobError`.
- `bti/draft/thread.py`: one line, `_normalize_turn` keeps the turn's `agent` (it drops every key it does not list, so the edit result could not name its agent).
- `tests/e2e/stages/remote.mjs`: one line, `BTI_STAGES_LAUNCH` chooses another launcher (the browser check wraps `launch.py`); `tests/e2e/stages/prompt_edit.mjs`: its checks about the model link and the settings box updated to the new layout.
- `tests/editor/test_backend_fixes.py`: `test_every_job_endpoint_demands_a_model` became `..._refuses_a_model_that_is_not_a_model_id`: a request that leaves the model out is no longer 400 (the project's agent decides); `""`, blank, a number and a list still are.

## 4. Tests

Python, on the Windows server in the snapshot `agentpick` (`BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh agentpick -- <folder> -q -p no:cacheprovider`, one folder per run, after the last Python change). Summary lines exactly as printed:

```
tests/settings                  44 passed, 1 warning in 4.43s
tests/script                    243 passed, 7 skipped in 29.50s
tests/draft                     330 passed, 1 warning in 121.87s (0:02:01)
tests/editor                    478 passed, 1 warning in 209.55s (0:03:29)
tests/identity                  77 passed in 1.20s
tests/engine -m "not slow"      304 passed, 14 skipped, 150 deselected in 181.79s (0:03:01)
tests/draft/test_helper_confinement.py (Part B, alone, first run)   22 passed in 3.27s
```

On the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` printed `tests 302`, `pass 302`, `fail 0` (279 before; 23 new in `agentlogic.test.mjs`).

The 7 skipped in `tests/script` are the same as in `docs/qa/FIX_claude_runner.md`. The 4 tests of `tests/draft/test_helper_confinement.py` that need a symbolic link ran (the server allows links) and so did the Windows-only one.

New tests: `tests/settings/test_agents.py` (35), `tests/editor/test_agent_routes.py` (29), `tests/draft/test_agent_choice.py` (18), `tests/draft/test_helper_confinement.py` (22), `tests/editor_frontend/agentlogic.test.mjs` (23). One existing test changed (section 3). A first run of `tests/draft` had 5 failures, all in my new `test_agent_choice.py`: `bti/draft/thread.py` dropped the `agent` key of a turn (fixed, section 3); two of my assertions were wrong and were corrected.

Browser check, `BTI_SSH_HOST=winbox-cmd node tests/e2e/agent/agent_select.mjs` (a second instance of the app on the server with the two mock agents; headless Chrome on the Mac; no real model): the last run printed `65 pass, 0 fail`. Earlier runs found real problems that were fixed: 53 pass 8 fail (the draft panel check needs the picks approved; the edit card's quota time was computed from the server's clock time; two of my probes were wrong), then 62 pass 1 fail (the fake model of `launch.py` answers an edit with a heading of an older template; see below), then 65 pass 0 fail with that one probe relaxed while the cause was found, then 65 pass 0 fail with the strict probe once `launch_agent.py` carried its own canned answer, and 65 pass 0 fail again on the final code. What it covers (contract section 8): the select on step 2 and on step 5 (the draft panel and the prompt box), a change on a step for that step only, "Dùng cho cả dự án", a reload keeps it, a second project is not affected, the page sends no model and the job and the source line name the agent, an agent that cannot run (shown, reason, the server's sentence on start), the quota message with its sentence and ONE button at the three places (step 2 dialog, draft panel, prompt box card) and the rerun with the other agent, the settings box (default agent on top and saved at once, "Nâng cao" collapsed with its hint line, the table inside), stale and bad ids, no raw words or leftovers on each page.

Screenshots (1700x1000 and 1280x720 each), `.scratch/agentpick/shots/`:

| Point | Files |
|---|---|
| Step 2 with the select ("Theo mặc định") | `01-step2-select-1700.png`, `01-step2-select-1280.png` |
| Step 2, a choice for this step ("Riêng cho bước này", the link) | `02-step2-step-choice-1700.png`, `-1280` |
| Step 2, "Dùng cho cả dự án" ("Theo dự án") | `03-step2-whole-project-1700.png`, `-1280` |
| Step 2, an agent that cannot run | `04-step2-unavailable-1700.png`, `-1280` |
| Step 2, the quota message with its one button | `05-step2-quota-1700.png`, `-1280` |
| Step 5, the prompt box | `06-step5-prompt-box-1700.png`, `-1280` |
| Step 5, the draft panel | `07-step5-draft-panel-1700.png`, `-1280` |
| Step 5, the draft panel's quota message | `08-step5-draft-quota-1700.png`, `-1280` |
| Step 5, the prompt box card's quota message | `09-step5-prompt-quota-1700.png`, `-1280` |
| The settings box, top, and with "Nâng cao" open | `10-settings-top-1700.png`, `11-settings-advanced-1700.png` (and `-1280`) |

Note on `tests/e2e/stages/launch.py` (not edited): its canned answer to an edit looks for the heading "# Edit Storyboard by Instruction" of an older template (the current `skills/storyboard_edit/FAST.template.md` starts "# Briefing: change a few shots ..."), so with that launcher alone the mock answers "mock response" and every fast edit ends `spec_invalid`. `tests/e2e/stages/prompt_edit.mjs` (the previous worker's probe, only its settings and link lines were updated here) cannot pass its edit steps against the current template. `tests/e2e/agent/launch_agent.py` carries its own canned answer for the current template.

## 5. What I could not verify

- Any real call: forbidden, none made. The Opus agent on the server is "not signed in" (contract section 2a); that state was **simulated** in the browser check (`launch_agent.py` makes the mock Opus model answer with the sentence of the real check), and the real `claude_status()` path is covered by the claudeprov tests and by `tests/settings/test_agents.py` with fakes. `GET /api/agents` was never asked of the real app on port 8560 (forbidden).
- The wording of a REAL Claude Code usage-limit answer and a real `agy` quota answer: the sentences and the time come from the providers (recorded shapes, `docs/qa/FIX_claude_runner.md`); the page shows the seconds the provider reported.
- That the owner reads "mở lại sau khoảng 4 giờ 30 phút" correctly across time zones for an old edit card (see deviation 8).
- The old browser probes `tests/e2e/shell_library_script/run.mjs`, `run_extra.mjs`, `tests/e2e/round2/run.mjs` and `tests/e2e/round3/fixes.mjs` select the model through `#model-pick`, which no longer exists. They are historical probes with launchers of their own; I did not port them (a private agent file would be needed there as well).
- Windows `cmd` quoting of the three helper commands through the wrappers: the tests run the commands with `python -m` (what the wrappers run), on the Windows server.

## 6. What I chose not to do

- The picks agent and the automatic run (contract section 7), a third agent, any change to the prompts, the briefings, the engine, the media or picks code, the identity code, or how a runner calls its program.
- Step 4 gets no select (its agent does not exist yet); its choice can already be stored through the API (`steps.picks`).
- The proposals list (`bti/editor/static/js/proposals.js`, not in my list) still prints the proposal's `author` string (`agent:agy:gemini-3.8-flash-high`) raw. **Needs another worker**: show the agent's label there (the proposal document could carry `agent` next to `author`; `run.py` already knows it).
- I did not make an unavailable agent unselectable, and I did not hide "Thử lại" on a quota card (deviations 3 and 7).
