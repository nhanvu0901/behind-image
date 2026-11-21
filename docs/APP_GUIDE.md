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
- Agent chạy trong terminal (agy, Codex, Claude) làm việc với dự án qua lệnh `bti` (mục 12) và API của ứng dụng: bắt đầu từ `AGENTS.md` ở gốc kho mã, rồi `docs/AGENT_API.md` (dự án đang ở đâu, việc gọi được ngay, lỗi và cách sửa).
- Các thao tác nhỏ cho bước Chọn hình và Dựng hình (gửi theo lô, có nhật ký và hoàn tác) nằm ở `docs/OPS.md`; cả hai tệp được sinh từ mã và một bài test trượt nếu chúng cũ.

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

Mọi bước gọi mô hình (bước 2 Kịch bản, ô sửa bằng lời của bước 4 Chọn hình, bước 5 Dựng hình) có **cùng một ô chọn agent**: `Agent: [Gemini 3.8 Flash]`. Có hai agent, mỗi cái chạy bằng chương trình của chính hãng theo gói đăng ký của bạn:

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

**Khi agent hết hạn mức**, thông báo nêu tên agent và giờ mở lại, ví dụ "Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút.", kèm **đúng một nút**: "Chuyển sang Gemini 3.8 Flash và chạy lại". Nút này lưu agent kia làm lựa chọn của bước này rồi chạy lại đúng yêu cầu vừa rồi. Hệ thống **không bao giờ tự đổi agent**. Thông báo này hiện ở hộp thoại của bước Kịch bản, ở khung Bản nháp và ở thẻ lần sửa bằng lời của bước Chọn hình và bước Dựng hình.

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

**Giọng kể.** Lời dẫn là lời của một người kể chuyện nói với người xem chưa từng nghe tên các cuốn sách, không phải bài điểm sách. Vì vậy lời dẫn **không nêu tên tác giả của sách nguồn** và không nói "các sách", "cả hai sách", "các nguồn", "đoạn ấy"; chỗ các sách bất đồng được kể thành hai cách đọc cùng một vật ("một cách đọc thấy ..., cách khác thấy ..."; "có nhà sử học cho rằng ..., người khác ..."). Chỉ gọi tên người thuộc về câu chuyện: họa sĩ, những người trong tranh, người đặt vẽ, một học giả mà đề xuất của ông là một phần lịch sử của bức tranh (như Panofsky năm 1934). **Bảng dữ kiện của dàn ý vẫn ghi đúng ai nói gì**; chỉ lời đọc là đổi. Lời nhắn của mô hình dành cho bạn (một đoạn sách có vẻ mô tả bức tranh khác, một lựa chọn chỉ bạn quyết được) nằm ở dòng "Ghi chú của mô hình cho bạn" trong hộp Kiểm tra, không nằm trong dữ kiện và không bao giờ được đọc lên.

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
2. **Lập dàn ý**. Đọc, sửa, đặc biệt: câu hỏi chính, chọn câu mở, bảng dữ kiện (kiểm tra các mã nguồn), ngân sách từ của chương. Chỗ nào các sách mâu thuẫn, mô hình phải ghi ở cột "Mâu thuẫn" (chỉ ghi các sách nói gì, không kèm lời nhắn hay lời dặn cho bạn: nếu có, hộp Kiểm tra cảnh báo); bạn là người quyết định, hệ thống không tự chọn.
3. Lưu, **Duyệt dàn ý**.
4. **Viết lời dẫn**. Thanh dưới hiện từng chương: xanh dương đang chạy, xanh lá xong, đỏ lỗi. Chương nào không qua kiểm tra (có ký hiệu trong lời đọc, dòng trống, thiếu chương) được mô hình viết lại một lần, kèm thông báo lỗi của bộ kiểm tra. Nếu vẫn lỗi, tác vụ dừng, các chương đã xong được giữ, câu trả lời lỗi nằm ở ô "Dán".
   **Độ dài.** Số từ ngân sách của chương là mức trần: prompt dặn viết nhiều nhất bằng số đó. Chương nào xong mà dài hơn ngân sách quá 10% thì được viết lại **một lần**, kèm lời nhắn nói cần cắt bao nhiêu từ và cho mô hình xem lại bản vừa viết (tối đa 4 chương mỗi lần chạy; mỗi lần viết lại là **một lần gọi mô hình thêm**). Thanh tiến độ ghi "đã cắt từ 310 xuống 247 từ", và kết quả của tác vụ (`shortened`) liệt kê các chương đó. Bản viết lại chỉ được giữ khi dùng được và gần ngân sách hơn bản đầu; nếu không, bản đầu được giữ và cảnh báo "Lệch mục tiêu" hoặc "Chương lệch ngân sách" vẫn hiện như trước. Khi còn quá dài, bấm "Viết lại chương" cho các chương ấy với ghi chú nói rõ con số ("nhiều nhất 230 từ"), hoặc tách, gộp, bỏ dòng bằng tay.
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
- Dàn ý: lấy phần sau dòng `OUTLINE` cuối cùng. Các nhãn: `THESIS:`, `HOOKS` (`h1: ...`), `HOOK CHOICE:`, `FACTS` (mỗi dòng `f01 | established | PAY-07, HOD-02 | câu khẳng định | conflict: ...`), `CHAPTERS` (mỗi chương `## c01 TÊN` rồi `ROLE:`, `CARD:`, `BUDGET:`, `PURPOSE:`, `FACTS:`, `SHOW:`), `NOTE:` (một câu nhắn cho bạn, tối đa ba dòng, ở bất cứ chỗ nào; lưu riêng, không thành dữ kiện hay mục đích chương, và mô hình viết lời dẫn không thấy), `TARGET WORDS:`. Ở lời dẫn, dòng `>>` còn nhận thêm `note: ...` (ghi chú riêng của dòng, không đọc lên).

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
| Câu quá dài (`long_sentence`) | Một dòng có câu dài hơn **25 từ**: đó là giới hạn duy nhất (prompt, bộ kiểm tra và tài liệu cùng một số). Tách câu. |
| Lời dẫn nêu tên tác giả sách nguồn (`source_author_named`) | Một dòng có họ của người viết một trong các sách của dự án ("Payne nói", "Hodge đọc là ..."). Người xem chưa từng nghe tên họ: viết lại dòng bằng giọng người kể, hoặc bấm "Viết lại chương" với ghi chú. Chỉ tính họ viết hoa nguyên từ (không tính "hitching a ride", "Hodges"), và không tính người khác trùng họ khi trước họ có một tên khác trong câu ("Sir Thomas Hodge"). Tên đầu sách không được tìm. |
| Lời dẫn nói về chính các nguồn (`source_talk`) | Một dòng nói "các sách", "cả hai sách", "các nguồn", "nguồn này", "đoạn ấy có thể mô tả bức tranh khác" hoặc mang lời nhắn dành cho chủ kênh ("chủ kênh nên kiểm tra"). Lời dẫn chỉ kể về bức tranh. "Quyển Exodus", "các cuốn sách trên bàn" không bị tính. |
| Dàn ý: dữ kiện không dẫn đoạn nguồn, mã đoạn nguồn lạ, tranh cãi chưa mô tả mâu thuẫn, dữ kiện chưa chương nào dùng, chưa chọn câu mở, tổng ngân sách lệch mục tiêu | Mỗi dữ kiện nên dẫn ít nhất một mã đoạn có trong cột Nguồn. Dữ kiện "tranh cãi" cần ghi các nguồn nói gì khác nhau. |
| Dàn ý: dữ kiện chứa lời nhắn cho bạn (`fact_for_owner`) | Chữ của một dữ kiện hoặc chỗ mâu thuẫn có lời nhắn hay lời dặn ("chủ kênh nên kiểm tra trước khi dùng", "hãy kiểm tra ..."). Lời dẫn được viết từ dữ kiện nên có thể đọc to nó: xóa câu ấy. Lời nhắn thật cho bạn thuộc dòng `NOTE:`. |
| Dàn ý: ghi chú của mô hình cho bạn (`outline_note`) | Một dòng `NOTE:` mô hình để lại cho bạn (ví dụ một đoạn sách có vẻ mô tả bức tranh khác). Đọc nó trước khi duyệt dàn ý; nó không đi vào lời dẫn. |

**Thông tin (không chặn)**

| Thông báo | Nghĩa là gì |
|---|---|
| Độ dài (`length`) | Số từ và số phút ước tính, theo tốc độ **2,41 từ/giây** (đo từ giọng này). Đổi ở cột Nguồn, ô "Từ/giây". |
| Nhịp câu (`sentence_profile`) | So độ dài câu với chuẩn kể chuyện (trung vị 12 đến 22 từ, không câu nào quá 25 từ, không quá 5% câu dưới 4 từ, và có đổi nhịp dài ngắn). |
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

### 5.9 Tựa video (viết sau khi duyệt lời dẫn)

Tựa video là một dòng mà người lạ đọc trước khi quyết định xem, và cũng là dòng hiện dưới tên kênh sau đoạn mở đầu. Ngay sau khi bạn **duyệt lời dẫn**, một agent đọc lời dẫn và viết tựa theo một bản hướng dẫn viết sẵn (`skills/title/TASK.template.md`): nó nghĩ ra ít nhất mười hai tựa, loại những tựa không đạt, chấm điểm và đưa lại từ năm đến tám tựa tốt nhất, tựa đầu tiên là lựa chọn của nó. Mỗi tựa có một câu giải thích bằng tiếng Việt và những dòng lời dẫn làm cho tựa đó đúng. Mất khoảng một phút máy, tính vào lượt dùng mô hình (như viết lời dẫn). Khi bạn cho agent tự chạy cả dự án, bước này tự làm, trước giọng đọc; không có cổng duyệt cho tựa.

Trên trang Kịch bản có khung **Tựa video** (dưới thanh nút):
- **Tựa đang dùng**, ai chọn (agent nào, hay bạn) và lúc nào. Nếu lời dẫn đã đổi sau khi agent viết tựa, khung ghi "lời dẫn đã đổi, nên viết lại" và nút **Viết lại tựa** nổi lên.
- **Các tựa agent đề xuất**: bấm vào một tựa để chọn nó. Mỗi tựa hiện số ký tự, dạng của nó, các điểm và câu giải thích.
- **Ô gõ tựa riêng**: một dòng, tối đa 60 ký tự (dài hơn bị cắt trên điện thoại và không vừa một dòng trên hình). Tựa bạn gõ hoặc chọn không bao giờ bị coi là cũ, và chạy tự động không bao giờ ghi đè lên nó; chỉ khi bạn bấm **Viết lại tựa** thì agent mới viết lại (tựa cũ được giữ trong lịch sử).
- **Viết lại tựa** (kèm ô "Điều bạn muốn", tối đa 600 ký tự): nhờ agent viết lại, ví dụ "nói về tấm gương, không phải chiếc nhẫn". Lời nhắn của bạn được đưa vào bản hướng dẫn của agent.

Đổi tựa khi dự án đã có storyboard thì storyboard được áp lại ngay với tựa mới (đoạn tên kênh đổi chữ): storyboard đổi nên **duyệt storyboard cũ không còn hiệu lực**, bạn duyệt lại. **Cùng khung đó nằm ở trang Dựng hình**, ngay dưới thanh nút (cùng một mô-đun, cùng nút **Mở**, **Viết lại tựa** và ô gõ tựa riêng): bạn xem và đổi tựa ở ngay chỗ thấy đoạn tên kênh. Nếu giọng đọc vừa được làm lại và storyboard đang lệch với nó, tựa vẫn được **lưu**, nhưng storyboard chưa nhận tựa ngay: khung ghi "Storyboard đang lệch với giọng đọc nên chưa nhận tựa này" (không báo lỗi), và nút **Khớp lại với giọng đọc** nằm cạnh khung. Bấm nút đó: storyboard khớp lại với giọng đọc và đoạn tên kênh lấy đúng tựa đang lưu. (Đổi tựa bằng `PUT /api/projects/<mã>/identity` trong lúc lệch thì bị từ chối bằng mã `storyboard_off_voice`: hãy khớp lại trước.) Chưa có tựa thì đoạn tên kênh hiện tên bức tranh và trang báo một lần. Bản dựng nháp (bước Dựng hình) chờ tựa nếu agent có thể viết nó. Tựa còn là dòng đầu tiên của mô tả video (`description.txt`) và nằm trong thư mục output ở `2_script/title.md` (cùng các tựa khác và lý do của từng tựa). Tệp của dự án: `projects/<dự-án>/title.json`.

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

