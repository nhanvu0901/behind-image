# AGENTS.md: operating a project of Behind the Image

**This file is for an agent that OPERATES a project** of this app (Claude Code, Codex or Antigravity in a terminal), step by step, without clicking
a web page. If you are changing this repository's code instead, read the developer documents: `docs/AGENT_API.md` (the HTTP API), `docs/OPS.md`
(the typed operations), `docs/APP_GUIDE.md` (the six steps for the owner, in Vietnamese), `docs/WINDOWS.md` (the server) and `docs/design/`.

The app turns an art book into a long video about one painting. It runs on a server; you talk to it with one command, `bti`, which speaks the app's
HTTP API and answers in plain text (or JSON with `--json`). The owner reads Vietnamese; the page and the labels the app returns are Vietnamese,
the command's own words are English.

## The pipeline in six steps

| # | step (`bti status`) | what it makes | gate before the next | skill |
|---|---|---|---|---|
| 1 | `artwork` | the painting and the book sources of the project (chosen in the library by the owner) | | |
| 2 | `script` | the outline, then the narration (a model writes, you check), then the video's title (an agent writes it from the narration) | `outline`, then `narration` | `skills/script/SKILL.md`, `skills/title/SKILL.md` |
| 3 | `voice` | the narration read aloud and timed word by word (about an hour of machine time) | | `skills/voice/SKILL.md` |
| 4 | `picks` | the main painting, its regions, and the pictures for each line of the narration | `picks` | `skills/picks/SKILL.md` |
| 5 | `edit` | the storyboard: a draft by a model, then typed operations | `storyboard` | `skills/storyboard/SKILL.md` |
| 6 | `export` | the finished video, its description and chapters (about 25 minutes of machine time) | | `skills/export/SKILL.md` |

Steps 3 and 4 open together once the narration is approved. `bti doc <step>` prints a step's skill document (`bti doc` alone prints this file). The title is not a gate: nobody approves it (`title.generate` writes it, `title.set` sets your own, at any time).

## Start here

- `bti status` lists the projects; `bti status <project>` says where the project stands, what blocks it, what can be done now (with the action ids), the jobs running, and the one command to run next.

Read the last line, `next: ...`, and run it. It is the first action that is ready and moves the project forward; when a job is running it is
`bti job <id> --wait`; when only the owner can go on it says so and names the gate or the spend. After every command run `bti status <project>` again.
`bti` talks to `BTI_URL` (default `http://127.0.0.1:8560`); `--actor NAME` (or `BTI_ACTOR`) names you in the change log and in every approval you make.

## The rules

1. **Change data only through actions and operations.** Never edit a file of a project (`projects/<project>/...`), never write to the app's folders: the app checks every
   change, keeps a change log and can undo it. An action is what `bti status` lists under `can do now`; an operation is a small typed change sent with `bti ops` (see `bti schema ops <document>`).
   To READ a document (the outline, the narration, the picks, the storyboard) use its GET route (`GET /api/projects/{pid}/narration`, `docs/AGENT_API.md`): `bti` prints no documents.
2. **Gates belong to the owner unless the owner allowed you.** By default every gate (`outline`, `narration`, `picks`, `storyboard`) is approved by the owner on the page. When the owner turned
   automatic running on for a project and allowed a gate, `bti approve <project> <gate>` works for that gate; otherwise it exits 3. Never send the actor `human` and never look for another way to approve: stop and tell the owner which gate waits. `bti status` shows `automatic running` and who approved each gate.
3. **Costs are marked, and you confirm only what the owner allowed.** An action with a cost (machine time, a model call or money) runs only with `--yes-cost`, and only if the owner allowed
   that kind of spending. Money (`paid`) is never yours: the owner starts it on the page. Add `--yes-cost` only when the owner asked for this work.
4. **Never start a second long job on a project.** A voice, a draft, an export, a picture search or the agent's choice of pictures is one job; wait for it (`bti job <id> --wait`, or `--wait` on the action) before anything of the same kind. The agent's choice of pictures (`picks.auto`), a request-box turn (`picks.edit`, `draft.edit`), a draft (`draft.start`) and the video's title (`title.generate`) hold the one agent run of the project and also run one at a time.
   An action that waits only for a running job is not an error: exit 5.
