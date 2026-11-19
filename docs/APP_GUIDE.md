# Hướng dẫn ứng dụng Behind the Image

Một ứng dụng duy nhất, một quy trình: chọn dự án, xem các bước theo thứ tự, làm một bước, duyệt, sang bước kế tiếp. Hướng dẫn này gộp hai hướng dẫn cũ (trang Kịch bản và trang Biên tập video) và mô tả cả thư viện sách.

## 1. Khởi động

```
cd /Users/nhanvu/Documents/code/behind-the-image
tools/run_editor.sh          # lần đầu tự tạo .venv và cài requirements.txt (cần ffmpeg)
```

Mở http://127.0.0.1:8560/ . Chỉ nghe trên 127.0.0.1, cổng 8560 (không dùng 8550). Kiểm tra `http://127.0.0.1:8560/api/health`: phải thấy `engine: real` và `media: real`. Nếu thấy `stub` thì khung hình/hình ảnh chỉ là giả để thử. Huy hiệu tình trạng này luôn hiện ở góc phải thanh trên cùng.

- `projects/arnolfini/` và `projects/technique_lab/` là bản gốc, được bảo vệ (không xóa được). Để sửa thử hãy dùng bản sao `projects/arnolfini_edit/`.
- `?mock=1` chạy ứng dụng với dữ liệu giả, không cần server; chỉ bước Dựng hình dùng được trong chế độ này.
- `?all=1` hiện thêm các dự án `lab_*` và `demo_*` (mặc định bị ẩn).
- Đổi thư mục dự án (để thử mà không đụng dữ liệu thật): đặt biến `BTI_PROJECTS_ROOT` trước khi chạy `tools/run_editor.sh`.

## 2. Khung ứng dụng

Khung nằm cố định trên cùng, bên dưới là **một màn hình tại một thời điểm**.

| Phần | Việc |
|---|---|
| **Behind the Image** | Bấm để về trang chủ (danh sách dự án). |
| **Ô chọn dự án** | Chuyển sang dự án khác; mở dự án ở bước mà giai đoạn của nó cần làm tiếp. |
| **Tên dự án, tên tác phẩm, giai đoạn** | Dự án đang mở. |
| **Dòng trạng thái** | "đang lưu...", "đang mở dự án..." và các thông báo ngắn. Thông báo nổi hiện ở góc dưới phải; hộp thoại hiện giữa màn hình. Chỉ có một hệ thống thông báo cho cả ứng dụng. |
| **Cài đặt** | Hộp "Cài đặt": agent mặc định cho dự án mới, và dưới mục "Nâng cao" là bảng mô hình cho từng việc (xem "Chọn agent" dưới đây và mục 7, "Cài đặt"). |
| **+ Tạo video mới** | Đi tới thư viện để chọn tác phẩm. |
| **Huy hiệu engine/media** | Tình trạng backend. |
| **Thanh các bước** | Sáu bước của dự án, xem mục 3. |

### Địa chỉ (để tải lại trang và dùng nút Quay lại)

| Địa chỉ | Màn hình |
|---|---|
| `/#/` | Trang chủ: danh sách dự án |
| `/#/library`, `/#/library/books`, `/#/library/book/<sách>`, `/#/library/work/<sách>/<số>`, `/#/library/artwork/<mã>` | Thư viện: tác phẩm, kệ sách, các mục của một sách, một mục, hồ sơ một tác phẩm |
| `/#/project/<id>` | Mở dự án ở bước mà giai đoạn của nó cần làm tiếp |
| `/#/project/<id>/<bước>` | Một bước: `artwork`, `script`, `voice`, `picks`, `edit`, `export` |

Các địa chỉ cũ vẫn dùng được và tự chuyển vào ứng dụng: `/library.html` (kèm `#/books`, `#/artwork/<mã>`, `#/book/<id>`, `#/work/<sách>/<số>`; `#/projects` nay là trang chủ), `/script.html?project=<id>` (sang bước Kịch bản) và `/?project=<id>` (sang bước Dựng hình). `?mock=1` và `?all=1` được giữ nguyên.

### Chọn agent

Mọi bước gọi mô hình (bước 2 Kịch bản, bước 5 Dựng hình) có **cùng một ô chọn agent**: `Agent: [Gemini 3.8 Flash]`. Có hai agent, mỗi cái chạy bằng chương trình của chính hãng theo gói đăng ký của bạn:

- **Gemini 3.8 Flash** chạy bằng Antigravity CLI (`agy`, mục 5.4).
- **Opus 5.5 High** chạy bằng Claude Code (`claude`, mục 5.4b).

Ô chọn luôn hiện agent **sẽ được dùng** cho bước này của dự án này. Đổi ô chọn là đổi ngay, không hỏi lại, và chỉ đổi cho **bước này của dự án này**. Dòng nhỏ dưới ô cho biết giá trị đến từ đâu:

| Dòng dưới ô | Nghĩa |
|---|---|
| **Riêng cho bước này** (kèm liên kết **Dùng cho cả dự án**) | Bạn đã chọn agent cho riêng bước này. |
| **Theo dự án** | Dự án có một agent chung, mọi bước dùng nó. |
| **Theo mặc định** | Dự án chưa chọn gì: dùng agent mặc định trong **Cài đặt** (mặc định ban đầu là Gemini 3.8 Flash). |

**Dùng cho cả dự án** biến agent đang chọn thành agent của cả dự án và bỏ các lựa chọn riêng từng bước, nên các bước sau dùng nó mà bạn không phải chọn lại. Lựa chọn được nhớ theo dự án (tệp `projects/<mã dự án>/agent.json`), tải lại trang vẫn còn, dự án khác không bị ảnh hưởng. Agent mặc định cho dự án mới đặt trong **Cài đặt** (ô "Agent mặc định cho dự án mới", lưu vào `run/settings.json`).

Một agent chưa dùng được (ví dụ "Claude Code trên máy chủ chưa đăng nhập") vẫn hiện trong ô chọn, ghi "(chưa dùng được)"; chọn nó thì dòng dưới ô nói lý do, và bấm chạy sẽ báo lý do đó bằng tiếng Việt. Việc kiểm tra này không gọi mô hình.

**Khi agent hết hạn mức**, thông báo nêu tên agent và giờ mở lại, ví dụ "Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút.", kèm **đúng một nút**: "Chuyển sang Gemini 3.8 Flash và chạy lại". Nút này lưu agent kia làm lựa chọn của bước này rồi chạy lại đúng yêu cầu vừa rồi. Hệ thống **không bao giờ tự đổi agent**. Thông báo này hiện ở hộp thoại của bước Kịch bản, ở khung Bản nháp và ở thẻ lần sửa bằng lời của bước Dựng hình.

Thứ tự quyết định agent cho một lần chạy: mô hình do yêu cầu nêu rõ (dành cho thử nghiệm và công cụ ngoài; trang không gửi mô hình) → lựa chọn riêng của bước → agent của dự án → agent mặc định trong Cài đặt → bảng mô hình cho từng việc ("Nâng cao"). Kết quả và nhật ký công việc ghi tên agent (nhãn, không phải mã mô hình).

## 3. Trang chủ và các bước

**Trang chủ** liệt kê mọi dự án: tên, mã, tác phẩm, giai đoạn, thanh năm sáu ô tiến độ, bước kế tiếp và nút **Tiếp tục** (mở dự án ở bước kế tiếp). Nút **+ Tạo video mới** dẫn tới thư viện. Nút **Xóa** xóa cả thư mục dự án: phải gõ đúng mã dự án để xác nhận, không khôi phục được. Hai dự án gốc `arnolfini` và `technique_lab` hiện nhãn "được bảo vệ" và máy chủ từ chối xóa chúng (HTTP 403).

**Các bước**, theo thứ tự:

| Bước | Màn hình |
|---|---|
| 1. Tác phẩm | Hồ sơ của tác phẩm đã chọn và các nguồn sách đang dùng. Với video mới, đây là thư viện: tác phẩm, kệ sách, hồ sơ, tạo dự án. |
| 2. Kịch bản | Nguồn, dàn ý, lời dẫn. |
| 3. Giọng đọc | Máy đọc lời dẫn đã duyệt thành tệp âm thanh và đo thời điểm từng từ (mục 6). |
| 4. Chọn hình | Chọn tranh chính, vùng chi tiết và hình cho từng dòng lời dẫn (mục 6). |
| 5. Dựng hình | Dựng bản nháp storyboard rồi sửa trong trình biên tập (mục 7). |
| 6. Xuất video | Máy dựng video hoàn chỉnh, mô tả và mục lục (mục 9). |

Mỗi bước trên thanh các bước có một trạng thái, do máy chủ tính (`GET /api/projects/<id>/pipeline`):

| Trạng thái | Nghĩa là gì |
|---|---|
| **Xong** (dấu tích xanh) | Bước đã hoàn thành (ví dụ lời dẫn đã duyệt và còn khớp, storyboard đã duyệt). |
| **Hiện tại** | Bước mà giai đoạn của dự án cần làm tiếp. Mở dự án là vào thẳng bước này. |
| **Mở được** | Bước mở được nhưng chưa phải bước kế tiếp. |
| **Khóa** | Chưa mở được. Rê chuột hoặc bấm vào bước sẽ thấy lý do (ví dụ "Cần duyệt lời dẫn ở bước Kịch bản trước"). |
| **Không có dữ liệu** | Dự án nhập từ bản dựng trước, không có dữ liệu cho bước này (mục 9). |

**Thứ tự mở bước.** Bước 3 (Giọng đọc) và bước 4 (Chọn hình) cùng mở khi lời dẫn đã duyệt; làm cái nào trước cũng được, hoặc làm cùng lúc (máy đọc mất chừng 50 phút trong khi bạn chọn hình). Bước 5 mở khi cả hai đã xong: lúc đó nó cho dựng bản nháp storyboard. Bước 6 mở khi storyboard đã duyệt và còn khớp. Giai đoạn của dự án là bước xa nhất mà mọi bước trước nó đều xong: *Đã chọn tác phẩm*, *Có kịch bản*, *Có giọng đọc*, *Đã chọn hình*, *Có storyboard*, *Đã duyệt storyboard*, *Đã dựng xong*. Dự án nhập từ bản dựng trước (mục 9) không có bước 1 đến 4 nhưng có storyboard, nên vẫn mở bước 5 và, sau khi duyệt, bước 6.

Bước đang mở được gạch chân màu xanh. Bước mà giai đoạn của dự án cần làm tiếp có dấu "Hiện tại". Bước giọng đọc, chọn hình, bản nháp hoặc xuất video đang chạy hiện "Đang chạy"; bước đã xong nhưng dữ liệu đã đổi sau đó hiện "Cần làm lại". Sau khi duyệt xong một bước, nút **Tiếp tục: <tên bước>** dẫn tới bước kế tiếp mở được (bước khóa bị bỏ qua). Nút này có ở bước Kịch bản (sau khi lời dẫn đã duyệt), bước Dựng hình (sau khi storyboard đã duyệt), và ở cuối các màn hình thông báo.

## 4. Bước 1: Tác phẩm và thư viện

