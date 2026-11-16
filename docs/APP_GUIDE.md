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

## 3. Trang chủ và các bước

**Trang chủ** liệt kê mọi dự án: tên, mã, tác phẩm, giai đoạn, thanh năm sáu ô tiến độ, bước kế tiếp và nút **Tiếp tục** (mở dự án ở bước kế tiếp). Nút **+ Tạo video mới** dẫn tới thư viện. Nút **Xóa** xóa cả thư mục dự án: phải gõ đúng mã dự án để xác nhận, không khôi phục được. Hai dự án gốc `arnolfini` và `technique_lab` hiện nhãn "được bảo vệ" và máy chủ từ chối xóa chúng (HTTP 403).

**Các bước**, theo thứ tự:

| Bước | Màn hình |
|---|---|
| 1. Tác phẩm | Hồ sơ của tác phẩm đã chọn và các nguồn sách đang dùng. Với video mới, đây là thư viện: tác phẩm, kệ sách, hồ sơ, tạo dự án. |
| 2. Kịch bản | Nguồn, dàn ý, lời dẫn. |
| 3. Giọng đọc | Chưa xây dựng. |
| 4. Chọn hình | Chưa xây dựng. |
| 5. Dựng hình | Trình biên tập storyboard. |
| 6. Xuất video | Chưa xây dựng. Nếu dự án đã có tệp video dựng sẵn, màn hình chỉ rõ tệp nằm ở đâu. |

Mỗi bước trên thanh các bước có một trạng thái, do máy chủ tính (`GET /api/projects/<id>/pipeline`):

| Trạng thái | Nghĩa là gì |
|---|---|
| **Xong** (dấu tích xanh) | Bước đã hoàn thành (ví dụ lời dẫn đã duyệt và còn khớp, storyboard đã duyệt). |
| **Hiện tại** | Bước mà giai đoạn của dự án cần làm tiếp. Mở dự án là vào thẳng bước này. |
| **Mở được** | Bước mở được nhưng chưa phải bước kế tiếp. |
| **Khóa** | Chưa mở được. Rê chuột hoặc bấm vào bước sẽ thấy lý do (ví dụ "Chưa có storyboard"). |
| **Chưa xây dựng** | Bước chưa có trong ứng dụng. Vẫn mở được để xem bước đó sẽ làm gì, nhưng không có nút giả nào. |
| **Không có dữ liệu** | Dự án nhập từ bản dựng trước, không có dữ liệu cho bước này (mục 8). |

Bước đang mở được gạch chân màu xanh. Bước mà giai đoạn của dự án cần làm tiếp có dấu "Hiện tại" (hoặc "ở đây" với bước chưa xây dựng). Sau khi duyệt xong một bước, nút **Tiếp tục: <tên bước>** dẫn tới bước kế tiếp mở được (bước khóa bị bỏ qua, bước chưa xây dựng thì không). Nút này có ở bước Kịch bản (sau khi lời dẫn đã duyệt), bước Dựng hình (sau khi storyboard đã duyệt), và ở cuối các màn hình thông báo.

## 4. Bước 1: Tác phẩm và thư viện

Với video mới, bấm **+ Tạo video mới**. Thư viện có hai thẻ:

- **Tác phẩm**: mỗi tác phẩm là một video; các sách cùng nói về một tranh đã được gộp vào một hồ sơ. Lọc theo tên, thế kỷ, đã có dự án chưa, có trong từ 2 sách, có gồm chương chủ đề hay không. Bản quyền chỉ là thông tin ước lượng, không chặn gì.
- **Kệ sách**: chọn một cuốn, xem các mục của nó (lọc theo tên, thế kỷ, bản quyền), mở một mục để xem các trang, văn bản trích (bản scan là văn bản OCR, có thể sai chữ), hình nhúng, và các sách khác có cùng tác phẩm.