**Chọn hình là gì?** Sau khi lời dẫn được duyệt, bạn quyết định mỗi đoạn lời dẫn sẽ cho xem hình gì: bức tranh chính, một chi tiết của nó, hay một hình khác. Bước này nằm giữa Kịch bản và Dựng hình. Từ khi có agent chọn hình, trang **mở ra với kết quả của agent** chứ không phải một bảng trống: bạn xem, sửa bằng lời hoặc bằng tay, rồi duyệt. Công cụ tìm và chọn hình bằng tay vẫn còn nguyên, nằm sau nút **Tự chọn tay** (phần "Tự chọn tay" dưới đây).

#### Trang mở ra như thế nào

Theo thứ tự bạn gặp từ trên xuống:

- **Dòng đầu trang**: tên dự án; **"25/28 đoạn đã có hình"** kèm một thanh nhỏ; nút vàng **"3 đoạn chưa có hình"** (bấm để nhảy tới đoạn đầu tiên chưa có hình, bấm nữa để tới đoạn kế tiếp); khi có đoạn bỏ qua thì ghi "N đoạn bỏ qua". Bên phải là nút **Kiểm tra** và nút **Duyệt chọn hình**. Khi nút Duyệt chưa bấm được, một dòng nhỏ cạnh nó nói còn thiếu gì: cần duyệt lời dẫn ở bước Kịch bản, cần chọn tranh chính, hay còn N lỗi cần sửa (bấm Kiểm tra để xem, mỗi dòng nói đoạn số mấy và hình nào, không có mã). Đoạn chưa có hình **không** chặn việc duyệt: bản nháp dùng tranh chính ở đó, trang nhắc điều này bằng một dòng.
- **Dải "Agent chọn hình"**: ô chọn agent (cùng ô như các bước khác, mục 2), nút **Để agent chọn hình** (sau lần chạy đầu thành **Chọn lại phần còn thiếu**), tiến độ khi đang chạy và câu kết quả. Chi tiết ở phần "Để agent chọn hình" bên dưới. Ô chọn agent của ô sửa bằng lời được ẩn đi trên trang này vì dải này đã có (đổi một chỗ là đổi cho cả bước).
- **Mỗi đoạn lời dẫn một hàng**, theo thứ tự, gom theo chương (bấm tên chương để thu gọn hoặc mở ra; con số bên phải là số đoạn đã có hình trên tổng số đoạn của chương). Hàng gồm: thời điểm của đoạn trong video (chỉ hiện khi giọng đọc đã xong) và số đoạn; **câu đầu** của đoạn (**Xem cả đoạn** mở phần còn lại); các hình sẽ hiện trong lúc đoạn được đọc, mỗi hình một ảnh nhỏ với chú thích bằng lời: **Cả bức tranh**, **Cận cảnh: khuôn mặt**, **Ảnh: ...**, **Bản đồ: ...**, **Clip 6 giây: ...** (dấu **!** ở góc ảnh là cờ giấy phép, chỉ để bạn biết); dấu **+** để thêm một hình (cả bức tranh, một vùng của tranh chính, hoặc "Tìm hình khác" mở Tự chọn tay; sau khi thêm, dải dưới danh sách nói "Đã thêm ... vào đoạn N." kèm nút **Hoàn tác** trong vài giây); dòng **"Agent: ..."** là lý do agent đưa ra (hết khi bạn sửa hình hoặc ghi chú của đoạn); nút **Tự chọn tay** của đoạn. Đoạn chưa có hình nói bằng chữ: "Chưa có hình. Bản nháp sẽ dùng tranh chính ở đoạn này.", kèm lý do agent không tìm được nếu lần chạy gần nhất có ghi. Hình nào không còn trong dự án hiện "Hình này không còn".
- **Chọn đoạn**: bấm vào hàng; giữ **Ctrl** (hoặc **⌘**) và bấm để chọn thêm hoặc bỏ bớt; giữ **Shift** và bấm để chọn cả một dãy; **Chọn cả chương** ở đầu mỗi chương chọn mọi đoạn của chương. Luôn có ít nhất một đoạn được chọn (mở trang là đoạn đầu). Ô **Nhờ agent sửa hình** ở bên phải nói bằng chữ phần sẽ sửa: "Đoạn 4 đang chọn", "2 đoạn đang chọn (4, 6)", "Chương: ...", "Cả video".
- **Ba mục dưới các hàng**: **Vùng của tranh chính**, **Hình bối cảnh**, **Clip** (kèm số lượng). Bấm một mục để xem ảnh nhỏ của từng thứ và nó được dùng ở những đoạn nào ("Dùng ở đoạn 4, 7" hoặc "Chưa đoạn nào dùng"); nút **Vẽ vùng trên tranh** mở khung vẽ vùng.
- **Lịch sử thay đổi** nằm dưới các lần sửa ở cột bên phải, vẫn là nơi hoàn tác từng lô (của agent hoặc của yêu cầu bạn gõ).
- **Bàn phím**: phím **/** đưa con trỏ vào ô gõ yêu cầu; Tab đi theo thứ tự đọc (đầu trang, dải agent, các hàng, ô gõ); mũi tên lên xuống đi giữa các hàng; **Esc** đóng menu của dấu **+**, và khi đang ở Tự chọn tay thì quay về danh sách.
- Chưa có tranh chính thì trang nói ngay trên các hàng ("Chưa chọn tranh chính...") với nút **Chọn tranh chính** (mở Tự chọn tay ở tab "Tranh chính"); lời dẫn chưa duyệt thì có một dòng kèm liên kết "Mở bước Kịch bản" (bạn vẫn chọn hình được, chỉ chưa duyệt được). Khi tải trang lỗi, trang nói bằng một câu và có nút **Thử lại**.
- Cửa sổ nhỏ hơn 1100 px bề ngang không phải là mục tiêu; ở 1280 x 720 và 1920 x 1080 trang không có thanh cuộn ngang, các hàng cuộn trong khung của chúng.

#### Để agent chọn hình

**Làm thay phần tự chọn tay ở dưới, bạn chỉ sửa.** Sau khi đã chọn tranh chính, dải "Agent chọn hình" ở phía trên trang có ô chọn agent (cùng ô như các bước khác, xem mục 2) và nút **Để agent chọn hình**. Bấm một lần, agent làm bốn phần liền nhau, trang hiện từng phần và việc đang làm: (1) **lập danh sách**: agent đọc lời dẫn và các dữ kiện, nhìn tranh chính rồi ghi mỗi dòng cần gì (một chi tiết của tranh kèm khung, cả bức tranh, một hình bối cảnh như chân dung họa sĩ hay một tác phẩm khác, một bản đồ khi dòng nói về *nơi chốn*, hoặc không cần hình mới) và đề xuất các khung chi tiết trên tranh chính; mỗi chương xin được tối đa một clip dài 4 đến 10 giây, và chỉ trên dòng bối cảnh (không phải dòng nói về tranh); (2) **tìm**: máy tìm ứng viên ở các nguồn miễn phí (trước tiên là Wikipedia: tra tên người, nơi chốn, đồ vật rồi lấy hình trong bài; sau đó Wikimedia Commons, The Met, ảnh trong sách của bạn, ảnh kho Pexels và Pixabay nếu máy có khóa, OpenStreetMap cho bản đồ). Bước này không gọi mô hình và **mặc định không gọi dịch vụ trả tiền (You.com)**, trừ khi bạn bật công tắc "Tìm hình trên web khi chọn hình tự động" (xem "Tìm hình trên web" ngay dưới); nguồn nào báo "quá nhiều yêu cầu" thì để yên đúng số phút nguồn ấy nêu và chỉ ghi các hình đó là chưa tìm được lúc này; (3) **chọn**: agent nhìn các tờ hình ứng viên có đánh số và nhìn từng khung chi tiết đã đề xuất, rồi chọn hình đúng hoặc nói "không hình nào chắc chắn đúng", sửa hoặc bỏ khung chưa trúng; (4) **ghi**: máy tải các hình đã chọn, tạo các vùng và ghi từng dòng bằng các thao tác có nhật ký (tên người làm là `agent:<mô hình>`), nên hoàn tác được từng lô ở nhật ký thay đổi. Agent **không bao giờ duyệt**: bạn vẫn là người bấm "Duyệt chọn hình".

- **Lời của agent dưới hình.** Mỗi dòng agent ghi có một câu lý do ngay dưới các hình của dòng ("Agent: mở bằng cả bức tranh rồi vào khuôn mặt."). Bạn sửa ghi chú của dòng thì dòng đó không còn hiện là của agent.
- **Khung chi tiết khít ("nhìn lần hai").** Khi lập kế hoạch, mỗi vùng chi tiết trên tranh chính chỉ tương ứng đúng **một** sự vật (đặt khung thô có chừa viền) và chỉ dùng bản xem thu nhỏ 1.568 px. Sau đó, ở lượt chọn hình, chương trình tự cắt từng vùng trực tiếp từ **bức ảnh gốc độ phân giải đầy đủ** (nới rộng 15% mỗi chiều, giữ trong phần mặt tranh), phóng về cạnh dài 1.024 px kèm lưới tọa độ 100 px để agent đo sát mép sự vật (không chừa viền thừa), rồi vẽ khung xanh lên tờ kiểm tra (tối đa 6 vùng một tờ) cho agent duyệt lại một lần trước khi đánh dấu `khít`. Với các dự án đã tạo từ trước khi có bước này, lệnh **`Đo lại khung chi tiết`** (`picks.tighten`) chạy riêng phần nhìn lần hai cho các vùng chưa khít trên tranh chính mà không đụng vào các hình đã chọn của từng câu; khi khung thay đổi, duyệt chọn hình tự động bỏ hiệu lực để bạn duyệt lại.
- **Kết quả** là một câu, ví dụ "Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp.", kèm danh sách các đoạn chưa có hình và lý do bằng lời thường (không tìm thấy, nguồn đang giới hạn lượt tải, agent không chắc hình nào đúng...). Đoạn nào không tìm được hình thì **để nguyên như cũ**, không ghi gì. Nút **Chọn lại phần còn thiếu** chạy lại cho đúng các đoạn chưa có hình.
- **Chỉ làm các dòng chưa có hình.** Dòng bạn đã chọn (hoặc đã bỏ qua) không bị đụng tới; dòng bạn chọn trong lúc agent đang chạy cũng được giữ. Khi mọi dòng đã có hình, hoặc chọn hình đã được duyệt, bấm nút sẽ hỏi trước: agent chọn lại tất cả sẽ thay hình hiện có (hoàn tác được) và chọn hình phải duyệt lại.
- **Không chạy mãi.** Mỗi lần agent làm việc có giới hạn 20 phút và 80 bước (hiện cả hai trong dòng tiến độ), và chỉ được nhắc sửa một lần nếu tệp kết quả chưa đạt; quá giới hạn mà chưa có kết quả dùng được thì việc dừng kèm một câu nói rõ. Nút **Dừng** dừng ngay; bấm bắt đầu lần nữa thì làm tiếp từ phần đã xong (không hỏi lại agent phần đã có, không ghi lại dòng đã ghi).
- **Hết hạn mức**: thông báo nêu tên agent và giờ mở lại, kèm đúng một nút "Chuyển sang <agent kia> và chạy lại" (mục 2). Hệ thống không tự đổi agent.
- Tệp tạm của lần chạy nằm ở `projects/<mã dự án>/cache/picks_auto/` (xóa được); API và lệnh: `docs/AGENT_API.md` mục 7.

#### Tìm hình trên web (tùy chọn, có tốn tiền)

Trong **Cài đặt** có công tắc **Tìm hình trên web khi chọn hình tự động**, **mặc định tắt**. Khi bạn bật, nếu một đoạn nói về điều không có trong tranh mà Wikipedia và các nguồn miễn phí chưa có hình đúng, agent chọn hình tìm thêm trên web bằng dịch vụ You.com: một lần tìm cho đoạn còn ít ứng viên, rồi tìm lại sau lượt chọn đầu cho mọi đoạn agent trả lời "không hình nào đúng", rồi agent nhìn riêng các hình mới tìm một lần nữa. Mỗi lần chạy tìm tối đa 80 lượt (tốn tiền), nên nút ghi "tối đa 80 lượt tìm trên web"; câu kết quả nói đã tìm bao nhiêu lượt, và đoạn nào chưa tìm được vì hết lượt thì ở lại chưa có hình, để bạn tự chọn. Hình tìm trên web **chưa rõ giấy phép** nên được đánh dấu để bạn xem lại, và không bao giờ có hình của kho ảnh có chữ đóng dấu. Agent không tự bật được công tắc này; tắt thì không tốn khoản nào.

#### Dòng nói về thứ ngoài bức tranh

Có những dòng lời dẫn nói về thứ **không có trong tranh**: một người, một nơi, một đồ vật, một sự kiện, một phong tục. Với các dòng ấy, agent không cho tranh chính ở đó cho xong việc: ứng dụng đi tìm **hình thật của chính thứ đó** (trước tiên trong bài Wikipedia về nó, rồi ở Wikimedia Commons, The Met, ảnh trong sách của bạn và các nguồn miễn phí khác, và trên web nếu bạn đã bật công tắc ở trên). Mỗi dòng nói về điều ngoài tranh được tìm qua ba bước trước khi quay về tranh chính: (1) chính sự vật đó; (2) thứ cùng loại từ cùng thời kỳ (tiểu họa, tranh in mô tả cảnh tương tự); (3) một hiện vật thực tế còn sót lại trong viện bảo tàng. Chỉ khi cả ba bước đều không tìm được gì, dòng đó mới dùng chi tiết gần nhất của bức tranh. Nếu vẫn chưa tìm được hình đúng, dòng đó **không bị bỏ trống**: nó hiện chi tiết gần nhất của tranh (hoặc cả bức tranh) mà agent đã chọn sẵn từ đầu, và được **ghi vào danh sách "Cảnh báo"** ("Đoạn 7 nói về thứ ngoài bức tranh nhưng chỉ có tranh chính: chưa tìm được hình của chính thứ đó") để bạn tự chọn hình thay. Khi chạy tự động, nếu **hơn khoảng một phần ba** số dòng loại này (đúng hơn là hơn 34%) chưa có hình riêng thì lần chạy **dừng ở cổng chọn hình** để bạn xem; bằng hoặc dưới ngưỡng đó nó vẫn đi tiếp và nói rõ có bao nhiêu dòng như vậy.

#### Nhờ agent sửa hình (ô sửa bằng lời)

Ở cột bên phải có ô **Nhờ agent sửa hình** (ở Tự chọn tay vẫn mang tên cũ, **Sửa chọn hình bằng lời**), làm việc y như ô của bước Dựng hình (mục 7, "Sửa video bằng lời") nhưng trên chọn hình. Phần sẽ sửa là các **đoạn lời dẫn** bạn chọn: mặc định là đoạn đang chọn; ba nút **Đoạn**, **Chương** và **Cả video** đổi phạm vi; chọn nhiều đoạn bằng Ctrl hoặc Shift ở danh sách (ở Tự chọn tay thì bật **Chọn nhiều dòng** rồi bấm các dòng ở cột trái). Agent nhận lời dẫn của các dòng đó, các hình của dự án với tên, vùng và nơi mỗi hình đang được dùng, và chỉ được **sắp lại, thêm, bỏ hình và vùng mà dự án đã có**; đổi tranh chính hoặc vùng chỉ có khi bạn chọn cả video. Một lần gọi không tìm hình và không nhìn hình, nên yêu cầu cần **một hình dự án chưa có** (một bản đồ, một tranh khác) hoặc cần ai đó **nhìn tranh** để tìm một chi tiết được trả lời **Cần làm kỹ hơn**: thẻ nói còn thiếu gì và có hai nút. **Để agent chọn hình** (lựa chọn đầu, ghi rõ "mất vài phút") giao đúng các dòng của lần sửa đó, kèm nguyên lời bạn gõ, cho agent chọn hình ở thanh phía trên: thẻ chuyển sang "đang chạy", hiện từng phần việc (lập danh sách, tìm hình, chọn hình, ghi), có nút **Dừng**, rồi nói kết quả một câu ("Agent đã chọn hình cho 1/1 đoạn.") kèm câu mô tả từng đoạn đã đổi, và dòng nào chưa có hình phù hợp. Agent chỉ làm đúng các dòng đó và chọn lại chúng (hình cũ của các dòng ấy bị thay, hoàn tác được); mỗi lần agent ghi là một mục trong **Lịch sử thay đổi**, hoàn tác ở đó (thẻ không có nút Hoàn tác riêng vì agent ghi nhiều lô). **Tìm hình bằng tay** (lựa chọn thứ hai) mở ô tìm. **Mỗi dự án chỉ có một việc của agent chạy một lúc**: khi agent đang chọn hình thì chưa gửi được yêu cầu sửa bằng lời (và ngược lại, cũng không dựng bản nháp hay sửa video bằng lời của bước 5), trang báo bằng một câu "Agent đang làm một việc khác cho dự án này (chọn hình, sửa bằng lời hoặc dựng bản nháp). Chờ xong hoặc bấm Dừng rồi thử lại." Có thẻ kết quả, câu mô tả của từng thay đổi, **Hoàn tác** (hoàn tác lô) và **Lịch sử thay đổi** của chọn hình như ở bước Dựng hình. Agent chọn ở ô **Agent** của bước Chọn hình (xem mục 2).

#### Tự chọn tay

Nút **Tự chọn tay** ở mỗi đoạn (hoặc "Tìm hình khác" trong menu của dấu **+**) đổi trang sang bộ công cụ cũ của bước này, mở sẵn ở đoạn đó: cột các dòng lời dẫn, cột "Dòng này" (khay hình của dòng), cột "Tìm hình" (các tab Tranh chính, Tìm kiếm, Sách, Gợi ý, Video, Tải lên) và ô sửa bằng lời. Mọi thứ làm việc đúng như trước. Nút **Về danh sách đoạn** ở đầu trang (hoặc phím **Esc** khi không đang gõ) quay về các hàng; ảnh vừa thêm hiện ngay ở hàng. Chỉ trang đơn giản mới mở đầu mỗi lần: trang không nhớ bạn đang ở mặt nào (địa chỉ có `?mode=hand` mở thẳng Tự chọn tay, dành cho đường dẫn và bài kiểm tra).

**1. Chọn tranh chính (làm đầu tiên).** Mở tab "Tranh chính" ở cột bên phải. Ô tìm đã có sẵn tên tranh và tác giả; bấm "Tìm". Kết quả lấy từ Wikimedia Commons và The Met, mỗi ảnh cho biết kích thước và giấy phép. Ảnh từ Wikimedia được lưu ở chiều rộng tối đa 3840 px, thường là 1920 hoặc 3840, vì Wikimedia phục vụ ổn định những cỡ này (thẻ ghi đúng cỡ sẽ được lưu); kích thước ghi trong dự án và các vùng bạn vẽ luôn tính theo đúng tệp đã lưu. Bấm "Làm tranh chính" ở ảnh bạn muốn. Cũng có thể lấy ảnh từ sách (tab "Sách") hoặc tải ảnh của bạn lên (tab "Tải lên").

**2. Cờ cảnh báo.** Ảnh có thể mang một cờ: "Giấy phép bị hạn chế", "Chưa rõ giấy phép" hoặc "Ảnh nhỏ" (dưới 1200 px). Cờ chỉ để bạn biết: ảnh vẫn dùng được và không bao giờ bị từ chối. Nguồn và giấy phép luôn được ghi lại để điền vào phần mô tả video.

**3. Vẽ vùng chi tiết.** Bấm "Vùng trên tranh". Bấm vào tâm của chi tiết trên tranh rồi kéo ra tới mép, đặt tên (D1, D2... là các chi tiết trong hồ sơ tác phẩm, hoặc tên tùy ý), bấm "Thêm vùng này", rồi "Lưu các vùng". Vùng dùng được ở mọi dòng.

**4. Chọn hình cho từng dòng.** Cột trái là các dòng lời dẫn theo chương, số bên phải là số hình đã chọn. Chọn một dòng: cột giữa hiện lời dẫn, các từ gợi ý hình (bấm vào để tìm), và "khay" hình của dòng. Thêm "cả tranh chính" hoặc một vùng bằng các nút nhỏ, hoặc bấm "Thêm vào dòng" ở một kết quả tìm. Mỗi hình có ô chọn vùng, vai trò (cả bức tranh, chi tiết, bối cảnh, so sánh, tài liệu, bản đồ, video), ghi chú, và nút đổi thứ tự hoặc bỏ. Dòng không cần hình riêng thì để trống: bản nháp sẽ dùng tranh chính ở đó. Dòng bạn không muốn tính là thiếu thì tick "Bỏ qua dòng này". Mọi thay đổi tự lưu sau chưa đến một giây.

**5. Tìm thêm.** Tab "Tìm kiếm": gõ từ khóa, hoặc bấm "Dùng chữ gợi ý của dòng này". Tab "Sách": ảnh và trang trong chính các cuốn sách của dự án. Tab "Gợi ý": nút "Gợi ý thêm" hỏi You.com nên cho xem gì. **Nút này tốn tiền**, chỉ chạy khi bạn bấm và xác nhận, tính cho từng dòng. Kết quả được giữ lại, bấm lại cho dòng đã có thì không tốn thêm.

#### Duyệt

Bấm "Kiểm tra" để xem lỗi (phải sửa: chưa có tranh chính, hình hoặc vùng không còn) và cảnh báo (không chặn: dòng chưa có hình, ảnh có cờ). Rồi bấm "Duyệt chọn hình". Chỉ duyệt được khi lời dẫn đã duyệt. Nếu sau đó bạn sửa hình hoặc sửa lời dẫn, bước này cần duyệt lại và bước Dựng hình sẽ nói bản nháp cũ không còn khớp.

**Nếu có sự cố.** "Nguồn ảnh đang bận": đợi vài giây rồi tìm lại, hoặc bỏ tick một nguồn. "Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng N phút": nguồn (thường là Wikimedia Commons) tự báo phải chờ; ứng dụng không thử lại dồn dập, hãy đợi đúng số phút đó rồi bấm lại, hoặc dùng nguồn khác. "Tệp ảnh bị cắt dở": tải lại tệp đầy đủ. "Chọn hình đã đổi ở nơi khác": trang tự tải lại bản mới nhất; phần bạn vừa sửa chưa lưu sẽ mất.

## 7. Bước 5: Dựng hình (trình biên tập storyboard)

Bước này dựng video từ giọng đọc và hình đã chọn. Trang có **hai mặt** trên cùng một video, cùng một khung xem trước và cùng một ô gõ yêu cầu: **trang đơn giản** (mặc định) cho bạn thấy video và danh sách các cảnh bằng lời thường, và **Chỉnh tay** là trình biên tập đầy đủ (dòng thời gian, bảng tham số, thư viện kỹ thuật). Dự án chưa có storyboard thì trang mở khung "Bản nháp storyboard" (mục "Bản nháp storyboard" dưới đây) cho tới khi có bản đầu tiên.

### Trang mở ra như thế nào (danh sách cảnh)

Theo thứ tự bạn gặp:

- **Dòng đầu trang**: "Dựng hình", tên dự án, **"93 cảnh · 14:24"** (số cảnh và độ dài). Khi có cảnh lỗi: nút đỏ **"2 cảnh cần sửa"** (bấm để nhảy tới cảnh đầu tiên cần sửa, bấm nữa để tới cảnh kế tiếp) và, nếu có lỗi không thuộc cảnh nào, **"N vấn đề chung của video"**. Bên phải: nút **Chỉnh tay**; nút **Duyệt** (sau khi duyệt là "Đã duyệt" và nút **Tiếp tục: Xuất video**). Khi chưa duyệt được, một dòng nhỏ nói vì sao ("Còn 2 cảnh cần sửa nên chưa duyệt được.", "Lưu rồi mới duyệt được."); bấm Duyệt lúc đó mở danh sách các chỗ cần sửa, mỗi chỗ một câu tiếng Việt ("Cảnh 12: còn thiếu một hình hoặc một thông tin bắt buộc.") kèm nút **Xem** (tới cảnh trong danh sách) và **Sửa ở Chỉnh tay** (mở trình biên tập đúng cảnh đó). Có chỗ sửa chưa lưu (làm ở Chỉnh tay rồi quay lại) thì hiện "Có chỗ sửa chưa lưu" và nút **Lưu**.
- **Video** ở bên trái: đúng khung xem trước và thanh phát của trình biên tập (Space phát/dừng, `[` và `]` chuyển cảnh, mũi tên trái phải chuyển từ). Ở 1280 x 720 khung xem trước cao ít nhất 300 px. Dưới khung là phần **cảnh đang xem**: số cảnh, từ giây nào đến giây nào, một câu nói cảnh làm gì, lời đang đọc trong cảnh, các chỗ cần sửa của cảnh, và nút **Sửa cảnh này ở Chỉnh tay**.
- **Danh sách cảnh** ở giữa, mỗi cảnh một hàng: số cảnh, thời điểm bắt đầu, ảnh nhỏ của khung hình, **một câu** nói cảnh làm gì, độ dài (kèm "đã khóa" nếu cảnh bị khóa) và, nếu có, câu mô tả chỗ cần sửa màu đỏ. Các cảnh gom theo chương: tên chương, số cảnh, thời điểm chương bắt đầu; bấm tên chương để thu gọn hoặc mở ra; nút **Chọn cả chương** chọn mọi cảnh của chương.
- **Câu của một cảnh** được làm từ tên tiếng Việt của kỹ thuật, hình và vùng cảnh dùng, và các lớp phủ trên cảnh: "Zoom vào khuôn mặt · vòng sáng", "Giữ yên cả bức tranh · 2 nhãn tên", "Bản đồ: Bruges tới Lucca", "Trục thời gian: 6 mốc", "Thẻ chương: ...", "Hai ô: cả bức tranh và ảnh “...”". Không bao giờ hiện mã kỹ thuật, mã cảnh, tên tệp hay tên tham số; khi không biết gì về cảnh thì ghi "Một cảnh". Vùng của tranh được gọi bằng nhãn của nó (nhãn tiếng Việt viết như nó, nhãn bằng chữ khác đặt trong ngoặc kép, nhãn chỉ là mã thì ghi "một chi tiết của tranh"); cảnh không ghi vùng nhưng máy quay dừng trong một vùng đã đặt tên thì câu nêu vùng đó.
- **Chọn cảnh**: bấm một hàng thì cảnh được chọn và video nhảy tới đó (như khi chọn trong trình biên tập); giữ **Ctrl** (hoặc **⌘**) và bấm để chọn thêm hoặc bỏ bớt, giữ **Shift** và bấm để chọn một dãy. Mũi tên lên xuống đi giữa các hàng; phím **/** đưa con trỏ vào ô gõ yêu cầu. Khi video đang phát, lựa chọn một cảnh đi theo đầu phát, còn nhiều cảnh bạn đã chọn thì được giữ.
- **Ô "Sửa video bằng lời"** ở bên phải: đúng ô và đúng thẻ của mục "Sửa video bằng lời" dưới đây (ảnh trước và sau, **Xem thử**, **Hoàn tác**, **Lịch sử thay đổi**). Phần sẽ sửa nói bằng chữ ("Cảnh 12 đang chọn", "2 cảnh đang chọn (12, 13)", "Chương: ...", "Cả video") và là các cảnh bạn chọn trong danh sách; chọn cả chương thì là cả chương đó. Ô **Chọn nhiều cảnh** của ô được ẩn ở trang này vì danh sách đã có Ctrl và Shift.
- Trang đơn giản **không** cắt, khóa hay xóa gì: phím S, L, Delete không làm gì ở đây (những việc đó ở Chỉnh tay), và các tay cầm kéo trên khung xem trước bị ẩn.

