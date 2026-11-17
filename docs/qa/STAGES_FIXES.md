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
