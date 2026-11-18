# REVIEW 2026-11-17: kiểm tra độc lập công việc của agent khác (3 đợt, 56 tệp chưa commit trên nền `6552271`)

Người kiểm tra: reviewer độc lập (Sonnet 5.5). Không sửa mã sản phẩm. Bằng chứng nằm ở `.scratch/review_20261117/` (nhật ký pytest, ảnh chụp trong `shots/`, ảnh khung trước/sau trong `frames/`, nhật ký các lần chạy mô hình `run_a.log`, `run_b.log`, `job_*.json`, `thread_*.json`, `prop_a.json`).

## 0. Tóm tắt một trang

| Khu vực | Hoạt động thật? | Kết luận |
|---|---|---|
| 1. Xuất video bỏ phụ đề | Có. Pytest xuất 78 đạt, trang Xuất video đúng, bản xuất cũ vẫn mở được, `.srt` cũ bị ẩn (404). | Giữ nguyên (xem 1.4: đây là quyết định sản phẩm đảo ngược thiết kế cũ, cần chủ xác nhận). |
| 2. Video clip ở bước Chọn hình | Tải tệp video lên: hoạt động (đã thử trong trình duyệt). Dán link YouTube / tìm: mã chạy được (đã nhập một đoạn 8 giây CC BY thật trên máy Mac) nhưng trên máy chủ Windows KHÔNG chạy được: thiếu `yt-dlp`. Dùng clip trong storyboard: hoạt động (khung vẽ thật + bản nháp tự động dùng FOOT-01). | Giữ và sửa (danh sách ở 2.5). |
| 3. Sửa storyboard bằng câu lệnh gõ (bước 5) | CHỈ MỘT PHẦN. Lần a (chương c01) chạy đúng, đúng phạm vi, đúng ý, 570 s. Lần b (chương c02) bị từ chối sau 26 phút, và tôi chứng minh bằng mã (không cần mô hình) rằng MỌI sửa chạm vào chương c02 đến c08 của `arnolfini-live` đều bị từ chối, kể cả khi agent trả lại storyboard không đổi (E0, blocker). Thiếu nhiều thứ của 7.4; chậm; nhiều chữ thô trên trang. | Giữ và sửa, bắt đầu bằng E0 (nhỏ: một điều kiện ở `compile.py:189`). |

Số kiểm thử tự chạy: JS Mac 188/188 đạt; Python trên máy chủ (cây của máy chủ trùng từng byte với cây Mac: 48/48 tệp đã băm giống nhau, nên dùng `--no-sync`): editor 158 đạt (255 bỏ qua do "reference projects are missing"), script+library 179 đạt (9 bỏ qua), media 110 đạt, picks 55 đạt, draft 113 đạt, export 78 đạt (2 loại trừ), longjob 66 đạt (1 bỏ qua, 3 loại trừ), voice 73 đạt (1 loại trừ). Không có test nào thất bại. Bộ kiểm trình duyệt cũ `tests/e2e/stages/run.mjs`: 70 đạt, 1 hỏng (SU-008, lỗi cũ đã biết, không do đợt này).

## 1. Xuất video bỏ phụ đề (đợt 08:26)

### 1.1 Nó làm gì
- `bti/export/subtitles.py` và `tests/export/test_subtitles.py` bị xóa. `mux_command` không còn đầu vào `.srt` và không còn `-c:s mov_text`. `run.py` bỏ phần làm cue; `FILE_NAMES = ("video","description","chapters")`; phiếu kiểm tra mất hai mục `subtitles`, `cues`; mô tả mất dòng "Subtitles available - turn on CC".
- Tương thích ngược ở `bti/editor/export_api.py`: `GET .../export/files/*.srt|.ass|.ssa` trả 404; `public_manifest()` lọc `cues`, `cue_problems`, mục `subtitles`/`cues` của bản xuất cũ và tính lại `report_status`; `clean_description()` cắt dòng "Subtitles available" khỏi mô tả cũ.
- Chủ thấy: trang Xuất video không còn chữ phụ đề, danh sách tệp chỉ có MP4, mô tả, mục lục.

### 1.2 Có chạy thật không (tôi đã chạy)
- `tests/export` trên máy chủ: 78 đạt.
- Trình duyệt, trang `#/project/lm-hrit0/export` (bản sao riêng, công cụ giả): không có chữ phụ đề/srt/CC; ảnh `shots/export-01-1280.png`.
- Bản xuất cũ thật (`arnolfini-live`, làm trước thay đổi): `GET /export` trả `files=[video,description,chapters]`, phiếu 10 mục không có phụ đề, `report_status ok`, không có `cues`; `GET .../arnolfini-live.srt` = 404; mô tả không còn dòng CC.
- Sau lệnh xóa không còn tham chiếu `subtitles` trong `bti/` ngoài chỗ đọc `ffprobe` (`check.py:55-67`, vô hại) và bộ lọc tương thích.