### Chỉnh tay (trình biên tập storyboard)

Nút **Chỉnh tay** ở đầu trang đổi sang trình biên tập **đúng như trước**: thanh công cụ (Lưu, Kiểm tra, Hoàn tác, Làm lại, Bản nháp, Đề xuất, Duyệt, Xem thử 10 giây), khung xem trước với các ô "Ảnh gốc" và "Hiện vùng", bảng bên phải (Shot, Lớp phủ, Hình, Lỗi), dòng thời gian, thư viện kỹ thuật và phím tắt, như mô tả từ đây trở xuống. Nút **Danh sách cảnh** ở đầu thanh công cụ quay về trang đơn giản; cảnh đang chọn được giữ. Trang **nhớ mặt bạn dùng lần cuối cho từng dự án** (trong trình duyệt này); đường dẫn cần trình biên tập (`?select=`, `?open=`, `?t=`, `?zoom=`, `?source=` hoặc `?mode=hand`) mở thẳng Chỉnh tay, còn `?mode=simple` mở thẳng trang đơn giản. Từ trang đơn giản, nút **Sửa ở Chỉnh tay** của một chỗ cần sửa mở trình biên tập ở đúng cảnh (và lớp phủ) đó, ở tab Shot hoặc Lớp phủ.

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

### Mở đầu bằng cả bức tranh, tựa video dưới tên kênh, và nút "Khớp lại với giọng đọc"

