# `cuHgxPe3J7I` — Sargent, catalog đang thực hiện

Trạng thái: file đã hoàn chỉnh, ASR và scan toàn video đang chạy. Đã xem overview 20 ảnh lấy cách 100 giây, PTS được `showinfo` ghi, từ 0 đến 1900.032 giây; chưa xem xong toàn bộ candidate và mẫu dày, không coi là xem toàn bộ frame. Không suy ra transition hay camera move từ một ảnh đơn.

| ID | PTS (giây) | Quan sát | Tin cậy |
|---|---:|---|---|
| A-J01 | 600.033 | Chia đôi chân dung Madame X và bản vẽ nét trên nền đen. | Trung bình: một frame |
| A-J02 | 1000.032 | Chia đôi chân dung áo đỏ và chân dung cổ khác, kèm caption nguồn chữ trắng nhỏ. | Trung bình: một frame |
| A-J03 | 1100.032 | Chữ lớn màu trắng, nghiêng serif, nằm chồng ngang lên ảnh nội thất triển lãm. Cần chuỗi dày để xác nhận xuất hiện và thời gian. | Trung bình: một frame |
| A-J04 | 1400.032 | Hai crop cạnh nhau so sánh cận bàn tay với toàn thân người mẫu. | Trung bình: một frame |
| A-J05 | 1500.032; 1700.032 | Tư liệu đen trắng/sepia có người trình diễn hoặc cảnh kịch; chưa xác nhận chuyển động bằng frame đơn. | Trung bình: bố cục |

Dự kiến bổ sung toàn bộ scene candidate, mẫu PTS gốc và chuỗi dày; chưa nghe kiểm âm thanh. Các quan sát không chứng minh danh mục đầy đủ của phim.

Kiểm dày ba đoạn mỗi 15 frame (~0,5 giây), xem thực tế sheet trong `analysis-a/cuHgxPe3J7I/dense-*`:

- `A-J06` PTS 1096.529–1102.535: nhiều mẩu chữ serif trắng, nghiêng, cỡ lớn trượt ngang từ phải sang trái trên nền tranh triển lãm; các câu nối đuôi, một phần bị cắt bởi mép khung. Nhãn credit nhỏ ở góc trái dưới nằm lại. PTS 1103.035 đã là chân dung trên nền đen; không xác định điểm cắt chính xác giữa hai mẫu. Cao.
- `A-J07` PTS 1395.027–1396.528: bố cục chuyển từ crop mép bàn bên cạnh chân dung sang crop sát bàn tay ở trái và thân váy bên phải; giữ hai vùng so sánh trong chuỗi đến 1404.536. Không biết cut hay wipe chính xác giữa các frame mẫu. Cao về bố cục.
- `A-J08` PTS 1893.024–1894.526: ảnh thứ hai trượt vào từ mép trái, trở thành ô chia đôi với ảnh đang có; 1899.030–1899.531 ô mới rút về mép trái và khung trở lại ảnh cũ. Xấp xỉ 1–1,5 giây cho chiều vào và dưới một giây theo khoảng mẫu cho chiều ra; không suy ra easing hoặc xác quyết mặt nạ so với chuyển ảnh. Cao.
- `A-J09` PTS 140.007–149.516: trên bản đồ châu Âu tĩnh, nhiều chấm đỏ lần lượt xuất hiện ở nhiều vị trí; chuỗi dày không cho biết tọa độ hay ngữ nghĩa từng điểm. Cao.
- `A-J10` PTS 540.540, 550.550, 560.560, 570.570, 580.580, 590.590: hai ô so sánh ảnh vẽ ở các giai đoạn hình thành bên trái và chân dung hoàn thiện bên phải, hình bên trái tiến triển giữa các mẫu. Không xác định nhịp brushstroke trong khoảng 10 giây. Cao về các trạng thái.
- `A-J11` PTS 1555.020–1564.530: tiêu đề chương serif nhỏ căn giữa trên nền mờ, chuyển sang hai tranh đặt cạnh; mũi tên kích thước và chữ số trắng xuất hiện theo trục dọc/ngang, sau đó mờ đi và nền tối dần. Cao; số liệu cụ thể cần xem nguồn ở độ phân giải gốc.
- `A-J12` PTS 720.720: bảng màu lưới 3×3, mỗi ô màu có nhãn; 1291.290 và 1391.390: hình ellipse vàng đánh dấu vị trí hoặc cạnh bàn trên tranh. Trung bình, các frame đơn.

Coverage: đã xem trực tiếp 190/190 candidate scene >0,35, 195/195 mẫu PTS gốc cách tối thiểu 10 giây từ 0 tới 1941.940/1951.1s và 5 đoạn dày ~0,5 giây (140–150, 1095–1105, 1395–1405, 1555–1565, 1890–1900). Quét scene toàn frame không đảm bảo phát hiện mọi lớp hay cut. Recurring: black matte, crop, hình ghép, chú thích nguồn, chapter serif, tư liệu đen trắng, dissolve, callout. Novel: A-J06, A-J08–A-J11. ASR đã tạo; audio chưa nghe kiểm.
