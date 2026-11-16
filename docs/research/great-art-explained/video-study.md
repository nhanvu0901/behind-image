# Great Art Explained: nghiên cứu hai video long-form

Ngày nghiên cứu: 12-11-2026. Đây là phân tích biên tập từ hai bản tải cục bộ, không phải đo retention hay nghiên cứu khán giả. Nguồn đối chiếu web riêng: [web-research.md](web-research.md).

## Mẫu, phương pháp và giới hạn

- [UPDATED: Vincent Van Gogh’s The Starry Night](https://www.youtube.com/watch?v=crCPVoPsTtk): chọn tác phẩm kinh điển, bản cập nhật. Bản cũ `AfPUUm_autM` có trong kết quả tìm kiếm nhưng khi trích xuất trả “video is not available”; không suy đoán nguyên nhân.
- [The School of Athens by Raphael](https://www.youtube.com/watch?v=9x0tsuS4dk0): chọn tập thứ hai để đối chiếu một bố cục nhiều nhân vật với bức phong cảnh của Van Gogh. Đây là mẫu có chủ đích, không đại diện thống kê cho toàn kênh. Metadata `yt-dlp` giới hạn 25 video mới và ba kết quả tìm kiếm, không crawl toàn kênh.
- Tải lần lượt bằng `yt-dlp --ignore-config --no-cookies`, không retry, giới hạn chiều cao 720; cả hai thành công, không gặp 429. `ffprobe` cho thấy cả hai 1280×720, 30000/1001 fps, đều có audio. Video Starry 1.213,679 s / audio 1.213,701 s; Raphael video 1.437,403 s / audio 1.437,421 s. Một số nguồn web bên thứ ba ghi Raphael 25:12–25:13, khác file đo được 23:57,421; không rõ nguyên nhân hoặc có phải phiên bản khác.
- Groq `whisper-large-v3`, ngôn ngữ `en`, chia đoạn mặc định 10 phút, tạo đủ TXT, SRT, JSON cho từng file. Những nhận định về nội dung lời kể dưới đây dựa trên **transcript ASR của audio trong bản tải**, không phải bản chép web. Đây chưa phải transcript được con người nghe kiểm chính tả từng câu: ví dụ ASR viết “screened” ở khoảng 01:01, có thể là lỗi nhận dạng. Các mốc câu chỉ xấp xỉ theo segment; không dùng những câu chưa kiểm âm làm trích dẫn nguyên văn. Lời kể là lập luận của video, không tự chứng minh các chi tiết lịch sử là đúng.
- Đã trực tiếp xem ảnh bằng `view_image`: overview mỗi 60 giây (21 và 24 ảnh), 00:00–01:25 mỗi 5 giây (18 ảnh/video), thêm ba đoạn 10 ảnh mỗi giây và một số đoạn dày gần 30 ảnh/giây. Các nhãn là thời điểm seek bằng ffmpeg, không phải PTS ghi trực tiếp; frame lấy tại hoặc ngay sau mốc, xấp xỉ một frame (~0,033 s), và tìm theo mốc 1/30 s không đảm bảo bao phủ từng frame nguồn 30000/1001 fps. Sheet là mẫu, không phải xem thủ công toàn bộ video. Khung đen trong các ô cuối là khoảng trống lưới, không phải cảnh phim. `ffprobe` lưu manifest timestamp từng frame; ffmpeg quét scene score toàn video như phần đo bên dưới. Các ví dụ là quan sát ảnh tĩnh theo thời gian, không khẳng định đã nghe hoặc xem toàn bộ theo thời gian thực.
- Tài liệu và media chỉ lưu để nghiên cứu cục bộ; không tải lại nội dung lên nơi khác.

## Hook và cấu trúc

### Starry Night

Khung 00:00 là quảng bá sách; không coi nó là hook của câu chuyện. Lời ASR mở bằng ngày Van Gogh vào cơ sở ở Saint-Rémy (00:00–00:22); ảnh mẫu từ 00:10–00:25 ghép cảnh địa điểm hiện nay với bức tranh cùng mô-típ. Khoảng 00:30 là footage Marseille, 00:35–00:45 đối chiếu tác phẩm/phong cảnh và địa điểm. Cách mở tạo câu hỏi phản thực: điều kiện ở một cơ sở nhỏ ảnh hưởng thế nào đến khả năng làm việc của ông; sau đó đưa năng suất và ngày vẽ tác phẩm vào khoảng 01:13–01:36. Mẫu ảnh cho thấy dựng theo câu chuyện và đối chiếu, không chỉ đưa bức tranh chính lên ngay đầu.

Lộ trình luận điểm theo ASR: khoảng 01:50 nêu hình tượng “nghệ sĩ điên” trong văn hóa đại chúng; các phần tiếp theo đưa hoàn cảnh, ảnh hưởng hội họa và đối chiếu nguồn thị giác; khoảng 10:00 bàn bầu trời như hình dung giàu cảm xúc; khoảng 10:38 chuyển sang quan hệ phong cảnh thực và các tranh nhìn qua cửa sổ; khoảng 13:12 chuyển sang kỹ thuật sơn; về cuối xem xét thiên văn và ý nghĩa tinh thần. 19:10–20:04 kết lại bằng lập luận: giá trị của tranh nằm ở khả năng chuyển trải nghiệm cá nhân thành điều người khác có thể nhận ra, thay vì chỉ kể thiên tài qua bệnh lý. Ảnh mẫu 20:00 đưa tranh trở lại bối cảnh phòng trưng bày. Đây là diễn giải cấu trúc, không phải xác minh y khoa hay lịch sử độc lập.

### School of Athens

Ở 00:00 ảnh mẫu đen; 00:05–00:10 là toàn cảnh Vatican. ASR mở bằng hai nghệ sĩ làm việc gần nhau trong Vatican, rồi so sánh Michelangelo với Raphael về đề tài và tính cách (đến khoảng 01:14). Khoảng 01:14–01:35 xem bố cục như sân khấu, đồng thời mở chuyện chân dung Michelangelo trong vai Heraclitus. Lời hứa kể chuyện không chỉ là nhận diện nhân vật, mà là giải thích quan hệ giữa đối lập và hòa hợp.

Các mốc gần đúng trong ASR: khoảng 04:00 đưa nghệ sĩ vào cộng đồng các nhà tư tưởng; 05:48–08:08 mở rộng sang đối thoại giữa niềm tin và lý trí trong không gian Vatican; 10:00–12:00 đọc kiến trúc và phối cảnh; 12:00–19:00 đi qua các nhóm triết gia; khoảng 20:00 nói về sửa fresco và Heraclitus; 21:50 trở đi quay về phép thống nhất đối lập. Kết 23:04–23:51 kết nối sự khác biệt, tính phức tạp và tư tưởng Phục Hưng. Đây là một tuyến luận điểm quay về hình tượng được đặt ra lúc mở đầu, không phải danh sách các chi tiết rời.

## Lời kể và nhịp

Đếm regex token từ trường `segments[].text` của JSON, tính cả phần không thuộc câu chuyện nếu ASR nhận ra, chia cho **toàn bộ thời lượng container**: Starry 2.841 từ / 20,228 phút ≈ **140,4 từ/phút**; Raphael 3.170 / 23,957 phút ≈ **132,3 từ/phút**. Đây là tốc độ trung bình toàn file, bao gồm khoảng lặng và có sai số ASR/tokenization; không phải tốc độ phát âm khi đang nói, không chứng minh nhịp từng đoạn, và không đo giọng, âm nhạc hay cảm xúc. Các câu kéo qua nhiều hình và hình được giữ đủ lâu để hỗ trợ một ý; không có căn cứ để áp một mục tiêu motion của Shorts vào phim này.

## Bằng chứng hình ảnh và dựng

| Mốc | Đã quan sát trực tiếp | Vai trò trong lập luận / giới hạn |
|---|---|---|
| Starry 00:10–00:25 | Hình cơ sở thực và tranh đặt cạnh nhau, nhãn nhỏ nhận diện tư liệu. | So sánh cùng địa điểm thay vì minh họa chung. Các mẫu 5 giây không xác định chính xác điểm cut. |
| Starry 00:55, 01:20–01:25 | Cửa sổ thật bên tranh; sau đó lưới 2×2 các đoạn phim/diễn xuất, có credit. | Từ bối cảnh thực đến những hình ảnh điện ảnh về nghệ sĩ; không suy ra giấy phép cho asset. |
| Starry 10:33–10:42 | Cận nét sơn → tiêu đề chương trên hình mờ → lưới bốn phong cảnh với đường chéo trắng xuất hiện từ khoảng 10:39. | ASR 10:37–10:45 nói về đường chéo của dãy đồi. Đường là annotation phục vụ so sánh nhiều ảnh; tại 10:37 chưa thể kết luận máy quay đang chỉ cây bách. [Sheet](../../../research_media/great-art-explained/crCPVoPsTtk_tree.jpg). |
| Starry 13:08–13:17 | Tranh → tiêu đề “Techniques” trên hai ảnh làm mờ → chia đôi chi tiết nét sơn và video bàn tay/cọ. | ASR 13:12–13:23 nói impasto và cách đặt sơn; hình ghép cho thấy ví dụ kỹ thuật cạnh bề mặt tác phẩm. Mẫu dày 13:09,5–13:10,47 cho thấy chữ tiêu đề hiện dần trên nền mờ. [Sheet kỹ thuật](../../../research_media/great-art-explained/crCPVoPsTtk_impasto.jpg), [sheet dày](../../../research_media/great-art-explained/crCPVoPsTtk_chapter_transition.jpg). |
| Raphael 01:24–01:24,97 | Nền kiến trúc còn trống; cặp nhân vật trung tâm dần hiện lên, rồi bắt đầu có thêm nhân vật. Đã xem 30 ảnh seek cách nhau 1/30 s. | Bằng chứng về compositing và độ mờ theo thời gian trong hình xuất; không biết họ dùng mask, phần mềm hay quy trình nào. [Sheet](../../../research_media/great-art-explained/9x0tsuS4dk0_figure_transition.jpg). |
| Raphael 11:16–11:25 | Giữ toàn bố cục với các đường trắng hội tụ ở vùng trung tâm. | ASR 11:19–11:26 nói phối cảnh một điểm dẫn mắt đến Plato và Aristotle; đường kẻ biến hình thức thành luận cứ trực quan. [Sheet](../../../research_media/great-art-explained/9x0tsuS4dk0_perspective.jpg). |
| Raphael 13:00–19:00 | Overview chuyển giữa toàn tranh, các crop nhân vật và tranh liên quan; 20:00 có hình minh họa thao tác bề mặt. | Thay đổi quy mô đọc từ tập thể tới chi tiết; mẫu thưa không đủ để xác định mọi cut hoặc thời lượng từng hold. |

Các mẫu mở đầu cho thấy có cả footage, tranh toàn cảnh, crop, split-screen, nền đen, caption nguồn và các lớp đồ họa. Ở một vài đoạn ảnh gần nhau rất giống nhau, trong khi nội dung chi tiết hoặc opacity thay đổi dần; đó là bằng chứng của giữ bố cục và chuyển lớp trong phạm vi đã mẫu, không phải bằng chứng toàn video có shot length hay tốc độ zoom cụ thể. Sự có mặt của các nhân vật đã tách khỏi nền được quan sát ở đầu Raphael; phương pháp tách và công cụ thực hiện không thể suy ra từ thành phẩm.

Về năng lực biên tập có thể rút ra từ mẫu: cần cho phép đối chiếu nhiều ảnh có nhãn, chọn vùng ảnh theo ý nghĩa lời kể, ghép footage vào bố cục, đặt đường chỉ dẫn và điều khiển xuất hiện của các lớp theo timeline. Đây là mô tả năng lực thể hiện trong video, **không phải kết luận rằng sản phẩm hiện tại hỗ trợ hay thiếu chúng**, vì nghiên cứu này không kiểm toán mã sản phẩm.

## Quét tự động toàn bộ frame

`ffprobe -show_entries frame=best_effort_timestamp_time,pkt_duration_time,key_frame` ghi **36.374** dòng frame Starry và **43.079** dòng Raphael, khớp `nb_frames` trong stream. Sau đó `ffmpeg` giải mã toàn video và dùng `select=gt(scene,0.35),showinfo`: thu được lần lượt **133** và **109** frame vượt ngưỡng scene score 0,35. Log lưu timestamp các ứng viên. Đây là số phát hiện của bộ lọc tại một ngưỡng, **không phải số cut biên tập**: dissolve chậm, pan, đổi lớp, footage chuyển động có thể bị bỏ sót hoặc kích hoạt sai; không suy ra shot length trung bình hay xác nhận từng chuyển cảnh bằng tay. Không dùng các con số này để suy đoán retention.

## Tài liệu nghiên cứu

- [Starry overview](../../../research_media/great-art-explained/crCPVoPsTtk_overview.jpg) và [90 giây đầu](../../../research_media/great-art-explained/crCPVoPsTtk_opening.jpg); [Raphael overview](../../../research_media/great-art-explained/9x0tsuS4dk0_overview.jpg) và [90 giây đầu](../../../research_media/great-art-explained/9x0tsuS4dk0_opening.jpg).
- Cùng thư mục media: `<id>.mp4`, `<id>.txt`, `<id>.srt`, `<id>.json`, `<id>_frames.csv` và `<id>_scenes.log`. JSON/SRT/TXT là đầu ra ASR, không phải bản được biên tập thủ công. Manifest là dữ liệu máy đọc, không chứng minh đã xem tay từng frame.
