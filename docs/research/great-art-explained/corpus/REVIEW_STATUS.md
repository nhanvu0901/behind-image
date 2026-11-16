# Trạng thái nghiên cứu hình ảnh — checkpoint cục bộ

Inventory công khai: **93 ID**. Đã ffprobe **86 MP4 có video và audio**, gồm 72 video tab `/videos`, 13 Shorts, 1 stream. Một video `/videos` yêu cầu xác nhận tuổi; sáu Shorts còn lại gồm hai lỗi kết nối, một thử thách bot trực tiếp và ba mục chưa thử vì dừng requests. Không suy đoán các mục thiếu nội dung hay hiệu ứng. Trạng thái chi tiết và bytes: [coverage.md](coverage.md), [manifest JSON](manifest.json) và [manifest TSV](manifest.tsv).

Theo ledger và báo cáo hiện tại, **86/86 MP4 sẵn có đã được xem mẫu thủ công theo timeline**: 72 videos, 13 Shorts và một stream. Cờ `visual_reviewed_sampled` trong manifest là xem mẫu, không phải xem từng frame bằng tay hay bảo đảm tìm mọi effect. Có video được kiểm thêm các chuỗi ảnh dày cho motion tiêu biểu; những khoảng giữa các ảnh mẫu vẫn có thể chứa chi tiết chưa thấy. Scene scan tự động không tương đương xem thủ công liên tục. Audio nằm ngoài phạm vi audit hình ảnh.

- [Ledger A](visual-a/ledger.md) và [coverage B](visual-b/coverage.md) là nguồn trạng thái theo phim dài/talk; báo cáo riêng có mốc và sheet.
- [Shorts coverage](visual-shorts/coverage.md) ghi 13 video dọc được xem mẫu, phương pháp giữ tỷ lệ, ba chuỗi dày và 6 ID thiếu.
- [EFFECTS_CATALOG.md](EFFECTS_CATALOG.md) hợp nhất họ kỹ thuật, bằng chứng motion/tĩnh, ngữ cảnh và clip minh họa; chưa kết luận toàn bộ kênh hay toàn bộ hiệu ứng.
- [manifest.json](manifest.json) và [manifest.tsv](manifest.tsv) giữ metadata flat, duration/kích thước đo từ ffprobe, `upload_date` khi có trong metadata, trạng thái tải và cờ đã xem mẫu theo ID. Giá trị trống là chưa có dữ liệu, không suy đoán.

YouTube requests đã dừng khi gặp bot challenge; các mục chưa tải được vẫn chờ rõ ràng. Không coi age restriction là video xóa hoặc private.

Các ID chưa có MP4: `LejFaCncuc4` (restricted_age); `l8EMN1Hu7aI`, `TXYDSDmW1WE` (lỗi kết nối, không đủ video để ghép offline); `qHF5ZNA_gCQ` (bot challenge trực tiếp); `y4tyypLxRpQ`, `y4raWGPCWpk`, `rxoETUQdrvo` (deferred, chưa thử sau khi dừng requests).