Với video mới, bấm **+ Tạo video mới**. Thư viện có hai thẻ:

- **Tác phẩm**: mỗi tác phẩm là một video; các sách cùng nói về một tranh đã được gộp vào một hồ sơ. Lọc theo tên, thế kỷ, đã có dự án chưa, có trong từ 2 sách, có gồm chương chủ đề hay không. Bản quyền chỉ là thông tin ước lượng, không chặn gì.
- **Kệ sách**: chọn một cuốn, xem các mục của nó (lọc theo tên, thế kỷ, bản quyền), mở một mục để xem các trang, văn bản trích (bản scan là văn bản OCR, có thể sai chữ), hình nhúng, và các sách khác có cùng tác phẩm.

Bấm một tác phẩm để mở **hồ sơ**: tên, hoạ sĩ, năm (chỗ các sách ghi khác nhau được tô vàng), nguồn của từng sách (dàn ý theo cấu trúc, chú thích hình, các trang, văn bản thân bài). Sách dịch máy có nhãn "bản dịch máy, không dùng làm nguồn sự kiện". Một tác phẩm của sách dịch máy đã được khôi phục và rà soát thì có nhãn **"Bản khôi phục"** thay cho nhãn đó: dùng được cho ý tưởng và mô tả bức tranh (lời dẫn sẽ nói "Kelly Grovier cho rằng…"), nhưng **không bảo đảm** số liệu, năm và trích dẫn; những thứ đó phải có một nguồn khác xác nhận, và dấu […] là chỗ chưa khôi phục được nên bị bỏ trống. Nếu tác phẩm chưa có nguồn tin cậy đầy đủ nào (chỉ có bản khôi phục hoặc bản dịch máy), trang ghi "Chưa có nguồn tin cậy đầy đủ cho tác phẩm này." và mọi dữ kiện cần kiểm tra thêm. Ở hồ sơ có thể **Gộp với…** một tác phẩm khác thực ra là cùng một bức tranh, hoặc **Tách** một nguồn thành tác phẩm riêng (ghi vào `library/overrides/artworks.json`).

**Tạo dự án**: bấm "Tạo dự án", bỏ tick những nguồn không muốn dùng (mặc định bỏ sách dịch máy chưa khôi phục nếu còn nguồn khác; bản khôi phục được giữ), có thể đặt tên thư mục (slug: a-z, 0-9, `-`, `_`; không được bắt đầu bằng `lab_` hoặc `demo_`). Dự án nhận một bản sao hồ sơ và văn bản; chưa có storyboard. Tạo xong ứng dụng mở dự án ở bước Kịch bản.

Với dự án đã có, bước **Tác phẩm** hiện hồ sơ tác phẩm của dự án: tên, hoạ sĩ, năm, các nguồn không thống nhất, các chi tiết có tên, và từng nguồn sách đang dùng (xem văn bản, mở mục trong thư viện). Chọn sách nào làm nguồn thì chỉnh ở bước Kịch bản, cột Nguồn.

## 5. Bước 2: Kịch bản (dàn ý và lời dẫn)

Bước này biến một tác phẩm đã chọn thành lời dẫn đã duyệt. Có hai giai đoạn, và bạn duyệt cả hai:

1. **Dàn ý**: một mô hình đọc các đoạn sách đã đánh số, rồi viết câu hỏi chính, ba câu mở đầu, bảng dữ kiện (mỗi dữ kiện dẫn mã đoạn sách, có độ chắc chắn và mâu thuẫn giữa các sách) và danh sách chương kèm số từ. Bạn sửa rồi **Duyệt dàn ý**.
2. **Lời dẫn**: mô hình viết từng chương theo dàn ý đã duyệt. Bạn sửa, cắt, tách, gộp rồi **Duyệt lời dẫn**.

Có hai đường làm, cùng dùng một prompt và một bộ đọc, nên kết quả giống nhau:

- **Nút bấm**: chọn agent ở ô "Agent" (xem "Chọn agent" ở mục 2), bấm "Lập dàn ý" rồi "Viết lời dẫn".
- **Sao chép và dán**: bấm "Sao chép prompt", dán vào Gemini, rồi dán nguyên câu trả lời vào nút "Dán".

Tác vụ mô hình chạy trên máy chủ nên vẫn chạy khi bạn rời bước này; quay lại sẽ thấy tiến độ và kết quả.

### 5.1 Màn hình

Ba cột và một thanh trạng thái.

| Cột | Nội dung |
|---|---|
| **Nguồn** (trái) | Thẻ tác phẩm, mục tiêu số từ và tốc độ đọc, các chi tiết có tên (D1, D2, ...), chỗ các sách không thống nhất, một thẻ cho mỗi sách với các đoạn đã đánh số (`PAY-07`, `HOD-02`, ...), ô tìm kiếm. Sách dịch máy có nhãn "bản dịch máy, không dùng làm nguồn sự kiện" và một ô tick để cho phép dùng; bản khôi phục có nhãn "Bản khôi phục", được dùng sẵn (bỏ tick nếu không muốn). |
| **Dàn ý** (giữa) | Câu hỏi chính, chọn một trong các câu mở đầu, các chương (tên, vai trò, thẻ chương, số từ, mục đích, dữ kiện, cho xem), bảng dữ kiện (độ chắc chắn, mã đoạn nguồn, mâu thuẫn). |
| **Lời dẫn** (phải) | Các chương, mỗi chương gồm nhiều dòng (beat). Mỗi dòng là một đoạn lời đọc, sửa trực tiếp được. |
| **Thanh dưới** | Tổng số từ, số phút ước tính, thanh ngân sách từng chương, tiến độ của tác vụ đang chạy kèm nút Hủy. |

Bấm vào mã dữ kiện (`f03`) hoặc mã đoạn nguồn (`PAY-07`) ở cột giữa hoặc cột phải: đoạn sách tương ứng sáng lên ở cột trái.

#### Thanh công cụ của bước

| Nút | Việc làm |
|---|---|
| Ô **Agent** | Agent dùng cho hai nút "Lập dàn ý" và "Viết lời dẫn" của dự án này, kèm dòng "Riêng cho bước này / Theo dự án / Theo mặc định" và liên kết "Dùng cho cả dự án". Agent chưa dùng được vẫn hiện, ghi "(chưa dùng được)", chọn vào sẽ có lời giải thích. (Dự án chọn ở thanh trên cùng của ứng dụng.) Dòng "Nguồn dàn ý" và "Nguồn lời dẫn" ở cuối mỗi cột ghi tên agent đã viết. |
| **Lập dàn ý** | Mô hình viết dàn ý. Có ô ghi chú để dặn thêm. Dàn ý cũ được giữ ở `outline.prev.json`. |
| **Viết lời dẫn** | Mô hình viết lời dẫn từng chương, cần dàn ý đã duyệt. Mỗi chương xong là được lưu ngay. |
| **Sao chép prompt** | Mở hộp chứa prompt đầy đủ (dàn ý, hoặc lời dẫn cho tất cả hoặc một chương) trong ô văn bản luôn bôi đen được, kèm nút Sao chép. Nếu trình duyệt chặn bộ nhớ tạm, bấm Ctrl+C (Cmd+C) trên phần đã bôi đen. |
| **Dán** | Dán câu trả lời của mô hình. Hộp có hai thẻ: dàn ý, lời dẫn. |
| **Lưu** (Ctrl+S) | Lưu. Có kiểm tra phiên bản: nếu tệp đã đổi ở nơi khác, trang báo và không ghi đè. |
| **Hoàn tác, Làm lại** | Theo cột bạn vừa sửa. |
| **Kiểm tra (n)** | Danh sách lỗi, cảnh báo, thông tin (xem mục 5.5). |
| **Duyệt** | Duyệt dàn ý nếu dàn ý chưa duyệt, ngược lại duyệt lời dẫn. Chỉ duyệt khi đã lưu và không còn lỗi. Khi lời dẫn đã duyệt, nút **Tiếp tục** ở góc phải thanh công cụ mở bước kế tiếp. |

**Mọi chỉnh sửa làm mất dấu duyệt.** Dấu duyệt gắn với mã băm (sha1) của đúng nội dung đã duyệt. Sửa một chữ là phải duyệt lại. Nếu bạn sửa dàn ý sau khi đã duyệt lời dẫn, lời dẫn vẫn giữ dấu duyệt của nó, nhưng không thể duyệt lại nó cho tới khi dàn ý được duyệt lại ("Dàn ý đã đổi sau khi duyệt").

### 5.2 Đường 1: dùng nút bấm

1. Chọn agent ở ô "Agent" (mặc định là Gemini 3.8 Flash qua Antigravity CLI, hoặc agent đặt trong Cài đặt). Muốn thử mà không tốn hạn mức, xem mục 5.7.
2. **Lập dàn ý**. Đọc, sửa, đặc biệt: câu hỏi chính, chọn câu mở, bảng dữ kiện (kiểm tra các mã nguồn), ngân sách từ của chương. Chỗ nào các sách mâu thuẫn, mô hình phải ghi ở cột "Mâu thuẫn"; bạn là người quyết định, hệ thống không tự chọn.
3. Lưu, **Duyệt dàn ý**.
4. **Viết lời dẫn**. Thanh dưới hiện từng chương: xanh dương đang chạy, xanh lá xong, đỏ lỗi. Chương nào không qua kiểm tra (có ký hiệu trong lời đọc, dòng trống, thiếu chương) được mô hình viết lại một lần, kèm thông báo lỗi của bộ kiểm tra. Nếu vẫn lỗi, tác vụ dừng, các chương đã xong được giữ, câu trả lời lỗi nằm ở ô "Dán".
5. Sửa lời dẫn:
   - sửa chữ trực tiếp trong ô;
   - **Tách**: đặt con trỏ vào giữa dòng rồi bấm Tách (dòng mới có mã mới);
   - **Gộp lên**: nối với dòng phía trên;
   - **Bỏ**: bỏ dòng (mã không bao giờ được dùng lại);
   - **Chèn dưới**, hoặc "+ Dòng" ở đầu chương;
   - ↑ ↓: chuyển dòng, kể cả sang chương bên cạnh;
   - **khóa**: dòng khóa không sửa, không bị viết lại;
   - **Viết lại chương**: mô hình viết lại một chương với ghi chú của bạn (ví dụ "ngắn hơn, bớt tiểu sử"). Các chương khác không đổi. Chương có dòng khóa sẽ hỏi trước khi thay.
6. Xem "Kiểm tra". Hết lỗi thì **Duyệt lời dẫn**. Dự án chuyển sang giai đoạn "Có kịch bản".

Nếu agent hết hạn mức, hộp thoại nêu tên agent và giờ mở lại, kèm một nút "Chuyển sang <agent kia> và chạy lại" (xem "Chọn agent" ở mục 2). Hệ thống **không tự đổi agent**. Nếu mô hình chỉ hết thời gian, trang báo bằng một thông báo và bạn bấm chạy lại. Chương đã viết xong vẫn còn.

### 5.3 Đường 2: sao chép và dán