**Cảnh mở đầu.** Video làm mới bắt đầu bằng khoảng lặng 5 giây trước lời đầu tiên. Khi lời đầu tiên bắt đầu từ giây 3,3 trở đi, máy tự viết cảnh đầu tiên của video: **cả bức tranh, đủ 100 %**, từ giây 0 đến 0,35 giây trước lời đầu, hơi tiến vào chậm (không quá 3 %, mép tranh không bao giờ ra ngoài khung). Phần mở đầu vệt sáng và nhãn tên tác phẩm nằm trên cảnh này; sau đó lời dẫn mới nói tranh có gì đặc biệt hoặc lạ. Cảnh này do máy viết (trong danh sách cảnh nó đọc là "Mở đầu: cả bức tranh", mã `s0000`), mô hình không viết lại và cảnh đầu tiên của mô hình bắt đầu đúng ở từ đầu tiên. Khi lời đầu tiên bắt đầu sớm hơn giây 3,3 (video cũ) thì không có cảnh này và mọi thứ như trước.

**Tên kênh giữ lâu hơn và có tựa video.** Đoạn hiện tên kênh nay dài khoảng 9 giây: vệt sáng quét một lần hiện tên kênh, giữ một lúc, quét lần nữa hiện **tựa video** ở dòng dưới, rồi giữ thêm. Dưới tựa có một dòng nhỏ chữ hoa: tên bức tranh và tên họa sĩ, năm. Chưa đặt tựa video thì dòng tựa là tên bức tranh. Tựa video là một dòng, tối đa 60 ký tự khi gõ ở khung **Tựa video** (có ở trang Kịch bản và trang Dựng hình, xem mục 5.9); một agent có thể đặt bằng lệnh `title.set` hoặc `PUT /api/projects/{pid}/identity` với `video_title` (tối đa 90 ký tự, gõ `""` để bỏ). Đổi tựa thì chữ ở đoạn tên kênh đổi theo; việc đổi là một lần lưu (bản trước nằm trong `history/`).

**Hai khoảng lặng của giọng đọc.** Khoảng lặng trước lời đầu tiên (`lead`, 0,2 đến 15 giây) và khoảng lặng dành cho đoạn tên kênh (`title`, 3 đến 30 giây) là của từng dự án (`PUT /api/projects/{pid}/voice/settings`). Dự án tạo mới có 5 giây và 10,2 giây; dự án cũ giữ 0,35 và 6,2 giây cho tới khi bạn đổi. Đổi một trong hai thì trang Giọng đọc báo "Tốc độ hoặc nhạc nền đã đổi: cần ghép lại": máy chỉ ghép lại và đo lại thời điểm từng từ (vài phút), không đọc lại câu nào.

**Nút "Khớp lại với giọng đọc".** Thẻ chương, đoạn tên kênh và điểm cuối của video nằm ở một giây cụ thể, còn các cảnh của agent neo vào từ nào đó. Khi giọng đọc được làm lại (đổi hai khoảng lặng trên, hoặc đọc lại một câu), các từ dời đi nhưng thẻ chương và điểm cuối thì ở nguyên chỗ cũ, nên bị lệch. Khi đó trang Dựng hình hiện một dòng "Giọng đọc đã được làm lại nên thẻ chương, tên kênh hoặc điểm cuối của video đang lệch" và nút **Khớp lại với giọng đọc**. Bấm nút: máy dời thẻ chương và đoạn tên kênh về đúng chỗ giọng đọc để lại, đặt điểm cuối, thêm cảnh mở đầu cả bức tranh (hoặc bỏ nó nếu lời đầu bắt đầu sớm) và áp lại kiểu mở đầu hiện tại. Không cảnh nào do agent hoặc bạn dựng bị đổi (trừ chỗ bắt đầu của cảnh ngay sau cảnh mở đầu), cảnh đang khóa được giữ nguyên và được báo. Việc này không tốn tiền, không gọi mô hình, nằm trong *Lịch sử thay đổi* và hoàn tác được. Chưa khớp thì **Duyệt storyboard** và **Xuất video** bị từ chối ("Giọng đọc đã được làm lại nên thẻ chương..."), và duyệt cũ không còn hiệu lực vì storyboard đã đổi: duyệt lại rồi xuất.

### Trục thời gian, sơ đồ quan hệ và hai trạng thái (TIME-01, TREE-01, STATE-01)

Ba kỹ thuật làm rõ một ý trong lời dẫn. Chọn ở thư viện rồi điền ở khung tham số; mỗi danh sách sửa theo từng hàng (*+ Thêm mục*, *Xóa*, *Lên*, *Xuống*). Máy tự xếp bố cục, bạn chỉ điền dữ liệu.

