# Visual B: phương pháp và trạng thái

12-11-2026. Chờ partition và MP4 hoàn chỉnh; chưa phân tích video nào trong partition. Không tải video. Ưu tiên bản full-length dài nhất theo thời lượng MP4 được giao, không dựa vào thời lượng bên thứ ba.

## Quy trình cho từng video

1. Ghi ID, đường dẫn file, trạng thái file hoàn tất, thời lượng, kích thước, codec, frame rate và thời gian bắt đầu stream bằng ffprobe; ghi cách quy đổi timestamp nếu cần. Lưu output Groq JSON/SRT/TXT riêng trong analysis-b; đây là ASR cần đối chiếu audio, không phải lời thoại đã xác minh.
2. Giải mã toàn stream và lập log timestamp/frame, quét scene score trên toàn bộ frame. Đây là quét bằng máy, không phải xem tay toàn bộ; ngưỡng và kết quả phải được ghi rõ. Nó có thể bỏ sót dissolve, pan, thay lớp hoặc bắt nhầm chuyển động. Báo lỗi giải mã và khoảng thiếu nếu có.
3. Tạo contact sheets trải từ đầu đến hết với timestamp thực, khoảng cách đều tối đa 5 giây, bao gồm frame đầu/cuối khả dụng; lưu manifest timestamp và ảnh. Dùng view_image xem lần lượt tất cả sheets, ghi phạm vi đã xem, số sheet và khoảng cách lấy mẫu. Ảnh đại diện không chứng minh các hiệu ứng ngắn giữa mẫu. Tạo thêm khung hình độ phân giải đầy đủ khi cần đọc chi tiết, không dựa riêng thumbnail.
4. Lập timeline bao phủ từ 0 đến hết video thành các khoảng liên tục, ghi hình, bố cục và thay đổi quan sát được; phân biệt khoảng xác nhận, khoảng chỉ có mẫu thưa và chưa xem. Xem thêm video/chuỗi frame dày cho hiệu ứng mới, ranh giới cut/chuyển lớp và các trường hợp không rõ; ghi chính xác khoảng và bước lấy mẫu. Ước lượng thời gian bắt đầu/kết thúc bằng cặp frame hoặc khoảng bất định; không ghi chính xác hơn dữ liệu cho phép.
5. Đối chiếu lời thoại và âm thanh tại đoạn liên quan; ghi quan hệ đồng thời hoặc đồng bộ quan sát được, không gán dụng ý chắc chắn. Kiểm tra riêng nhạc, narration, hiệu ứng âm thanh nếu nghe phân biệt được; ASR không xác minh nhạc hoặc khoảng im lặng.
6. Mỗi hiệu ứng có ID video, category/tên mô tả, hành vi, start/end và bất định, đường dẫn bằng chứng local, lớp thấy được và thứ tự tương đối, camera transform, chuyển cảnh, typography/annotation/maps/charts/3D/parallax/masks/footage và quan hệ âm thanh nếu có; ghi 'không thấy', 'không rõ' hoặc 'không áp dụng' theo bằng chứng. Mô tả hiệu ứng nhìn thấy thay vì khẳng định phương pháp dựng, phần mềm, 3D hay mask khi chưa chứng minh.
7. Kiểm tra đủ manifest, contact sheets đã xem, log quét, timeline, catalog, bằng chứng và transcript; ghi các khoảng thiếu, hạn chế, khác biệt giữa automated full-frame scan và xem mẫu thủ công. Không tuyên bố đã xem mọi frame bằng tay hoặc đã tìm được mọi hiệu ứng.

## Nguồn được công bố riêng

- [Last Supper, eKyYPSpiC9g, mô tả chính kênh](https://www.youtube.com/watch?v=eKyYPSpiC9g): credit Brian Adsit cho opening animation và title sequence; Robert Lewis cho recording. Đây là credit được công bố, không chứng minh người này làm mọi hiệu ứng hoặc công cụ nào được dùng. Một [trang lập chỉ mục bên thứ ba](https://gridvids.com/great-art-explained/great-art-explained-the-last-supper-by-leonardo-da-vinci) ghi 21:04 cho ID/tựa này; chưa đối chiếu local và không đồng nhất với bản được mô tả 36 phút nếu chưa xác định ID.
- Bosch full-length và Mona Lisa full-length: chưa xác minh được credit kỹ thuật sơ cấp trong lượt tra cứu ngắn này. Các mô tả trong web-research là thông tin creator được dẫn trước đó, không thay thế việc xem bản MP4 được giao.
