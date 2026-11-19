# Five small defects left open by earlier builds (worker `followups`, 2026-11-18 and 19)

Brief: `.scratch/agy_tasks/followups/TASK.md`. No model call of any kind (no `agy`, no `claude`); every test uses fakes, fixtures and the mock
provider. Python ran only on the server in the snapshot `followups` (`BTI_SSH_HOST=winbox-cmd tools/deploy/snapshot_test.sh followups -- <folder> -q -p no:cacheprovider`,
one folder per run). Nothing was written in the server's main folder or library, port 8560 and 8550 were never used (the browser probes used 8572),
no git command that writes was run. Each item: the cause first, then the fix, then the test that fails without it.

## 1. The list of proposals showed a raw agent id

- **Cause.** `bti/editor/static/js/proposals.js` printed `p.author` and `data.proposal.author` as stored. The server stores `agent:<model id>`
  (`agent:claude:claude-opus-5-5@high`, `agent:agy:gemini-3.8-flash-high`, `agent:auto`) and nothing on the page translated it.
- **Fix.** Two pure functions in `agentlogic.js`: `authorLabel(info, author)` and `proposalLine(info, p, withId)`; the words in `labels.js`
  (`AGENT_LABELS.author`). A listed agent shows its label ("Opus 5.5 High", "Gemini 3.8 Flash"); `agent:auto` shows "Dựng tự động"; `human` shows
  "Bạn"; an agent the list does not offer shows "Agent <model without the runner name>"; any other text stays as stored; a missing author is left out
  (no "null | null"). The stored form may also be an agent id (`agent:opus`). `proposals.js` loads `GET /api/agents` (a failure to load it only means
  the fallback above) and builds both lines with `proposalLine`.
- **Files.** `bti/editor/static/js/agentlogic.js`, `labels.js`, `proposals.js`.
- **Test.** `tests/editor_frontend/agentlogic.test.mjs` (4 new tests, one of them reads `proposals.js` and fails if it reads `.author`). Against a copy of
  the HEAD `static/js` the file does not even load (`authorLabel` is not exported).

## 2. "Claude Code is too old for this model" had no sentence of its own

- **Cause.** `claudecode.classify` knew auth, limit, unknown model and timeout, and nothing else. The answer of the server's Claude Code 2.1.233
  (`Claude Code 2.1.233 does not support this model; version 2.1.280 or newer is required. Run 'claude update'`) matched none of them, so it became
  `claude_error` (the English text under "báo lỗi", or "Thử lại, hoặc dùng Dựng tự động") and, when the program framed it with `api_error_status` 404,
  `claude_model` ("Chọn mô hình khác": wrong advice). I could not tell which status the real answer carried, so the tests feed it as a result with
  status 404, 400 and none, and as a plain stderr line.
