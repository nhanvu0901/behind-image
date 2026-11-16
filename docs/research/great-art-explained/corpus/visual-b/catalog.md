# Visual B — catalog nhóm đang cập nhật

Một canonical name là một họ biểu hiện, không phải số lượng lần xuất hiện. Mỗi report video có event ID, mốc gần đúng và đường dẫn ảnh; các mục mẫu đang tiếp tục kiểm dày. Không suy ra phần mềm hoặc quy trình nội bộ.

| Canonical name | Mô tả nhìn thấy | Ví dụ video / event |
|---|---|---|
| `ART_CROP_PUSH_PAN` | Thay khung/độ lớn vùng tranh; cần chuỗi frame xác minh chuyển động. | GLW9omJfAdk GOYA-01; vBG621XEegk BOSCH-01; ElWG0_kjy_Y; eKyYPSpiC9g; YFI6cQF1ros; hiyCTfSoH9Q; cE0BqbS2n6M |
| `BLACK_MATTE`, `SOURCE_LABEL`, `FOOTAGE_INSERT`, `CHAPTER_BLUR_TITLE`, `QUOTE_OVERLAY` | Nền đen, nhãn tác phẩm, tư liệu, chữ chương trên nền mờ, trích dẫn trên hình. | Báo cáo của 7 video đã xem mẫu. |
| `PERSPECTIVE_LINE_ANNOTATION` | Các đường hội tụ phủ hình. | BOSCH-02, SUPPER-01, MENINAS-04. |
| `ANNOTATION_CONTOUR`, `FIGURE_OUTLINE`, `CIRCLE_ANNOTATION` | Đường viền hoặc vòng chỉ vùng/nhân vật. | GOYA-04/08; SUPPER-04; BOSCH-05; BACON-04; CARR-04. |
| `COMPARISON_SPLIT`, `REGISTERED_SCAN_COMPARISON`, `IR_COMPARISON` | Ảnh đối chiếu cạnh/chồng hoặc bản scan và màu. | GOYA-03; BOSCH-06; MONA-03; BACON-02; CARR-03. |
| `PROGRESSIVE_FIGURE_REVEAL` | Nhân vật hiện dần theo nhóm trên bố cục nền. | SUPPER-03: đã xem chuỗi 1 fps. |
| `PANEL_OPEN_REVEAL` | Hai cánh ngoài có biểu hiện xoay/mở, lộ tranh giữa. | BOSCH-04: đã xem chuỗi 1 fps; chưa xác định footage hay mô phỏng. |
| `PAINT_CROSS_SECTION_DIAGRAM` | Sơ đồ các lớp sơn kèm tia và nhãn. | MONA-02: đã xem chuỗi 1 fps. |
| `SPACE_RECONSTRUCTION`, `SPACE_DIAGRAM`, `VIEWPOINT_DIAGRAM` | Minh họa phòng, vị trí và đường nhìn. | GOYA-06; SUPPER-02; MENINAS-01/02. Không khẳng định công nghệ 3D. |
| `DIMENSION_ANNOTATION` | Đường đo và con số trên/giữa ảnh. | GOYA-07; MONA-01; MENINAS-03. |
| `GEOMETRIC_ANNOTATION`, `GEOMETRIC_SPACE_ANNOTATION` | Tam giác hoặc đường khối gắn trên ảnh. | MONA-04; SUPPER-05; BACON-01. |
| `MAP_STATIC`, `MAP_ROUTE` | Hình bản đồ hoặc đường màu nối địa điểm. | BOSCH-07; CARR-01. Đường bản đồ chưa chứng minh được vẽ động. |
| `ART_GRID`, `ARCHIVAL_GRID`, `GRID_COMPARE` | Nhiều ảnh/footage trong ô song song. | GOYA, BACON-03, SUPPER. |
| `SILHOUETTE_OVERLAY`, `REGION_HIGHLIGHT` | Bóng hình hoặc vùng sáng/khác màu trên ảnh. | MONA-05; BOSCH-03. Không khẳng định cách tạo mask. |
| `VISION_DIAGRAM`, `PALETTE_LABEL`, `ILLUSTRATED_SEQUENCE` | Sơ đồ mắt, footage bảng màu kèm tên, chuỗi hình vẽ. | MONA-06; MENINAS-05; CARR-02. |

Chưa có bằng chứng đủ để gán true 3D, parallax thực hay ảnh sinh AI ở các report này. Đây là kết quả trên mẫu đã xem, không là bằng chứng vắng mặt toàn corpus. Danh mục và timeline sẽ tiếp tục mở rộng.

## Bổ sung sau khi xem mẫu 37 phim dài

Mỗi ID dẫn tới báo cáo cùng tên trong thư mục này; `sheets/` là bằng chứng mẫu 5 giây, không phải kiểm từng frame. Tên có quan hệ gần được gộp khi merge: `ART_PULL_OUT` thuộc `ART_CROP_PUSH_PAN`; `ANNOTATION_CIRCLE`/`CIRCLE_ANNOTATION` cùng họ; `PANEL_PERSPECTIVE_OPEN` là `PANEL_OPEN_REVEAL`; `MAP_ROUTE_PATH` là `MAP_ROUTE` (đường có trong ảnh, chưa chắc vẽ động); `FIGURE_REVEAL_ROOM` cùng họ `PROGRESSIVE_FIGURE_REVEAL`, nhưng event khác. Không cộng các biến thể này thành effect mới.