- **Trục thời gian có ngày** (`TIME-01`): nền tối, một đường mảnh mọc từ trái sang, từng mốc mọc lên theo lời dẫn. Mỗi hàng của **items** là một mốc: *Năm* (số nguyên, số âm là trước Công nguyên), *Chữ ghi* (vài chữ, tối đa 48 ký tự), *Phía* (để *Tự chọn* thì máy chọn phía, độ dài cọc và chỗ đặt chữ sao cho chữ không chạm nhau và không ra khỏi khung), *Thời điểm* (giây, hoặc bấm *= đầu phát* để mốc hiện đúng lúc từ đó được đọc) và *Nhấn mạnh* (mốc quan trọng nhất: đến lúc `focus_s` nó sáng lên, có chấm trên trục, các mốc khác mờ đi; `focus_s` là số giây, hoặc bấm *= đầu phát* để nó sáng đúng lúc một từ được đọc). `from` và `to` là năm đầu và năm cuối của trục; để trống thì lấy theo các mốc, chừa một năm ở hai đầu. Một mốc nằm ngoài trục, hai đầu trục ngược nhau, hoặc quá nhiều mốc dồn quá gần nhau thì trang báo lỗi và nói rõ mục nào.
- **Sơ đồ quan hệ** (`TREE-01`): nền tối, tên với một dòng nhỏ bên dưới (năm hoặc vai trò), các nét nối mảnh vẽ dần. Mỗi hàng của **nodes** là một người (hoặc một tác phẩm): *Mã*, *Tên*, *Dòng nhỏ*, *Nổi bật* và *Thời điểm* tên hiện ra. Mỗi hàng của **edges** là một quan hệ: *Từ* và *Đến* (theo mã), *Loại quan hệ* (*Con cháu* vẽ từ cha mẹ xuống con, *Hôn nhân* là nét ngang ngắn giữa hai tên, *Quan hệ khác* cho người bảo trợ, người vẽ, người mua), chữ nghiêng nhỏ ghi cạnh nét nối và thời điểm vẽ. Để *Hàng* và *Cột* là -1 thì máy tự xếp: các thế hệ theo hướng con cháu, vợ chồng đứng cạnh nhau, ít nét cắt nhau nhất, cỡ chữ tự nhỏ lại khi sơ đồ rộng. Muốn tự đặt vị trí thì điền cả hai ô cho mọi người. Tối đa 14 người và năm thế hệ; một người có nhiều nhất hai lần kết hôn; sơ đồ không vừa khung thì trang báo lỗi.
- **Cùng một tranh ở hai trạng thái** (`STATE-01`): cần hai hình **cùng một vùng tranh** (ảnh màu và ảnh hồng ngoại, trước và sau khi phục chế) ở hai ô *a* và *b*; hình b được đặt khít lên khung của hình a nên hai hình khác độ phân giải vẫn khớp. Máy quay là một khung chung và đứng yên trong lúc tan sang hình kia. `holds` là số giây giữ từng trạng thái, ví dụ `1.5; 2.5; 1.5` (hình a, hình b rồi lại hình a), `dissolve_s` là thời gian mỗi lần chuyển, `first` chọn hình hiện trước. Góc dưới bên trái ghi tên trạng thái bằng chữ hoa nhỏ (`label_a`, `label_b`), đổi ở giữa lúc chuyển. Dự án chưa có hình thứ hai của tranh thì đừng dùng kỹ thuật này.

Cả ba ngắn hơn 3 giây thì không lưu được (trang nói rõ). Phần mô hình không đoán năm, tên hay quan hệ: mục nào chưa chắc thì bỏ ra khỏi danh sách. Ví dụ mặc định lấy từ video Arnolfini; khi dùng cho video khác phải thay toàn bộ dữ liệu mẫu.

### Bản đồ (kỹ thuật MAP-01)

Mọi câu lời dẫn nhắc một nơi, một chuyến đi hay một vùng đất đều dùng **Bản đồ atlas** (`MAP-01`). Nó thay ba kỹ thuật bản đồ cũ (`STATIC-06`, `AN-04`, `X-ANN-05`) cho video mới; storyboard cũ vẫn dùng được ba kỹ thuật kia. Bản đồ vẽ trên bờ biển thật của Natural Earth (dữ liệu công cộng, đi kèm sẵn trong dự án, không cần mạng khi dựng), nhãn chữ EB Garamond, không có khung chữ.

**Dữ liệu nó nhận** (chọn kỹ thuật ở thư viện, rồi điền ở khung tham số; mỗi danh sách sửa theo từng hàng, có nút *+ Thêm mục*, *Xóa*, *Lên*, *Xuống*):

- **places** (địa điểm): mã ngắn, tên hiện trên bản đồ, kinh độ và vĩ độ (gõ "3.2247, 51.2093"), thời điểm hiện (số giây kể từ đầu phần này, hoặc bấm *= đầu phát* để gắn vào từ lời dẫn đang phát, để chấm hiện đúng lúc từ đó được đọc) và phía đặt nhãn (để *Tự chọn* thì máy tự tìm chỗ không đè lên đường đi hay nhãn khác).
- **route** (đường đi, có thể không có): từ địa điểm nào đến địa điểm nào (theo mã), các điểm uốn (kinh độ, vĩ độ, cách nhau bằng dấu chấm phẩy), dạng cong hay thẳng, lúc bắt đầu vẽ và số giây vẽ. Đường là hàng chấm đỏ nâu có chấm đầu chạy theo.
- **region_iso** (vùng được tô): mã nước hai chữ cái theo ISO, ví dụ BE là Bỉ; **region_label** là chữ nhỏ ghi tên vùng (nằm trong vùng nếu vừa chỗ, không thì nằm ngay bên cạnh, trên chỗ trống), **region_at** là lúc vùng được tô (số giây, hoặc bấm *= đầu phát* để tô đúng lúc một từ được đọc).
- Khung nhìn: bắt đầu từ một khung rộng (`view_start_width_km`, tính bằng km) rồi máy quay đẩy chậm vào khung vừa với các địa điểm (`view_end_mode` = *Vừa các địa điểm*, chừa lề `view_end_margin_pct` phần trăm) hoặc vào một tâm và chiều rộng do bạn đặt (*Tự đặt*). Các điểm uốn của đường đi cũng được giữ trong khung.

**Hai màu biển** (`sea`): *Xanh xám* (mặc định) và *Nâu cũ*. Cả hai đều cho biển một màu riêng, đậm dần về phía bờ, có hai nét nước chạy theo bờ như atlas cổ, và đất liền sáng hơn, nên nhìn là phân biệt được đất với biển.

Nhãn địa điểm luôn nằm ở chỗ không đè lên nét bờ biển, hai nét nước, viền của vùng, đường đi hay nhãn khác (với một địa điểm nằm giữa chỗ chật, nhãn có thể cách chấm một đoạn); tên biển chỉ hiện khi nằm trọn trên mặt nước, không thì bỏ. Bản đồ dành cho nước, vùng và hành trình (khung rộng từ 300 km trở lên); khung hẹp hơn chỉ có cảnh báo "Bản đồ này quá gần", vì dữ liệu bờ biển không có chi tiết ở cỡ đó: một chỗ trong thành phố thì dùng ảnh bản đồ đường phố ở bước Chọn hình. Đường đi trên biển cần các điểm uốn nằm giữa biển, nếu không đường chấm sẽ cắt qua đất liền. Máy quay đẩy vào nhưng chữ và chấm địa điểm giữ nguyên cỡ, chỉ vị trí đi theo bản đồ. Hạt giấy và vầng tối ở góc đứng yên so với màn hình. Phần mô hình không đoán toạ độ: địa điểm nào chưa chắc thì bỏ ra khỏi danh sách. Một phần bản đồ ngắn hơn 3 giây thì không lưu được (trang nói rõ); dữ liệu địa lý và cách làm lại nằm ở `style/gae/geo/README.md`.

### Ba lớp phủ giải thích (KEY-01, NUM-01, DOC-01)

Ba lớp phủ đặt lên một shot để làm rõ đúng một ý, chữ EB Garamond, không có khung, gạch chân hay đường nối, chữ chỉ hiện và tắt bằng mờ dần (không trượt, không to lên). Chọn trong thư viện (nhóm lớp phủ), điền ở khung tham số; mỗi danh sách sửa theo từng hàng như ở bản đồ, và ô *Thời điểm* nhận số giây kể từ đầu lớp phủ hoặc một từ của lời dẫn (bấm *= đầu phát*), để chữ hiện đúng lúc từ đó được đọc.

**Nhãn chỉ các phần của tranh (`KEY-01`)** dùng khi lời dẫn gọi tên lần lượt các phần của tranh. Mỗi hàng của **labels**: chữ hiện ra (tối đa 60 ký tự), chi tiết của tranh (tên một vùng đã đặt cho tranh, hoặc hai số x, y trên ảnh gốc), phía đặt chữ (*Tự chọn* thì máy tự chọn), thời điểm hiện và kiểu chữ (*Nghiêng*, *Thường*, *Chữ hoa nhỏ*). Chữ nằm ngoài vùng của chi tiết, ở đúng phía đã chọn, đi theo máy quay của shot và giữ nguyên cỡ; các nhãn không chạm nhau và không ra khỏi khung (máy tự lo, bạn không phải sắp xếp). Tranh tối đi một chút (`dim_picture_to`) để chữ nổi. Nét nối (`leader`): *Chỉ khi nhãn bị đẩy xa chi tiết* (mặc định) chỉ vẽ một nét mảnh từ chữ tới mép chi tiết khi nhãn bị đẩy xa chi tiết, hoặc nằm đè lên chi tiết của nhãn khác nên khó biết thuộc về đâu; *Nét mảnh cho mọi nhãn* vẽ cho tất cả; *Không có nét nối* thì không bao giờ có. Khi chọn phía *Tự chọn*, máy ưu tiên chỗ tranh tối hơn để chữ dễ đọc. Chỉ nên để tối đa năm nhãn trên màn hình một lúc; các chi tiết nằm sát nhau thì chia ra hai shot cho dễ nhìn. Lớp phủ này chỉ dùng được trên shot chiếu một bức tranh qua camera; đặt lên thẻ chữ, sơ đồ hay bản đồ thì trang báo lỗi và nói rõ vì sao.

**Con số lớn và so sánh (`NUM-01`)** dùng khi lời dẫn nêu một con số hoặc so sánh các con số. Mỗi hàng của **rows** (một đến bốn hàng): nhãn nhỏ, con số (gõ đúng như muốn hiện, ví dụ 2,000), đơn vị, số chấm tròn và thời điểm. Các chấm chạy ra lần lượt trong khoảng 1,1 giây (`marks_s`) sau con số của hàng, để thấy ngay con số này gấp mấy lần con số kia; **caption** nói một chấm là bao nhiêu (hiện ra lúc các chấm đầu tiên bắt đầu chạy và ở lại đến hết), **source** là dòng nguồn nhỏ. Tranh phía sau tối đi nhiều (`dim_picture_to`), cỡ con số do `cap_pct` đặt (6 đến 14 phần trăm chiều cao khung), `align` đặt khối chữ bên trái hay bên phải. Nhiều hàng thì máy tự thu gọn cho vừa khung. Dùng được trên mọi shot.

**Dòng chữ được làm sáng (`DOC-01`)** dùng khi lời dẫn đọc hay trích một dòng nhìn thấy trong tranh (chữ ký, dòng chữ khắc, thư từ, sổ sách). Mỗi hàng của **lit**: tên vùng của tranh *hoặc* một khung `x0, y0, x1, y1` trên ảnh gốc (khung được ưu tiên), thời điểm sáng lên và số giây giữ sáng (0 là giữ cho đến khi dòng sau sáng, hoặc đến hết). Phần còn lại của tranh tối đi (`dim_to`), ô sáng có mép mềm (`edge_px`), không có viền, và đi theo máy quay của shot: để máy quay tiến vào dòng chữ thì ô sáng tiến theo. Bên dưới (hoặc bên trên nếu ô sáng xuống thấp) hiện **reading** (lời đọc hiện đại, chữ nghiêng) tại `reading_at` (số giây, hoặc bấm *= đầu phát* để hiện đúng lúc một từ được đọc), rồi 0,4 giây sau là **original** (dòng chữ như đã viết, chữ hoa nhỏ). Cũng chỉ dùng được trên shot chiếu một bức tranh qua camera.

Dữ liệu mặc định của ba lớp phủ là ví dụ trên bức Arnolfini (các nhãn đèn, bảng chữ, gương; 600 so với 2.000 tấm da sóc; chữ ký của Jan van Eyck): khi dùng cho tranh khác phải điền lại cả danh sách lẫn chữ đi kèm. Cách chạy lại ảnh mẫu, đo thời gian và làm lại xem thử: `tools/explain/render_examples.py`.

