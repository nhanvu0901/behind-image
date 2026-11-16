# Lỗi giao diện: khung ứng dụng, thư viện, bước Kịch bản

> **Trạng thái sau khi sửa (xem `FIXES_ui_shell_library_script.md`):** U1-002..009 đã sửa và check qua. U1-001: giao diện đã sửa (check U1-013 qua), check gốc còn FAIL vì gọi thẳng API và cần backend đổi `catalogue.norm`. Phát hiện mới U1-010..022 có check trong `run_extra.mjs` (13 pass).

Người kiểm thử: UI tester độc lập (U1). Máy chủ thử: cổng 8564, dữ liệu là bản sao (`.scratch/uitest1/projects`, `.scratch/uitest1/library`). Chỉ dùng mô hình Mock. Chạy lại kiểm tra: `node tests/e2e/shell_library_script/run.mjs` (tự dựng máy chủ trên cổng trống với bản sao dữ liệu tạm; hiện 0 pass / 9 fail, mỗi lỗi U1-001..009 có một check cùng tên).

## Bảng đếm

| Mức | Khung ứng dụng | Thư viện | Kịch bản | Tổng |
|---|---|---|---|---|
| blocker | 0 | 0 | 1 (U1-005) | 1 |
| major | 0 | 0 | 1 (U1-003) | 1 |
| minor | 1 (U1-008) | 1 (U1-001) | 5 (U1-004, 006, 009; U1-002 chạy qua cả ba khu; U1-007 mọi hộp thoại) | 7 |
| Tổng | | | | 9 |

(U1-002 và U1-007 tính vào Kịch bản/khung chung.)

## Đã kiểm tra và thấy đúng
- Mọi địa chỉ trong hướng dẫn mục 2 và các địa chỉ cũ (`/library.html`, `/script.html?project=`, `/?project=`, `?all=1`, `?mock=1`), dự án/bước/địa chỉ lạ: hiện thông báo đúng, không lỗi console ngoài 404 dự kiến.
- Thanh các bước cho dự án mới, đã có dàn ý, đã duyệt dàn ý, đã duyệt lời dẫn, dự án nhập (storyboard); sửa sau khi duyệt làm mất dấu duyệt; Tiếp tục -> Giọng đọc; ba bước chưa xây hiện thông báo trung thực.
- Cảnh báo "chưa lưu": bấm bước, ô chọn dự án, trang chủ, "+ Tạo video mới", nút Quay lại, tải lại trang (beforeunload), Esc/nền hộp = Ở lại; cả ba đáp án (Ở lại, Bỏ, Lưu rồi) cho kết quả đúng.
- Trang chủ: danh sách, Tiếp tục, xóa với gõ mã (chữ hoa/sai mã thì nút tắt, Enter/Esc đúng), dự án gốc bị từ chối 403, dự án bị xóa ở tab khác cho thông báo, không tạo lại thư mục.
- Thư viện: 285/297 tác phẩm, lọc và sắp xếp (đơn lẻ và kết hợp), tìm với ký tự lạ/HTML/emoji, mẫu 43 hồ sơ và 52 mục qua 6 sách (ảnh tải đủ, không tràn ngang, không "undefined"), nhãn dịch máy, tạo dự án (mặc định bỏ sách dịch máy, quy tắc slug, trùng slug), gộp và tách đầy đủ trên bản sao thư viện.
- Kịch bản: Lập dàn ý, sửa, lưu (Ctrl+S), duyệt, Viết lời dẫn, rời trang giữa tác vụ rồi quay lại, Hủy, `[mock:bad]`, `[mock:alwaysbad]`, `[mock:ratelimit]`, `[mock:badoutline]`, dòng khóa và hỏi trước khi viết lại, Tách/Gộp/Bỏ/Chèn/chuyển, hoàn tác/làm lại (mã dòng không bị dùng lại sau hoàn tác rồi lưu), dán tốt/xấu/trống, Sao chép prompt (cả ba thẻ, ghi chú lạ), xung đột hai tab (lưu bị từ chối, duyệt bản cũ bị từ chối), thêm/xóa/đổi chỗ chương, duyệt khi thiếu tên/câu hỏi (bị chặn, hộp Kiểm tra hiện).
- Bố cục ở 1280, 1920 và 125%: không cuộn ngang.

