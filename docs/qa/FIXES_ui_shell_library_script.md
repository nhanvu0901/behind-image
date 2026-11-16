# Sửa lỗi giao diện: khung ứng dụng, thư viện, bước Kịch bản

Người sửa: front-end fixer, 2026-11-16. Chỉ dùng Mock, không gọi mạng. Không commit.
Kiểm tra: `node tests/e2e/shell_library_script/run.mjs` (check của tester, không sửa): **8 pass, 1 fail** (U1-001, xem dưới).
`node tests/e2e/shell_library_script/run_extra.mjs` (check mới U1-010..022): **13 pass, 0 fail**.
`node --test tests/editor_frontend/*.test.mjs`: 100 pass. `pytest tests/script tests/editor tests/library`: 383 pass.

## Bảng

| Id | Mức | Nguyên nhân (một dòng) | Cách sửa (một dòng) | Tệp | Check qua |
|---|---|---|---|---|---|
| U1-001 | minor | Chuẩn hóa tìm kiếm ở máy chủ biến "đ" thành rỗng nên `q=đ` khớp tất cả; giao diện gửi nguyên chữ | Giao diện gửi chuỗi đã bỏ dấu và đổi đ thành d (`text.js`); ô tìm trong sách cũng bỏ dấu | text.js, views/library.js, views/script.js | **không** (check gọi thẳng API, cần backend sửa `catalogue.norm`); check giao diện U1-013 qua |
| U1-002 | minor | Không có một nơi nào biến lỗi thành thông báo | `errmsg.js`: danh mục tiếng Việt cho mọi lỗi máy chủ, mã vấn đề (issue), lỗi tác vụ; lạ thì câu chung + "chi tiết" | errmsg.js, errors.js, util.js, mọi view | có |
| U1-003 | major | Hành động gửi đi trước khi câu trả lời trước cập nhật phiên bản | Một hàng đợi (`queue.js`) cho mọi yêu cầu đổi bản nháp; ↑/↓ xếp hàng dưới dạng ý định, tính lệnh cụ thể khi đến lượt | queue.js, views/script.js | có |
| U1-004 | minor | `\w` chỉ khớp ASCII | `wordCount` theo Unicode, khớp máy chủ (3006 chuỗi so với Python, 0 lệch) | text.js, views/script.js | có |
| U1-005 | blocker | Câu trả lời máy chủ ghi đè bản nháp và xóa dấu "chưa lưu" | `reconcile()`: ghép ba bên (bản cũ, bản đang sửa, câu trả lời) theo chương/dòng/dữ kiện; trùng chỗ thì hỏi; lưu bị giữ khi tác vụ đang ghi | merge.js, views/script.js | có |
| U1-006 | minor | Bấm "Phân tích" khi trống thì thoát im lặng | Thông báo trong hộp, viền đỏ, trả tiêu điểm về ô | views/script.js, theme.css | có |
| U1-007 | minor | `modal()` không giữ Tab | `modal()` dùng chung: role=dialog, nền `inert`, Tab xoay vòng, Esc hộp trên cùng, Enter bấm nút chính, trả tiêu điểm | util.js | có |
| U1-008 | minor | `refreshProjects()` không vẽ lại ô chọn | Vẽ lại ô ngay; bỏ dự án vừa xóa khỏi danh sách; làm mới khi quay lại tab | app.js, views/home.js | có |
| U1-009 | minor | Ô số nhận mọi giá trị | `intField`: số nguyên trong khoảng, sai thì báo và trả giá trị cũ | views/script.js | có |

## Anh em của lỗi (đã tìm và sửa)

- **U1-005**: lưu/duyệt/dán/thao tác cấu trúc/tải lại sau xung đột đều đi qua `reconcile()`. Nếu gõ trong lúc yêu cầu lưu đang bay, chữ đó cũng được giữ. Phần đang sửa không lưu được khi tác vụ đang ghi cùng tệp (backend ghi theo bản nạp lúc bắt đầu và sẽ đè); chờ ghép khi xong. Hộp dán với "Chỉ thay các chương" lưu bản nháp trước để các chương khác giữ chữ chưa lưu. Khi gặp 409 lúc lưu: ghép với bản máy chủ và lưu lại (trước: "tải lại trang", mất chữ).
- **U1-003**: `saveAll`, thao tác cấu trúc, duyệt, dán, tùy chọn nguồn, bắt đầu tác vụ đều qua một hàng đợi. Còn: theo dõi tác vụ có thể chạy chồng hai lần `jobEnded` (đã chặn); sao chép prompt trả lời cũ ghi đè mới (đã gắn số thứ tự); tìm trong thư viện trả lời lẻ thứ tự (đã gắn số thứ tự).
- **U1-004/001**: `Tách` đếm theo "token" (như `str.split` của máy chủ), không theo "từ": trước đây sau một dấu gạch lẻ thì cắt sai chỗ (U1-020). Tách tên bằng `[,;\s]` thêm dấu phẩy toàn rộng. Không còn regex/so sánh chữ nào trong các view dùng `\w` hay `toLowerCase` để so tiếng Việt.
- **U1-002**: cả `ApiError.message` giờ là tiếng Việt, nên mọi nơi (kể cả view dựng hình) hiện tiếng Việt; `e.detail` giữ chữ gốc; nhãn mã vấn đề, lỗi tác vụ, lý do dán hỏng, lỗi dữ liệu (`data_error`), xóa bị từ chối đều có câu tiếng Việt.
- **U1-007**: Esc/Enter nhất quán cho mọi hộp; hộp chứa chữ dán không đóng khi bấm nền; phím tắt của view không chạy khi có hộp; lightbox thành hộp thật (Esc, Tab, trả tiêu điểm, không rò listener).