### 1.3 Lỗi
- Không có lỗi chặn. Xem 1.4 cho điểm cần hỏi.
- (minor, không phải hồi quy) `bti/export/check.py:29,55-67` vẫn đọc luồng phụ đề của tệp: vô hại, chỉ là mã thừa.
- (minor) Bản MP4 CŨ vẫn chứa luồng `mov_text` bên trong (do tài liệu đã nói "bản xuất cũ không bị thay đổi") và phiếu kiểm tra mới không còn báo điều đó; chỉ xuất lại mới sạch. Không cần sửa mã, chỉ cần chủ biết.

### 1.4 Điều trái với quy tắc / tài liệu
- Quy tắc "phụ đề không bao giờ vẽ vào hình" vẫn được giữ. Nhưng thiết kế cũ (mục 8 của `2026-11-16-stages-3-4-6-and-draft-design.md`) CHO PHÉP và yêu cầu `.srt` kèm luồng `mov_text`; đợt này xóa hẳn và sửa tài liệu cho khớp (`docs/APP_GUIDE.md` mục 9, hai tệp thiết kế). Tài liệu đã khớp mã. Nhưng trong `git status` không thấy yêu cầu của chủ trong ghi chú nào: cần chủ xác nhận đây là điều họ muốn (YouTube cần `.srt` để tải phụ đề lên; xóa hẳn nghĩa là không còn đường sinh `.srt` về sau, ngoài việc dựng lại từ git).
- `tests/export/test_subtitles.py` (123 dòng) đã xóa đúng với tính năng đã xóa; không có kiểm thử nào bảo vệ thứ còn cần.

### 1.5 Kết luận khu vực 1
Giữ nguyên mã. Việc cần: chủ xác nhận bỏ `.srt` (và nếu cần `.srt` để đăng YouTube thì phải đảo lại).

## 2. Video clip ở bước Chọn hình (đợt 12:58 đến 13:06)

### 2.1 Nó làm gì
- Tab mới "Video" ở bước 4 (`views/picks.js`), hai đường vào:
  - Dán link YouTube + "Xem link (miễn phí)": `POST /api/projects/{pid}/picks/video-search {url}` chạy `yt-dlp --dump-single-json` (và phụ đề) rồi trả một thẻ: tiêu đề, kênh, độ dài, giấy phép, các "đoạn gợi ý" (từ chương/phụ đề/biểu đồ "xem lại nhiều nhất"), khung YouTube nhúng để xem trước.
  - Tìm từ khóa: `POST .../video-search {query, confirm_paid:true}`, gọi You.com (tốn tiền, có hộp xác nhận) rồi lấy metadata song song.
  - Thẻ có ô "Từ giây/Đến giây" (0,5 đến 120 s), ô ghi chú và nút "Cắt & thêm vào dòng" gọi `POST .../picks/import-clip {url,start,end,title}`: tải đoạn (yt-dlp `--download-sections`, tối đa 180 s), chuẩn hóa H.264 30 fps CÓ TẮT TIẾNG, làm tờ contact, ghi `media/<khóa>.mp4` và `picks.json` (asset `kind:"video"`, `duration`), gắn vào dòng đang chọn với vai trò `video`.
- Tab "Tải lên" nhận thêm mp4/mov/webm/m4v (`/picks/upload`): chuẩn hóa tắt tiếng, đo thời lượng.
- Bên dưới: `workspace.py` sao chép video và tạo tờ contact 2x2 cho agent; `compile.py` tự gán slot `footage` (FOOT-01) cho clip video; `TASK.template.md` hướng dẫn dùng FOOT-01 hoặc LAY-04; `app.py` + `media_adapter.py` nhận video ở route tải lên của trình biên tập cũ; thumbnail video có đường lui sang OpenCV.
- Giấy phép: chỉ là cờ (`strict_licence=False`), không từ chối nhập. Đúng quy tắc của chủ.

