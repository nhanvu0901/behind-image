# STAGES_ui: tìm lỗi giao diện các bước 3, 4, 6 và khung bản nháp (tester độc lập)

Chạy trên máy chủ Windows (một bản thứ hai của ứng dụng, cổng 8562, dữ liệu sao chép trong thư mục tạm, mọi thứ chậm hoặc bên ngoài đều giả), trình duyệt là Chrome headless trên máy Mac qua đường hầm ssh. Mã kiểm tra: `tests/e2e/stages/` (`launch.py` chạy trên máy chủ, `remote.mjs`, `run.mjs`). Ảnh chụp: `.scratch/stages_ui/shots/`.

## Cách chạy
- Mã của cây làm việc được đóng gói bằng `tools/deploy/deploy_windows.sh --pack-only` rồi giải nén vào một thư mục tạm riêng trên máy chủ (không dùng thư mục `D:\code\behind-the-image`, vì mỗi lần triển khai của agent khác sao lưu đè cả cây và lúc 23:09 đã đè lên bản của tôi bằng bản cũ hơn). Dùng lại `.venv`, `books`, `projects`, `library` của máy chủ ở chế độ chỉ đọc; dữ liệu được SAO CHÉP.
- Đồ giả đã chọn: giọng `fake`, máy đo từ `even`, mô hình `mock`, bản nháp `auto` (agy bị giấu khỏi PATH, `agy models` không bao giờ được gọi), gợi ý `FakeProvider`, Commons và Met qua dữ liệu mẫu `tests/media/fixtures`, engine/ffmpeg của bước xuất qua `fake_tools_wrap.py` (không dựng thật dù chỉ 5 khung hình: engine trên máy chủ chậm gấp 4 lần và điểm cần xem là trang, không phải điểm ảnh; ffprobe thật vẫn dùng cho tệp âm thanh thật), khóa nặng chỉ trong tiến trình.
- Ảnh thu nhỏ từ Wikimedia là địa chỉ ngoài nên Chrome bị chặn mạng ngoài (ảnh nhỏ hỏng là do thử nghiệm, không phải lỗi).

## Lỗi