## Chưa kiểm tra và lý do
Do bị yêu cầu dừng, các phần sau CHƯA làm hoặc chưa làm hết:
- Mọi câu "đến dòng" trong hộp Kiểm tra (đã đọc mã: chỉ có cho dòng lời dẫn, không có cho lỗi của dàn ý; chưa thử trong trình duyệt).
- Hai tab sửa dàn ý (chỉ thử lời dẫn); `?mock=1` chỉ xem địa chỉ, không dùng bước Dựng hình (thuộc tester khác).
- Dán dàn ý hợp lệ/xấu, dán lời dẫn "Chỉ thay các chương" (ô merge), dán văn bản khổng lồ (500 KB) và 5.000 ký tự.
- Hộp thoại chọn mô hình thay thế khi hết lượt (chỉ nhìn thấy, không bấm vì các mô hình đó là `agy` thật).
- Ô tick sách dịch máy trong cột Nguồn, ô tìm trong sách, bấm mã dữ kiện sáng đoạn nguồn, thanh ngân sách màu (chỉ đã thấy chúng hiển thị), nhập dự án "arnolfini" ở các bước Tác phẩm/Kịch bản (đã xem nội dung "không có dữ liệu").
- Thư viện: bấm ảnh phóng to (lightbox), "Xem nhanh" ở mục, dự án tạo từ nhiều nguồn/chỉ nguồn dịch máy qua giao diện (chỉ qua API/hộp tạo từ tác phẩm), phím tắt ở đúng/sai màn hình, mọi hộp thoại bằng bàn phím ngoài Tab/Esc/Enter, hai máy tải cùng lúc, 100% so với 125% đối với thư viện (chỉ chụp ảnh, chưa xem hết).
- Không đo thời gian "chậm" vì máy dùng chung.
- Không có check riêng cho các ghi chú nhỏ cuối danh sách.

## Danh sách lỗi

### U1-001 [giao diện đã sửa, chờ backend] (minor, Thư viện) Ô tìm kiếm bỏ qua chữ "đ" và so khớp sai
Cách tái hiện: mở `/#/library`, gõ `đức` (hoặc `Đức`) vào ô tìm. Kết quả: 14 tác phẩm không liên quan (Crucifixion, The Stag Hunt, Benefits Supervisor Sleeping...). Gõ `đ` một mình: hiện cả 285 tác phẩm như chưa lọc. `GET /api/library/artworks?kind=artwork&q=%C4%91` trả về cả 285. Mong đợi: `đ` được đổi thành `d` như các chữ có dấu khác (gõ `Dürer` vẫn tìm được "Adoration of the Magi"), hoặc không khớp gì. Ảnh: `.scratch/uitest1/shots/U1-001.png`. Tái hiện: mọi lần (2/2).

### U1-002 [ĐÃ SỬA] (minor, chữ) Thông báo lỗi của máy chủ hiện nguyên tiếng Anh trong giao diện tiếng Việt
Cách tái hiện (đều 2/2):
- `/#/library/artwork/munch-the-scream`, bấm "Tạo dự án", gõ slug `Bad Slug`, bấm "Tạo dự án": dòng lỗi là `slug must match [a-z0-9][a-z0-9_-]{0,63}`. Slug `lab_x` cho `slug may not start with lab_ or demo_`; slug `arnolfini` cho `project 'arnolfini' already exists`.
- `/#/library/artwork/nope` và `/#/library/work/payne_gae/9999` hiện `Lỗi: artwork not found` và `Lỗi: work not found` (trong khi `/#/library/book/nope` hiện tiếng Việt `Lỗi: Không có sách này`).
- Hộp "Kiểm tra" của bước Kịch bản: `Dữ kiện chưa chương nào dùng. Fact f08 is not used by any chapter.` (nhãn tiếng Việt, lời giải thích tiếng Anh).
- Thông báo xung đột phiên bản khi bấm nhanh (xem U1-003): `the file changed since you loaded it; reload before saving`.
Mong đợi: một hệ thống thông báo tiếng Việt (hướng dẫn mục 2: "Chỉ có một hệ thống thông báo cho cả ứng dụng"). Ảnh: `shots/U1-002.png`.