### 2.2 Có chạy thật không (tôi đã chạy)
- `tests/media` 110, `tests/picks` 55 đạt trên máy chủ; JS `picks_logic` đạt.
- Tải tệp lên (trình duyệt, bản sao riêng trên máy chủ, tệp mp4 4 giây có tiếng): 0,6 giây, tệp chuẩn hóa còn H.264 30 fps, KHÔNG còn luồng âm thanh (ffprobe trên tệp tải về), thẻ "VIDEO · 4.0s Test clip" có hình thu nhỏ, vai trò "Video" (ảnh `shots/picks-06-after-upload-1280.png`).
- Dùng clip: `POST /frame` với storyboard có shot FOOT-01 trỏ tới clip đã tải lên vẽ ra đúng khung của clip (`frames/vid_frame.jpg`, thấy dải màu thử). Chạy "Dựng tự động" (provider `auto`) sau khi duyệt lại danh sách hình: bản đề xuất có 1 shot FOOT-01 dùng đúng clip và `assets` chứa clip (ví dụ `draft_20261117-183025`).
- Dán link trên máy chủ Windows: lỗi, trang nói "Không đọc được video: Máy chủ thiếu công cụ yt-dlp hoặc ffmpeg để xử lý video." (ảnh `shots/picks-03-paste-link-1700.png`). Lý do thật: `shutil.which("yt-dlp")` = None và `yt_dlp` không import được trong `.venv` của máy chủ; `requirements.txt` không có `yt-dlp`. Tôi không cài (quy tắc). Nghĩa là TRÊN MÁY CHỦ TÍNH NĂNG LINK/TÌM KHÔNG CHẠY, hai nút đầu của tab Video chỉ cho thông báo lỗi.
- Nhập thật một lần, làm trên máy Mac (có yt-dlp 2026.08.19 và ffmpeg), thư mục nháp riêng `.scratch/review_20261117/clipproj`: gọi `clips.import_clip` cho `https://www.youtube.com/watch?v=aqz-KE-bpKQ` (Big Buck Bunny, kênh Blender, giấy phép "Creative Commons Attribution", 635 s) từ giây 30 đến 38. Kết quả sau 17,9 s, thử một lần: `media/big_buck_bunny.mp4`, 1920x1080, 30 fps, 8,0 s, 7,9 MB, không âm thanh, `credit.licence "CC BY"`, `flag null`, kèm tờ contact. (Đây là ngoại lệ có chủ ý: máy chủ thiếu công cụ nên không làm được ở đó; chỉ là một lệnh nhập, không phải pytest.)
- Trang không có chỗ nghe thử/xem clip đã cắt (chỉ có hình thu nhỏ): xem 2.4.

### 2.3 Lỗi

| # | Mức | Vị trí | Mô tả và cách thấy | Hồi quy? |
|---|---|---|---|---|
| C1 | major (chặn tính năng trên máy chủ) | `requirements.txt` (thiếu), máy chủ `.venv` | `yt-dlp` không được khai báo và không cài trên máy chủ: dán link/tìm bằng You.com luôn lỗi `tool_missing`. Xem bằng: mở tab Video trên máy chủ, dán link, bấm "Xem link". Mã chỉ ghi "pip install yt-dlp" trong thông báo lỗi (`clips.py:68`), không khai báo ở đâu. | Không (mới). |
| C2 | major | `bti/picks/service.py:249-290` (`import_video_clip`), `bti/media/clips.py:116-118,443-452` | Đường dẫn dán vào được chấp nhận bởi `video_id()` bằng `re.search` KHÔNG neo (`clips.py:118`), rồi chính chuỗi thô (không chuẩn hóa thành `https://www.youtube.com/watch?v=<id>` như `inspect_video_url` làm) được đưa nguyên làm một phần tử argv của yt-dlp. Chuỗi `--batch-file=C:/x youtube.com/watch?v=aaaaaaaaaaa` qua được `video_id` và yt-dlp coi nó là tùy chọn `--batch-file` (đã thử trên Mac: yt-dlp báo "batch file ... could not be read"). Không có shell nên không phải chèn lệnh, và vì cả chuỗi là một đối số nên tác hại bị giới hạn (một tùy chọn `--x=...`, không có URL), nhưng đáng chuẩn hóa. Cách thấy: gọi `POST /picks/import-clip` với `url` như trên. App chỉ lắng nghe 127.0.0.1, nên mức tác hại thực tế thấp; đánh "major" vì là lỗ hổng đối số lạ trong mã nhận chuỗi người dùng. | Không. |
| C3 | minor | `bti/editor/static/js/views/picks.js:393,370,417` | Chữ thô lên màn hình: lý do đoạn gợi ý bằng tiếng Anh từ máy chủ (`chapter "..."`, `subtitle "..."`, `most replayed (0.87)`), `v.error` thô, tên kênh. Quy tắc "mọi chữ qua labels/errmsg" bị vi phạm (kiểm thử `no_raw_text` vẫn đạt vì nó không quét các nhánh này). | Không. |
| C4 | minor | `bti/picks/service.py:272-275` + `picks_api.py:203` | Việc cắt đoạn chạy ĐỒNG BỘ trong một yêu cầu HTTP (tối đa 180 s tải + chuẩn hóa), không phải việc dài (long job). Trang chỉ đổi nút thành "Đang cắt..." và không thể hủy; nếu chủ đóng trang thì kết quả vẫn có nhưng không biết. | Không. |
| C5 | minor | `bti/media/clips.py` `import_clip` | Tệp được ghi hai lần (`cache/clips/*.mp4` và `media/*.mp4`), cache không bao giờ dọn: mỗi lần thử một đoạn thêm ~8 MB (đoạn 8 s) x2 trên đĩa. | Không. |
| C6 | minor | `bti/editor/app.py` route `/assets/upload` + `media_adapter.py:168-190` | Đường tải lên của trình biên tập cũ nhận video nhưng KHÔNG chuẩn hóa/tắt tiếng (copy nguyên), khác `/picks/upload` (chuẩn hóa). Hai đường cho kết quả khác nhau. | Không. |
| C7 | minor | thiết kế | Thẻ video luôn dùng khung nhúng YouTube; với video "tắt nhúng" chỉ mở tab mới. Không xem được chính đoạn đã cắt trước khi dựng. | Không. |