Bấm một tác phẩm để mở **hồ sơ**: tên, hoạ sĩ, năm (chỗ các sách ghi khác nhau được tô vàng), nguồn của từng sách (dàn ý theo cấu trúc, chú thích hình, các trang, văn bản thân bài). Sách dịch máy có nhãn "bản dịch máy, không dùng làm nguồn sự kiện". Ở hồ sơ có thể **Gộp với…** một tác phẩm khác thực ra là cùng một bức tranh, hoặc **Tách** một nguồn thành tác phẩm riêng (ghi vào `library/overrides/artworks.json`).

**Tạo dự án**: bấm "Tạo dự án", bỏ tick những nguồn không muốn dùng (mặc định bỏ sách dịch máy nếu còn nguồn khác), có thể đặt tên thư mục (slug: a-z, 0-9, `-`, `_`; không được bắt đầu bằng `lab_` hoặc `demo_`). Dự án nhận một bản sao hồ sơ và văn bản; chưa có storyboard. Tạo xong ứng dụng mở dự án ở bước Kịch bản.

Với dự án đã có, bước **Tác phẩm** hiện hồ sơ tác phẩm của dự án: tên, hoạ sĩ, năm, các nguồn không thống nhất, các chi tiết có tên, và từng nguồn sách đang dùng (xem văn bản, mở mục trong thư viện). Chọn sách nào làm nguồn thì chỉnh ở bước Kịch bản, cột Nguồn.

## 5. Bước 2: Kịch bản (dàn ý và lời dẫn)

Bước này biến một tác phẩm đã chọn thành lời dẫn đã duyệt. Có hai giai đoạn, và bạn duyệt cả hai:

1. **Dàn ý**: một mô hình đọc các đoạn sách đã đánh số, rồi viết câu hỏi chính, ba câu mở đầu, bảng dữ kiện (mỗi dữ kiện dẫn mã đoạn sách, có độ chắc chắn và mâu thuẫn giữa các sách) và danh sách chương kèm số từ. Bạn sửa rồi **Duyệt dàn ý**.
2. **Lời dẫn**: mô hình viết từng chương theo dàn ý đã duyệt. Bạn sửa, cắt, tách, gộp rồi **Duyệt lời dẫn**.

Có hai đường làm, cùng dùng một prompt và một bộ đọc, nên kết quả giống nhau:

- **Nút bấm**: chọn mô hình ở ô thả xuống, bấm "Lập dàn ý" rồi "Viết lời dẫn".
- **Sao chép và dán**: bấm "Sao chép prompt", dán vào Gemini, rồi dán nguyên câu trả lời vào nút "Dán".

Tác vụ mô hình chạy trên máy chủ nên vẫn chạy khi bạn rời bước này; quay lại sẽ thấy tiến độ và kết quả.

### 5.1 Màn hình

Ba cột và một thanh trạng thái.

| Cột | Nội dung |
|---|---|
| **Nguồn** (trái) | Thẻ tác phẩm, mục tiêu số từ và tốc độ đọc, các chi tiết có tên (D1, D2, ...), chỗ các sách không thống nhất, một thẻ cho mỗi sách với các đoạn đã đánh số (`PAY-07`, `HOD-02`, ...), ô tìm kiếm. Sách dịch máy có nhãn "bản dịch máy, không dùng làm nguồn sự kiện" và một ô tick để cho phép dùng. |
| **Dàn ý** (giữa) | Câu hỏi chính, chọn một trong các câu mở đầu, các chương (tên, vai trò, thẻ chương, số từ, mục đích, dữ kiện, cho xem), bảng dữ kiện (độ chắc chắn, mã đoạn nguồn, mâu thuẫn). |
| **Lời dẫn** (phải) | Các chương, mỗi chương gồm nhiều dòng (beat). Mỗi dòng là một đoạn lời đọc, sửa trực tiếp được. |
| **Thanh dưới** | Tổng số từ, số phút ước tính, thanh ngân sách từng chương, tiến độ của tác vụ đang chạy kèm nút Hủy. |

Bấm vào mã dữ kiện (`f03`) hoặc mã đoạn nguồn (`PAY-07`) ở cột giữa hoặc cột phải: đoạn sách tương ứng sáng lên ở cột trái.

#### Thanh công cụ của bước

