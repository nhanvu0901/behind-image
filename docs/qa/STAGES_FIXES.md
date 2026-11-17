# STAGES_FIXES: fixes for the findings of `STAGES_ui.md`

## SU-002 (major): `PermissionError [WinError 5]` at `os.replace(<file>.wav.part, <file>.wav)` kills the voice job

**Cause.** On Windows another process (antivirus, indexer, a reader) can hold a just-written file for a moment; `os.replace` then fails and nothing retried. In `fake.py` / `chatterbox.py` the error escaped `synth`, so one chunk killed the whole job.

**Change.**
- New `bti/fsio.py`: `atomic_replace(src, dst)`. Windows: retries on `PermissionError` and on `winerror` 5 / 32 with pauses 0.05, 0.1, 0.15, 0.25, 0.4, 0.6, 0.8, 0.65 s (about 3.0 s in all), then raises the last error; other errors (for example `FileNotFoundError`) are never retried. Elsewhere: plain `os.replace`.
- All rename sites in `bti/` routed through it (one-line change each, plus the import). Full list:
  `longjob/manager.py` (job record), `library/catalogue.py` (write_json), `library/extract.py` (page jpeg, embedded image jpeg),
  `script/store.py` (json and text atomic writers: outline, narration, proposals, picks, draft's proposal writer and the voice manifest all use them), `script/runner.py` (job record),
  `voice/assemble.py` (dry wav and the m4a mix, through `_finish`), `voice/providers/fake.py` (chunk wav), `voice/providers/chatterbox.py` (chunk wav moved out of the worker folder),
  `export/render.py` (part file, joined file), `export/run.py` (final video into the export folder), `engine/storyboard.py` (storyboard save),
  `editor/frames.py` (frame cache), `editor/pipeline_api.py` (project folder to `.deleting-*`; was `os.rename`), `editor/jobs.py` (silent video to final), `editor/common.py` (json writer and `quarantine`), `editor/app.py` (two thumbnail writes),
  `media/http.py` (download), `media/_io.py` (json writer and the `.corrupt` move), `media/clips.py` (transcode), `media/assets.py` (`.corrupt` move of the index), `media/sources/bookpage.py` (page render).
  No `shutil.move` and no other `os.rename` existed.
- A test (`test_no_bare_rename_is_left_in_bti`) fails when a bare `os.replace`/`os.rename`/`tmp.replace`/`shutil.move` appears anywhere in `bti/` outside `fsio.py`.
- One failed chunk never kills the job: `fake.py` and `chatterbox.py` catch `OSError` from the finish and report `{"ok": False}` for that chunk only; `run.py` already retries such a chunk in the next part and reports it at the end. The mix and the dry wav (`assemble.py: _finish`) turn a still-failing rename into `VoiceError("voice_assemble_failed")` (a Vietnamese part error) instead of a raw `OSError`.
- Found while testing: in a multi-part run a chunk that failed in part 1 used its two tries in part 2, so `synth-retry` found an empty batch, returned silently, and the job died later in the assembler with `voice_chunks_missing`. `voice/run.py` (`synth_run`): the last part now reports the still-failed chunks (`voice_chunks_failed`, with the sentences) even when there is nothing left to try.
- Readers: the voice routes use Starlette `FileResponse` (opens the file in the response and closes it at the end of it), `export_api._iter_file` opens with `with` and closes when the generator ends, `wav_seconds` and `assemble` use `with`/ffmpeg subprocesses. Nothing keeps a handle open beyond a response. Found and fixed: `voice/align_worker.py` read and wrote JSON with `open(...)` that was never closed explicitly (now `with`). One residual: when a browser aborts a range download, the generator is closed by the server a moment later (not immediately), a few milliseconds in practice; the new retry window covers it.

**Tests.** `tests/fsio/test_fsio.py` (7: retries until success, WinError 32 without PermissionError, last error raised after about 3 s, other errors not retried, plain replace elsewhere, real file, no bare rename in `bti/`); `tests/voice/test_run.py` (two new: a chunk whose finish fails once is retried and the job is `done`; a chunk that never finishes gives `voice_chunks_failed`, not a crash). Ran on the server.

**Changes outside my files.** The one-line rename change in: `bti/library/*`, `bti/script/store.py`, `bti/script/runner.py`, `bti/engine/storyboard.py`, `bti/editor/{frames,pipeline_api,jobs,common,app}.py`, `bti/media/*` (as allowed by the rule for SU-002).

## SU-001 (cosmetic): the word "null" in the button bars

**Cause.** `acts.append(..., run ? h(...) : null, ...)` in `views/voice.js`, and the same in `views/picks.js` (`top.replaceChildren(..., cond ? banner : null)`): `Element.append(null)` writes the text "null".

**Change.** `util.js` gets `kids(...)` (drops null, undefined, false; flattens). The seven calls in the code base that could pass such a value now go through `...kids(...)`: `views/voice.js` (`acts.append`), `views/picks.js` (top bar and the beat column, `replaceChildren`), `views/library.js` (preview), `app.js` (header info). The last two were the same bug found by the new test.

**Tests.** `tests/editor_frontend/no_null_children.test.mjs`: reads every JS file, masks strings and comments, finds each `.append(` / `.prepend(` / `.replaceChildren(` and fails on a literal null/undefined/false argument, a `cond && x` argument, or a ternary with a null/undefined/false branch; plus a second test that the detector catches those shapes. Mac: all frontend tests pass (see below).

**Changes outside my files.** `util.js` (new `kids`), `app.js:180`, `views/library.js:144` (wrap in `kids`).

---

# Batch 2

## SU-001 remainder: "null" on the export page (and the class, widened)

**Why the first static test missed it.** It only looked at a conditional written inside the call (`a ? b : null`). `views/export.js` builds the page with `root.replaceChildren(h(...), staleBox(d), blockedBox(d), lastErrorBox(), planBox(d), ..., resultBox(d))`: the helpers return `null` when they have nothing to show, so the null was hidden behind a function call. `draftpanel.js` was already safe (`kids.filter(Boolean)`); the "null" the tester saw in the "Bản nháp" dialog of the old project was the top bar title (SU-010), which is the same `info.replaceChildren(..., null, ...)`.

**Change.** `tests/editor_frontend/no_null_children.test.mjs` now also (1) finds, per file, the functions that can return `null`/`undefined`/`false` (a `return null`, a bare `return`, a `: null` branch) and fails on a call to one of them passed straight to `append`/`prepend`/`replaceChildren`, (2) fails on a spread of a `.map` whose callback has a null branch, (3) has self-tests for each shape. Fixed: `views/export.js:136` (`...kids(...)`), `views/script.js:743` (`paragraphList(...)`).

## SU-003 and SU-008: a step that has output is never hidden behind the locked page

**Rule implemented.** `GET /pipeline` adds, to steps 3 to 6 (fields added, none renamed): `blocked_by` (id of the first earlier step this one stands on that is not done; `script` for voice and picks, `script|voice|picks` for the storyboard, plus `edit` for the export; steps with no data are never blockers) and `has_output` (voice cached or stale or done, picks chosen or approved, a storyboard, an export or an old video file). New state value `waiting`: the step has output and is blocked. A blocked step without output is `locked` (and says which step to do first). `bti/editor/pipeline_api.py` (`DEPENDS_ON`, `_has_output`, `_mark_blocking`, called from `compute`).
**Pages.** A waiting step opens its normal page. One banner under the stepper (`#step-banner`, painted by the shell from `labels.js: waitText(step, blocked_by)`, nine sentences, the voice/script one is the owner's text) with a button "Mở bước <step>" to the blocker. The voice page is read-only where acting is wrong (the "Tạo giọng đọc", "Đọc lại toàn bộ" and every "Đọc lại câu này" buttons are off while the narration is not approved, with the reason as title). The stepper shows `waiting` as "Chờ bước trước" (not "Xong", not "Khóa", and not "Cần làm lại": a stale voice is the reason it waits); only a running job overrides it. Every truly locked page (`views/placeholder.js`) gets a primary button to the step that has to be done first ("Mở bước Kịch bản", "Mở bước Dựng hình") from `blocked_by`; imported projects keep their "Mở bước Dựng hình" button on the no-data pages.
**Tests.** `tests/editor/test_pipeline_waiting.py` (9, server), `tests/editor_frontend/waiting_idle.test.mjs` (stepper, banner texts), e2e `SU-003`/`SU-008` checks.

## SU-004: the reason a sentence is read again is named for what it is

`bti/voice/status.py`: for the sentences whose id changed under the same voice settings, `classify_changed` gives one of `narration_changed` (its written text is new), `pronounce_changed` (the written text is the same as a sentence of the last run but the spoken text differs) or `reread` (the spoken text is the same, only the seed moved: "đọc lại câu này"); a change of voice settings is `voice_changed`, a change of tempo or music `mix_settings_changed`. Counts per reason are in `counts.by_reason`; the detail sentence is one reason, or "Cần đọc lại 2 câu: 1 do lời dẫn đổi, 1 do bảng phát âm đổi." when mixed. To tell the table from the narration the manifest now stores `wh` (hash of the written words) per sentence (`voice/chunks.py: written_hash`, written by `voice/run.py`). **A manifest made before this change has no `wh`** and keeps saying `narration_changed` (never a wrong new word); it fixes itself at the next run. Page: `labels.js` has the four sentences, `views/voice.js` adds "(N câu)" per reason when they are mixed. Tests: `tests/voice/test_run.py` (5 new).

## SU-007: one number of shots

`voice`-independent: `bti/draft/run.py` now counts the shots of the compiled storyboard once (`n_shots`), and the split once (`n_content`, `n_cards`); the proposal summary is "Bản nháp tự động: 54 cảnh: 48 cảnh nội dung, 6 thẻ" (`shots_text`), the panel says "Xong. Có 54 cảnh: 48 cảnh nội dung, 6 thẻ." from the same record, the editor opens with the same shots. (The old summary counted only the agent shots; the panel counted all.) Test: `tests/draft/test_run.py::test_one_number_of_shots_everywhere`.

## SU-009: a page notices a job started elsewhere

New `static/js/idlewatch.js` (`watchIdle`): ONE timer per page in the view's scope (cleared on unmount), every 5 s, one cheap GET (the list of jobs of its kind, not the heavy state), only while the tab is visible, no dialog is open (the draft panel inside its own dialog says `ownDialog`), the page shows no running job, the owner is not typing in a field of the page, and the last check has finished; and one check at once when the tab becomes visible again. Wired into `views/voice.js`, `views/picks.js` (suggestion jobs), `views/export.js`, `draftpanel.js` (both its places). On finding a job the page switches to its running view and the shell refreshes the stepper. Tests: `waiting_idle.test.mjs` (visible, idle, typing, no overlap, scope disposal), e2e `SU-009` for voice, export and draft.

## SU-010: "null" in the top bar of an imported project

Same class as SU-001: `app.js` `info.replaceChildren(h(...), cond ? h(...) : null, h(...))` is now `...kids(...)` (done in batch 1; the new test now guards it). The e2e check passes only when the painting is missing artist and year.

## SU-011: the draft panel introduction

There was no stylesheet for `.draft-panel` at all (the intro was the app's 11 px `.hint`). `css/edit.css` now has one: 14 px text, line height 1.55, a 10 px gap between rows. e2e check at 1700x1000 and 1280x720 (font size, gap to the next row, no overflow) and screenshots.

## Unconfirmed: the stepper said "Đang chạy" after the job had ended

After a job ends the voice, picks, export and draft pages ask for the pipeline once more a second later (`scope.timeout`), so a stepper that was painted between the job's last poll and the manifest write is corrected. Draft panel: new `onJobEnd` option, passed by the storyboard view (both mounts). e2e check 3.5 s after the job.

## Changes outside my files (batch 2)
`bti/editor/pipeline_api.py` (fields, `waiting`), `static/js/stepper.js` (waiting tag), `static/js/views/placeholder.js` (locked button), `static/js/app.js` (banner, `kids`), `static/index.html` (`#step-banner`), `static/css/shell.css` (banner, waiting chip), `static/css/edit.css` (draft panel), `static/js/labels.js` (waiting, banner sentences, reasons), `static/js/util.js` (`kids`, batch 1), `views/storyboard.js` (`onJobEnd` and `inDialog` for the draft panel), `views/script.js` and `views/library.js` (`kids`).

## Batch 2: how it was checked
- Server (one folder per run): voice 73 passed (1 deselected, the `server` one), draft 89, editor 413 (the first run had 2 failures that were the old rule: a done step with an unapproved narration, and an old video file, are now `waiting`, tests changed to say so), editor `test_shell_static` 3 (after the last JS change). Mac: `node --test` 184 pass, 0 fail.
- The tester's browser checks, run by me with `tests/e2e/stages` (own copy of the tree on the server, port 8562, fakes): **72 pass, 0 fail** (the last run). Checks added: SU-011 (both sizes), SU-003 (pipeline fields, stepper text, banner and button on voice/picks/edit/export, not the locked page, the button goes to the script), SU-009 for voice (and the stepper follows), export and draft, and "after the job ended the stepper no longer says Đang chạy"; `stepperAgrees` knows `waiting`. Screenshots at both sizes of the waiting voice and export pages, the draft panel and the draft dialog were looked at.
- Test-infrastructure changes: `tests/e2e/stages/common.mjs` asks a GET again (up to 4 times) when the ssh tunnel drops a connection ("fetch failed", seen 3 times); `tests/voice/test_run.py` and `test_api.py` now build their `LongJobManager` with an in-process heavy slot and fake probes. They used the server's real lock folder and the process list before, so while a real run holds the lock or runs ffmpeg (as today) they waited for 26 minutes and failed.

## Found while doing this
- A job this page followed itself must not count as "a job elsewhere": `jobWatcher.know(id)`. (Without it the page reloaded itself after its own job and the "play" button of a sentence went back to "▶".)
- A job that started and ended between two looks (the fake export takes seconds) is noticed too ("changed"), so the page does not keep saying the old video is out of date.

## Open
- Manifests of voice runs made before this change have no `wh`: a pronunciation change in such a project is still reported as "Lời dẫn đã đổi" until the next voice run (the real run's project, if its voice was made earlier today).
- The waiting export page keeps its "Xuất lại video" button when the export API itself allows it (the backend decides); only the voice page is made read-only.
- Picks suggestions SU-009 is covered by the unit tests of the watcher and by the same code path; there is no browser check for it (the suggestion needs the paid provider fake and the "Gợi ý" tab).