### 2.4 Chủ sẽ thấy gì khó hiểu ở trang Chọn hình (đầu vào cho thiết kế lại)
- Tab "Video" nằm cạnh "Tải lên"; hai nút hàng đầu ("Xem link (miễn phí)", "Tìm trên YouTube (You.com, tốn tiền)") có chữ dài, nút thứ ba "Dùng chữ gợi ý của dòng này" thực chất cũng là TÌM TỐN TIỀN nhưng không ghi.
- "Cắt & thêm vào dòng" bị tắt xám nếu chưa chọn dòng ở cột trái mà không giải thích rõ (chỉ có chú giải khi rê chuột).
- Hai ô "Từ giây/Đến giây" là số thập phân; không có thanh kéo hoặc nút "đặt tại đây từ khung đang xem" (khung nhúng YouTube không cho đọc thời điểm).
- Không có chỗ xem lại clip sau khi cắt: trong khay chỉ có hình thu nhỏ + nhãn "VIDEO · 4.0s" và chọn vai trò (danh sách 8 vai trò gồm "Cả bức tranh", "Bản đồ"... vô nghĩa với video). Vùng/region bị ẩn đúng, nhưng chủ không biết video sẽ vào chỗ nào trong storyboard.
- Khi máy chủ thiếu yt-dlp, trang chỉ hiện một toast đỏ rồi biến mất, vùng bên dưới vẫn ghi "Dán link YouTube (miễn phí)...": không có câu nói rõ "tính năng này chưa dùng được trên máy này".

### 2.5 Kết luận khu vực 2
Giữ và sửa: (1) thêm `yt-dlp` vào `requirements.txt` và cài trên máy chủ (cần chủ đồng ý vì là cài đặt); (2) chuẩn hóa URL trong `import_video_clip` (chỉ nhận `https://www.youtube.com/watch?v=<id 11 ký tự>` dựng lại từ `video_id`); (3) chữ thô ở C3; (4) đưa việc cắt vào long job có Hủy; (5) cho xem clip đã cắt.

## 3. Sửa storyboard bằng câu lệnh gõ ở bước 5 (đợt 13:28 đến 14:59)

### 3.1 Nó làm gì (lời thường)
- Dưới khung xem trước ở bước 5 có hộp "Sửa video bằng prompt": ô gõ, "Phạm vi" (N shot đang chọn / chương tại đầu phát / cả video; có thẻ chip để thêm/bỏ shot), "Mô hình", ô "Tiếp tục hội thoại trước", nút "Gửi cho agent", rồi danh sách "Lịch sử sửa bằng prompt".
- Route: `POST /api/projects/{pid}/draft/edit {instruction, scope:{shots|chapter|all}, model?, followup?, base_rev?}` (việc dài, trả `job_id`, `turn_id`), `GET .../draft/thread` (đối chiếu `reconcile_thread` rồi trả các lượt), `DELETE .../draft/thread`. Dữ liệu: `cache/draft/thread.json` mỗi dự án (tối đa 50 lượt), và một đề xuất `proposals/edit_<giờ>.json`. Bản đề xuất mở ở hộp "Đề xuất" sẵn có; "Áp dụng" kiểm tra `base_rev` khớp (409 `stale` nếu storyboard đã lưu đổi) và ghi `accepted` vào lượt.
- Phía máy chủ: `resolve_edit_scope` chặn phạm vi rỗng/lạ/trộn/khóa hết; `compile` ở chế độ sửa tắt hạ cấp; `decompile.scope_violations` từ chối kết quả đụng cảnh ngoài phạm vi, cảnh khóa, lớp phủ khóa, mốc thời gian bị dịch; kết quả chỉ ghi chú (không spec) thành `no_change`; có `compile_error`, `edit_degraded`, `edit_outside_scope` (lượt thành `refused`).

