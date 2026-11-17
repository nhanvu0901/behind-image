# Vòng 3: kiểm tra giao diện trình duyệt (R3U)

Người kiểm tra: agent độc lập, Chrome thật (headless), máy chủ và dữ liệu tạm từ `tests/e2e/shell_library_script/lib.mjs`, chỉ mô hình `mock`.
Chạy: `node tests/e2e/round3/run.mjs` (mỗi lỗi một check khẳng định hành vi ĐÚNG, FAIL khi lỗi còn). Kiểm tra ngày 2026-11-16 ~21:00-21:30, trước khi các fix vòng 3 bắt đầu.

## Lỗi

### R3U-001 (minor, storyboard, xác nhận: 2 lần) Ý đồ không có trong danh sách (hoặc rỗng) hiện như "Giới thiệu bối cảnh"
Các bước: mở `arnolfini_edit`, bước Dựng hình; đặt ý đồ của một shot là `dance` (hoặc để trống), chọn shot, tab Shot.
Mong đợi: ô "Ý đồ" hiện giá trị lạ như nó là (hoặc "chưa chọn"), như `formui.js:93` làm với tham số enum.
Thực tế: ô hiện "Giới thiệu bối cảnh" (mục đầu), trong khi dữ liệu giữ `dance` / `null`. Chủ tưởng shot là "establish". Giá trị lưu vẫn đúng (không bị đổi nếu không chạm vào ô).
Nguyên nhân: `inspector.js:132-133` (và lớp phủ `inspector.js:189`) chỉ dựng option từ `ctx.reg.intents`, không thêm giá trị hiện tại.
Hồi quy: mới từ `464bf85` (nhãn mới); cái cũ cũng không thêm giá trị lạ. Check: `R3U-001`.

### R3U-002 (major, script, xác nhận: 2 lần) Không xóa được chương thừa khỏi lời dẫn từ trang, nên không duyệt được lời dẫn
Các bước: dự án mới, lập dàn ý và viết lời dẫn (mock), duyệt cả hai; xóa chương cuối (c06) khỏi dàn ý, lưu, duyệt dàn ý; mở bước Kịch bản, bấm "Duyệt lời dẫn".
Mong đợi: hộp nói "Xóa chương đó khỏi lời dẫn" và trang có nút làm việc đó.
Thực tế: tiêu đề chương c06 chỉ có "Viết lại chương" và "+ Dòng". Bỏ hết từng dòng (nút "Bỏ") vẫn để lại chương rỗng `c06:0` trên máy chủ, và duyệt vẫn bị từ chối với cùng câu. Chủ chỉ thoát bằng cách viết lại cả lời dẫn (mất sửa tay) hoặc thêm lại chương vào dàn ý (id tự sinh, không đặt được `c06`). Ảnh: `.scratch/round3_ui/shots/f_refused.png`.
Nguyên nhân: `views/script.js:447-453` (tiêu đề chương không có nút xóa), lời khuyên ở `script.js:234`. Có thể cần cả API (op xóa chương).
Hồi quy: lời khuyên này mới từ `464bf85` (R2B-001), nút thì chưa bao giờ có. Check: `R3U-002`.

### R3U-003 (minor, storyboard, xác nhận: 2 lần) Bấm lỗi về tệp ảnh nhảy tới shot 1
Các bước: mở `arnolfini_edit`; trong thư mục tạm thay `media/durer.jpg` bằng chữ; bấm Duyệt; ở tab Lỗi bấm dòng "Tệp media/durer.jpg của hình durer không đọc được như một ảnh".
Mong đợi: tới shot dùng ảnh đó (s0080) hoặc tab Hình.
Thực tế: chọn s0001, đặt đầu phát về 0:00 (ảnh `shots/d3_click_issue.png`).
Nguyên nhân: `inspector.js:216-220` `selectIssue` rơi về shot đầu khi lỗi không có shot. Check: `R3U-003`.

### R3U-004 (minor, storyboard, xác nhận: 2 lần) Khung xem không vẽ được: tab Shot không giải thích, và hình cũ còn nằm trên màn hình
Các bước: như R3U-003 (ảnh hỏng), chọn s0080.
Mong đợi: dòng cạnh khung xem VÀ tab Shot (R2U-P3 hứa) đều nói "Không dựng được hình của shot ..."; khung xem không còn hình của shot khác.
Thực tế: chỉ có dòng cạnh khung xem; tab Shot không có `.render-fail`; canvas vẫn vẽ bức tranh Arnolfini của shot trước, kèm khung camera K1/K2, nên dòng cảnh báo mâu thuẫn với hình. Slot hình hiện icon ảnh vỡ với chữ "durer". Ảnh: `shots/d3_durer_shot.png`.
Nguyên nhân: `preview.js:frameError` không ghi vào `ctx.thumbFails`/không xóa canvas; banner chỉ đọc `ctx.thumbFailOf` (`inspector.js:120`).
Hồi quy: chưa hoàn chỉnh từ `464bf85`. Check: `R3U-004`.

