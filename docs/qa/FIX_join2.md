# FIX join2: the prompt box and the pictures agent on one page and one API

Worker `join2`, worktree `.worktrees/integ2` (branch `integ2`), 2026-11-19. Brief: `.scratch/agy_tasks/join2/TASK.md`. Inputs: `docs/qa/FIX_c5_cli.md`, `docs/qa/FIX_c2_box.md`,
`docs/qa/FIX_c3_picks_agent.md`. No git command that writes was run (the coordinator stages and commits). No model, no `agy`, no `claude`, no `.env`: the mock agents only.
Python ran on the server (`snapshot_test.sh join2`, one folder per run); Node and the two probes from the Mac. No conflict marker is left anywhere in the tree (searched).

## 1. The five conflicted files

| File | How it was resolved |
|---|---|
| `bti/editor/picks_api.py` | Both blocks kept. The agent's two routes (`POST` and `GET .../picks/auto`, `c3picks`) first, then the prompt box's routes (`POST .../picks/edit`, `GET .../picks/edit/thread`, `POST .../picks/edit/{turn}/undo`, `DELETE .../picks/edit/thread`, `c2box`) and one new route of this join (`POST .../picks/edit/{turn_id}/escalate`). |
| `bti/editor/state_api.py` | Two hunks. The catalogue (`SPECS`) and the table of builders (`BUILDERS`) have both actions, in the order of the page's work: `picks.search`, `picks.import`, `picks.import_book_image`, `picks.import_clip`, `picks.suggest`, `picks.put`, **`picks.auto`** (the agent), **`picks.edit`** (the request box), `picks.ops`, `picks.approve`, `picks.cancel` (the c2 side had `approve` before `ops`; it is last of the work now; the sort of the answer is by tier, so what an agent is told to do next did not change: what advances comes first). `picks.cancel` keeps the agent's wording. Nothing of either side dropped. |
| `bti/editor/static/css/picks.css` | The page root grid has three rows (top bar, the agent's bar `#pk-auto`, the body) and `min-width: 1280px` (the four columns of the box need 1280, the agent's side only asked 980): `auto auto minmax(0, 1fr)`. Both blocks of rules kept (the agent's bar and the reason under a line; the prompt box column). One more rule of this join: the foot of the line column (`.pk-beatfoot`) wraps, because at 1280 px its note field made a horizontal scroll bar inside the column (seen in the probe's screenshot, now gone). |
| `bti/editor/static/js/views/picks.js` | Both mounts kept: the agent's bar (`mountPicksAuto`, `auto`), then `selectListeners.clear()` and the prompt box (`mountPromptEdit`). The box page object got the hook `agentStarted` (see 2). |
| `tests/state/test_state.py` | `PICKS_OPEN` has the box (`picks.edit`), `PICKS_OPEN_MAIN` has the agent too (ready once a main painting exists), in the page's order: `... picks.put, picks.auto, picks.edit, picks.ops`. Every other expectation of both sides is as it was. |

## 2. How the two builds are connected now

* **A request the box cannot do hands over to the agent.** A step-4 turn that ends as `escalate` (nothing written) has a card with two buttons: **Để agent chọn hình** (first, primary, "mất vài phút") and **Tìm hình bằng tay** (second, opens the search).
  The first calls the new route `POST /api/projects/{pid}/picks/edit/{turn_id}/escalate` (`bti/editor/boxroutes.py::escalate_picks_turn`), which finds the lines of the turn's scope (a line, several, a chapter, all)
  and calls `bti.picks.auto.escalate(pid, pdir, beat_ids, note=<the owner's request>)`: the agent works on exactly those lines, choosing them again (`redo`), with the owner's words in both of its briefings. Same refusals as `picks/auto`, same answer plus `turn_id`.
  The button is disabled (with the reason) when the agent chosen for the step cannot run.
