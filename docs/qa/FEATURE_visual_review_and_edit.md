# Visual review and edit

## Implementation and integration

`bti.visual.edit` builds an isolated planner workspace with the current visual document, catalogue, timing, narration, selected moment IDs and request. It runs the planner validator and a scope check, asks for repair in the same agent session, searches and chooses newly wanted pictures, saves the visual document with revision history and calls the composer. Existing wanted entries remain intact. The standalone job occupies the picks-agent job slot. `bti.visual.review` renders one numbered frame per shot at a mark-visible time using the scorecard's technique list, includes spoken words, subject, reason and composer notes, asks again once for omitted shots, and groups findings into one edit per repair round. It performs at most two repairs; a missing requested picture is reported once in Vietnamese. Reports use the existing revision-bound viewer-review storage.

**Integration is incomplete.** The app does not mount the two routers in `bti.visual.edit` and `bti.visual.review`; the action specifications have no state builders and the existing `storyboard.review` action still points to the legacy review. Mount and route the visual path in the owning step-machine/app modules before use. The web-search cost disclosure in state also needs to cover visual edits when web search is enabled. The action block names the new review action `visual.review`, so the integration owner must reconcile it with the required `storyboard.review` identifier. No model or paid service was called.

## Real-data inspection

A copy of `arnolfini-v3` was placed under the private Windows snapshot, excluding caches, exports and audio, then converted with `bti.visual.from_project` and composed. Conversion covered 1,730/1,730 words in 108 moments. The composed storyboard had 114 shots, producing 19 sheets of six shots. I inspected all 19 sheets. The opening sheets show the whole painting between wide black bars twice, then the named couple, skirt and dog. The early sheets include a modern view of Lucca and two portraits; long runs of middle sheets repeat details of the painting and show no borrowed pictures. Sheet 9 shows repeated views of the couple and a small whole painting; sheet 19 shows the woman, the couple, portraits of Dürer and Velázquez, a close-up of the mirror and a final view of the couple. These are observations of stills, not a judgment of the whole video or of the pictures against every spoken sentence.

The converted input is not valid under the full planner check: the converter reported one V1 finding, 51 affected moments for V3, four for V5, three for V6, 51 for V7, and 41 for V8 (counts include judgment-level reports). It also recorded 14 conversion notes. A scoped edit is required to pass the full script check, so unchanged errors outside a three-moment scope can prevent that edit from completing. This is a real-data limitation, not an acceptance pass for the edit. The three findings used to create the example edit workspace below were explicitly simulated, not claims made by a model.

Review workspace: `acceptance/review-final/TASK.md`, `shots.json`, `sheet-001.jpg` through `sheet-019.jpg`, and `out/`. Edit workspace `acceptance/edit-final/`: `TASK.md`, `check.cmd`, `crop.cmd`, `out/`, `look/`; `inputs/{catalogue,context,dossier,facts,narration,painting,picks,scope,timing,visual}.json`, `inputs/PLAN.md`, `inputs/main_large.jpg`; `images/main.jpg`, `grid.jpg`, `pool_1.jpg` through `pool_56.jpg`, and `region_0.jpg` through `region_47.jpg`. These folders were generated inside `D:\code\behind-the-image\run\snap-review2\acceptance\`.

Rendered review instruction:

```text
# Review the video as a viewer

Open every numbered contact sheet and read `shots.json`, including the spoken words, the moment's subject and reason, and the composer's notes. Decide whether a viewer can follow what is being said. Judge only what is visible and supported by the supplied words and sources.

For every shot write one entry in `out/review.json`: `{"shots":[{"id":"s1","problems":[]}]}`. Use an empty list when it works, otherwise at most one object with `code` and a short Vietnamese `detail`. The only codes are `picture_mismatch` (picture does not show what the words are about), `text_wrong` (on-screen text is wrong), `context_missing` (the viewer lacks needed context), and `picture_repeated` (the same picture returns without reason). Answer for every shot.
```

Rendered edit instruction:

```text
# Edit the visual script

Read `inputs/visual.json`, `inputs/scope.json`, the narration, timing, painting and catalogue. Apply the owner's request to the selected moments. Keep every unselected moment and existing wanted entry unchanged. You may split or join moments only inside the selected word spans; add cast entries or adjust them where needed, while keeping cast used by unselected moments unchanged. Use existing regions or pool pictures, or add an open wanted picture with a sensible fallback. Do not create regions here.

Apply the picture, name, mark and source principles in `inputs/PLAN.md` to the changed moments; do not start the script afresh. Write the complete updated script to `out/visual.json`, preserving `made_from`. Run .\check.cmd and fix every ERROR.

Owner request:
Sửa các vấn đề khi xem video sau đây, chỉ dựa vào lời dẫn và nguồn của dự án. Có thể chọn vùng khác, ảnh khác trong kho, yêu cầu ảnh mới, ghép hai ảnh, chuyển điểm cắt hoặc bỏ một ý định hiển thị. Không thêm chữ không cần thiết.
s_m0001 (m0001): Thiếu thông tin để theo dõi: Giả lập: cần thêm ngữ cảnh.
s_m0002 (m0002): Hình không đúng nội dung lời dẫn: Giả lập: cần kiểm tra chủ thể.
s_m0003 (m0003): Hình lặp lại không có lý do: Giả lập: kiểm tra hình lặp.
```

## Verification

Windows snapshot: `tests/visual` 129 passed and 2 application integration tests failed after scope, short-mark, missing-picture and changed-cut tests; focused fake-agent tests exercise a rejected edit followed by repair, found and missing pictures, clean review, a grouped repair, a short answer, a missing picture and the two-round limit. The real-data inspection above is not an end-to-end model run. Additional regression and generator results will be recorded below.

The final sampling implementation also tests a mark that ends in under 1.3 seconds: the chosen frame stays inside that mark. On the Arnolfini copy, 11 sheets changed relative to the first sampling; all 11 were inspected again. The other eight were byte-identical.

One-folder Windows runs: visual 129 passed, 2 app-integration tests failed (both routes return 405); auto 270 passed; editor 534 passed; ops 565 passed; picks 506 passed; draft 650 passed; compose 39 passed; scorecard 12 passed; music 56 passed; export 89 passed, 2 skipped; identity 108 passed; output 81 passed; settings 44 passed; script 384 passed, 7 skipped; voice 108 passed, 1 skipped; title 198 passed; library 163 passed; longjob 69 passed, 1 skipped; clean_text 62 passed; engine (`not slow`) 859 passed, 14 skipped, 168 deselected. State after regeneration: 319 passed, 8 failed; CLI after regeneration: 132 passed. The first run had two additional state failures and two CLI failures caused by stale generated documents, now regenerated; the state action expectations, missing builders and `music_invalid` hint remain integration issues. Media: 458 passed, 2 failed, both point to existing `bti/music/fetch.py` privacy checks. Fsio: 8 passed, 1 failed, pointing to `bti/media/sources/web.py:302`. Mac Node: 507 passed, 1 skipped. No JavaScript files were changed. All three generator `--check` commands passed after regeneration.
