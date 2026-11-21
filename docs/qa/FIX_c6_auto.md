# FIX c6auto: "Chạy tự động" (the automatic run through the gates) and the bench for the agents

Worker `c6auto`, worktree `.worktrees/c6auto` (branch `wt/c6auto`), 2026-11-19. Brief: `.scratch/agy_tasks/c6auto/TASK.md`. Every Python test ran on the server through `snapshot_test.sh c6auto`; the Node tests ran on the
Mac. No model, no `agy`, no `claude`, no port 8560, no `.env`, no git write. The bench was never run against a real agent.

## What was built

| part | files |
|---|---|
| the run | `bti/auto_run/` (`loop.py` the loop, `checks.py` the quality bar, `reasons.py` every end with its sentences, `runlog.py` the run log, `job.py` the long job, `api.py` the routes), mounted at the end of `bti/editor/auto_api.py` |
| the state answer | `bti/editor/state_api.py` (`auto.run`, `auto.cancel`, the cost of the run), `bti/editor/hints.py` (3 codes, a generated part), `bti/auto.py` (a docstring) |
| the command | `bti run` in `bti/cli/main.py`, `auto_not_enabled` in `bti/cli/exitcodes.py`; `AGENTS.md`, `skills/export/SKILL.md` and `docs/AGENT_API.md` regenerated, a short hand-written part in `AGENTS.md`, section 7 in `docs/AGENT_API.md` |
| the page | `autologic.js` (pure), `autoswitch.js` (the button, the bar), blocks marked `c6auto` in `labels.js`, `errmsg.js` and `css/shell.css`; Node test `tests/editor_frontend/autorun.test.mjs` with `tests/editor_frontend/fixtures/autorun_results.json` |
| the bench | `bti/evals/` (`cases.py`, `criteria.py`, `samples.py`, `driver.py`, `runner.py`, `report.py`, `cli.py`), 39 case files in `evals/cases/<step>/` |
| documents | `docs/APP_GUIDE.md` sections 13 (Vietnamese, for the owner) and 14 (the bench), this report |
| tests | `tests/auto/` (155), `tests/evals/` (56) |

## A. The automatic run

### The loop's rule (five lines)

