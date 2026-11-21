# Prompt Video Editing Implementation Plan

> **For agentic workers:** Execute the existing approved section 7.4 task-by-task. The user explicitly assigned product coding to Gemini 3.8 Flash through agy; the parent does analysis and review only. No additional workers, commits or unrelated changes.

**Goal:** Let the owner edit an existing storyboard by natural-language instruction, scope it to selected shots/a chapter/the whole video, and continue through a persistent project conversation.

**Architecture:** Reuse the draft workspace, strict edit compiler and proposals/apply flow. Add validated edit/thread endpoints and a focused panel below the step-5 preview. Changes remain proposals until accepted; thread context survives app restarts.

**Tech Stack:** Existing Python/FastAPI, longjobs, agy provider and vanilla JavaScript.

**Spec:** `docs/design/2026-11-16-stages-3-4-6-and-draft-design.md`, section 7.4; `docs/qa/BUILD_draft.md`, edit-mode handoff.

## Global Constraints

- All product coding belongs to the Gemini worker. Parent may write plans, inspect and review.
- Preserve every pre-existing dirty change, including subtitle removal and media/clip work. Do not revert or commit any files.
- Keep rendering, narration, audio, exports, existing project data and comic repository untouched. Never reintroduce narration subtitles.
- User-visible text and progress messages are Vietnamese. Reuse app lifecycle, cancellation, stale-revision and proposal safeguards.
- Only in-scope unlocked content may change; reject scope/lock violations, do not degrade them into fallback edits.
- Never auto-apply/approve a proposal. A stale base revision must not silently overwrite newer work.
- No real render, TTS, paid API, production model call, system installation or production deploy before parent review. Use fakes for automated tests.
- Follow `docs/WINDOWS.md`: runtime/tests on Windows in an isolated snapshot under this project's run directory; not Mac. Never point deployment helper at a fake root: its remote updater hardcodes the production repository.
- Spawned coding worker uses `agy --dangerously-skip-permissions --model gemini-3.8-flash-high` interactively. No nested agents.

## Review Focus

1. Shot/chapter/all scope resolution cannot silently broaden the request, and boundaries/cards/locked overlays remain unchanged.
2. A newer storyboard revision or a pending unsaved browser edit cannot be lost during a long job or proposal application.
3. Conversation history is durable, project-isolated, escaped in the UI, and records successful/failed/cancelled jobs accurately.
4. Follow-up prompts receive previous context even when a provider session/workspace is unavailable; never claim continuation when starting fresh.
5. Existing drafts/proposals/clip assets continue to work and failed/no-op edits never mutate the saved storyboard.

## Task 1: Edit execution and scope validation

**Files:** `bti/draft/run.py` or focused new edit service, `inputs.py`, existing `workspace.py`/`compile.py`/`decompile.py`/provider only where needed; focused `tests/draft/` regressions.

- [ ] Capture current dirty baseline and file ownership before editing. Inspect and preserve media changes already present.
- [ ] Add tests for shots/chapter/all validation, empty/unknown/ambiguous scope, locked/outside-scope edits, no-op, stale revision and cancellation.
- [ ] Implement an edit run using the existing three-stage longjob/provider mechanism. `POST /draft/edit` accepts `{instruction, scope:{shots?:[],chapter?:string,all?:true},model?,base_rev?}`.
- [ ] Use the saved storyboard and timing as the edit source; do not re-draft unrelated content. If current input-loading gates prevent legitimate editing of a saved storyboard, report and resolve narrowly without weakening ordinary draft approval rules.
- [ ] Compile with strict edit behavior and refuse violations/errors rather than fallback/degrade. Preserve cards, source assets and existing anchors outside scope.
- [ ] Ensure draft and edit jobs cannot race for the same project or provider. Use unique run IDs.

## Task 2: Persistent thread and HTTP integration

**Files:** focused thread store under `bti/draft/`, `bti/editor/draft_api.py`, proposal apply integration in `bti/editor/app.py` or `proposals.py` as needed, tests.

- [ ] Test input types/limits, invalid scopes, project isolation, persistence/restart, no-op/error/cancel history and successful/partial acceptance tracking.
- [ ] Add `GET /api/projects/{pid}/draft/thread` and the edit endpoint; return longjob IDs and actionable Vietnamese errors.
- [ ] Persist instruction verbatim, resolved scope/base revision/model/job/proposal IDs, agent notes and acceptance status atomically under the project's cache.
- [ ] Reuse provider conversation only if genuinely resumable; otherwise include a bounded recent exchange history in INSTRUCTION.md. Avoid exposing full raw provider logs or secrets.
- [ ] Record acceptance after the existing proposal-apply transaction succeeds; preserve current stale/lock checks.

## Task 3: Prompt panel in step 5

**Files:** new focused JS module/CSS, `views/storyboard.js`, labels/errors where needed, relevant frontend tests.

- [ ] Add prompt textarea below preview, visible scope options and model selector, submit/cancel/progress, conversation history and open-proposal action.
- [ ] Support more than one shot via an explicit shot selector if the editor currently only selects one shot. Default to the selected shot(s), then chapter at playhead, then whole video; never silently submit all after invalid selection.
- [ ] Resolve chapters using actual normalized timing IDs; update scope when selection/playhead changes, while preserving entered text.
- [ ] Route unsaved-work decisions through existing save/confirm flow. Reuse proposal accept/reject; do not build the separate before/after comparison feature in this task.
- [ ] Guard duplicate submits and late responses, clean up polling/listeners on navigation, and safely render arbitrary prompt/agent text.
- [ ] Add meaningful frontend tests for request payload/scopes, follow-up history, busy/cancel/errors and lifecycle.

## Task 4: Verification and handoff

- [ ] Update the relevant APP_GUIDE section, preserving unrelated documentation edits.
- [ ] Run targeted fake backend/frontend tests on an isolated Windows snapshot. Provide raw log paths and exact commands, including any compatibility-only adjustments.
- [ ] Run `git diff --check`; self-review against section 7.4 and list any remaining limitations explicitly.
- [ ] Write `/tmp/bti-prompt-edit-gemini-report.md` with files changed, data contracts, test evidence and limitations; notify parent via `hc send $PARENT`.
- [ ] Stop implementation after handing off for parent review; do not deploy, rerender, call a production model or spawn reviewers yourself.
