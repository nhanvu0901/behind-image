# C4 pages: the two simple pages, step 4 "Chọn hình" and step 5 "Dựng hình" (worker c4pages)

Worker `c4pages`, 2026-11-19, worktree `.worktrees/c4pages` (branch `wt/c4pages`, base `2bf0b20`). Brief: `.scratch/agy_tasks/c4pages/TASK.md`. Design: `docs/design/2026-11-18-agent-first-design.html`
("Bước 4 mới: Chọn hình", "Bước 5 mới: Dựng hình"). Built on `docs/qa/FIX_c2_box.md`, `FIX_c3_picks_agent.md`, `FIX_c5_cli.md`, `FIX_join2.md`, `FIX_c6_auto.md`.
No model was called (the mock agents of the test launchers only), no `.env` was read, no git command that writes was run, no Python ran on the Mac.

**State of this report (2026-11-19, 11:15).** The server was unreachable from 09:51 to about 10:35 (the Windows machine had lost power), and the Mac refused access to the project folder
from about 10:35 to 10:54 (it was restarted); the work was resumed at 10:59. Everything is now run on the server instance: the pages probe (section 9), the three existing probes, the Node tests,
and I looked at every screenshot of the probe myself (section 8). Section 8 separates what I saw on the real app (the server instance, real frames of the Arnolfini storyboard) from the earlier Mac-only pictures.
No Python folder was run by me (the coordinator runs them).

## 1. What was built

| Part | Files |
|---|---|
| step 5, the simple page | `static/js/sbsimple.js` (header, list of shots, the selected shot under the player, the problems dialog), `views/storyboard.js` (the two faces, the remembered choice, the keys), `css/edit.css` (block `c4pages`) |
| step 5, the pure parts | `shotsentence.js` (the one sentence of a shot), `shotlist.js` (rows, chapters, problems in words, the numbers of the header, the approval), `selectlogic.js` (Ctrl, Shift, chapter, the playhead) |
| step 4, the simple page | `views/picks_rows.js` (header, rows, "+" menu, three lists), `views/picks_rows_logic.js` (pure), `views/picks.js` (the two faces, the voice times, the check in words), `views/picks_auto.js` (two small additions), `css/picks.css` (block `c4pages`) |
| the request box | `promptedit.js` and `editlogic.js`: two options (`sel`, `words`) and one parameter (`chapter`); without them the box is what it was |
| words | `labels.js`: blocks `SHOT_WORDS`, `EDIT_PAGE_LABELS`, `PICKS_PAGE_LABELS` at the end of the file, each a complete `export const` (nothing inside another worker's table; `node --check` after every edit) |
| tests | Node: `shotsentence`, `shotlist`, `selectlogic`, `picksrows`, `pageswords` (44 tests). Browser probe: `tests/e2e/pages/pages.mjs` (103 checks, all pass on the server instance) |
| documents | `docs/APP_GUIDE.md` (sections 6 and 7 rewritten for the new pages, the old tools described under "Tự chọn tay" and "Chỉnh tay"), this report |

No Python file was changed, no route was added: the pages read the state they already read. The one extra read is `GET /api/projects/{pid}/voice` (step 4, once, for the start time of each line;
its `chunks` carry `beat` and `start`; used only when the voice is `done`; a failure leaves the rows without a time).

## 2. What each page shows on opening, in the order a person meets it

**Step 4, "Chọn hình"** (`#/project/<id>/picks`; `?mode=hand` opens the hand tools):
1. The frame of the app (top bar, stepper). Then the header: "Chọn hình", the project's name, "25/28 đoạn đã có hình" (lines with pictures or skipped) with a small bar, the amber button "3 đoạn chưa có hình" (it selects and scrolls to the first
   line without a picture, again to the next, and goes round), "1 đoạn bỏ qua" when there is one; on the right "Kiểm tra" and "Duyệt chọn hình". When the approval cannot be pressed a line beside it says what is
   missing (narration to approve, main painting to choose, "Còn N lỗi cần sửa"); lines without a picture only warn.