### Bản nháp storyboard

Khi dự án đã xong Giọng đọc và Chọn hình mà chưa có storyboard, bước Dựng hình không mở một bảng trống: nó hiện khung **Bản nháp storyboard**. Khi đã có storyboard, nút **Bản nháp** trên thanh công cụ mở cùng khung đó.

1. Khung cho biết giọng đọc và chọn hình đã xong chưa. Ô **Agent** (cùng ô chọn của mục 2, bước "Dựng hình") cho biết agent sẽ dựng; đổi ở đây là đổi cho cả bước Dựng hình của dự án, cả ô Agent bên hộp "Sửa video bằng lời" đổi theo. Bấm **Dựng bản nháp**. Khung ghi tên agent đã dựng ("Agent: Gemini 3.8 Flash."). Nếu agent hết hạn mức, thông báo nêu tên agent và giờ mở lại kèm một nút chuyển sang agent kia và dựng lại. Nút **Dựng tự động (không dùng agent)** làm mỗi dòng lời dẫn một cảnh từ hình bạn đã chọn, không gọi mô hình nào: dùng khi agy chưa đăng nhập, hoặc để so sánh.
2. Bạn có thể rời trang; khung hiện số bước và việc agent đang làm. **Dừng** dừng agent ngay.
3. Kết quả không bao giờ tự ghi vào dự án. Nó là một **đề xuất**; bấm **Mở đề xuất** để xem. Với dự án chưa có storyboard, bấm **Áp dụng** (chấp nhận cả đề xuất) biến nó thành storyboard đầu tiên; chọn từng thay đổi chưa dùng được ở bước này. Mục nào còn dở được ghi trong đề xuất để bạn sửa tiếp.
4. Dựng lại sau này: cảnh bạn đã khóa không bao giờ bị đổi. Nếu giọng đọc hoặc danh sách hình đã đổi sau khi dựng, khung báo "dựng từ giọng đọc hoặc danh sách hình đã đổi" và đề xuất cũ vẫn xem được.
5. Agent chỉ làm việc trong một thư mục tạm chứa bản sao; trước và sau lần chạy, ứng dụng so thư mục dự án (và, trên máy chủ, kho truyện tranh). Nếu có gì bị đổi, lần dựng bị bỏ và trang báo.
6. Dùng agy trên máy chủ cần agy đã đăng nhập trong phiên làm việc của chủ máy; nếu chưa, trang báo rõ và bạn vẫn dùng được "Dựng tự động".
7. **Ghi chú cho bản nháp.** Lệnh dựng bản nháp nhận thêm một ghi chú không bắt buộc (tối đa 600 ký tự), ví dụ "ít cận cảnh hơn, cho xem căn phòng nhiều hơn": ghi chú được đưa vào tệp việc của agent như điều bạn muốn cho lần dựng này (agent làm theo miễn là không trái các quy tắc của nó). Trang chưa có ô gõ ghi chú; agent ở cửa sổ lệnh gõ `bti do <dự án> draft.start --set note="..."`. Ghi chú dài hơn 600 ký tự bị từ chối ("Ghi chú cho bản nháp quá dài") và chưa có gì chạy.
8. **Bản nháp đầu không nên cần hai chục lần sửa.** Agent được dặn các điều sau (chi tiết ở `skills/storyboard/SKILL.md`): bức tranh đứng chỉ cho xem cả bức, nhỏ giữa hai dải đen, tối đa 5% thời lượng video (cuối cảnh mở đầu, một đầu chương và cảnh cuối), còn lại luôn một khung lấp đầy màn hình; vùng rọi sáng ít (một lần trong hai phút), nằm trong khung hình và không làm phần còn lại tối quá; không sơ đồ nền riêng trong nửa phút đầu; bản đồ atlas cho dòng nói về một nơi; chữ trên hình chỉ lấy từ lời dẫn hoặc tên của chính bức hình; và chỉ dùng hình mà một dòng lời dẫn đã chọn (hình bạn đã gỡ khỏi mọi dòng vẫn nằm trong dự án nhưng không còn được đưa cho agent). Những điều ấy cũng được kiểm tra bằng máy sau khi agent làm xong (xem mục dưới); lỗi nào còn sót, agent được nhắc sửa tối đa hai lần trước khi đưa bản nháp cho bạn.

### Những điều phần Kiểm tra bắt ở bước Dựng hình (cái người xem sẽ thấy)

Bên cạnh các lỗi (chặn lưu và duyệt), tab **Lỗi** và nút **Kiểm tra (n)** còn hiện chín **cảnh báo** về cái người xem sẽ thấy. Chúng không chặn lưu hay duyệt, nhưng đó là những kiểu bạn đã từ chối ở video đầu tiên làm trọn vòng bằng agent (bản nháp qua kiểm tra mà vẫn phải sửa hai chục lần). Mỗi cảnh báo nói cảnh nào, vì sao và nên làm gì; con số là ước tính từ camera, kích thước hình và các thông số (không dựng hình thử).

| Cảnh báo | Nghĩa là | Nên làm |
|---|---|---|
| Bức tranh chính hiện nhỏ giữa hai dải đen | Hơn 6% thời lượng video (clip dưới một phút thì không xét), bức tranh chính chỉ che dưới 60% màn hình. Bản nháp thật đầu tiên có 41 trong 109 cảnh như vậy. | Cho các cảnh ấy một khung lấp đầy màn hình (tranh rộng hết khung, đi chậm lên hoặc xuống, một dải rộng của tranh); chỉ giữ cả bức ở cuối cảnh mở đầu, một đầu chương và cảnh cuối. |
| Vùng sáng nằm sát mép hoặc ngoài khung hình | Một lớp rọi sáng mà chỗ cần sáng cách mép dưới 5% hoặc đã ra ngoài khung trong lúc rọi (thường vì máy quay vừa đổi): cả hình tối đi mà không sáng chỗ nào. | Chỉnh máy quay cho chỗ đó nằm trong khung, hoặc bỏ lớp rọi sáng. |
| Lớp rọi sáng làm khung hình gần như đen | Độ sáng trung bình của khung hình dưới 32 (thang 16 đến 235; trung vị của cả video là 55) và lớp rọi sáng lấy đi ít nhất một phần tư độ sáng. Video xuất đầu tiên có ba đoạn như thế, mỗi đoạn năm giây. Ước tính này khớp với độ sáng đo trong tệp video xuất ở cả mười bảy lớp (lệch dưới 1 đơn vị trung bình). | Bỏ lớp rọi sáng nếu máy quay đã gần sát chủ thể; nếu không thì nâng độ sáng của phần còn lại lên khoảng 0,6 (trang nêu mức vừa đủ). |
| Chữ giữ chỗ, lặp, hoặc không ai viết | Dòng chữ như "UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950", "Source: an estimate cited in the narration" (có chữ "narration"), chữ nhỏ chỉ là tên tác giả và năm lấy từ tệp hình đặt dưới một dòng chữ chính khác, hoặc cùng chữ nói hai lần liền. | Xóa, hoặc thay bằng chữ lấy từ lời dẫn hoặc tên của chính bức hình. |
| Chữ hoặc con số mà lời dẫn không nói | Nhãn bản đồ (tên nước, tên biển, địa điểm), con số, năm, tên người, dòng "đọc" của một dòng chữ trên tranh mà lời dẫn không có ("hai mươi ba" tính là 23; năm, tên hoặc tác giả của chính hình trong cảnh thì được). | Dùng đúng điều lời dẫn nói, hoặc để trống. Phần kiểm tra này không thấy chữ nằm trong ảnh, tên mà bản đồ tự vẽ từ dữ liệu của nó, hay nhãn tự do như dải chữ chỉ chi tiết. |
| Hình mà không dòng lời dẫn nào chọn | Một cảnh dùng hình mà bạn đã gỡ khỏi mọi dòng ở bước Chọn hình (ví dụ ba ảnh sóc, chồn và bột màu của video đầu tiên) và không phải bức tranh chính. | Thay bằng hình đã chọn cho phần đó hoặc bằng bức tranh chính. |
| Sơ đồ nền riêng trong nửa phút đầu | Bản đồ, trục thời gian, sơ đồ quan hệ hoặc hai trạng thái bắt đầu trước giây 30: bức tranh biến mất ngay lúc người xem vừa vào. | Nói các mốc thời gian bằng chữ số lớn ngay trên tranh, dời sơ đồ sang chương sau. |
| Cảnh ngắn hơn 1,5 giây | Cảnh sẽ nhấp nháy. | Gộp vào cảnh trước hoặc dời điểm cắt. |

**Chạy tự động** dừng ở tám cảnh báo đầu (cần bạn xem rồi duyệt hoặc nhờ agent sửa); cảnh báo "ngắn hơn 1,5 giây" được cho qua và ghi vào nhật ký. Cũng như các kiểm tra khác, các cảnh báo này nằm trong `GET /api/projects/{id}` (`issues`) và trong lệnh `bti do <dự án> storyboard.validate`.

### Đề xuất của agent

Bản nháp cả video (không phải sửa bằng lời) ghi `projects/<id>/proposals/<id>.json`. Nút *Đề xuất* mở danh sách; mở một đề xuất để xem từng thay đổi (trước/sau), chọn Chấp nhận hoặc Từ chối cho từng cái rồi *Áp dụng*. Thay đổi chạm vào mục khóa bị gạch và không áp dụng được. Đề xuất áp lên bản đã lưu, không phải bản nháp chưa lưu (trừ bản nháp đầu tiên của dự án chưa có storyboard, xem trên). Đề xuất soạn trên một bản đã cũ (storyboard đã lưu thêm kể từ đó) có dải cảnh báo "dựa trên bản cũ" và hỏi lại trước khi áp dụng. Áp dụng khi bản nháp chưa lưu cũng hỏi (hộp thoại của ứng dụng, không dùng hộp thoại của trình duyệt).

### Sửa video bằng lời

Bên phải khung xem trước ở bước Dựng hình có ô **Sửa video bằng lời**. Bạn gõ điều muốn đổi, ví dụ *"zoom chậm hơn vào chiếc gương và thêm một vòng sáng quanh nó"*, và agent sửa thẳng storyboard. Không còn "đề xuất" để chấp nhận: agent trả lời bằng **một danh sách ngắn các thao tác nhỏ** (cùng bộ thao tác của `docs/OPS.md`), máy chủ thử chạy trong đúng phần bạn đã chọn, nếu từ chối thì báo lại cho agent đúng một lần, rồi áp dụng **thành một lô** có tên trong lịch sử thay đổi. Mỗi lần sửa là một thẻ, có ảnh trước và sau, và hoàn tác được.