1. **Sao chép prompt**, thẻ "Prompt dàn ý". Dán vào Gemini hoặc chat bất kỳ (prompt đã bảo mô hình chỉ dùng các đoạn sách).
2. Dán nguyên câu trả lời vào **Dán**, thẻ "Dán dàn ý", bấm "Phân tích và lưu". Không cần cắt bỏ phần mở đầu, danh sách câu mở hay bảng kiểm tra: bộ đọc lấy phần sau dòng `OUTLINE` cuối cùng.
3. Sửa, duyệt dàn ý như ở trên.
4. **Sao chép prompt**, thẻ "Prompt lời dẫn" (tất cả chương, hoặc chọn một chương). Dán vào Gemini, lấy câu trả lời, dán vào thẻ "Dán lời dẫn". Hộp có ô "Chỉ thay các chương có trong bản dán" để thay một chương mà giữ các chương khác.

**Bản dán bị lỗi.** Nếu bộ đọc không đặt được văn bản vào dàn ý, **không có gì bị ghi**. Hộp hiện danh sách từng đoạn đã thấy: số thứ tự, số từ, 70 ký tự đầu, và chương mà đoạn đó nằm dưới. Nhìn danh sách là biết đoạn nào lạc chỗ. Văn bản vừa dán được **giữ lại** (`script/last_paste.txt` cho lời dẫn, `script/last_paste_outline.txt` cho dàn ý) và hiện lại trong ô Dán khi tải lại trang. Sửa tại chỗ rồi bấm lại.

#### Cách bộ đọc hiểu văn bản (để biết nó bỏ qua gì)

- Lời dẫn: lấy phần sau dòng `FINAL SCRIPT` cuối cùng (không có thì lấy hết). Bỏ: hàng rào mã, danh sách câu mở, bảng, dòng đếm từ, các khối "Fact trace", "Audit", "Notes", "Sources"... (một khối như vậy sau lời dẫn kết thúc phần đọc). Dòng `## c02 TÊN CHƯƠNG` mở một chương, khớp với dàn ý theo mã, rồi theo tên (và theo thứ tự nếu bản dán không ghi mã). Mỗi đoạn là một dòng (beat). Dòng `>> facts: f03, f07 | show: cái gương; chữ phía trên` sau đoạn là thông tin phụ, không bắt buộc. Mã dữ kiện lạ được báo nhưng không làm hỏng việc đọc.
- Dàn ý: lấy phần sau dòng `OUTLINE` cuối cùng. Các nhãn: `THESIS:`, `HOOKS` (`h1: ...`), `HOOK CHOICE:`, `FACTS` (mỗi dòng `f01 | established | PAY-07, HOD-02 | câu khẳng định | conflict: ...`), `CHAPTERS` (mỗi chương `## c01 TÊN` rồi `ROLE:`, `CARD:`, `BUDGET:`, `PURPOSE:`, `FACTS:`, `SHOW:`), `TARGET WORDS:`.

### 5.4 Mô hình: Antigravity CLI là mặc định

Mặc định, máy chủ chạy **Antigravity CLI** (`agy`) ở chế độ không giao diện, theo gói đăng ký của bạn. **Không cần khóa API.**

**Chuẩn bị một lần:** chạy lệnh `agy` trong Terminal và đăng nhập Google. Sau đó tải lại trang. Nếu `agy` chưa cài hoặc chưa đăng nhập, agent Gemini 3.8 Flash ghi "(chưa dùng được)" kèm lời nhắc chạy `agy` một lần trong Terminal.

**Danh sách mô hình** lấy từ lệnh `agy models` (nhớ trong khoảng 10 phút), hiện thành `Antigravity CLI: <tên>`, mô hình mặc định của CLI đứng đầu. Hiện có: Gemini 3.8 Flash (High, Medium, Low), Claude Sonnet 4.6, Claude Opus 4.6, GPT-OSS 120B. Mỗi lần chạy tốn hạn mức của gói đăng ký.

**Cách chạy (để bạn yên tâm):** mỗi lần gọi là một tiến trình `agy -p "<prompt>" --output-format json --sandbox --disable-slash-commands --settings {...}`:
- chạy trong một thư mục tạm **trống**, nằm ngoài dự án, xóa sau khi xong, nên `agy` không thấy và không đụng được tệp nào của dự án;
- chế độ quyền nghiêm nhất (`toolPermission: strict`, không ra ngoài thư mục làm việc, sandbox terminal), và không bao giờ dùng `--dangerously-skip-permissions`;
- prompt dặn trả lời thẳng bằng chữ, không dùng công cụ, viết tiếng Anh dù có quy tắc nào khác (ví dụ "luôn trả lời tiếng Việt") và đúng bố cục;
- kiểm tra kết quả: trạng thái phải là SUCCESS, đúng 1 lượt, không có thông báo bị từ chối công cụ, thư mục tạm vẫn trống. Có dấu hiệu dùng công cụ thì **bỏ kết quả** và báo lỗi.
- mỗi lúc chỉ một lần gọi `agy`. Nút Hủy kết thúc cả nhóm tiến trình. Giới hạn mỗi lần gọi 15 phút (`timeout` trong `config/models.json`), mỗi tác vụ tối đa 30 phút.

Lỗi thường gặp (thông báo hiện tiếng Việt): chưa đăng nhập (chạy `agy` một lần trong Terminal), hết hạn mức của gói (đợi hoặc đổi mô hình), tên mô hình lạ (tải lại trang), quá thời gian.

**Hệ thống không bao giờ tự chuyển sang API trả tiền.** Muốn dùng thì chọn tay:

| Mô hình | Cần |
|---|---|
| Antigravity CLI | `agy` đã cài và đăng nhập |
| Claude qua OpenRouter (**trả tiền theo token**) | biến `OPENROUTER_API_KEY` |
| Mock | không cần |

Mã của nhà cung cấp Gemini API vẫn còn trong dự án nhưng không có trong danh sách. Muốn dùng, thêm lại một dòng `provider: "gemini"` với `key_env: "GEMINI_API_KEY"` vào `config/models.json`.

**Tệp `.env`** (có thể dùng chung với dự án truyện tranh): trang chỉ đọc đúng ba biến `OPENROUTER_API_KEY`, `YDC_API_KEY`, `GEMINI_API_KEY`. Mọi dòng khác (đường dẫn ffmpeg, TTS, danh sách mô hình...) bị bỏ qua và không được đưa vào tiến trình. Khóa không bao giờ xuất hiện trong nhật ký hay câu trả lời của máy chủ. Sửa `.env` thì chỉ cần tải lại trang.

Thêm một mô hình OpenRouter: thêm một dòng vào `config/models.json`, ví dụ `{"id": "or-x", "label": "X (trả tiền)", "provider": "openrouter", "model": "tên/trên-OpenRouter", "key_env": "OPENROUTER_API_KEY", "timeout": 300}`. Mô hình của Antigravity không cần thêm tay, chúng tự hiện từ `agy models`.

### 5.4b Bộ chạy thứ hai: Claude Code (`claude`)

Có hai bộ chạy, mỗi bộ chạy bằng chương trình của chính hãng, theo gói đăng ký của bạn: Gemini 3.8 Flash chạy bằng **Antigravity CLI** (`agy`, mục 5.4), Opus 5.5 High chạy bằng **Claude Code** (`claude`). Mô hình của Claude Code có mã dạng `claude:<mô hình>@<mức nỗ lực>`, hiện có một dòng trong danh sách: `claude:claude-opus-5-5@high`, hiện là **Claude Code: Opus 5.5 High**. Dùng được ở mọi chỗ dùng được mã `agy:` (kịch bản, sửa nhanh, dựng storyboard, sửa sâu); mã nào đúng dạng trên cũng được nhận, tên mô hình sai thì Claude Code từ chối khi chạy và trang báo bằng tiếng Việt.

**Đăng nhập một lần trên máy chủ** (làm trong phiên làm việc của chủ máy, như `agy`): mở Terminal trên máy chủ, chạy `claude auth login` rồi làm theo trình duyệt. Kiểm tra bằng `claude auth status` (phải thấy `loggedIn: true`). Chưa cài hoặc chưa đăng nhập thì agent Opus 5.5 High hiện "(chưa dùng được)" kèm lý do: *chưa cài Claude Code* hoặc *Claude Code trên máy chủ chưa đăng nhập*. Việc kiểm tra này không gọi mô hình, nhớ 10 phút (1 phút nếu đang lỗi); sau khi đăng nhập, tải lại trang hoặc đợi một phút. Ứng dụng không bao giờ truyền `ANTHROPIC_API_KEY` cho `claude`, nên luôn chạy theo gói đăng ký, không tính tiền theo token.

**Một lần gọi** (dàn ý, lời dẫn, sửa nhanh): `claude -p --model <mô hình> --effort <mức> --output-format json --tools "" --safe-mode --setting-sources "" --strict-mcp-config --disable-slash-commands --no-session-persistence --permission-mode dontAsk --system-prompt <câu hệ thống>`, prompt đi qua đầu vào chuẩn. Không có công cụ nào, không lưu phiên, thư mục tạm trống, và không lẫn cài đặt riêng của người đang đăng nhập (hướng dẫn dự án, hook, skill, bộ nhớ, MCP, plugin): cùng một câu hỏi cho cùng một câu trả lời trên mọi máy.

**Agent làm việc trong thư mục** (dựng storyboard, sửa sâu): `claude -p --input-format stream-json --output-format stream-json --verbose --tools Bash,Read,Write,Edit,Glob,Grep --permission-mode dontAsk --allowedTools ... --disallowedTools ...` cùng các tùy chọn tách biệt ở trên. Nó **không** chạy với quyền bỏ kiểm tra như `agy`: chỉ được đọc trong thư mục làm việc của nó, chỉ được ghi vào `out/`, chỉ được chạy ba lệnh hỗ trợ của lời dặn (`check`, `defaults`, `still`); web, thư mục khác, lệnh khác đều bị từ chối. Khi kiểm tra còn lỗi, lời nhắc sửa được gửi vào cùng tiến trình (cùng cuộc trò chuyện, tối đa 2 lần); không lưu phiên nào trên đĩa nên lần sửa tiếp theo dựng lại ngữ cảnh từ các lượt trước.

Lỗi thường gặp (hiện tiếng Việt): chưa đăng nhập (`claude auth login`), hết hạn mức của gói kèm giờ mở lại, tên mô hình bị từ chối, quá thời gian, chưa cài `claude`. Cần Claude Code từ 2.1.233 (bản trên máy chủ); bản quá cũ thiếu các tùy chọn trên thì bị từ chối kèm lời nhắc `claude update`.

### 5.5 Ý nghĩa các thông báo kiểm tra

**Lỗi (chặn duyệt)**