* **The card follows the job.** The turn becomes `running` on that job (`path: "agent"`, `job_id`); the card shows the agent's parts ("Lập danh sách hình cần tìm (1/4) - ..."), says it takes minutes, has Dừng; the bar of the page picks up the same job at once (`auto.follow()`).
  When the job ends the thread gives the turn its result: `applied` with the sentence of the result (`Agent đã chọn hình cho 1/1 đoạn.`), the sentences of the batches the agent wrote, `result` (lines done, lines without a picture), or `failed` / `cancelled` with the code (a quota failure shows the usual one-button message).
  A failed or stopped agent turn can be handed over again ("Thử lại"). The card has no "Hoàn tác" of its own (the agent writes several batches): it points to "Lịch sử thay đổi", where each batch is undone. The page takes the saved picks in when the turn changes, as for any turn.
  `bti/draft/thread.py` keeps the new turn field `result`; `reconcile_thread` already gave the status.
* **One agent run at a time per project.** The agent in a folder (`picks.auto`, kind `picks`, `meta.action` `auto`), a prompt-box turn of either step and the storyboard draft (kind `draft`) hold the one agent run. `bti.draft.run.other_agent_job` / `refuse_while_agent_busy` and `bti.picks.auto.job.start` refuse a start while the other kind runs:
  409 `agent_job_running` (`retry` `later`, `job_id`), one Vietnamese sentence on the page and in `texts.VI`: "Agent đang làm một việc khác cho dự án này (chọn hình, sửa bằng lời hoặc dựng bản nháp). Chờ xong hoặc bấm Dừng rồi thử lại." The state answer says it earlier: `no_running_job` in `needs` of `picks.auto`, `picks.edit`, `draft.start`, `draft.edit` (`Ctx.agent_busy`).
  I also refused the storyboard draft and the step-5 box while the pictures agent runs (the brief named only the step-4 box): they would meet the agent's own lock (`agy_busy`) half way otherwise. A second job of the same kind is still the runner's `busy`.
* **The state answer is consistent.** `picks.auto` and `picks.edit`: `long_job` true, `uses_model` true, `cost.kind` `model` (about 20 minutes, about 30 seconds), `follow` `GET /api/longjobs/{job_id}`, the agent of role `picks`; the example body of `picks.auto` is accepted as it stands, `picks.edit` has `fill` `["instruction", "scope"]` and a template the route takes (a test posts both). New code `turn_not_escalated` (409: only an `escalate` turn, or a failed or stopped agent run of one, can be handed over).
* **Wording.** The box's briefing no longer sends the owner to "the column Tìm hình" (the card has the buttons): the model says what is missing. The old card sentence "Agent chọn hình chưa có" is gone.

## 3. The gate rule and the command

Nothing in `bti/auto.py` or `bti/cli/` needed a change, and I did not add a line there: `picks.auto`, `picks.edit` (and `draft.edit` of step 5) carry `cost = (model, ...)` in the catalogue, and the rule of `c5cli` reads exactly that: `auto_ok` is `spend.model` of `auto.json` (true by the defaults, false when the owner forbids it), `bti status` prints `costs model (...); needs --yes-cost; long job`, `bti do` refuses an unconfirmed cost with exit 3 (`cost_not_confirmed`), a forbidden one with exit 3 (`spend_not_allowed`, before anything is sent), a not-ready action with exit 5 when it only waits for a job (`no_running_job`), and `--wait` follows the job. Proven in `tests/cli/test_cli_picks_agent.py` (8 tests, the fake agent runner and the mock model of the box, the real search over fake sources):
status lists both in the page's order with their marks; `--yes-cost` is needed; `--set beats=[...]` names lines; a forbidden model spend refuses both (and `draft.edit`) with nothing sent and no model asked; `bti do picks.edit` through the box ends `escalate`, and `bti do picks.auto --set beats=[...]` does what the box could not;
while the agent runs, `picks.edit` and `picks.auto` are exit 5 and `bti status` says `next: bti job <id> --wait`, the server itself answers 409 `agent_job_running`. `AGENTS.md` rule 4 and `skills/picks/SKILL.md` (a hand-written part "Let the agent choose first, then correct with the request box" and two rows of the refusals) say it for an agent that operates a project.

## 4. Generated documents