| Nút | Việc làm |
|---|---|
| Ô mô hình | Chọn mô hình dùng cho hai nút "Lập dàn ý" và "Viết lời dẫn". Mô hình chưa dùng được vẫn hiện, ghi "(không dùng được)", chọn vào sẽ có lời giải thích. (Dự án chọn ở thanh trên cùng của ứng dụng.) |
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

1. Chọn mô hình (mặc định là Antigravity CLI, Gemini 3.8 Flash High). Muốn thử mà không tốn hạn mức: chọn **Mock** (câu trả lời mẫu, không gọi mạng, nội dung không có giá trị thật).
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

Nếu mô hình hết thời gian hoặc bị giới hạn lượt gọi, hộp thoại đề nghị mô hình khác. Hệ thống **không tự đổi mô hình**. Chương đã viết xong vẫn còn.

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

**Chuẩn bị một lần:** chạy lệnh `agy` trong Terminal và đăng nhập Google. Sau đó tải lại trang. Nếu `agy` chưa cài hoặc chưa đăng nhập, ô mô hình ghi "(không dùng được)" kèm lời nhắc chạy `agy` một lần trong Terminal.

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

**Lỗi tác vụ mô hình**: `timeout` (không trả lời kịp, thử mô hình khác), `rate_limit` (hết hạn mức hoặc lượt, thử mô hình khác), `auth` (chưa đăng nhập `agy` hoặc khóa bị từ chối), `config` (chưa cài `agy`, chưa đặt khóa, hoặc tên mô hình lạ), `parse` / `validation` (câu trả lời không đọc được hoặc không qua kiểm tra, ngay cả sau một lần thử lại; câu trả lời được giữ ở ô Dán), `conflict` (dàn ý chưa duyệt).

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

Chọn mô hình **Mock**. Trong ô ghi chú có thể gõ các dấu hiệu để thử các tình huống: `[mock:bad c02]` (lần viết đầu của chương c02 có ký hiệu lỗi, lần thử lại đúng), `[mock:alwaysbad c02]` (luôn lỗi, tác vụ dừng), `[mock:badoutline]` (dàn ý lần đầu không đọc được), `[mock:slow]` (chạy chậm khoảng 10 giây, để thử Hủy), `[mock:ratelimit]` (báo hết lượt).

## 6. Bước 3, 4 và 6: chưa xây dựng

Ba bước này hiện chỉ là màn hình thông báo trung thực, không có nút giả:

- **Giọng đọc** sẽ cho máy chủ giọng đọc đọc lời dẫn đã duyệt, cho bạn nghe thử và chọn lại từng dòng, và tạo `audio/mix.m4a` cùng `timing.json`.
- **Chọn hình** sẽ cho bạn chọn, với mỗi dòng lời dẫn, thứ hiện trên hình và thêm cảnh, rồi soạn một đề xuất storyboard để sửa ở bước Dựng hình.
- **Xuất video** sẽ dựng video cuối chất lượng cao từ storyboard đã duyệt và giọng đọc. Nếu dự án đã có tệp `.mp4` dựng sẵn (trong `render/`, `output/`, `out/` hoặc thư mục dự án), màn hình liệt kê đường dẫn và nút mở tệp.

Vì chưa có hai bước đầu, một dự án tạo từ thư viện chưa có storyboard: bước Dựng hình ở trạng thái **Khóa** với lý do ghi rõ, cho tới khi các bước đó được xây.

## 7. Bước 5: Dựng hình (trình biên tập storyboard)

Bước này để xem và sửa `storyboard.json` của một video: shot, lớp phủ (overlay), kỹ thuật, tham số, hình và thời điểm. Khung hình xem trước là ảnh thật do engine dựng, không phải ảnh giả.

### Các khu vực

