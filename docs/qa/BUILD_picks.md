# BUILD: step 4, picks ("Chọn hình")

Status 2026-11-16: first batch written. Compiled and imported on the Mac; **no test has been run** (tests run only on the Windows server, which was not ready: no `docs/WINDOWS.md`). Second batch (video clips, Pexels, Pixabay) not started.

## What exists

| Path | What |
|---|---|
| `bti/picks/doc.py` | `bti.picks/1` document: normalise (forgiving read), `doc_problem` (strict check of a client's document), revision (sha1 without `approval`), atomic save with `.prev.json`, `base_rev` (StaleRevision), `Held` (picks lock plus "project still exists"), approval pinned to the picks revision and the narration revision, `issues()` (errors: no main, unknown asset or region, missing file; warnings: beat without pick, flagged asset, unknown beat) |
| `bti/picks/context.py` | reads the narration (and whether its approval stands), dossier identity and details (`D1...`), the beat's first search words, the books' images and pages of the project |
| `bti/picks/service.py` | `payload`, `put`, `import_asset`, `import_book`, `upload`, `search`, `set_regions`, `approve` |
| `bti/picks/suggest.py` | You.com suggestion job on `bti.longjob` (one part per beat, resumable, `PartError` with Vietnamese sentences), `FakeProvider`, `YouComProvider`, stored suggestions in `cache/picks/suggestions.json` |
| `bti/picks/__init__.py` | `state(project_dir)` -> `{state: none|running|stale|done, detail, main_asset, picked, beats}`; never raises |
| `bti/editor/picks_api.py` | `router` (module level, reads `app.state.projects_root` and optional `app.state.picks_provider`), `make_router(root)` returns the same router |
| `bti/media/` | advisory gate (below); new source `sources/bookpage.py` (`book`) |
| `bti/editor/static/js/views/picks.js`, `picks_logic.js`, `static/css/picks.css` | the page; `picks_logic.js` holds the pure helpers (kept under `views/` so the file list of the contract is respected) |
| `tests/picks/`, `tests/media/` | see "Tests" |

Routes (all under `/api/projects/{pid}/picks`): `GET` and `PUT` (`{picks, base_rev}`), `POST search`, `POST import`, `GET book-images`, `POST import-book-image`, `POST upload`, `PUT assets/{key}/regions` (`{regions, base_rev?}`), `POST suggest` (`{beats, confirm_paid: true, refresh?}` answers `{job_id}`), `GET suggestions` (extra, not in the contract), `POST approve` (`{rev}`). Every route that changes the document answers the whole state (`picks`, `rev`, `approved`, `approval_reason`, `issues`, `narration`, `identity`, `details`, `suggest`), plus `asset_key` and `asset` for imports. Errors are `{detail, code, ...}`; codes: `stale` (409, with `rev`), `narration_not_approved` (409), `picks_have_errors` (422, with `issues`), `unknown_asset`, `unknown_source`, `not_found`, `query_required`, `source_unreachable` (503), `source_error`, `region_name`, `region_shape`, `region_outside`, `image_empty`/`image_unreadable`/`image_truncated`, `confirm_required`, `suggest_off`, `suggest_no_key`, `suggest_failed`, `busy`, `too_many`, `longjob_missing`, `invalid`. A damaged `picks.json` is a 409 with `data_error: "picks"`.

Document rules worth knowing: `PUT` cannot invent an asset or change its file, size or credit (those are what is on disk); it can change beats, `main_asset`, and each asset's title, artist, year and regions; assets left out are dropped from the picks (the files stay in `media/`). Saving a changed document drops the approval. The approval stands only while the picks revision and the narration revision both match and the narration is itself approved.

## The advisory gate (bti/media)

- `credit.flag` is `rejected | unknown | small | null` on every asset the facade makes (Commons, Met, books, uploads). Licence first (`rejected`: NC, ND, fair use, all rights reserved, not public domain; `unknown`: missing or unclear), then `small` (short side under 1200 px, still the `min_short_side` argument). A size of 0 means unknown, not small.
- `import_candidate` and `add_upload` never raise `LicenceRejected` or `ImageTooSmall` any more; sources are asked to download with no floor. `add_upload` needs no metadata (missing author is recorded as "unknown"). Candidates from `search` carry `flag` too. The broken-file refusal (`image_empty`, `image_unreadable`, `image_truncated`) stays: it is about the file, not the licence.
- Asset keys now also avoid the keys of `picks.json`.
- The storyboard view's import and upload use the same facade, so they are advisory too, **provided the real facade is loaded**. The stub path of `bti/editor/media_adapter.py` (used only when `bti.media.api` cannot be imported) still refuses; see "Needs another agent".
- `bti/media/clips.py` still gates on the video licence. It is not reachable from any route yet; it becomes advisory with the second batch.
- Book images: source `book`, ids `<book_id>/img/<xref>` and `<book_id>/page/<n>`; pixels from `bti.library.extract` (imported only when something is rendered); licence recorded as missing (flag `unknown`), credit `source: "book"`, `source_url` = "<book title>, p. N", author = the book's author. The route only imports pictures of the books the project was made from.

## Tests (written, not run)

Counts by file (functions; parametrised cases not counted): `tests/picks/test_doc.py` 9, `test_api.py` 20, `test_suggest_state.py` 12, `picks_logic.test.mjs` 9 (node), `tests/media/test_bookpage.py` 4 (new), `test_licence.py` +2. Run on the server only: `tools/deploy/remote_test.sh tests/picks tests/media` and `node --test tests/picks/picks_logic.test.mjs`.

- **Faked:** Commons and Met (`FakeNet` openers over `tests/media/fixtures`), book rendering (a renderer function), the suggestion provider (`FakeProvider`). The long-job runner is the real `bti.longjob.manager` (not a fake). An autouse fixture makes `suggest.live_allowed()` False for every test, so the real You.com provider cannot be built by accident; the one test of `YouComProvider` replaces `research.visual_research` itself.
- **Changed tests in `tests/media/test_api.py` (they asserted a refusal):** `test_import_rejects_licence_before_download` is now `test_import_nc_licence_is_kept_and_flagged_not_refused`; `test_import_too_small` is now `..._is_flagged_not_refused` (and checks the 500 px floor still works); `test_met_non_pd_rejected` is now `..._flagged_not_refused`; `test_add_upload_requires_fields_and_licence` is now `test_add_upload_needs_no_metadata_and_flags_the_licence`; the candidate key-set test gains `flag`. `test_clips.py` is untouched (clips not wired). Classification tests of the gate in `test_licence.py` are unchanged: the gate still classifies, it just does not block.
- Not covered: the page in a browser (`picks.js` is only syntax-checked); real Commons and Met; PyMuPDF rendering of a real book page (`default_renderer`); the real You.com call (never made).

## Open questions and decisions

- `config/picks.json` `{"suggest": "youcom" | "off"}` (optional) is the flag for the real provider; the default is `youcom` (the button works) and every click still asks the owner to confirm the cost and sends `confirm_paid: true`. A file that is not mine; CORE may prefer another place.
- One job kind, `picks`, is used for suggestions; `state()` reports `running` while one is active for the project.
- Suggestions are kept per beat in `cache/picks/suggestions.json` and a beat that already has some is skipped unless `refresh`, so a re-run does not pay twice.
- The page saves by itself 0.7 s after an edit (PUT with the revision it loaded); a 409 reloads the project's picks and discards the unsaved edit, with a message.
- Disagreement with the contract: none that blocks. Notes: (1) the contract's example uses key `A` for the main asset; keys here are slugs of the title (`arnolfini_portrait`), as the media layer has always made them; the field is free text for the draft compiler. (2) `status: picked` is set by the page when an item is added; a beat with items but status `todo` (hand-edited file) is normalised to `picked` on read.

## Needs another agent

CORE:
- Register `picks_api.router` in `app.py` (`app.include_router(router)`; it needs `app.state.projects_root`, which exists). Call `bti.picks.state(project_dir)` for step 4 in `pipeline_api.py` (it returns `none|running|stale|done`, `detail` is Vietnamese). Mount `views/picks.js` for the step `picks` (same `mount(host, ctx)` shape as `script.js`; returns `isDirty`, `save`, `dirtyMessage`). Add `<link rel="stylesheet" href="css/picks.css">` to `index.html`. Remove the `picks` entry of `PLANNED` and `NOT_BUILT`.
- `errmsg.js`: `DATA_ERROR.picks` = "Tệp chọn hình (picks.json) của dự án bị hỏng." The view has its own table `ERR` (by `code`) for the codes listed above; merge it if you want one place. Nothing else is needed for plain errors (they fall through to the catalogue).
- `labels.js`: the view's local tables `LBL` (flag names and explanations, roles, tab names, issue sentences, approval reasons) can move there. Flag words: `rejected` "Giấy phép bị hạn chế", `unknown` "Chưa rõ giấy phép", `small` "Ảnh nhỏ".
- Storyboard view: its media tab (`js/media.js`, `app.py` upload route) should show `asset.credit.flag` too, and must not require licence, source and author before an upload (the server no longer does).
- `bti/editor/media_adapter.py` stub path still refuses licences (only used without `bti.media.api`).
- Project delete: call `bti.picks.doc.forget_lock(pdir)` next to the other lock forgets (optional, a leak of one lock object).

DRAFT: reads `picks.json` as in section 6. `assets[*].credit.flag` is new and optional; `regions` values carry `x, y, rx, ry, label`.

## Guide: "Chọn hình" (for the owner)

**Chọn hình là gì?** Sau khi lời dẫn được duyệt, bạn quyết định mỗi dòng lời dẫn sẽ cho xem hình gì: bức tranh chính, một chi tiết của nó, hay một hình khác. Bước này nằm giữa Kịch bản và Dựng hình.

**1. Chọn tranh chính (làm đầu tiên).** Mở tab "Tranh chính" ở cột bên phải. Ô tìm đã có sẵn tên tranh và tác giả; bấm "Tìm". Kết quả lấy từ Wikimedia Commons và The Met, mỗi ảnh cho biết kích thước và giấy phép. Bấm "Làm tranh chính" ở ảnh bạn muốn. Cũng có thể lấy ảnh từ sách (tab "Sách") hoặc tải ảnh của bạn lên (tab "Tải lên").

**2. Cờ cảnh báo.** Ảnh có thể mang một cờ: "Giấy phép bị hạn chế", "Chưa rõ giấy phép" hoặc "Ảnh nhỏ" (dưới 1200 px). Cờ chỉ để bạn biết: ảnh vẫn dùng được và không bao giờ bị từ chối. Nguồn và giấy phép luôn được ghi lại để điền vào phần mô tả video.

**3. Vẽ vùng chi tiết.** Bấm "Vùng trên tranh". Bấm vào tâm của chi tiết trên tranh rồi kéo ra tới mép, đặt tên (D1, D2... là các chi tiết trong hồ sơ tác phẩm, hoặc tên tùy ý), bấm "Thêm vùng này", rồi "Lưu các vùng". Vùng dùng được ở mọi dòng.

**4. Chọn hình cho từng dòng.** Cột trái là các dòng lời dẫn theo chương, số bên phải là số hình đã chọn. Chọn một dòng: cột giữa hiện lời dẫn, các từ gợi ý hình (bấm vào để tìm), và "khay" hình của dòng. Thêm "cả tranh chính" hoặc một vùng bằng các nút nhỏ, hoặc bấm "Thêm vào dòng" ở một kết quả tìm. Mỗi hình có ô chọn vùng, vai trò (cả bức tranh, chi tiết, bối cảnh, so sánh, tài liệu, bản đồ, video), ghi chú, và nút đổi thứ tự hoặc bỏ. Dòng không cần hình riêng thì để trống: bản nháp sẽ dùng tranh chính ở đó. Dòng bạn không muốn tính là thiếu thì tick "Bỏ qua dòng này". Mọi thay đổi tự lưu sau chưa đến một giây.

**5. Tìm thêm.** Tab "Tìm kiếm": gõ từ khóa, hoặc bấm "Dùng chữ gợi ý của dòng này". Tab "Sách": ảnh và trang trong chính các cuốn sách của dự án. Tab "Gợi ý": nút "Gợi ý thêm" hỏi You.com nên cho xem gì. **Nút này tốn tiền**, chỉ chạy khi bạn bấm và xác nhận, tính cho từng dòng. Kết quả được giữ lại, bấm lại cho dòng đã có thì không tốn thêm.

**6. Duyệt.** Bấm "Kiểm tra" để xem lỗi (phải sửa: chưa có tranh chính, hình hoặc vùng không còn) và cảnh báo (không chặn: dòng chưa có hình, ảnh có cờ). Rồi bấm "Duyệt chọn hình". Chỉ duyệt được khi lời dẫn đã duyệt. Nếu sau đó bạn sửa hình hoặc sửa lời dẫn, bước này cần duyệt lại và bước Dựng hình sẽ nói bản nháp cũ không còn khớp.

**Nếu có sự cố.** "Nguồn ảnh đang bận": đợi vài giây rồi tìm lại, hoặc bỏ tick một nguồn. "Tệp ảnh bị cắt dở": tải lại tệp đầy đủ. "Chọn hình đã đổi ở nơi khác": trang tự tải lại bản mới nhất; phần bạn vừa sửa chưa lưu sẽ mất.

## Run on the server (2026-11-16)

`tools/deploy/remote_test.sh tests/picks`: 43 passed. `tests/media`: 106 passed. `node --test tests/picks/picks_logic.test.mjs` (Mac): 9 passed.
Fixes needed after the first run: (1) the test compared the revision of a raw document with that of the normalised one (test fixed; the code is right, the revision is always of the normalised document); (2) the app has a GET catch-all `/{path:path}` inside `create_app`, so a router included after it never answers a GET: the tests move the routes before it (`picks_helpers.mount`), and **CORE must include `picks_api.router` before that catch-all**.
View: unknown issue codes and job errors no longer show server text (`jobErrorText`, local code table); on a 409 the page reloads, re-applies the owner's pending beat edits that still make sense and says in one line what was dropped.