2. The agent's bar, one line that wraps: "Agent chọn hình", the agent select, "Để agent chọn hình" (after a run "Chọn lại phần còn thiếu"), the progress with the part and the limits while it runs, the result sentence
   after it. (The c3 bar; the select's "from where" line is hidden while the agent is the default; the request box's own select is hidden on this face, the bar's is the one.)
3. The rows, one per narration line, grouped by chapter (title, "4/5", fold, "Chọn cả chương"). Each row: its time (only when the voice is done) and "ĐOẠN 4", the first sentence ("Xem cả đoạn" for the rest),
   the pictures as small frames with a plain caption each ("Cả bức tranh", "Cận cảnh: khuôn mặt", "Ảnh: ...", "Bản đồ: ...", "Clip 6 giây: ..."; a "!" on the frame for a licence flag), a "+", "Tự chọn tay", the
   agent's reason ("Agent: ...") and, for a line without a picture, "Chưa có hình. Bản nháp sẽ dùng tranh chính ở đoạn này." with the agent's plain reason when the last run gave one. The first line is selected.
4. Under the rows: "Vùng của tranh chính (4)", "Hình bối cảnh (3)", "Clip (1)" (closed; a click shows the thumbnails and "Dùng ở đoạn 4, 7") and "Vẽ vùng trên tranh".
5. On the right: the request box ("Nhờ agent sửa hình"), "Sẽ sửa: Đoạn 4 đang chọn" / "2 đoạn đang chọn (4, 6)" / "Chương: ..." / "Cả video", its cards and "Lịch sử thay đổi".
6. A project without a main painting says so above the rows with "Chọn tranh chính"; a narration that is not approved gets one soft line with "Mở bước Kịch bản"; a failed load says one sentence with "Thử lại".

**Step 5, "Dựng hình"** (`#/project/<id>/edit`; `?mode=hand` or `?select=`, `?open=`, `?t=`, `?zoom=`, `?source=` open the editor):
1. The header: "Dựng hình", the project's name, "93 cảnh · 14:24", the red button "2 cảnh cần sửa" (jumps to the shots, again to the next) and "N vấn đề chung của video" when a problem belongs to no shot; on the right
   "Chỉnh tay" and "Duyệt" (a line says why it cannot approve yet; "Đã duyệt" and "Tiếp tục: Xuất video" after).
2. The player on the left (the same stage, frame and transport as the editor), then "the shot being looked at": number, from-to, one sentence, the words being read in it, its problems, "Sửa cảnh này ở Chỉnh tay".
3. In the middle the list: one row per shot (number, time, a small frame, the sentence, the length, "đã khóa", the problem in words), grouped by chapter (title, fold, "Chọn cả chương"). A shot the engine cannot draw has a hatched small frame, and the player says so in words while the playhead is in it.
4. On the right the request box and its cards (the c2 box, unchanged: before and after frames, "Xem thử", "Hoàn tác", "Lịch sử thay đổi").
5. "Chỉnh tay" turns the same elements into the editor exactly as it was (toolbar, tools row, inspector, timeline), with "Danh sách cảnh" first in the toolbar to go back. The choice is remembered per project.

## 3. How a shot's sentence is made, with ten real examples

`shotSentence(shot, env)` (`shotsentence.js`), pure, tested. `env`: the registry (`tech(id)`), the assets of the storyboard, and the key of the main painting (the asset whose title is the project's painting, else the picture the
base slots use most). Steps: (1) the base of the shot: a camera-family phrase table (`SHOT_WORDS.camera`: "Zoom vào", "Kéo ra, thấy", "Lia lên", "Zoom kèm dịch tới", "Giữ yên"), an explainer with its own facts (map "A tới B", timeline "N mốc",
tree "N người", two states "A và B"), a text card ("Thẻ chương: ..."), or, for every other technique, the registry's own Vietnamese name `label_vi` followed by the pictures of its slots; (2) the target of a camera shot: the region of the slot,
else the smallest named region the last camera key ends in (only when the camera comes in), else "cả bức tranh" / "ảnh “...”" / "clip “...”, N giây"; (3) the overlays as short phrases ("vòng sáng", "nhãn chi tiết"; the same phrase is counted: "2 vòng sáng"; more than
three are folded into "và N lớp khác"), joined with " · "; (4) at most 96 characters. A region is named by its label (Vietnamese as it is, any other word in quotes, a label that is only an id becomes "một chi tiết của tranh"). When nothing is known
the sentence is "Một cảnh". A test runs every technique of the registry as a base and as an overlay, and every shot of every real storyboard in the repository (more than 200): none gives an empty sentence, an id, an underscore name or a file name.

Ten real shots (the tests read them from `projects/arnolfini` and `projects/technique_lab`):

| Shot | Technique | Sentence |
|---|---|---|
| arnolfini s0001 | CAM-01 | Zoom vào “Mirror” |
| arnolfini s0002 | CAM-03 | Kéo ra, thấy cả bức tranh |
| arnolfini s0003 | STATIC-01 + AN-05 | Giữ yên cả bức tranh · thước kích thước |
| arnolfini s0004 | CAM-05 + 2 x HI-01 + X-ANN-01 | Zoom kèm dịch tới “Latin inscription” · 2 vòng sáng · nhãn chi tiết |
| arnolfini s0009 | X-CARD-02 | Thẻ tiêu đề: The arnolfini portrait |
| arnolfini s0011 | X-LAY-01 + X-ANN-02 | Ảnh tĩnh: ảnh “Grote Markt, Bruges” · nhãn tác phẩm |
| arnolfini s0020 | STATIC-01 + 2 x STATIC-08 | Giữ yên cả bức tranh · 2 nhãn tên |
| technique_lab s0011 | LAY-01 | Hai ô: cả bức tranh và ảnh “Virgin and Child with Canon v…” |
| technique_lab s0014 | LAY-04 | Cửa sổ ảnh chèn: ảnh “The Arnolfini Portrait” và clip “Virgin and Child with Canon v…” |
| technique_lab s0022 | CAM-05 + AN-01 | Zoom kèm dịch tới “Dog” · khoanh tròn |

Known limits, said plainly: the region labels of the real dossier are English ("Mirror", "Joined hands"): they are project data and stay as they are, in quotes. The map, timeline, tree and two-states sentences are tested on made-up parameters shaped like
the registry's (the real storyboards in the repository have none of them filled: `MAP-01` and `STATIC-06` in the lab have no places). The inference of the region from the camera is a heuristic (the centre of the last key inside a region with a size).

## 4. What moved behind "Chỉnh tay" and "Tự chọn tay"

| Behind | What | Where it was |
|---|---|---|
| "Chỉnh tay" (step 5) | the toolbar (Lưu, Kiểm tra, Hoàn tác, Làm lại, Bản nháp, Đề xuất, Duyệt, Xem thử 10 giây, "Tiếp tục"), the tools row ("Ảnh gốc", "Hiện vùng", the opening-style select), the inspector (Shot, Lớp phủ, Hình, Lỗi), the timeline, the drag handles of the preview, the shortcuts S, L, Delete, the draft and proposals | the whole page |
| "Tự chọn tay" (step 4) | the column of lines, the tray of a line (order, region, role, note, skip), the tabs Tranh chính, Tìm kiếm, Sách, Gợi ý (paid, with its confirmation), Video (YouTube link, You.com search, trim), Tải lên, the region editor, the old top (main painting, "Vùng trên tranh", "Kiểm tra", the note banners) | the whole page |

They work as before: the DOM of the editor is the same DOM (the simple page only hides parts of it and lays the player, the box and a new list out in three zones), and the hand face of step 4 is the same four columns. Not moved, kept on both faces: the player,
the request box and its list of changes, the agent's bar, the switch and the run bar of the shell. Not on the simple page of step 5 (reachable in "Chỉnh tay"): "Bản nháp", "Đề xuất", "Xem thử 10 giây", the opening-style select, saving by hand (a "Lưu" appears only when something is unsaved).

## 5. Tests

Node (Mac), `node --test tests/editor_frontend/*.test.mjs tests/picks/picks_logic.test.mjs tests/picks/sourcelimit.test.mjs` from the worktree, last lines as printed:

```
ℹ tests 439
ℹ pass 438
ℹ fail 0
ℹ skipped 1
```
(before: 393, 392, 0, 1; the one skipped is the existing `ISSUE_CODES` check that needs `.venv/bin/python`.) New files: `shotsentence.test.mjs` (11: the ten real shots, every technique, every real storyboard, the camera family, regions, explainers, clips, the main painting),
`shotlist.test.mjs` (8: rows, chapters, problems and what counts, "cần sửa" jumping, the header, the approval), `selectlogic.test.mjs` (8: click, Ctrl, Shift, chapter, the playhead, arrows), `picksrows.test.mjs` (14: captions, first sentence, voice times, rows, missing and its jump, header,
approval, blockers, the three lists, the check in words), `pageswords.test.mjs` (5: every word of the new tables is Vietnamese and shows no id; the box says "đoạn"; a whole chapter chosen in the list; the chip of a card of the pictures box; a chapter written in capitals read as words). The existing guards (`no_null_children`, `no_raw_text`) read the new files too.

Browser probes: section 9. Python: not run by me (the coordinator runs the four folders on this tree).

## 6. The changes to files of others, and the older probes

* `promptedit.js`: `mountPromptEdit` takes `sel` ({get, onChange, active?}) and `words`; while `sel.active()` the page owns the selection (no "Chọn nhiều ..." box, no chips, a new selection puts the scope back to "what is selected"). `editlogic.js`: `pickScope` and `pickBeatScope` take `chapter` (a chapter chosen as a whole),
  `pickBeatScope` takes `words`. Without these the functions answer as before (a test pins both).
* `views/picks_auto.js`: `onInfo` (the page repaints its rows when the reasons or the last result arrive) and `whyMissing(beatId)`.
* The request box now says "đoạn" (not "dòng") on both faces of step 4 (the owner's words in the brief: "2 đoạn đang chọn"); the hand tools' own columns keep "dòng".
* Older probes (each: why):
  * `tests/e2e/stages/common.mjs` `go()`: the first address now carries `?mode=hand`, so every probe that uses it (box, agent_select, picks_auto, the stages probes) meets the faces it was written for. One line.
  * `tests/e2e/storyboard/lib.mjs`, `storyboard/run.mjs` (two addresses), `round2/run.mjs` (`openEdit`), `round3/common.mjs` (`openEdit`): the same `mode=hand` in their own address.
  * `tests/e2e/box/box.mjs` and `tests/e2e/picks_auto/picks_auto.mjs`: "Dòng N đang chọn" became "Đoạn N đang chọn" (one check each).
  * `tests/e2e/stages/prompt_edit.mjs` is superseded (header) and was not touched. No selector moved: the old selectors are all still there on the hand faces.
  Run since: `box.mjs`, `picks_auto.mjs` and `agent_select.mjs` (section 9); the older ones that only had their address changed were not run.

## 7. Decisions where the brief or the sketch was silent

1. **Two faces over the same elements, not two copies.** Step 5: `data-mode` on `.edit-root`; the player, box and editor are the same DOM, so "Chỉnh tay" is the editor exactly as it was and its tests keep their selectors. Step 4: `data-mode` on `.pk-root`; "Tự chọn tay" shows the old four columns
   on the chosen line (the whole old page, not a part of it), "Về danh sách đoạn" or Escape (not while typing, not under a dialog) goes back.
2. **Remembering.** Step 5 remembers the last face per project (`localStorage`, guarded; the key `bti.edit.mode.<pid>`); an address that needs the editor (or `?mode=hand`) opens it there without changing the choice. Step 4 always opens on the rows (the brief asked the memory for step 5 only).
3. **The third zone's place.** At 1280x720 a vertical page cannot keep the player at 300 px and the list in view: three zones side by side (player, list, request box), the box last in the Tab order too (it is moved in the DOM when the simple face shows).
4. **Never nothing selected.** A request with no selection would fall back to a whole chapter; both pages keep at least one row selected (the first on opening).
5. **"Duyệt" on step 5 is pressable while there are problems:** the click opens the problems in words (the editor's dialog names shots and techniques by id). Its look is the quiet one ("blocked") and a line says why.
6. **A problem** is counted when it is an error, an incomplete shot or a shot that cannot be drawn; a plain warning is not. Each is a sentence from a code family (`incomplete`, `undrawable`, picture, region, too short, overlay outside, time, other); the technical text stays in the editor.
7. **"+" is the old quick add** (the same autosave as the old "+ Cả tranh chính" buttons): it is not in the change log, as today; only the agent and the request box write batches. So that the page's own edit can still be taken back, the foot of the list says "Đã thêm ... vào đoạn N." with **Hoàn tác** for nine seconds (it removes that picture when the line still has it there). After that, the request box or "Tự chọn tay" (the ✕ of the tray) is the way.
8. **Raw things hidden on the simple face of step 5:** the transport's "s0000 | CAM-01" text, the drag handles, the "Ảnh gốc" and "Hiện vùng" switches (reset when the face changes), the shortcuts S, L, Delete.
9. **Chapter titles** that are written as an id ("THE_MIRROR") are read as words ("The mirror"); "c03" becomes "Chương 3". The box's scope words use the editor's own function and still show the raw title of such a chapter (only the lab data has these).
10. **The Tab order** of the list is one stop (the selected row, arrow keys inside), then the buttons of each chapter; the rows of step 4 are the same.
11. The hand face of step 4 keeps the old header, with one added button, "Về danh sách đoạn".
12. **Numbers.** The header of step 4 counts a line as having its picture when it has pictures or is skipped (the agent's sentence and the chapter badges count the same way); "N đoạn bỏ qua" says how many of them are skipped. The count of lines without a picture is only the ones that have none and are not skipped.
13. **A shot the engine cannot draw** is not shown by its stand-in picture on the simple page (it carries the technique's id): a hatched small frame, and a note in words over the player while the playhead is in it. The editor shows the stand-in as before.
14. **`editlogic.js`** got two small changes the real app asked for: a picks turn's scope in words ("3 đoạn"), and a chapter written in capitals read as words. They also fix the old page.

## 8. What I saw, and on what

**On the real app** (a second instance on the server, port 8585, the mock agents, a copy of the real `arnolfini` storyboard with its real frames; screenshots `.scratch/c4pages/shots/*.png`, every state at 1280x720 and 1920x1080, all looked at one by one):
step 4 at rest (rows without pictures, the agent's bar, the count and the amber button), running (the part "(1/4)" and the limits), after the agent (pictures with their captions, the agent's reasons in
plain words, the reason it gave for the line it could not fill), a request and its card, "Tự chọn tay" (the old four columns, a search with its results), the three lists, the list of changes; step 5 on the video and the list (real frames, 93 shots, 14:24, chapters
with their titles), several shots and a chapter selected, the card of a request with its before and after frames, "Chỉnh tay" (the editor with its timeline fitted), a shot with a problem.
What the real app showed that the Mac pictures had not (all fixed, and the probe now checks them):
* A shot that cannot be drawn showed the engine's stand-in picture in the player and in its small frame: a dark card with the technique's id and "incomplete: slot image". The simple page now puts a note in words over the player ("Cảnh 1 chưa vẽ được: còn thiếu một hình hoặc một thông tin bắt buộc.") and a hatched small frame (`stage-note`, `sr-frame.bad`).
* The sentence of a shot without its picture read "Zoom kèm dịch bức tranh" (a missing preposition): "Zoom kèm dịch trên bức tranh".
* The chip of a card of the pictures box said "Chưa chọn cảnh nào." (the old scope function knew only shots; the old page has the same defect): it says "1 đoạn", "3 đoạn".
* The header counted 4/6 lines with pictures while the agent's sentence said 5/6 (a line that needs nothing of its own was not counted): the header counts settled lines (pictures or skipped) and keeps "1 đoạn bỏ qua".
* The chapters of the real project are written in capitals ("COLD OPEN"): the request box said "Chương: COLD OPEN" while the list said "Chương 1 · Cold open": both read them as words now.
* Scrolling up to a line put it under the sticky chapter title: `scroll-margin-top`.
* A `W.stageNote` that I had put in the wrong label table threw inside the list's repaint and the header never came (found by the probe, not by looking): fixed, and the checks about the note stay.
What the real app confirmed: the layout at both sizes (no horizontal bar; the preview 355 px high at 1280x720 with the shell's yellow banner above it), the selection with Ctrl/Meta and Shift and the chapter header, the request and its undo, the faces and the remembered choice, "Chỉnh tay" with a fitted timeline.
Two things that are not mine and were seen: the small pictures of the search results of "Tự chọn tay" are broken in this instance (the launcher's fake sources give addresses nothing serves: the same in the older probe), and the real chapter titles are English.
Earlier Mac-only pictures (`.scratch/c4pages/shots/mac/`, a Node stand-in for the API with invented lines about "The Scream", and the app's `?mock=1`) are what the first layout was made on; they are not evidence about the real app.

**The two contact sheets** (six pictures each, with captions): `.scratch/c4pages/shots/contact-sheet-1-step4.png` (rows at rest 1280, the agent running 1280, after the agent 1920, a request and its card 1280, the lists 1280, "Tự chọn tay" 1280) and
`.scratch/c4pages/shots/contact-sheet-2-step5.png` (the list 1280 and 1920, a chapter selected, the card of a request, a shot with a problem, "Chỉnh tay"). On them: step 4 reads as rows of narration with their pictures and the reason under each; the amber count is the first thing to find;
the agent's bar is one line; step 5 reads as player, list, box from left to right; the red count and the note over the player are the only red; at the thumbnail size the text is too small to read, the full-size pictures are the evidence.

## 9. Probes, exactly as printed

Pages probe, `BTI_SSH_HOST=winbox-cmd node tests/e2e/pages/pages.mjs` (instance on port 8585, suffix `c4pages`, stopped by the probe; afterwards only TIME_WAIT entries remain on 8585):
* first run: `98 pass, 4 fail`: "the header counts again: 5/6" (the header said 4/6: fixed as above), "Ctrl adds a line" and "Ctrl adds a shot" (headless Chrome on a Mac sends a Ctrl click as a right click that never reaches the page as a click: the probe now holds Meta, the page takes Ctrl or Meta), and "no failed request" (the broken thumbnails of the fake search results, now excluded by their address `/t/...`, nothing else).
* second run: `95 pass, 2 fail` (the wrong label table above; the probe found it).
* last two runs: `49 pass, 0 fail` (`--only=step5`) and the whole probe, last line as printed: `103 pass, 0 fail`.

Existing probes after my edits (one at a time, each instance stopped by its own script):
* `tests/e2e/box/box.mjs`: `54 pass, 0 fail` (as in `FIX_join2.md`).
* `tests/e2e/picks_auto/picks_auto.mjs`: `86 pass, 0 fail` (as in `FIX_join2.md`).
* `tests/e2e/agent/agent_select.mjs`: first run `64 pass, 1 fail` (the failing check, "put back to Gemini", reads `machine_default` right after the settings dialog's save toast, which is not a part of my pages: the dialog's own save was slower than the 15 s the probe waits; nothing in the check was changed); second run on the same code: `65 pass, 0 fail`.

Not run by me: the Python folders (the coordinator's), `tests/e2e/stages/prompt_edit.mjs` (superseded), the older probes whose navigation I changed to `?mode=hand` (`storyboard/run.mjs`, `storyboard/lib.mjs`, `round2/run.mjs`, `round3/common.mjs`) and the stages probes that use `go()`.
Not seen on the server because the probe cannot provoke it: a failing load of the picks (seen only against the Mac stand-in), a project without a main painting (same), the disabled agent button when the agent cannot run, the quota card on a handed-over turn.
A look at the pages by the owner is still the real test of whether a person who has never seen them understands them in a few seconds.

## 10. Needs another worker

* Nothing in Python. If the owner wants the "+" of step 4 in the change log (and not only the nine-second "Hoàn tác"), the page can send `add_pick` operations through `POST .../picks/ops` instead of the autosave (a change in `views/picks.js`, no server change).
* `errmsg.js` was not touched (no new error code).