### R3U-005 (major, storyboard, xác nhận: 2 lần) Ctrl+Z đầu tiên sau "Đã ghép với bản sửa ở nơi khác" xóa sửa đổi mà tab kia đã lưu, và Lưu ghi đè nó không hỏi
Các bước: hai tab `arnolfini_edit`. Tab A sửa ghi chú shot 4, Lưu. Tab B sửa ghi chú shot 10, Lưu (hiện "Đã ghép..."; B giờ có cả hai). Ở B bấm Ctrl+Z một lần, rồi Ctrl+S.
Mong đợi: hoàn tác chỉ lấy lại việc của B; chữ của A còn.
Thực tế: ghi chú shot 4 về giá trị gốc (sửa của A biến mất khỏi bản nháp, nháp "chưa lưu"); Ctrl+S gửi với rev mới nên máy chủ nhận, sửa của A mất, không có hộp hỏi nào. Cũng thấy khi ba lần lưu xen kẽ (`.scratch/round3_ui/a2.mjs`).
Nguyên nhân: `store.js:68-76` `rebase` đẩy bản chụp TRƯỚC khi ghép vào undoStack, nên hoàn tác ghép đưa cả phần đã lấy từ tab kia về trạng thái cũ, trong khi baseline (`savedSnap`) đã là bản máy chủ.
Hồi quy: mới từ `464bf85`. Check: `R3U-005`.

## Quan sát (không tính lỗi)
- Hai tab Dựng hình: sửa một bên `start.off` (kéo ranh giới) và bên kia sửa ghi chú CÙNG shot cho hộp xung đột, dù hai trường khác nhau. Đúng quy tắc "một đơn vị cả hai đổi", nhưng hơi thô.
- Câu lỗi lặp: một shot có nhiều mốc camera sai thứ tự hiện cùng một câu nhiều lần, không nói mốc nào.
- Duyệt storyboard 82 shot mất ~5 s; Ctrl+S bấm trong lúc chờ được xếp hàng và chạy sau, kết quả đúng (duyệt ghi rev cũ, chip "Duyệt cũ (đã sửa)": trung thực).

- Hộp xung đột (`shots/h_conflict_1280.png`): trong lúc hộp mở, đầu trang vẫn ghi "đang lưu..." và nút Lưu còn dấu chấm; hộp cũng không nói xung đột ở shot nào (cosmetic).
- Lần đầu mở bước Kịch bản sau khi máy chủ khởi động, `/api/models` chạy 1,4 đến 1,9 s và chặn việc tải dàn ý/lời dẫn (chúng chỉ bắt đầu sau khi danh sách về, xem `shots`-less thời gian trong `.scratch/round3_ui/h6.mjs`); các lần sau 1 ms phía máy chủ, 160 ms cả trang. Một lần đo khác ở `h.mjs`/`h3.mjs` ra 8,4 s mỗi lần, nhưng không tái hiện ở `h6.mjs` (máy đang bận do agent kiểm tra phụ trợ), nên không ghi là lỗi.