- **Thanh công cụ của bước**: Lưu, Kiểm tra (số lỗi/cảnh báo), Hoàn tác, Làm lại, Đề xuất, Duyệt (và trạng thái duyệt), Xem thử 10 giây. Khi bản lưu đã được duyệt, nút **Tiếp tục** ở góc phải mở bước kế tiếp.
- **Khung xem trước (trái trên)**: ảnh thật tại vị trí đầu phát. Các khung màu K1, K2... là khóa camera của shot, kéo để đổi `cx, cy`; kéo núm vuông ở góc để đổi zoom. Khi chọn lớp phủ có tham số điểm/vùng, kéo chấm vàng để dời, kéo núm để đổi bán kính. Ô "Ảnh gốc" cho xem toàn ảnh để kéo khung dễ hơn. Ô "Hiện vùng" hiện tên các vùng (region) của hình.
- **Thanh phát**: shot trước/sau, phát/dừng, thời gian, từ đang đọc.
- **Bảng bên phải**: tab *Shot* (kỹ thuật, slot hình, thời điểm bắt đầu, tham số, chuyển cảnh, khóa, ghi chú), *Lớp phủ*, *Hình* (hình của dự án, vùng, tìm kiếm Commons/The Met, tải lên), *Lỗi*.
- **Timeline (dưới)**: chương, shot (ảnh nhỏ, huy hiệu kỹ thuật), lớp phủ, từng từ (khi phóng to), sóng âm, bản đồ nhỏ.

Biểu mẫu tham số được sinh tự động từ registry (`style/gae/techniques.json` cùng các bản vá), nên kỹ thuật mới xuất hiện không cần sửa trang. Kiểu hỗ trợ: số, enum, bool, chuỗi, màu, điểm, danh sách điểm (`points`, có nút "Chọn trên ảnh" cho từng điểm), danh sách dòng (`lines`, mỗi dòng một mục), khung, camera. Kiểu lạ sẽ hiện ô JSON.

Không có phụ đề nào được vẽ lên hình. Lời thoại chỉ hiện ở timeline và thanh phát.

### Phím tắt

Chỉ chạy khi bước Dựng hình đang mở (bước Kịch bản chỉ có Ctrl+S để lưu và Ctrl+Z, Ctrl+Shift+Z để hoàn tác khi không đang gõ).

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

### Cắt, gộp, camera

- **Cắt**: mỗi nửa giữ đúng tư thế camera tại điểm cắt (zoom nội suy theo log, giống engine).
- **Gộp với shot trước**: camera của shot trước giữ nguyên mốc thời gian tuyệt đối và giữ tư thế cuối trong phần gộp; camera của shot bị gộp bỏ đi; lớp phủ của hai shot được nối lại.
- Đổi hình của một slot sẽ đặt lại camera theo hình mới (engine tính lại mặc định).

### Khóa, nguồn, duyệt

- Mọi chỉnh sửa tay đặt `source: "human"`. **Khóa** (L) nghĩa là người đã chốt mục đó: đề xuất của agent không bao giờ sửa mục khóa (kể cả khi chọn "chấp nhận tất cả").
- **Lưu** gửi bản nháp kèm `base_rev`. Nếu server đã đổi (409) trang hỏi giữ nháp hay tải lại. Nếu còn lỗi (422) trang không lưu và mở tab *Lỗi*; bấm vào một lỗi để chọn đúng mục.
- **Duyệt** chỉ bật khi đã lưu và không còn lỗi. Trạng thái: *Chưa duyệt*, *Đã duyệt*, *Duyệt cũ (đã sửa)*. Duyệt gắn với phiên bản (`rev`), sửa xong lưu lại thì phải duyệt lại.

### Đề xuất của agent

Agent ghi `projects/<id>/proposals/<id>.json`. Nút *Đề xuất* mở danh sách; mở một đề xuất để xem từng thay đổi (trước/sau), chọn Chấp nhận hoặc Từ chối cho từng cái rồi *Áp dụng*. Thay đổi chạm vào mục khóa bị gạch và không áp dụng được. Đề xuất áp lên bản đã lưu, không phải bản nháp chưa lưu.

### Xem thử 10 giây

Dựng clip 10 giây từ đầu phát (kèm âm thanh) bằng bản nháp hiện tại, rồi phát trong cửa sổ nổi. Mất vài giây. Dự án không có file âm thanh vẫn xem thử được (không có tiếng) và timeline ghi rõ "chưa có file âm thanh".