- **Fix.** New code `claude_outdated`, kind `config`, decided first in `classify` (`outdated_versions`, `outdated_message` in
  `bti/script/providers/claudecode.py`). The sentence is exactly the brief's, and a version the answer does not state is left out:
  "Claude Code trên máy chủ quá cũ cho mô hình này (cần bản 2.1.280 trở lên, đang là 2.1.233). Chạy `claude update` trên máy chủ rồi thử lại."
  A bare "does not support this model" with no mention of Claude, a version or `claude update` is not taken for it. It reaches the page like the other
  `claude_*` codes: the single call and the agent in a folder carry it (`.code`, the draft provider's `classify`), `bti/draft/run.py` has the static sentence
  in `VI` and uses the runner's sentence (with the versions) for this code (`vi`, `rate_limit_sentence(..., message)`), `errmsg.js` has the static
  sentence in `STAGE_CODES.draft` and `stageJobErrorText` shows the server's sentence with the versions, a failed script job (kind `config`) shows the
  server sentence as it already does, and `editlogic.js` lists the code in `EDIT_CODES` (one line). It is not a quota: it is in no `QUOTA_CODES`, no sentence
  says "hết hạn mức", the quota card is not offered.
- **No probe sees it.** The minimum version is only in the answer of a failed call (`claude auth status` and `--help` do not carry it), so the availability
  reason of `GET /api/agents` is unchanged.
- **Files.** `bti/script/providers/claudecode.py`, `bti/draft/providers/claudecode.py`, `bti/draft/run.py`, `bti/editor/static/js/errmsg.js`, `editlogic.js`;
  tests: `tests/script/fake_claude.py` (modes `error_text`, `stderr_text`), the new fixture `tests/script/fixtures/claude/too_old.txt` (the answer, exactly),
  `tests/script/test_claudecode.py`, `tests/draft/test_claude_runner.py` (single call, agent run, draft job, fast and deep edit turns),
  `tests/editor_frontend/errmsg.test.mjs`.
- **Proof.** Both Python files against the HEAD sources: `16 failed, 146 passed, 1 skipped, 1 warning in 51.10s` (the fast edit showed `claude_model`
  with "Chọn mô hình khác"); `errmsg.test.mjs` against the HEAD `static/js`: `pass 16`, `fail 2`.

## 3. Old browser probes selected the model through a control that no longer exists

Reality found first: the four old probes did not start the app on the server; they started a LOCAL server on the Mac from the worktree's `projects/` and
`library/`, and the worktree has no library data, so none of them could run. They were ported to the same second-instance-on-the-server launcher as the
stages and agent probes. What was built for it:

- `tests/e2e/shell_library_script/remote_server.mjs` (new): `startServer`, `own` (the same instance, projects started over), `writeFile`, `exists`, `stop`,
  `restart`, `ensureUp`, `closeServer`; retries a GET the ssh tunnel dropped; sets the machine default agent to "Gemini 3.8 Flash" (the mock agent) as the settings
  box does (without it a script job runs the role's real `agy` model and is refused); `--reuse-server`, `--keep-server`.
- `tests/e2e/stages/launch.py`: the canned answer to an edit now follows the CURRENT fast-edit briefing (the old one looked for a heading of an older template, so
  every edit ended `spec_invalid`; this was the cause of `prompt_edit.mjs` failing its edit steps); `arnolfini_edit` and `technique_lab` are copied too; three
  test-only routes in this launcher only (`POST /api/_e2e/reset`, `PUT /api/_e2e/file`, `POST /api/_e2e/exists`; the app answers any unknown GET under `/api`
  with "not found" before a route added here, so `exists` is a POST).
- `tests/e2e/stages/remote.mjs`: port and folder can be set (`BTI_STAGES_PORT`, `BTI_STAGES_SUFFIX`, so two workers do not collide), and a real bug fixed: the
  20-second timer of `stopRemote` killed the NEW instance after a restart (`/start` within 20 s), which made every probe that stops and restarts the app lose it.
- `tests/e2e/shell_library_script/lib.mjs`: a closed page now fails what waits on it, and an unexpected Chrome exit is logged (a promise tied to a closed page
  never settles and ends the probe silently: "unsettled top-level await").

Per file (results exactly as printed are in section 6):

- `stages/prompt_edit.mjs`: kept; `launch.py` fixed as above; its last check (preview height) is item 7 below.
- `shell_library_script/run.mjs`: ported (the model select is replaced by the agent select). The stall at U1-008 seen in the first run did not come back;
  most likely a page or tunnel that closed, which can no longer hang the probe.
- `shell_library_script/run_extra.mjs`: ported; U1-015 dropped (the old "other model" dialog after a rate limit; the one-button quota card is checked by
  `tests/e2e/agent/agent_select.mjs`); fixed waits (library search, Enter in a dialog, Lưu) that assumed a local server's speed.
- `round2/run.mjs`: ported; R2U-P6 and R2U-P6b dropped (the note under the old model list and its "Thử lại" are gone; an agent that cannot run is shown with its
  reason by the agent select, checked by `agent_select.mjs`); the checks that stop the app wait for the message (the ssh tunnel needs 2 to 3 s to tell that the
  app is gone; a fixed sleep of 1 to 2 s was shorter than that).
- `round3/fixes.mjs`: ported (`common.mjs` `setup(size, {remote: true})`; the corrupted picture is written through the `_e2e` route); F-006 rewritten for the
  agent select (the old premise, "the buttons wait for the model list", is gone with the list). `round3/run.mjs` was not in the list and is untouched.

## 4. A picture's recorded size in a saved storyboard overrode the picks

- **Cause.** `bti/draft/compile.py::_merge_assets` copied the picks' assets and then let the saved storyboard's copy of each asset replace the whole entry, so a
  storyboard drafted before a size correction kept the wrong size for ever and `asset_size_mismatch` never cleared on a new draft.
- **Rule and fields.** The facts of the stored file always come from the picks: `file`, `kind`, `width`, `height`, `original_width`, `original_height`, `duration`
  (`FILE_FACTS`; these are all the fields of an asset record that describe the file: `title`, `artist`, `year`, `credit` and `regions` describe the picture or were
  added by people, and `mime` and the like do not exist in the picks). A fact the picks do not state is dropped from the saved copy instead of kept from another file.
  Everything else on the saved copy is kept as before (regions, title, artist, year, credit, any field only the storyboard has, and a picture only the storyboard
  has). The saved copy's regions are scaled by new size / old size with `bti.media.assets.scale_regions`, the helper `reconcile_sizes` now uses too (x and rx by the
  width factor, y and ry by the height factor; no scaling when the old size is unknown).
- **Known limit.** The camera keys of kept shots (locked shots, chapters that are not re-drafted) stay in the old size space; only the asset record and its regions follow.
  So the warning clears while such shots may still be framed for the old size.
- **The advice.** `sbissues.js` `asset_size_mismatch` now ends "Dựng nháp lại để cập nhật kích thước hình." (true now: a draft takes the stored size from the picks).
- **Files.** `bti/draft/compile.py`, `bti/media/assets.py`, `bti/editor/static/js/sbissues.js`; tests `tests/draft/test_size_follow.py` (the test that pinned the old
  behaviour is replaced by four new ones, one is `test_drafting_again_clears_the_size_warning`: an auto draft job, the proposal saved as the storyboard, the warning gone),
  `tests/editor_frontend/sizefollow.test.mjs`.
- **Proof.** `tests/draft/test_size_follow.py` against the HEAD `compile.py`: `3 failed, 12 passed in 2.72s`; with the fix `15 passed in 3.13s`.

## 5. A library test failed on the real library

- **Which side was wrong.** The builder. `docs/design/2026-11-16-library-design.md` lists `artist` among the keys of every work (only `headline` is marked optional) and
  says an unknown artist is "artist null"; `year` is always stored (null when unknown). But `catalogue._public` wrote only the keys a work had, and `artist` is set only when a
  source names one. On the server's built library 45 of 340 works have no `artist` key (hagen_wgps 1, grovier_nws 7, brookehitching_mad 25, dasal_artcurious 12; none has it
  present and empty). The readers already used `.get("artist")`.
