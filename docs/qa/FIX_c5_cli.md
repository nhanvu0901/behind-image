# FIX c5cli: the command `bti`, the rule for who may approve a gate, and the documents an agent reads

Worker `c5cli`, worktree `.worktrees/c5cli` (branch `wt/c5cli`), 2026-11-19. Brief: `.scratch/agy_tasks/c5cli/TASK.md`. Nothing was run on the Mac except the standard-library docs
generators (`python -m bti.editor.hints`, `python -m bti.cli.docgen`: imports only, no test, no model) and the Node tests; every Python test ran on the server through
`snapshot_test.sh c5cli`. No model, no port 8560, no `.env`, no git write.

## What was built

| part | files |
|---|---|
| the command | `bti/cli/` (`main.py` the sub-commands, `exitcodes.py` the table, `render.py` the text, `transport.py` urllib and the swappable transport, `docgen.py` the generator of the documents' lists), `tools/bti`, `tools/bti.bat` |
| the rule | `bti/auto.py` (the document `auto.json`, the rule), `bti/editor/auto_api.py` (GET and PUT `/api/projects/{pid}/auto`, the check of the approval routes), small marked edits in `app.py`, `script_api.py`, `picks_api.py`, `state_api.py`, `hints.py` |
| where who is recorded | `bti/script/store.py`, `bti/picks/doc.py`, `bti/picks/service.py` (see decision 1) and `storyboard.json` through `app.py` |
| the switch on the page | `static/js/autologic.js` (pure), `autoswitch.js`, blocks in `labels.js`, `errmsg.js`, `app.js`, `index.html`, `css/shell.css` |
| documents | `AGENTS.md`, `skills/{script,voice,picks,storyboard,export}/SKILL.md`, a part in `docs/APP_GUIDE.md` (section 12, Vietnamese), `docs/WINDOWS.md`, `docs/AGENT_API.md` (hand-written parts and its generated parts) |
| tests | `tests/cli/` (own `conftest.py`, `cli_helpers.py`, `sessions.py`, `test_cli_commands.py`, `test_cli_exitcodes.py`, `test_cli_http.py`, `test_cli_docs.py`), `tests/state/test_auto.py`, `tests/editor_frontend/autologic.test.mjs`, two existing tests adjusted (`tests/state/test_state.py`, `test_errors.py`) |

## The sub-commands, with one real output each

All outputs below are real (from the test fixtures: the sample project `arn`, test doubles for the model, the voice and the export; the job ids and revisions are shown as `<job>`, `<rev>`).

`bti status` (no project) and `bti status <project>` (the rest of the long answer is cut at `...`):

```
$ bti status
projects (bti status <project> for one):
  arn                      script       The Arnolfini Portrait
$ bti status arn
project: arn   stage: script   current step: voice (Giọng đọc)
automatic running: off (an agent approves no gate; the owner approves on the page or turns it on there)
approvals: outline human; narration human; picks -; storyboard -
...
can do now:
  voice.generate          Tạo giọng đọc   [advances; costs machine_time (about 1 hour); needs --yes-cost; long job: add --wait]
  picks.search            Tìm hình
...
next: bti do arn voice.generate --yes-cost --wait   (Tạo giọng đọc)
```

`bti do` (a cost without `--yes-cost` is exit 3 with one line; with it the action runs; `--wait` follows the job, one line per change):

```
$ bti do arn voice.generate
a person is needed: cost_not_confirmed
  detail: voice.generate costs machine_time (about 1 hour).
  fix: Run it again with --yes-cost when the owner asked for this work.
(exit 3)
$ bti do arn voice.generate --yes-cost --wait
started job <job> (voice.generate)
job <job>: running 0%
job <job>: running 50% - Phần 1 (đang chạy)
job <job>: done 100%
done: {"fixture":"voice"}
$ bti do arn narration.generate        # a project at the start: not ready, refused with its needs (exit 4; pieces asserted by test_do_refuses_an_action_that_is_not_ready_with_its_needs)
refused: not_ready
  detail: The action narration.generate is not ready: it needs outline_approved.
  fix: outline_approved: The outline is not approved, or it changed after it was approved. Call outline.approve.
  needs: outline_approved
```

`bti approve` (refused by default, exit 3; after the owner turned automatic running on):

```
$ bti approve arn outline
a person is needed: gate_needs_human (HTTP 403)
  detail: The outline gate can only be approved by the owner: automatic running is off for this project.
  fix: Ask the owner to approve this gate on the page, or to turn automatic running on for this project and allow the gate (the switch on the page, PUT /api/projects/arn/auto), then call again.
(exit 3)
# owner: auto on
$ bti approve arn outline
approved outline as cli:bti
```

`bti ops` (dry run, then real; the command reads the revision itself), `bti changes`, `bti undo` (fixture `ops1`, picks):

```
$ bti ops ops1 picks --file ops.json --dry-run
dry run: nothing was written; 2 operation(s) applied; revision <rev>
changes:
  0:42   Đoạn 4: dùng lại tranh chính
  0:59   Đoạn 5: thay 1 hình
$ bti ops ops1 picks --file ops.json
batch batch_0001 written; 2 operation(s) applied; revision <rev>
changes:
  ...
undo: bti undo <project> batch_0001
$ bti changes ops1 picks
batch        doc         actor                 time                 note
batch_0001   picks       cli:bti               <time>
    0:42   Đoạn 4: dùng lại tranh chính
    0:59   Đoạn 5: thay 1 hình
$ bti undo ops1 batch_0001
undone batch_0001; the undo is batch batch_0002; revision <rev>
  0:42   Đoạn 4: trở lại như trước khi sửa
  0:59   Đoạn 5: trở lại như trước khi sửa
```

A refused batch (exit 4, the field and the fix printed) and a stale revision (exit 5) are in `tests/cli/test_cli_commands.py` (`test_ops_refused_is_exit_4_with_the_field_and_the_fix`, `test_ops_on_a_stale_revision_is_exit_5`):
`refused: unknown_shot (HTTP 422)` / `fix: Use a shot id from allowed ...` / `field ops[0].shot: ... (allowed: s0001 ...)`; `busy: stale_revision (HTTP 409)` / `current_rev: ...`.

`bti job` (view; `--wait` and `--cancel` as above; `--json` prints the server's record):

```
$ bti job <job>
job <job>: done 100%
done: {"fixture":"voice"}
```

`bti schema ops picks` (text; `--json` gives every JSON Schema), `bti doc voice` (prints `skills/voice/SKILL.md`; `bti doc` alone prints `AGENTS.md`, `bti doc edit` is `storyboard`; `--json` gives `{step, path, text}`):

```
$ bti schema ops picks
operations of the picks (send them with: bti ops <project> picks --file ops.json):
  set_main: Choose the main picture (the whole painting) of the video.
    required: asset
    example: {"op":"set_main","asset":"B"}
  ...
```

An error with `--json` is one JSON object of the command's own; the app not reachable is exit 6:

```
$ bti status nope --json
{"ok": false, "exit": 4, "exit_name": "refused", "code": "project_not_found", "detail": "project not found", "fix": "Take the project id from GET /api/projects.", "retry": "no", "status": 404}
$ bti status arn            # nothing listens
cannot reach the app: unreachable
  detail: Cannot reach the app: [Errno 61] Connection refused
  fix: Check that the app runs and that BTI_URL (or --url) is right; do not retry in a loop.
$ bti frobnicate
usage: argument command: invalid choice: 'frobnicate' (choose from status, do, approve, ops, job, undo, changes, schema, doc)
```

Options of every command: `--json`, `--actor NAME`, plus `--url`, `--timeout` (and `--interval`, `--max-wait` for `--wait`, `--limit` for `changes`).

## The exit codes (one table: `bti/cli/exitcodes.py`, printed in `AGENTS.md`)

| code | name | meaning |
|---|---|---|
| 0 | done | the command did what it was asked |
| 2 | usage | typed wrong: unknown sub-command, missing argument, an action id that does not exist, a bad `--set`, a bad file; nothing was sent |
| 3 | person_needed | a gate the agent may not approve, a cost not confirmed (`--yes-cost`) or not allowed, money, a sign-in |
| 4 | refused | the server refused (4xx) or a job failed: `code`, `fix`, `fields` printed |
| 5 | busy | a job of the kind runs, a stale revision, a service that answers `later`, a cancelled or interrupted job |
| 6 | unreachable | nothing answers, a broken connection, or the answer is not the app's JSON |

The mapping (first rule that matches): 2xx is 0; status 401 or 403, or a `code` in `gate_needs_human`, `auto_needs_human`, `spend_needs_human`, `confirm_required`, `agy_auth`,
`claude_auth`, `claude_outdated`, `real_models_off` is 3; `stale` or `stale_revision` is 5; `retry` `later` is 5; any other 4xx or 5xx JSON answer is 4; no answer or a non-JSON answer is 6.
A job that ends: `done` 0; `cancelled` and `interrupted` 5; `error` by its `error_code` through the same rules (the `retry` word from the server's hint table), a script job by its `error_kind`.

## The gate rule as built

* `projects/<pid>/auto.json` (`bti.auto/1`): `{enabled: false, gates: {outline, narration, picks, storyboard: true}, spend: {model: true, machine_time: true, paid: false}}` (the defaults; no file is the defaults).
  `GET /api/projects/{pid}/auto` answers `{schema, rev, enabled, gates, spend, warnings}`; `PUT` takes `{base_rev, enabled?, gates?, spend?}` (only the keys it names change), 409 `stale` with `current_rev`, 422 `invalid_field` with `fields`.
* The four approval routes (`outline/approve`, `narration/approve`, `picks/approve`, and `POST /api/projects/{pid}/approve` for the storyboard) take an optional `actor` in the body: `human` (the default: the page sends none and works unchanged),
  `agent:<model id>` or `cli:<name>` (the same forms the operations take; anything else is 422 `invalid_field`). The check is the first thing a route does after the project is known. An actor that is not `human` is refused with
  403 `gate_needs_human` (`gate`, `actor`, `reason` = `auto_off` or `gate_not_allowed`, `auto`; the `fix` says the owner approves on the page or turns automatic running on) unless `auto` is enabled and allows that gate. Nothing is written when refused.
* Who approved is recorded where the approval is stored: `approval.by` in `script/outline.json`, `script/narration.json` and `picks.json`; `approvals.storyboard.by` in `storyboard.json`. A change to the document drops the approval and its `by`.
  An approval made before this existed has no `by`.
* The state answer: top-level `auto` (`{enabled, gates, spend}`) and `approvals` (`{outline, narration, picks, storyboard}`, each `null` or `{by, at, stands}`); `auto_ok` of an action is: for a gate, enabled and allowed (so false by default); for an action with a `cost`,
  that kind of spending allowed (`paid` never, so `picks.suggest` is always false); true otherwise.
* The command: `bti approve` and `bti do <gate>.approve` send `actor` `cli:<name>`; a gate that is not ready and not allowed is exit 3 (the owner's decision comes first); `--yes-cost` cannot override a spend the owner did not allow (exit 3, nothing sent); `--actor human` is refused (exit 2).
* The page: a button "Agent tự chạy: tắt/bật" in the top bar (visible while a project is open) opens "Cho agent tự chạy dự án này": the switch, the four gates as checkboxes (disabled while the switch is off), the line "Việc tốn tiền luôn cần bạn."; every change is saved at once
  with the revision the page holds (one retry when stale), all words through `labels.js` (`AUTO_LABELS`) and `errmsg.js`.

## The documents and which parts are generated

`AGENTS.md` (one page, says at the top it is for an agent that operates a project and sends a code developer to `docs/`): generated parts `commands` (sub-commands and options), `exit_codes`, `exit_mapping`, `gates`.
`skills/<step>/SKILL.md` for script, voice, picks, storyboard, export: generated `actions` (the actions of the step, from `state_api.SPECS`), `ops` (picks and storyboard: the registry of `bti/ops`), `techniques` (storyboard: the registry's 12 headings with their 85 ids);
the goal, needs and gives, the worked session, what a good result is and the refusals are written by hand. `python -m bti.cli.docgen` rewrites the parts, `--check` fails when stale. `docs/AGENT_API.md` keeps its own generator (`python -m bti.editor.hints`), regenerated.
Tests (`tests/cli/test_cli_docs.py`): the parts are not stale; every command, action id, route, exit code and file a document names exists; every word in code ticks is a word the app has (hint table, needs, registries, the app's documents, the command's own codes);
every concrete command line parses with the real parser; the codes in the `(exit N)` rows really give that exit; and every worked session is **played** against the app and must print what the document says (`<job>`, `<rev>`, `<time>`, `<any>` and a line `...` stand for what varies).

## Decisions where the brief was silent

1. **Recording who needed three files that are not on the list.** The approval normalizers (`_approval` in `bti/script/store.py` and `bti/picks/doc.py`) drop keys they do not know, so `by` had to be added there and to `store.approve`, `doc.stamp_approval` and `service.approve` (each: one optional argument, a few lines, marked `c5cli`).
2. **Paid is refused by the server too.** Beyond the brief: `POST .../picks/suggest` answers 403 `spend_needs_human` to an actor that is not `human`, and `PUT .../auto` refuses `spend.paid: true`; a hand-edited file that says true is read as false.
3. **Only the owner changes `auto`.** A `PUT .../auto` with an actor that is not `human` is 403 `auto_needs_human` (otherwise an agent could switch itself on). New codes `gate_needs_human` (after_fix), `auto_needs_human` and `spend_needs_human` (no) are in the hint table and in `errmsg.js`.
4. **`spend` stands on its own.** It is not conditioned on `enabled`: the defaults allow `model` and `machine_time` (that is what `--yes-cost` confirms), so `enabled` is the switch for gates (and for the later automatic run). Spending of those two kinds is enforced by the marks and by the command, not by the server (the routes take no actor); only the paid call is enforced by the server.
5. **The command refuses the actor `human`** (exit 2) and turns `--actor NAME` into `cli:NAME` (`agent:...` kept; `BTI_ACTOR` is the default; else `cli:bti`).
6. **Exit codes in the cases the brief did not name**: an action that exists but is not listed now is 4 (`action_not_listed`), a typo is 2; not ready is 4, or 5 when it waits only for a running job; a cost the owner did not allow is 3 before readiness is looked at; a failed job maps as above; `bti job <id>` without `--wait` exits 0 whenever it could read the job.
7. **`bti status` is compact**: the actions of the current steps, the advancing ones and every gate in full; the other ready actions as ids with a mark on one `also` line; the last line `next:` is a command, `bti job <id> --wait` while a job runs, or the owner's name when only the owner can go on. `bti status --json` has everything.
8. **JSON mode** prints one object on stdout; with `--wait` the progress lines go to stderr. Text errors go to stderr.
9. **Extra options and one alias**: `--url`, `--timeout`, `--interval`, `--max-wait` (exit 5 `still_running`, so a harness that cuts commands short can come back), `--limit`; `bti doc` with no step prints `AGENTS.md`; `edit` is an alias of `storyboard`.
10. **The switch is a button in the top bar plus a dialog**, not a section of "Cài đặt" (that dialog is the machine's, the switch is one project's); hidden on the home page, in the library and in `?mock=1`.
11. **The state answer grew two keys** (`auto`, `approvals`); the hand-written part of `docs/AGENT_API.md` (example, the `auto_ok` row, a section "Automatic running and who approved") was updated by hand, `tests/state/test_docs.py` compares the example's keys with the real answer.
12. **`AGENTS.md` has no table of all actions** (it would not stay one page): the step documents list theirs, generated, and `bti status` lists what is possible now.
13. **Test modules have unique names** (`test_cli_*.py`) and the helpers are in `cli_helpers.py`, so that no two test folders clash when pytest runs several in one session.
14. **No `bti get`.** An agent reads documents (outline, narration, picks, storyboard) with their GET routes; the documents say so. A read command would be small and would spare agents `curl` (recommendation, not built: the brief lists the sub-commands).

## What could not be verified

* The command was not run against the real app on 8560 (forbidden) nor against a real model, voice or render: the long jobs of the tests are real jobs of the app's runner with quick parts; the voice, draft and export starters are stood in.
* `tools/bti` and `tools/bti.bat` were only read and checked as text (they need the `.venv` of the folder; a worktree has none). The batch file was never run on Windows.
* The page switch was not seen in a browser: only its logic (Node, 8 tests), the files that carry it and the server's answers were tested. The dialog's look and focus order are unseen.
* The `actor` is what the caller says it is, not an authentication: an agent that sends raw HTTP and claims `human` can approve, and one that skips the command can start model and machine-time jobs. The rule keeps an honest agent honest (documented in `docs/AGENT_API.md` and `docs/APP_GUIDE.md`).
* The actions of the two other workers (`picks.auto`, the edit actions) are not in this checkout: the command works from the state answer, and the generated lists of the documents will pick them up when `python -m bti.cli.docgen` runs after the join (the test says so if it is forgotten).
* The folders `tests/state`, `ops`, `editor`, `picks`, `script`, `settings` ran on a snapshot made before the last edits of `bti/cli/` and `AGENTS.md` (their payload and option text, which no test of those folders touches); `tests/cli` ran again on the final tree.

## Summary lines as printed (snapshot `c5cli`, `-q`; Node on the Mac)

```
tests/cli       119 passed, 1 warning in 35.90s
tests/state     277 passed, 1 warning in 152.89s (0:02:32)
tests/ops       468 passed, 1 warning in 95.70s (0:01:35)
tests/editor    481 passed, 1 warning in 222.22s (0:03:42)
tests/picks     92 passed, 1 warning in 13.22s
tests/script    262 passed, 7 skipped in 31.60s
tests/settings  44 passed, 1 warning in 3.34s
node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs
ℹ tests 350   ℹ pass 349   ℹ fail 0   ℹ skipped 1
```

## Needs another worker

Nothing blocks. At the join: `state_api.py`, `hints.py`, `picks_api.py`, `labels.js`, `errmsg.js` carry small blocks marked `c5cli`; after the join run `python -m bti.editor.hints` and `python -m bti.cli.docgen` and the three test folders `tests/state`, `tests/cli`, `tests/editor`.
