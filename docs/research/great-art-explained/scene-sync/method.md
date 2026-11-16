# Phương pháp kiểm tra đồng bộ lời và hình

## Nguồn và giới hạn

Chỉ dùng tám MP4 và JSON ASR cục bộ ghi trong [sync-source-index.json](sync-source-index.json). Các tệp `*.info.json` là metadata, không phải ASR. `ffprobe` lấy time base, thời gian bắt đầu, thời lượng, FPS trung bình/danh nghĩa và thông tin hai luồng. Hiệu `audio.start_time − video.start_time` là độ lệch mốc container, không chứng minh lời nói hay ASR đã căn chính xác. Thời gian của ASR chưa được xác minh độc lập so với audio; nội dung ASR cũng có thể sai. Không khẳng định đã nghe khi không có công cụ nghe.

Tám JSON hiện chỉ có `segments` với `start`, `end`, `text`; không có word timestamp thực. Khoảng ASR là khoảng được mô hình gán, không phải biên âm thanh đã xác thực. Không chia đều thời gian cho các từ; một từ nằm trong đoạn vẫn có thời điểm nội đoạn chưa biết. Với onset hình V và đoạn chứa cue [S,E], chỉ có thể nêu V trước S, nằm trong [S,E], hoặc sau E; nếu giả định cue thực sự nằm trong đoạn, độ lệch V−cue nằm trong [V−E,V−S]. Khoảng giao 0 không chứng minh trùng khớp; sai số nhận dạng và căn thời gian ASR không được định lượng.

## Quy trình audit chọn mẫu

1. Chọn 4–6 ví dụ từ hai kế hoạch; ghi ID, lý do chọn, nguồn và đoạn ASR liên quan, cả các trường hợp không rõ hoặc phản ví dụ. Đây không phải đánh giá toàn bộ corpus.
2. Decode MP4 gốc quanh mỗi mốc, kiểm tra các frame và PTS thực tế; dùng frame trước/sau để khoanh khoảng thay đổi có thể thấy. Phân biệt bắt đầu chuyển cảnh, bắt đầu hình mới, thời điểm đủ rõ để nhận diện, và animation onset; định nghĩa rõ mốc đang xét. FPS/time base là độ phân giải biểu diễn, không tự chứng minh onset hay lời nói chính xác.
3. So sánh nội dung quan sát trực tiếp với câu ASR, ghi rõ đối tượng/thao tác có khớp hay không, thông tin còn thiếu, và khoảng lead/lag có thể suy ra. Không suy luận ý nghĩa hình ảnh chỉ từ tên case, transcript hoặc chỉ số tự động.
4. Nếu trích clip, lưu lệnh và `ffprobe` kiểm tra thời lượng, timestamps audio/video, quy tắc ánh xạ về thời gian gốc; không mặc định clip PTS bằng PTS nguồn. Chỉ số cut/fade có thể giúp định vị, không tự chứng minh semantic match hoặc loại chuyển cảnh.
5. Rà soát hai báo cáo theo bằng chứng thực tế và phạm vi; không khẳng định tất cả 86 cảnh đồng bộ. Chỉ đề xuất ASR cấp từ cho tối đa hai đoạn ngắn nếu khoảng segment không đủ trả lời câu hỏi trọng yếu; timestamp cấp từ của mô hình vẫn cần xem là ước lượng, không phải ground truth.