`python -m bti.editor.hints` regenerated `docs/AGENT_API.md` (both actions, the new `no_running_job` text, the two new codes); `python -m bti.cli.docgen` regenerated the lists of `skills/picks/SKILL.md` (`picks.auto`, `picks.edit`; `AGENTS.md` and the other skills had no change in their generated parts);
`python -m bti.ops.doc --check` and `python -m bti.cli.docgen --check`: up to date (`docs/OPS.md` has nothing stale: no operation changed). Hand-written: `docs/AGENT_API.md` section 8 (the box, the hand-over, one agent run at a time), `docs/APP_GUIDE.md` (the card of step 4, in Vietnamese), `AGENTS.md` rule 4, `skills/picks/SKILL.md`.
Every new code has its hint (`agent_job_running`, `turn_not_escalated`), its Vietnamese sentence (`errmsg.js`, `draft_run.VI`, `texts.VI`) and its place in the scan lists (`EDIT_CODES`); the scan tests of `tests/state` and the Node tests decide.

## 5. Files touched beyond the five

Code: `bti/draft/run.py`, `bti/draft/thread.py`, `bti/editor/boxroutes.py`, `bti/editor/draft_api.py`, `bti/editor/hints.py`, `bti/picks/auto/job.py`, `bti/picks/auto/texts.py`, `bti/editor/static/js/editlogic.js`, `promptedit.js`, `errmsg.js`, `labels.js`, `views/picks_auto.js`.
Documents: `AGENTS.md`, `docs/AGENT_API.md`, `docs/APP_GUIDE.md`, `skills/picks/SKILL.md`, `skills/picks_edit/FAST.template.md`, this report.
Tests: `tests/picks/test_join_box_auto.py` (new, 14), `tests/cli/test_cli_picks_agent.py` (new, 8), `tests/editor_frontend/editlogic.test.mjs` (the c2 expectation of the step-4 card changed: first choice the agent, second the search by hand; 6 tests added), `tests/e2e/box/box.mjs`, `tests/e2e/picks_auto/picks_auto.mjs`, `tests/e2e/picks_auto/launch_picks_auto.py` (a second demo project `picks-join`), `tests/e2e/stages/box_mock.py` (the canned reason).
`.scratch/agy_tasks/join2/STATUS.md`.

## 6. Summary lines as printed (snapshot `join2`, `-q`, one folder per run, nothing else running on that snapshot)

```
tests/state     295 passed, 1 warning in 169.44s (0:02:49)
tests/cli       127 passed, 1 warning in 43.47s
tests/ops       468 passed, 1 warning in 118.43s (0:01:58)
tests/picks     235 passed, 1 warning in 55.03s
tests/draft     400 passed, 1 warning in 148.10s (0:02:28)
tests/editor    488 passed, 1 warning in 221.98s (0:03:41)      (see the note below: not run again after the last css edit)
tests/script    262 passed, 7 skipped in 35.12s
tests/media     363 passed in 4.10s
tests/longjob   69 passed, 1 skipped, 1 warning in 7.21s
tests/settings  44 passed, 1 warning in 5.60s
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
ℹ tests 381   ℹ pass 380   ℹ fail 0   ℹ skipped 1
```

The skipped Node test is the existing `ISSUE_CODES` template check that needs `.venv/bin/python`. `tests/library` was not run (the brief).
Two of my own test loops overlapped on the snapshot for a few minutes (the first was still running when I started the second: my mistake). `state`, `cli` and `draft` failed in that overlap (a project of the shared data missing for a moment, a snapshot file in use) and were run again alone and passed; the other seven were run again alone too: the lines above are those runs.
**`tests/editor` was not run on the very last tree.** Its line above is from the run before the last edit of `picks.css` (the wrap of the foot of the line column, a rule of 2 lines; no test reads that file: `grep -rn picks.css tests` finds nothing). I started it again twice after the edit: the connection to the server (`ssh winbox-cmd`, 100.74.19.84 port 22) timed out from 07:22 on, the first run dropped at 44% (`Read from remote host ... Operation timed out`),
the others never connected (`ssh: connect to host 100.74.19.84 port 22: Operation timed out`, exit 255), and it was still down at 08:04 when I stopped trying. Reported as skipped on the final tree, not as passed. The same server loss is why nothing else was run after it.