1. **Gõ yêu cầu** vào ô, bấm **Gửi** (hoặc Ctrl+Enter).
2. **Phần sẽ sửa** nằm ngay dưới ô, nói bằng chữ: "Cảnh 12 đang chọn", "2 cảnh đang chọn (12, 13)", "Chương: tên chương", "Cả video". Mặc định là cảnh đang chọn; bấm **Cả chương** hoặc **Cả video** để đổi. Muốn sửa nhiều cảnh: bật **Chọn nhiều cảnh**, rồi bấm vào từng cảnh trên thanh thời gian; mỗi cảnh thành một thẻ nhỏ, bấm × để bỏ. Ở trang đơn giản không có ô này: bạn chọn nhiều cảnh bằng Ctrl hoặc Shift trong danh sách. Máy chủ không bao giờ đổi cảnh ngoài phần bạn chọn, và không bao giờ đổi cảnh đã khóa (nó từ chối, bất kể agent có nghe lời hay không).
3. **Khi đang làm**, thẻ của lần sửa hiện một dòng tiến độ ("Đang nghĩ...", "Đang kiểm tra...") và nút **Dừng**. Việc nhỏ (tối đa 12 cảnh) chạy nhanh, mục tiêu vài chục giây; bạn có thể rời trang, lần sửa vẫn chạy.
4. **Kết quả** là một trong các trạng thái:
   - **Đã áp dụng**: thẻ có một câu tóm tắt của agent, rồi **từng thay đổi do máy chủ mô tả** (số cảnh, thời điểm, một câu tiếng Việt, kể cả thay đổi ở lớp phủ), kèm ảnh **Trước** và **Sau** của cảnh đã đổi. Trình biên tập tự lấy storyboard mới: nếu bạn chưa có sửa đổi chưa lưu thì tải lại và giữ nguyên cảnh đang chọn và vị trí đầu phát; nếu có, các sửa của bạn được ghép với lần sửa này.
   - **Không đổi**: agent không làm được (ví dụ cần một bức tranh mới); thẻ nói lý do bằng tiếng Việt và việc bạn có thể làm.
   - **Cần làm kỹ hơn**: việc này cần nhìn kỹ vào tranh hoặc sửa nhiều hơn phần đã chọn. Không có gì bị đổi. Nút **Làm kỹ hơn** gửi lại đúng yêu cầu đó cho agent làm việc từng bước trong một thư mục riêng; thẻ nói trước là việc này **mất vài phút**, và khi nó bắt đầu thẻ nêu giới hạn: agent tự dừng sau tối đa 30 phút, chỉ được làm lại tối đa 2 lần sau câu trả lời đầu, và bạn bấm Dừng lúc nào cũng được. Kết quả của đường này cũng được ghi **thành một lô** (thay các cảnh đã đổi), có cùng nhật ký và cùng nút Hoàn tác; sửa đổi bạn lưu trong lúc agent làm vẫn được giữ.
   - **Cần bạn chọn**: trong lúc agent làm, bạn cũng sửa đúng các cảnh đó (chỉ với đường **Làm kỹ hơn**). Chọn **Dùng bản của agent** (các sửa tay của bạn từ lúc đó sẽ mất) hoặc **Giữ bản của bạn** (bỏ lần sửa này).
   - **Không làm được**: một câu nói vì sao (ví dụ "Cảnh 6 đang khóa nên không sửa được"), kèm nút **Thử lại**. Chữ gốc của máy chủ nằm dưới "chi tiết".
   - **Đã hủy**, **Đã hoàn tác**.
5. **Xem thử** dựng một đoạn ngắn (tối đa 10 giây) ở chỗ vừa sửa. **Hoàn tác** là hoàn tác **lô** của lần sửa đó (qua nhật ký thay đổi): chỉ phần lô đã đổi được đưa về như trước, các sửa khác của bạn giữ nguyên. Nếu sau lần sửa bạn đã đổi chính phần đó, máy chủ nói rõ vì sao chưa hoàn tác được và không đổi gì; nếu bản lưu của lô đã bị xóa bớt (chỉ giữ 50 lô gần nhất) thẻ nói vậy. Các lần sửa làm trước bản này vẫn hoàn tác bằng cách cũ.
6. **Lịch sử thay đổi** (dưới danh sách các lần sửa, bấm để mở): nhật ký của storyboard, mới nhất ở trên: giờ, ai làm ("Bạn" hoặc tên agent), yêu cầu của bạn và các câu mô tả, kèm nút **Hoàn tác** ở lô mà trạng thái của dự án cho biết hoàn tác được ngay. Cả sửa bằng lời, đường **Làm kỹ hơn** và các thao tác của agent ngoài đều nằm trong danh sách này.
7. Lần sửa bắt đầu ở thẻ trình duyệt khác cũng hiện ở đây sau vài giây. **Xóa lịch sử** hỏi một lần; nó chỉ xóa danh sách các thẻ, không đổi video và không xóa nhật ký thay đổi.

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
- Cả 85 kỹ thuật đều chọn được trong thư viện (không mục nào xám; 74 `done`, 11 `partial` ở chip "Engine"; 7 trong số đó, họ `ID-*`, là kỹ thuật của kiểu mở đầu và mốc chương: mỗi cái ngắn hơn 1,5 giây thì không lưu được và trang nói rõ phần nào cần dài thêm; `MAP-01`, `TIME-01`, `TREE-01`, `STATE-01`, `NUM-01` và `DOC-01` cũng không lưu được khi ngắn hơn 3 giây, `KEY-01` khi ngắn hơn 2,5 giây). Chọn, điền slot, lưu rồi tải lại đã được kiểm tra tự động cho từng kỹ thuật (`tests/e2e/storyboard/techniques71.mjs`).
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
9. Xuất xong, ứng dụng cũng chép video vào thư mục `output/<mã tác phẩm>/` và dọn các tệp tạm của dự án để nhẹ máy (mục 15). Nghĩa là xuất **lại cùng một storyboard** sẽ dựng lại từ đầu; sửa storyboard rồi xuất thì vốn đã dựng lại từ đầu.

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
| `projects/<dự-án>/cache/picks_auto/` | Việc "Để agent chọn hình": danh sách agent lập, ứng viên đã tìm, lựa chọn, kết quả lần chạy gần nhất và lý do từng dòng; xóa được. |
| `projects/<dự-án>/proposals/` | Đề xuất (kể cả bản nháp do agent dựng). |
| `projects/<dự-án>/export/` | Video, mô tả, mục lục và `export.json`. |
| `output/<mã tác phẩm>/` | Thư mục để bạn đọc, mỗi tác phẩm một thư mục: video `final.mp4`, `README.md` và sáu phần đánh số (mục 15). Ứng dụng viết, không đọc ngược. |
| `projects/<dự-án>/cache/longjobs/` | Bản ghi và nhật ký các việc dài (giọng đọc, bản nháp, xuất video); xóa được, mất thì chỉ mất lịch sử. |
| `library/overrides/artworks.json` | Gộp và tách tác phẩm. |

Trong `projects/<dự-án>/script/`:

| Tệp | Nội dung |
|---|---|
| `outline.json`, `narration.json` | Dàn ý và lời dẫn, kèm khối `approval` (sha1 của nội dung đã duyệt). Mã dòng (`b0001`, ...) và mã chương, dữ kiện không bao giờ bị đánh số lại hay dùng lại. |
| `outline.prev.json`, `narration.prev.json` | Bản trước của lần ghi gần nhất (một bản). |
| `last_paste.txt`, `last_paste_outline.txt` | Bản dán lỗi gần nhất, hoặc câu trả lời lỗi của mô hình. Tự xóa khi lưu thành công. |
| `brief_options.json` | Mục tiêu số từ, tốc độ đọc, sách dịch máy được phép dùng, ghi chú chung. |

## 12. Cho agent tự chạy dự án và lệnh `bti`

Mặc định mọi cổng duyệt (dàn ý, lời dẫn, chọn hình, storyboard) do bạn duyệt trên trang. Một agent trong terminal (Claude Code, Codex, Antigravity) muốn duyệt thay bạn sẽ bị máy chủ từ chối.

- **Công tắc.** Khi đang mở một dự án, thanh trên cùng có nút **Agent tự chạy: tắt** (hoặc **bật**). Bấm vào là mở hộp **Cho agent tự chạy dự án này**: bật công tắc, rồi tick những cổng agent được tự duyệt (mặc định tick cả bốn: duyệt dàn ý, lời dẫn, chọn hình, storyboard). Mỗi lần đổi được lưu ngay, chỉ cho dự án đang mở (tệp `projects/<mã dự án>/auto.json`), và không đổi việc bạn tự duyệt trên trang.
- **Việc tốn tiền luôn cần bạn.** Agent không bao giờ tự chạy việc tốn tiền (ví dụ nút "Gợi ý hình"). Việc tốn giờ máy (giọng đọc, xuất video) hoặc một lần gọi mô hình chỉ chạy khi agent xác nhận rõ ràng bằng `--yes-cost`.
- **Ai đã duyệt.** Mỗi lần duyệt ghi lại ai duyệt: `human` là bạn trên trang, `cli:...` hoặc `agent:...` là một agent. Lệnh `bti status <dự án>` hiện dòng này cho cả bốn cổng.
- **Lệnh `bti`** là lệnh mỏng gọi đúng API của trang đang chạy (`tools/bti`, trên máy chủ `tools\bti.bat`; xem `docs/WINDOWS.md`). Agent bắt đầu bằng `bti status <dự án>` và chạy lệnh ở dòng cuối `next:`. Tài liệu cho agent là `AGENTS.md` và `skills/<bước>/SKILL.md`; danh sách trong đó được sinh từ mã và có bài test, nên không lệch với ứng dụng.
- **Giới hạn cần biết.** Máy chủ nhận agent qua lời tự khai (`actor`) trong yêu cầu, không phải qua đăng nhập: luật này giữ cho một agent trung thực không duyệt hoặc tiêu thứ bạn chưa cho phép, chứ không phải hàng rào bảo mật. Chỉ bạn mới đổi được công tắc (agent đổi sẽ bị từ chối).

## 13. Chạy tự động

Khi công tắc **Agent tự chạy** đang bật, bên cạnh nó có nút **Chạy tự động**. Bấm vào: ứng dụng tự đi tiếp từ chỗ dự án đang đứng cho đến khi xuất xong video, trong lúc bạn đi làm việc khác. Có thể mất vài giờ (giọng đọc khoảng một giờ, xuất video khoảng 25 phút). Nút chỉ bấm được khi công tắc đang bật và dự án chưa có việc nào đang chạy.