### 3.2 Có chạy thật không (bằng chứng tôi tự chạy)
- Python: `tests/draft` 113 đạt trên máy chủ (gồm 23 test sửa trong `tests/draft/test_edit.py`). JS `tests/editor_frontend/promptedit.test.mjs` đạt (188/188 tất cả).
- Lỗi vào của route (máy chủ thật, `arnolfini-live`): `base_rev` cũ trả 409 `stale_revision`; chương lạ 422 `unknown_chapter`; tên mô hình xấu 422 `bad_model`; trộn hai phạm vi 422 `edit_bad_scope`; shot lạ 422 `edit_bad_scope`; gõ rỗng 422 `edit_empty_instruction`.
- Chạy mô hình thật (qua ứng dụng chính của máy chủ, dự án `arnolfini-live`, chỉ có 3 lần như cho phép; storyboard `rev b80987be...` TRƯỚC = SAU, không áp dụng gì):

| Lần | Lệnh | Phạm vi | Mô hình | Thời gian | Bước agent | Kết quả |
|---|---|---|---|---|---|---|
| a | "zoom in more slowly on the mirror and add a ring around it" | s0001, s0056 | gemini-3.8-flash-high | 570 s (agent 552 s, ghép 13 s) | 116 | `done`, đề xuất `edit_20261117-181857`, 93 -> 92 cảnh |
| b | "make this chapter more varied: do not use the same camera technique on two neighbouring shots, and keep every shot at least 5 seconds long" | chương c02 | gemini-3.8-flash-high | 1557 s (agent 1540 s, sát giới hạn 1800 s; ghép 12 s) | 435 | LỖI `edit_outside_scope`: kết quả bị TỪ CHỐI, không có đề xuất, 26 phút mô hình bỏ đi (xem E0) |
| c | (lần hủy ngoài ý muốn, xem 3.6) | 1 shot | gemini-pro-orchestrator-g1-pro | hủy sau ~1 phút | n/a | hủy bằng nút "Hủy" |

  Lần a, so từng cảnh với bản đang lưu (bỏ trường dẫn xuất `_t`): chỉ `s0001` đổi (thêm lớp phủ AN-01, vòng quanh vùng MIRROR) và `s0056` bị xóa; 91 cảnh còn lại giống từng chữ; chỉ `assets`/`end` không đổi. Cả hai cảnh đều nằm trong phạm vi. Xóa `s0056` làm `s0001` kéo dài từ 8,7 s thành 17,2 s: "zoom chậm hơn" được thực hiện BẰNG CÁCH GIỮ NGUYÊN các khóa camera và kéo dài thời gian (không đổi tham số zoom). Ảnh `frames/compare_a.png` (hàng trên trước, hàng dưới sau; t = 1, 4, 7,5, 12, 16 s): ở giây 4 sau khi sửa có vòng trắng quanh gương; ở giây 7,5 cảnh trước đã zoom sát gương còn cảnh sau vẫn đang ở khung rộng, đúng "chậm hơn". Việc làm đúng ý. Một nhược điểm: cảnh kéo dài cũng làm mất cú kéo ra ở `s0056` mà chủ không yêu cầu (đề xuất nói rõ "removed").
- Trình duyệt: nhìn ngay trên ứng dụng chính (đọc, không áp dụng): thẻ lịch sử, thanh tiến trình khi chạy lần b (`shots/live-02-proposal-1700.png`), hộp đề xuất mở ra (`shots/live-03-proposal-1280.png`), hủy (`shots/edit-05-cancelled-1700.png`), 1280x720 (`shots/edit-06-card-1280.png`).

### 3.3 Lỗi

