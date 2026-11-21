# Round 3: UI fixes (answer to ROUND3_ui.md and ROUND3_decisions.md)

Fixer: UI, 2026-11-16. Mock model only, no network. Nothing committed. Screenshots: `.scratch/round3_ui_fix/shots/` (1700x1000, and `_1280x720` for the same screens; `SIZE=1280x720 node tests/e2e/round3/fixes.mjs`).

## R3U-001 A dropdown always shows the real value: fixed
- Cause: the `<select>`s were built from the list only, so a stored value outside the list (or none) fell to the first entry.
- Change: one pure helper `dropdownOptions` (`labels.js`, end of file) and one DOM wrapper `fillSelect` (`util.js`). A value the list does not know gets its own first entry "... (không có trong danh sách)"; an empty value shows a disabled "— chưa chọn —" (unless "" is itself a choice). Nothing is written until the owner picks something.
- Dropdowns gone through (every `<select>` of the app):
  - fixed with the helper: shot Ý đồ and overlay Ý đồ (`inspector.js`), Chuyển vào (transition; unknown technique, "chưa có" entries stay disabled), enum params (`formui.js` select, also on `sync`), asset params (`formui.js` asset), camera key easing (`formui.js`), outline chapter role and fact certainty (`views/script.js`).
  - not applicable (value comes from page state, not from stored data): camera key "kind" (derived from the key), gallery intent filter, Hình tab source/kind/licence, library filters, copy-prompt chapter filter, project picker, alternative-model picker.
  - model picker: the stored choice is always taken from the list it shows (`loadModels`), so it cannot disagree.
