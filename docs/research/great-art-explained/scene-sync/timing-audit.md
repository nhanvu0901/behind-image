# Audit thời điểm: năm ví dụ

Năm ví dụ được chọn từ hai kế hoạch, không phải kiểm tra toàn bộ. Bảng ảnh được decode từ MP4 gốc, lấy khoảng mỗi 0,2 giây; `showinfo` trong log kèm theo ghi **PTS của frame nguồn** trước khi ghép ảnh. Khoảng khung là cận quan sát theo mẫu và ngưỡng nhìn thấy, không phải thời điểm chính xác frame đầu. ASR chỉ là khoảng segment ước lượng; không xác minh độc lập nội dung hoặc mốc lời bằng nghe.

Các khoảng Δ dưới đây là cận có điều kiện của (thời điểm hình − thời điểm cue trong lời), tính [đầu khoảng hình − cuối segment, cuối khoảng hình − đầu segment], **giả sử cue thực nằm trong segment**. Đây không phải sai số đã đo; ASR có thể căn sai.

## bosch-micro

- Frame nguồn: 736.803–737.003 s; dải màu giữa hai cánh bắt đầu nhìn thấy trong mẫu.
- Segment ASR: 727.500–734.660 s; cue: “two of his men would open the gloomy panels”.
- Δ có điều kiện: +2.143 đến +9.503 s. Dải màu lộ ra giữa hai cánh sau đoạn ASR mô tả mở cánh; khớp ý, hình đi sau đoạn, không thể gán độ trễ tới từ open chính xác.
- Bằng chứng ảnh: `research_media/great-art-explained/scene-sync/timing/bosch-dense.jpg`; log cùng tên `-dense.log` chứa PTS, lệnh và các frame kế cận.

## mona-micro

- Frame nguồn: 500.417–500.617 s; nét vàng biểu diễn đường ánh sáng xuất hiện.
- Segment ASR: 496.760–503.160 s; cue: “light falling onto the painting to reflect”.
- Δ có điều kiện: -2.743 đến +3.857 s. Nét vàng xuất hiện trên sơ đồ lớp sơn trong đoạn giải thích ánh sáng phản xạ; hợp ý, vị trí từ trong đoạn chưa biết, không chứng minh đồng thời.
- Bằng chứng ảnh: `research_media/great-art-explained/scene-sync/timing/mona-dense.jpg`; log cùng tên `-dense.log` chứa PTS, lệnh và các frame kế cận.

## supper-micro

- Frame nguồn: 1194.827–1195.027 s; nhân vật mờ dần hiện ở giữa phòng.
- Segment ASR: 1193.860–1200.000 s; cue: “in a fairly austere room ... making it a story of human”.
- Δ có điều kiện: -5.173 đến +1.167 s. Phòng trống đã hiện trước khi nhân vật bắt đầu xuất hiện; lời mô tả phòng và câu chuyện con người phù hợp tổng thể, nhưng không chứng minh nhân vật là cue của một từ cụ thể.
- Bằng chứng ảnh: `research_media/great-art-explained/scene-sync/timing/supper-dense.jpg`; log cùng tên `-dense.log` chứa PTS, lệnh và các frame kế cận.

## starry-landscape

- Frame nguồn: 692.425–692.825 s; vùng bản vẽ mờ dần xuất hiện bên phải cảnh người đi.
- Segment ASR: 694.420–700.260 s; cue: “on one of these walks he drew this bird's eye view of the village”.
- Δ có điều kiện: -7.835 đến -1.595 s. Hình bản vẽ xuất hiện trước đoạn ASR giới thiệu bản vẽ; phù hợp ý liên quan chuyến đi/bản vẽ, nhưng không xác nhận danh tính bản vẽ hay chính xác từ nào được nhấn.
- Bằng chứng ảnh: `research_media/great-art-explained/scene-sync/timing/starry-dense.jpg`; log cùng tên `-dense.log` chứa PTS, lệnh và các frame kế cận.

## sargent-reviews

- Frame nguồn: 1096.629–1097.029 s; dòng chữ trắng objectionably Parisian mờ dần vào trên hình.
- Segment ASR: 1096.200–1101.960 s; cue: “British critics found it objectionably Parisian, too decadent”.
- Δ có điều kiện: -5.331 đến +0.829 s. Cụm chữ trùng cụm ASR trong cùng đoạn; nội đoạn chưa biết và sự xuất hiện được khoanh theo ngưỡng nhìn thấy, không xác định điểm đầu tuyệt đối.
- Bằng chứng ảnh: `research_media/great-art-explained/scene-sync/timing/sargent-dense.jpg`; log cùng tên `-dense.log` chứa PTS, lệnh và các frame kế cận.

## Trích đoạn có âm thanh

Năm clip 6 giây và lệnh, ffprobe được ghi trong `research_media/great-art-explained/scene-sync/timing/excerpt-validation.json`. Mốc clip dự kiến là PTS nguồn trừ thời gian bắt đầu trim; audio bắt đầu 0, video bắt đầu 0,016–0,033 s trong container clip, khác 0 vì ranh giới frame. Không coi timestamp clip là timestamp nguồn nếu chưa cộng mốc trim; container duration 6,005–6,039 s do ranh giới frame, và có cả hai luồng. Clip tái mã hóa, dùng đối chiếu, không thay thế MP4 gốc.

Không cần gọi ASR cấp từ để rút ra những kết luận có giới hạn trên. Độ chính xác PTS hình không tương đương thời điểm phát âm.