| # | Mức | Vị trí | Mô tả và cách thấy | Hồi quy? |
|---|---|---|---|---|
| E0 | BLOCKER | `bti/draft/compile.py:189-191` (`zones`, nhánh `if self.edit`) | Ở chế độ sửa, thẻ chương cũ của storyboard chỉ được "giữ nguyên" nếu thời điểm của thẻ `<= c["start"] + EPS`. Nhưng với `timing` hiện nay các thẻ nằm TRONG khoảng lặng đầu chương, SAU `c["start"]` (c02: `start 73.57`, thẻ s0004 ở 77.27 và s0005 ở 80.17; c03: start 195.21, thẻ s0015 ở 195.61). Nên thẻ bị bỏ, `scope_violations` thấy "shot s0004/s0005 was removed (outside the scope)" và "s0060: effective end was changed", và cả kết quả bị từ chối bằng `edit_outside_scope`. Cách thấy KHÔNG cần mô hình (chỉ đọc, dự án thật `arnolfini-live`, script `.scratch/review_20261117/viol3.py`, chạy trên máy chủ): lấy chính storyboard đang lưu, `decompile` ra spec, nộp lại NGUYÊN VĂN như "kết quả của agent" cho `compile_specs` ở chế độ sửa: phạm vi `{"chapter":"c01"}` -> 0 vi phạm; `{"chapter":"c02"}` -> 3 vi phạm; `{"chapter":"c03"}` -> 2; `{"shots":["s0009"]}` (một shot ở c02) -> 3. Nghĩa là: ở dự án này chỉ chương c01 (không có thẻ) sửa được; mọi sửa ở 7 chương còn lại, kể cả một shot đơn, luôn bị từ chối SAU khi mô hình đã chạy 10 đến 26 phút (đúng như lần b). Lần b khẳng định: tôi chạy lại việc ghép trên đúng tệp `out/c02.json` của agent và nhận đúng 3 vi phạm trên. Test của agent kia (23 test sửa, xanh) không bắt được vì fixture không có thẻ nằm sau `start`. | Không (mới; `kept_cards` có từ `6552271` nhưng chưa có đường vào). |
| E0b | major | `bti/draft/run.py` (nhánh `res.violations`) + `thread.py` | Khi bị từ chối, trang chỉ hiện nhãn "Từ chối (ngoài phạm vi)" và câu chung "Agent đã thay đổi phần ngoài phạm vi...": không nói cảnh nào, không giữ kết quả của agent để xem, không cho agent một lượt sửa (draft có vòng sửa 2 lượt, sửa-theo-prompt thì không). Công việc 26 phút bỏ đi. Cũng ghi nhận: ghi chú của agent nói "Compiler check reports 0 error(s)" trong khi bước ghép của máy chủ từ chối; chưa tìm vì sao công cụ kiểm tra trong thư mục làm việc không thấy ra. | Không. |
| E1 | major | `bti/editor/static/js/promptedit.js:461` + `errmsg.js` | Lượt bị hủy (`error:"cancelled"`) hiện câu "Lỗi: Có lỗi: [object Object]" ngay dưới huy hiệu "Đã hủy" (đã đo trong trình duyệt: `.prompt-turn-card` có chữ đó). `stageErrorText('draft', {body:{code}})` không có mã `cancelled`, và `stale_revision`, `edit_locked_changed` cũng rơi vào "Có lỗi: [object Object]". Cách thấy: gửi một lệnh rồi bấm Hủy. | Không (mới). |
| E2 | major | `promptedit.js:387` | Thanh tiến trình in trạng thái thô tiếng Anh: "Chuẩn bị dữ liệu: done - Đã chuẩn bị dữ liệu.", "Agent sửa storyboard: running - Bước 86, agent_response; đã viết 1/1 chương.", "Ghép và kiểm tra: queued". `draftpanel.js:79` dịch bằng `TEXT.partState`, hộp mới thì không. `agent_response`, `tool` là chữ thô của chương trình. | Không. |
| E3 | major | `promptedit.js:451-456` | "Agent: ..." in nguyên ghi chú của mô hình bằng tiếng Anh, kèm mã nội bộ (`s0056`, `AN-01`, `HI-01`, "reduced from 8"). Vi phạm quy tắc "mọi chữ trên màn hình bằng tiếng Việt qua labels". (Phần `instruction` của chủ là chữ của chính họ: đúng.) Thiết kế muốn "một dòng lý do của agent", ở đây là cả một đoạn dài tiếng Anh. | Không. |
| E4 | major | `bti/editor/app.py:881-899`, `proposals.js:38` | Đề xuất sửa trở nên VÔ DỤNG ngay khi chủ lưu bất cứ thay đổi nào (kể cả ở cảnh khác): `apply` trả 409 `stale`, trong khi giao diện hiện "dựa trên bản cũ... Vẫn áp dụng?" (cho phép bấm) rồi báo lỗi chung "Việc này xung đột với trạng thái hiện tại của dữ liệu." Lệnh mất 9 đến 13 phút của mô hình, không thể áp dụng một phần cũ, không có ghép. Lời hứa "chủ sửa tay tinh chỉnh song song" mâu thuẫn. | Không (mới, nhưng làm hỏng thiết kế 7.4: "Undo hoạt động..."). |
| E5 | major | `proposals.js` (không đổi), thiết kế 7.4 | THIẾU phần cốt lõi của 7.4: hộp đề xuất vẫn chỉ là JSON thô trước/sau (`shots[id=s0001].overlays[id=o4]`, khối `{ "technique": "AN-01", ...}`), KHÔNG có khung trước/sau, KHÔNG có đoạn xem thử của vùng đổi, KHÔNG có "một dòng lý do cho từng cảnh" (chỉ có tóm tắt chung). Chủ không biết lập trình sẽ không đọc nổi (ảnh `shots/live-03-proposal-1280.png`). | Không. |
| E6 | major | `bti/draft/run.py:254` | `r.conversation_id_in = None` luôn đặt None: dù `agy.run` đã nhận `conversation_id`, KHÔNG BAO GIỜ tiếp nối cuộc trò chuyện; "Tiếp tục hội thoại trước" chỉ sao chép 3 lượt trước vào `INSTRUCTION.md` (đã lưu `conversation_id` trong lượt nhưng không dùng). Thiết kế 7.4 nói tiếp nối khi còn dùng được. Mất ngữ cảnh ảnh đã xem của agent, tốn thêm thời gian. | Không. |
| E7 | major (hiệu năng, không phải lỗi mã) | `skills/storyboard_draft/TASK.template.md`, `agy.py` | Một lần sửa 2 cảnh mất 9,5 phút và 116 bước; agent viết xong chương rất sớm (thanh tiến trình đứng ở 0,89 từ giây 80) rồi còn kiểm tra thêm ~7 phút. Thiết kế hỏi "20 giây hay 3 phút": thực tế 9 đến 13 phút. Tiến trình hiển thị 0,07 rồi 0,89 rồi đứng: chủ không thấy gì chạy. | Không. |
| E8 | minor | `promptedit.js:14`, `agy.py:34`, `draft_api.py:48` | Mặc định vẫn `gemini-pro-orchestrator-g1-pro`; chủ muốn `gemini-3.8-flash-high` làm mặc định. | Không. |
| E9 | minor | `bti/draft/run.py:479-489` (và 532 cho dựng nháp) | Thứ tự kiểm tra: `agy_missing` được kiểm trước phạm vi/đối số, nên máy không có agy không thể thấy lỗi phạm vi; và ở bộ kiểm giả của `tests/e2e/stages` (cố ý giấu `agy` khỏi PATH) agy vẫn được tìm thấy (nguyên nhân chưa tìm, không đọc `find_agy`/PATH sâu hơn) nên nút "Gửi cho agent" ĐÃ KHỞI ĐỘNG MỘT LẦN CHẠY MÔ HÌNH THẬT trên bản sao (xem 3.6). Bộ giả không phục vụ được việc kiểm sửa, và còn nguy hiểm: nó phát lệnh thật. | Không. |
| E10 | minor | `promptedit.js:377` | Giờ hiện "06:30:54 PM" theo ngôn ngữ trình duyệt (không phải định dạng Việt). Chuỗi "chương c02" (id thô) ở `scope_words` (`inputs.py:372`) trong khi danh sách chọn ghi "Chương COLD OPEN". | Không. |
| E11 | minor | `promptedit.js` bố cục, `edit.css` | Ô lịch sử chỉ cao 46 px (1700x1000) và 20 px (1280x720): không đọc được; khung xem trước ở 1280x720 co còn ~190 px chiều cao (`shots/edit-06-card-1280.png`). Chọn thêm cảnh dùng một `<select>` liệt kê tất cả cảnh (93 dòng). | Không. |
| E12 | minor | `run.py:198-203` (`_write_last`), `run.py:153` (`overview`) | `last_run.json` dùng chung cho dựng nháp và sửa: sau một lần sửa, hộp "Bản nháp" ghi `n_shots 92`, đề xuất `edit_...` như thể là bản nháp (đã thấy: `GET /draft` trả `last_run` của lần sửa). | Không. |
| E13 | minor | `run.py:518-522` | Dòng lượt được ghi SAU khi việc đã chạy (`m.start` rồi `append_turn`): nếu việc lỗi cực nhanh, `update_turn` không thấy lượt và lượt nằm ở "running" cho tới lần `GET /thread` sau (được `reconcile_thread` sửa). Cửa sổ nhỏ. | Không. |
| E14 | minor | `promptedit.js:479` xóa lịch sử | "Xóa lịch sử" không hỏi lại và mất cả lượt đã áp dụng. | Không. |

