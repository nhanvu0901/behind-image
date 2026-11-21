# Vòng 2: kiểm tra giao diện trình duyệt (R2U)

Người kiểm tra: agent độc lập, Chrome thật (headless), máy chủ và dữ liệu tạm tạo bởi `tests/e2e/shell_library_script/lib.mjs`, chỉ dùng mô hình `mock`.
Kiểm tra tự động: `node tests/e2e/round2/run.mjs` (mỗi lỗi một check khẳng định hành vi ĐÚNG, nên FAIL khi lỗi còn; thoát với số check FAIL).
Mức: blocker, major, minor, cosmetic. "Xác nhận" = tái hiện ít nhất hai lần; "thấy một lần" = chỉ một lần.

## Lỗi

### R2U-001 (major, storyboard, xác nhận: 2 lần) Mất kết nối máy chủ: bước Dựng hình hiện "Failed to fetch" bằng tiếng Anh
Các bước: mở `#/project/arnolfini_edit/edit`, sửa một ghi chú của shot (nháp chưa lưu), tắt máy chủ, bấm **Lưu**; thử thêm **Xem thử 10 giây**, **Đề xuất**, và bấm vào timeline (khung hình).
Mong đợi: câu tiếng Việt "Không kết nối được máy chủ..." (như bước Kịch bản), nháp còn nguyên.
Thực tế: thông báo "Lưu thất bại: Failed to fetch", "Không dựng được clip: Failed to fetch", hộp Đề xuất "Không tải được danh sách đề xuất: Failed to fetch", ô khung hình "Lỗi dựng khung: Failed to fetch". Nháp được giữ (đúng) và lưu lại được sau khi máy chủ chạy lại (đúng).
Nguyên nhân: `bti/editor/static/js/views/storyboard.js` (saveOnce, previewClip, loadProject) và `proposals.js`, `preview.js` dùng `e.message` / `e.status || e.message` chứ không qua `describeError` (`errmsg.js:155` đã có nhánh TypeError). Chỉ bước Kịch bản và khung ứng dụng dùng `errorToast`.
Check: `R2U-001`.

### R2U-002 (major, storyboard, xác nhận: 2 lần) Danh sách lỗi của storyboard hiện thông báo kiểm tra tiếng Anh nguyên văn
Các bước: mở `#/project/arnolfini_edit/edit` (dự án sao để sửa của chủ), bấm tab **Lỗi**.
Mong đợi: câu tiếng Việt như ở bước Kịch bản (`issueText`).
Thực tế: "project 'arnolfini' differs from the folder name 'arnolfini_edit'" (cảnh báo luôn có ngay khi mở dự án này) và, khi sửa tham số, "at: must be a region name or [x, y]" và các câu tương tự. Cũng hiện trong hộp tooltip/đếm của nút Kiểm tra. Ảnh: `.scratch/round2_ui/shots/c2_issues.png`.
Nguyên nhân: `inspector.js`/`checks.js`/`storyboard.js` vẽ `issue.message` thẳng; không dùng `issueText` của `errmsg.js` (U1-002 chỉ sửa bước Kịch bản và khung).
Check: `R2U-002`.

### R2U-003 (minor, storyboard, xác nhận: 2 lần) Hộp "Xung đột phiên bản (409)": số lỗi thô, hứa "xuất ra xem" (không có tính năng xuất), và bản nháp không bao giờ lưu được
Các bước: mở cùng dự án ở hai tab; tab A sửa ghi chú shot s0005 và Lưu; tab B sửa shot s0007 và Lưu.
Mong đợi: tiêu đề không có "(409)"; lời nhắc đúng; có cách giữ cả hai bản sửa (như bước Kịch bản đã ghép, U1-011), hoặc ít nhất cách lưu đè có hỏi.
Thực tế: tiêu đề "Xung đột phiên bản (409)"; câu "giữ bản nháp, xuất ra xem rồi tải lại sau" (không có nút xuất nào); chỉ có "Giữ bản nháp" hoặc "Tải lại từ server" (mất sửa đổi của B). Sau "Giữ bản nháp" mọi lần Lưu lại đều ra đúng hộp này: nháp của B không thể lưu nếu không tải lại. Không mất chữ âm thầm (chủ được báo), nên chỉ là minor.
Nguyên nhân: `views/storyboard.js` (khối `e.status === 409` trong `saveOnce`).
Check: `R2U-003`.

### R2U-004 (minor, storyboard, xác nhận: 2 lần) Danh sách "Ý đồ" và vài giá trị hiện mã tiếng Anh thô
Các bước: mở `arnolfini_edit` bước Dựng hình, tab Shot, mở ô "Ý đồ (intent)".
Mong đợi: chữ tiếng Việt dễ hiểu. Thực tế: `establish, explore, point_at, isolate, reveal, compare, explain_mechanism, quote...`; tương tự giá trị `ease` (`in_quad`, `inout_cubic`), nguồn "import", nhãn "clean" ở thư viện. (Mã kỹ thuật như CAM-03 được phép.) Ảnh: `.scratch/round2_ui/shots/c0_edit.png`.
Check: `R2U-004` (chỉ kiểm tra danh sách ý đồ).

