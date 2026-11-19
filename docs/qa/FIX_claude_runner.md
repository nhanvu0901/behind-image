# Claude Code as the second runner (worker `claudeprov`, 2026-11-18)

Contract: `docs/design/2026-11-18-agent-choice.md`, section 2a. The id `claude:claude-opus-5-5@high` is now usable wherever an `agy:` id is
usable: one call (outline, narration, fast edit) and the agent that works in a folder (draft, deep edit). The agent select is the next
worker's task and is not built here. The `agy` runner, the prompts and the briefings are untouched.

## 1. What was built, per point of the brief

| Point | Where |
|---|---|
| 1. Id family `claude:<model>@<effort>`, parsed in one place, listed, resolved, accepted by the settings check | `bti/script/providers/claudecode.py` (`parse_model_id`, `make_model_id`, `is_claude_id`, `label_for`); `config/models.json` (one tracked entry, label "Claude Code: Opus 5.5 High"); `bti/script/models.py` (`PROVIDERS`, `load_models`, `public`, `resolve`); `bti/settings.py` (agent roles accept `agy:` or `claude:`); `bti/draft/run.py` (`MODEL_RE` allows `@`, `_bad_model_name`) |
| 2. Availability without a model call, cached | `claudecode.availability()` / `auth_status()` (`claude auth status`, only the `loggedIn` flag is read), `models.claude_status()` (cached 10 min, 1 min after a failure, one check at a time), reasons `not_installed`, `not_signed_in`, `timeout`, `unreadable` in `public_models()[i]["claude"]` and `unavailable*` fields of the spec |
| 3. One call | `bti/script/providers/claudecode.py` (`complete`, registered as provider `claudecode` in `bti/script/providers/__init__.py`) |
| 4. Agent in a folder | `bti/draft/providers/claudecode.py` (`run`, same signature and `AgyResult` as `agy.run`); chosen by the model id in `bti/draft/run.py` (`_agent_module`, used by the draft job and by the deep edit) |
| 5. Failure sentences | `bti/draft/run.py` (`VI`, `rate_limit_sentence`, `provider_code`), `bti/editor/static/js/errmsg.js` (block `worker claudeprov`), one line in `editlogic.js` (see section 6) |
| 6. Tests | `tests/script/test_claudecode.py`, `tests/script/fake_claude.py` (fake `claude`), `tests/draft/test_claude_runner.py`, fixtures `tests/script/fixtures/claude/`, `tests/draft/fixtures/claude/`, `tests/settings/test_settings.py`, `tests/editor_frontend/errmsg.test.mjs` |
| Docs | `docs/APP_GUIDE.md` section 5.4b (two runners, signing in on the server) |

Failure codes (each has its own Vietnamese sentence, in `run.py` and `errmsg.js`): `claude_missing`, `claude_auth` (the exact sentence of the
brief), `claude_rate_limit` (with the time it opens again: "Hạn mức của gói Claude Code đã hết. Thử lại sau 4 giờ 30 phút (khoảng 18:20)."),
`claude_model`, `claude_config`, `claude_error`, `claude_no_result`, `claude_timeout`. For single calls the same facts are `ProviderError` kinds
`config` (not installed, refused model name, build too old), `auth`, `rate_limit` (with `retry_after_seconds`), `timeout`, `cancelled`, `empty`, `http`;
every such error also carries `.code` (the `claude_*` code), which `run.py` uses for the fast edit.

## 2. The two command lines (Claude Code 2.1.327 on the Mac, 2.1.233 on the server: only options both list in `--help`)

One call (`claudecode.build_command`; the prompt goes in through a file used as standard input, never as an argument):

```
claude -p --model claude-opus-5-5 --effort high --output-format json --tools "" --safe-mode --setting-sources "" \
       --strict-mcp-config --disable-slash-commands --no-session-persistence --permission-mode dontAsk --system-prompt <the system text>
```

