# BUILD: step 6, export (EXPORT agent)

Status: written, compiled, imported on the Mac. **Nothing has been run**: tests run only on the Windows server and `docs/WINDOWS.md` (STATUS: ready) did not exist yet. Waiting for the server.

## What exists

| File | What |
|---|---|
| `bti/export/plan.py` | cuts the timeline at shot starts into parts of about 240 s (between 0.5x and 1.5x; a hard cut at the wanted frame when one shot is very long); part key = hash of storyboard revision, frame range, width, quality; estimate |
| `bti/export/render.py` | `Tools` (ffmpeg, ffprobe, engine command builder: swappable by tests); `render_part` (engine child process through `ctx.run_process`, `progress N%` read, partial file renamed only after a frame-count check, skipped when a current file exists); `join_parts` (concat by stream copy, frame count must equal `round(end*fps)`) |
| `bti/export/subtitles.py` | cues from timing words: sentence ends, pauses of 0.6 s, beat and chapter starts break; DP split of long sentences preferring commas and pauses; 2 lines x 42 characters; 0.8 s to 6 s; gap of at least 40 ms; times in integer ms; `.srt` writer and reader, `check_cues` |
| `bti/export/mux.py` | join and mux commands (video copy, audio copy or AAC 192k when the mix is not AAC, `mov_text`, chapters from an ffmetadata file, `+faststart`, `-t` = video length; no video filter of any kind), chapter marks |
| `bti/export/describe.py` + `description.template.txt` | description and `chapters.txt`; a paragraph with an empty placeholder is dropped; credit line per asset that appears in a shot; flagged asset gets a note, never a refusal; books from `project.json` `sources` with titles from `bti.library.config.BOOKS` |
| `bti/export/check.py` | ffprobe (`-count_packets`), `ebur128` loudness, report card with `ok/warn/fail` per item |
| `bti/export/run.py` | `start`, `state`, `plan_for`, `read_manifest`; the job parts: `prepare` (subtitles and description first, so a bad timing fails before the render), `render-N` (heavy, with `is_done`), `join`, `mux`, `finish` (checks, then publishes under the project lock: manifest removed, files replaced, manifest written last) |
| `bti/export/settings.py` | threads and part length from `config/server.json` (block `windows` or `default`), with defaults |
| `bti/editor/export_api.py` | `router`: `GET .../export`, `POST .../export/start`, `GET|HEAD .../export/files/{name}` (own range handling: 206, 416, suffix ranges; only a regular file directly in `export/`, no links, strict name pattern) |
| `bti/editor/static/js/views/export.js`, `static/css/export.css` | the page; the view loads its own stylesheet, so `index.html` needs no edit |
| `tests/export/` | fakes: `fake_tools.py` (engine, ffmpeg, ffprobe writing tiny JSON files), `fakelongjob.py` (synchronous stand-in with the real interface; it uses the real `PartError` through `bti.longjob`), tests below |

Files written: `projects/<pid>/export/{<pid>.mp4, <pid>.srt, description.txt, chapters.txt, export.json}`. Scratch (parts, join, staged mux) is under `projects/<pid>/cache/export/`; parts of an older storyboard revision are deleted after a successful join.

Manifest `export.json` (`bti.export/1`): storyboard revision, audio signature, duration, frames, cues, cue problems, chapters, parts, file names, report card and its worst status, loudness, credits, flag notes, created time, seconds taken. State: `none` (no manifest, or a job is not running), `running` (an active job), `stale` (reason `storyboard`, `audio` or `files`), `done`.

## Tests (written, NOT run)