5. **Read the refusal.** Every error says `code`, `detail`, `fix` and `retry`; do what `fix` says. A refused batch of operations wrote nothing. A stale revision means someone changed the
   document: run the command again (the command reads the current revision itself).
6. **Do not guess content.** Names, dates, places, figures and relations come only from the narration and the project's sources; leave an item out when you are unsure. Never put the narration on screen as text.

## The commands

<!-- BEGIN GENERATED: commands -->
| command | what it does |
|---|---|
| `bti status [project]` | Where a project stands, what blocks it, what can be done now and the next command (no project: the list of projects). |
| `bti do <project> <action id> [--body FILE \| --set key=value ...] [--wait] [--yes-cost]` | Call one action of the state answer. An action that is not ready is refused with its needs; one that costs runs only with --yes-cost. |
| `bti approve <project> <gate>` | Approve outline, narration, picks or storyboard; refused (exit 3) when the owner did not allow an agent to approve it. |
| `bti ops <project> picks\|storyboard --file ops.json [--dry-run] [--note TEXT]` | Send a batch of typed operations (the command reads the current revision itself) and print the changes. |
| `bti run <project> [--until STEP] [--max-steps N] [--wait] [--yes-cost]` | Run the project by itself (automatic running, a long job): take the first allowed action that moves it forward, over and over, until it is exported or a reason stops it (a gate or a cost the owner did not allow, a warning, a failure, nothing left to do); every step is in the run log. |
| `bti output <project> [--clean]` | Fill (or refill) the project's folder output/<artwork key>/ (the video, the readable documents, the log) from the project as it stands; --clean also removes the working folder's caches when the export stands. |
| `bti job <id> [--wait] [--cancel]` | Look at a long job, follow it to its end, or stop it. |
| `bti undo <project> <batch>` | Undo one batch of operations. |
| `bti changes <project> [picks\|storyboard]` | The change log of the project, newest batch first. |
| `bti schema ops picks\|storyboard` | The operations of a document with their schemas and examples. |
| `bti doc [step]` | Print the skill document of a step (script, title, voice, picks, storyboard, export); without a step, AGENTS.md. |

Options of every command (before or after the sub-command):

| option | meaning |
|---|---|
| `--json` | Print the server's JSON (or one JSON object of the command's own on an error) instead of text; the progress lines of `--wait` then go to stderr. |
| `--actor NAME` | Who is calling, sent wherever the API takes an actor: `cli:NAME` (default `cli:bti`, or `BTI_ACTOR`); `agent:<model id>` is kept as it is; `human` is refused. |
| `--url URL` | The app's address (default `BTI_URL`, else http://127.0.0.1:8560). |
| `--timeout SECONDS` | How long one request may take (default 60). |
<!-- END GENERATED: commands -->

## Exit codes