## Phát hiện mới (U1-010 trở đi, đều có check trong `run_extra.mjs`)

| Id | Mức | Mô tả | Sửa |
|---|---|---|---|
| U1-010 | major | Dán/mở lời dẫn 500 KB (825 dòng): trang đứng ~30 giây (`fit()` ép tính bố cục từng ô) | Đo chiều cao một lượt (hoặc CSS `field-sizing`); chỉ mục lỗi theo dòng. Vẽ lại 166 ms |
| U1-011 | major | Hai tab sửa cùng dàn ý: tab sau bị 409 và bảo "tải lại trang", mất chữ đã gõ | Ghép và lưu lại; trùng chỗ thì hỏi (hộp "Hai bản sửa khác nhau") |
| U1-012 | major | 125% zoom (1024 px): cột lưới của khung bị thanh bước Kịch bản kéo rộng, nút Duyệt, Tiếp tục, huy hiệu health bị cắt (tester báo không có, đo `#view` chứ không đo khung) | `#shell` cột `minmax(0,1fr)`, thanh công cụ tự xuống dòng, bề rộng tối thiểu 920 |
| U1-013 | minor | Ô tìm thư viện: placeholder bị cắt, kết quả khác nhau theo dấu | Rộng hơn, ngắn gọn, bỏ dấu khi gửi |
| U1-014 | minor | "Đến dòng" chỉ có cho dòng lời dẫn, hộp Kiểm tra không dẫn tới lỗi của dàn ý | Đến thẻ chương, dữ kiện, câu hỏi chính, câu mở, mục tiêu, tiêu đề chương; làm sáng chỗ đó |
| U1-015 | minor | Hộp "mô hình khác" liệt kê 18 nút `agy`: một cú bấm nhầm là gọi mô hình thật | Một ô chọn + một nút "Chạy tiếp với mô hình này" (tắt cho đến khi chọn) |
| U1-016 | minor | Dự án chỉ có sách dịch máy (chưa tick) vẫn cho chạy mô hình trên 0 nguồn | Cảnh báo ở cột Nguồn, chặn chạy kèm lời giải thích |
| U1-017 | minor | Lightbox không phải hộp thoại, mỗi lần mở thêm một listener, lỗi "Xem nhanh" không bắt | Viết lại; bắt lỗi |
| U1-018 | minor | Ô chọn mức chắc chắn của dữ kiện bị cắt ("chắc c") | Rộng cố định 150 px |
| U1-019 | minor | Enter trong ô tên thư mục không làm gì | Enter trong ô chữ của hộp bấm nút chính |
| U1-020 | minor | Nút Tách cắt sai chỗ sau dấu gạch lẻ (đếm "từ" khác "token" của máy chủ) | Đếm token |
| U1-021 | minor | "Lưu" luôn báo "Đã lưu" (ghi chú nhỏ của tester) | "Không có gì cần lưu" |
| U1-022 | minor | Bấm nền hộp "Dán" làm mất chữ dán, kể cả 500 KB | Không đóng khi bấm nền; chữ giữ khi đóng |

Ghi chú nhỏ của tester: 1280 px chật (thanh tự xuống dòng, ô mô hình rút gọn có dấu ...); "Gộp với…" nay ghi "Đang hiện 40 trong N"; "Huỷ" thành "Hủy"; "Đã lưu" khi không có gì (U1-021); nhãn sắp xếp "Nhiều chữ nhất (cả dịch máy)" và chú thích cột. Cả bốn có sửa nhưng chỉ U1-021 có check riêng.

Đã thử bằng Chrome thật, không thấy lỗi: dán dàn ý tốt và xấu (hộp báo lý do bằng tiếng Việt và danh sách đoạn), "Chỉ thay các chương", trường 5.000 ký tự (lưu và đếm đúng), ô tick sách dịch máy, tạo dự án từ nhiều nguồn và từ chỉ sách dịch máy qua trang, phím tắt không chạy ở màn hình khác hay sau hộp thoại, bố cục 1280 và 1920 (sau sửa, 125% cũng vừa). Ảnh trong `.scratch/fix_shell/shots/` (đã xem: `L_*`, `U1-011_conflict`, `alt_model_dialog2`, `goto_outline`...).

