# FIX_A_page: the page side of "edit the video by typing an instruction" and the model settings

(Written as the work went on; the final summary is at the end.)

## What was built
- `bti/editor/static/js/editlogic.js` (new, pure, tested): scope words, default scope, turn card data for every status, progress line, 24-hour clock, preview range, "take the turn in" rules, settings rows.
- `bti/editor/static/js/promptedit.js` (rewritten): the box (text field, scope in words, "Chọn nhiều cảnh", send), the thread of turn cards, undo / resolve / retry / cancel, idle watch for a job started in another tab.
- `bti/editor/static/js/settings.js` (new): the dialog "Mô hình cho từng việc"; opened by the top-bar "Cài đặt" (`index.html`, `app.js`) and by the link "Mô hình" in the box.
- `views/storyboard.js` hooks only: `takeInTurn()` (reload keeping selection and playhead, or the rebase merge with fresh undo history), `previewClip(t0, t1)` takes a range, the old proposals path of the prompt box is gone (the "Đề xuất" box stays for the draft of a whole video).
- `draftpanel.js`: the model select starts on the model of the role `draft` from `GET /api/settings/models`.
- `labels.js` (`EDIT_LABELS`, `SETTINGS_LABELS`) and `errmsg.js` (blocks marked `// --- draft and edit (page)`).
- `edit.css`: the box is a column beside the preview (see "Layout").