| Thông báo | Nghĩa là gì, làm gì |
|---|---|
| Thiếu chương (`chapter_missing`) | Một chương của dàn ý chưa có trong lời dẫn, hoặc có tiêu đề mà không có dòng nào. Bấm "Viết các chương còn thiếu" hoặc dán chương đó. |
| Dòng trống (`empty_beat`) | Có một dòng không có chữ (thường do "Chèn dưới" chưa điền). Điền hoặc Bỏ. |
| Có ký hiệu trong lời đọc (`markup_in_text`) | Lời đọc có thứ không đọc được: `##`, `>>`, `**đậm**`, `[ghi chú]`, thẻ `<...>`, mã nguồn như `PAY-07` hoặc mã dữ kiện `f03`, `facts:` / `show:`, gạch đứng, dấu đầu dòng. Lời đọc chỉ chứa chữ sẽ được nói. Chuyển phần hình ảnh sang dòng "cho xem". |
| Quá ngắn (`words_under`) | Tổng số từ dưới 70% mục tiêu. Viết thêm, hoặc hạ mục tiêu ở cột Nguồn rồi lập lại dàn ý. |
| Chưa có dàn ý, chưa duyệt, đã đổi sau khi duyệt (`outline_missing`, `outline_not_approved`, `outline_stale`) | Lời dẫn đi theo dàn ý đã duyệt. Duyệt lại dàn ý trước, rồi duyệt lời dẫn. |
| Dàn ý: Chưa có câu hỏi chính, chưa có chương, trùng mã chương, chương chưa có tên, chưa có số từ, trùng mã dữ kiện | Điền cho đủ trước khi duyệt dàn ý. |

**Cảnh báo (không chặn)**

| Thông báo | Nghĩa là gì |
|---|---|
| Lệch mục tiêu quá 15% (`words_off_target`) | Tổng số từ cách mục tiêu hơn 15%. |
| Chương lệch ngân sách quá 30% (`chapter_off_budget`) | Một chương dài hoặc ngắn hơn ngân sách hơn 30%. Thanh ngân sách ở dưới cùng đổi sang vàng (lệch trên 15%) hoặc đỏ (trên 30%). |
| Dòng quá dài (`beat_too_long`) | Một dòng hơn 90 từ. Nên Tách. |
| Mã dữ kiện không có trong dàn ý (`unknown_fact`) | Dòng hoặc chương nhắc tới một mã không có ở bảng dữ kiện. |
| Dòng chưa có gợi ý hình (`no_show`) | Ô "cho xem" trống. Cần cho bước chọn hình sau này. |
| Chương không có trong dàn ý (`unknown_chapter`) | Lời dẫn có chương mà dàn ý không có. |
| Dấu câu giọng đọc không ngắt được (`spoken_chars`) | Có `; : ( )` hoặc gạch ngang. Giọng đọc chỉ ngắt ở dấu phẩy và dấu chấm. |
| Dàn ý: dữ kiện không dẫn đoạn nguồn, mã đoạn nguồn lạ, tranh cãi chưa mô tả mâu thuẫn, dữ kiện chưa chương nào dùng, chưa chọn câu mở, tổng ngân sách lệch mục tiêu | Mỗi dữ kiện nên dẫn ít nhất một mã đoạn có trong cột Nguồn. Dữ kiện "tranh cãi" cần ghi các nguồn nói gì khác nhau. |

**Thông tin (không chặn)**

| Thông báo | Nghĩa là gì |
|---|---|
| Độ dài (`length`) | Số từ và số phút ước tính, theo tốc độ **2,41 từ/giây** (đo từ giọng này). Đổi ở cột Nguồn, ô "Từ/giây". |
| Nhịp câu (`sentence_profile`) | So độ dài câu với chuẩn kể chuyện (trung vị 12 đến 22 từ, 90% câu không quá 32 từ, không quá 25% câu trên 25 từ, không quá 5% câu dưới 4 từ, và có đổi nhịp dài ngắn). |
| Phần nguồn đã dùng (`source_share`) | Với mỗi sách, bao nhiêu đoạn được các dữ kiện đã dẫn trong lời dẫn chạm tới. |
| Trùng với văn bản nguồn (`overlap`) | Tỷ lệ chữ nằm trong các đoạn 8 từ liên tiếp giống hệt sách. Chỉ để biết, không bao giờ chặn (chủ kênh đã quyết định bản quyền không chặn). |

**Lưu ý khi đọc bản dán** (hiện sau khi dán thành công): "chương khớp theo vị trí", "chương xuất hiện hai lần", "mã dữ kiện lạ", "đoạn trước chương đầu bị bỏ", "dòng `>>` không có đoạn đi trước", "chương không có đoạn nào". Đều chỉ là lưu ý, văn bản đã được lưu.

**Lỗi tác vụ mô hình**: `timeout` (không trả lời kịp, chạy lại), `rate_limit` (hết hạn mức hoặc lượt: thông báo nêu agent và giờ mở lại, kèm nút chuyển sang agent kia), `auth` (chưa đăng nhập `agy` hoặc khóa bị từ chối), `config` (chưa cài `agy`, chưa đặt khóa, hoặc tên mô hình lạ), `parse` / `validation` (câu trả lời không đọc được hoặc không qua kiểm tra, ngay cả sau một lần thử lại; câu trả lời được giữ ở ô Dán), `conflict` (dàn ý chưa duyệt).

### 5.6 Tệp được ghi

Trong `projects/<dự-án>/script/`:

| Tệp | Nội dung |
|---|---|
| `outline.json`, `narration.json` | Dàn ý và lời dẫn, kèm khối `approval` (sha1 của nội dung đã duyệt). Mã dòng (`b0001`, ...) và mã chương, dữ kiện không bao giờ bị đánh số lại hay dùng lại. |
| `outline.prev.json`, `narration.prev.json` | Bản trước của lần ghi gần nhất (một bản). |
| `last_paste.txt`, `last_paste_outline.txt` | Bản dán lỗi gần nhất, hoặc câu trả lời lỗi của mô hình. Tự xóa khi lưu thành công. |
| `brief_options.json` | Mục tiêu số từ, tốc độ đọc, sách dịch máy được phép dùng, ghi chú chung. |

Giai đoạn hiện ở trang chủ và ở thanh trên cùng: "Đã duyệt dàn ý" (dàn ý đã duyệt, còn khớp), "Có kịch bản" (lời dẫn đã duyệt, còn khớp). Sửa bất cứ chữ nào sau khi duyệt thì giai đoạn lùi lại.

### 5.7 Chạy thử nhanh không cần khóa

Ô "Agent" chỉ có hai agent thật. Để thử không tốn hạn mức, cho máy chủ một tệp agent riêng bằng biến môi trường `BTI_AGENT_CHOICES_FILE` (cùng dạng với `config/agent_choices.json`, trong đó một agent chạy mô hình `mock`: câu trả lời mẫu, không gọi mạng, nội dung không có giá trị thật); các thử nghiệm của dự án làm đúng như vậy. Một yêu cầu gửi thẳng tới máy chủ vẫn nêu được `"model": "mock"`. Trong ô ghi chú có thể gõ các dấu hiệu để thử các tình huống: `[mock:bad c02]` (lần viết đầu của chương c02 có ký hiệu lỗi, lần thử lại đúng), `[mock:alwaysbad c02]` (luôn lỗi, tác vụ dừng), `[mock:badoutline]` (dàn ý lần đầu không đọc được), `[mock:slow]` (chạy chậm khoảng 10 giây, để thử Hủy), `[mock:ratelimit]` (báo hết lượt).

### 5.8 Chữ bạn đang sửa không bao giờ bị ghi đè

- Câu trả lời của máy chủ (lưu, duyệt, dán, tác vụ mô hình kết thúc hoặc bị hủy, tải lại sau xung đột) luôn được **ghép** vào bản bạn đang sửa, theo từng chương, từng dòng, từng dữ kiện. Chỗ nào chỉ bạn sửa thì giữ, chỗ nào chỉ máy chủ sửa (một chương mô hình vừa viết) thì lấy.
- Khi cả hai cùng sửa một chỗ (cùng một chương, cùng một câu hỏi chính...), trang hỏi: "Giữ bản của tôi" hoặc "Lấy bản mới" cho từng chỗ. Đóng hộp = giữ bản của bạn. Bản cũ vẫn lấy lại được bằng Hoàn tác.
- Trong lúc một tác vụ mô hình đang ghi dàn ý (hoặc lời dẫn), phần đó **chưa lưu được** (tác vụ cũng ghi vào cùng tệp). Cứ gõ tiếp: chữ được giữ trên trang, ghép với kết quả khi tác vụ xong (hoặc bị hủy), rồi bạn bấm Lưu. Tách, gộp, bỏ, chuyển dòng chờ tác vụ xong.
- Hai tab cùng sửa một dàn ý: lưu ở tab sau sẽ ghép phần bạn sửa vào bản mới (và lưu lại); chỉ khi trùng chỗ mới hỏi.
- Mọi thao tác ghi (lưu, tách, gộp, chuyển, duyệt, dán, đổi tùy chọn) đi qua một hàng đợi: hai lần bấm ↑ liên tiếp là hai bước, không bao giờ báo "tệp đã đổi ở nơi khác" giả.
- Ô số (số từ, mục tiêu): chỉ nhận số nguyên trong khoảng cho phép (0 đến 20000; mục tiêu của dự án 300 đến 20000). Giá trị sai bị từ chối kèm thông báo và ô quay về giá trị cũ.
- Thông báo lỗi luôn bằng tiếng Việt. Văn bản gốc của máy chủ nằm dưới nút "chi tiết".
- Hộp thoại: Tab xoay vòng trong hộp, Esc đóng hộp trên cùng, Enter trong ô chữ bấm nút chính (nút xanh). Trang phía sau bị khóa khi có hộp. Hộp có chữ bạn dán không đóng khi bấm ra ngoài.
- Tìm kiếm (thư viện, trong sách) không phân biệt dấu và chữ hoa: "duc" khớp "Đức", "Durer" khớp "Dürer". Bộ đếm từ tính chữ của mọi bảng chữ cái, khớp với máy chủ.

## 6. Bước 3 và 4: Giọng đọc và Chọn hình

### Giọng đọc

Bước 3 biến lời dẫn đã duyệt thành một tệp âm thanh (`audio/mix.m4a`) và một tệp ghi thời điểm từng từ (`timing.json`). Bước này mở khi bạn đã duyệt lời dẫn ở bước Kịch bản, và bạn có thể chọn hình (bước 4) trong lúc máy đọc.

1. Mở bước "Giọng đọc". Trang cho biết còn bao nhiêu câu chưa đọc và máy cần khoảng bao lâu (một video 12 phút mất chừng 50 phút máy chạy, chia thành các phần khoảng 20 phút).
2. Bấm "Tạo giọng đọc". Bạn có thể rời trang, máy vẫn chạy. Trang hiện từng phần đang chạy; phần nào chờ máy rảnh sẽ ghi "Chờ máy rảnh". Bấm "Hủy" để dừng; các câu đã đọc xong được giữ lại, bấm tạo lại sẽ đọc tiếp từ chỗ dở.
3. Khi xong, bấm nút nghe để nghe cả bài, hoặc nghe từng câu ở danh sách lời dẫn theo chương. Câu nào chưa vừa ý, bấm "Đọc lại câu này" để máy đọc lại bằng một lần đọc khác.
4. Con số, năm, thế kỷ, tiền, phần trăm, chữ viết tắt và số La Mã (vua, giáo hoàng) được đọc thành chữ tự động. Từ nào máy đọc sai (thường là tên riêng), thêm vào "Bảng phát âm": chữ viết bên trái, cách đọc bên phải, rồi bấm "Lưu bảng phát âm". Chỉ những câu có từ đó phải đọc lại.
5. "Tốc độ đọc" (1.00 đến 1.20) và "Nhạc nền nhẹ" chỉ cần ghép lại, không phải đọc lại (vài phút).
6. Nếu bạn sửa lời dẫn sau khi đã có giọng đọc, trang báo "Lời dẫn đã đổi" và chỉ những câu đã đổi được đọc lại. Các shot của storyboard neo vào từ nào sẽ được kiểm tra lại ở bước Dựng hình.
7. Nếu máy chưa có máy đo từ, thời điểm từng từ được chia đều trong mỗi câu (trang ghi rõ); chỉ đầu và cuối mỗi câu là chính xác.