## Thay đổi ở module dùng chung (storyboard dùng)

Mọi export cũ vẫn còn.
- `errors.js`: `ApiError.message` giờ là tiếng Việt (trước: `detail` thô); thêm `.detail` (chữ gốc). `status`, `body`, `url` không đổi.
- `util.js`: thêm `errorToast`, `errorInto`, `detailFold`, `focusablesIn`, `modalOpen`; `toast(msg, kind, ms, detail?)` có tham số thứ tư; `modal()` có thêm tùy chọn `backdrop`, `enter` và hành vi mới (role, inert, Tab, Enter); Esc vẫn như cũ. Cả `ask`, `confirmDialog` đi theo.
- Mới: `text.js`, `queue.js`, `merge.js`, `errmsg.js`. `labels.js`, `lifecycle.js`, `api.js` không đổi.
- CSS: `shell.css` (cột lưới, nowrap), `theme.css` (chi tiết lỗi, ô không hợp lệ). Đã nói với bên view dựng hình: không sửa tệp của họ.

## Phụ thuộc backend

- **U1-001**: `bti/library/catalogue.norm` cần đổi đ/Đ thành d trước khi bỏ dấu (hiện chuỗi chỉ gồm "đ" thành rỗng và khớp mọi thứ). Giao diện đã gửi chuỗi đã bỏ dấu nên không bị ảnh hưởng, nhưng check của tester gọi thẳng API.
- Mọi yêu cầu `generate` luôn kèm `model` (trang từ chối khi chưa chọn hoặc mô hình chưa dùng được).
- Đã nối: 409 `locked` khi dán (hộp hỏi, rồi gửi `force`), trạng thái duyệt lời dẫn đọc lại sau khi dàn ý lưu/duyệt/dán, `error_kind: interrupted`, chương `failed`/`skipped`, `data_error`, xóa bị từ chối khi tác vụ chạy. Phần còn nên làm ở backend: `run_narration` giữ bản nạp lúc bắt đầu và ghi đè lên bản lưu giữa chừng; giao diện đã né bằng cách không lưu phần đó khi tác vụ chạy.

## Chưa sửa

- U1-001 ở phía API (xem trên).
- Chưa có check tự động riêng cho: trả lời lưu về sau khi gõ tiếp (đã có test đơn vị của phép ghép), chữ "Huỷ/Hủy", danh sách "Gộp với…".
- Phím tắt của view dựng hình thuộc fixer khác, chưa kiểm tra.
- Hộp thoại thử mô hình thay thế chỉ thử bằng `[mock:ratelimit]`; không bấm mô hình `agy` nào.
- Hai tệp `projects/arnolfini/project.json` và `projects/technique_lab/project.json` (chưa theo dõi bởi git) do backend fixer tạo (cờ protected), không phải tôi.

## Cập nhật sau khi backend sửa xong (jobs, đ)

- U1-001: backend dùng `bti/textfold.fold`; `text.js` nay có cùng bảng và NFKD (2005 chuỗi so với Python, 0 lệch). `run.mjs`: 9 pass.
- Quyết định về việc giữ lưu: **chỉ giữ cho tác vụ dàn ý**. Tác vụ lời dẫn nay ghi từng chương dưới cùng khóa với lưu và giữ phần đã lưu, nên lưu, khóa dòng, tách/gộp trong lúc chạy đều được; nếu tác vụ ghi xen giữa thì 409 và trang tự ghép rồi lưu lại. Lưu dàn ý trong lúc tác vụ dàn ý chạy sẽ làm tác vụ kết thúc `conflict` và đẩy dàn ý của mô hình vào ô Dán, nên trang giữ chữ trên máy đến khi tác vụ xong. Cả hai cách đều không thể mất chữ gõ.
- Một kết quả duy nhất: máy chủ ghi theo khóa, trang đọc lại tài liệu khi tác vụ kết thúc (lấy `rev` mới từ chính bản đọc lại, cùng giá trị với `result.rev`) rồi ghép; không hai phép ghép chồng nhau vì sau mỗi lần ghép bản cơ sở của trang là bản máy chủ.
- Dòng bị bỏ qua vì khóa (`result.skipped`) hiện trong thông báo; `error_kind: conflict` của dàn ý có hộp giải thích tiếng Việt kèm nút "Mở ô Dán".
- Check mới: U1-023 (lưu chương khác khi tác vụ chạy), U1-024 (khóa dòng khi tác vụ chạy), U1-025 (lưu dàn ý khi tác vụ dàn ý chạy, Mock `[mock:slow]`).