### Quan sát nhỏ (thấy một lần, chưa có check)
- Trang chủ: các cột của từng dự án không thẳng hàng giữa các hàng (cosmetic, `shots/a1_home.png`).
- Mở dự án không có âm thanh (technique_lab) tạo hai yêu cầu 404 (`/waveform`, `/audio`) trong console; trang xử lý và thông báo, nên không tính lỗi.
- Phím Backspace (ngoài ô gõ) cũng xóa shot, không có trong hướng dẫn (chưa kiểm tra kỹ).
- Sau khi tắt rồi bật lại máy chủ, huy hiệu engine/media chỉ cập nhật mỗi 30 giây.
- Lưu ý chung: ô mô hình mặc định là Antigravity (mô hình thật); các hộp "Lập dàn ý"/"Viết lời dẫn" chạy ngay mô hình đang chọn. Khi tôi thử khi máy chủ tắt tôi đã không bấm Chạy với mô hình thật nào còn hoạt động.
- Trang liệt kê mô hình gọi `agy models` trên máy chủ mỗi lần mở bước Kịch bản (chỉ liệt kê, không gọi mô hình).

## Đã thử và thấy ổn (Tried and found sound)
- A. Một phiên liền: trang chủ, thư viện, tìm có/không dấu (Dürer/durer, Đức/duc, Vermeer), hồ sơ tác phẩm, tạo dự án, bước Kịch bản: lập dàn ý (mock), sửa, duyệt (kể cả bấm Duyệt khi còn chưa lưu: tự lưu rồi duyệt), viết lời dẫn (mock), gõ, Tách, Gộp, khóa, chuyển, Bỏ, Hoàn tác, Lưu, duyệt lời dẫn. Thanh bước, thẻ giai đoạn và `GET /pipeline` luôn khớp (kể cả sau khi sửa lời dẫn đã duyệt: lùi về "Hiện tại"; sửa dàn ý sau khi duyệt lời dẫn: máy chủ lùi về "selected/Kịch bản hiện tại"). Bước khóa cho lý do bằng tiếng Việt. Liên kết sâu: dự án không có, bước không có, mã viết hoa, đường dẫn lạ, tác phẩm/sách/mục không có: đều có thông báo tiếng Việt.
- B. Rời khi chưa lưu: bước Kịch bản và Dựng hình, qua thanh bước, logo, nút Tạo video mới, sửa hash tay, ô chọn dự án, Back: hộp hỏi đúng một lần, tiếng Việt, "Ở lại" giữ nguyên chữ và địa chỉ, "Bỏ" cho màn hình sạch; Ctrl+S/Ctrl+Z/Space/Delete ở màn hình kế tiếp không ghi gì của màn cũ. Đóng tab/tải lại (beforeunload) dùng hộp của trình duyệt (không đo được qua giao thức).
- C. Storyboard `arnolfini_edit`: 15 thao tác (chọn, cắt, đổi kỹ thuật, thêm lớp phủ, tham số, khóa, ghi chú, gộp, xóa shot, vùng thêm/đổi tên/xóa, chuyển cảnh, xóa lớp phủ): hoàn tác hết rồi làm lại hết, nháp bằng đúng bản lưu ở mỗi bước; 13 shot của `technique_lab` bị nhập chữ rác vào mọi ô số/chữ: không có NaN trong tham số lưu (đã thử từng giá trị rác riêng).
- D. Hai tab bước Kịch bản: sửa khác chỗ thì ghép, một bên xóa một bên sửa thì hỏi, đổi thứ tự khi bên kia sửa thì ghép đúng. (Hai tab Dựng hình: xem R2U-003.)
- E. Tắt máy chủ giữa chừng: bước Kịch bản báo tiếng Việt, giữ chữ, hồi phục sau khi bật lại; bước Dựng hình giữ nháp và lưu lại được sau khi bật lại (nhưng lời báo xem R2U-001).
- F. Tiêu điểm trở về nút mở hộp sau Esc (Kiểm tra, Sao chép, Dán, Lập dàn ý, Đề xuất).
- G. 1280x720, 1440x900, 1700x1000, 1920x1080 ở 125%: không tràn ngang, không nút ngoài tầm với (đo hộp bao và xem ảnh `shots/g_*`). 1280x720 chật nhưng dùng được.
- H. Chưa đủ 300 thao tác trong MỘT tab: chạy 7 vòng (31 thao tác mỗi vòng, qua Kịch bản, Dựng hình, trang chủ, thư viện) trong tab sạch, tổng khoảng 220 thao tác chia ba lần; số nút DOM và listener quay về cùng mức mỗi lần vào lại bước Kịch bản (không tăng), độ trễ một cú bấm 6 đến 28 ms. Không có console.error hay yêu cầu 4xx/5xx ngoài những cái xử lý được (409 có hộp, 404 âm thanh).
- I. Console và mạng: không có ngoại lệ chưa bắt trong lúc dùng bình thường; chỉ có lỗi SVG "NaN" khi cố tình nhập chữ rác vào ô camera (xem ghi chú ngoài danh sách).
- J. Quét chữ tiếng Anh trên mọi màn hình và hộp thoại: ngoài R2U-002 và R2U-004 chỉ còn dữ liệu sách/tên tranh.
- Chưa làm: xem thử clip 10 giây trong phiên dài (chỉ có trong vòng lặp ở vòng 4, không lỗi), kéo thả chuột trên timeline và trên khung xem (round 1 đã có check), thư viện kỹ thuật cho cả 71 kỹ thuật (đã có `techniques71.mjs`), và đóng tab thật để thấy hộp beforeunload.
- Ghi chú: sau 18:5x máy chủ phụ trợ có thể đang được sửa; máy chủ tôi dùng cho thăm dò chạy mã cũ, các check trong `run.mjs` tự khởi động máy chủ mới.
