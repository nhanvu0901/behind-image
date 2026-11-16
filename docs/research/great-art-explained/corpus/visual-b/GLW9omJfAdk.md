# Dark Goya — GLW9omJfAdk

**Trạng thái: xem mẫu toàn thời lượng; catalog và kiểm tra dày đang tiếp tục.** MP4 local 51:10.40, 1280×720, ~29.97 fps; probe và transcript Groq JSON/SRT/TXT tại `research_media/great-art-explained/analysis-b/GLW9omJfAdk/`. Transcript ASR chưa được hiệu đính. Đã dùng view_image xem 10 contact sheets, tổng 614 ảnh cách 5 giây, nhãn gần tâm khoảng; phạm vi từ đầu đến cuối. [Thư mục sheet](../../../../../research_media/great-art-explained/analysis-b/GLW9omJfAdk/sheets/). Frame đầu/cuối thực tế chưa kiểm tra riêng; thời điểm mẫu và các ranh giới bên dưới chỉ xấp xỉ. FFmpeg đã giải mã toàn video cho scene filter 0.35, log `scenes.log`; scan máy không phải xem tay mọi frame hay đếm cut chính xác.

## Timeline mẫu toàn phim

| Khoảng | Nội dung thấy ở các ảnh mẫu | Sheet |
|---|---|---|
| 00:00–05:20 | Cảnh báo chữ trên đen; Saturn phóng gần; montage mở; tranh, bảo tàng, thẻ chương, chân dung và tư liệu lịch sử. | 01 |
| 05:20–10:40 | Tranh, tranh in, tư liệu chiến tranh; chương mới; footage làm bản khắc và so sánh original/copper plate. | 02 |
| 10:40–16:00 | Footage kỹ thuật, so sánh trước/sau, trang báo và quote, lưới bản in, chi tiết etching, montage và footage. | 03 |
| 16:00–21:20 | Tranh chiến tranh; bảo tàng; ảnh X-ray cạnh nhau; đường viền trắng trên nhân vật, crop chi tiết và ảnh đối chiếu; tranh khác và footage. | 04 |
| 21:20–26:40 | Các bản in, chú giải; địa điểm; tư liệu ngôi nhà và tranh; hình dựng phòng, sơ đồ không gian và ảnh cũ. | 05 |
| 26:40–32:00 | Lưới tác phẩm; bố cục tranh trên nền đen; montage chi tiết; đặt ảnh đối chiếu, ảnh xám và màu trên/dưới. | 06 |
| 32:00–37:20 | Tranh đứng trên nền đen, các ảnh đặt cạnh; tài liệu xám/cũ so với tranh; hai tranh với đường kích thước và con số. | 07 |
| 37:20–42:40 | Chữ trích dẫn, chi tiết tranh; đặt bản xám bên cạnh hoặc chồng lên tranh màu; viền nhân vật; sơ đồ phòng và thẻ chương. | 08 |
| 42:40–48:00 | Tranh, footage, chồng ảnh; chương Saturn; cận tranh, các tác phẩm liên hệ và tư liệu. | 09 |
| 48:00–51:10 | Chương Drowning Dog, ảnh xám so tranh màu và vòng tròn chú giải; kết bằng tranh, footage, đen. | 10 |

## Catalog theo tên chuẩn; các mốc mẫu có bất định khoảng 5 giây hoặc lớn hơn