- **Nó làm gì.** Mỗi lần nó lấy đúng việc đầu tiên mà trang sẽ gợi ý làm tiếp (việc làm dự án tiến lên): dựng dàn ý, viết lời dẫn, đọc giọng, dựng bản nháp, áp dụng bản nháp, xuất video, và duyệt các cổng. Nó không làm gì khác: không tự sửa lời dẫn, không tự sửa storyboard, không tự chọn hình thay bạn.
- **Cổng duyệt.** Nó chỉ duyệt cổng bạn đã tick trong hộp **Cho agent tự chạy dự án này**. Trước mỗi cổng nó đọc đúng những cảnh báo mà trang cho bạn xem trước khi duyệt, và **dừng lại nếu còn lỗi, hoặc một cảnh báo thuộc loại quan trọng**: dàn ý có dữ kiện chưa ghi nguồn, nguồn lạ hay nguồn bạn đã loại, dữ kiện tranh cãi chưa nói rõ mâu thuẫn, dữ kiện chứa lời nhắn cho bạn (lời dẫn viết từ đó có thể đọc to); lời dẫn lệch độ dài quá 15%, nhắc dữ kiện không có trong dàn ý, nêu tên tác giả sách nguồn hoặc nói về chính các sách và nguồn (giọng đọc mất khoảng một giờ nên chặn trước còn rẻ hơn sửa sau); chọn hình có **hơn một phần tư số dòng lời dẫn chưa có hình** hoặc hình gắn vào dòng không còn trong lời dẫn; storyboard thiếu âm thanh, dài hơn giọng đọc, cảnh đầu không bắt đầu ở giây 0, nhãn chưa có vị trí, hình ghi sai kích thước, và tám kiểu "cái người xem sẽ thấy" (bức tranh chính nhỏ giữa hai dải đen quá lâu, vùng sáng ngoài khung hoặc làm hình gần như đen, chữ giữ chỗ hoặc lặp, chữ hay con số lời dẫn không nói, hình không dòng nào chọn, sơ đồ nền riêng trong nửa phút đầu). Các cảnh báo về cách viết (dấu câu khó đọc, câu dài, dòng chưa có gợi ý hình, ngân sách chương lệch...) và ghi chú của mô hình cho bạn (`outline_note`) nó cho qua và ghi lại trong nhật ký. Cảnh báo lạ chưa ai xếp loại cũng làm nó dừng.
- **Hai chỗ nó cho qua ở bước Chọn hình.** (1) **Hình bị gắn cờ** (ảnh nhỏ, chưa rõ giấy phép) không làm nó dừng: bản quyền không phải điều chặn, và ảnh lấy từ sách của bạn luôn mang cờ "chưa rõ"; nó ghi số hình có cờ vào nhật ký. (2) **Dòng chưa có hình**: từ một phần tư số dòng lời dẫn trở xuống nó vẫn đi tiếp (bản nháp dùng tranh chính ở các dòng đó), và nhật ký lẫn câu cuối cùng của lần chạy nói rõ có bao nhiêu dòng như vậy ("Có 3 dòng lời dẫn không có hình riêng: bản nháp dùng tranh chính ở các dòng đó."); nhiều hơn một phần tư thì nó dừng để bạn chọn hình.
- **Dòng nói về thứ ngoài bức tranh mà chưa có hình riêng** (chỉ có tranh chính, vì chưa tìm được hình của chính thứ đó; xem mục 6, "Dòng nói về thứ ngoài bức tranh"): được tính riêng, trên số dòng loại này chứ không phải trên mọi dòng. Đến khoảng một phần ba (34%) nó vẫn đi tiếp và ghi số dòng vào nhật ký; nhiều hơn thì nó dừng để bạn chọn hình.
- **Việc tốn giờ máy hoặc gọi mô hình** chỉ chạy khi bạn cho phép loại việc đó; **việc tốn tiền thì không bao giờ**. Nó cũng không bao giờ khôi phục một storyboard bị hỏng: đó là quyết định của bạn.
- **Không chạy hai việc cùng lúc** trên một dự án. Nếu bạn đang chạy một việc (ví dụ giọng đọc) thì chưa bấm được "Chạy tự động"; nếu một việc khác bắt đầu giữa chừng, nó dừng lại và nói rõ. Ngược lại, trong lúc chạy tự động, **ô sửa bằng lời (bước 4 và bước 5) và nút "Để agent chọn hình" bấm tay bị từ chối** với câu "Agent đang làm một việc khác cho dự án này...", vì chính lần chạy tự động tự làm các việc ấy từng bước; chờ nó xong hoặc bấm Dừng rồi mới dùng.
- **Theo dõi.** Dưới thanh bước hiện "Đang chạy tự động: Giọng đọc (3/6)" và nút **Dừng**. Dừng cũng dừng luôn việc nó đang chạy; bấm "Chạy tự động" lại là làm tiếp, phần đã xong được giữ.
- **Khi nó dừng**, thanh đó hiện một câu nói dừng ở đâu và vì sao, kèm liên kết tới bước đó. Các lý do: **xong** (đã xuất video, hoặc tới bước bạn yêu cầu); **cần bạn** (cổng chưa cho phép, việc chưa được phép, cảnh báo hoặc lỗi trong tài liệu, tắt công tắc giữa chừng); **bị lỗi** (việc nào, mã lỗi và câu giải thích); **chưa có việc để chạy** (dự án đang chờ gì, ví dụ chọn tranh chính); **đã dừng** (bạn bấm Dừng); **hết giới hạn** (mỗi lần chạy tối đa 40 việc và 12 giờ; bấm lại để làm tiếp).
- **Nhật ký.** Mỗi lần chạy ghi một tệp `projects/<mã dự án>/auto_runs/<mã lần chạy>.json`: từng bước (giờ, việc, kết quả, mất bao lâu) và lý do dừng; trang liệt kê qua `GET /api/projects/<mã>/auto/runs`. Lệnh cho agent là `bti run <dự án> --yes-cost --wait`.

## 14. Bộ bài kiểm cho agent (cho người làm kỹ thuật)

Các nghiên cứu cho thấy agent làm cùng một việc nhiều lần cho kết quả không ổn định, nên một lần chạy tốt chứng minh rất ít. Bộ bài kiểm chạy các yêu cầu mẫu nhiều lần và đếm xem tiêu chí nào đạt: `python -m bti.evals run --step outline --agent gemini --repeat 3 --yes-cost`. Có sáu bước (outline, narration, draft, edit_storyboard, edit_picks, picks_agent), mỗi bước vài chục ca trong `evals/cases/`, mỗi ca là một tệp JSON với tiêu chí một chương trình kiểm được (số chương, số từ, mỗi dòng không quá 90 từ, một cảnh khoảng bảy giây, chỉ sửa đúng phạm vi...). Nó làm việc trên **bản sao** của dự án mẫu, không bao giờ trên dự án của bạn, nói trước sẽ gọi agent bao nhiêu lần và chỉ chạy khi có `--yes-cost`. Kết quả là một tệp JSON, một bảng tóm tắt (mỗi ca đạt mấy lần trên mấy lần, tiêu chí nào trượt nhiều nhất) và lệnh `python -m bti.evals compare A B` cho thấy gì đổi giữa hai lần chạy (khi đổi lời nhắc hoặc đổi mô hình). Chạy lại mỗi khi đổi lời nhắc hoặc đổi mô hình. Ba bước về hình và sửa bằng lời (edit_storyboard, edit_picks, picks_agent) gọi đúng các route của ứng dụng: ô sửa bằng lời bước 5 (`draft.edit`, trả lời bằng thao tác có kiểu: một yêu cầu không làm được kết thúc là `no_change` hoặc `escalate`), ô sửa bằng lời bước 4 (`picks.edit`) và agent chọn hình (`picks.auto`); ba ca của bước chọn hình và ba ca sửa chọn hình cần một dự án mẫu có lời dẫn đã duyệt và tranh chính (dự án mẫu `arnolfini-from-books` chưa có `script/narration.json`, nên trên dự án mẫu thật các ca ấy bị bỏ qua kèm một câu nói rõ lý do). Chi tiết: `docs/qa/FIX_c6_auto.md`.

## 15. Thư mục output: mỗi tác phẩm một thư mục

Thư mục làm việc `projects/<mã dự án>/` là nơi ứng dụng làm việc: nhiều tệp tạm, bản sao cũ, ảnh không dùng. Bạn không cần mở nó. Thay vào đó, mỗi tác phẩm có **một thư mục sạch** tên theo mã tác phẩm của thư viện (ví dụ `eyck-the-arnolfini-portrait`; dự án không làm từ thư viện thì lấy mã dự án), trong thư mục `output/` nằm cạnh `projects/` (trên máy chủ: `D:\code\behind-the-image\output\`). Mở `output/INDEX.md` để thấy mọi tác phẩm và video nào đã xong.

```
output/<mã tác phẩm>/
  final.mp4          video đã xuất (có khi xuất xong)
  README.md          một trang để đọc: tác phẩm, đang ở bước nào, các bước và ngày giờ, ai duyệt, agent nào, video dài bao lâu, nên xem gì tiếp
  state.json         bản máy đọc của README
  1_sources/         văn bản các nguồn sách đã dùng, hồ sơ tác phẩm, danh sách nguồn
  2_script/          outline.md và narration.md (dàn ý, lời dẫn đọc được: chương, dòng kèm mã, số từ) cùng hai tệp JSON
  3_voice/           giọng đọc (một tệp), bản trộn âm, thời điểm từng từ
  4_pictures/        tranh chính, các hình đang hiện trên màn hình (không có hình không dùng), picks.json, regions.jpg (các vùng vẽ trên tranh chính), credits.txt
  5_storyboard/      storyboard.json, shots.md (mỗi cảnh một dòng bằng lời thường), các tờ ảnh tổng hợp video (mỗi cảnh một khung hình có số và giờ)
  6_export/          mô tả đăng video, mục lục, báo cáo kiểm tra
  log/               changes.md (từng lần sửa: lúc nào, ai, yêu cầu gì, đổi gì), jobs.md (từng việc dài: loại, agent, bao lâu, kết quả), auto_runs.md nếu có chạy tự động
```

- **Nó đầy dần theo dự án.** Nguồn sách ghi khi tạo dự án; dàn ý và lời dẫn ghi khi bạn duyệt; giọng đọc ghi khi làm xong; hình ghi khi duyệt chọn hình; storyboard ghi khi duyệt; video, các tờ ảnh tổng hợp và `6_export` ghi khi xuất xong. `README.md`, `state.json`, `log/` và `INDEX.md` được cập nhật mỗi lần.
- **Phần cũ.** Nếu sau khi ghi bạn sửa tài liệu (sửa lời dẫn, rút lại một lần duyệt, sửa storyboard), phần ấy trong thư mục được **đánh dấu "bản cũ"** trong `README.md` và `state.json`, cho tới khi bạn duyệt lại hoặc xuất lại. Nó không bao giờ nằm đó trông như còn mới.
- **Làm lại cùng một tác phẩm.** Dự án mới của cùng tác phẩm ghi đè thư mục này; mọi lần làm được giữ lại trong `state.json` (mục `runs`). Dự án cũ hơn không tự ghi đè lại.
- **Không có trong thư mục:** tệp tạm, bản sao lịch sử, hình không dùng, đề xuất cũ, mọi cấu hình của máy.
- **Dọn thư mục làm việc.** Sau khi xuất video **thành công**, ứng dụng xóa các tệp tạm của dự án: bản dựng từng đoạn (thường là phần nặng nhất, hơn một gigabyte), ảnh và đoạn xem thử, bản ghi từng lượt chạy của agent chọn hình, nhật ký dài của các việc. Tài liệu, lịch sử sửa, bản lưu cũ, hình, giọng đọc và video **không** bị xóa; dự án vẫn mở, xem thử, sửa và xuất lại được. Cái giá duy nhất: xuất lại **cùng một** storyboard sẽ dựng lại từ đầu. `README.md` ghi đã giải phóng bao nhiêu. Không dọn nếu lần xuất lỗi hay phiếu kiểm tra báo lỗi. Muốn tắt: **Cài đặt**, ô "Dọn thư mục làm việc sau khi xuất video".
- **Ghi lại từ một dự án có sẵn** (hoặc khi README báo không ghi được): `bti output <mã dự án>`; thêm `--clean` để dọn luôn các tệp tạm của dự án đã xuất xong.
- **Chép video về máy Mac:** trên Mac chạy `tools/deploy/fetch_video.sh <mã tác phẩm>`; nó chỉ chép đúng `final.mp4` về `~/Desktop/Claude Render/<mã tác phẩm>.mp4`, không chép gì khác.
- Đừng sửa tay trong thư mục `output/`: lần ghi sau sẽ ghi đè. Ứng dụng không bao giờ đọc ngược từ đó.

Khi xem storyboard, cảnh báo có thể báo chi tiết nhỏ chưa được rọi sáng,
vùng sáng chiếm quá nhiều khung hình hoặc chữ hiện quá nhanh. Hãy chỉnh cảnh
hay chữ theo gợi ý trước khi duyệt. Với dự án mới, giọng đọc mặc định ở tốc
độ 1,1; dự án cũ giữ cài đặt riêng hoặc tốc độ cũ.

Với các cảnh trên bức tranh chính do agent dựng bản nháp, chương trình tự tính
khung hình và chuyển động máy quay từ tên vùng của chi tiết (tới sớm trước lúc
gọi tên, không phóng quá giới hạn độ nét của ảnh gốc và không chạy quá nhanh);
tab kiểm tra cũng cảnh báo nếu đến cuối cảnh vùng được nhắc vẫn bị cắt mép
(`camera_off_region`) hoặc máy quay tới chi tiết quá muộn (`thing_arrives_late`).

Khi một người, vị thánh hoặc đồ vật được gọi tên lần đầu và đang hiện trên hình, bản dựng cần hiện tên ở dải dưới. Nếu danh tính còn chưa chắc, dòng nhỏ giữ cách nói thận trọng của lời dẫn; với hình mượn, dòng nhỏ có thể ghi thông tin tác phẩm có trong hồ sơ.