- **Fix.** `_public` always writes `artist` (null when none, after `title` as the spec orders it); `catalogue.load_works` reads an old file's missing key as null, so every reader
  sees the documented shape before any rewrite. `bti/library/catalogue.py` only.
- **Tests.** `tests/library/test_library.py`, three new (use the tmp `lib` fixture): `_public`, `load_works` on an old record, and `regroup()` rewriting an old works file.
  Against the HEAD `catalogue.py`: `4 failed, 117 passed in 1.43s` (the three new ones and `test_works_json_shape`).
- **Still owed, the owner's decision.** `tests/library/test_library.py::test_works_json_shape` reads the works.json files on disk, so it stays red on the server's real library until
  they are rewritten there. Cheap way: `python -m bti.library regroup` (no PDF access, under a minute, it rewrites works.json and artworks.json through the fixed `_public`; it also
  recomputes the artwork groups and aliases, so look at the result). Heavy way: the full `python -m bti.library build` (re-reads the PDFs). I ran neither and never wrote to the library.

## 6. Results

@@RESULTS@@

## 7. The two fixes the coordinator added

- `bti/editor/static/js/editlogic.js`: `'claude_outdated'` in `EDIT_CODES` (one line); `editlogic.test.mjs` `tests 23 / pass 23 / fail 0`.
- `bti/editor/static/css/edit.css`: the preview was under 300 px at 1280x720. **Cause:** in `#preview-tools` the identity picker (label, select, note) and the two checkbox labels wrapped,
  so the row was 60 px tall instead of about 36 and the stage got 283 px. **Fix:** the row stays one line (`flex-wrap: nowrap`, items keep their size, only the picker's note shrinks with an
  ellipsis, what still does not fit scrolls sideways with no scroll bar, which would take height). Measured: 1280x720 row 32 px, stage 311 px; 1500x900 36 px / 343 px; 1920x1080 36 px / 523 px.
  `prompt_edit.mjs` printed `69 pass, 0 fail`.

## 8. What I could not verify

@@UNVERIFIED@@
