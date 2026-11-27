# Visual Path Pages for Step 4 ("Kịch bản hình") and Step 5 ("Dựng hình")

Worker: `visualpage` (branch `wt/visualpage`, base `5040c60`).

## 1. What was built

### Backend (read-only route)
- `bti/visual/api.py`: added `GET /api/projects/{pid}/visual/words` returning `timing.json` `words`, `beats`, `chapters`, and `duration` (`present: false` when `timing.json` does not exist yet).
- `tests/visual/test_visual_words_api.py`: unit tests covering missing `timing.json`, populated `timing.json`, and 404 for unknown projects.

### Frontend labels, pure logic, and views
- `bti/editor/static/js/labels.js`: added `VISUAL_PAGE_LABELS` inside the marked `// ---- worker visualpage` block (all Vietnamese, no raw identifiers).
- `bti/editor/static/js/visualpage_logic.js`: pure helpers for Step 4 and state-driven action lookup:
  - `isVisualProject` detects visual-path projects (`visual.moments` or `pipeline === 'visual'`), leaving legacy projects untouched.
  - `findStateAction`, `visualEditAction`, and `needsHint` read readiness, `method`, `path`, and Vietnamese `needs` hints directly from `GET /api/projects/{pid}/state` (`next_actions`).
  - `buildVisualScriptView`, `resolveShow`, `describeIntents`, `momentWordsText`, `momentWhy`, and `regionDisplayName` render narration lines in order with each line's moments, spoken words, thumbnails (painting region crop, pool picture + caption, pair, or map sign), subject (`about` + `about_not_shown`), `intro` name + word position, `point`/`read`/`labels`/`number` intents, one-sentence `why`, top counts (moments, borrowed pictures, not-found count, top 5 painting regions), and not-found wanted pictures with every tried query (`tried`) and fallback (`else`).
- `bti/editor/static/js/visualedit_logic.js`: pure helpers for Step 5:
  - `isVisualStoryboard` detects composed visual storyboards (`made_from.visual`, `compose_notes`, `shot.moment`, or `visual.moments`).
  - `momentWordsMap` attaches exact spoken words of `shot.moment` to each composed shot.
  - `translateComposeNoteText` and `groupComposeNotes` translate `bti.compose` notes into plain Vietnamese sentences prefixed with `"câu N: ..."` (e.g., `"câu 8: hình mượn được kéo dài về đầu câu"`), grouped by kind (`timing`, `pair`, `camera`, `intro`, `caption`, `mark`, `device`, `boundary`).
  - `extractReviewFindings` merges and deduplicates `review_*` findings via `issueText`.
- `bti/editor/static/js/visual_box.js`: shared request box wired to `visual.edit` from `state.next_actions` (supports sync or `long_job` polling + cancel; hidden completely when `visual.edit` is absent).
- `bti/editor/static/js/views/visual_script.js`: Step 4 ("Kịch bản hình") view, wired via `bti/editor/static/js/views/picks.js` only when `isVisualProject(...)` is true.
- `bti/editor/static/js/visual_edit_panels.js` + minimal visual-path hooks in `bti/editor/static/js/views/storyboard.js`, `bti/editor/static/js/sbsimple.js`, and `bti/editor/static/js/shotlist.js`: Step 5 tabs (`Các cảnh`, `Ghi chú dựng`, `Chấm chất lượng`, `Rà soát hình`), moment words under each shot row, compose-first panel when no storyboard exists yet, and state-driven `visual.edit` box. Legacy storyboards render identically to before.
- `bti/editor/static/css/visual.css`: scoped styling for `.v-vis`, `.vbox`, and `.edit-root[data-visual="1"]`.

## 2. Verification results

### Mac JavaScript checks
- `node --check` passed on all 10 created/modified JS files under `bti/editor/static/js/`.
- `node --test tests/editor_frontend/*.test.mjs tests/picks/*.test.mjs tests/output/*.test.mjs`: **513 passed, 0 failed, 1 skipped** (`sbissues.test.mjs` engine-code check skipped in worktree without `.venv/bin/python`; no engine issue codes were added by this task).
  - Includes `tests/editor_frontend/visualpage.test.mjs` (6 tests), `no_null_children.test.mjs`, `no_raw_text.test.mjs`, `pageswords.test.mjs`, `scorecard.test.mjs`, `shotlist.test.mjs`, and `picksrows.test.mjs`.

### Windows server snapshot (`winbox-cmd`, one folder per run)
- `tests/visual`: **106 passed**
- `tests/editor`: **534 passed**
- `tests/compose`: **39 passed**
- `tests/scorecard`: **12 passed**
- `tests/picks`: **506 passed**
- `tests/cli`: **132 passed**
- `tests/ops`: **565 passed**
- `tests/state`: **319 passed, 8 failed** — all 8 failures are pre-existing on base commit `5040c60` in `pipewire`-owned files (`tests/state/test_errors.py::test_every_code_in_the_source_has_a_hint` missing `music_invalid` from `bti/export/run.py`, and 7 `test_the_exact_action_ids_at_each_stage` cases differing on `visual.plan` / `scorecard.make`).
- Doc generators (`--check`): `bti.cli.docgen --check`, `bti.ops.doc --check`, and `bti.editor.hints --check` all exited **0**.

