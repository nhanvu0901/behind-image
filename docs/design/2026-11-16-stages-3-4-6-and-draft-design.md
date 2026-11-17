# Voice, picks, storyboard draft and export: design

Written by the analyst on 2026-11-16 (evening). It is the contract for the agents that build step 3 (voice), step 4 (picks), the storyboard draft agent for step 5, and step 6 (export). Facts it rests on are in `docs/design/research/R7_build_facts.md`; earlier decisions are in `2026-11-16-owner-decisions.md`, `2026-11-16-script-voice-picks-design.md` and `2026-11-16-editor-engine-design.md`. Where this file differs from those, this file wins.

## 1. What the owner asked for (2026-11-16, evening)

- Build the four missing parts so that a project can go from an approved script to a finished video.
- **Test on the Windows server only.** The Mac is for writing code. (A test process took 24 GB on the 16 GB Mac today.)
- The storyboard draft agent runs as `agy --dangerously-skip-permissions` with the model listed as "Orchestrator (Argon)" (slug `gemini-pro-orchestrator-g1-pro`). A real run of it is to be tested.

Unchanged rules: one painting per video; subtitles are never drawn into the picture; the licence gate is advisory (record and warn, never block); the comic repo is read-only; the server is production for another channel, so heavy jobs take `D:\bench\_heavy.lock`, stay under about 30 minutes each, and check for production processes and free memory first; no paid call (You.com, OpenRouter) in any test; everything the owner reads is Vietnamese.

## 2. The shape of the whole thing

```
approved narration ──► step 3 voice ──► audio/mix.m4a + timing.json ─┐
        │                                                             ├─► draft agent ──► proposal ──► step 5 (owner edits, approves) ──► step 6 export
        └────────────► step 4 picks ──► picks.json (approved) ───────┘
```

- Steps 3 and 4 both open when the narration is approved, and can be done in either order or at the same time (the voice takes about 50 minutes of machine time for a 12-minute video; the owner picks images meanwhile).
- Step 5 opens when both are done. The draft agent's result is a **proposal**, reviewed with the existing "Đề xuất" box. The agent never writes into a project.
- The same principle as the rest of the pipeline: **the model decides content; fixed code does the mechanics; the owner approves at gates.** The draft agent writes a short shot list; a deterministic compiler turns it into a storyboard.

### Freshness (who pins what)

| File | Pins | Stale when |
|---|---|---|
| `voice/voice.json` (manifest) | hash of the approved narration, voice settings | the narration's spoken text or the settings change |
| `picks.json` approval | hash of `picks.json`, hash of the approved narration | either changes |
| a draft proposal | `timing.json` hash, `picks.json` hash, `base_rev` of the saved storyboard | any of them changes (it is flagged, not deleted) |
| `export/export.json` | approved storyboard revision, signature of the audio file | the storyboard or the audio changes |

Step states: step 3 is done when the voice is fresh; step 4 when the picks approval is fresh; step 6 when the export is fresh. The stage names stay `voiced`, `picked`, `storyboard`, `approved`, `rendered`; the stage is the furthest step for which every earlier step is done.

## 3. Ownership, and how the agents fit together

| Agent | Owns (may create and edit) |
|---|---|
| WIN | `tools/deploy/**`, `tools/run_editor.bat`, `bti/proc.py`, `docs/WINDOWS.md`, Windows portability fixes anywhere once round 3 is committed (announced first) |
| CORE | `bti/longjob/**`, `config/server.json`, the integration points: router registration in `bti/editor/app.py`, step states in `bti/editor/pipeline_api.py`, stage inference in `bti/library/projects.py`, `static/js/{router,stepper,labels,errmsg}.js`, removing the three placeholder views |
| VOICE | `bti/voice/**`, `bti/editor/voice_api.py`, `static/js/views/voice.js`, `static/css/voice.css`, `tests/voice/**`, `config/voice.json` |
| PICKS | `bti/picks/**`, `bti/editor/picks_api.py`, `static/js/views/picks.js`, `static/css/picks.css`, `tests/picks/**`, and `bti/media/**` with `tests/media/**` |
| DRAFT | `bti/draft/**`, `bti/editor/draft_api.py`, `skills/storyboard_draft/**`, `static/js/draftpanel.js`, `tests/draft/**` |
| EXPORT | `bti/export/**`, `bti/editor/export_api.py`, `static/js/views/export.js`, `static/css/export.css`, `tests/export/**` |

