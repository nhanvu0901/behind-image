# Fix B: Video clips in the picks step (2026-11-17)

Tracking file for Task B implementation and verification.

## 1. Step 1 (C2): Safe YouTube URL & Hostile String Protection

### Changes
- `bti/media/clips.py`:
  - `_YT_PATTERNS`: Anchored regexes for YouTube watch, shorts, embed, live, and youtu.be URLs.
  - `video_id(url)`: Validates input is string, strips, rejects leading `-`, fullmatches against `_YT_PATTERNS`, extracts 11-char ID.
  - `safe_youtube_url(url)`: Validates URL via `video_id` and canonicalizes to `https://www.youtube.com/watch?v=<id>`. Raises `ValueError` on hostile/invalid input.
  - `video_metadata`, `video_metadata_with_cues`, `ytdlp_section_args`, `fetch_section`: Passes canonical URL preceded by `"--"` argument to `yt-dlp`.
- `bti/picks/service.py`:
  - `video_search`: Validates and normalizes `url` via `clips.safe_youtube_url(url)` (raising `PicksError(422, "not a supported YouTube URL", "video_bad_url")` on error).
  - `import_video_clip`: Validates and normalizes `url` via `clips.safe_youtube_url(url)` (raising `PicksError(422, "not a supported YouTube URL", "video_bad_url")` on error), passing canonical URL to importer.
- `tests/media/test_clips.py`:
  - Added `test_safe_youtube_url_hostile_strings` covering leading dashes (`--batch-file=...`, `--help`, `-v`), spaces, double URLs, shell injection characters (`;`, `&&`, `|`, `$()`, backticks), other hosts, malformed IDs.
  - Added check that `ytdlp_section_args` places `"--"` before the canonical URL.
- `tests/picks/test_api.py`:
  - Added hostile URL test cases to `/video-search` and `/import-clip` returning `video_bad_url`.
  - Added assertion that `clip_importer` receives the normalized canonical URL.

### Tests
- Snapshot test on Windows server: `tests/media` 111 passed (including `test_safe_youtube_url_hostile_strings`); `tests/picks/test_api.py -k video` 2 passed.

## 2. Step 2 (C1): yt-dlp pinned in requirements.txt & Tool Missing Notice

### Changes
- `requirements.txt`: Added pinned `yt-dlp==2026.08.19`.
- `bti/media/clips.py`: Added `has_ytdlp()` and `tool_status()` returning `{"available": bool, "code": "tool_missing" | None}`.
- `bti/picks/service.py`: Added `video_tools` to `payload(...)` dict.
- `bti/editor/static/js/views/picks.js`: Rendered standing warning banner in `tabVideo` when `video_tools.available` is false or `S.v.toolMissing` is set; handled `tool_missing` error code in `runVideoInspect` and `runVideoSearchPaid` by showing standing notice instead of a toast.
- `tests/media/test_clips.py`: Added `test_clips_tool_status`.
- `tests/picks/test_api.py`: Verified `video_tools` presence in `payload` and 503 `tool_missing` on missing tool.