About 100 tests in `tests/export/`: `test_plan.py` (cuts, frame sums on the real arnolfini timeline), `test_subtitles.py` (every rule; the real arnolfini timing: no violation, every word once in order, no cue across a chapter start), `test_mux.py` (a test that fails if any command holds `-vf`, `subtitles=`, `-filter_complex` or `ass=`), `test_describe.py`, `test_check.py`, `test_settings.py`, `test_job.py` (full run with fakes, resume after a failed part, frame mismatch, cancel, stale reasons, busy, not approved, deleted project), `test_api.py` (routes, ranges, traversal and link refusal), `test_server.py`.
Run on the server: `tools/deploy/remote_test.sh tests/export`. The two tests of `test_server.py` (marked `server`) render 5 seconds at final quality with the real engine and ffmpeg, mux with a 5 s cut of the real mix and check with ffprobe; they are skipped unless `--run-server` and `BTI_HEAVY_HELD=1` (the caller took the heavy slot first).
Faked: engine, ffmpeg, ffprobe, the long-job runner (`tests/export/fakelongjob.py`; CORE's `bti.longjob` is not exercised by these tests except `PartError`). Not covered: a real full export, `HEAD`/range against a real browser player, the page itself (no browser run).

## Needs another agent (CORE)

1. Register `bti.editor.export_api.router` in `app.py` (it reads `app.state.projects_root`), call `bti.export.state(project_dir)` for the step state, mount `views/export.js` for step `export` (same `mount(host, ctx)` shape; it uses `ctx.shell.go`, `ctx.shell.refreshPipeline`, `ctx.pipeline.project` and `ctx.pipeline.steps`).
2. `errmsg.js`: the view has a local table `EXPORT_ERRORS` (exported) keyed by `body.code`: `no_storyboard not_approved approval_stale storyboard_unreadable no_audio no_timing no_subtitles busy render_failed frames_mismatch join_failed part_missing mux_failed plan_failed project_gone`. Move it into `BY_CODE_HTTP`. Error answers have `{detail, code}`. Job failures use the same codes through `PartError(code, vietnamese message)` (table `bti/export/errors.py:VI`).
3. `labels.js`: local table `EXPORT_LABELS` (part and job states, report card item names and help, stale reasons, file names).
4. The step state of `export` in `pipeline_api.py`: `bti.export.state()` gives `state` and a Vietnamese `detail`; `rendered` stage = state `done`.
5. `PLANNED.export` in labels and the placeholder view for `export` can go.

## Open questions and objections

- Section 8 says "joined by stream copy; frame count checked against duration x 30": implemented as `round(end*fps)` frames, where `end` is the storyboard's end (the engine's own rule), checked with `ffprobe -count_packets` for every part and the joined file.
- The mux length is the video's (`-t`), as in the benchmark. If the mix is shorter than the video the end is silent; the report card does not flag a short audio track yet.
- A very short chapter (under 10 s) is not merged: YouTube ignores chapter lists with a mark under 10 s. The voice step controls chapter lengths.
- Loudness is measured but never corrected here (the voice step normalises); a miss is a `warn`.
- The audio and subtitle language tag is `eng` (settings key `language`).

## Guide section: "Xuất video" (for the owner's guide)

**Xuất video** là bước cuối: máy dựng bản video hoàn chỉnh từ storyboard đã duyệt và giọng đọc.

1. Vào bước **Xuất video**. Nếu trang báo "Chưa xuất được", làm theo nút bên dưới (thường là duyệt storyboard ở bước Dựng hình, hoặc làm xong Giọng đọc).
2. Hộp **Sẽ làm ra** cho biết video dài bao lâu, chia thành mấy đoạn và khoảng bao lâu máy làm xong (máy chủ dựng bằng bộ xử lý nên khoảng 2 phút cho mỗi phút video; video 12 phút mất chừng nửa tiếng).
3. Bấm **Xuất video**. Bạn có thể đóng trang, máy vẫn làm. Trang hiện từng đoạn đang chạy. Nếu máy đang bận việc khác, đoạn sẽ ở trạng thái "Chờ máy rảnh".
4. Bấm **Hủy** nếu muốn dừng. Những đoạn đã dựng xong được giữ lại; bấm **Xuất video** lần nữa sẽ làm tiếp, không dựng lại từ đầu. Việc này cũng đúng khi máy chủ khởi động lại giữa chừng.
5. Khi xong, bạn có: video để xem ngay trên trang, **phiếu kiểm tra** (độ dài, số khung hình, độ lớn tiếng, có phụ đề trong tệp, số dòng phụ đề, mục lục), **mô tả video** (có nút Chép mô tả: gồm mục lục, sách đã dùng, nguồn và giấy phép của từng hình) và các tệp để tải về: video MP4, phụ đề .srt, mô tả, mục lục.
6. Phụ đề không bao giờ bị vẽ lên hình: có một tệp .srt riêng và một dòng phụ đề bật/tắt được nằm trong tệp MP4.
7. Nếu bạn sửa storyboard hoặc giọng đọc sau khi xuất, trang báo "Cần xuất lại". Bản cũ vẫn xem được cho đến khi xuất bản mới.
8. Hình nào chưa rõ giấy phép sẽ có ghi chú trong mô tả để bạn kiểm tra trước khi đăng; việc xuất không bị chặn.