| Canonical name / event | Quan sát, lớp và bằng chứng | Camera/chuyển cảnh, chữ, âm thanh |
|---|---|---|
| `ART_PUSH_IN` / GOYA-01 | 00:12–00:58: Saturn từ vùng tranh nhỏ đến cận mặt, nền tối; [sheet 01](../../../../../research_media/great-art-explained/analysis-b/GLW9omJfAdk/sheets/01.jpg). | Crop/phóng liên tục có vẻ tăng; cần clip để đo easing. Nhãn tác phẩm góc dưới. Quan hệ lời/nhạc chưa nghe xác minh. |
| `CHAPTER_BLUR_TITLE` / GOYA-02 | ~02:17; ~24:42; ~45:37: nền tranh/ảnh mờ, chữ trắng ở giữa trên cùng. Sheets 01/05/09. | Chuyển lớp chưa xác nhận chính xác; âm thanh chưa đối chiếu. |
| `COMPARISON_SPLIT` / GOYA-03 | ~09:27, 30:42–31:02, 34:32–34:47, 48:47–49:02: ảnh in/bản đồng hoặc ảnh cũ xám cùng ảnh màu; cạnh nhau/chồng hoặc trên dưới, nền đen. Sheets 02/06/07/10. | Có bố cục so sánh, chưa thể kết luận registration hay kỹ thuật ghép. Chữ nhãn ở một số ảnh. |
| `ANNOTATION_CONTOUR` / GOYA-04 | Đoạn 17:44–18:06: tranh nền, đường trắng viền nhóm lính rồi nhóm nhân vật khác; [mẫu dày 1 fps, 22 giây bắt đầu 17:44](../../../../../research_media/great-art-explained/analysis-b/GLW9omJfAdk/dense/outline-1064.jpg), thứ tự trái sang phải, trên xuống dưới. Xuất hiện sau hai mẫu đầu và thay đổi tiếp; biên chính xác cần PTS. | Có crop cận nhóm lính rồi trở về toàn cảnh; đường vẽ là lớp đồ họa thấy được, không suy ra mask. Âm thanh chưa kiểm. |
| `COMPARE_OVERLAY_ARTWORK` / GOYA-05 | ~18:42–18:47: ảnh Guernica đặt trên cạnh hình chi tiết tranh Goya; sheet 04. | Lớp ảnh chồng/cạnh, chưa xác định chuyển động hoặc điểm cắt. |
| `SPATIAL_RECONSTRUCTION_DIAGRAM` / GOYA-06 | ~25:02–25:17: góc phòng, sơ đồ khối dạng wireframe có hình tranh trên mặt phẳng; sheet 05. | Có biểu diễn phối cảnh, không đủ chứng cứ kết luận 3D thực hoặc camera 3D. |
| `DIMENSION_ANNOTATION` / GOYA-07 | ~35:42–35:52: hai tranh trên nền đen, đường đo và con số trắng; sheet 07. | Lớp ảnh + annotation; chưa kiểm tra chuyển động/nhạc. |
| `CIRCLE_ANNOTATION` / GOYA-08 | ~48:57: vòng tròn trắng chỉ chi tiết ảnh xám; sheet 10. | Ảnh nền + vòng; chưa xác nhận kiểu xuất hiện. |
| `ART_GRID`, `SOURCE_LABEL`, `FOOTAGE_INSERT`, `BLACK_MATTE` | Lưới bản in ~11:42 và tranh ~26:57; nhãn trắng nhỏ lặp lại; footage bảo tàng/khắc/chiến tranh; tranh dọc trên nền đen, ví dụ 33:12 và 35:37. | Những loại lặp được nhóm theo tên, không đếm mỗi lần xuất hiện thành loại mới. |

**Chưa quan sát/không đủ bằng chứng:** true 3D, parallax thực, AI generation, map route, color wheel, chart/timeline, perspective/anamorphic warp. Điều này chỉ áp dụng cho các mẫu đã xem, không chứng minh vắng mặt toàn video. Chưa kiểm tra nghe độc lập quan hệ narration/music/SFX; chưa xác định software. Dense timestamp, motion cơ bản và các đoạn so sánh còn cần đối chiếu trước khi coi catalog hoàn thiện.

Kiểm dày GOYA-01: [20 mẫu 1 fps 00:12–00:32](../../../../../research_media/great-art-explained/analysis-b/GLW9omJfAdk/dense/push-12.jpg) xác nhận push-in trên nền đen và nhãn nguồn biến mất; mốc ±1 giây.
