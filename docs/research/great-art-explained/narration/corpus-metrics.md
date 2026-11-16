# Corpus narration: phạm vi, phép đo và cách đọc

## Phạm vi và độ phủ

Manifest tại `docs/research/great-art-explained/corpus/manifest.json` có 93 ID, trong đó 86 MP4 tồn tại tại chỗ. Quét đệ quy workspace theo ID manifest, loại `*.info.json` và chỉ nhận JSON có `segments` là danh sách. Index ghi cả đường dẫn JSON/TXT/SRT, thời lượng, loại, số segment/từ và mức tin cậy cho từng ID, kể cả ID thiếu transcript. Một ID chỉ tính một lần; không thấy ID nào có nhiều đường dẫn cùng định dạng tại thời điểm quét. TXT/SRT không dùng để đếm lại JSON.

- **Baseline:** 50/93 ID có JSON segments và 50 có TXT/SRT: 39 documentary dài, 7 Cities, 3 Shorts, 1 talk/live; 43 ID thiếu JSON segments. Snapshot baseline tại `research_media/great-art-explained/narration-analysis/metrics-baseline.json` và `transcript-index-baseline.json` cùng thư mục.
- **Bản mở rộng:** 51/93 có JSON segments, 51 TXT/SRT: thêm Seurat `AJr2T1ko3Is`, do đồng nghiệp đã ASR, không gọi ASR lại. Lưu JSON gốc và TXT/SRT chuyển đổi từ segments tại `research_media/great-art-explained/narration-analysis/transcripts/AJr2T1ko3Is/`. File JSON có 163 segments, thời lượng 924,595374 s trùng ffprobe MP4 có audio; start tăng, không có segment ngược hoặc vượt thời lượng, điểm cuối 915,627 s. Không có đối chiếu nghe để xác thực chữ hoặc độ chính xác mốc.
- Cả 16 ID được hai nhóm chọn để đọc sâu hiện có JSON segments; trong baseline chỉ Seurat thiếu. Bản mở rộng còn 42 ID thiếu JSON segments, danh sách cụ thể trong index và metrics. Ngôn ngữ English là suy đoán từ văn bản ASR, không phải nhận diện độc lập từng file; độ tin cậy vừa.
- Phân loại dựa vào tab trước, sau đó từ khóa title; không xác minh thể loại từng tác phẩm bằng cách nghe/xem hết. Shorts gồm cả announcement vì tab ưu tiên. Mẫu đích: documentary tab videos, thời lượng ≥300 giây, có transcript và duration; loại Cities, talk/live, quảng bá và Shorts. Có 63 documentary theo title/tab trong manifest, 40 có transcript đủ điều kiện sau bổ sung; mẫu thuận tiện không đại diện thống kê cho toàn bộ kênh.

## Thống kê mô tả

Bảng dưới là bản mở rộng; baseline giữ riêng, không hồi tố gộp. p50/p90 nội suy tuyến tính. Đại lượng gộp lấy tổng tử chia tổng mẫu số, còn p50/p90 theo video là mỗi video một giá trị.

| Chỉ số | 40 video có overlap | 35 đại diện family | Baseline 39 / 34 |
|---|---:|---:|---:|
| Tổng từ regex | 124.755 | 112.750 | 122.498 / 110.493 |
| Duration video p50 / p90 | 1.096,88 / 1.953,34 s | 1.213,70 / 1.964,51 s | 1.111,82 / 1.955,57 s; 1.228,07 / 1.966,74 s |
| Từ mỗi video p50 / p90 | 2.545,5 / 4.733,8 | 2.851 / 4.887,8 | 2.563 / 4.764,6; 2.924 / 4.918,6 |
| Từ/phút toàn file, gộp | 140,31 | 139,75 | 140,20 / 139,62 |
| Từ/phút toàn file, p50 / p90 theo video | 138,79 / 149,92 | 138,31 / 147,20 | 138,75 / 149,95; 137,96 / 146,93 |
| Từ/phút tổng span segment, gộp | 149,59 | 149,05 | 149,40 / 148,82 |
| Từ/phút span segment, p50 / p90 theo video | 147,93 / 158,34 | 147,67 / 158,00 | 147,85 / 158,22; 147,25 / 157,25 |
| Câu ASR: số từ p50 / p90 | 17 / 36 | 17 / 36 | 17 / 36; 17 / 36 |
| Tỷ lệ câu ASR >25 từ | 23,29% | 23,49% | 23,37% / 23,59% |

Từ regex là `[A-Za-z]+(?:['’][A-Za-z]+)*`: đếm contraction một từ, bỏ chữ số và từ không dùng chữ Latin ASCII. Câu là chuỗi tách tại khoảng trắng sau `.`, `!`, `?`, chỉ giữ chuỗi có từ; lỗi ASR, viết tắt, dấu câu thiếu hoặc sai ảnh hưởng p50/p90 và share. Tổng span là tổng `(end-start)` các segment hợp lệ, không trừ overlap; segment có thể gồm cả khoảng im hoặc nhạc. Vì thế cả hai tỷ số đều là mật độ văn bản theo mẫu số đã nêu, **không phải tốc độ nói thực tế**.