Phụ đề không bao giờ được vẽ vào hình; bước này không đưa chữ lên màn hình.

## Update 2026-11-16 (late): silences and cards, and the model load time
- Silences (`config/voice.json`): sentence 0.20, beat 0.45, plain chapter 1.0, **chapter with `card: true` 3.2** (0.2 air + the 2.8 s card, none after), **title card 6.2** (`title`), `card_length` 2.8, lead 0.35. The title silence goes before the first chapter that follows a cold open (`role == "cold_open"`, the exact value in `bti/script/store.py` `ROLES`), or at the very start of the audio when the narration has no cold open. When that chapter also has `card: true`, the silence is title + card (9.4 s) and the lead kind is `title`.
- `timing.json` chapters keep every old field and gain `lead: {kind: "title"|"card"|"plain", start, end}` (the silence before the first word); `card_start/card_end` = the last 2.8 s of the silence (card chapters); `title_start/title_end` = the first 6.2 s (title leads).
- Model load: the real test took 269 s of synthesis part for 7.48 s of speech. The worker's lines do not let me split load from synthesis after the fact (the `ready` line was not logged; `sec` is audio length, not compute). The provider now logs `voice model ready after N s` and a `voice part: {load_s, total_s, chunks}` line to the job log, so the next real run gives the split. Until then the planner's `load_seconds: 60` is too low: treat load as up to about 4 minutes on this server (269 s total for two sentences, so load is at most 269 s and almost all of it) and keep one load inside each 20-minute part.
- Tests on the server: 66 passed, 1 skipped.

### Chọn hình

**Chọn hình là gì?** Sau khi lời dẫn được duyệt, bạn quyết định mỗi dòng lời dẫn sẽ cho xem hình gì: bức tranh chính, một chi tiết của nó, hay một hình khác. Bước này nằm giữa Kịch bản và Dựng hình.

**1. Chọn tranh chính (làm đầu tiên).** Mở tab "Tranh chính" ở cột bên phải. Ô tìm đã có sẵn tên tranh và tác giả; bấm "Tìm". Kết quả lấy từ Wikimedia Commons và The Met, mỗi ảnh cho biết kích thước (của bản gốc ở nguồn) và giấy phép. Ảnh quá lớn được lấy bản thu nhỏ do chính nguồn cung cấp; kích thước ghi trong dự án và các vùng bạn vẽ luôn tính theo đúng tệp đã lưu. Bấm "Làm tranh chính" ở ảnh bạn muốn. Cũng có thể lấy ảnh từ sách (tab "Sách") hoặc tải ảnh của bạn lên (tab "Tải lên").

**2. Cờ cảnh báo.** Ảnh có thể mang một cờ: "Giấy phép bị hạn chế", "Chưa rõ giấy phép" hoặc "Ảnh nhỏ" (dưới 1200 px). Cờ chỉ để bạn biết: ảnh vẫn dùng được và không bao giờ bị từ chối. Nguồn và giấy phép luôn được ghi lại để điền vào phần mô tả video.

**3. Vẽ vùng chi tiết.** Bấm "Vùng trên tranh". Bấm vào tâm của chi tiết trên tranh rồi kéo ra tới mép, đặt tên (D1, D2... là các chi tiết trong hồ sơ tác phẩm, hoặc tên tùy ý), bấm "Thêm vùng này", rồi "Lưu các vùng". Vùng dùng được ở mọi dòng.

**4. Chọn hình cho từng dòng.** Cột trái là các dòng lời dẫn theo chương, số bên phải là số hình đã chọn. Chọn một dòng: cột giữa hiện lời dẫn, các từ gợi ý hình (bấm vào để tìm), và "khay" hình của dòng. Thêm "cả tranh chính" hoặc một vùng bằng các nút nhỏ, hoặc bấm "Thêm vào dòng" ở một kết quả tìm. Mỗi hình có ô chọn vùng, vai trò (cả bức tranh, chi tiết, bối cảnh, so sánh, tài liệu, bản đồ, video), ghi chú, và nút đổi thứ tự hoặc bỏ. Dòng không cần hình riêng thì để trống: bản nháp sẽ dùng tranh chính ở đó. Dòng bạn không muốn tính là thiếu thì tick "Bỏ qua dòng này". Mọi thay đổi tự lưu sau chưa đến một giây.

**5. Tìm thêm.** Tab "Tìm kiếm": gõ từ khóa, hoặc bấm "Dùng chữ gợi ý của dòng này". Tab "Sách": ảnh và trang trong chính các cuốn sách của dự án. Tab "Gợi ý": nút "Gợi ý thêm" hỏi You.com nên cho xem gì. **Nút này tốn tiền**, chỉ chạy khi bạn bấm và xác nhận, tính cho từng dòng. Kết quả được giữ lại, bấm lại cho dòng đã có thì không tốn thêm.

**6. Duyệt.** Bấm "Kiểm tra" để xem lỗi (phải sửa: chưa có tranh chính, hình hoặc vùng không còn) và cảnh báo (không chặn: dòng chưa có hình, ảnh có cờ). Rồi bấm "Duyệt chọn hình". Chỉ duyệt được khi lời dẫn đã duyệt. Nếu sau đó bạn sửa hình hoặc sửa lời dẫn, bước này cần duyệt lại và bước Dựng hình sẽ nói bản nháp cũ không còn khớp.

**Nếu có sự cố.** "Nguồn ảnh đang bận": đợi vài giây rồi tìm lại, hoặc bỏ tick một nguồn. "Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng N phút": nguồn (thường là Wikimedia Commons) tự báo phải chờ; ứng dụng không thử lại dồn dập, hãy đợi đúng số phút đó rồi bấm lại, hoặc dùng nguồn khác. "Tệp ảnh bị cắt dở": tải lại tệp đầy đủ. "Chọn hình đã đổi ở nơi khác": trang tự tải lại bản mới nhất; phần bạn vừa sửa chưa lưu sẽ mất.

## 7. Bước 5: Dựng hình (trình biên tập storyboard)

Bước này để xem và sửa `storyboard.json` của một video: shot, lớp phủ (overlay), kỹ thuật, tham số, hình và thời điểm. Khung hình xem trước là ảnh thật do engine dựng, không phải ảnh giả.

### Các khu vực

- **Thanh công cụ của bước**: Lưu, Kiểm tra (số lỗi/cảnh báo), Hoàn tác, Làm lại, Đề xuất, Duyệt (và trạng thái duyệt), Xem thử 10 giây. Khi bản lưu đã được duyệt, nút **Tiếp tục** ở góc phải mở bước kế tiếp.
- **Khung xem trước (trái trên)**: ảnh thật tại vị trí đầu phát. Các khung màu K1, K2... là khóa camera của shot (cách kéo ở mục "Kéo khung camera" ngay dưới). Khi chọn lớp phủ (hoặc shot) có tham số điểm/khung, kéo chấm vàng để dời, kéo núm để đổi bán kính hoặc kích thước. Ô "Ảnh gốc" cho xem toàn ảnh để kéo khung dễ hơn. Ô "Hiện vùng" hiện tên các vùng (region) của hình. Khung xem trước luôn là khung **tại đầu phát**: chọn một shot hoặc lớp phủ (trên timeline, trong danh sách, hoặc bấm một lỗi) thì đầu phát tự vào trong mục đó, để ảnh và tay cầm cùng một thời điểm.

**Mỗi tham số điểm/khung sống trong đúng một hệ tọa độ**, ghi bên cạnh ô nhập: *px ảnh nguồn* (điểm trên ảnh gốc, qua camera, có thể là tên vùng), *px khung hình* (1920 x 1080), hoặc *tỉ lệ khung* (0 đến 1). Tay cầm được vẽ và ghi đúng hệ đó. Tham số mà xem trước không vẽ được (ví dụ `to_quad`) chỉ có ô số. Shot không có camera vẫn có tay cầm cho tham số theo px khung hình; tham số theo px ảnh nguồn của shot đó dùng ô số hoặc bật "Ảnh gốc". "Chọn trên ảnh" trả giá trị theo hệ của ô (tên vùng chỉ khi hệ là ảnh nguồn; Shift = luôn lấy x, y).
- **Thanh phát**: shot trước/sau, phát/dừng, thời gian, từ đang đọc.

### Kéo khung camera (bước Dựng hình, ô "Ảnh gốc")

Mỗi khóa camera của shot là một khung trên ảnh gốc, **đúng phần ảnh mà camera nhìn thấy ở khóa đó**, có số (K1, K2...) và bảng ghi số cùng zoom ở góc trên trái. Kích thước khung = ô hiển thị chia cho zoom (zoom 2 thì khung bằng nửa ô), nên khung nhỏ là cận cảnh, khung lớn là xa. Khung luôn có tỉ lệ của ô mà camera nhìn qua: 16:9 với camera phủ cả khung hình, còn kỹ thuật bố cục thì là ô của nó (ví dụ LAY-01 mặc định 900 x 740, CMP-03 là 610 x 900), lấy từ chính tham số của shot (`panel_w_px`, `panel_h_px`...). Làm được với mọi kỹ thuật có tham số camera và với số khóa bất kỳ.
- **Chọn**: bấm vào một khung. Khóa đó được tô đậm trên ảnh và khối "Khóa N" ở biểu mẫu bên phải sáng lên (có chữ "đang chọn trên ảnh") và tự cuộn tới. Ngược lại, bấm hoặc gõ vào khối của một khóa ở biểu mẫu thì khung của khóa đó được chọn trên ảnh.
- **Dời tâm**: kéo bên trong khung. Khóa chưa chọn được chọn và kéo luôn trong một lần.
- **Đổi zoom**: kéo một trong bốn núm vuông ở góc của khung đang chọn. Tâm giữ nguyên, khung giữ tỉ lệ; kéo ra xa thì zoom giảm, kéo vào thì zoom tăng. Kéo chéo theo đường chéo thì góc đi theo con trỏ.
- **Giới hạn**: tâm không ra khỏi ảnh (khóa nào đã nằm ngoài ảnh thì không bị kéo ngược vào); zoom từ 0,01 đến 1000, tâm trong ±1.000.000, đúng giới hạn của ô nhập và của phần kiểm tra storyboard.
- **Nhiều khung chồng nhau**: núm của khóa đang chọn luôn được ưu tiên; ở chỗ khác, khung nhỏ nhất dưới con trỏ được chọn, nên khung nhỏ nằm trong khung lớn vẫn bấm được. Các khóa giống hệt nhau (camera đứng yên lúc đầu) vẽ chồng đúng lên nhau: kéo thì dời khóa đang chọn, bấm không kéo thì chuyển sang khóa kế trong chồng.
- **Kỹ thuật có nhiều camera** (LAY-01 `camera_left`/`camera_right`, LAY-02, LAY-07, CAM-02, CMP-02...): mỗi camera nhìn một ảnh khác nhau, nên ô "Camera:" cạnh "Ảnh gốc" chọn camera đang vẽ và ảnh gốc đổi theo ảnh của camera đó. Ở chế độ khung hình (không bật "Ảnh gốc") chỉ camera phủ cả khung hình được vẽ khung; camera của một ô thì trang nhắc bật "Ảnh gốc".
- **Hoàn tác**: một lần kéo là **một** bước hoàn tác (kể cả khi dừng tay giữa chừng), ô số cập nhật theo, và storyboard được đánh dấu đã sửa như khi gõ số. Trong lúc kéo, trang không gọi máy chủ; chế độ khung hình dựng lại ảnh thật khi thả chuột.
- **Bảng bên phải**: tab *Shot* (kỹ thuật, slot hình, thời điểm bắt đầu, tham số, chuyển cảnh, khóa, ghi chú), *Lớp phủ* (danh sách, và cho lớp phủ đang chọn: kỹ thuật, **slot hình của lớp phủ**, thời điểm, tham số), *Hình* (hình của dự án, vùng, tìm kiếm Commons/The Met, tải lên), *Lỗi*.