<!-- BEGIN GENERATED: exit_codes -->
| exit code | name | meaning | what to do |
|---|---|---|---|
| 0 | `done` | The command did what it was asked. | Go on with the next command. |
| 2 | `usage` | The command was typed wrong (an unknown sub-command, a missing argument, an action id that does not exist). Nothing was sent. | Read the message and the usage line, then type the command again. |
| 3 | `person_needed` | A person is needed: a gate the agent may not approve, a cost that is not confirmed (`--yes-cost`) or not allowed, a spend of money, a sign-in on the server. | Stop and tell the owner what the line says; do not try another way round. |
| 4 | `refused` | The data was refused (HTTP 4xx, or a job that failed): the server's `code`, `fix` and `fields` are printed. | Do what `fix` says, then send the command again. |
| 5 | `busy` | Busy: a job of the same kind is running, a revision is stale, or the service is not answering right now. | Wait (`bti job <id> --wait`), read the document again, then send the command again. |
| 6 | `unreachable` | The app cannot be reached (nothing listens at `BTI_URL`, the connection broke, or the answer was not the app's). | Check that the app runs and that `BTI_URL` is right; do not retry in a loop. |
<!-- END GENERATED: exit_codes -->

How the server's answer becomes an exit code (one table, in `bti/cli/exitcodes.py`):

<!-- BEGIN GENERATED: exit_mapping -->
| rule (the first that matches wins) | exit code |
|---|---|
| any 2xx answer | 0 (`done`) |
| status 401 or 403, or a `code` of `gate_needs_human`, `auto_needs_human`, `spend_needs_human`, `auto_not_enabled`, `confirm_required`, `agy_auth`, `claude_auth`, `claude_outdated`, `real_models_off` | 3 (`person_needed`) |
| a stale revision (`code` `stale` or `stale_revision`) | 5 (`busy`) |
| `retry` is `later` (a job is busy, a service is not answering, a quota opens later), whatever the status | 5 (`busy`) |
| any other answer with a status of 400 or more (`retry` is `after_fix` or `no`) | 4 (`refused`) |
| no answer, a broken connection, a time-out, or an answer that is not JSON | 6 (`unreachable`) |

A job that ends (`bti do ... --wait`, `bti job ... --wait`) maps like this: `done` is 0; `cancelled` and `interrupted` are 5; `error` goes by the job's `error_code` through the same rules (a code in the person list is 3, a code whose `retry` is `later` is 5, any other is 4); a script job has an `error_kind` instead: `auth` 3, `blocked` 4, `config` 4, `conflict` 4, `parse` 4, `validation` 4, `empty` 5, `http` 5, `rate_limit` 5, `timeout` 5.
<!-- END GENERATED: exit_mapping -->

## The gates

<!-- BEGIN GENERATED: gates -->
| gate | action id | route | what follows it | who approves it |
|---|---|---|---|---|
| `outline` | `outline.approve` | `POST /api/projects/{pid}/outline/approve` | writing the narration (a few minutes of a model) | the owner on the page; an agent only when the owner turned automatic running on for the project and allowed this gate (`auto` of `bti status`) |
| `narration` | `narration.approve` | `POST /api/projects/{pid}/narration/approve` | the voice (about an hour of machine time) | the owner on the page; an agent only when the owner turned automatic running on for the project and allowed this gate (`auto` of `bti status`) |
| `picks` | `picks.approve` | `POST /api/projects/{pid}/picks/approve` | the storyboard draft (about 20 minutes of a model) | the owner on the page; an agent only when the owner turned automatic running on for the project and allowed this gate (`auto` of `bti status`) |
| `storyboard` | `storyboard.approve` | `POST /api/projects/{pid}/approve` | the export (about 25 minutes of machine time) | the owner on the page; an agent only when the owner turned automatic running on for the project and allowed this gate (`auto` of `bti status`) |
<!-- END GENERATED: gates -->

## Running by itself

When the owner asks for the whole run and has turned automatic running on, `bti run <project> --yes-cost --wait` takes the first allowed action that moves the project forward, over and over, until the video is exported, and stops with a reason. It approves a gate only where the owner allowed it (as `agent:auto`), checks the warnings before each gate, never spends money and writes every step to the run log. At the pictures gate a flagged picture (`asset_flag`) never stops it (copyright is not a blocker; the count goes into the log) and lines with no picture (`beat_no_pick`) stop it only when they are more than a quarter of the narration: up to a quarter it goes on, and the end of the run says how many lines have none. It takes `picks.auto` itself as one of its steps, and `picks.retry_missing` once after it (when a source refused the download of a picture the agent chose, `missing` says `import_limited`); while it runs, a hand-started `picks.auto`, `picks.edit` and `draft.edit` are refused (`agent_job_running`), and a job that is not its own stops it (`busy_elsewhere`). Exit 0: done. Exit 3: the owner is needed (`gate_not_allowed`, `spend_not_allowed`, `quality_warning`, `nothing_to_do`, `auto_not_enabled`). Exit 4: a step failed (`action_failed`, `job_failed`). Exit 5: cancelled or a limit; run it again to continue. Stop it with `bti job <id> --cancel`. The reasons and the quality bar are in `docs/AGENT_API.md`, section 9.

## Where to go on

One document per step, with its goal, what it needs and gives, every action and operation it uses (the action ids are listed there, generated from the code), a worked session with real output, what a good result is and the refusals you will meet:
`skills/script/SKILL.md`, `skills/title/SKILL.md`, `skills/voice/SKILL.md`, `skills/picks/SKILL.md`, `skills/storyboard/SKILL.md`, `skills/export/SKILL.md` (or `bti doc <step>`). The lists in this file and in those
documents are generated from the code and tested: when the app changes they change with it (`python -m bti.cli.docgen`).
