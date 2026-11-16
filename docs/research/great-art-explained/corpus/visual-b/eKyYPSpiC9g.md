# Last Supper — eKyYPSpiC9g

**Checkpoint:** 36:11.16 MP4; đã dùng view_image xem 7 sheet, 434 ảnh mẫu cách 5 giây từ đầu đến cuối. [Sheets](../../../../../research_media/great-art-explained/analysis-b/eKyYPSpiC9g/sheets/); transcript ASR JSON/SRT/TXT cùng thư mục analysis-b. Các mốc dưới xấp xỉ ±5 giây, không phải ranh giới chính xác; full-frame scan, dense và nghe audio còn chờ. Metadata local xác nhận khoảng 36 phút, không dùng snippet 21:04.

| Khoảng | Mẫu thị giác | Sheet |
|---|---|---|
| 00:00–05:20 | Kênh/subscribe, montage tranh, Last Supper, so sánh, bản vẽ Leonardo, tranh và thẻ chương. | 01 |
| 05:20–10:40 | Sân khấu/thiết kế, sách, nhà thờ; mặt bằng, sơ đồ phòng và đường viền; các tác phẩm so sánh. | 02 |
| 10:40–16:00 | Footage kỹ thuật/ghép, tranh, mặt bằng, đường phối cảnh, cận bề mặt và sơ đồ không gian. | 03 |
| 16:00–21:20 | Mặt bằng/phòng, footage và sách, nhiều Last Supper; tranh được dựng hình từng nhóm và đường chỉ dẫn. | 04 |
| 21:20–26:40 | Chi tiết, tên nhân vật, hình so sánh, đường viền, trích dẫn và lưới footage. | 05 |
| 26:40–32:00 | So sánh tác phẩm, quote, nhân vật xuất hiện dần trong không gian, tam giác, cảnh nhà thờ và montage. | 06 |
| 32:00–36:11 | Nhân vật và nhãn, lưới so sánh, tư liệu phục chế, tác phẩm và credit. | 07 |

| Canonical / ID | Quan sát, bằng chứng | Giới hạn |
|---|---|---|
| `PERSPECTIVE_LINE_ANNOTATION` / SUPPER-01 | ~14:32, 15:47–15:52: nhiều đường hội tụ trên tranh/phòng, sheet 03. | Đường phủ hình; chưa kiểm cách xuất hiện. |
| `SPACE_DIAGRAM` / SUPPER-02 | ~08:22–08:47 mặt bằng rồi phòng với đường bàn/nhân vật dạng viền; sheet 02. | Mô hình không gian quan sát được; chưa chứng minh digital 3D. |
| `PROGRESSIVE_FIGURE_REVEAL` / SUPPER-03 | ~19:52–20:07 và 29:27–29:47: phòng/tranh ít nhân vật rồi thêm nhóm; sheets 04/06. | Các mẫu rời không xác định opacity/mask; cần dense. |
| `FIGURE_OUTLINE` / SUPPER-04 | ~09:47–09:57 và 23:52–24:02 viền người/nhóm trên tranh; sheets 02/05. | Chưa xác nhận timing và thứ tự lớp. |
| `GEOMETRIC_ANNOTATION` / SUPPER-05 | ~30:17–30:27 tam giác trắng trên nhân vật chính, sheet 06. | Chưa kiểm motion. |
| `GRID_COMPARE`, `FOOTAGE_INSERT`, `CHAPTER_BLUR_TITLE`, `SOURCE_LABEL`, `QUOTE_OVERLAY`, `BLACK_MATTE`, `ART_CROP_PUSH_PAN` | Ví dụ lưới ~20:12 và 33:32, title ~14:07, quote ~24:12, cận nhóm ~21:27; sheets 03–07. | Loại lặp được nhóm, không đếm mỗi lần thành hiệu ứng riêng. Audio chưa nghe kiểm. |

Nguồn [creator](https://www.youtube.com/watch?v=eKyYPSpiC9g) credit Brian Adsit cho opening animation và title sequence; đó là thông tin công bố, không gán mọi hiệu ứng cho người này. Mẫu chưa đủ chứng minh true 3D, parallax hay AI generation, map route, color wheel hoặc anamorphic warp; không khẳng định vắng mặt toàn phim.

**Dense SUPPER-03:** [20 ảnh tại 1 fps, khoảng 19:50–20:10](../../../../../research_media/great-art-explained/analysis-b/eKyYPSpiC9g/dense/reveal-1190.jpg), đọc trái sang phải, trên xuống. Nền phòng và bàn giữ nguyên, nhân vật trung tâm hiện mờ rồi rõ khoảng 19:55–19:57; các nhóm bên lần lượt hiện mờ tới đủ tranh khoảng 20:00–20:05. Quan sát phù hợp thay đổi độ mờ của các lớp hình, không chứng minh kỹ thuật mask hay phần mềm; mốc gần đúng theo bước mẫu 1 giây.

**Scan máy:** FFmpeg giải mã toàn stream với `select=gt(scene\,0.35),showinfo`, exit 0; log `scenes.log` tại thư mục analysis-b của ID. Đây là ứng viên theo ngưỡng, không phải số cut hoặc quan sát tay từng frame.