### Dấu hiệu chuỗi ký tự, không phải phân tích ý nghĩa

Với 40 video, tổng số và số trên 1.000 từ lần lượt: dấu hỏi 96 / 0,77; contrast 1.097 / 8,79; we 945 / 7,57; you 259 / 2,08; hedge 329 / 2,64; visual deictic 3.346 / 26,82. Với 35 đại diện: 94 / 0,83; 1.006 / 8,92; 817 / 7,25; 248 / 2,20; 298 / 2,64; 2.977 / 26,40. Các regex cụ thể có trong `metrics.json`: contrast gồm but/however/although/though/yet/whereas/while/nevertheless; we gồm we/us/our/ours/ourselves; you gồm you/your/yours/yourself/yourselves; hedge gồm perhaps/maybe/possibly/probably/might/may/seems/appears/suggests và dạng gốc; visual gồm here/there/this/these/that/those/look/see/notice/above/below/left/right/foreground/background. Không tách nghĩa: ví dụ while, may, right, see hoặc this có nhiều cách dùng, và dấu hỏi phụ thuộc ASR. Đây là số lần khớp, không chứng minh câu thực sự tương phản, chỉ thị hình ảnh, mức độ thận trọng hay tác động retention.

## Overlap và độ nhạy

So khớp mọi cặp transcript bằng tập 8 từ liên tiếp viết thường; phát hiện cạnh khi giao ≥30 shingles và ≥8% tập nhỏ hơn. Metadata tên phim củng cố hai family: **Dark Goya full + Part One/Two** (containment 72,40% và 77,96%); **Bosch Garden full + Parts One/Two/Three** (84,69–92,95%). Các phần không được coi là quan sát độc lập khi đọc kết quả đã điều chỉnh. Phép nhạy giữ bản full dài nhất của mỗi family, loại 5 part; không khẳng định toàn bộ nội dung y hệt. Phép này có thể bỏ mất phần mới của các bản part và không phát hiện mọi loại trùng.

Pollock Part One/Two cùng chủ đề nhưng không đạt ngưỡng overlap: giữ cả hai, không tự xem cùng nội dung. Mona Lisa full/short là candidate theo title; bản short thiếu transcript nên chưa kiểm chứng. Sargent full chưa có các part tương ứng trong manifest: không suy đoán nhóm trùng. Danh sách cặp và ID trong metrics.

## Quan sát văn phong có giới hạn

Đã đọc thủ công các đoạn mở, giữa và kết của bốn transcript Matisse Red Studio, School of Athens, Starry Night updated và Guernica; không tuyên bố đọc thủ công toàn corpus. Trong bốn mẫu này có thể thấy một cách tổ chức đáng thử: mở bằng tình huống lịch sử hoặc sự nghịch lý cụ thể; chuyển từ bối cảnh sang những chi tiết tạo hình có thể định vị; đặt các cách nhìn đối lập cạnh nhau; rồi mở rộng kết luận từ bức tranh sang một ý nghĩa khái quát. Các phim khác có thể tổ chức khác; ASR có sai sót và các phát biểu lịch sử trong transcript chưa được kiểm chứng ở đây.

Cảm giác văn chương đến từ sự đan xen câu tường thuật sự kiện, miêu tả thị giác và nhận định có trọng tâm: mô tả chi tiết trước, sau đó mới giải thích nó thay đổi cách nhìn thế nào. Một motif hoặc đối lập có thể trở lại trong đoạn kết, cho đoạn kết cảm giác khép vòng. Với người viết, đây là quan sát định tính về bốn mẫu chứ không phải công thức được suy từ số lần xuất hiện từ khóa; tránh áp nhận định phổ quát và cảm xúc lên mọi tác phẩm.

## Âm thanh: đo tín hiệu, không nghe

Không có công cụ nghe âm thanh thực trong lượt này; không dùng `afplay` để khẳng định đã nghe. `audio-measurements.json` ghi sáu mẫu tiện chọn 20 s: bốn documentary tại 60 s và hai Shorts tại 10 s; không phải mẫu ngẫu nhiên. FFmpeg trộn mono 16 kHz đo RMS toàn clip; `silencedetect` ngưỡng -35 dB, tối thiểu 0,3 s. RMS dBFS lần lượt -25,62, -22,48, -24,74, -15,06, -17,89, -20,51; số khoảng phát hiện lần lượt 3, 5, 3, 0, 0, 2. Chi tiết timestamp và thời lượng ở JSON. Nhạc/âm nền và mix thay đổi kết quả, nên đoạn dưới ngưỡng không tương đương ngắt lời, không đo nhịp nghỉ speech hay chất giọng; không đo F0, tuổi, tính cách hoặc voice clone.

Phân tích tái lập bằng `research_media/great-art-explained/narration-analysis/analyze.py` và `audio.py`. Không tải thêm nội dung từ YouTube; máy xử lý toàn bộ transcript hiện có, còn phần diễn giải thủ công chỉ là mẫu được nêu rõ.