### Tests
- JS unit tests: 188 passed (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs`).
- Snapshot test on Windows server: `tests/media/test_clips.py` 9 passed; `tests/picks/test_api.py -k "video or get_new_project"` 3 passed.

## 3. Step 3 (C4): Cutting clip as long job with progress & cancel

### Changes
- `bti/picks/service.py:304-380`:
  - Added `start_clip_job()` which kicks off a long job via `bti.longjob.manager.start(kind="picks", ...)` with action `"clip"`.
  - Reports progress via `c.progress(0.1, ...)` and checks `c.cancelled()` to cleanly abort.
- `bti/editor/picks_api.py:213-234`:
  - Updated `import_clip_picks` to call `start_clip_job` and return `{"job_id": ...}` by default.
  - Added optional `wait: bool` parameter to synchronously await the job if requested (e.g. for simple API clients / tests).
- `bti/editor/static/js/views/picks.js`:
  - Updated clip cutting trigger to run the long job and invoke `watch(r.job_id)`.
  - Added running clip card in `tabVideo` showing progress percent, status message, and "Hủy" (cancel) button.
  - Reload survival: `mount()` queries `/api/projects/{pid}/longjobs?kind=picks` and resumes watching any running clip job.
- `tests/picks/test_api.py:317-353`:
  - Verified async clip cutting job creation and polling with `lj.manager.wait()`.
  - Verified `wait=True` synchronous response.
  - Verified job cancellation via `POST /api/longjobs/{job_id}/cancel`.

### Tests
- Snapshot test on Windows server: `tests/picks/test_api.py` 21 passed. Full `tests/picks` 55 passed.

## 4. Step 4 (C5 & C6): One copy on disk, cache pruning & uniform video normalisation

### Changes
- `bti/media/clips.py:612-680`:
  - Added `prune_clips_cache(project_dir, max_bytes=500*1024*1024)`: removes oldest files in `cache/clips/` until total size is <= 500 MB.
  - In `fetch_section`: cleans up raw downloaded file and metadata json once normalized file is generated.
  - In `import_clip`: removes intermediate working copy under `cache/clips/` and intermediate sheet after copying to `media/`, leaving only one copy on disk, then calls `prune_clips_cache`.
- `bti/editor/media_adapter.py:168-195`:
  - Updated old editor upload endpoint (`add_upload`) fallback for video files to transcode using `clips.normalize(file_path, dest, strip_audio=True)` to `.mp4` (constant 30 fps, muted), identical to `/picks/upload` and `bti/media/api.py`.
- `tests/media/test_clips.py:173-208`:
  - Added `test_import_clip_one_copy_and_prune_cache`: asserts intermediate file in `cache/clips` is deleted, final file in `media` exists, and cache is pruned to the byte cap.

### Tests
- Snapshot test on Windows server: `tests/media` 113 passed.

## 5. Step 5 (C3): Nothing raw on screen & extend no_raw_text test

### Changes
- `bti/media/clips.py:270-330`:
  - Video candidate moments now emit structured reasons in `why`:
    - `{"code": "chapter", "title": ...}`
    - `{"code": "subtitle", "text": ...}`
    - `{"code": "replayed", "value": ...}`
- `bti/editor/static/js/labels.js:148-164`:
  - Added section `// --- picks and clips` with `MOMENT_WHY` translations and `momentWhy(why)` helper converting structured codes into clean Vietnamese.
- `bti/editor/static/js/views/picks.js:370-425`:
  - Rendered `m.why` through `LBL.momentWhy(m.why)`.
  - Rendered `v.error` mapped via `ERR[v.error_code || v.error] || ERR.video_fetch_failed` in Vietnamese instead of raw English text.
- `tests/editor_frontend/no_raw_text.test.mjs:101-118`:
  - Extended checks to forbid raw `v.error` text interpolation/assignment and raw `m.why` text display in views.

### Tests
- JS unit tests on Mac: 188 passed (`node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs`).

## 6. Step 6 (C7 & confusing points)

### Changes
- `bti/editor/static/js/views/picks.js`:
  - **C7 (Play imported clip file)**: The tray card for video clips renders an HTML5 `<video class="pk-tray-video" controls muted playsinline preload="metadata">` playing the actual imported mp4 file via range requests, allowing the user to review what was cut.
  - **Two sliders**: Added dual range sliders (`<input type="range" class="pk-slider">`) for start and end times in `videoCard`, synchronized in real time with the numeric input fields over the video duration.
  - **Paid button label**: Updated the third button text to `"Dùng chữ gợi ý của dòng này (tốn tiền)"` so the user clearly sees that it incurs search cost.
  - **Disabled button explanation**: Next to the disabled `"Cắt & thêm vào dòng"` button, rendered helper text: `"(Chọn dòng ở cột trái để thêm)"` when no beat is currently selected.
- `bti/editor/static/js/views/picks_logic.js:11-30`:
  - Restricted clip roles: For video items, role selection is limited to `VIDEO_ROLES = ["video", "context", "compare"]` (excluding non-video roles such as "full", "map", etc.). Image items exclude the `"video"` role.
- `bti/editor/static/css/picks.css:48-80`:
  - Added styling for `.pk-tray-video`, `.pk-sliders`, and `.pk-btn-reason`.

### Tests
- JS unit tests on Mac: 188 passed.
- Snapshot tests on Windows server: `tests/picks` 55 passed.

## 7. Step 7 (Part C): Dead subtitle reads in check.py

### Changes
- `bti/export/check.py:28-68`:
  - Removed `"subtitle: {codec}|None"` from docstring.
  - In `parse_probe`: removed `s = first("subtitle")`, removed `"subtitle": None` from output dictionary, and removed `if s: out["subtitle"] = ...`.
- `tests/export/test_check.py:18-35`:
  - Removed subtitle stream from fixture `PROBE`.
  - Updated `test_parse_probe` to assert `"subtitle" not in i` instead of checking `i["subtitle"]["codec"]`.
- `tests/export/test_server.py:68`:
  - Updated assertion to `info.get("subtitle") is None` for backward compatibility.

### Tests
- Snapshot test on Windows server: `tests/export` 78 passed (2 skipped for `--run-server`).

---

## 8. What the owner will now see (against section 2.4 of the review)

1. **Missing tool on server**:
   When `yt-dlp` is missing, the "Video" tab immediately displays a standing warning banner: `"Máy chủ chưa có công cụ yt-dlp để tải video YouTube."` rather than showing transient toasts while leaving the inputs looking available.
2. **Paid keyword searches**:
   The search buttons explicitly state costs on their face: `"Tìm trên YouTube (You.com, tốn tiền)"` and `"Dùng chữ gợi ý của dòng này (tốn tiền)"`. The owner will not trigger a paid search inadvertently.
3. **Disabled "Cắt & thêm vào dòng" button**:
   When no narration beat is selected in the left column, a clear note in Vietnamese appears right beside the disabled button: `"Chọn dòng ở cột trái để thêm"`.
4. **Setting start and end time**:
   The owner can use two responsive range sliders (start and end) directly linked to the numeric fields to drag-and-set the clip segment over the video duration.
5. **Previewing the cut clip**:
   Once imported into the tray, the card contains an interactive HTML5 video player with controls (`controls muted playsinline`), allowing immediate playback of the normalized clip.
6. **Role list for video clips**:
   The dropdown only offers video-appropriate roles: `"Đoạn video"` (`video`), `"Bối cảnh"` (`context`), and `"So sánh"` (`compare`), eliminating confusing image-only roles like "Cả bức tranh" or "Bản đồ".

---

## 9. Final Checklist

- **Needs another worker**: None. All requirements for Task B and Part C are self-contained and complete.
- **Objections**: None. All decisions from `docs/qa/REVIEW_2026-11-17_decisions.md` were implemented as specified.
- **Open points**: None. All 7 steps have been implemented and verified with snapshot tests on the Windows server and JS tests on the Mac.
