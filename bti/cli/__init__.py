"""`bti`: a thin command for an agent in a terminal (Claude Code, Codex, Antigravity) that runs a project of the app step by step.

It speaks the running app's HTTP API (`BTI_URL`, default http://127.0.0.1:8560) and answers in plain text or, with `--json`, in JSON. It never
reads or writes a project's files, never calls a model and uses the standard library only. Which gates an agent may approve is the server's
rule (`bti/auto.py`); the command only says what the server said. Run it as `python -m bti.cli ...` or through `tools/bti` / `tools/bti.bat`.

    bti status [project]                          where a project stands and the next command (without a project: the list of projects)
    bti do <project> <action id> [...]            call one action of the state answer
    bti approve <project> <gate>                  approve outline, narration, picks or storyboard
    bti ops <project> picks|storyboard --file F   send a batch of typed operations
    bti job <id> [--wait] [--cancel]              look at, follow or stop a long job
    bti undo <project> <batch>                    undo one batch of operations
    bti changes <project> [picks|storyboard]      the change log
    bti schema ops picks|storyboard               the operations' schemas
    bti doc [step]                                the step's skill document (no step: AGENTS.md)

The commands, the exit codes and their mapping are in `bti/cli/exitcodes.py` and `bti/cli/main.py`; `python -m bti.cli.docgen` writes the lists of
`AGENTS.md` and `skills/*/SKILL.md` from them.
"""