**Slot hình chỉ nhận hình đúng loại**: ảnh, video và mặt nạ (mask) là ba loại khác nhau. Bấm "Chọn" ở một slot thì tab *Hình* chỉ hiện hình loại đó. Đổi kỹ thuật không bao giờ đặt bức tranh vào slot video hay mask: các slot ấy để trống. Lớp phủ có slot riêng như shot (ví dụ HI-03 cần `mask`); `image` của lớp phủ mặc định là hình của shot ("theo shot"), bấm "Bỏ" để quay lại như vậy.

**Chưa đủ không phải là sai.** Shot hoặc lớp phủ còn trống slot bắt buộc (hoặc tham số bắt buộc) được đánh dấu "! thiếu: mask" trên timeline (viền cam nét đứt), trong danh sách lớp phủ và đầu tab Shot/Lớp phủ, và nút "N mục chưa đủ" hiện cạnh trạng thái duyệt. Vẫn **Lưu** được; khung xem trước hiện khung tạm kèm lý do. Nhưng **Duyệt** bị từ chối cho tới khi điền đủ, và hộp thoại liệt kê từng mục (bấm để tới).
- **Timeline (dưới)**: chương, shot (ảnh nhỏ, huy hiệu kỹ thuật), lớp phủ, từng từ (khi phóng to), sóng âm, bản đồ nhỏ.

Biểu mẫu tham số được sinh tự động từ registry (`style/gae/techniques.json` cùng các bản vá), nên kỹ thuật mới xuất hiện không cần sửa trang. Kiểu hỗ trợ: số, enum, bool, chuỗi, màu, điểm, danh sách điểm (`points`, có nút "Chọn trên ảnh" cho từng điểm), danh sách dòng (`lines`, mỗi dòng một mục), khung (`box`, bốn số `[x0, y0, x1, y1]`, hai góc, đúng dạng registry; kỹ thuật cho phép bỏ trống thì có nút "Bỏ khung"), camera. Kiểu lạ sẽ hiện ô JSON. Số gõ ngoài khoảng được ép về min/max, ô hiện giá trị thật đã lưu kèm chữ "đã ép về ...". Chữ của kỹ thuật (tiêu đề, nhãn...) là tham số cùng tên, nhập ở biểu mẫu; ô bắt buộc để trống bị tô đỏ.

Không có phụ đề nào được vẽ lên hình. Lời thoại chỉ hiện ở timeline và thanh phát.

### Phím tắt

Chỉ chạy khi bước Dựng hình đang mở (bước Kịch bản chỉ có Ctrl+S để lưu và Ctrl+Z, Ctrl+Shift+Z để hoàn tác khi không đang gõ). **Phím tắt không chạy khi có hộp thoại đang mở** (Đề xuất, thư viện kỹ thuật, xác nhận, xem thử...): lúc ấy Delete, S, Space... thuộc về hộp thoại, kể cả Ctrl+S. Cũng không chạy khi đang gõ trong ô nhập (Ctrl+S vẫn lưu), khi đang ở chế độ "Chọn trên ảnh" hoặc chọn hình cho slot (chỉ Esc là của trang), và Space/Enter/mũi tên thuộc nút hay ô đang giữ tiêu điểm. Giữ phím không lặp lại việc phá hủy (xóa, cắt, khóa).

| Phím | Việc |
|---|---|
| Space | Phát/dừng (phát âm thanh thật, hình bám theo) |
| S | Cắt shot tại đầu phát |
| L | Khóa/mở khóa mục đang chọn |
| Delete hoặc Backspace | Xóa lớp phủ (hoặc shot nếu không chọn lớp phủ). Bàn phím Mac không có Delete nên dùng Backspace; Ctrl+Z hoàn tác được |
| `[` `]` | Shot trước/sau |
| Mũi tên trái/phải | Từ trước/sau |
| Ctrl+S | Lưu |
| Ctrl+Z, Ctrl+Shift+Z (hoặc Ctrl+Y) | Hoàn tác, Làm lại |
| Ctrl+cuộn | Zoom timeline |
| Shift+cuộn | Cuộn ngang timeline |
| Alt khi kéo | Đặt thời điểm tự do (neo `{t}`), không bám từ |
| Esc | Hủy chế độ "Chọn trên ảnh" |

Trên timeline: nhấp vào shot luôn chọn shot đó và dời đầu phát tới đó. Kéo (không chỉ nhấp) ranh giới giữa hai shot để đổi thời lượng; vùng bắt ranh giới co lại theo độ rộng của shot nên ở mức zoom nhỏ vẫn nhấp được vào shot. Ranh giới bám đầu từ chỉ khi có từ trong vòng 0,35 s; trong khoảng lặng thì đi theo con trỏ (Alt = luôn tự do). Nhấp vào thanh lớp phủ chọn nó và đưa đầu phát vào trong nó. Nhấp (hoặc kéo) bản đồ nhỏ để cuộn timeline. Kéo thân thanh lớp phủ để dời, kéo mép trái/phải của thanh để đổi đầu/cuối. Khi một ranh giới đi qua lớp phủ, lớp phủ tự co hoặc dịch vào trong shot.

### Cắt, gộp, camera

- **Cắt**: mỗi nửa giữ đúng tư thế camera tại điểm cắt (zoom nội suy theo log, giống engine).
- **Gộp với shot trước**: camera của shot trước giữ nguyên mốc thời gian tuyệt đối và giữ tư thế cuối trong phần gộp; camera của shot bị gộp bỏ đi; lớp phủ của hai shot được nối lại, lớp phủ nào trùng id (cả hai shot đều có `o1`) được cấp id mới để chọn, sửa, xóa đúng mục.
- Đổi hình của một slot sẽ đặt lại camera theo hình mới (engine tính lại mặc định).

### Khóa, nguồn, duyệt

- Mọi chỉnh sửa tay đặt `source: "human"`. **Khóa** (L) nghĩa là người đã chốt mục đó: đề xuất của agent không bao giờ sửa mục khóa (kể cả khi chọn "chấp nhận tất cả").
- **Lưu** gửi bản nháp kèm `base_rev`. Chỉ phần đã gửi được coi là đã lưu: nếu bạn gõ thêm trong lúc đang lưu, phần đó vẫn giữ nguyên và dấu "chưa lưu" vẫn bật cho tới lần lưu sau. Vùng (region) là một phần của bản nháp: tạo, đổi tên, dời, xóa vùng đều Hoàn tác được và chỉ ghi lên đĩa khi Lưu; vùng đang được lớp phủ dùng thì không xóa được (trang nói rõ mục nào dùng), đổi tên thì hỏi có cập nhật các tham chiếu không. Đổi hình của slot mà các lớp phủ đang trỏ vùng của hình cũ thì trang hỏi: giữ tên vùng (sẽ báo lỗi) hoặc đổi thành tọa độ. Nếu server đã đổi (409) trang hỏi giữ nháp hay tải lại. Nếu còn lỗi (422) trang không lưu và mở tab *Lỗi*; bấm vào một lỗi để chọn đúng mục.
- **Duyệt** chỉ chạy khi đã lưu, không còn lỗi và không còn mục chưa đủ (nếu còn, bấm Duyệt sẽ mở danh sách các mục đó). Trạng thái: *Chưa duyệt*, *Đã duyệt*, *Duyệt cũ (đã sửa)*. Duyệt gắn với phiên bản (`rev`), sửa xong lưu lại thì phải duyệt lại.

### Kiểu mở đầu và mốc chương

Ở thanh công cụ phía trên khung xem trước có ô **Kiểu mở đầu và mốc chương**: cách video mở đầu (hình hiện dần dưới một vệt sáng, hoặc tối lại rồi hiện tên), lúc hiện tên kênh sau đoạn mở đầu, và các mốc chương "1. Tên chương" ở đầu mỗi chương. Có hai kiểu: **Vệt sáng quét** và **Tối lại, hiện tên**. Video làm bằng bản nháp mới tự có kiểu **Vệt sáng quét**; video cũ vẫn ở **Kiểu cũ** (thẻ tiêu đề và thẻ chương nền đen) cho tới khi bạn chọn một kiểu.

1. Chọn một kiểu trong ô. Máy đổi ngay trên storyboard đã lưu, khung xem trước hiện kiểu mới, và có một dòng nói đã đổi mấy chỗ. Không cần bấm Lưu: việc đổi kiểu là một lần lưu (bản trước nằm trong `history/`).
2. Nút **Hoàn tác** cạnh ô trả storyboard về đúng như trước khi đổi kiểu (kể cả "Kiểu cũ"). Nút này chỉ có sau lần đổi vừa xong và mất khi bạn Lưu hoặc tải lại trang; khi đó dùng bản trong `history/`.
3. Cảnh **đã khóa** không bao giờ bị đổi. Chỗ nào không đổi được thì trang ghi bằng chữ dưới ô: cảnh nào đang khóa, video chưa có thẻ tiêu đề, không cảnh nào đủ dài (3 giây) cho phần mở đầu, cảnh ngắn quá (dưới 1,5 giây). Tab *Lỗi* cũng hiện một cảnh báo cho mỗi thẻ còn kiểu khác với kiểu đã chọn.
4. Nếu bạn đang có sửa đổi chưa lưu, trang làm đúng như với một lần sửa bằng lời: ghép sửa đổi của bạn với bản mới của máy chủ (hỏi bạn chỉ khi cả hai cùng sửa một cảnh).
5. **Sửa video bằng lời** không đổi kiểu này (agent trả lời "không làm được" và chỉ về ô này); nó chỉ sửa chữ của một mốc chương hoặc thêm một mốc mới, đúng kỹ thuật của kiểu đang dùng.
6. Bước **Xuất video** ghi kiểu nào sẽ dùng trong hộp *Sẽ làm ra* (dòng "Kiểu mở đầu và mốc chương"); đổi kiểu thì phải duyệt lại storyboard rồi xuất lại.

