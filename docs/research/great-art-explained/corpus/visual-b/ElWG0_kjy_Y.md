# Mona Lisa full length — ElWG0_kjy_Y

**Checkpoint:** MP4 32:53.44; đã dùng view_image xem 7 sheet, 395 ảnh cách 5 giây phủ toàn timeline. [Sheets](../../../../../research_media/great-art-explained/analysis-b/ElWG0_kjy_Y/sheets/); transcript ASR JSON/SRT/TXT trong analysis-b. Mốc xấp xỉ ±5 giây; chưa xem từng frame, chưa nghe đối chiếu audio, quét toàn frame và dense còn chờ.

| Khoảng | Mẫu thị giác | Sheet |
|---|---|---|
| 00:00–05:20 | Cảnh Louvre đông/vắng, logo, chân dung, tư liệu, bản viết và các tranh khác. | 01 |
| 05:20–10:40 | Cận Mona Lisa, đường trên ảnh quét; đo kích thước; footage vẽ và sơ đồ lớp sơn. | 02 |
| 10:40–16:00 | So sánh ảnh scan, cận nét sơn, chân dung khác, footage thao tác và ảnh Prado. | 03 |
| 16:00–21:20 | Những phiên bản Mona Lisa, tam giác bố cục, chân dung khác, lớp tối trên hình. | 04 |
| 21:20–26:40 | Silhouette, mắt/nụ cười, giải phẫu, sơ đồ mắt và so sánh thị giác. | 05 |
| 26:40–32:53 | Tư liệu lịch sử, tranh/ảnh lưu trữ và footage; Mona Lisa và credit cuối. | 06–07 |

| Canonical / ID | Quan sát, bằng chứng | Giới hạn |
|---|---|---|
| `DIMENSION_ANNOTATION` / MONA-01 | ~06:57–07:02 ảnh tranh trong phòng, mũi tên và số chiều ngang/dọc; sheet 02. | Chưa kiểm cách xuất hiện. |
| `PAINT_CROSS_SECTION_DIAGRAM` / MONA-02 | ~08:07–08:52 mặt cắt lớp sơn với nhãn, mũi tên ánh sáng và thước; sheet 02. | Các lớp và đồ họa hiển thị; chưa xác định chuyển động từng thành phần hay phương pháp sản xuất. |
| `REGISTERED_SCAN_COMPARISON` / MONA-03 | ~09:12–09:17 phần ảnh xám và màu kề nhau ở mặt Mona Lisa; sheet 02. | Có so sánh khớp vị trí thị giác; không xác định kỹ thuật registration. |
| `GEOMETRIC_ANNOTATION` / MONA-04 | ~17:17–17:32 tam giác trắng phủ lần lượt hai tranh và Mona Lisa; sheet 04. | Chưa kiểm các frame trung gian. |
| `SILHOUETTE_OVERLAY` / MONA-05 | ~21:27–21:42 silhouette đen và đường ngang chấm trên tranh; sheet 05. | Hình dạng phủ; không khẳng định mask cụ thể. |
| `VISION_DIAGRAM` / MONA-06 | ~25:27–25:47 bảng 3 hình về thị giác và sơ đồ mắt có label; sheet 05. | Không suy ra animation hay độ chính xác y học từ ảnh mẫu. |
| `ART_CROP_PUSH_PAN`, `SOURCE_LABEL`, `FOOTAGE_INSERT`, `BLACK_MATTE`, `CHAPTER_BLUR_TITLE` | Các crop khuôn mặt ~10:22–10:37; footage vẽ ~07:22–07:52; tranh dọc nền đen ~16:00; title ~06:37. | Các loại lặp gom theo tên; cần xác minh chuyển cảnh và âm thanh. |

Mẫu chưa đủ bằng chứng true 3D, parallax, AI generation, map route hay color wheel; không kết luận vắng mặt toàn phim. Cần kiểm dày các hiệu ứng và âm thanh trước khi hoàn thành.

**Dense MONA-02:** [20 ảnh tại 1 fps, khoảng 08:15–08:35](../../../../../research_media/great-art-explained/analysis-b/ElWG0_kjy_Y/dense/layers-495.jpg), đọc trái sang phải, trên xuống. Trên mặt cắt nhiều lớp nằm ngang, các nét vàng dạng tia chữ V hiện và dịch/nhân sang trái khoảng 08:20–08:27; sau đó biến mất, cuối mẫu thấy phần mặt cắt được giản lược thành các nét ngang đen. Đây là đồ họa minh họa thấy được, không suy ra công cụ dựng; các mốc xấp xỉ theo mẫu 1 giây.

**Scan máy:** FFmpeg giải mã toàn stream với `select=gt(scene\,0.35),showinfo`, exit 0; log `scenes.log` tại thư mục analysis-b của ID. Đây là ứng viên theo ngưỡng, không phải số cut hoặc quan sát tay từng frame.