| Option | Why |
|---|---|
| `-p`, `--output-format json` | non-interactive; one result object with `result`, `is_error`, `api_error_status`, `permission_denials`, `num_turns` |
| `--model`, `--effort` | from the id. Both values are checked against `[A-Za-z0-9][A-Za-z0-9._-]*` and `low|medium|high|xhigh|max` before they reach the command |
| `--tools ""` | no built-in tool exists, so there is nothing to approve or deny (the real init event lists `tools: []`) |
| `--safe-mode` | no CLAUDE.md, hooks, skills, plugins, MCP servers, custom commands or agents, output styles, auto memory of whoever is signed in. `--bare` is not used: it refuses the plan login |
| `--setting-sources ""` | no settings file of the user, the project or the folder |
| `--strict-mcp-config`, `--disable-slash-commands` | no MCP server connects, no skill or command (belt and braces next to safe mode) |
| `--no-session-persistence` | nothing is kept in the program's session folder (the owner's text would otherwise stay on disk) |
| `--permission-mode dontAsk` | anything that would ask is refused; never `--dangerously-skip-permissions` |
| `--system-prompt` | the `system` text REPLACES the default prompt. If the executable is a Windows `.cmd` shim and the text holds characters cmd.exe re-reads (`"%^&|<>!` or a newline), the text goes in front of the user text on standard input instead (`arg_ok_for`) |

Environment (`clean_env`): a whitelist (PATH, HOME or USERPROFILE and the other Windows system variables, TERM, language, `CLAUDE_CONFIG_DIR`,
`CLAUDE_CODE_OAUTH_TOKEN`, proxy and certificate variables). `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, a base URL and every project variable
are never passed, so a call is always a plan call, never a paid API call. The working folder is a fresh empty temporary folder, deleted afterwards and
checked to be still empty. A result with `permission_denials`, more than one turn, files in the folder, or an empty text is refused.

The agent in a folder (`bti/draft/providers/claudecode.py`, `build_command`):

```
claude -p --model claude-opus-5-5 --effort high --input-format stream-json --output-format stream-json --verbose \
  --tools Bash,Read,Write,Edit,Glob,Grep --safe-mode --setting-sources "" --strict-mcp-config --disable-slash-commands --no-session-persistence \
  --permission-mode dontAsk \
  --allowedTools 'Edit(./out/**)' 'Bash(./check)' 'Bash(./check --no-draw)' 'Bash(./check --chapter *)' 'Bash(./check --no-draw --chapter *)' \
     'Bash(./check --chapter * --no-draw)' 'Bash(./check --help)' 'Bash(./defaults --help)' 'Bash(./defaults *)' 'Bash(./still --help)' \
     'Bash(./still --shot * -o look/*)' 'Bash(./still --shot * --at * -o look/*)' 'Bash(./still --shot * -o look/* --at *)' \
  --disallowedTools WebFetch WebSearch 'Bash(*..*)' 'Bash(* /*)' "Bash(*'/*)" 'Bash(*"/*)' 'Bash(* ~*)' 'Bash(*:/*)' 'Bash(*--workspace*)' \
     'Bash(*-o/*)' 'Bash(*$(*)' 'Bash(*`*)' \
  --append-system-prompt "You work unattended inside one folder, ... only under out/ ... only the helper commands that TASK.md names ..."