- Tests: `tests/editor_frontend/dropdown.test.mjs` (5), e2e `F-001`, `F-001b` (and the tester's `R3U-001`).

## R3U-002 A chapter difference can always be resolved from the page: fixed
- Cause: no operation and no button existed for removing a chapter; advice only.
- Change: pure `chapdiff.js` (`chapterDiffItems`) turns `chapter_diff` into items with one action each. `views/script.js`: `diffRow` (a row with its buttons), `dropChapter` (asks once, then `drop_chapter`). Used in three places: the refusal dialog, the note above the narration (`approvalNote`), and the chapter header ("Xóa chương này khỏi lời dẫn", only for chapters the outline lacks). Missing chapter: "Viết chương này" (existing job, only that chapter, chosen model) and "Thêm chương trống" (`add_chapter`). Empty chapter (`empty_in_narration`): "Viết chương này" and "+ Dòng" (see objection). The header button of a chapter with no text reads "Viết chương này" instead of "Viết lại chương".
- Undo: `doOp` now records the document as it was before a structural operation, so Hoàn tác brings back a dropped chapter or beat (before, operations were not undoable at all).
- `empty_chapter` issue: `errmsg.js` sentence, `labels.js` code label.
- Objection (small): for an empty chapter the contract says "the same two choices"; "Thêm chương trống" is meaningless there (the chapter exists), so the second choice is "+ Dòng".
- Tests: `round3.test.mjs` (chapter items), `errmsg.test.mjs` (empty_chapter has a sentence), e2e `F-002` (refusal dialog -> drop -> undo -> redo -> approved), `F-002b`, and the tester's `R3U-002`.

## R3U-003 Clicking an issue never lands on an unrelated shot: fixed
- Cause: `selectIssue` fell back to shot 1.
- Change: pure `issueTarget` + `shotsUsingAsset` in `sbissues.js`; `inspector.js:selectIssue` follows it. Shot (path or id) -> that shot and overlay. `args.asset` (or `assets.<key>` path) -> first shot using it, with a message saying how many use it; none uses it -> Hình tab opened on that asset (`media.js:selectAsset`). No place -> stays, shows the sentence and its detail in a message. The fallback is gone.
- Tests: `round3.test.mjs` (5), e2e `F-003`, tester's `R3U-003`.

## R3U-004 A frame that cannot be drawn leaves no stale picture: fixed
- Cause: `frameError` only wrote the line next to the preview.
- Change (`preview.js`): `setFrameFail` clears the old bitmap, draws a neutral panel with the sentence, hides all handles (`drawHandles` returns early), and gives the Shot tab the same sentence through `ctx.thumbFails` (its own entry, removed again on recovery). A failure applies only while the playhead is on the shot that failed. Recovers by itself on the next good frame. The slot picture of an unreadable image no longer shows a broken-image icon with a name (`inspector.js:slotRow`).
- Tests: e2e `F-004` (no handles, dark panel, no banner on another shot), tester's `R3U-004`.

## R3U-005 Undo cannot go back past a merge: fixed
- Cause: `Store.rebase` pushed the pre-merge draft on the undo stack.
- Change: `store.js:rebase(..., {fresh})`; the merge in `views/storyboard.js` passes `fresh: true` (history restarts at the merged document; unchanged content keeps the history; "Ghi đè" is not a merge and keeps it). The merge message adds "Hoàn tác không quay lại trước lúc ghép."
- Tests: `round3.test.mjs` (3), e2e `F-005`, tester's `R3U-005`.

## Observations
- Repeated issue sentence: camera-key issues (`camera_keys_order`, `camera_rel_range`, `unknown_ease`, `anchor_invalid`, `stale_anchor`) now name the key ("Mốc camera thứ 3: ..."); identical sentences that cannot be told apart are shown once with "(N chỗ)" (`errmsg.js:groupIssues`, used by the Lỗi tab). Test in `round3.test.mjs`.
- Two tabs, different fields of one shot: conflict dialog stays (as decided).

## R3B-007 page half: order
- `chapdiff.js` item `order` ("Các chương của lời dẫn xếp khác thứ tự trong dàn ý.") with one action "Sắp xếp theo dàn ý" -> `{"op":"order_like_outline"}`; shown in the refusal dialog and the note above the narration. Tests: `round3.test.mjs`, e2e `F-007` (real backend).

## R3B-009 / R3B-010 page half
- `describeHttp` and `jobFailText` give `render_failed` no "chi tiết" (the server text is never shown); the sentence comes from code, shot and (new) `asset`: "... hình X: tệp ảnh bị hỏng ..." (`errmsg.js:renderFailText`).
- Templates (`sbissues.js`): `asset_file_truncated`, `asset_video_unreadable`; `undrawable` names `args.asset`. The `ISSUE_CODES` test passes.
- Tests: `round3.test.mjs`.

## Script page never waits for the model list
- `views/script.js`: `loadModels()` is not awaited by `mount`; outline, narration and brief show first. The dropdown reads "Đang tải danh sách mô hình..." and is disabled; "Lập dàn ý" and "Viết lời dẫn" are disabled only while there is no model (loading or failed). Failure: message plus "Thử lại" (`loadModels(true)`); the Antigravity flag and its "Thử lại" are unchanged.
- Test: e2e `F-006` (the browser delays `/api/models` by 6 s; beats and outline on screen in under 3.5 s).

## Last small items
- `chapter_order` issue sentence, `too_large` (413) sentence (`errmsg.js`), and `stale` note hidden while the narration is approved (`views/script.js`). Tests in `round3.test.mjs` and `errmsg.test.mjs`.
- The chapter-difference sentence keeps the words "không có trong dàn ý" ... (round 2 check `R2U-P5` looks for "không có trong dàn ý").

## Needs the other agent
- Nothing missing. One note: with a damaged image the server prints a long Python traceback (`AssertionError` in `vfx.Img.__init__`) to its log on every frame request; the answer to the page is fine. Backend may want to log one line.

## Tests changed and why
- `tests/editor_frontend/errmsg.test.mjs`: `empty_chapter` added to the list of codes that must have a sentence (new code).
- `tests/e2e/round3/run.mjs`: not changed. New files: `tests/e2e/round3/fixes.mjs`, `tests/editor_frontend/dropdown.test.mjs`, `tests/editor_frontend/round3.test.mjs`.

## Suite results at the end
- `node --test tests/editor_frontend/*.test.mjs`: 155 pass, 1 fail. The failure is `no_raw_text.test.mjs` on `views/picks.js` and `views/voice.js`, files another agent is writing right now (not part of this batch).
- `round3/run.mjs` 5 pass 0 fail; `round3/fixes.mjs` 9 pass 0 fail; `storyboard/run.mjs` (BE=1) 35 pass 0 fail; `shell_library_script/run.mjs` 9 pass 0 fail; `run_extra.mjs` 16 pass 0 fail; `round2/run.mjs` 20 pass 1 fail at first (R2U-P5 looked for "không có trong dàn ý"; the sentence was reworded, now PASS when run alone).