### U1-003 [ĐÃ SỬA] (major, Kịch bản) Bấm nhanh hai lần nút ↑/↓ của một dòng lời dẫn: lần hai bị từ chối bằng lỗi xung đột giả
Cách tái hiện: mở `/#/project/padded/script` (dự án có lời dẫn), chọn Mock, nhấp đúp (hai lần bấm liên tiếp bằng chuột thật) vào nút ↑ của dòng `b0006`. Kết quả: dòng chỉ lên một vị trí; lần thử thứ hai hiện toast đỏ tiếng Anh `the file changed since you loaded it; reload before saving` và mạng ghi `409 POST /api/projects/padded/narration/ops`. Mong đợi: hai lần bấm = hai bước chuyển, hoặc lần hai bị bỏ qua êm, không có thông báo sai "tệp đã đổi ở nơi khác" (không có ai khác sửa). Nguyên nhân gần: `doOp` gửi `base_rev` cũ khi yêu cầu trước chưa trả về. Ảnh: `shots/U1-003.png`. Tái hiện 2/2 lần có 409, 1/2 lần có hiện toast (toast tồn tại 4 giây).

### U1-004 [ĐÃ SỬA] (minor, Kịch bản) Bộ đếm từ ở trình duyệt bỏ sót các từ chỉ gồm chữ có dấu
Cách tái hiện: ở bước Kịch bản, sửa một dòng lời dẫn thành `Đó là ở đây để ý. Việt Nam ơi!` (9 từ). Số đếm ở dòng ghi `5 từ`. Sau khi lưu, tiêu đề chương `c01` ghi `221 / 200 từ` còn máy chủ (`GET /api/projects/padded/narration`, `stats.chapters[0].words`) ghi 225, và thanh dưới `2121 từ` so với máy chủ 2125. Nguyên nhân: `words()` trong `static/js/views/script.js` dùng `\S*\w\S*` mà `\w` chỉ khớp ASCII, nên `Đó`, `ở`, `để`, `ý.` không được đếm. Tác động thực tế nhỏ nếu lời dẫn là tiếng Anh; sai ngay khi có tiếng Việt. Tái hiện: mọi lần (2/2).

### U1-005 [ĐÃ SỬA] (blocker, Kịch bản) Chữ vừa gõ bị xóa lặng lẽ khi một tác vụ mô hình kết thúc hoặc bị hủy
Cách tái hiện A (hủy): mở `/#/project/padded/script` (dự án đã duyệt dàn ý và có lời dẫn), chọn Mock, "Viết lời dẫn", ghi chú `[mock:slow]`, Chạy. Trong lúc chạy, gõ thêm một chữ vào đầu một dòng lời dẫn (chấm "Lưu" hiện, huy hiệu "đang sửa, chưa lưu"). Bấm "Hủy" ở thanh dưới. Kết quả: toast "Đã hủy. Phần đã viết xong được giữ lại.", chữ vừa gõ biến mất, chấm "chưa lưu" tắt, không có hỏi gì (tác vụ bị hủy không ghi gì lên đĩa, đĩa vẫn là bản cũ). Tái hiện 2/2.
Cách tái hiện B (viết lại một chương): bấm "Viết lại chương" ở chương c03, Chạy, rồi ngay lập tức gõ vào một dòng của chương c05 (không liên quan). Khi tác vụ xong, chữ ở c05 biến mất. Tái hiện 2/2.
Mong đợi: hướng dẫn mục 5 nói chỉnh sửa mất dấu duyệt nhưng không bao giờ nói bản đang sửa bị bỏ; nút Lưu và các thao tác sửa vẫn bật trong lúc chạy. Hoặc khóa ô sửa khi tác vụ chạy, hoặc giữ bản đang sửa và báo xung đột. Nguyên nhân: `jobEnded()` gọi `applyNarr(...)`/`applyOutline(...)` ghi đè `D.*` và đặt `dirty=false` mà không kiểm tra. Ảnh: `shots/U1-005.png`.

