# Bosch — The Garden of Earthly Delights, vBG621XEegk

**Trạng thái:** đã xem 10 sheets bao phủ toàn 50:52 với 610 ảnh mẫu cách 5 giây bằng view_image; chưa xem mọi frame, các khoảng giữa mẫu và ranh giới transition còn bất định. Ảnh và transcript ASR JSON/SRT/TXT ở `research_media/great-art-explained/analysis-b/vBG621XEegk/`; [sheets 01–10](../../../../../research_media/great-art-explained/analysis-b/vBG621XEegk/sheets/). Mốc theo nhãn xấp xỉ (± vài giây); nội dung sound chưa nghe kiểm, quét toàn frame và dense còn chờ.

## Timeline mẫu

| Khoảng | Nội dung | Sheet |
|---|---|---|
| 00:00–05:20 | Montage chi tiết, tranh toàn cảnh, cảnh gallery; đường trắng phân tích bố cục, crop, infrared. | 01 |
| 05:20–10:40 | Địa điểm, bản đồ châu Âu, tranh, công trình, sách và tư liệu; thẻ chương. | 02 |
| 10:40–16:00 | Tranh và đối chiếu; các panel đóng/mở, kinh văn, bản đồ cổ, ảnh chi tiết. | 03 |
| 16:00–21:20 | Cận panel đóng, sách, thiên văn, biểu đồ cổ, panel trái; chữ kinh thánh và ảnh đối chiếu. | 04 |
| 21:20–26:40 | Đọc chi tiết tranh, ảnh động vật/đối chiếu, panel giữa, vòng tròn chỉ dẫn và quote. | 05 |
| 26:40–32:00 | Cận nhân vật, quote, ảnh đối chiếu bản thảo, footage và tranh. | 06 |
| 32:00–37:20 | Chữ trên đen, panel địa ngục, chi tiết, ảnh/footage tư liệu và nhãn chú thích. | 07 |
| 37:20–42:40 | Infrared, cận nhạc cụ và nhân vật, tranh phụ đặt cạnh; chữ overlay. | 08 |
| 42:40–48:00 | Cận tranh địa ngục, tranh khác, quote, tranh trên nền đen, sơ đồ so sánh hình. | 09 |
| 48:00–50:52 | Tranh, footage trưng bày, panel đóng/mở và credit nền đen. | 10 |

## Catalog mẫu

| Canonical / ID | Hành vi, lớp, bằng chứng | Giới hạn |
|---|---|---|
| `ART_CROP_PUSH_PAN` / BOSCH-01 | ~00:02–00:58 montage crop các chi tiết; ~25:42–26:07 crop quả cầu xanh. Sheet 01, 05. | Khung thay đổi giữa mẫu; hướng/tốc độ liên tục chưa kiểm clip. |
| `PERSPECTIVE_LINE_ANNOTATION` / BOSCH-02 | ~02:07–02:12 nhiều đường trắng hội tụ phủ toàn triptych; sheet 01. | Hai lớp hình + đường; không chứng minh 3D, chưa xác định quá trình vẽ. |
| `REGION_HIGHLIGHT` / BOSCH-03 | ~02:17–02:22 vùng trong tranh sáng/màu khác nền; sheet 01. | Quan sát vùng khác màu, chưa khẳng định mask/quy trình. |
| `PANEL_OPEN_REVEAL` / BOSCH-04 | ~12:02–12:22 từ hai cánh ngoài đến toàn tranh trong; sheet 03. | Ảnh rời cho thấy nhiều trạng thái; chưa phân biệt mô phỏng hay footage, cần dense. |
| `CIRCLE_ANNOTATION` / BOSCH-05 | ~15:42 và ~26:27 vòng trắng trên chi tiết tranh, sheets 03/05. | Chưa xác định điểm bắt đầu/kết thúc hoặc motion. |
| `IR_COMPARISON` / BOSCH-06 | ~03:07, ~19:02–19:22, ~37:27–37:37 hình xám hồng ngoại xen ảnh màu; sheets 01/04/08. | Chưa chứng minh registration hay phép trộn. |
| `MAP_STATIC` / BOSCH-07 | ~05:52 bản đồ châu Âu, ~14:47–14:57 bản đồ cổ, sheets 02/03. | Chưa thấy route/path trong mẫu. |
| `QUOTE_OVERLAY`, `SOURCE_LABEL`, `CHAPTER_BLUR_TITLE`, `BLACK_MATTE`, `FOOTAGE_INSERT` | Trích kinh văn phủ hình ~17:37, label nhỏ lặp, title nền mờ ~01:02 và ~05:32, tranh dọc trên đen ~33:22, footage bảo tàng ~50:02. | Không đếm mỗi lần lặp là loại mới; transition và âm thanh chưa kiểm nghe. |

Chưa đủ bằng chứng true 3D, parallax thực, sinh ảnh AI, route/path, color wheel, warp phối cảnh; không coi credit là bằng chứng hiệu ứng. Đây là kết quả mẫu, không kết luận vắng mặt trong toàn video. Cần dense cho BOSCH-02/04 và nghe đối chiếu sound.

**Dense BOSCH-04:** [20 ảnh tại 1 fps, khoảng 12:05–12:25](../../../../../research_media/great-art-explained/analysis-b/vBG621XEegk/dense/panels-725.jpg), đọc trái sang phải, trên xuống dưới. Cánh ngoài xám giữ đóng, khe giữa hiện ảnh màu khoảng 12:17–12:18; hai cánh thu hẹp theo phối cảnh và mở ra hai bên, để lộ tranh trong khoảng 12:18–12:23. Đây là chuyển động có biểu hiện xoay cánh, chưa xác minh nguồn là footage hay mô phỏng hoặc công cụ; mốc theo bước 1 giây và seek, không phải PTS frame chính xác.

**Scan máy:** FFmpeg giải mã toàn stream với `select=gt(scene\,0.35),showinfo`, exit 0; log `scenes.log` tại thư mục analysis-b của ID. Đây là ứng viên theo ngưỡng, không phải số cut hoặc quan sát tay từng frame.