Rules for every agent:

- A stage package exposes exactly two things to the rest of the app: `router` (a FastAPI `APIRouter`, in its `*_api.py`) and `state(project_dir) -> dict` (in the package), where the dict has at least `{"state": "none|running|stale|done", "detail": str}`. A view module exports the same `mount`/`unmount` shape as `views/script.js`. Nobody but CORE edits the integration points; CORE wires a stage in only through those two things.
- Reuse what exists: revisions and `base_rev` (409 on mismatch), atomic writes and the single file loader that raises `DataError` (409 `data_error`), the per-project lock (take it only for the final write of a result, never across a long computation or a network call; after taking it, check that the project still exists), `{detail, code}` error answers, `errmsg.js` and `labels.js` for every word on screen, the lifecycle and queue helpers of the existing views.
- Every external program (the voice worker, the aligner, ffmpeg, the engine's command line, `agy`) is reached through a small provider with a **fake** twin, so that tests need no GPU, no model, no network and no minutes of compute. Real programs are exercised by a few tests marked `server` that run only on the Windows server.
- Paths of other machines never appear in code: they come from `config/server.json`.
- Tests are run on the server (`tools/deploy/remote_test.sh`, made by WIN). On the Mac an agent may compile and import its own modules, nothing more.

## 4. Shared: long jobs and the heavy slot (CORE)

The script runner stops a job after 30 minutes and the editor's runner cannot cancel; neither knows the server's lock. A voice run and an export are longer than that, so there is one new runner.

```python
from bti.longjob import manager, Part

job = manager.start(kind="voice", pid=pid, project_dir=d, parts=[
    Part(key="synth-1", title="Đọc phần 1/4", run=fn, heavy=True, est_seconds=900),
    ...], meta={...})            # raises Busy if this project already runs a job of this kind

# fn(ctx) -> dict | None
# ctx.progress(fraction, note="")   ctx.log(text)   ctx.cancelled() -> bool
# ctx.run_process(cmd, cwd=None, env=None, on_line=None) -> int    # child in its own process group, killed as a tree on cancel
# ctx.workdir  (a scratch folder for this job, under the project's cache)

manager.get(job_id) -> {id, kind, pid, state, progress, parts: [{key, title, state, progress, note, started, ended, error}],
                        error, error_code, result, created, log_tail}
manager.cancel(job_id)      manager.active(pid, kind=None)
```

- States: `queued | waiting | running | done | error | cancelled | interrupted`. `waiting` means a heavy part is waiting for the machine to be free; the note says so in Vietnamese.
- A part marked `heavy` runs inside the heavy slot: one heavy part at a time in the whole app, and on the server also the `D:\bench\_heavy.lock` protocol from the benchmark rules (check free virtual memory and production processes; atomic `mkdir`; `owner.txt` with our host, process id and time; retry every 60 s; release in `finally`; never remove a lock that is not ours; a lock of ours whose process is dead is released at start-up). Off the server it is an in-process lock only.
- A part has a hard limit of 35 minutes; plan parts for about 20. A job has no total limit.
- Resume: starting the same kind of job again is the resume. Each part decides for itself whether its output already exists and is current, and then reports done at once.
- Records persist under `projects/<pid>/cache/longjobs/`; after a restart a running job is reported as `interrupted`.
- Routes: `GET /api/longjobs/{id}`, `POST /api/longjobs/{id}/cancel`, `GET /api/projects/{pid}/longjobs?kind=`.

`config/server.json` has one block per platform (`"windows"`, `"default"`): the lock folder, the memory floor, production process patterns, the comic voice worker (Python, worker script, reference voice, the four synthesis numbers), the aligner's Python and model, render threads and part length.

## 5. Step 3: voice (VOICE)

**Input:** the approved narration. **Output:** `audio/mix.m4a` (AAC, 48 kHz stereo, about -15 LUFS, true peak under -1.5 dBTP), `audio/voice.wav` (the dry voice, for alignment), `timing.json`, and the manifest `voice/voice.json`.

1. **Spoken text.** The narration keeps the written text. `bti/voice/speak.py` turns each sentence into what is said: years, numbers, ordinals, centuries, currency, symbols, common abbreviations, Roman numerals for kings and popes. A per-project table `voice/pronounce.json` (written form to spoken form, edited on the page) is applied first. Pure functions, heavily unit-tested.
2. **Chunks.** One chunk per sentence, with the comic's rule: a sentence under 40 characters joins the next; over 280 characters is cut at a comma. Our own copy of that rule; nothing is imported from the comic repo. Chunk id = hash of spoken text + voice settings + seed. The seed is derived from the text hash (not from the position), so an unchanged sentence always gives the same audio; "Đọc lại câu này" stores a new seed for that sentence in the manifest.
3. **Synthesis.** Chunks without a cached file (`voice/chunks/<id>.wav`, 24 kHz mono) are grouped into heavy parts of about 4,000 characters of spoken text (about 20 minutes of compute at the measured 4.1 seconds per second of audio). Each part writes a job file and runs the comic's worker script with the comic's voice Python, both read-only, with the reference voice and numbers from the config, and one explicit seed per chunk. A chunk the worker reports as failed is retried once in the next part and then reported by sentence.
4. **Assembly** (light): chunks in order with silences from `config/voice.json` (between sentences 0.20 s, between beats 0.45 s, before a chapter 1.0 s, or 3.0 s when the chapter has a card), optional tempo 1.00 to 1.20, the same quiet pad with ducking that the benchmark used (can be switched off), two-pass loudness normalisation. The exact start and end of every sentence in the final audio is recorded.
5. **Word times** (heavy): forced alignment with faster-whisper on the server, sentence by sentence inside the known sentence span; script words that the recogniser did not return are interpolated between their neighbours. If the aligner is not installed, word times are spread evenly inside each sentence and the manifest says `"timing_quality": "even"`; otherwise `"aligned"` with the match rate.
6. **`timing.json`:** `{duration, words: [{w, s, e}], beats: [{id, chapter, text, start, end, w0, w1}], chapters: [{id, name, start, end, card}]}`, the shape the engine already reads, with the narration's beat and chapter ids added.

After a narration change only the changed sentences are spoken again; assembly and alignment are redone. Storyboard anchors are word indexes with the word's text, so the engine already reports the ones that no longer match.

**Page.** State and progress by part with an honest estimate; "Tạo giọng đọc", "Đọc lại phần đã đổi", cancel; the script by chapter with a play button per sentence and "Đọc lại câu này"; the pronunciation table; tempo and pad; a player for the whole mix; what is stale and why.

**Routes.** `GET /api/projects/{pid}/voice`, `POST .../voice/generate {scope: "all" | "changed" | [chunk ids], reseed?: [chunk ids]}`, `PUT .../voice/settings`, `GET .../voice/chunks/{id}.wav`, `GET .../voice/mix`.

Providers: `chatterbox` (real, server), `fake` (short tones whose length follows the text, for tests); aligner `whisper` (real) and `even`.

## 6. Step 4: picks (PICKS)

**Input:** the approved narration and the project's dossier. **Output:** `picks.json` (`bti.picks/1`) and image files under `media/`.

```json
{"schema": "bti.picks/1", "main_asset": "A",
 "assets": {"A": {"file": "media/arnolfini.jpg", "kind": "image", "title": "...", "artist": "...", "year": "...",
                  "width": 4386, "height": 6000, "credit": {"source": "...", "source_url": "...", "author": "...", "licence": "...", "flag": null},
                  "regions": {"MIRROR": {"x": 2210, "y": 1730, "rx": 160, "ry": 160, "label": "Gương"}}}},
 "beats": {"b0007": {"items": [{"asset": "A", "region": "MIRROR", "role": "detail", "note": ""}], "status": "picked", "note": ""}},
 "approval": {"approved": false}}
```

- `assets` has the same shape as `storyboard.assets`, so the draft compiler copies it as it is. The flow goes one way: picks feed the draft; regions later tuned in step 5 live in the storyboard. On a re-draft the compiler merges the two, the storyboard winning for a key both have.
- `role` is one of `main, detail, context, compare, document, map, video`. `status` is `todo | picked | skip`.
- **The main painting first.** A new project has no pixels. The page opens on choosing the main image: results from Wikimedia Commons and the Met for the title and artist, with pixel size and licence, plus the page images of the books (rendered from the PDF by `bti/library/extract.py`) and upload.
- **Candidates for a beat:** regions of the main painting (drawn on the page; the detail names `D1…` of the dossier are offered as names); a search with the beat's `show` words as the first query (Commons, Met); book page images; upload; and "Gợi ý thêm" which asks You.com for visual suggestions (`bti/media/research.py`) for the chosen beats. That button says it costs money, runs only when the owner clicks it, and is never called by a test (fake provider).
- **The licence gate becomes advisory, as decided:** an import is never refused for its licence or for being under 1200 px; the asset gets `credit.flag` (`rejected | unknown | small | null`) and the page shows it. This also changes the storyboard view's import, which uses the same code.
- **Approval:** needs a main asset. Beats without picks are listed as a warning, not an error (the draft will use the main painting there).
- **Second batch, after the above works on the server:** video clips (wire `bti/media/clips.py`: a pasted link with in and out times), and more sources (Pexels, Pixabay).

**Page.** Top: the main painting. Left: chapters and beats with a count of picks. Middle: the beat's text, facts and `show` words, and its tray (reorder, remove, set region, role, note). Right: candidates in tabs (Tranh chính, Tìm kiếm, Sách, Gợi ý, Tải lên). "Duyệt chọn hình".

**Routes.** `GET/PUT /api/projects/{pid}/picks`, `POST .../picks/search`, `POST .../picks/import`, `GET .../picks/book-images`, `POST .../picks/import-book-image`, `POST .../picks/upload`, `PUT .../picks/assets/{key}/regions`, `POST .../picks/suggest` (a long job), `POST .../picks/approve`.

## 7. The storyboard draft agent (DRAFT)

### 7.1 What the agent writes: a draft spec, not a storyboard

One file per chapter, `out/c03.json`:

```json
{"schema": "bti.draft/1", "chapter": "c03", "shots": [
  {"beat": "b0031", "start_word": 512, "technique": "CAM-05", "intent": "point_at",
   "slots": {"image": {"asset": "A", "region": "MIRROR"}},
   "params": {},
   "overlays": [{"technique": "HI-01", "start_word": 518, "end_word": 524, "slots": {}, "params": {}}],
   "note": "the mirror is named here"}]}
```

- `start_word` is an index into the word list of `timing.json`. A shot runs until the next shot's first word. That is all the agent says about time.
- `params` holds only what the agent wants to differ from the defaults.

### 7.2 What fixed code does: `bti/draft/compile.py`

It turns the chapter files into one full `bti.storyboard/1` document: canvas, timing, audio and assets; shot ids (existing ids kept on a re-draft, new ones never reuse an old id); start anchors `{w, off, text}`; tiling; default slots and params from the engine's `default_params` for each technique and its picked asset or region (this is where camera key lists come from); chapter cards in the silences the voice left for them; `source: "agent"`; locked shots of the saved storyboard copied through untouched. Then `validate` and `draw_check`. Issues are reported in the agent's terms (chapter, shot number, field), in plain English, with the engine's code.

`python -m bti.draft.check <workspace>` runs exactly that and prints the issues; `python -m bti.draft.defaults <technique> [--asset A --region R]` prints the defaults and bounds of a technique; `python -m bti.draft.still <workspace> --shot c03:4 -o look/c03_4.jpg` draws one small frame of a compiled shot so the agent can look at its own work.

A second provider, `auto`, needs no model: one shot per beat, the first pick of the beat (or the main painting), techniques rotated among the registry's core ones by the beat's `show` and role. It is the fallback, the baseline to compare the agent with, and what the tests use.

### 7.3 The run

- **Workspace:** a new folder in the system temp directory, never inside the project or the repo. It holds copies only: `TASK.md` (the instructions: the job, the spec format, the rules below, one worked chapter as an example), `inputs/beats.json` (chapters and beats with text, facts, `show`, start, end, `w0`, `w1`, the picks of each beat), `inputs/words.tsv` (index, word, start, end), `inputs/assets.json`, `images/<key>.jpg` (copies no larger than 1568 px on the long side, with the scale to source pixels in `assets.json`), `inputs/techniques.md` (a compact description of the 71 techniques generated from the registry: id, kind, intents, when to use it, how often the reference channel uses it, slots, params with type, bounds and default), `inputs/style.json`, and `inputs/current/` (the saved storyboard's shots by chapter, with `locked` marked) on a re-draft.
- **Command:** `agy --dangerously-skip-permissions --model gemini-pro-orchestrator-g1-pro --input-format stream-json --output-format stream-json`, working directory = the workspace, the prompt on standard input ("Read TASK.md in this folder and do the task"), an environment that holds only what the program needs plus the path of our Python for the three helper commands. One agent run at a time. Time limit 30 minutes by default; cancel kills the process tree. The model can be changed in the dropdown; the default is the one above.
- **Rules given to the agent (TASK.md):** work only in this folder; write `out/<chapter>.json` for every chapter and `out/notes.md`; run the check until it reports no error; every beat is covered by at least one shot; follow the pacing numbers of `style.json` (median shot about 7 s, none under 1.5 s); use the picks of a beat first; when a beat has no pick, stay on the main painting and move (zoom, detail, comparison) rather than hold a still; use regions that exist, and when a detail has no region, look at the image and add one (name, centre and radius in source pixels) to `out/regions.json`; prefer the core techniques, use occasional and rare ones where the beat calls for them, leave the Shorts-only ones out; never touch a locked shot; never put narration text on screen as subtitles.
- **Because the run is unattended and auto-approved, it is contained by construction and then checked:** the project and the repo are not in the workspace; only `out/` is read back; before and after the run a listing (names, sizes, times) of the project folder is compared, and on the server `git status --short` of the comic repo as well; any difference marks the run `tampered`, nothing is taken from it, and the owner is told. This does not prevent a determined mistake; it makes one visible at once. The owner chose this mode knowing it.
- **Afterwards:** compile, validate, draw check. If errors remain, one more turn is sent to the same conversation with the issue list, at most twice. What is left after that is kept as "incomplete" items for the owner. The result is written as a proposal `projects/<pid>/proposals/draft_<time>.json` with `author: "agent:agy:<slug>"` (or `agent:auto`), the summary from `out/notes.md`, and the hashes it was made from.
- **First draft of a new project:** there is no saved storyboard to compare with. `apply` with `accept: "all"` on a project without a storyboard adopts the proposal's document as the first `storyboard.json` (DRAFT asks CORE for this change in `bti/editor/proposals.py`).
- **Re-draft:** whole video, or one chapter ("Dựng lại chương này").

**Page.** A small panel in step 5 (`draftpanel.js`, hooked in by CORE): what is ready (voice, picks), the model dropdown, "Dựng bản nháp", progress read from the event stream (step count, last action, issues left), cancel, and then the proposal opens in the existing box.

**Routes.** `GET /api/projects/{pid}/draft` (readiness, last run), `POST .../draft/start {provider: "agy" | "auto", model?, chapters?}`, progress through the long-job routes.

**The live test** (owner asked for it): one real run on the server for one chapter of a real project, then the whole video, with the transcript of events kept under the project's cache. It needs `agy` signed in on the server and the app running in the owner's desktop session (see section 9).

### 7.4 Editing by prompt (owner's request, 2026-11-16, late evening)

The owner does not want to learn the editing tools. In step 5 they type what they want ("ở đoạn nói về chiếc gương, zoom chậm hơn và thêm vòng sáng quanh gương") and the agent changes that part. This is the draft run with two more inputs, so it reuses everything in 7.1 to 7.3:

- **Inputs added to the workspace:** `INSTRUCTION.md` (the owner's words, unchanged, plus the scope) and `inputs/current/` (the saved storyboard as draft specs by chapter, each shot marked `in_scope`, `locked`, or neither). The scope is the selected shots, or the chapter at the playhead, or the whole video; the default is the smallest that contains the selection.
- **What the agent may change:** only shots in scope, plus regions it adds. Everything else must come back identical; the compiler checks this and refuses a result that touched anything outside the scope or any locked shot.
- **What it must do when the request cannot be met** with the 71 techniques and the images the project has (a new image, a change to the narration or the voice): change nothing and say so in `out/notes.md`, with what the owner should do instead. A question back to the owner is a valid result.
- **Result:** a proposal, as always. The page shows, for each changed shot, the frame before and after, the agent's one-line reason, and a preview clip of the changed range; the owner accepts all, some, or none. Nothing in the project changes before that. Undo works on an accepted change like on any other edit.
- **Conversation:** one thread per project, kept under the project's cache: each instruction, the agent's notes, what was accepted. A follow-up ("nhanh hơn chút nữa") is sent to the same `agy` conversation when it is still available, and otherwise starts a new run with the last exchanges copied into `INSTRUCTION.md`.
- **Page:** a prompt box under the preview in step 5, with the scope shown in words ("3 shot đang chọn", "chương 2", "cả video") and the thread beside it. The manual tools stay, as the way to fine-tune.
- **Routes:** `POST /api/projects/{pid}/draft/edit {instruction, scope: {shots?: [...], chapter?: "c02", all?: true}, model?}` (a long job), `GET /api/projects/{pid}/draft/thread`.
- **Order of work:** after the first real draft run has worked on the server, because how fast and how reliable the agent is decides the details (whether a one-shot change takes twenty seconds or three minutes).

## 8. Step 6: export (EXPORT)

**Input:** an approved storyboard, the mix, the timing. **Output:** under `projects/<pid>/export/`: `<slug>.mp4`, `<slug>.srt`, `description.txt`, `chapters.txt`, `export.json`.

1. **Render in parts** (heavy): the timeline is cut at shot boundaries into parts of about 240 s of video (about 8 minutes of compute each at the measured 2.0 minutes per minute). Each part is `python -m bti.engine render --quality final` as a child process, its progress lines read. A part whose file exists for the same storyboard revision and range is not redone. Parts are joined by stream copy; the frame count is checked against duration × 30.
2. **Subtitles:** cues from the timing words: at most two lines of 42 characters, broken at sentence ends and pauses, no cue under 0.8 s or over 6 s, no two cues overlapping. Written as a sidecar `.srt` and as a soft `mov_text` track. Never drawn into the picture.
3. **Mux:** video by copy, the mix by copy, the subtitle track, chapter marks from `timing.chapters`, `+faststart`.
4. **Description:** title; the artwork line; chapters as `mm:ss Title`; the books used; one credit line per asset that appears in a shot (title, author, licence, link), with a note on any flagged one; "Subtitles available". Wording comes from a template file so the new channel identity can change it later.
5. **Checks, shown as a report card:** duration, frame count, integrated loudness and true peak measured from the file, subtitle track present, cue count, file size.

**Page.** What will be made and how long it should take; "Xuất video"; progress by part; cancel; the result with a player, the report card, the description with a copy button, and links to the files. A stale export says why.

**Routes.** `GET /api/projects/{pid}/export`, `POST .../export/start`, `GET .../export/files/{name}` (with range requests).

## 9. The Windows server (WIN)

Known state (R7, section E): no NVIDIA card, so voice and render run on the processor; `agy` 1.5.9 is installed; the project folder is a plain copy with an empty virtual environment; the unfinished portability work sits in `git stash@{0}`.

- **Environments, all inside `D:\code\behind-the-image\`:** `.venv` with `requirements.txt`; `.venv-align` (Python 3.12) with faster-whisper and its model cache in the project folder. Nothing is installed system-wide and nothing in the comic repo changes.
- **Deploy:** one command from the Mac that syncs code (and, on request, data) and takes a small lock so two agents do not sync at once. `tools/deploy/remote_test.sh <pytest arguments>` syncs, then runs pytest on the server and brings the output back.
- **Running the app:** bound to `127.0.0.1:8560` on the server; reached from the Mac through `ssh -N -L 8561:127.0.0.1:8560 winbox-lan`. No port is opened.
- **`agy` and the desktop session:** over ssh, `agy models` answers "Please sign in" although the owner has used the program at the server's desktop. If the sign-in is kept in the desktop session's credential store, the app must run in that session for the script button and the draft agent to work. Two ways, the owner's choice: a scheduled task that runs only while the owner is logged on and is started on demand (a system change, needs the owner's yes), or the owner starts a `.bat` at the desktop. Until then the app is started the way the benchmark jobs were, and everything except real `agy` calls can be built and tested.
- **Order:** first the environments and a run of the existing suites on the server, to learn what is not portable; after round 3 is committed, the stash is applied and the rest made green on Windows.

## 10. Testing

- Unit tests with fakes for every pure part (spoken text, chunking, assembly arithmetic, timing merge, picks document, draft compiler, cue building, description, part planning, the long-job runner and the heavy slot with a fake lock folder).
- Tests marked `server`, run only on the server, short and under the heavy slot: speak two sentences for real and check the files; align them; render five seconds at final quality and mux; one `auto` draft of a real project end to end; one real `agy` draft once the sign-in works.
- One journey test on the server when all parts are in: a small real project from approved narration to an exported file, with the `auto` draft.
- Browser checks for the three new views run from the Mac's headless Chrome against the server's app through the tunnel.

## 11. Not in this build

A new visual identity (needs the channel name), the Shorts-highlight skill, music beyond the pad, automatic region proposals by a vision model outside the draft run.