### U1-006 [ĐÃ SỬA] (minor, Kịch bản) Nút "Phân tích và lưu" không làm gì khi ô dán trống
Cách tái hiện: bấm "Dán", để trống, bấm "Phân tích và lưu". Không có thông báo, không có viền đỏ, hộp vẫn mở. Mong đợi: một câu như "Chưa có gì để phân tích". Tái hiện 2/2. Ảnh: `shots/U1-006.png`.

### U1-007 [ĐÃ SỬA] (minor, mọi hộp thoại) Hộp thoại không giữ phím Tab bên trong hộp
Cách tái hiện: ở bước Kịch bản có chữ chưa lưu, bấm một bước trên thanh các bước để hiện hộp "Có thay đổi chưa lưu", rồi bấm Tab liên tiếp. Tiêu điểm đi ra ngoài hộp (qua nhãn "Behind the Image", ô chọn dự án, nút "+ Tạo video mới", các bước), tức là bàn phím vẫn thao tác được phần nền bị che. Hộp không có `role="dialog"`/`aria-modal`. Mong đợi: Tab xoay vòng trong hộp. Tái hiện 2/2. Ảnh: `shots/U1-007.png`.

### U1-008 [ĐÃ SỬA] (minor, khung ứng dụng) Ô chọn dự án vẫn liệt kê dự án vừa xóa
Cách tái hiện: ở trang chủ `/#/`, xóa một dự án (gõ mã, "Xóa vĩnh viễn"). Danh sách ở trang chủ cập nhật, nhưng `#project-pick` ở thanh trên cùng vẫn còn tùy chọn của dự án đã xóa cho tới khi chuyển trang. Chọn nó cho `Không có dự án này.` và 404 `GET /api/projects/<id>/pipeline`. Nguyên nhân: `home.js` gọi `shell.refreshProjects()` nhưng khung không vẽ lại ô chọn. Mong đợi: ô chọn cập nhật ngay. Tái hiện 2/2 (hai dự án xóa liên tiếp). Ảnh: `shots/U1-008.png`.

### U1-009 [ĐÃ SỬA] (minor, Kịch bản) Ô "Số từ" của chương nhận số âm, số lẻ và số rất lớn mà không báo
Cách tái hiện: ở cột Dàn ý, ô "Số từ" của một chương, gõ `-5` rồi Tab: giá trị -5 được giữ trong bản nháp (đã thử thêm `12.7` và `99999999999`, đều được giữ). Hộp "Kiểm tra" không báo gì cho -5 (chỉ `0` bị báo "chưa có ngân sách"). Chữ `abc` hoặc rỗng thành 0. Mong đợi: số nguyên dương hợp lý (thuộc tính `min`/`step` hoặc một cảnh báo). Tái hiện 3 giá trị khác nhau trong cùng phiên, và check `U1-009` của bộ e2e (1/1 lần chạy). Ảnh: `shots/s31_approve_err.png`.

### Ghi chú nhỏ (chưa đủ hai lần tái hiện hoặc chỉ là nhận xét, không có check)
- Ở cửa sổ 1280 px rộng, thanh công cụ Kịch bản chật: ô mô hình bị cắt thành `Antigravity CLI: Gemini 4 .` và nút "Tiếp tục" sát mép phải (`shots/v_1280x800z1_script.png`). Chưa có check.
- Hộp "Gộp với…" chỉ liệt kê 40 tác phẩm đầu khi ô tìm trống và không báo còn nữa (`slice(0, 40)` trong `library.js`). Chỉ đọc mã, chưa kiểm tra bằng trình duyệt. Chưa có check.
- Chữ "Huỷ" (hộp thư viện) và "Hủy" (nơi khác) không thống nhất (đọc mã, thấy trên giao diện hộp tạo dự án). Chưa có check.
- Mọi lần bấm "Lưu" hoặc bắt đầu tác vụ đều hiện toast "Đã lưu" kể cả khi không có gì để lưu.
- Cột "Số chữ" của thư viện hiện số chữ thường trong khi "Nhiều chữ nhất trước" sắp theo tổng gồm cả bản dịch máy nên cột trông không đơn điệu.

