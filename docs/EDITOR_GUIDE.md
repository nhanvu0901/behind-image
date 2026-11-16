# Hướng dẫn trang biên tập video

Trang này để xem và sửa `storyboard.json` của một video: shot, lớp phủ (overlay), kỹ thuật, tham số, hình và thời điểm. Khung hình xem trước là ảnh thật do engine dựng, không phải ảnh giả.

## Khởi động

```
cd /Users/nhanvu/Documents/code/behind-the-image
tools/run_editor.sh          # lần đầu tự tạo .venv và cài requirements.txt (cần ffmpeg)
```

Mở http://127.0.0.1:8560/ . Chỉ nghe trên 127.0.0.1, cổng 8560 (không dùng 8550). Kiểm tra `http://127.0.0.1:8560/api/health`: phải thấy `engine: real` và `media: real`. Nếu thấy `stub` thì khung hình/hình ảnh chỉ là giả để thử.

- Chọn dự án ở ô trên cùng bên trái, hoặc mở `/?project=<tên>`.
- `projects/arnolfini/` là bản gốc, đừng sửa. Để sửa thử hãy dùng bản sao `projects/arnolfini_edit/`.
- `?mock=1` chạy trang với dữ liệu giả, không cần server.

## Các khu vực

- **Thanh trên cùng**: Lưu, Kiểm tra (số lỗi/cảnh báo), Hoàn tác, Làm lại, Đề xuất, Duyệt (và trạng thái duyệt), Xem thử 10 giây.
- **Khung xem trước (trái trên)**: ảnh thật tại vị trí đầu phát. Các khung màu K1, K2... là khóa camera của shot, kéo để đổi `cx, cy`; kéo núm vuông ở góc để đổi zoom. Khi chọn lớp phủ có tham số điểm/vùng, kéo chấm vàng để dời, kéo núm để đổi bán kính. Ô "Ảnh gốc" cho xem toàn ảnh để kéo khung dễ hơn. Ô "Hiện vùng" hiện tên các vùng (region) của hình.
- **Thanh phát**: shot trước/sau, phát/dừng, thời gian, từ đang đọc.
- **Bảng bên phải**: tab *Shot* (kỹ thuật, slot hình, thời điểm bắt đầu, tham số, chuyển cảnh, khóa, ghi chú), *Lớp phủ*, *Hình* (hình của dự án, vùng, tìm kiếm Commons/The Met, tải lên), *Lỗi*.
- **Timeline (dưới)**: chương, shot (ảnh nhỏ, huy hiệu kỹ thuật), lớp phủ, từng từ (khi phóng to), sóng âm, bản đồ nhỏ.

Biểu mẫu tham số được sinh tự động từ registry (`style/gae/techniques.json` cùng các bản vá), nên kỹ thuật mới xuất hiện không cần sửa trang. Kiểu hỗ trợ: số, enum, bool, chuỗi, màu, điểm, danh sách điểm (`points`, có nút "Chọn trên ảnh" cho từng điểm), danh sách dòng (`lines`, mỗi dòng một mục), khung, camera. Kiểu lạ sẽ hiện ô JSON.

Không có phụ đề nào được vẽ lên hình. Lời thoại chỉ hiện ở timeline và thanh phát.

## Phím tắt

| Phím | Việc |
|---|---|
| Space | Phát/dừng (phát âm thanh thật, hình bám theo) |
| S | Cắt shot tại đầu phát |
| L | Khóa/mở khóa mục đang chọn |
| Delete | Xóa lớp phủ (hoặc shot nếu không chọn lớp phủ) |
| `[` `]` | Shot trước/sau |
| Mũi tên trái/phải | Từ trước/sau |
| Ctrl+S | Lưu |
| Ctrl+Z, Ctrl+Shift+Z (hoặc Ctrl+Y) | Hoàn tác, Làm lại |
| Ctrl+cuộn | Zoom timeline |
| Shift+cuộn | Cuộn ngang timeline |
| Alt khi kéo | Đặt thời điểm tự do (neo `{t}`), không bám từ |
| Esc | Hủy chế độ "Chọn trên ảnh" |

