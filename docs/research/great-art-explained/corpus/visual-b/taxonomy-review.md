# Đối chiếu độc lập EFFECTS_CATALOG với visual B

Bản kiểm trên `EFFECTS_CATALOG.md` đọc lúc 2026-11-13 10:29:22; corpus đang viết lại nên cần kiểm lại phiên bản sau. So sánh catalog B và report longform, không xem lại mọi bằng chứng gốc. Mẫu thưa 5 giây không chứng minh animation; mốc chỉ xấp xỉ trừ khi nói khác.

## Bằng chứng B chưa được đưa vào hoặc có thể bổ sung

| Bằng chứng | Đề xuất merge | Giới hạn |
|---|---|---|
| [MONA-06](ElWG0_kjy_Y.md) ~25:27–25:47 | Sơ đồ thị giác / mắt ba hình và nhãn: bổ sung ví dụ diagram, riêng về nội dung thị giác nếu catalog muốn phân loại theo nội dung. | Trạng thái tĩnh trong mẫu; không suy animation hoặc độ đúng y học. |
| [MENINAS-05](YFI6cQF1ros.md) ~15:52–16:12 | Footage bảng màu, tên pigment và chi tiết tranh: bổ sung palette + nhãn dưới footage/vật liệu. | Không phải bánh xe màu; không tự tạo primitive mới nếu đã gộp footage + label. |
| [HOPPER-CINEMA-01](mQVC0qJGJ_c.md) ~00:42–01:02, ~06:02–06:22 | Bổ sung ví dụ so sánh ảnh phim với tranh đặt cạnh nhau vào LAY-01, không cần tạo primitive trùng. | Các cặp là trạng thái; chưa kiểm nhịp từng cut. |
| [NIGHTHAWKS-01](lKIbT-4UFaE.md) ~00:00–00:20 | Bằng chứng B 1 fps pull-out, có thể dẫn thêm CAM-03; [KISS-04](SNhmSdLDmto.md) ~05:20–05:31 bổ sung zoom + dịch ngang cho CAM-05. | KISS kết hợp zoom và dịch; không xác nhận pan thuần. |
| [ARNOLFINI-04](T15Kv6dtYO0.md) ~04:39–04:41 | Thêm ví dụ đổi crop đột ngột vào TR-04. | 1 fps không loại trừ transition ngắn dưới 1 giây; không nói frame-exact hard cut. |
| [HOPPER-CINEMA-02](mQVC0qJGJ_c.md) ~07:40–07:45 | Thêm ví dụ footage cửa hàng hòa/chồng sang Nighthawks vào TR-01. | Bằng chứng 1 fps; biên ±1 giây. |

Các record CAM-02, DIA-04/05, AN-06, CMP-03 và ví dụ tuyến tĩnh đã được merge; không đếm lại như kỹ thuật mới. `ILLUSTRATED_SEQUENCE` CARR-02 chỉ là chuỗi hình mẫu, chưa đủ chứng minh motion.

## Mâu thuẫn hoặc phát biểu cần chỉnh

1. Dòng sau bảng kỹ thuật nói **pull-out và pan theo từng hướng chờ kiểm dày**, nhưng CAM-03 đã có pull-back và CAM-04 đã có pan dọc lên; CAM-05 có zoom + dịch. Viết lại theo từng phần còn thiếu, không nói cả họ chưa kiểm.
2. Phần ngữ cảnh nói **Shorts còn chờ tổng hợp**, nhưng ngay sau đó có mục Shorts 13/13 và ba chuỗi dày. Cập nhật cho nhất quán với coverage Shorts.
3. Lời mở đầu “đang xây dựng” có thể lỗi thời ở bản bàn giao; xác nhận với tác giả final trước khi đổi.
4. Không thấy khẳng định 3D, AI hoặc software vượt bằng chứng ở các mục B đã so. `CAM-02` nói motion tương đối và nêu không chứng minh 3D là phù hợp. `DIA-04` và `DIA-05` chỉ gọi trạng thái, phù hợp.
5. Report B gốc của Bosch/Mona ở checkpoint đầu có câu scan/dense “còn chờ” trong khi phần bổ sung cuối đã ghi scan/dense hoàn tất; khi trích nên dùng thông tin cập nhật ở cuối, không lấy câu cũ làm trạng thái mới.

## Review lại bản rewrite 2026-11-13 10:32:11

Hai mâu thuẫn trạng thái pull-out/pan và Shorts đã được sửa. Các đề xuất MONA-06, MENINAS-05, so sánh phim–tranh và ví dụ dense B đã được đưa vào hợp lý, không thấy suy đoán 3D/AI/software ở các record B.

**Hồi quy cần sửa trước merge:** các dòng `CAM-01`, `TR-01`–`TR-03`, `HI-01`/`HI-02`, `AN-01`, `TXT-02`, `DIA-01`–`DIA-03` bị rút thành ID + liên kết clip, cột giới hạn lặp lại nhãn clip; thiếu tên kỹ thuật bằng tiếng Việt, mô tả hành vi và lớp/asset, bằng chứng report, giới hạn/tin cậy. Điều này làm mất nội dung bản trước, đặc biệt B: `TR-03` mở cánh Bosch chưa biết footage/mô phỏng; `HI-02` nhân vật hiện nhóm trên nền phòng chưa chứng minh tách lớp; `DIA-03` tia vàng trên mặt cắt sơn có motion. Khôi phục mô tả cũ ở bảng, giữ clip như bằng chứng bổ sung và không tăng số record.

## Kiểm hồi quy sau sửa

Đã kiểm lại 11 record được nêu: `CAM-01`, `TR-01`–`TR-03`, `HI-01`/`HI-02`, `AN-01`, `TXT-02`, `DIA-01`–`DIA-03` đều đã khôi phục tên, hành vi, asset, report, clip và giới hạn. Ba record B giữ đúng giới hạn: BOSCH-04 chưa xác định footage/mô phỏng, SUPPER-03 không chứng minh cách tách lớp, MONA-02 chỉ khẳng định motion tia. Không còn hồi quy này; kết quả review giới hạn ở các record đối chiếu và mâu thuẫn đã nêu, không phải xác minh độc lập toàn bộ catalog A/Shorts.
