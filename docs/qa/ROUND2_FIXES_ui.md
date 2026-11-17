# Round 2: UI fixes (answer to ROUND2_ui.md)

Fixer: UI, 2026-11-16. Mock model only, no network. Nothing committed. Part 1 done; part 2 waits (see the end).
The rule behind all four bugs, stated once in `ROUND2_decisions.md`: nothing the owner reads comes straight from the server or from an exception. Errors go through `describeError`, issues through `issueText`, enum values through `labels.js`. A static test now enforces it.

## R2U-001 Errors in the storyboard view: fixed
- Cause: `views/storyboard.js`, `proposals.js`, `preview.js`, `media.js` built text from `e.status || e.message` instead of `describeError`.
- Change: every catch now uses `errorToast` / `errorInto` / `describeError` (the same helpers as the script view): `views/storyboard.js` (registry load, project load, restore, approve, save, clip, clip job error via new `jobFailText` in `errmsg.js`), `proposals.js` (list, open, apply, skipped files), `preview.js:frameError`, `media.js` (search, import, upload, licence reasons via new `licenceText` in `errmsg.js`), `app.js` boot error, `views/library.js` last-resort message, `slots.js` (no raw message as a name). The data-error box of the storyboard view shows a Vietnamese sentence and the server text under "chi tiết".
- Swept (every module that catches or shows text): `app.js`, `api.js`, `actions.js`, `checks.js`, `edit.js`, `formgen.js`, `formui.js`, `gallery.js`, `inspector.js`, `media.js`, `preview.js`, `proposals.js`, `slots.js`, `timeline.js`, `views/home.js`, `views/library.js`, `views/artwork.js`, `views/script.js`, `views/storyboard.js`. In `views/script.js` three tooltips still carried the raw English issue text (`title: x.message`); removed.
- Tests: `tests/editor_frontend/no_raw_text.test.mjs` (static: fails when a view shows `.message`, a status number, a raw issue/job text); e2e `R2U-001` (the tester's), `R2U-001b` (clip preview and proposals box with the server down).

## R2U-002 Storyboard issues are translated: fixed (templates by message today; by code in part 2)
- Cause: `inspector.js` drew `issue.message`; `issueText` knew only the script codes.
- Change: new `js/sbissues.js` (templates for every message the storyboard checks produce today, 70 entries keyed by a provisional code plus a regex of the English message; parameter reasons translated one by one; enum values through `labels.js`); `errmsg.js:issueText` sends storyboard issues there (by `code` when known, else by message). An unknown code or message gives "Shot s0005: có một điểm chưa đúng ở mục "thời lượng". Xem "chi tiết"." with the English only under "chi tiết". `inspector.js` issues tab uses `issueText`, no path line. Every issue names its shot (by id when the engine gives it, else by position).
- Swept (everything that lists or counts issues): `inspector.js` (issues tab), `views/storyboard.js` (counter, toasts), `checks.js` (already Vietnamese, passes through), `slots.js` (incomplete list), `views/script.js` (tooltips), `app.js`.
- Tests: `sbissues.test.mjs` (every message of `bti/engine/storyboard.py` and `registry.py` has a template and no English; unknown code; shot naming; script codes untouched); e2e `R2U-002`, `R2U-002b`.
- Left for part 2: align the provisional codes with `ISSUE_CODES`, use `args`, the test that reads `ISSUE_CODES`.

## R2U-003 Two tabs on one storyboard: fixed
- Cause: the 409 block of `saveOnce` only offered "keep draft" / "reload", showed "(409)", promised an export, and never rebased, so the draft could not be saved.
- Change: `js/sbmerge.js` (pure three-way merge: each shot by id, each other top-level key, the shot list as one unit; `mergedNote`), `store.js:rebase`, `views/storyboard.js:resolveConflict` / `conflictDialog`. Not both changed: merge, validate the merged document, save, one line "Đã ghép với bản sửa ở nơi khác (...)". Errors in the merged document or both changed: dialog "Có người sửa storyboard này ở nơi khác" with "Để sau", "Lấy bản trên máy chủ" (asks again), "Ghi đè bằng bản của tôi" (asks again; the server keeps the other version in `history/`). After any choice a later save works (the rebase moves the base revision).
- Tests: `sbmerge.test.mjs` (11 cases); e2e `R2U-003` (same shot: dialog, "Để sau", ask again, overwrite saves), `R2U-003b` (two shots: merged and saved with one line).

## R2U-004 Labels: fixed
- Cause: raw ids in dropdowns.
- Change: `labels.js` adds `INTENT` (12), `EASE` (7), `VALUE` (all enum values of the registry, with `PARAM_VALUE` for words that mean two things), `SOURCE`, `TEXT_SOURCE`, `intentLabel`, `valueLabel`, `sourceLabel`, `textSourceLabel`. Used in `inspector.js` (shot and overlay intent, source chip), `formui.js` (every enum select and the camera ease select), `gallery.js` (intent filter and chips), `views/library.js` (text source tag). The raw value is the option's tooltip. Technique ids stay.
- Tests: `labels_registry.test.mjs` reads `style/gae/techniques.json` and fails when an intent or enum value has no label or shows an underscore; e2e `R2U-004`, `R2U-004b`.

## Small items
- Home columns line up: `css/shell.css` last column of `.prow` is a fixed 176 px, actions right-aligned. Check `R2U-S5`.
- Backspace: already resolved to "delete" in `shortcuts.js` (kept, undoable). Check `R2U-S2`. Written in `docs/APP_GUIDE.md`.
- Badges refresh at once: `api.js` notices the first request that fails and the first that works again (`setNetworkHook`); `app.js` reloads the health badge on both. Check `R2U-S3`.
- No `/audio` or `/waveform` when the storyboard names no audio: `timeline.js:loadWave`, `views/storyboard.js:setupAudio`. Checks `R2U-S1` (no audio: no request), `R2U-S1b` (audio: waveform still loaded).
- Garbage in a camera field: `formui.js` camera numbers keep the old value on blank or non-number, zoom stays above 0, `at` clamped. Check `R2U-S4`.
- Model list (API fixer): part 2.

## Needs the other agent
- Engine: `ISSUE_CODES` and per-issue `code`/`args` are not delivered yet (`docs/qa/ROUND2_FIXES_engine.md` says "in progress"). The page works without them.

## Tests changed and why
- `tests/e2e/round2/run.mjs` `R2U-003`: tab B now edits the SAME shot as tab A (shot 4). With a note on another shot (6) the contract (R2U-003) merges automatically and shows no dialog, so the original scenario could not show the dialog it asserts on. The assertions about the dialog text and buttons are unchanged; the check now also proves "Để sau", asking again, and overwrite. The merge scenario is the new `R2U-003b`.
- `tests/e2e/round2/run.mjs` `R2U-004`: the row is found by `/ý đồ|intent/i` (the label is now "Ý đồ", no English word "intent"). Assertions unchanged.

## Part 2 status: done
Backend reports read: `ROUND2_FIXES_engine.md` (99 codes in `ISSUE_CODES`, `numeric_only`, `pattern`, `min_items`/`max_items`) and `ROUND2_FIXES_api.md`.
1. Engine issue codes: `js/sbissues.js` `BY_ARGS` has a Vietnamese template for every code, using `args` (param, technique, limits, region, index, hint). The message-pattern table is only the fallback. Test `sbissues.test.mjs` runs `.venv/bin/python` to read `ISSUE_CODES` and fails when a code has no template (or a template has no code), and renders each code with missing args.
2. Home: rows with `data_error` are "Dự án hỏng" rows (`views/home.js:damagedRow`), "Tiếp tục" disabled, the picker lists them disabled (`app.js`), a deep link shows the Vietnamese data-error sentence, Delete shows `project_file_damaged` as "sửa hoặc xóa thư mục bằng tay" (`errmsg.js:BY_CODE_HTTP`). Check `R2U-P1`.
3. Approve: button reads "Đang duyệt...", the header says what is happening, a second click returns at once; a refusal with `undrawable` issues opens the same kind of list as "incomplete", one row per shot or overlay, a click jumps to it (`views/storyboard.js:undrawableItems`). Check `R2U-P2`.
4. `render_failed`: the preview line and the Shot tab say "Không dựng được hình của shot s0012 (kỹ thuật CAM-01)..."; a thumbnail that fails is asked again for the reason and the shot gets a red dashed frame and "!" in the timeline (`timeline.js:explainThumb`, `ctx.thumbFails`); a failed preview clip uses the job's `error_code`, `shot` (`errmsg.js:jobFailText`). Check `R2U-P3`.
5. Registry keys: `pattern_hint` under string fields, a wrong value is marked before saving (`formgen.js:validateValue`, `formui.js:setNote`); `min_items`/`max_items` bound the point editor buttons and are checked for lines and points; `numeric_only` removes region names from the point editors and marks them; box range (inside 1920x1080, at least 16 px) and camera zoom up to 1000 mirrored. Check `R2U-P4`, unit tests in `part2.test.mjs`.
6. Script page: the narration badge and a note above it use `approval_reason` ("dàn ý đã đổi, cần duyệt lại" and a sentence on what to do); `stale` alone is only a hint; a refused approval lists `chapter_diff` in a dialog and in the note. Check `R2U-P5`.
7. Model list: the Antigravity flag `agy: {ok: false, reason}` shows "Lệnh Antigravity không trả lời kịp..." with "Thử lại" (`/api/models?refresh=1`) (`views/script.js:paintModels`, `labels.js:agyProblem`). Checks `R2U-P6` (real list), `R2U-P6b` (list with the flag injected).
8. New codes in `errmsg.js`: `project_busy`, `too_deep`, `project_file_damaged`, `undrawable`, `render_failed`, and `data_error` values `project`, `source`, `library`. Unit test `part2.test.mjs`.
9. Screenshots (opened with Read): `.scratch/round2_ui_fix/shots/` at 1700x1000 (`p1_*`, `*_p2_*` without prefix `1280_`) and 1280x720 (`1280_p2_*`, `p1_*_1280`). At 1280x720 the status text in the header was cut, so it was shortened ("đang kiểm tra khi duyệt...").
Run the e2e with `--size=1280x720` for the small screenshots.

Remarks for the owner of the backend: with the default model list the Antigravity command answers on this machine, so the flag was proven with an injected list, not a real failure. The engine report notes a clone of `arnolfini` was refused by approval as `undrawable` (X-LAY-01); the page lists it like any other refusal.