## Tried and found sound
- A. Hai tab `arnolfini_edit`: khác shot (ghép đúng, JSON máy chủ có cả hai, 82 shot); một tab xóa shot, tab kia sửa shot đó (hộp hỏi, máy chủ 81, nháp 82, không mất gì); một tab thêm shot, tab kia sửa chữ (ghép, 83 shot, id đúng vị trí, không nhân đôi); đổi vùng (`regions.MIRROR.rx`) một bên, sửa shot dùng nó bên kia (ghép); sửa tiêu đề hình một bên, sửa vùng bên kia (ghép sâu, cả hai còn); sáu lần lưu xen kẽ A/B (máy chủ đúng, không hộp thừa); hoàn tác/làm lại trong tab ghép chạy (nhưng xem R3U-005); dấu "chưa lưu" đúng sau ghép (false) và sau hoàn tác (true); duyệt vẫn trung thực (chip "Duyệt cũ (đã sửa)" khi lưu sau khi duyệt).
- B. Cho 71 shot của `technique_lab` đổi 428 ô chọn sang mục cuối: không có chuỗi nhãn tiếng Việt nào lọt vào dữ liệu nháp (đều là giá trị gốc); không có hai giá trị cùng nhãn trong một danh sách enum (54 enum quét tĩnh bằng `labels.mjs`).
- C. Đối chiếu `validateValue` của trang với `POST /validate` của máy chủ trên 3416 cặp (kỹ thuật, tham số, giá trị: mặc định, rỗng, sai mẫu, thừa/thiếu mục, ngoài khoảng) cho mọi tham số kiểu string, text, lines, points, number: trang và máy chủ cùng kết luận (9 chỗ lệch đều do giá trị thử sai dạng của tôi). Câu lỗi tiếng Việt, đúng và nói tên shot; xem quan sát về câu lặp.
- D. Duyệt 82 shot ~5 s: bấm lần hai, sửa ghi chú, Ctrl+S, Esc và đổi bước bằng thanh bước trong lúc chờ: một lần duyệt, không toast sai, không lỗi console; sửa trong lúc chờ được lưu sau, chip nói đúng. Tệp ảnh bị xóa hoặc không đọc được: duyệt bị từ chối ở bước kiểm tra (`asset_file_missing`/`asset_file_unreadable`), câu tiếng Việt, phần còn lại của trang vẫn dùng được (xem R3U-003, R3U-004 cho phần chưa tốt). Ảnh JPEG bị cắt cụt vẫn duyệt được (PIL đọc được).
- E. Dự án hỏng (`project.json` là `[1]`): hàng "Dự án hỏng", ô chọn dự án vô hiệu, liên kết sâu ở mọi bước báo tiếng Việt, Xóa báo "sửa hoặc xóa thư mục bằng tay" và không xóa; dự án khác trên trang chủ bình thường; sửa lại tệp thì dự án mở lại đúng. Ảnh `shots/e_home.png`.
- F. Dàn ý đổi sau khi duyệt lời dẫn: badge "dàn ý đã đổi, cần duyệt lại", ghi chú giải thích; thanh bước ("Kịch bản: Hiện tại") khớp `/pipeline` (`script:current`) ở mọi thời điểm đã kiểm; từ chối vì chương khác nhau liệt kê tiếng Việt (nhưng xem R3U-002).
- G1. Kéo chuột thật: kéo ranh giới shot (bắt đầu đổi từ `w117` sang `w120`), kéo lớp phủ, kéo đầu phát, kéo minimap: mỗi lần hoàn tác/làm lại đưa nháp về đúng, Lưu cho JSON máy chủ bằng nháp, không lỗi console.
- G2. 330 thao tác trong MỘT tab (trang chủ, thư viện, Kịch bản, Dựng hình hai dự án; chọn, sửa, hoàn tác, làm lại, tua, đổi tab, Kiểm tra, resize), đo mỗi 50: Nodes 8472, 10191, 8561, 12846, 9252, 7918; JSEventListeners 518, 549, 512, 903, 594, 376; heap 5 đến 19 MB; trung vị một cú bấm 5 đến 12 ms. Số đo lên xuống theo màn hình đang mở và về thấp ở cuối: không tăng liên tục.
- G3. Ảnh 1280x720 đã xem: hộp xung đột, thông báo ghép, hộp chương không khớp, ghi chú dàn ý đổi, danh sách dự án có hàng hỏng, cờ danh sách mô hình, danh sách lỗi: không tràn, đọc được.
- H. Cờ `agy` giả hiện đúng câu và "Thử lại". Quay lại bước Kịch bản trong ứng dụng: 160 ms (cache phía trang); tải lại: 160 ms khi máy chủ đã có cache.
- I. Console/mạng: chỉ có 409/422/415 mà trang xử lý (xung đột, từ chối duyệt, dự án hỏng, ảnh hỏng); không có ngoại lệ chưa bắt.

## Not tested, and why
- Tìm/lọc theo giá trị (bộ lọc ý đồ ở thư viện kỹ thuật, ô tìm theo nhãn): hết thời gian.
- Thêm/bớt điểm bằng nút của trình soạn điểm tới giới hạn `min_items`/`max_items` bằng chuột: chỉ kiểm tra bằng đối chiếu hàm kiểm tra với máy chủ (mục C).
- Kéo để vẽ khung và chọn điểm trên khung xem (G1 một phần): chưa làm.
- Một ảnh bị xóa hẳn hoặc cắt cụt khiến `/frame` hỏng thật ở một shot nằm giữa danh sách và thumbnail lỗi trên timeline (R2U-P3 phần thumbnail): chỉ tới được khi ảnh hỏng nhưng vẫn qua kiểm tra; không dựng được trường hợp thật.
- Xem thử clip 10 giây trong phiên dài, sửa dàn ý bằng nút trong trang (chỉ dùng API để đổi dàn ý ở F), và nhiều kích thước màn hình ngoài 1280x720 và 1700x1000.
- Sau khi các fix vòng 3 bắt đầu (khoảng 21:20), tôi chỉ đo thêm mục G, H và ảnh hộp xung đột; một thông báo ghép đã đổi chữ ("Hoàn tác không quay lại trước lúc ghép") ở ảnh `h_merge_toast_1280.png`, tức đã có người sửa R3U-005.