Phần được kiểm và KHÔNG thấy lỗi (đã thử): phạm vi và khóa được ép phía máy chủ (chạy `scope_violations`, `compile`, lỗi vào; lần a: 91 cảnh ngoài phạm vi giống từng chữ), không tự nới phạm vi (chính E0 là ép quá chặt, không phải quá lỏng), `base_rev` cũ bị chặn, không ghi đè storyboard (rev không đổi trước/sau cả 3 lần chạy), lượt không lẫn giữa các dự án (tệp ở `cache/draft` của từng dự án), HTML không bị chèn (mọi chữ mô hình vào bằng `text:`/`h()`; không dùng `innerHTML`), việc dài được nối lại sau khi tải lại trang (nút "Hủy" xuất hiện lại, đã thấy khi tải lại trang giữa chừng), hủy hoạt động (lượt thành `error/cancelled`). Chưa thử trong trình duyệt: hộp thoại "Lưu thay đổi chưa lưu trước khi gửi" (chỉ đọc mã `promptedit.js:294-308` và bài test giả của agent kia), vì thử thật nghĩa là thêm lần chạy mô hình.

### 3.4 Thiếu so với mục 7.4
- Có: nhập yêu cầu, phạm vi bằng chữ ("3 shot đang chọn"/chương/cả video), chỉ sửa trong phạm vi (đã đo), ghi chú khi không làm được (`no_change`), đề xuất không đụng storyboard cho tới khi chủ bấm, một luồng mỗi dự án, `POST /draft/edit` và `GET /draft/thread`.
- Thiếu: khung trước/sau cho từng cảnh đổi (E5); đoạn xem thử của vùng đổi (E5); một dòng lý do cho từng cảnh (E5); tiếp nối cuộc trò chuyện của agy (E6); "Undo hoạt động trên thay đổi đã chấp nhận như bất kỳ sửa nào" có (qua commit sẵn có) nhưng đề xuất cũ không áp dụng được sau khi lưu (E4); "hỏi lại chủ" như một kết quả hợp lệ chỉ có dạng ghi chú.
- Mâu thuẫn với quy tắc: E1 đến E3 (chữ thô trên màn hình), E8 (mô hình mặc định).