**For an agent** (HTTP, the same choice as the page; an agent never writes title cards or chapter cards by hand, and a draft ignores such shots):

```
GET  /api/projects/{pid}/identity
  -> {"style": null, "default": "raking", "options": [{"id": "raking", "label": "Vệt sáng quét"}, {"id": "dim", "label": "Tối lại, hiện tên"}]}
     `style` is null while nothing was chosen (the old cards); `default` is the style a new draft gets.

PUT  /api/projects/{pid}/identity
     {"style": "dim", "base_rev": "<rev of GET /api/projects/{pid}>"}
  -> {"rev": "<new revision>", "style": "dim", "changed": ["s0001", "s0004", "s0005"],
      "skipped": [{"shot": "s0015", "reason": "locked", "what": "mark", "message": "..."}]}
```

The style is applied to the saved storyboard under the same lock, revision rule and `history/` copy as `PUT /api/projects/{pid}/storyboard`: `409` (with the current `rev`) when `base_rev` is stale, nothing written; `422` for a style that is not in `options` (`code: identity_style_unknown`, `allowed`) or a missing `style` or `base_rev`; `404` for an unknown project or a project without a storyboard. `skipped` lists what was left as it is (`reason`: `locked`, `no_title_slot`, `extra_title`, `no_title`, `too_short`, `no_room`, `no_time`; `what`: `open`, `label`, `brand`, `mark`; `shot` is null when no shot is concerned). The same style twice changes nothing; `raking`, `dim`, `raking` gives what `raking` alone gives. To undo, `PUT /api/projects/{pid}/storyboard` the previous document with the new `rev`, or restore the copy in `history/`. A `PUT .../identity` does not touch the instruction box's undo (edit by instruction never re-applies the identity). The techniques of a style are in the `identity` block of `style/gae/style.json`. A shot or overlay of any `ID-*` technique shorter than its registry `timing.min_s` (1.5 s for all seven) is a validation error `element_too_short` (args `technique`, `min`, `got`): the save is refused (`422`), so lengthen it or remove it; the applier never makes one (a card under the floor stays an old card and is reported as `too_short`). The technique catalogue given to the draft and edit models lists the `ID-*` techniques marked `PROGRAM ONLY` and leaves them out of the choice by intent: a model never writes them.

### Bản đồ (kỹ thuật MAP-01)

Mọi câu lời dẫn nhắc một nơi, một chuyến đi hay một vùng đất đều dùng **Bản đồ atlas** (`MAP-01`). Nó thay ba kỹ thuật bản đồ cũ (`STATIC-06`, `AN-04`, `X-ANN-05`) cho video mới; storyboard cũ vẫn dùng được ba kỹ thuật kia. Bản đồ vẽ trên bờ biển thật của Natural Earth (dữ liệu công cộng, đi kèm sẵn trong dự án, không cần mạng khi dựng), nhãn chữ EB Garamond, không có khung chữ.

**Dữ liệu nó nhận** (chọn kỹ thuật ở thư viện, rồi điền ở khung tham số; mỗi danh sách sửa theo từng hàng, có nút *+ Thêm mục*, *Xóa*, *Lên*, *Xuống*):

- **places** (địa điểm): mã ngắn, tên hiện trên bản đồ, kinh độ và vĩ độ (gõ "3.2247, 51.2093"), thời điểm hiện (số giây kể từ đầu phần này, hoặc bấm *= đầu phát* để gắn vào từ lời dẫn đang phát, để chấm hiện đúng lúc từ đó được đọc) và phía đặt nhãn (để *Tự chọn* thì máy tự tìm chỗ không đè lên đường đi hay nhãn khác).
- **route** (đường đi, có thể không có): từ địa điểm nào đến địa điểm nào (theo mã), các điểm uốn (kinh độ, vĩ độ, cách nhau bằng dấu chấm phẩy), dạng cong hay thẳng, lúc bắt đầu vẽ và số giây vẽ. Đường là hàng chấm đỏ nâu có chấm đầu chạy theo.
- **region_iso** (vùng được tô): mã nước hai chữ cái theo ISO, ví dụ BE là Bỉ; **region_label** là chữ nhỏ ghi tên vùng.
- Khung nhìn: bắt đầu từ một khung rộng (`view_start_width_km`, tính bằng km) rồi máy quay đẩy chậm vào khung vừa với các địa điểm (`view_end_mode` = *Vừa các địa điểm*, chừa lề `view_end_margin_pct` phần trăm) hoặc vào một tâm và chiều rộng do bạn đặt (*Tự đặt*). Các điểm uốn của đường đi cũng được giữ trong khung.

**Hai màu biển** (`sea`): *Xanh xám* (mặc định) và *Nâu cũ*. Cả hai đều cho biển một màu riêng, đậm dần về phía bờ, có hai nét nước chạy theo bờ như atlas cổ, và đất liền sáng hơn, nên nhìn là phân biệt được đất với biển.

Máy quay đẩy vào nhưng chữ và chấm địa điểm giữ nguyên cỡ, chỉ vị trí đi theo bản đồ. Hạt giấy và vầng tối ở góc đứng yên so với màn hình. Phần mô hình không đoán toạ độ: địa điểm nào chưa chắc thì bỏ ra khỏi danh sách. Một phần bản đồ ngắn hơn 3 giây thì không lưu được (trang nói rõ); dữ liệu địa lý và cách làm lại nằm ở `style/gae/geo/README.md`.

### Bản nháp storyboard

Khi dự án đã xong Giọng đọc và Chọn hình mà chưa có storyboard, bước Dựng hình không mở một bảng trống: nó hiện khung **Bản nháp storyboard**. Khi đã có storyboard, nút **Bản nháp** trên thanh công cụ mở cùng khung đó.

1. Khung cho biết giọng đọc và chọn hình đã xong chưa. Ô **Agent** (cùng ô chọn của mục 2, bước "Dựng hình") cho biết agent sẽ dựng; đổi ở đây là đổi cho cả bước Dựng hình của dự án, cả ô Agent bên hộp "Sửa video bằng lời" đổi theo. Bấm **Dựng bản nháp**. Khung ghi tên agent đã dựng ("Agent: Gemini 3.8 Flash."). Nếu agent hết hạn mức, thông báo nêu tên agent và giờ mở lại kèm một nút chuyển sang agent kia và dựng lại. Nút **Dựng tự động (không dùng agent)** làm mỗi dòng lời dẫn một cảnh từ hình bạn đã chọn, không gọi mô hình nào: dùng khi agy chưa đăng nhập, hoặc để so sánh.
2. Bạn có thể rời trang; khung hiện số bước và việc agent đang làm. **Dừng** dừng agent ngay.
3. Kết quả không bao giờ tự ghi vào dự án. Nó là một **đề xuất**; bấm **Mở đề xuất** để xem. Với dự án chưa có storyboard, bấm **Áp dụng** (chấp nhận cả đề xuất) biến nó thành storyboard đầu tiên; chọn từng thay đổi chưa dùng được ở bước này. Mục nào còn dở được ghi trong đề xuất để bạn sửa tiếp.
4. Dựng lại sau này: cảnh bạn đã khóa không bao giờ bị đổi. Nếu giọng đọc hoặc danh sách hình đã đổi sau khi dựng, khung báo "dựng từ giọng đọc hoặc danh sách hình đã đổi" và đề xuất cũ vẫn xem được.
5. Agent chỉ làm việc trong một thư mục tạm chứa bản sao; trước và sau lần chạy, ứng dụng so thư mục dự án (và, trên máy chủ, kho truyện tranh). Nếu có gì bị đổi, lần dựng bị bỏ và trang báo.
6. Dùng agy trên máy chủ cần agy đã đăng nhập trong phiên làm việc của chủ máy; nếu chưa, trang báo rõ và bạn vẫn dùng được "Dựng tự động".

### Đề xuất của agent

Bản nháp cả video (không phải sửa bằng lời) ghi `projects/<id>/proposals/<id>.json`. Nút *Đề xuất* mở danh sách; mở một đề xuất để xem từng thay đổi (trước/sau), chọn Chấp nhận hoặc Từ chối cho từng cái rồi *Áp dụng*. Thay đổi chạm vào mục khóa bị gạch và không áp dụng được. Đề xuất áp lên bản đã lưu, không phải bản nháp chưa lưu (trừ bản nháp đầu tiên của dự án chưa có storyboard, xem trên). Đề xuất soạn trên một bản đã cũ (storyboard đã lưu thêm kể từ đó) có dải cảnh báo "dựa trên bản cũ" và hỏi lại trước khi áp dụng. Áp dụng khi bản nháp chưa lưu cũng hỏi (hộp thoại của ứng dụng, không dùng hộp thoại của trình duyệt).

### Sửa video bằng lời

Bên phải khung xem trước ở bước Dựng hình có ô **Sửa video bằng lời**. Bạn gõ điều muốn đổi, ví dụ *"zoom chậm hơn vào chiếc gương và thêm một vòng sáng quanh nó"*, và agent sửa thẳng storyboard. Không còn "đề xuất" để chấp nhận: mỗi lần sửa được ghi lại thành một thẻ, có ảnh trước và sau, và hoàn tác được.

1. **Gõ yêu cầu** vào ô, bấm **Gửi** (hoặc Ctrl+Enter).
2. **Phần sẽ sửa** nằm ngay dưới ô, nói bằng chữ: "Cảnh 12 đang chọn", "2 cảnh đang chọn (12, 13)", "Chương: tên chương", "Cả video". Mặc định là cảnh đang chọn; bấm **Cả chương** hoặc **Cả video** để đổi. Muốn sửa nhiều cảnh: bật **Chọn nhiều cảnh**, rồi bấm vào từng cảnh trên thanh thời gian; mỗi cảnh thành một thẻ nhỏ, bấm × để bỏ. Cảnh đã khóa không bao giờ bị đổi.
3. **Khi đang làm**, thẻ của lần sửa hiện một dòng tiến độ ("Đang nghĩ...", "Đang kiểm tra...") và nút **Dừng**. Việc nhỏ (tối đa 12 cảnh) chạy nhanh trong vài giây; việc lớn hơn chạy sâu hơn, có thể mất vài phút. Bạn có thể rời trang, lần sửa vẫn chạy.
4. **Kết quả** là một trong các trạng thái:
   - **Đã áp dụng**: thẻ có một câu tóm tắt và từng thay đổi (số cảnh, thời điểm, một câu mô tả, ảnh **Trước** và **Sau**). Trình biên tập tự lấy storyboard mới: nếu bạn chưa có sửa đổi chưa lưu thì tải lại và giữ nguyên cảnh đang chọn và vị trí đầu phát; nếu có, các sửa của bạn được ghép với lần sửa này (Hoàn tác của trình biên tập bắt đầu lại từ chỗ ghép).
   - **Không đổi**: agent không làm được (ví dụ cần một bức tranh mới); thẻ nói lý do và gợi ý nói rõ hơn hoặc chọn phần khác.
   - **Cần bạn chọn**: trong lúc agent làm, bạn cũng lưu sửa đúng các cảnh đó. Chọn **Dùng bản của agent** (các sửa tay của bạn từ lúc đó sẽ mất) hoặc **Giữ bản của bạn** (bỏ lần sửa này).
   - **Không làm được**: một câu nói vì sao, kèm nút **Thử lại**. Chữ gốc của máy chủ nằm dưới "chi tiết".
   - **Đã hủy**, **Đã hoàn tác**.
