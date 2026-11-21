# Agent choice: two agents, one select per step, remembered for the whole pipeline

Build contract, 2026-11-18. Owner's request, in their words: "For now I want two agents that he can work on this pipeline
with, which are Opus 5.5 High, and Gemini 3.8 Flash. Make a select, something that I can choose to toggle between Agent in
each step. But it also can work full pipeline without me selecting an agent again."

Owner's answers of the same day on the agent-first design (`2026-11-18-agent-first-design.html`), recorded here because
this contract depends on them: every gate (outline, narration, picks, storyboard) may be approved by the agent in an
automatic run; at most one video clip per chapter, 4 to 10 s, context passages only; the step-5 page shows the shot list
by default with the timeline behind "Chỉnh tay"; no `.srt` file at export.

## 1. What the owner sees

- A small select, the same on every step that uses a model: `Agent: [Gemini 3.8 Flash v]`, with the two choices
  "Gemini 3.8 Flash" and "Opus 5.5 High". It shows the agent that WILL be used for this step of this project.
- Changing it on a step changes the agent for that step of that project only, at once, with no dialog. Under the select one
  line says where the value comes from: "Riêng cho bước này" (with a link "Dùng cho cả dự án") or "Theo dự án" or
  "Theo mặc định".
- "Dùng cho cả dự án" makes the chosen agent the project's agent and removes the per-step choices, so every later step uses
  it without the owner choosing again. A new project starts on the default agent of the settings box.
- The settings box ("Cài đặt") gets "Agent mặc định cho dự án mới" on top; the existing table of models per role moves
  under a collapsed "Nâng cao" heading and keeps working.
- Where a finished result names what wrote it (source lines of outline and narration, the draft job, the edit result), it
  names the agent by its label, not the raw model id.
- Steps: 2 "Kịch bản" (outline and narration), 5 "Dựng hình" (draft, the prompt box's fast and deep paths). Step 4 "Chọn
  hình" gets the same select when its agent exists (build stage C3 of the agent-first design); until then the choice for
  step 4 can already be stored through the API. Steps 1, 3 and 6 call no model.

## 2. The agents (tracked file `config/agent_choices.json`)

The owner's correction of the same evening: "each run through its [own]: gemini use agy, claude use claude code". So the
two agents do not share a runner: Gemini is run by the Antigravity command line (`agy`), Opus by the Claude Code command
line (`claude`), each under the owner's own account of that product. Section 2a is the contract of the second runner.

```json
{
  "default": "gemini",
  "agents": [
    {"id": "gemini", "label": "Gemini 3.8 Flash", "model": "agy:gemini-3.8-flash-high"},
    {"id": "opus", "label": "Opus 5.5 High", "model": "claude:claude-opus-5-5@high"}
  ],
  "steps": {
    "script": ["script.outline", "script.narration"],
    "picks": ["picks"],
    "storyboard": ["draft", "edit.fast", "edit.deep"]
  }
}
```

An agent is one model for every role of a step. The file path can be replaced with the environment variable
`BTI_AGENT_CHOICES_FILE` (tests use it to offer a mock agent). The role `library.restore` is not a step and keeps its
entry in `config/agents.json`.

## 2a. The second runner: Claude Code

A model id `claude:<model>@<effort>` (for example `claude:claude-opus-5-5@high`) is run by the `claude` command line in its
non-interactive mode (`-p`), with `--model <model>` and `--effort <effort>`. It must do everything the `agy` runner does
today, behind the same two interfaces, so nothing above them changes:

- **One call, text in and text out** (outline, narration, the fast edit; later the picks agent): the interface of
  `bti/script/providers` (`complete(spec, system, user, *, timeout, on_progress, cancel) -> text`). No tools, no files, no
  session kept on disk, nothing of the machine's own Claude Code set-up mixed in (no project instructions, hooks, skills,
  memory or MCP servers of whoever is signed in: the call must give the same answer on any machine).
- **An agent working in a folder** (the storyboard draft, the deep edit): the interface of `bti/draft/providers/agy.py`
  `run(ws_root, model=..., timeout=..., max_repairs=..., check=..., cancel=..., ...)`: start in the workspace, send the
  first message, follow the stream of events for progress, run the check when the agent says it is done, send the repair
  message up to `max_repairs` times in the SAME conversation, stop on cancel or on the time limit and leave no process
  behind, report the same result object. The agent may read and write only inside its workspace and run only what the
  briefing tells it to run.