| Canonical | Evidence bổ sung / hành vi quan sát | Giới hạn |
|---|---|---|
| `ART_CROP_PUSH_PAN` → pull-out | `lKIbT-4UFaE` NIGHTHAWKS-01, ~00:00–00:20: [mẫu 1 fps](../../../../../research_media/great-art-explained/analysis-b/lKIbT-4UFaE/dense/pullout-0.jpg) cho thấy crop nhân vật rộng dần, nhãn tác phẩm xuất hiện rồi mất. | Đầu/cuối khoảng ±1 giây; không đo easing. |
| `DISSOLVE_OVERLAY` | `mQVC0qJGJ_c` HOPPER-CINEMA-02, khoảng 07:40–07:45: [mẫu 1 fps](../../../../../research_media/great-art-explained/analysis-b/mQVC0qJGJ_c/dense/dissolve-450.jpg) cho thấy footage cửa hàng và Nighthawks chồng trong lúc chuyển. | Chuỗi lấy 07:30–07:50; mốc ±1 giây, chưa nghe sound. |
| `LAYER_RELATIVE_MOTION` | `IBcB_dYtGUg` WAVE-01, khoảng 01:05–01:20: [mẫu 1 fps](../../../../../research_media/great-art-explained/analysis-b/IBcB_dYtGUg/dense/opening-65.jpg), sóng/thuyền thay vị trí và tỷ lệ tương đối với núi/nền. | Quan sát chuyển động tương đối; chưa xác định tách lớp, reprojection hay camera 3D. |
| `ANNOTATION_CIRCLE`, `ANNOTATION_CONTOUR` | HUNTERS-02, GOYA2-03, DAVID-02, ISTANBUL-02; vòng/đường phủ tranh hoặc tượng. | Không mặc định vòng được vẽ động. |
| `DIMENSION_ANNOTATION` | THINKER-02 ~06:42; ARNOLFINI-02 ~02:57; MICHELANGELO-03 ~10:52. | Nhãn và vạch đo trong ảnh mẫu, thời điểm ±5 giây. |
| `PROCESS_DIAGRAM_SILHOUETTE` | THINKER-03 ~12:32–13:17: silhouette đổi màu/viền bên cạnh footage quy trình đúc. | Chưa xem dense để xác định chính xác thứ tự. |
| `SCULPTURE_EXPLODED_VIEW` | MICHELANGELO-02 ~12:57–13:02, tượng và các mảnh tách trên nền đen. | Chưa xác định vật thể/mô hình số hay thời gian animation. |
| `SCULPTURE_FOOTAGE`, `PROCESS_FOOTAGE` | MICHELANGELO-01, DAVID-01/02, THINKER-01, MARILYN-01; footage tượng thật, thao tác tạc/đúc/in. | Vật thể ba chiều ngoài đời và camera thật không là bằng chứng đồ họa 3D số. |
| `COMPOSITION_GEOMETRY_OVERLAY`, `PERSPECTIVE_GRID` | GUERNICA-01 ~06:42–06:47, lưới và tam giác/vùng màu; NIGHTHAWKS-02 ~05:57–06:02 lưới phối cảnh. | Chưa xác định cách đường xuất hiện. |
| `COMPARE_COLOR_RECONSTRUCTION`, `COMPARE_IMAGING` | ISTANBUL-03 ~04:57–05:27 bản trắng/màu; BOSCH2-02 ~00:52–01:02 ảnh infrared có nhãn; KISS-03 ~06:57–07:07 ảnh thường và xanh/tím. | Không suy đoán thuật toán tô màu hay loại thiết bị nếu không có nhãn. |
| `COMPARE_FILM_ART`, `FOOTAGE_GRID`, `DETAIL_GRID` | HOPPER-CINEMA-01, NIGHTHAWKS-03; NYC-01 footage vẽ chia ô; TANNING-03 crop tranh chia ô. | Bản thân bố cục lưới trong tác phẩm không mặc định là hiệu ứng dựng. |

Đủ bằng chứng lớp chuyển động tương đối trong WAVE-01; **chưa đủ** để kết luận parallax 3D, reprojection, digital true 3D hay tạo ảnh AI. Các trạng thái không quan sát này chỉ áp dụng cho mẫu đã xem, không xác nhận vắng mặt ở mọi frame.

Các mẫu dày bổ sung: `ART_PUSH_IN` GOYA-01 ~00:12–00:32, tranh Saturn phóng lớn đều trên nền đen, [20 mẫu 1 fps](../../../../../research_media/great-art-explained/analysis-b/GLW9omJfAdk/dense/push-12.jpg); nhãn nguồn mất trong chuỗi. `CHAPTER_BLUR_TITLE` TANNING-01 ~08:53–08:56 chuyển hình đang rõ sang mờ kèm chữ, sau đó về rõ; [20 mẫu 1 fps từ 08:42](../../../../../research_media/great-art-explained/analysis-b/zTmq2hgzReQ/dense/pan-522.jpg). Mốc ±1 giây; ảnh mẫu không cho phép đo fade từng frame. Các hướng pan ngang/dọc/chéo và cut/fade/hold chưa có exemplar dense phân loại riêng, không nên coi đã xác minh đầy đủ chỉ từ contact sheet.

`ART_PAN_HORIZONTAL` / KISS-04: ~05:20–05:31, [1 fps](../../../../../research_media/great-art-explained/analysis-b/SNhmSdLDmto/dense/details-320.jpg), hình dịch sang trái trong khung khi đi từ nhân vật sang nền vàng, đồng thời phóng gần; không tách riêng vận tốc pan và zoom. `CROP_CUT_IN` / ARNOLFINI-04: ~04:39–04:41, [1 fps](../../../../../research_media/great-art-explained/analysis-b/T15Kv6dtYO0/dense/details-270.jpg), khung váy/chó chuyển đột ngột sang crop thân và tay; nhãn xuất hiện sau đó. Sai số khoảng ±1 giây, ảnh 1 fps không loại trừ transition ngắn dưới một giây. Pan dọc/chéo, fade và hold vẫn chưa có exemplar dense phân loại riêng.