### Un-run test folders and why they cannot be reached
`tests/auto`, `tests/draft`, `tests/music`, `tests/export`, `tests/identity`, `tests/output`, `tests/settings`, `tests/media`, `tests/fsio`, `tests/script`, `tests/voice`, `tests/title`, `tests/library`, `tests/longjob`, `tests/clean_text`, and `tests/engine -m "not slow"` do not serve or execute `bti/editor/static/**` and do not call `GET /api/projects/{pid}/visual/words`.

## 3. Real-data acceptance on `arnolfini-v3`

Tested in `D:\code\behind-the-image\run\snap-visualpage\_realdata\arnolfini-v3` (copied from `D:\code\behind-the-image\projects\arnolfini-v3`, using `.scratch/golden/arnolfini-v3/visual.json`, composed via `bti.compose` to **114 shots** and **72 raw compose notes** [53 deduplicated Vietnamese sentences], scorecard built via `bti.scorecard.build` with **7/10 passed, 3 failed, 2 unmeasured** and **6 contact sheets**), plus `arnolfini-notfound` (a copy with one `status: "none"` wanted entry for verifying the not-found UI).

Screenshots saved in `.scratch/agy_tasks/visualpage/out/` (1440×900) and visually inspected:
- `step4_top.png`: Step 4 header (`108 khoảnh khắc`, `5 lượt hình mượn`, `Đủ hình cần tìm`, top 5 painting regions), action buttons (`Lập lại kịch bản hình`, `Đã duyệt kịch bản hình`), line-by-line moments with painting crops, spoken quotes, `Nói về`, `Hiện tên`, `Chỉ vào`, and `Lý do`.
- `step4_borrowed.png`: Lines 7–8 (`b0136`–`b0137`) showing borrowed pool thumbnails (`02_lucca_seen` "Lucca seen from the Guinigi Tower", `jan_van_eyck` "Jan van Eyck - Portrait of a Man (Self Portrait?) 1433") with captions, `Nói về`, and `Hiện tên` word positions.
- `step4_not_found.png`: `arnolfini-notfound` showing `"1 hình chưa tìm thấy"` top badge, `"Chưa tìm thấy hình cần tìm: a team of dyers"`, all 3 tried keyword chips, `"Chưa chiếu trực tiếp"`, and `"Đang dùng hình dự phòng"` thumbnail + label.
- `step5_top.png`: Step 5 preview frame (rendered `The Arnolfini Portrait, Jan van Eyck, 1434` at shot 3, `0:07`), 4 visual tabs (`Các cảnh (114)`, `Ghi chú dựng (53)`, `Chấm chất lượng (7/10)`, `Rà soát hình (0)`), and composed shots with moment spoken words underneath each shot sentence.
- `step5_notes.png`: `"Ghi chú dựng (53)"` showing grouped Vietnamese notes (`Nhịp cảnh và thời lượng`, `Khung hình máy quay`, etc.) prefixed with `"câu N: ..."` and `"Xem cảnh"` jump buttons.
- `step5_scorecard.png` and `step5_scorecard_sheets.png`: `"Chấm chất lượng (7/10)"` showing the full Vietnamese metrics table (`Tranh chính nhỏ giữa hai dải đen` 5,2% Đạt, `Hình mượn ngoài tranh` Ngoài mục tiêu, `Đoạn nhắc chủ thể nhưng không chiếu` 40 Ngoài mục tiêu, etc.) and all 6 contact sheet thumbnails (`Tờ 1`–`Tờ 6`).
- `step5_review.png`: `"Rà soát hình (0)"` cleanly showing `"Chưa có kết quả rà soát hình cho bản dựng này."`.

### What is still unclear or noticed on real data
1. **Unregistered region keys in golden `visual.json`**: `arnolfini-v3/visual.json` references 5 region keys (`BAND_TOP`, `MAN_WINDOW`, `WOMAN_UPPER`, `FULL_UPPER`, `FULL_MIDDLE`) that are not present in `picks.json`'s `regions` map. Step 4 safely suppresses raw keys and displays `một chi tiết của tranh` without cropping (and counts one as `một chi tiết của tranh (5 lần)` in top regions).
2. **No real `wanted` entries in golden `arnolfini-v3/visual.json`**: golden `wanted` is `[]`, so the not-found UI was inspected on the `arnolfini-notfound` copy rather than an unedited run of `visual.plan`.
3. **Chapter title casing in Step 4**: `"COLD OPEN"` renders as `"Chương 1 · COLD OPEN"` in Step 4 because of the space, whereas Step 5 formats it as `"Chương 1 · Cold open"`.
4. **Shared `scorecardlogic.js` detail line**: existing `formatMetricDetail` prints raw shot IDs (`s_m0013`, `s_m0015`) in the borrowed-pictures detail row (shared with Export page).
5. **`visual.edit` hidden on base `5040c60`**: `state.next_actions` did not yet include `visual.edit` (owned by `review2`), so the request box stayed hidden on both Step 4 and Step 5 as specified; unit tests verify its state-driven rendering and submission when `visual.edit` is offered.