## The nine steps
1. Words: the nine codes of the task already had sentences (added by another worker in an unmarked `dsources` block, kept). In my block: `real_models_off` for every stage (it lives in the shared long-job table, so `stageErrorText` finds it for draft, picks, voice, export), `edit_failed`, `stale_revision`, `edit_locked_changed`, `compile_empty`, `spec_invalid`, `cancelled`, the settings codes (`unknown_role`, `unknown_model`, `invalid_model`, `invalid_payload`, `agentic_role_needs_agy`) and more; `escalate` was reworded for a non-programmer. Statuses and the turn card words are in `EDIT_LABELS`. `stages_words.test.mjs` also checks `real_models_off` for four stages; `editlogic.test.mjs` scans the Python files of the edit routes and fails when a code raised there has no sentence.
2. Box and thread: `promptedit.js` + `editlogic.js`. No model dropdown; scope in words; cards for running, applied, no_change, needs_choice, failed, cancelled, undone (older thread statuses `done`, `refused`, `error` are mapped); changes with number, time, sentence, Trước/Sau thumbnails; Xem thử; Hoàn tác with the conflict question and `force`; the two choices; 24-hour clock; the model's own notes and any English or id-like text only under "chi tiết".
3. Taking a turn in: `takeInTurn()` in `storyboard.js` (reload keeping selection and playhead; or `mergeStoryboard` + `Store.rebase(..., {fresh: true})` when there are unsaved edits; a real conflict opens the existing conflict dialog). A turn of another tab is found by `watchIdle` (the same list of draft jobs `draftpanel.js` watches).
4. Several shots: "Chọn nhiều cảnh" adds the shots you click on the timeline (nothing is added while the playhead is playing); chips with × remove them. Default scope = selected shot, else the chapter at the playhead (else the whole video when the timing has no chapters).
5. Layout: the box is a column beside the preview (300 to 380 px wide), not a row under it. Under the preview the arithmetic does not work at 1280x720 (view 625 px, minus 44 bar, minus timeline, minus the preview's own tool rows leaves under 300 px before the box). At 1280x720 the timeline is 160 px and the preview stage is at least 300 px high (measured by the browser check); the thread scrolls inside the column.
6. Settings: `settings.js`; top-bar "Cài đặt"; link "Mô hình" in the box; `draftpanel.js` starts on the model of the role `draft`.
7. Proposals: the prompt box no longer has a proposals path (no `onProposal`, no `refreshProposalCount` after a job). `proposals.js` is untouched: it is still the box of the draft of a whole video, and nothing in it was only for edits.
8. Tests: see below. 9. `docs/APP_GUIDE.md` (section "Sửa video bằng lời", "Cài đặt: mô hình cho từng việc", the top-bar row, the draft panel's model).

## Tests
- `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs`: 208 tests, all pass (was 188 at the start; new: `editlogic.test.mjs` 19, plus the `real_models_off` test in `stages_words.test.mjs`).
- Browser: `tests/e2e/stages/prompt_edit.mjs`, last run 66 PASS, 0 FAIL (one earlier run: 64 pass, 2 fail, then fixed: the server sends conflicts as `{kind, id}` objects, not ids). It replaces `tests/e2e/test_prompt_edit_browser.mjs` (deleted). `launch.py` got: the settings file in the temp folder (edit.fast = mock), a mock that answers an edit from the shots in the prompt (`cannot` for "tranh mới", not-JSON for `[mock:broken]`, 10 s wait for `[mock:slow]`), and the project `arnolfini-live` copied (read-only source).
- What the browser check covers: layout numbers at 1280x720; default scope in words; multi-select by real clicks on the timeline; send; running card; applied card with 2 changes and 4 loaded thumbnails; the editor took the storyboard in (same revision, nothing unsaved, selection and playhead kept); Xem thử sends a request for at most 10 s and the clip opens; Hoàn tác; `cannot`; a failed turn and Thử lại; cancel; unsaved edit merged with an applied turn (fresh undo history, save keeps both); undo conflict dialog then force; needs_choice with each of the two choices; a turn started from the API shows up in the page; settings dialog (open, save one role, all, agent roles kept, link in the box); Xóa lịch sử asks once; no leftovers or raw words; no script error.
- Not covered by a browser check: the draft panel's preselected model (the test instance has no model list), the deep path (needs `agy`), real model answers.
- Screenshots in `.scratch/apage/shots/` (1700x1000 and 1280x720 of: idle, applied, failed, running, needs_choice, settings; 1700 only: preview dialog, undone, undo conflict, thread).

## Needs another worker
- The server's `undo` and `resolve` answers carry `rev` (and now `after_rev`): the page does not use either; it reloads the project.
- `needs_choice` turns have `changes: []` and `conflicts: [{kind, id, reason}]`; the page names the shots by number from `conflicts`, else from the scope. Fine as it is; if the server ever sends `changes` for such a turn the card could show them.
- Progress notes of a fast edit say "Đã chuẩn bị (N cảnh, chế độ fast)": the page maps them to its own words, so they never reach the owner.
- Preview clip: the page asks for at most 10 s because the existing button does; nothing needed.

## Known limits
- At 1280x720 the thread area is about 190 px high: a card is readable but the buttons of a long card (needs_choice, applied with several changes) need a scroll inside the thread.
- The model list in the settings dialog shows the ids when the server cannot read `agy models` (the test instance): the names appear when the list is there.

## Follow-up (coordinator's three fixes)
1. The action row of a card is directly under its header (Dừng, the two choices, Xem thử + Hoàn tác, Thử lại, "Chọn mô hình khác"); a turn that starts, ends or needs a choice is scrolled to the top of the history. Browser checks at 1280x720: every button of the `applied` card and of the `needs_choice` card lies fully inside the history area without scrolling.
2. Quota: `quotaView` in `editlogic.js` ("Mô hình đã dùng hết hạn mức. Mở lại lúc 14:20 [ngày 25/11]. Bạn có thể chọn mô hình khác." + button that opens the settings). Works with `retry_at` (local stamp, ISO or epoch seconds), only `retry_after_seconds`, or neither ("Chưa rõ khi nào mở lại."). Unit tests only (the rig cannot produce a quota). The job error is not shown by the page (it reads turns).
3. Settings: a real answer has `label` (not `name`) and `provider: antigravity`; options read "<label> (<id>)"; models with `enabled: false` and the `agy` entry that could not list are not offered; when agy gave no list, one banner "Chưa lấy được danh sách mô hình từ agy." replaces the per-row notes; a current value missing from a real list keeps "(không có trong danh sách)". The rig now has an `agy` entry in its models file and a fake `agy models` list of three models.
Counts: 212 node tests; browser check 69 PASS, 0 FAIL.