Trên timeline: kéo ranh giới giữa hai shot để đổi thời lượng (bám đầu từ). Kéo thân thanh lớp phủ để dời, kéo mép trái/phải của thanh để đổi đầu/cuối. Khi một ranh giới đi qua lớp phủ, lớp phủ tự co hoặc dịch vào trong shot.

## Cắt, gộp, camera

- **Cắt**: mỗi nửa giữ đúng tư thế camera tại điểm cắt (zoom nội suy theo log, giống engine).
- **Gộp với shot trước**: camera của shot trước giữ nguyên mốc thời gian tuyệt đối và giữ tư thế cuối trong phần gộp; camera của shot bị gộp bỏ đi; lớp phủ của hai shot được nối lại.
- Đổi hình của một slot sẽ đặt lại camera theo hình mới (engine tính lại mặc định).

## Khóa, nguồn, duyệt

- Mọi chỉnh sửa tay đặt `source: "human"`. **Khóa** (L) nghĩa là người đã chốt mục đó: đề xuất của agent không bao giờ sửa mục khóa (kể cả khi chọn "chấp nhận tất cả").
- **Lưu** gửi bản nháp kèm `base_rev`. Nếu server đã đổi (409) trang hỏi giữ nháp hay tải lại. Nếu còn lỗi (422) trang không lưu và mở tab *Lỗi*; bấm vào một lỗi để chọn đúng mục.
- **Duyệt** chỉ bật khi đã lưu và không còn lỗi. Trạng thái: *Chưa duyệt*, *Đã duyệt*, *Duyệt cũ (đã sửa)*. Duyệt gắn với phiên bản (`rev`), sửa xong lưu lại thì phải duyệt lại.

## Đề xuất của agent

Agent ghi `projects/<id>/proposals/<id>.json`. Nút *Đề xuất* mở danh sách; mở một đề xuất để xem từng thay đổi (trước/sau), chọn Chấp nhận hoặc Từ chối cho từng cái rồi *Áp dụng*. Thay đổi chạm vào mục khóa bị gạch và không áp dụng được. Đề xuất áp lên bản đã lưu, không phải bản nháp chưa lưu.

## Xem thử 10 giây

Dựng clip 10 giây từ đầu phát (kèm âm thanh) bằng bản nháp hiện tại, rồi phát trong cửa sổ nổi. Mất vài giây. Dự án không có file âm thanh vẫn xem thử được (không có tiếng) và timeline ghi rõ "chưa có file âm thanh".

## Tìm và nhập hình

Tab *Hình*: tìm trên Wikimedia Commons hoặc The Met, chỉ nhận giấy phép PD, CC0, CC BY, CC BY-SA. Bấm *Nhập* để tải về `media/` của dự án (nên dùng bản sao, không dùng `arnolfini`). Nếu bấm "Chọn" ở slot thì hình mới được gán vào slot ngay. Nhập xong phải *Lưu* để hình nằm trong storyboard. Nếu nguồn trả 429/503, trang báo thử lại sau vài giây.

## Chưa có

- Camera của kỹ thuật có nhiều camera (ví dụ `camera_left`/`camera_right` của LAY-01) chỉ sửa được bằng ô số, chưa kéo khung được.
- Chỉ Wikimedia Commons và The Met (chưa có AIC, Rijksmuseum, Europeana).
- Khoảng 47 kỹ thuật còn lại hiện xám trong thư viện cho đến khi engine port xong.
- Chưa có chỉnh âm thanh, TTS, dựng bản cuối chất lượng cao.
- Lịch sử hoàn tác chỉ nằm trong trình duyệt, mất khi tải lại trang. Bản lưu cũ nằm trong `history/`.