1. Read `GET .../state`. Stop when the project is exported (or the `until` step is done), when automatic running was turned off, or when a job that is not the run's runs on the project.
2. Take the FIRST action with `ready` and `advances`; never another, no operation batches of its own, no edits. The state answer decides what advancing means (a test adds a fake advancing action and the run takes it).
3. Allowed? A gate only when its `auto_ok` is true (and the owner's `gates` agree); a cost only when its kind is allowed in `spend`; a paid action never; `storyboard.restore` never.
4. Before a gate read its document and apply the quality bar; then call the action exactly as the answer describes it (its method, path and body), as the actor `agent:auto`.
5. If the call answers a job, follow it to its end (a failed job ends the run with the job's code and sentence), then read the state again. Every step is written to the run log.

### Which warnings stop the run before each gate, and why

An error-level issue always stops it (`quality_error`; the approval routes refuse those anyway, the run looks first so nothing is sent). A warning stops it when it is in the first list of its gate, passes
when it is in the second (and stays in the log), and **a warning in neither list stops it** (somebody added a check; the owner looks at it until it is sorted). `info` is never looked at. The storyboard says
`warn`, the script documents say `warning`: both count. The lists are `bti/auto_run/checks.py` (STOPS and TOLERATED), the table in `docs/AGENT_API.md` section 7 is generated from them, and a test reads the source
of the checks to prove that every code in the lists is a code a check really makes.

| gate | stops the run | why | lets through |
|---|---|---|---|
| `outline` | `fact_no_source`, `unknown_source_id`, `source_excluded`, `unknown_fact`, `disputed_no_conflict` | substance: a fact nothing in the books backs, a source that is not in the brief or that the owner excluded, a chapter on a fact that is not in the table, a disputed fact whose conflict is not told (the narration would state it as certain) | `fact_unused`, `no_hook_choice`, `budget_sum` |
| `narration` | `words_off_target`, `unknown_fact` | the length is the product's promise (a 10+ minute video) and the voice that follows is about an hour; a line may not cite a fact the outline does not have | `spoken_chars`, `beat_too_long`, `long_sentence`, `no_show`, `chapter_off_budget` |
| `picks` | `beat_no_pick`, `asset_flag`, `beat_unknown` | a line with no picture (the brief's own example), a flagged picture (size, licence), a picture on a line that is not in the narration any more | none |
| `storyboard` | `audio_missing`, `asset_size_mismatch`, `first_shot_late`, `label_without_position`, `end_after_audio`, `canvas_not_1080p`, `map_view_coarse`, `identity_technique_mismatch`, `incomplete` | the export (25 minutes) would be wrong: no voice, camera keys in the wrong space, a start that is not covered, a label that is not drawn, a video longer than the voice, a wrong canvas, a map with no detail, a title that does not follow the identity | `project_name_differs`, `unknown_source`, `unknown_intent`, `first_shot_transition` |

The storyboard's "a shot that cannot draw" is checked by the approval route itself (it draws small frames; `422 undrawable`); the run reads that refusal as a stop for the owner (`gate_refused`), nothing is written.

### Every end, with its Vietnamese sentence

Six outcomes: `done`, `needs_owner`, `failed`, `nothing_to_do`, `cancelled`, `limit`. The sentence below is `result.sentence`, the one the page shows; `detail` and `fix` (English, for an agent) are in `bti/auto_run/reasons.py` and in
`docs/AGENT_API.md` section 7. A failed step is said on the page with the page's own sentence of its code (`errmsg.js`), here shown with the server's fallback.

| reason | outcome | the sentence the owner reads (with a typical case) |
|---|---|---|
| `exported` | done | Xong: video đã được xuất. |
| `until_reached` | done | Đã chạy xong bước "Giọng đọc", như bạn yêu cầu. |
| `gate_not_allowed` | needs_owner | Dừng trước cổng duyệt lời dẫn: bạn chưa cho agent tự duyệt cổng này. Hãy duyệt ở bước "Kịch bản", hoặc cho phép cổng này trong "Cho agent tự chạy dự án này" rồi bấm "Chạy tự động" lại. |
| `auto_turned_off` | needs_owner | Dừng vì "Cho agent tự chạy dự án này" đã bị tắt. Bật lại rồi bấm "Chạy tự động" để làm tiếp. |
| `spend_not_allowed` | needs_owner | Dừng trước việc "Tạo giọng đọc": bạn không cho agent tự làm loại việc này (chiếm máy chủ rất lâu). Hãy bấm việc đó ở bước "Giọng đọc". |
| `paid_needs_owner` | needs_owner | Dừng trước việc "Gợi ý hình (tốn tiền)" vì nó tốn tiền. Việc tốn tiền luôn cần bạn: hãy làm ở bước "Chọn hình" nếu bạn muốn. |
| `quality_warning` | needs_owner | Dừng trước cổng duyệt chọn hình: có dòng lời dẫn chưa có hình, và còn 1 điều nữa. Xem ở bước "Chọn hình", sửa rồi bấm "Chạy tự động" lại, hoặc tự duyệt nếu bạn thấy ổn. |
| `quality_error` | needs_owner | Dừng trước cổng duyệt dàn ý: còn 1 lỗi chưa sửa. Hãy sửa ở bước "Kịch bản" rồi bấm "Chạy tự động" lại. |
| `gate_refused` | needs_owner | Cổng duyệt storyboard từ chối vì có cảnh không vẽ được. Hãy xem ở bước "Dựng hình" rồi bấm "Chạy tự động" lại. |
| `repair_needed` | needs_owner | Dừng vì storyboard bị hỏng. Hãy xem ở bước "Dựng hình" và khôi phục bản gần nhất rồi bấm "Chạy tự động" lại. |
| `nothing_to_do` | nothing_to_do | Chưa có việc nào để chạy: dự án đang chờ bạn chọn tranh chính. Làm việc đó ở bước "Chọn hình" rồi bấm "Chạy tự động" lại. |
| `busy_elsewhere` | nothing_to_do | Dự án đang có việc khác chạy (giọng đọc). Chờ nó xong rồi bấm "Chạy tự động" lại. |
| `needs_content` | nothing_to_do | Việc "Để agent chọn hình" cần nội dung do bạn đưa vào. Làm ở bước "Chọn hình" rồi bấm "Chạy tự động" lại. |
| `action_failed` | failed | Việc "Tạo giọng đọc" không làm được: (mã voice_not_configured) this machine has no voice worker configured. |
| `job_failed` | failed | Việc "Tạo giọng đọc" chạy không xong: Máy đọc giọng bị lỗi. |
| `unreachable` | failed | Không gọi được máy chủ của ứng dụng: Connection refused. Hãy kiểm tra rồi bấm "Chạy tự động" lại. |
| `no_progress` | failed | Việc "Áp dụng" đã chạy xong 2 lần mà dự án vẫn như cũ, nên dừng lại để khỏi lặp mãi. Hãy xem bước "Dựng hình". |
| `internal_error` | failed | Chạy tự động gặp lỗi bất ngờ: KeyError: 'x'. Hãy báo cho người quản lý máy. |
| `cancelled` | cancelled | Đã dừng theo yêu cầu của bạn. Bấm "Chạy tự động" để làm tiếp; phần đã xong được giữ lại. |
| `job_cancelled_elsewhere` | cancelled | Việc "Tạo giọng đọc" đã bị dừng ở nơi khác nên chạy tự động cũng dừng. Bấm "Chạy tự động" để làm tiếp. |
| `step_limit` | limit | Đã làm 40 việc, hết số việc tối đa của một lần chạy. Bấm "Chạy tự động" để làm tiếp. |
| `time_limit` | limit | Đã chạy quá 12 giờ trong một lần nên dừng. Bấm "Chạy tự động" để làm tiếp. |

The job's `meta.result` always holds the result; a run that fails ends its job as `error` with the failed action's code as `error_code` and the sentence as `error`; every other end is a normal end of the job (`done`),
a cancel is the runner's own (`cancelled`). `GET /api/projects/{pid}/auto/runs` lists the runs (newest first, `state` running or finished, `live` while it runs); `.../runs/{run_id}` is the whole record.

### The state answer, the command, the page

* `auto.run` (`POST /api/projects/{pid}/auto/run`, body `{until: null, max_steps: 40}`) is listed while the switch is on and nothing is exported; ready unless a job of the project runs; never `advances`; its `cost` is the SUM of what it may start from where
  the project stands and only of the kinds the owner allowed (`kind` machine_time if any, else model; `kinds` lists them; `null` when it may start nothing that costs). `auto.cancel` is listed while a run goes on. The jobs list shows kind `auto`.
* `bti run <project> [--until STEP] [--max-steps N] [--wait] [--yes-cost]`: exit 0 done; 3 the owner is needed (`needs_owner`, `nothing_to_do`, and `auto_not_enabled` when the switch is off); 4 or 5 (by the code of what failed, like `bti do`) when a step failed; 5 cancelled or a limit.
  It needs `--yes-cost` like every action with a cost.
* The page: a button "Chạy tự động" next to "Agent tự chạy" (disabled while the switch is off or a run goes on), under the stepper a bar "Đang chạy tự động: Giọng đọc (3/6)" with "Dừng" and, at the end, "<heading>: <sentence>" with a link "Mở bước ..." and "Đóng". The page
  polls `GET .../auto/runs?limit=1` every 3 seconds while a run goes on and asks the shell to read the pipeline again when the run moves on.

## B. The bench (`python -m bti.evals`)

### The case format

One JSON file per case in `evals/cases/<step>/<name>.json` (the name is the file name):

```json
{"schema": "bti.eval.case/1", "name": "outline-chapter-count", "step": "outline", "title": "...", "why": "where the criteria come from",
 "sample": {"project": "arnolfini-from-books", "start": "book"},
 "request": {},
 "criteria": [{"id": "chapters", "kind": "outline.chapters_between", "min": 5, "max": 9}]}
```

`step`: outline | narration | draft | edit_storyboard | edit_picks | picks_agent. `sample.start` (`bti/evals/samples.py`): `book`, `outline_approved`, `narration_approved`, `as_is`, `as_is_locked`, `redraft`. `request` per step
(`bti/evals/driver.py`): outline `{options, body}` (PUT brief/options, POST outline/generate), narration `{body}`, draft `{body: {chapters}, apply}`, edit_storyboard `{instruction, scope: {shots}|{chapter}|{all}, mode}`,
edit_picks `{action, instruction, scope: {beats}}`, picks_agent `{action, body}`. A criterion is `{id, kind, ...parameters}`; `python -m bti.evals list --criteria` lists the 47 kinds with their parameters and what each needs. A case file with a mistake
is refused with a sentence that names the file. The criteria read documents the driver reads back through GET routes (`outline`, `brief`, `narration`, `storyboard` with its resolved times, `timing`, `picks`, `before`, `after`, `answer`), never the project folder.

### A run

`python -m bti.evals run --step S --agent ID --repeat 3 [--case NAME ...] [--url URL] [--samples-root DIR] [--projects-root DIR] [--out DIR] [--keep] --yes-cost`. For every case and repeat it copies the sample project into the projects root of the app
(`eval-<run>-<case>-<n>`; `protected` is dropped from the copy), puts the copy at the start state (the gates through the app's own routes as the actor `agent:eval`), points the copy's agent at the one asked for, drives the step through the routes a person's buttons
call, reads the documents back, checks every criterion, and removes the copy through `DELETE /api/projects/{pid}?confirm={pid}` (only copies it made itself). The sample is hashed before and after and the run records that it did not change.
It records per repeat each criterion with its measured value, the seconds, the agent and model (as the project resolves them), the jobs, any error; per run the briefing's hash (sha1 of the prompt files of the step), the app and the command. Files: `<out>/<run id>.json`,
`<out>/<run id>/<case>-<n>.json` (the outputs), `<out>/<run id>.md` (the summary); `--out` defaults to `.scratch/evals`. A repeat passes only when every criterion passes and the driver had no error. A repeat that cannot run (the sample or the app cannot do it yet) is
**skipped** with a sentence and is in no count. `compare A B` shows the agent, model and briefing that changed, and for every case the repeats that passed and the criteria whose rate moved.

### The cases (39)

| case | sample / start | what it checks | criteria |
|---|---|---|---|
| `draft-closing-chapter` | `arnolfini/redraft` | The closing chapter (c08) is drafted alone without error | no-errors (`draft.no_error_issues`); reasons (`draft.every_shot_has_a_reason` min_share=0.9) |
| `draft-cold-open` | `arnolfini/redraft` | The cold open (chapter c01) is paced and complete | no-errors (`draft.no_error_issues`); pace (`draft.shot_pace` median_min=4.0 median_max=9.0 shortest=1.5 longest=30.0 max_share_under_4=0.35) |
| `draft-context-lines-leave-the-main-painting` | `arnolfini/redraft` | A shot about a person, a place or another work does not show the main painting | context (`draft.context_lines_avoid_the_main_painting`) |
| `draft-every-shot-has-a-reason` | `arnolfini/redraft` | Every shot has a note that says why | notes (`draft.every_shot_has_a_reason` min_share=0.9) |
| `draft-no-subtitles` | `arnolfini/redraft` | No sentence of the narration is put on screen as text | no-subtitles (`draft.no_narration_on_screen` run=5) |
| `draft-pace-seven-seconds` | `arnolfini/redraft` | About one shot every seven seconds | pace (`draft.shot_pace` median_min=5.0 median_max=9.0 shortest=1.5 longest=30.0 max_share_under_4=0.25) |
| `draft-redraft-keeps-locked-shots` | `arnolfini/as_is_locked` | A re-draft leaves the shots the owner locked exactly as they are | locked (`draft.locked_shots_unchanged`); no-errors (`draft.no_error_issues`) |
| `draft-technique-variety` | `arnolfini/redraft` | At least six different techniques, mostly the channel's core ones | variety (`draft.distinct_techniques_at_least` k=6); core (`draft.core_techniques` min_share=0.6) |
| `draft-uses-the-owners-picks` | `arnolfini/redraft` | A line the owner picked a picture for shows it | picks (`draft.picks_are_used` min_share=0.8) |
| `draft-whole-video-no-errors` | `arnolfini/redraft` | The draft is a storyboard the engine accepts and that covers the whole narration | no-errors (`draft.no_error_issues`); covers (`draft.covers_the_narration` slack=0.25) |
| `edit-picks-asks-for-something-impossible` | `arnolfini-from-books/narration_approved` | A request the project cannot do is answered `cannot` with a reason and nothing changes | cannot (`edit.answered_cannot`); scope (`picks.only_scope_changed` beats=[]) |
| `edit-picks-reuse-the-main-painting` | `arnolfini-from-books/narration_approved` | "Use the main painting here" changes only that line | scope (`picks.only_scope_changed` beats=['b0004']); changed (`picks.changed_in_scope` beats=['b0004']); no-errors (`picks.no_error_issues`) |
| `edit-picks-skip-a-line` | `arnolfini-from-books/narration_approved` | "No picture needed here" marks that line skip and nothing else | scope (`picks.only_scope_changed` beats=['b0006']); changed (`picks.changed_in_scope` beats=['b0006']); no-errors (`picks.no_error_issues`) |
| `edit-add-a-ring-of-light` | `arnolfini/as_is` | "Add a ring of light" adds an overlay in scope and leaves the rest alone | scope (`edit.only_scope_changed`); overlays (`edit.metric_moved` metric=overlay_count direction=increase); no-errors (`edit.no_error_issues`) |
| `edit-asks-for-a-picture-the-project-lacks` | `arnolfini/as_is` | A request that needs a new painting is answered `cannot` with a reason and nothing changes | cannot (`edit.answered_cannot`); scope (`edit.only_scope_changed`) |
| `edit-zoom-slower` | `arnolfini/as_is` | "Zoom slower" changes only the shots in scope and makes the zoom slower | scope (`edit.only_scope_changed`); changed (`edit.changed_something_in_scope`); slower (`edit.metric_moved` metric=zoom_rate direction=decrease); no-errors (`edit.no_error_issues`) |
| `narration-chapters-near-budget` | `arnolfini-from-books/outline_approved` | Every chapter is as long as its budget, within 30% | budgets (`narration.chapter_budgets` tolerance=0.3) |
| `narration-facts-come-from-the-outline` | `arnolfini-from-books/outline_approved` | Every fact a line cites is in the outline | facts (`narration.facts_in_outline`) |
| `narration-is-not-copied-from-the-books` | `arnolfini-from-books/outline_approved` | Not many words are runs copied from the books | copied (`narration.copied_runs_at_most` max_share=0.25) |
| `narration-length-within-target` | `arnolfini-from-books/outline_approved` | The narration is as long as the outline's target | length (`narration.words_within_target` tolerance=0.15) |
| `narration-lines-say-what-is-shown` | `arnolfini-from-books/outline_approved` | Every line says what is on screen | show (`narration.every_beat_has_show`) |
| `narration-no-errors-and-the-outline-chapters` | `arnolfini-from-books/outline_approved` | No error, and exactly the outline's chapters in its order | no-errors (`narration.no_error_issues`); chapters (`narration.chapters_match_outline`) |
| `narration-no-long-lines` | `arnolfini-from-books/outline_approved` | No line is longer than 90 words | lines (`narration.max_beat_words` max=90) |
| `narration-short-sentences` | `arnolfini-from-books/outline_approved` | Sentences are short enough to be spoken | longest (`narration.max_sentence_words` max=28); median (`narration.median_sentence_words` min=8 max=22) |
| `narration-spoken-words-only` | `arnolfini-from-books/outline_approved` | Nothing a voice cannot say | spoken (`narration.spoken_words_only`) |
| `narration-ten-minutes-at-least` | `arnolfini-from-books/outline_approved` | Read aloud it lasts at least ten minutes | minutes (`narration.minutes_at_least` minutes=10) |
| `outline-budget-matches-target` | `arnolfini-from-books/book` | The chapter budgets add up to the target of words | budget (`outline.budget_near_target` tolerance=0.15); each-chapter (`outline.chapter_budget_between` min=80 max=450) |
| `outline-chapter-count` | `arnolfini-from-books/book` | The outline has five to nine chapters | chapters (`outline.chapters_between` min=5 max=9) |
| `outline-disputes-are-flagged` | `arnolfini-from-books/book` | Every disputed fact says what the sources disagree about | conflicts (`outline.disputed_facts_have_conflict`) |
| `outline-every-chapter-cites-the-dossier` | `arnolfini-from-books/book` | Every chapter rests on facts that cite paragraphs of the dossier | chapters-cite (`outline.every_chapter_cites_a_source`) |
| `outline-facts-have-real-sources` | `arnolfini-from-books/book` | Every fact cites only paragraphs that exist in the included sources | facts-sourced (`outline.facts_sourced` min_share=1.0); no-excluded (`outline.no_excluded_source`) |
| `outline-leaves-out-an-excluded-book` | `arnolfini-from-books/book` | A book the owner excluded is not cited | no-excluded (`outline.no_excluded_source`); facts-sourced (`outline.facts_sourced` min_share=1.0) |
| `outline-longer-video` | `arnolfini-from-books/book` | A target of 3000 words gives a longer outline with matching budgets | budget (`outline.budget_near_target` tolerance=0.15); chapters (`outline.chapters_between` min=6 max=12) |
| `outline-no-errors` | `arnolfini-from-books/book` | The outline passes the app's own checks | no-errors (`outline.no_error_issues`); few-warnings (`outline.warnings_at_most` max=3) |
| `outline-structure` | `arnolfini-from-books/book` | A cold open first, a closing last, and every fact used | roles (`outline.roles` first=cold_open last=closing); facts-used (`outline.facts_all_used` min_share=0.9) |
| `outline-thesis-and-hooks` | `arnolfini-from-books/book` | A thesis that is a question, three openings, one chosen | thesis-hooks (`outline.thesis_and_hooks` hooks=3) |
| `picks-agent-credits-every-picture` | `arnolfini-from-books/narration_approved` | Every picture it brings says where it came from, and none is flagged | credited (`picks.credited`); no-flags (`picks.no_flagged_picture`) |
| `picks-agent-decides-every-line` | `arnolfini-from-books/narration_approved` | Every line of the narration gets a picture or a skip, and the main painting is chosen | decided (`picks.every_beat_decided` min_share=0.95); main (`picks.main_painting_chosen`); no-errors (`picks.no_error_issues`) |
| `picks-agent-uses-variety` | `arnolfini-from-books/narration_approved` | The video is not one picture repeated: at least six different pictures | variety (`picks.variety_at_least` k=6); decided (`picks.every_beat_decided` min_share=0.9) |

Ten cases each for the outline, the narration and the draft; three each for the edit of the storyboard (against `POST .../draft/edit`, which exists here), the edit of the picks and the pictures agent (against the actions `picks.edit` and `picks.auto`, which do not exist here:
the drivers call an action of the state answer by its id and **skip** the repeat with "not joined yet" when the app does not list it).

### What the coordinator must add when the other two builds are joined

* **The pictures agent (`picks.auto`).** The run needs nothing: it is an advancing action and is taken (and counted in the cost of `auto.run`, by `run_cost`, as soon as it is a long job with a cost that is not paid). Check: (1) `python -m bti.editor.hints` and `python -m bti.cli.docgen`, then `tests/auto`,
  `tests/evals`, `tests/cli`, `tests/state`; (2) a new word in `needs` has no Vietnamese phrase in `reasons.NEED_VI` until it is added (a test fails and says which); (3) new warnings of the picks document go into `checks.STOPS["picks"]` or `TOLERATED["picks"]` (until then they stop the run); (4) the bench: `drive_picks_agent` calls the action named in
  the case (`picks.auto`), with its example body plus the case's `body` and the actor `agent:eval`: confirm the id, its fields and that it answers a `job_id`; the three `picks_agent` cases and `picks.*` criteria then run; (5) put an approved narration in the sample `arnolfini-from-books` (`script/narration.json`): the start `narration_approved` needs it.
* **The edit requests (the prompt box).** Step 5 is driven through `POST .../draft/edit` + `GET .../draft/thread` (the turn's `status` becomes `answer.code`: `applied`, `cannot`, `escalate`, `no_change`, `failed`): if the prompt-box build changes that contract (operations instead of a storyboard write, another answer for "cannot"), change `drive_edit_storyboard` and the codes of
  `edit.answered_cannot`. Step 4 is driven through the action `picks.edit` (fields `instruction`, `scope`, `base_rev` from its `body_template`): confirm the id and the fields, and the shape of its answer (`answer.code`, `reason`) in `drive_edit_picks`. The shot ids (`s0004`, `s0005`) of the three storyboard cases are those of `projects/arnolfini`; the beat ids (`b0004`, `b0006`) of the picks cases
  are guesses until a narration is in the sample.
* **A sample for the draft.** The ten `draft` cases use `arnolfini/redraft`: that project is an old import whose timing beats have no ids, so today every repeat is SKIPPED with "the timing of the sample has no beat ids". Add a reference project made by the app (narration, voice with beat ids, approved picks) to `projects/` and change `sample.project` in the draft and picks case files (one line each).

### The first real run, and how many model calls each makes

Use a second instance of the app (its own port and projects folder, the way `tests/e2e/stages/launch.py` does), so that the copies never appear in the owner's projects folder; the agent quota first (`antigravity-quota.md`: the weekly quotas of `agy` were used up on 2026-11-18, they open again about 2026-11-24).

```
python -m bti.evals list
python -m bti.evals run --step outline --agent gemini --repeat 1 --case outline-chapter-count --url http://127.0.0.1:PORT --projects-root PATH_OF_THAT_INSTANCE_PROJECTS            # 1 agent call; prints the plan, exit 3, starts nothing
python -m bti.evals run --step outline --agent gemini --repeat 1 --case outline-chapter-count --url http://127.0.0.1:PORT --projects-root PATH --yes-cost                        # 1 call
python -m bti.evals run --step outline --agent gemini --repeat 3 --yes-cost --url ... --projects-root ...                                                                       # 10 cases x 3 = 30 calls
python -m bti.evals run --step narration --agent gemini --repeat 3 --yes-cost ...                                                                                                # 30 jobs of about 8 calls (one per chapter) = about 240 calls
python -m bti.evals run --step edit_storyboard --agent gemini --repeat 3 --yes-cost ...                                                                                          # 3 x 3 = 9 calls (fast path)
python -m bti.evals run --step draft --agent gemini --repeat 3 --yes-cost ...                                                                                                    # 10 x 3 = 30 agent sessions of about 20 minutes: skipped today (see above)
python -m bti.evals run --step edit_picks|picks_agent ...                                                                                                                         # 9 calls / 9 sessions; skipped until the builds are joined
python -m bti.evals compare RUN_A RUN_B
```

## Decisions where the brief was silent

1. **A job that is not the run's stops the run** (`busy_elsewhere`, outcome nothing to do); a preview render does not count. The start of a run is refused for the same jobs.
2. **`storyboard.restore` is never taken** (it is a repair, `advances`, but it puts an old copy over a damaged file: the owner's decision): `repair_needed`.
3. **Cancel stops the job the run started** too (the run asks the state's job route to cancel it), and starting again continues: the finished parts of voice and export are kept by the runner.
4. **Slices.** The runner kills a part after 35 minutes and the voice alone is about an hour, so the job is a row of 29 equal parts of 25 minutes (12 hours); each takes the loop over where the last stopped (a part that finds the run ended skips). The twelfth hour ends the run with `time_limit`. The job's `progress` is therefore not the run's: read `meta`
   (said in the docs). A cancel that arrives exactly between two parts leaves the job it started running and the run's log without an end: the list reports such a run from the state of its job. A per-part limit in the runner (`Part.limit_seconds`) would remove all of this: **Needs another worker** (`bti/longjob/manager.py`).
5. **`auto.run` is listed only while the switch is on** (or a run goes on) and nothing is exported, so that the nine exact lists of `tests/state` did not change; `step` is the step the project is at.
6. **The cost of `auto.run`** is computed from the catalogue: every long action with a cost, not paid, not a person's own request (`state_api.RUN_MANUAL`: `picks.import_clip`, `draft.edit`) whose step is not done, only of the allowed kinds; `kind` is machine_time when any, `kinds` is a new key.
7. **`bti run` needs `--yes-cost`** (the rule of the command), has `--max-steps`, and `auto_not_enabled` is a person code (exit 3). A refused start of the route is `409 auto_not_enabled`, `409 auto_running`, `409 longjob_running` / `script_job_running`.
8. **The actor** of the gates is `agent:auto`; the actor of the request that started the run (default `human`, `cli:NAME` from `bti`) is kept in the run log (`actor`).
9. **An unknown warning stops** (fail safe); the cosmetic ones pass; the lists above.
10. **A stale revision** is read again and retried up to three times; **the same call three times in a row without the state moving** ends the run as `no_progress`; a refusal by a gate route for the document (`undrawable`, `storyboard_incomplete`, `*_has_errors`) is `gate_refused` (the owner), not a failure.
11. **The run log** is `projects/<pid>/auto_runs/<run id>.json` (the newest 30 kept), rewritten after every step (a step is in the log before its call is made); one extra route `GET .../auto/runs/{run_id}`.
12. **Failed ends the job as `error`** with the action's code, so `bti job --wait` and the page's queue read it like any failed job; the page reads `meta.result` for every end.
13. **"(n/6)"** is the stepper's own number (`voice` is 3), not a count of finished steps; the example "(2/6)" of the brief was read as the format.
14. **The run calls the app over HTTP** at the address of the socket the request came in on (`request.scope["server"]`), through the command's own `HttpTransport`; `app.state.auto_transport` and `app.state.auto_options` are test seams.
15. **The page** reads the progress by polling every 3 seconds; the end bar is closed with "Đóng" (remembered per project in `localStorage`, guarded); the pipeline is refreshed by a dynamic `import('./app.js')` (the entry module, already loaded) because `app.js` is not in the files I may edit.
16. **Bench:** the output folder defaults to `.scratch/evals` (git-ignored); a repeat with a driver error is not a pass; the sample's own `script/outline.json` (a model-made outline) is the start of the narration cases; `redraft` builds an approved `picks.json` from the finished storyboard when the timing has beat ids; the bench acts as the owner on its own copy
    (it switches the copy's `auto.json` on to approve the start gates as `agent:eval`).
17. **The sentences of the ends are written once**, in `bti/auto_run/reasons.py`, and the page shows them as the server gives them (`result.sentence`); `labels.js` (block `c6auto`) has the page's own words (button, progress line, "Dừng", the heading and the link text, the fallbacks for a record without a sentence), `errmsg.js` the sentences of the new refusal codes and, through
    `describeHttp`, the sentence of a failed step. A Python test keeps `tests/editor_frontend/fixtures/autorun_results.json` equal to `reasons.samples()` (`python -m bti.auto_run.reasons --write tests/editor_frontend/fixtures/autorun_results.json` rewrites it) and the Node test reads that file, so the page and the server cannot drift.
18. **Existing files touched beyond the list:** `skills/export/SKILL.md` (a generated table), `tests/editor_frontend/fixtures/autorun_results.json` (new, the Node test's input, kept equal to the server's own list by a Python test).

## Tests

Python (snapshot `c6auto`, one folder per run, no `-m slow`), Node on the Mac. Lines as printed:

```
tests/auto       155 passed, 1 warning in 62.05s (0:01:02)
tests/evals      56 passed, 1 warning in 9.70s
tests/cli        119 passed, 1 warning in 42.53s
tests/state      277 passed, 1 warning in 156.03s (0:02:36)
tests/editor     481 passed, 1 warning in 231.59s (0:03:51)
tests/longjob    69 passed, 1 skipped, 1 warning in 12.30s
tests/script     262 passed, 7 skipped in 35.44s
tests/draft      358 passed, 1 warning in 136.52s (0:02:16)
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
ℹ tests 362
ℹ suites 0
ℹ pass 361
ℹ fail 0
ℹ cancelled 0
ℹ skipped 1
ℹ todo 0
```

The skipped Node test is `tests/editor_frontend/sbissues.test.mjs:135` (it needs `.venv/bin/python`, which the worktree does not have). The skipped Python tests are the ones the folders skip on their own. One earlier run of `tests/script` had
one failure, `test_claudecode.py::test_the_prompt_file_is_removed_after_a_normal_call_and_after_a_failure`: it lists the shared temporary folder of the server and found a prompt file of another worker's run; it passed alone and in the final run above (not mine).
`tests/auto` includes `test_live.py`: the run over real HTTP on an ephemeral port. The Python generators (`python -m bti.editor.hints --check`, `python -m bti.cli.docgen --check`) are clean.

## What I could not verify

* No browser: the button, the bar, the colours and the dynamic import of `app.js` were never seen; only the pure logic (Node, 12 tests) and the strings. The page was not tried against a real run.
* No real model, voice, draft or export was started, and the bench was never run against a real agent: the loop ran against fake long jobs (real jobs of the runner with quick parts) and the bench against the mock model and a fake app. The slices were tried with slices of a fraction of a second, not 25 minutes.
* The loop was proved over real HTTP on an ephemeral port (`tests/auto/test_live.py`), not against the owner's app on port 8560. `local_url` behind a proxy or on a unix socket was unit-tested only.
* The quality bar was tested on made-up documents and on the stub engine (whose warnings carry no code and so stop the run: the tests make the fake storyboard clean); no real storyboard of the real engine was judged. The lists were checked against the codes the checks make, not against a finished video.
* `docs/AGENT_API.md`, `AGENTS.md` and `skills/export/SKILL.md` were regenerated on the Mac with the standard generators (FastAPI 0.141 here, 0.163 on the server).