5. **Xem thử** dựng một đoạn ngắn (tối đa 10 giây) ở chỗ vừa sửa. **Hoàn tác** đưa các cảnh về như trước lần sửa. Nếu sau lần sửa bạn đã đổi chính các cảnh đó, ứng dụng hỏi trước ("Hoàn tác sẽ bỏ sửa đổi của bạn"); chọn **Vẫn hoàn tác** để tiếp tục. Chỉ 20 lần sửa gần nhất còn hoàn tác được.
6. Lần sửa bắt đầu ở thẻ trình duyệt khác cũng hiện ở đây sau vài giây. **Xóa lịch sử** hỏi một lần; nó chỉ xóa danh sách, không đổi video.

Agent làm việc này chọn ngay cạnh nút Gửi, bằng ô **Agent** (cùng ô với khung Bản nháp, bước "Dựng hình"; xem "Chọn agent" ở mục 2). Thẻ lần sửa xong ghi tên agent đã làm. Nếu agent hết hạn mức, thẻ nêu tên agent và giờ mở lại, kèm một nút "Chuyển sang <agent kia> và chạy lại" gửi lại đúng yêu cầu đó.

### Cài đặt

Nút **Cài đặt** ở thanh trên cùng mở hộp **Cài đặt**. Trên cùng là **Agent mặc định cho dự án mới**: dự án chưa chọn agent thì dùng agent này; chọn xong là lưu ngay (vào `run/settings.json`, được giữ qua các lần triển khai). Mỗi dự án vẫn đổi được agent của mình ở từng bước (mục 2, "Chọn agent").

Dưới đó là mục **Nâng cao**, mặc định đang đóng, có dòng "Chỉ dùng khi dự án và mặc định đều chưa chọn agent.". Mở ra là bảng **Mô hình cho từng việc**: mỗi việc (dàn ý kịch bản, lời dẫn kịch bản, dựng storyboard, sửa nhanh bằng lời, sửa sâu bằng lời, chọn hình) có một ô chọn mô hình. Mặc định tất cả là Gemini 3.8 Flash (High) qua agy. Ô **Dùng một mô hình cho tất cả** chọn một mô hình rồi bấm **Áp dụng cho tất cả**; các việc chạy qua agent (dựng storyboard, sửa sâu) chỉ nhận mô hình của agy hoặc của Claude Code nên giữ nguyên nếu mô hình đó không dùng được cho chúng. Bấm **Lưu** để ghi; lần chạy sau dùng mô hình mới, nhưng chỉ khi dự án và agent mặc định đều chưa chọn agent.

### Xem thử 10 giây

Dựng clip 10 giây từ đầu phát (kèm âm thanh) bằng bản nháp hiện tại, rồi phát trong cửa sổ nổi. Mất vài giây. Dự án không có file âm thanh vẫn xem thử được (không có tiếng) và timeline ghi rõ "chưa có file âm thanh".

### Tìm và nhập hình

Tab *Hình*: tìm trên Wikimedia Commons hoặc The Met. Nguồn và giấy phép luôn được ghi lại; hình có giấy phép hạn chế, chưa rõ hoặc nhỏ hơn 1200 px chỉ bị gắn **cờ** (không bao giờ bị từ chối), và tải lên không còn bắt buộc điền giấy phép, nguồn hay tác giả. Bấm *Nhập* để tải về `media/` của dự án (nên dùng bản sao, không dùng `arnolfini`). Nếu bấm "Chọn" ở slot thì hình mới được gán vào slot ngay. Nhập xong phải *Lưu* để hình nằm trong storyboard. Nếu nguồn trả 429/503, trang báo thử lại sau vài giây.

### Chưa có

- Khung camera chỉ có núm ở bốn góc của khóa đang chọn (không có núm ở cạnh); khung to hơn phần ảnh hiển thị bị cắt ở mép khung xem trước, và ảnh gốc tự thu nhỏ khi mở camera đó để chứa hết các khung.
- Chỉ Wikimedia Commons và The Met (chưa có AIC, Rijksmuseum, Europeana).
- Cả 79 kỹ thuật đều chọn được trong thư viện (không mục nào xám; 68 `done`, 11 `partial` ở chip "Engine"; 7 trong số đó, họ `ID-*`, là kỹ thuật của kiểu mở đầu và mốc chương: mỗi cái ngắn hơn 1,5 giây thì không lưu được và trang nói rõ phần nào cần dài thêm; `MAP-01` cũng không lưu được khi ngắn hơn 3 giây). Chọn, điền slot, lưu rồi tải lại đã được kiểm tra tự động cho từng kỹ thuật (`tests/e2e/storyboard/techniques71.mjs`).
- Chưa có chỉnh âm thanh trong trình biên tập (giọng đọc và tốc độ nằm ở bước 3; bản cuối ở bước 6).
- Lịch sử hoàn tác chỉ nằm trong trình duyệt, mất khi tải lại trang. Bản lưu cũ nằm trong `history/`.

## 8. Bước 6: Xuất video

**Xuất video** là bước cuối: máy dựng bản video hoàn chỉnh từ storyboard đã duyệt và giọng đọc.

1. Vào bước **Xuất video**. Nếu trang báo "Chưa xuất được", làm theo nút bên dưới (thường là duyệt storyboard ở bước Dựng hình, hoặc làm xong Giọng đọc).
2. Hộp **Sẽ làm ra** cho biết video dài bao lâu, chia thành mấy đoạn và khoảng bao lâu máy làm xong (máy chủ dựng bằng bộ xử lý nên khoảng 2 phút cho mỗi phút video; video 12 phút mất chừng nửa tiếng), và dòng **Kiểu mở đầu và mốc chương** cho biết video được xuất với kiểu nào (đổi ở bước Dựng hình).
3. Bấm **Xuất video**. Bạn có thể đóng trang, máy vẫn làm. Trang hiện từng đoạn đang chạy. Nếu máy đang bận việc khác, đoạn sẽ ở trạng thái "Chờ máy rảnh".
4. Bấm **Hủy** nếu muốn dừng. Những đoạn đã dựng xong được giữ lại; bấm **Xuất video** lần nữa sẽ làm tiếp, không dựng lại từ đầu. Việc này cũng đúng khi máy chủ khởi động lại giữa chừng.
5. Khi xong, bạn có: video để xem ngay trên trang, **phiếu kiểm tra** (độ dài, số khung hình, độ lớn tiếng, mục lục), **mô tả video** (có nút Chép mô tả: gồm mục lục, sách đã dùng, nguồn và giấy phép của từng hình) và các tệp để tải về: video MP4, mô tả, mục lục.
6. Bản xuất mới không tạo phụ đề lời đọc; nhãn và chú thích nghệ thuật trong storyboard vẫn được giữ. Bản xuất cũ không bị thay đổi.
7. Nếu bạn sửa storyboard hoặc giọng đọc sau khi xuất, trang báo "Cần xuất lại". Bản cũ vẫn xem được cho đến khi xuất bản mới.
8. Hình nào chưa rõ giấy phép sẽ có ghi chú trong mô tả để bạn kiểm tra trước khi đăng; việc xuất không bị chặn.

## 9. Dự án nhập từ bản dựng trước

`arnolfini`, `arnolfini_edit`, `technique_lab` (và các dự án `lab_*`, `demo_*`) chỉ có storyboard, không có thư mục `source/` hay kịch bản. Các bước 1 đến 4 của chúng ghi rõ: "Dự án này được nhập từ bản dựng trước, chưa có dữ liệu cho bước này", cùng nút mở bước Dựng hình. Bước Dựng hình dùng bình thường, và bước Xuất video mở sau khi storyboard đã duyệt.

## 10. Thay đổi chưa lưu

Rời một màn hình còn thay đổi chưa lưu (dàn ý hoặc lời dẫn ở bước Kịch bản, storyboard ở bước Dựng hình) luôn hỏi trước, dù bạn bấm thanh các bước, ô chọn dự án, một liên kết, hay nút Quay lại: **Ở lại**, **Bỏ thay đổi và rời đi**, hoặc **Lưu rồi rời đi**. Đóng hoặc tải lại tab cũng hỏi. Khi bạn rời một màn hình, mọi thứ nó đã bật đều tắt: bộ đếm giờ, phát âm thanh, hộp thoại đang mở, yêu cầu đang chờ. Phím tắt của màn hình này không bao giờ chạy ở màn hình khác.

Nút Quay lại của trình duyệt đã đổi địa chỉ trước khi ứng dụng kịp hỏi; nếu bạn chọn Ở lại, ứng dụng trả địa chỉ về chỗ cũ (có thể để lại một mục lịch sử trùng).

## 11. Tệp được ghi

| Nơi | Nội dung |
|---|---|
| `projects/<dự-án>/project.json`, `source/` | Dự án tạo từ thư viện: bản sao hồ sơ và văn bản nguồn. |
| `projects/<dự-án>/script/` | Kịch bản (bảng dưới). |
| `projects/<dự-án>/storyboard.json`, `history/` | Storyboard và các bản lưu cũ. |
| `projects/<dự-án>/voice/`, `audio/`, `timing.json` | Giọng đọc: từng câu đã đọc, bảng phát âm, tệp ghép `audio/mix.m4a`, thời điểm từng từ. |
| `projects/<dự-án>/picks.json`, `media/` | Chọn hình và các ảnh đã nhập. |
| `projects/<dự-án>/proposals/` | Đề xuất (kể cả bản nháp do agent dựng). |
| `projects/<dự-án>/export/` | Video, mô tả, mục lục và `export.json`. |
| `projects/<dự-án>/cache/longjobs/` | Bản ghi và nhật ký các việc dài (giọng đọc, bản nháp, xuất video); xóa được, mất thì chỉ mất lịch sử. |
| `library/overrides/artworks.json` | Gộp và tách tác phẩm. |

Trong `projects/<dự-án>/script/`:

| Tệp | Nội dung |
|---|---|
| `outline.json`, `narration.json` | Dàn ý và lời dẫn, kèm khối `approval` (sha1 của nội dung đã duyệt). Mã dòng (`b0001`, ...) và mã chương, dữ kiện không bao giờ bị đánh số lại hay dùng lại. |
| `outline.prev.json`, `narration.prev.json` | Bản trước của lần ghi gần nhất (một bản). |
| `last_paste.txt`, `last_paste_outline.txt` | Bản dán lỗi gần nhất, hoặc câu trả lời lỗi của mô hình. Tự xóa khi lưu thành công. |
| `brief_options.json` | Mục tiêu số từ, tốc độ đọc, sách dịch máy được phép dùng, ghi chú chung. |