### 3.5 Kết luận khu vực 3
Giữ và sửa (chưa nên đưa cho chủ dùng cho tới khi E0 xong: ở dự án thật nó hỏng 7 chương trên 8). Phía máy chủ ép phạm vi chặt và đúng khi qua được (lần a). Sửa: E0 trước hết (cho thẻ nằm trong khoảng lặng đầu chương, ví dụ so với `c["lead"]["end"]` hoặc thời điểm lời đầu tiên thay cho `c["start"]`; thêm test với timing có `lead`), rồi E0b, E1, E2, E3 (dịch/ẩn), E4 (cho áp dụng sau khi lưu hoặc ghép), E5 (khung trước/sau, một dòng lý do), E6, E8, E11; xem lại tốc độ (E7: bắt agent dừng sớm hơn, hiển thị bước thật).

### 3.6 Ghi chú về chạy mô hình
- Lần c là NGOÀI Ý ĐỊNH: khi thử trang bước 5 trên bản sao riêng (cổng 8562, dự án `lm-hrit0`), bấm "Gửi cho agent" khởi động một lần chạy agy thật (`gemini-pro-orchestrator-g1-pro`), vì chương trình `agy` vẫn được tìm thấy trên máy chủ dù bộ giả cố giấu nó khỏi PATH. Tôi hủy nó bằng nút "Hủy" sau khoảng một phút (dùng luôn để thử hủy, E1). Tổng số lần dùng mô hình: 3 (a, b, c); không có lần theo dõi (follow-up).

## 4. Chưa kiểm được và vì sao
- Đường tải lên video qua yt-dlp thật trên máy chủ: thiếu yt-dlp, không cài (cấm).
- Hộp "Lưu thay đổi chưa lưu trước khi gửi" (cần thêm một lần chạy mô hình) và sửa tiếp nối (follow-up) bằng mô hình thật (không dùng lần thứ ba).
- Phạm vi "khóa hết" (`edit_bad_scope` khi mọi cảnh bị khóa) chỉ qua test của agent kia (`test_scope_resolution`, đạt), dự án thật không có cảnh khóa và tôi không được khóa cảnh trong `arnolfini-live`.
- 255 test của `tests/editor` bị bỏ qua ("reference projects are missing") nên không chạy ở máy chủ này.

## 5. Dọn dẹp
Bản sao riêng cổng 8562 (daemon 77048, đường hầm 77074, tiến trình máy chủ 5848) đã dừng bằng `remote.mjs down`; thư mục tạm `bti-stages-oll98vem` trên máy chủ (còn sót sau khi dừng) đã xóa tay, `bti-stages-repo` đã mất; đường hầm riêng cổng 8571 (pid 77993) đã dừng; không còn Chrome do tôi mở; không đụng `scream`, cổng 8550/8560, khóa nặng. `git status --short`: chỉ thêm tệp báo cáo này (57 dòng so với 56); không có tệp test mới (thư mục `tests/review_20261117` rỗng đã xóa); tệp thử nằm ở `.scratch/review_20261117/` (được git bỏ qua).