### Tìm và nhập hình

Tab *Hình*: tìm trên Wikimedia Commons hoặc The Met, chỉ nhận giấy phép PD, CC0, CC BY, CC BY-SA. Bấm *Nhập* để tải về `media/` của dự án (nên dùng bản sao, không dùng `arnolfini`). Nếu bấm "Chọn" ở slot thì hình mới được gán vào slot ngay. Nhập xong phải *Lưu* để hình nằm trong storyboard. Nếu nguồn trả 429/503, trang báo thử lại sau vài giây.

### Chưa có

- Camera của kỹ thuật có nhiều camera (ví dụ `camera_left`/`camera_right` của LAY-01) chỉ sửa được bằng ô số, chưa kéo khung được.
- Chỉ Wikimedia Commons và The Met (chưa có AIC, Rijksmuseum, Europeana).
- Khoảng 47 kỹ thuật còn lại hiện xám trong thư viện cho đến khi engine port xong.
- Chưa có chỉnh âm thanh, TTS, dựng bản cuối chất lượng cao.
- Lịch sử hoàn tác chỉ nằm trong trình duyệt, mất khi tải lại trang. Bản lưu cũ nằm trong `history/`.

## 8. Dự án nhập từ bản dựng trước

`arnolfini`, `arnolfini_edit`, `technique_lab` (và các dự án `lab_*`, `demo_*`) chỉ có storyboard, không có thư mục `source/` hay kịch bản. Các bước 1 đến 4 của chúng ghi rõ: "Dự án này được nhập từ bản dựng trước, chưa có dữ liệu cho bước này", cùng nút mở bước Dựng hình. Bước Dựng hình dùng bình thường.

## 9. Thay đổi chưa lưu

Rời một màn hình còn thay đổi chưa lưu (dàn ý hoặc lời dẫn ở bước Kịch bản, storyboard ở bước Dựng hình) luôn hỏi trước, dù bạn bấm thanh các bước, ô chọn dự án, một liên kết, hay nút Quay lại: **Ở lại**, **Bỏ thay đổi và rời đi**, hoặc **Lưu rồi rời đi**. Đóng hoặc tải lại tab cũng hỏi. Khi bạn rời một màn hình, mọi thứ nó đã bật đều tắt: bộ đếm giờ, phát âm thanh, hộp thoại đang mở, yêu cầu đang chờ. Phím tắt của màn hình này không bao giờ chạy ở màn hình khác.

Nút Quay lại của trình duyệt đã đổi địa chỉ trước khi ứng dụng kịp hỏi; nếu bạn chọn Ở lại, ứng dụng trả địa chỉ về chỗ cũ (có thể để lại một mục lịch sử trùng).

## 10. Tệp được ghi

| Nơi | Nội dung |
|---|---|
| `projects/<dự-án>/project.json`, `source/` | Dự án tạo từ thư viện: bản sao hồ sơ và văn bản nguồn. |
| `projects/<dự-án>/script/` | Kịch bản (bảng dưới). |
| `projects/<dự-án>/storyboard.json`, `history/` | Storyboard và các bản lưu cũ. |
| `library/overrides/artworks.json` | Gộp và tách tác phẩm. |

Trong `projects/<dự-án>/script/`:

| Tệp | Nội dung |
|---|---|
| `outline.json`, `narration.json` | Dàn ý và lời dẫn, kèm khối `approval` (sha1 của nội dung đã duyệt). Mã dòng (`b0001`, ...) và mã chương, dữ kiện không bao giờ bị đánh số lại hay dùng lại. |
| `outline.prev.json`, `narration.prev.json` | Bản trước của lần ghi gần nhất (một bản). |
| `last_paste.txt`, `last_paste_outline.txt` | Bản dán lỗi gần nhất, hoặc câu trả lời lỗi của mô hình. Tự xóa khi lưu thành công. |
| `brief_options.json` | Mục tiêu số từ, tốc độ đọc, sách dịch máy được phép dùng, ghi chú chung. |
