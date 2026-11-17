# BUILD: step 3, the voice (VOICE agent)

Status 2026-11-16: written, compiled and imported on the Mac. **No test has been run**: `docs/WINDOWS.md` does not exist yet (server not ready). Run on the server with `tools/deploy/remote_test.sh tests/voice` (and `-m server` for the real ones, under the heavy slot).

## What exists

| Path | What |
|---|---|
| `config/voice.json` | silences, tempo range, pad, chunk sizes, part size, estimate numbers, loudness, aligner options, default provider |
| `bti/voice/speak.py` | written text to spoken text, as `Unit`s (written tokens + spoken words): numbers, years, ordinals, decades, ranges, currency, percent, time, degrees, fractions, abbreviations, `BC/AD`, Roman numerals for kings and popes, pause dashes, pronunciation table first |
| `bti/voice/chunks.py` | our own copy of the comic's chunk rule (sentence per chunk, under 40 chars joins the next, over 280 cut at a comma), per beat; chunk id = hash(spoken, voice settings, seed); seed from the text hash; silence before each chunk |
| `bti/voice/plan.py`, `planner.py` | the plan (chunks, settings, signatures) and the synthesis parts (about 4,000 characters each, estimate from the measured 4.1 s per audio second) |
| `bti/voice/providers/` | `chatterbox` (real; the comic worker as a child process, one explicit seed per chunk), `fake` (tones, 0.05 s per character) |
| `bti/voice/assemble.py` | layout in whole samples, per-chunk tempo (ffmpeg atempo), 8 ms fades, numpy pad with ducking, two-pass loudnorm, AAC 192k 48 kHz stereo; returns every sentence's span |
| `bti/voice/align.py`, `align_worker.py` | aligners `whisper` (faster-whisper in the aligner's own Python, sentence by sentence inside its span) and `even`; difflib merge, interpolation, written-word times |
| `bti/voice/timingfile.py` | `timing.json` (`duration, words, beats, chapters`), checked with the engine's `shape_problem` |
| `bti/voice/run.py` | the long job: `synth-N` (heavy), `synth-retry` (heavy), `assemble`, `align` (heavy only with whisper); `is_done` on every part; reseed |
| `bti/voice/status.py`, `__init__.py` | `describe()` (everything the page shows) and `state(project_dir)` |
| `bti/editor/voice_api.py` | `router` (reads `app.state.projects_root`) and `make_router(...)` for tests |
| `bti/editor/static/js/views/voice.js`, `css/voice.css` | the page |
| `tests/voice/` | see below |

### Files in a project
`voice/voice.json` (manifest: `seeds`, `plan{assemble_sig,text_hash,chunk_ids,settings}`, `assembled{sig,spans,duration,loudness}`, `timing{sig,quality,match_rate}`, `chunks[]` with final start/end, `timing_quality`, `duration`, `loudness`), `voice/settings.json` (`tempo`, `pad`), `voice/pronounce.json`, `voice/chunks/<id>.wav`, `audio/voice.wav` (dry, 48 kHz mono), `audio/mix.m4a`, `timing.json`.

### Decisions I took where the contract was silent
- Chunks never cross a beat (so every beat owns whole chunks and starts exactly). Settings that change a chunk's sound (voice numbers, reference file name, provider) are part of the chunk id; tempo and pad are not (they only redo assembly and alignment).
- The provider name is part of the chunk id, so the fake tones never pass for real audio. `config/voice.json` default provider is `chatterbox`; on a machine without a worker, generate answers 409 `voice_not_configured`.
- `scope: "changed"` = chunks without a file (also the resume of an interrupted run); `"all"` = force every chunk; a list of ids = force those. A forced chunk counts as done when its file is newer than the job start.
- Reseed stores a new seed under the sentence's text hash in the manifest, then the sentence is simply "missing" and gets spoken.
- Settings and the pronunciation table both go through `PUT .../voice/settings` (`{tempo?, pad?, pronounce?}`); no extra routes.
- Timing words are the narration's whitespace tokens (written form); chapter `start` is the start of its silence, `card_start/card_end` (extra keys) mark the silence left for a card.
- Alignment uses the aligner block of `config/server.json` (`python`, `model`); `.venv-align` needs faster-whisper. If `aligner` is null the `even` aligner is used and the manifest says `"timing_quality": "even"`.

## Tested (written, NOT yet run)
- `test_speak.py` (about 17): numbers, ordinals, years, decades, ranges, currency, percent, time, abbreviations, Roman numerals, table, units, dashes, quotes.
- `test_chunks.py` (9): comic rule, merging, comma cut, abbreviations, stable ids and seeds, reseed, gaps, written words preserved.
- `test_planner_plan.py` (6): parts, estimate, missing/forced, approval gate, signatures, pronunciation table scope.
- `test_align.py` (6): even times, merge and interpolation, clamping, written words from numbers, full coverage in order.
- `test_assemble.py` (about 8): layout arithmetic, loudnorm parsing, pad, mix, end to end with real ffmpeg (needs ffmpeg), missing chunks.
- `test_chatterbox_provider.py` (4): job file, scripted child process, crash, server config keys.
- `test_run.py` (8, needs ffmpeg): full run with fake voice and even aligner through a real `LongJobManager` instance; second run does nothing; one changed sentence is the only one redone; tempo change redoes only the mix; reseed; failed sentence retried then reported; not approved / not configured; cancel; busy.
- `test_api.py` (8): routes, validation, settings, serving chunk and mix, state().
- `test_server.py` (1, marked `server`): two real sentences, real worker, whisper if installed, checks files, words, loudness, codec.

## Faked
Voice (tones), aligner (`even`, or scripted child process), long-job manager is the real class with a temp root. Nothing real is used off the server.

## Open questions
1. Real aligner not tested at all (needs `.venv-align` with faster-whisper and ffmpeg on PATH; the worker calls `ffmpeg`).
2. `loudnorm` two-pass result vs the AAC encode: true peak is measured after the encode and stored; the server test allows tp <= -0.5.
3. Memory of the pad mix for a 14-minute video is about 1 GB of float arrays (same as the benchmark); fine on the server.

## Needs another agent
**CORE**
- `app.py`: `from .voice_api import router as voice_router; app.include_router(voice_router)` (it reads `app.state.projects_root`). Add `<link rel="stylesheet" href="css/voice.css">` to `index.html`; replace the voice placeholder with `views/voice.js` in the router.
- `pipeline_api.py` / `projects.py`: use `bti.voice.state(project_dir)` -> `{state, detail, reasons, counts}` (never raises) for step 3, and `audio/mix.m4a` + `timing.json` for the stage `voiced`.
- Delete handling: a running voice job should block deleting the project (it is a long job of kind `voice`).
- `errmsg.js`: the page translates codes through a local table `CODE_TEXT` in `views/voice.js`; to merge, add to `BY_CODE_HTTP` the codes (answers carry `code`): narration_missing, narration_not_approved, nothing_to_say, voice_not_configured, voice_busy, voice_worker_failed, voice_chunks_failed, voice_chunks_missing, voice_assemble_failed, voice_align_failed, no_voice, no_chunk, bad_scope, bad_tempo, bad_pad, bad_pronounce. Long-job error codes (`part_timeout`, `part_failed`, `interrupted`, `heavy_unavailable`) are also in that table.
- `labels.js`: the local tables `STATE_TEXT`, `JOB_STATE`, `REASON_TEXT` in `views/voice.js`; remove `PLANNED.voice` when the view is wired.
- `DATA_ERROR` in `errmsg.js` has no key `voice` (a damaged `voice/voice.json` raises `DocumentCorrupt(what="voice")`): add `voice: 'Tệp giọng đọc của dự án bị hỏng.'`.
**WIN**: `.venv-align` with `faster-whisper` (and its model `small.en` in the project folder); ffmpeg on PATH; `config/server.json` voice block already read (keys `voice.python/worker/reference_voice/exaggeration/cfg_weight/temperature`, `aligner.python/model`).
**DRAFT**: reads `timing.json` (`words`, `beats[{id,chapter,text,start,end,w0,w1}]`, `chapters[{id,name,start,end,card,card_start?,card_end?}]`) and `voice/voice.json` `timing_quality`.
**Packages**: none new on the Mac (numpy already there). Server: faster-whisper in `.venv-align`.

## Disagreements with the contract
- Section 5 says the `chatterbox` worker runs "with the comic's voice Python"; `config/server.json` (CORE) points to `.venv-chatterbox`, which is what the worker needs. Fine, only a naming note.
- "Đọc lại câu này" cannot know the new chunk id; the server reseeds, so the request carries the old id. No objection, just how it works.

## Guide section (for `docs/APP_GUIDE.md`, CORE merges)

### Giọng đọc

Bước 3 biến lời dẫn đã duyệt thành một tệp âm thanh (`audio/mix.m4a`) và một tệp ghi thời điểm từng từ (`timing.json`). Bước này mở khi bạn đã duyệt lời dẫn ở bước Kịch bản, và bạn có thể chọn hình (bước 4) trong lúc máy đọc.

1. Mở bước "Giọng đọc". Trang cho biết còn bao nhiêu câu chưa đọc và máy cần khoảng bao lâu (một video 12 phút mất chừng 50 phút máy chạy, chia thành các phần khoảng 20 phút).
2. Bấm "Tạo giọng đọc". Bạn có thể rời trang, máy vẫn chạy. Trang hiện từng phần đang chạy; phần nào chờ máy rảnh sẽ ghi "Chờ máy rảnh". Bấm "Hủy" để dừng; các câu đã đọc xong được giữ lại, bấm tạo lại sẽ đọc tiếp từ chỗ dở.
3. Khi xong, bấm nút nghe để nghe cả bài, hoặc nghe từng câu ở danh sách lời dẫn theo chương. Câu nào chưa vừa ý, bấm "Đọc lại câu này" để máy đọc lại bằng một lần đọc khác.
4. Con số, năm, thế kỷ, tiền, phần trăm, chữ viết tắt và số La Mã (vua, giáo hoàng) được đọc thành chữ tự động. Từ nào máy đọc sai (thường là tên riêng), thêm vào "Bảng phát âm": chữ viết bên trái, cách đọc bên phải, rồi bấm "Lưu bảng phát âm". Chỉ những câu có từ đó phải đọc lại.
5. "Tốc độ đọc" (1.00 đến 1.20) và "Nhạc nền nhẹ" chỉ cần ghép lại, không phải đọc lại (vài phút).
6. Nếu bạn sửa lời dẫn sau khi đã có giọng đọc, trang báo "Lời dẫn đã đổi" và chỉ những câu đã đổi được đọc lại. Các shot của storyboard neo vào từ nào sẽ được kiểm tra lại ở bước Dựng hình.
7. Nếu máy chưa có máy đo từ, thời điểm từng từ được chia đều trong mỗi câu (trang ghi rõ); chỉ đầu và cuối mỗi câu là chính xác.

Phụ đề không bao giờ được vẽ vào hình; bước này không đưa chữ lên màn hình.