## 7. The two browser probes (a second instance on the server with the mock agents, stopped after each; headless Chrome on the Mac), last lines as printed

`BTI_SSH_HOST=winbox-cmd node tests/e2e/box/box.mjs` (port 8571, suffix `c2box`): `54 pass, 0 fail` (the step-4 escalate check now wants the agent button first and the search by hand second; one check added; the rest unchanged).
`BTI_SSH_HOST=winbox-cmd node tests/e2e/picks_auto/picks_auto.mjs` (port 8577, suffix `c3p`): `86 pass, 0 fail` (the 52 of the agent's probe unchanged, 34 new: the layout and the joined path).
New in `picks_auto.mjs`, on a second demo project `picks-join`: **layout** at 1280x720 and at 1920x1080, each: no horizontal scroll bar on the page or on any column, the top bar and the agent's bar above the body with their button, the four columns each at least 220 px wide and 150 px high with the box's field and send button on the screen, the body ends above the bottom of the screen (screenshots `.scratch/stages_ui/shots/picks_auto-08-layout-*.png`);
**joined path**: a request "thêm một tấm bản đồ Bruges cho dòng này" on line 4 ends as `escalate` with nothing written; the card says "Cần làm kỹ hơn" and has "Để agent chọn hình" (primary, title says minutes) then "Tìm hình bằng tay"; the button turns the card into a running one (path `agent`, the lines of the request, a job of kind `picks` action `auto` for exactly that line with `redo`), names the part (1/4), the bar of the page shows the same job locked with Dừng, the box's field and send are locked;
a box turn sent meanwhile is 409 `agent_job_running` / `retry` `later` / the job's id and records nothing, the page's sentence for it is the Vietnamese one, a second agent start is refused; the card ends `applied` with "Agent đã chọn hình cho 1/1 đoạn.", the sentence of what was written for line 4, no "Hoàn tác" of its own and the pointer to "Lịch sử thay đổi"; line 4 got its two pictures (a map and a clip) and only that line was written, the bar says the same sentence, every batch is by the agent, the fake agent was asked once for plan and once for choose, the box is free again, no leftovers or raw words (screenshots `09-join-escalate`, `10-join-running`, `11-join-result`).
Mistakes of my own probe steps, fixed (never relaxed): a regular expression written with a single backslash inside a template string (the first run failed one check for it), and the check of the horizontal scroll bar only looked at the page, not at the columns (the first screenshot at 1280 showed a scroll bar inside the line column; the check now covers each column, and `picks.css` was fixed).

## 8. What I could not verify

* No real model: how a real agent answers the briefing that now carries the owner's request from the box, whether Gemini or Opus look at the sheets, and how long a real hand-over takes are as unverified as in `FIX_c3_picks_agent.md` section 13. The box's wording change in `FAST.template.md` is not measured with a real model.
* The card's own "Dừng" and "Thử lại" of a handed-over turn are tested through the server (a stopped turn and a failed one are handed over again, tests/picks) and by Node (the card data), not clicked in a browser; the probe cancels from the agent's bar (earlier steps) and lets the handed-over run end.
* The disabled state of "Để agent chọn hình" when the chosen agent cannot run (`agentUsable()`) is not seen in a browser (the mock agents are always usable), and neither is the quota card of a handed-over turn (Node and the server only).
* `tests/editor` on the final tree (see section 6).
* The layout was looked at in headless Chrome at the two sizes; no other browser, no zoom, no touch.
* `tests/library` was not run (the known failure on the server's stored data); the Windows form of `tools/bti.bat` and the Windows `.cmd` helpers of the agent are as in the earlier reports.
* The hand-over uses the agent chosen for the step; the route takes an optional `model` (as the others) but the page never sends one.
* The outputs of my runs (`join2_*.txt`) are in the session's scratchpad under `/private/tmp`; I left them there (the rule on deleting).

# Round two: the automatic run and the bench joined with the pictures agent and the prompt boxes

Worker `join2`, same worktree, after the coordinator merged the fourth build (`c6auto`, commit 2d29f93). Brief: the coordinator's message of round two; input: `docs/qa/FIX_c6_auto.md`
(especially "What the coordinator must add when the other two builds are joined"). Same rules: no git command that writes, no model, no `.env`, the deletion rule. The merge left
`docs/AGENT_API.md` at this branch's side; it had lost the whole c6 section (and with it the markers of its generated table, so `python -m bti.editor.hints` failed): the section is back as
**section 9** (sections 7 and 8 are the pictures agent and the prompt box), `AGENTS.md` and `jobs` point to it.

## R1. The run meets the pictures agent and the boxes

* **`picks.auto` is taken by the run with no change of its loop.** It is an advancing action, the run takes the first one that is ready (the catalogue puts it before `picks.approve`), follows its job and then
  meets the picks gate by the owner's rule. Proof on real routes, the fake agent runner of tests/picks and the fake sources (`tests/auto/test_run_joined.py`, a project with an approved narration, the voice
  made and a main painting): `picks.auto` then `picks.approve` (`until: picks`), the batches are by `agent:mock`, the approval by `agent:auto`; a gate the owner did not allow stops right after the agent
  (`gate_not_allowed`, the agent's work kept); model spending not allowed stops before it (`spend_not_allowed`, the agent never asked). Its cost: `auto.run`'s `cost.about` has `picks (about 20 minutes)`.
  `picks.edit` (a person's own request, like `draft.edit`) is now in `RUN_MANUAL`, so the run's cost does not count it.
* **One agent job at a time, both ways.** While a run goes on, `picks.edit` and `draft.edit` have `no_running_job` in `needs` and their routes answer 409 `agent_job_running` (`retry` `later`, the run's `job_id`);
  a hand-started `picks.auto` (any actor but the run's) is refused the same way, and so is the hand-over of a box turn to the agent. The run itself must still start `picks.auto` through its own job: it names itself
  (`actor` `agent:auto`, `bti.auto.RUN_ACTOR`) in the body, which the example body of `picks.auto` now has a place for (`actor`, as the operations' examples do); the route takes the actor (`actor_of`) and
  `bti.picks.auto.start(..., by_run=True)` ignores the run's own job. The plain draft start ignores it too (the run takes the draft). The sentence of `agent_job_running` now says "chọn hình, sửa bằng lời, dựng bản nháp hoặc chạy tự động"
  (`bti/draft/run.py` VI, `bti/picks/auto/texts.py`, `errmsg.js`, one text). The other way round, a job that is not the run's (a box turn, the pictures agent, a voice) ends the run as `busy_elsewhere` (`reasons.JOB_KIND_VI`
  says `draft` as "dựng hình hoặc sửa bằng lời"), a refusal `agent_job_running` of a call the run made is read as `busy_elsewhere` too (`loop.BUSY_CODES`), and `POST .../auto/run` is refused (`longjob_running`) while such a job runs.
  Honest limit: the state answer keeps `picks.auto` ready while a run goes on (the run reads the same answer and takes it); only the route tells another caller no.
* **Needs and warnings.** `reasons.NEED_VI` has a phrase for every word of `NEEDS` (a test already compares them; `no_running_job` now names the four kinds of job). Every warning code the picks document and the storyboard can give
  (`tests/auto/test_run_joined.py` scans the sources: dict literals with `level` `warn`/`warning`, the engine's `warn(path, message, code)` calls, and the `(warning)` codes of `ISSUE_CODES`) is in `STOPS` or `TOLERATED`
  of `bti/auto_run/checks.py`: nothing was unsorted (`asset_flag`, `beat_unknown`, `beat_no_pick` and the storyboard's were all there); the test fails the day a new one is not.

## R2. Two changes of the quality bar (the owner's statements)

* `asset_flag` is in `TOLERATED["picks"]`: a flagged picture never stops the run (copyright is not a blocker; a picture from the owner's books always carries "unknown"; a small one is no reason either). Its count is in the run log
  (the step's `note` `tolerated warnings: asset_flag x3` and `tolerated: [{code, count}]`) and in the result (`tolerated`, with a line in `detail`).
* `beat_no_pick` stops the run only when MORE than a quarter of the narration's lines have no picture (`checks.NO_PICK_LIMIT` 0.25, `SHARE_LIMITS`; the number of lines is `narration.beat_ids` of `GET .../picks`; unknown or zero: it stops).
  At or below a quarter the run goes on (the draft shows the main painting there) and says how many lines have none: the step's `tolerated`, the result's `tolerated` and `lines_without_pick`, and one more sentence at the end of
  `result.sentence` for every end (`Xong: video đã được xuất. Có 3 dòng lời dẫn không có hình riêng: bản nháp dùng tranh chính ở các dòng đó.`, also after a later stop at another gate). Tests on both sides of the threshold
  (12 lines with 3 / 4 without, 4 with 1 / 2, 8 with 2 / 3, 100 with 25 / 26, 1 with 1, no number of lines), flags alone, flags with a real stop, an error, `beat_unknown`, a warning nobody sorted.
* Words: `docs/AGENT_API.md` section 9 (the rule, the keys of the result, the generated table says "only when more than 25% of the lines have it"), `docs/APP_GUIDE.md` section 13 and 14 (Vietnamese), `AGENTS.md` ("Running by itself"),
  `skills/picks/SKILL.md`; the page's own fixture (`tests/editor_frontend/fixtures/autorun_results.json`, from `reasons.samples()`) was written again because its sample warning list used `asset_flag` as a stopping warning.

## R3. The bench meets the real routes

* The three drivers needed no new call: `drive_edit_storyboard` reads the turn of `GET .../draft/thread` (`status`, `summary`, `error`; the thread answers `{turns, active_job_id}`), `drive_edit_picks` the job result of `picks.edit`
  (`status`, `summary`) and `drive_picks_agent` the job of `picks.auto` (its body has `actor`, so the bench puts `agent:eval` there). One change was needed: a request the typed-operations boxes cannot do ends as `no_change` (the model said
  `cannot`, nothing written) or `escalate`, so `edit.answered_cannot` accepts `cannot`, `no_change`, `escalate` (it did not accept `no_change`), and for the picks it compares the picks document (it compared shots, which the picks do not have).
  `runner.BRIEFINGS` now hashes `skills/picks_edit/FAST.template.md` and the two `skills/picks_auto/*.template.md` (it was `[]`), so `compare` sees a changed briefing of the two picks steps.
* `tests/evals/test_joined_routes.py`: the joined app (real engine), the mock model answering each request of the nine cases the way a careful agent would (from the briefings' own data), the fake runner of the pictures agent, fake sources; a samples folder with the
  fixture project of tests/ops as `arnolfini` and a project with an approved narration and a main painting as `arnolfini-from-books`. **All nine cases run and are scored, none is skipped**: `edit_storyboard` (cannot, ring of light, zoom slower),
  `edit_picks` (impossible, reuse the main painting, skip a line), `picks_agent` (decides every line, credits, variety; the last two fail some criteria on the fake agent's four pictures and a main painting with no licence: scored, not skipped).
  **The cases that need a narration in the sample stay skipped with their sentence when the sample has none: today that is the repository's own sample `arnolfini-from-books` (an outline, no `script/narration.json`)**: the three cases of `edit_picks`
  and the three of `picks_agent` are skipped with "the sample project arnolfini-from-books has no script/narration.json: the pictures step needs a project with an approved narration" (a test proves it on a copy of the real sample);
  with a narration but no main painting they are skipped with "the action picks.auto is listed but not ready: it needs main_asset". The three cases of `edit_storyboard` use `projects/arnolfini` (a storyboard, an old import) and are not blocked by this.
  The ten `draft` cases still skip on that sample ("the timing of the sample has no beat ids"): not part of this round.

## R4. Documents

`python -m bti.editor.hints` (docs/AGENT_API.md: the `picks.auto`, `picks.edit`, `draft.edit` rows, the `no_running_job` text, section 9 with its generated reasons and quality-bar table), `python -m bti.cli.docgen` (the lists of `AGENTS.md` and `skills/*/SKILL.md`: nothing
stale), `python -m bti.ops.doc --check` and both `--check` modes: up to date. Hand-written: `docs/AGENT_API.md` sections 8 and 9, `docs/APP_GUIDE.md`, `AGENTS.md`, `skills/picks/SKILL.md`.

## R5. Files touched in round two

Code: `bti/auto.py`, `bti/auto_run/{checks,loop,reasons}.py`, `bti/draft/run.py`, `bti/picks/auto/{job,texts}.py`, `bti/editor/{picks_api,state_api,hints}.py`, `bti/editor/static/js/errmsg.js`, `bti/evals/{criteria,driver,runner}.py`.
Documents: `AGENTS.md`, `docs/AGENT_API.md`, `docs/APP_GUIDE.md`, `skills/picks/SKILL.md`, this report. Tests: new `tests/auto/test_run_joined.py` and `tests/auto/picks_agent.py` (the fake agent of tests/picks under another module name), `tests/evals/test_joined_routes.py`;
changed `tests/auto/test_run_api.py` (the picks step now waits first for a main painting, the pictures agent's own need), `tests/picks/test_auto_api.py` (the example body has an `actor`), `tests/evals/test_bench.py` (the skip sentence),
`tests/editor_frontend/fixtures/autorun_results.json`. `.scratch/agy_tasks/join2/STATUS.md`.

## R6. Checks of round two: what ran and what is owed

**Ran (Mac):** `python -m bti.editor.hints`, `python -m bti.cli.docgen`, `python -m bti.ops.doc --check`, both `--check` modes (up to date); `python -m bti.auto_run.reasons --write tests/editor_frontend/fixtures/autorun_results.json`;
the Node command: `ℹ tests 393`, `ℹ pass 392`, `ℹ fail 0`, `ℹ skipped 1`; every changed Python file parses; the pure functions of the quality bar were looked at on the threshold (12 lines with 3 pass, with 4 stop; 4 with 1 pass, with 2 stop; 8 with 2 pass, with 3 stop; 100 with 25 pass, with 26 stop; no number of lines stops).
**Not run: every Python folder and both browser probes.** The server (`ssh winbox-cmd`, 100.74.19.84) has not answered since about 07:22 on 2026-11-19; round two is edited and committed without a single Python test run on its final tree.
Owed, in this order, one folder per run on snapshot `join2`: `tests/state`, `tests/cli`, `tests/auto`, `tests/evals`, `tests/ops`, `tests/picks`, `tests/draft`, `tests/editor`, `tests/script`, `tests/media`, `tests/longjob`, `tests/settings`;
then `BTI_SSH_HOST=winbox-cmd node tests/e2e/box/box.mjs` (port 8571, suffix `c2box`) and `BTI_SSH_HOST=winbox-cmd node tests/e2e/picks_auto/picks_auto.mjs` (port 8577, suffix `c3p`), each stopped afterwards (check that nothing of the round-one probes still listens on those ports first).
The new tests (`tests/auto/test_run_joined.py`, `tests/evals/test_joined_routes.py`) and the changed ones were written without being run: expect first-run corrections in them (see the list in the final message of round two).


## R7. Round two on the server (after the coordinator's run of the commit 2bf0b20)

The coordinator ran every folder on a fresh snapshot: eleven were green and `tests/auto` did not start. **Cause:** `tests/picks/auto_helpers.py` (the pictures agent's fake runner, brought in by the merge of c3) and `tests/auto/auto_helpers.py` (the fake pipeline of the automatic run, c6) had one module name; the
conftest of `tests/auto` puts `tests/picks` in front of the import path, so `from auto_helpers import AppTransport, World` found the other file (and in one session a module cached under that name would be wrong for the other folder). **Fix:** the helper of `tests/auto` is renamed
`tests/auto/run_helpers.py` (a unique name; imports changed in `conftest.py`, `test_live.py`, `test_loop.py`, `test_run_api.py`, `test_run_command.py`, `test_run_joined.py`); nothing in `tests/picks` was renamed; `tests/auto/picks_agent.py` loads the picks helper by its path under its own module name.
One test of `tests/auto/test_run_command.py` also followed the join (the run's `nothing_to_do` at the picks step now waits for `main_asset` of `picks.auto`, not for `picks`) and was changed. No app code was changed in this step.