```

The first message is one NDJSON line on standard input (`{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Read TASK.md ..."}]}}`).
On Windows the three helpers are written `.cmd` by the workspace, so the rules exist in the three spellings `./x.cmd`, `.\x.cmd`, `x.cmd`, plus two
deny rules for a backslash path. Why each option: `--input-format stream-json` keeps standard input open so a repair message goes into the SAME
process; `--verbose` is required for stream-json output; `--tools` lists only what the briefing needs (no web, no task or notebook tools);
`--permission-mode dontAsk` plus an allow list means "refuse everything that is not named", not "bypass everything"; the isolation options are
those of the single call.

Repair rounds: the check runs on every `result`; its problems are written as the next `user` line to the same process (at most `max_repairs`), then
standard input is closed and the program leaves. I chose the open process over `--resume <id>` because both versions have `--input-format
stream-json`, it needs no session on disk (so `--no-session-persistence` stays true) and there is no second start. Cost: a program that ends before
its final result is an error (`claude_no_result`), not a restart, and a conversation cannot be continued by a LATER job: `conversation_id` is
accepted and ignored, the result's is `None`, and the follow-up edit rebuilds its context from the thread (`format_previous_exchanges`), which the
existing code already does for any run without a conversation (a conversation id of an agy turn is never handed to Claude Code).

Cancel and time limit: same machinery as `agy.run` (the job's `run_process`, a watchdog, `bti.proc.kill_tree`: `os.killpg` on POSIX, `taskkill /T /F`
on Windows); tests start a child process under the fake and check that both are gone after a cancel and after a time-out, on the Windows server too.
The result object, the guard (project listed before and after, `tampered`), the one-run-at-a-time lock (shared with `agy.LOCK`, `agy_busy`) are the same.

## 3. How the agent is confined, and what happened when it tried something outside (real calls, Mac, Claude Code 2.1.327, `--model haiku`)

Rules: reading inside the workspace needs no rule (the program's default); reading elsewhere, any write outside `out/`, any command not matched by an
allow rule, and every tool not in `--tools` are refused by `dontAsk`; deny rules (which win over allow rules and apply to every part of a compound
command) close what the wildcards of the allow rules leave open (a path that leaves the folder, a home path, a drive, `--workspace`, a command
substitution). Nothing allows a whole tool (`Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`).

Real call 5 (first try, allow rules wide: `./check *`, `./still *`, no deny rules; fixture `tests/draft/fixtures/claude/refusal_first_try.jsonl`): the
agent was told to make 19 attempts in order. Refused (by the program's own checks, "dontAsk mode"): Read of a file outside; `cat` and `ls` of a folder
outside; Write outside, Write to the workspace root (not `out/`), Write through `out/../`; redirects to a file outside; Grep and Glob with a path
outside; `sh -c 'cat <outside>'`; `cd <outside> && ls`; `./check && cat <outside>`; `./check $(cat <outside>)`; `./check | cat <outside>`;
`head ../*`. Let through: `python3 --version` (the program treats `<anything> --version` as read-only) and `./check <outside folder>` (a wide allow
rule matches any argument). Note: that Write to `<workspace>/out/ok.json` was also refused in this call, because my probe used the unresolved
temporary path (`/var/...`, a symbolic link to `/private/var/...` on macOS), which the rule `./out/**` does not match; the agent itself uses the
folder it is started in, and the later calls wrote to `out/` normally.

Real call 6 (rules as they are now; fixture `refusal_tightened.jsonl`): 20 attempts. Ran: `./check --no-draw`, `./check --chapter c01`,
`./defaults CAM-05 --asset A --region MIRROR`, `./still --shot c01:1 -o look/a.jpg`, `Write out/ok.json`, `Edit out/ok.json`, `Read TASK.md`, `ls`,
`cat TASK.md`, `./still ... -o look/b.jpg && ./check`, `./check --chapter c01 2>&1 | tail -3`, and a `Write out/notes.md` the agent chose to make
to record the refusals. Refused: `./check <outside>`, `./check --chapter c01 <outside>`, `./check '<outside>'`, `./still --shot c01:1 -o <outside>/x.jpg`,
`./still ... -o look/../../x.jpg`, `./defaults --workspace <outside> CAM-05`, `./check --chapter c01 $(cat <outside>/secret.txt)`,
`./check --chapter c01 ~/x`, `cat <absolute path inside the workspace>` (an absolute path is denied by the deny rule; the Read tool and relative paths
work). The filesystem confirmed it: nothing was created outside, no `x.jpg` next to the workspace. The program says "Permission to use X has been denied
because Claude Code is running in don't ask mode" for a command nothing allows, and "Permission to use Bash with command ... has been denied" for a
deny-rule hit; the final `result` lists every refusal in `permission_denials`, which `run()` keeps once each in `AgyResult.denials` (an extra
attribute: tool and what it tried).

A test replays both recorded sessions through `run()`, and one test checks that a model of the documented rule grammar decides every recorded
command exactly as the real program did (allowed, refused by "dontAsk", denied by a rule).

What this does NOT cover: the helper commands themselves. `bti/draft/still.py` writes to whatever `-o` says and `check.py`/`defaults.py` take a
workspace path; only the command TEXT is constrained (section 7, "Needs another worker").

## 4. Real calls (limit 10, all on this Mac, all `--model haiku`, all from an empty temporary folder; nothing on the server, nothing with Opus, nothing through the app)

Ten calls were made (the whole allowance). Raw output stayed in the scratchpad; fixtures were scrubbed of the home path, temporary paths,
account fields (`email`, `orgId`, `credential_expires_at`, ...) and `thinking` blocks.

| # | What | Recorded as |
|---|---|---|
| 1 | one call, the exact single-call command, prompt "Say hello." | `tests/script/fixtures/claude/single_ok.json` (answer "Hello!", English although the owner's own global instruction says Vietnamese: their set-up did not leak) |
| 2 | the same command with `--output-format stream-json --verbose`, to read the init event | `single_stream_init.jsonl`: `tools: []`, `mcp_servers: []`, `slash_commands: []`, `skills: []`, `plugins`: only four `@builtin` ones, `agents`: only the four built-in, `permissionMode: dontAsk`; also the `rate_limit_event` shape |
| 3 | agent session, first turn only (my probe looked for the result line in the wrong place and waited; I stopped it) | not kept (its events are in 4) |
| 4 | agent, two turns on one open process (write a file, run `./check`; then the repair message: edit it, run `./check`) | `tests/draft/fixtures/claude/agent_two_turns.jsonl` |
| 5 | refusals, first try | `refusal_first_try.jsonl` |
| 6 | refusals, rules as they are now | `refusal_tightened.jsonl` |
| 7 | a model name that does not exist | `wrong_model.json` (+ `.stderr.txt`): exit 1, `is_error: true`, `api_error_status: 404`, `api_error_type: not_found_error`, "There's an issue with the selected model (...)" |
| 8 | nobody signed in (an empty `CLAUDE_CONFIG_DIR`): `claude -p` and `claude auth status` | `not_signed_in.json` (exit 1, `is_error: true`, "Not logged in · Please run /login"), `auth_status_signed_out.json` (exit 1, `loggedIn: false`) |
| 9 | `complete()` itself, end to end, through `get_provider("claudecode")` | not a fixture: answer "Hello!", progress `[1.0]`, 2.2 s |
| 10 | agent session that reads a small PNG with the Read tool and writes `out/a.json` | `image_read.jsonl` (picture data cut): under the rules the Read of a picture inside the folder works; its tool result is `content: [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": ...}}]` (10.5 KB of base64 for a 64 by 64 picture) |

Not recordings (named so in the tests and in the fake): the usage-limit answers (`You've hit your session limit · resets 7pm (Asia/Saigon)` and
the others: documented wording and the recorded `rate_limit_event` shape with `status: "rejected"`), because a real limit could not be provoked.
Shapes learned from the real calls and used by the code: the result carries `is_error` with `subtype: "success"` even for failures; `result` holds the
text; an error has `api_error_status`; `claude auth status` prints JSON and exits 1 when nobody is signed in; the process stays open for the next
`user` line and leaves when standard input closes; the result of a turn has `num_turns` of the whole turn (several tool calls).

Other non-model commands run: `claude --version`, `claude --help` on both machines, `claude auth --help` / `auth status --help` on both, `claude auth
status` on the Mac (only the `loggedIn` flag was read or printed). The environment refused `ssh winbox-cmd "claude auth status"`; I did not work
around it: the server's "not signed in" state is the one the contract records.

## 5. Tests (server snapshot `claudeprov`, Windows; the fake is a `.cmd` launcher there)

Run with `BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh claudeprov [--no-sync] -- <folder> -q -p no:cacheprovider`, one folder per run, after the last change. Summary lines exactly as printed:

```
tests/script    243 passed, 7 skipped in 29.13s
tests/settings  9 passed, 1 warning in 5.00s
tests/draft     290 passed, 1 warning in 110.69s (0:01:50)
tests/editor    449 passed, 1 warning in 199.44s (0:03:19)
```

On the Mac: `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` printed `tests 279`, `pass 279`, `fail 0`.

The 7 skipped in `tests/script` are not new except one: `test_a_real_zone_name_is_read_with_the_machines_database` (the Windows server has no time-zone database; the same arithmetic is tested with fixed offsets).
New: `tests/script/test_claudecode.py` (97 tests: id parser, the exact command line and its isolation options, what the program is given (environment whitelist, empty folder, stdin), every failure kind and the owner's sentences, the usage-limit time parsing, cancel and time limit killing the tree, a 60,000-character prompt, one call at a time, availability, the model list and its cache, `resolve`), `tests/draft/test_claude_runner.py` (47 tests: the agent's command line and permission rules, the recorded sessions replayed through `run()`, repairs in the same process, error codes, cancel and time limit killing the tree, the shared lock, `run.py` picking the runner by the id, the edit routes with a Claude Code model, fast and deep, the usage limit and the signed-out sentence reaching the turn), 2 in `tests/settings`, 3 in `tests/editor_frontend/errmsg.test.mjs`. The fake is `tests/script/fake_claude.py`; it replays the real events and writes into `out/` like an agent.


## 6. Files touched beyond the strict list (one line each)

- `bti/editor/static/js/editlogic.js`: the eight `claude_*` codes added to `EDIT_CODES` and `claude_rate_limit` to `QUOTA_CODES` (so a failed turn shows the sentence and the quota card shows the time). Required by the existing test "every error code the server raises ... is in the list".
- `tests/script/conftest.py` (`BTI_CLAUDE_BIN=""`, so no test reaches a real `claude`) and `tests/script/test_providers.py` (the providers of the repo models file now include `claudecode`).
- `bti/editor/static/js/errmsg.js` also changes one existing sentence (`agentic_role_needs_agy`: now "...qua agy hoặc qua Claude Code.") and makes the script-job texts for kinds `auth` and `rate_limit` show the program's own Vietnamese sentence when it names Claude Code (the other providers keep their generic sentences).

## 7. Deviations from the contract, and what I could not verify

Deviations (each deliberate):
1. A later job cannot continue a Claude Code conversation (section 2). The contract asks for repair messages in the same conversation, which holds.
2. Any well-formed `claude:<model>@<effort>` resolves (the settings check and `resolve` accept `claude:claude-sonnet-4-5@medium`), not only the one tracked entry; a wrong model name is refused by the program when the job runs (`claude_model`). The model LIST has exactly one claude entry.
3. The single call adds none of the agy "task requirements" text (English, no tools): the tool-less, isolated call needs none, and an English-only rule would contradict prompts that ask for Vietnamese.
4. The agent's permission rules are narrower than "run what the briefing names": only the shapes the briefing shows are allowed (`./check` with `--no-draw`/`--chapter`, `./defaults <technique> ...`, `./still --shot ... -o look/...`), plus deny rules. A command the briefing names in another shape is refused and the agent is told to carry on.
5. `Glob` and `Grep` are in `--tools` (the default set leaves them out on macOS and Linux); a path outside the folder is refused for them like for `Read`.
6. `last_action` shows the step names the page already knows (`run_command`, `view_file`, `write_to_file`, ...), not the program's tool names.
7. No hook is used as a second lock: `--safe-mode` turns hooks off, and the brief asks for the permission options.
8. A build of `claude` whose `--help` lacks one of the options above (checked once per executable) is refused with "run `claude update`", never run half-open.
9. `BTI_NO_REAL_MODELS=1` makes the availability check answer "not available (test mode)" without starting `claude`, so no test suite reaches the real program.

Could not verify (needs the owner, or a real Opus run, or the server signed in):
- Any real call with Opus 5.5: not made (forbidden). So whether `--model claude-opus-5-5` is the name the program accepts, and `--effort high` on that model, are NOT verified (haiku accepted `--effort high`; a wrong name returns the recorded 404 answer, which the code maps to `claude_model`).
- Anything on the server: the permission behaviour of 2.1.233 (the rules were observed only on 2.1.327; the option names were read from both `--help` outputs; `dontAsk` and `--allowedTools`/`--disallowedTools` are listed by both), that the Bash tool works there (Claude Code on Windows needs Git Bash), whether the program is a `.exe` or a `.cmd` shim, the Windows rule spellings (`./check.cmd`, `.\check.cmd`) and the backslash deny rules, `--setting-sources ""` through a `.cmd` shim. The first real run on the server must be watched: if the agent cannot write `out/`, the job ends with `draft_no_output` and the transcript `cache/draft/<run>/events.jsonl` shows each refusal.
- A real usage-limit answer (its exact wording and whether `rate_limit_event` carries `status: "rejected"` and `resetsAt`): the parser reads that event first and the text second, and returns no time rather than a wrong one when it can read neither.
- The size of a real picture line: measured only for a 64 by 64 picture (10.5 KB of base64). The agent will read pictures up to 1568 px, so a line can reach hundreds of kilobytes; the transcript file shortens lines over 20,000 characters (`_compact`), but the long-job log (`bti/longjob/manager.py`, not mine) writes every line it receives.
- The time-zone names in a limit text on the Windows server: it has no time-zone database (`zoneinfo` needs `tzdata`), so a zone name is unknown there and the local clock is used (tests cover both paths; the one test with the real database is skipped on the server).
- `claude auth status` on the server: not re-run (the environment refused it); the owner signs in there once.

Needs another worker (not edited here):
- `bti/editor/draft_api.py`: its 409 list does not name `claude_missing`/`claude_auth` (they answer 422 with their code, which the page shows by code); `GET /draft/models` lists only `agy models`.
- `bti/draft/still.py`, `check.py`, `defaults.py`: refuse a `-o` / workspace path outside the workspace (today only the command text is constrained).
- The agent select and the quota button (section 6 of the contract): `claude_rate_limit` already carries `retry_after_seconds` and `retry_at` on the job and the turn, like `agy_rate_limit`.