- **Failures the owner must understand**, each with its own code and Vietnamese sentence: the command is not installed;
  Claude Code is not signed in on this machine ("Claude Code trên máy chủ chưa đăng nhập. ..."); the plan's usage limit is
  reached (with the time it opens again when the answer gives one: this is the "quota" case of section 6); the model name
  is refused; time limit; cancelled.
- **Availability without a model call**: installed and signed in (`claude auth status`), cached like the `agy models` list.
- The `claude:` family appears in the model list and passes the settings check for the roles that need an agent (today
  that check accepts only `agy:`).

Known on 2026-11-18: the server has Claude Code 2.1.233 installed and it is NOT signed in (`claude auth status` says
`loggedIn: false`); the owner signs in there once. Until then the Opus agent shows as not available with that reason.

## 3. Where a choice is stored

- Project: `projects/<pid>/agent.json`, written atomically:
  `{"schema": "bti.agent/1", "agent": "opus" | null, "steps": {"script": "gemini", ...}}`. A missing file means no choice.
  Its revision is computed the way the other project documents compute theirs.
- Machine: `run/settings.json`, key `agent` (an agent id): the default for projects without a choice.

## 4. Which model a call uses (one function, used by every model call of the six steps)

`bti.agents.model_for_project(project_dir, role) -> Resolved(model, agent_id | None, label, source)`; the first that applies:

1. the model named in the request itself (kept for tests and for outside tools; `source: "request"`);
2. the project's choice for the step the role belongs to (`"step"`);
3. the project's agent (`"project"`);
4. the machine's default agent, when the owner has set one (`"default"`);
5. what `bti.settings.model_for(role)` answers today (the per-role setting, else `config/agents.json`; `"role"`).

An agent id that the file no longer lists is ignored (the next rule applies) and reported as a warning in the GET answer.
`bti.settings.model_for(role)` stays as it is for callers without a project.

## 5. Routes

- `GET /api/agents` -> `{agents: [{id, label, model, available, reason}], default, machine_default}`. `available` comes from
  the cached `agy models` listing the app already keeps; this route never calls a model.
- `PUT /api/settings/agent {agent}` (`agent: null` clears it) -> the same answer as the GET. 422 `unknown_agent`.
- `GET /api/projects/{pid}/agent` -> `{rev, agent, steps, effective: {script: {id, label, model, source}, picks: {...},
  storyboard: {...}}, warnings}`.
- `PUT /api/projects/{pid}/agent {agent?, steps?, base_rev}` -> the same answer. A key that is present with `null` clears
  that choice; an absent key leaves it. 409 `stale` on an old `base_rev`, 422 `unknown_agent` / `unknown_step`.
- Every route that starts a model call for a project (outline, narration, draft, edit fast and deep) resolves through
  section 4 when the request names no model, and answers which agent it used. The pages stop sending a model of their own.

## 6. When the agent's quota is used up

`agy` answers "Individual quota reached ... Resets in ...", and Claude Code answers with its plan's usage-limit message.
The app already recognises the first; the second runner reports the second under the same code. New behaviour: the message
names the agent and the time ("Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút."), and offers exactly one
button, "Chuyển sang Gemini 3.8 Flash và chạy lại", which stores the other agent as this step's choice and runs the same
request again. Nothing switches by itself. (Whether an automatic run may switch by itself is decided with build stage C6.)

## 7. Not in this build

The picks agent (C3), the automatic run (C6), a third agent, a third runner, any change to the prompts or briefings.

Build order: first the Claude Code runner (section 2a, worker `claudeprov`), then the select (worker `agentpick`).

## 8. Checks that must exist

Resolution order (each rule, and an unknown id falling through); the document (rev, stale write, clearing, bad ids); the
routes; a job started without a model uses the project's choice and reports the agent; the select on steps 2 and 5 in a
real browser against the mock provider (change on a step, "Dùng cho cả dự án", reload keeps it, a second project is not
affected); the quota message and its one button with a fake quota answer; the settings box.
