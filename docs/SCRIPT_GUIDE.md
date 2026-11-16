# Hướng dẫn bước Kịch bản (dàn ý và lời dẫn)

Trang: `http://127.0.0.1:8560/script.html` (hoặc bấm "Kịch bản" ở thanh trên của Thư viện và của trang Biên tập video).

Bước này biến một tác phẩm đã chọn thành lời dẫn đã duyệt. Có hai giai đoạn, và bạn duyệt cả hai:

1. **Dàn ý**: một mô hình đọc các đoạn sách đã đánh số, rồi viết câu hỏi chính, ba câu mở đầu, bảng dữ kiện (mỗi dữ kiện dẫn mã đoạn sách, có độ chắc chắn và mâu thuẫn giữa các sách) và danh sách chương kèm số từ. Bạn sửa rồi **Duyệt dàn ý**.
2. **Lời dẫn**: mô hình viết từng chương theo dàn ý đã duyệt. Bạn sửa, cắt, tách, gộp rồi **Duyệt lời dẫn**.

Có hai đường làm, cùng dùng một prompt và một bộ đọc, nên kết quả giống nhau:

- **Nút bấm**: chọn mô hình ở ô thả xuống, bấm "Lập dàn ý" rồi "Viết lời dẫn".
- **Sao chép và dán**: bấm "Sao chép prompt", dán vào Gemini, rồi dán nguyên câu trả lời vào nút "Dán".

## 1. Màn hình

Ba cột và một thanh trạng thái.

| Cột | Nội dung |
|---|---|
| **Nguồn** (trái) | Thẻ tác phẩm, mục tiêu số từ và tốc độ đọc, các chi tiết có tên (D1, D2, ...), chỗ các sách không thống nhất, một thẻ cho mỗi sách với các đoạn đã đánh số (`PAY-07`, `HOD-02`, ...), ô tìm kiếm. Sách dịch máy có nhãn "bản dịch máy, không dùng làm nguồn sự kiện" và một ô tick để cho phép dùng. |
| **Dàn ý** (giữa) | Câu hỏi chính, chọn một trong các câu mở đầu, các chương (tên, vai trò, thẻ chương, số từ, mục đích, dữ kiện, cho xem), bảng dữ kiện (độ chắc chắn, mã đoạn nguồn, mâu thuẫn). |
| **Lời dẫn** (phải) | Các chương, mỗi chương gồm nhiều dòng (beat). Mỗi dòng là một đoạn lời đọc, sửa trực tiếp được. |
| **Thanh dưới** | Tổng số từ, số phút ước tính, thanh ngân sách từng chương, tiến độ của tác vụ đang chạy kèm nút Hủy. |

Bấm vào mã dữ kiện (`f03`) hoặc mã đoạn nguồn (`PAY-07`) ở cột giữa hoặc cột phải: đoạn sách tương ứng sáng lên ở cột trái.

### Thanh trên

| Nút | Việc làm |
|---|---|
| Ô dự án, ô mô hình | Chọn dự án. Chọn mô hình dùng cho hai nút "Lập dàn ý" và "Viết lời dẫn". Mô hình chưa dùng được vẫn hiện, ghi "(không dùng được)", chọn vào sẽ có lời giải thích. |
| **Lập dàn ý** | Mô hình viết dàn ý. Có ô ghi chú để dặn thêm. Dàn ý cũ được giữ ở `outline.prev.json`. |
| **Viết lời dẫn** | Mô hình viết lời dẫn từng chương, cần dàn ý đã duyệt. Mỗi chương xong là được lưu ngay. |
| **Sao chép prompt** | Mở hộp chứa prompt đầy đủ (dàn ý, hoặc lời dẫn cho tất cả hoặc một chương) trong ô văn bản luôn bôi đen được, kèm nút Sao chép. Nếu trình duyệt chặn bộ nhớ tạm, bấm Ctrl+C (Cmd+C) trên phần đã bôi đen. |
| **Dán** | Dán câu trả lời của mô hình. Hộp có hai thẻ: dàn ý, lời dẫn. |
| **Lưu** (Ctrl+S) | Lưu. Có kiểm tra phiên bản: nếu tệp đã đổi ở nơi khác, trang báo và không ghi đè. |
| **Hoàn tác, Làm lại** | Theo cột bạn vừa sửa. |
| **Kiểm tra (n)** | Danh sách lỗi, cảnh báo, thông tin (xem mục 5). |
| **Duyệt** | Duyệt dàn ý nếu dàn ý chưa duyệt, ngược lại duyệt lời dẫn. Chỉ duyệt khi đã lưu và không còn lỗi. |

**Mọi chỉnh sửa làm mất dấu duyệt.** Dấu duyệt gắn với mã băm (sha1) của đúng nội dung đã duyệt. Sửa một chữ là phải duyệt lại. Nếu bạn sửa dàn ý sau khi đã duyệt lời dẫn, lời dẫn vẫn giữ dấu duyệt của nó, nhưng không thể duyệt lại nó cho tới khi dàn ý được duyệt lại ("Dàn ý đã đổi sau khi duyệt").

## 2. Đường 1: dùng nút bấm

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

## 3. Đường 2: sao chép và dán

1. **Sao chép prompt**, thẻ "Prompt dàn ý". Dán vào Gemini hoặc chat bất kỳ (prompt đã bảo mô hình chỉ dùng các đoạn sách).
2. Dán nguyên câu trả lời vào **Dán**, thẻ "Dán dàn ý", bấm "Phân tích và lưu". Không cần cắt bỏ phần mở đầu, danh sách câu mở hay bảng kiểm tra: bộ đọc lấy phần sau dòng `OUTLINE` cuối cùng.
3. Sửa, duyệt dàn ý như ở trên.
4. **Sao chép prompt**, thẻ "Prompt lời dẫn" (tất cả chương, hoặc chọn một chương). Dán vào Gemini, lấy câu trả lời, dán vào thẻ "Dán lời dẫn". Hộp có ô "Chỉ thay các chương có trong bản dán" để thay một chương mà giữ các chương khác.

**Bản dán bị lỗi.** Nếu bộ đọc không đặt được văn bản vào dàn ý, **không có gì bị ghi**. Hộp hiện danh sách từng đoạn đã thấy: số thứ tự, số từ, 70 ký tự đầu, và chương mà đoạn đó nằm dưới. Nhìn danh sách là biết đoạn nào lạc chỗ. Văn bản vừa dán được **giữ lại** (`script/last_paste.txt` cho lời dẫn, `script/last_paste_outline.txt` cho dàn ý) và hiện lại trong ô Dán khi tải lại trang. Sửa tại chỗ rồi bấm lại.

### Cách bộ đọc hiểu văn bản (để biết nó bỏ qua gì)

- Lời dẫn: lấy phần sau dòng `FINAL SCRIPT` cuối cùng (không có thì lấy hết). Bỏ: hàng rào mã, danh sách câu mở, bảng, dòng đếm từ, các khối "Fact trace", "Audit", "Notes", "Sources"... (một khối như vậy sau lời dẫn kết thúc phần đọc). Dòng `## c02 TÊN CHƯƠNG` mở một chương, khớp với dàn ý theo mã, rồi theo tên (và theo thứ tự nếu bản dán không ghi mã). Mỗi đoạn là một dòng (beat). Dòng `>> facts: f03, f07 | show: cái gương; chữ phía trên` sau đoạn là thông tin phụ, không bắt buộc. Mã dữ kiện lạ được báo nhưng không làm hỏng việc đọc.
- Dàn ý: lấy phần sau dòng `OUTLINE` cuối cùng. Các nhãn: `THESIS:`, `HOOKS` (`h1: ...`), `HOOK CHOICE:`, `FACTS` (mỗi dòng `f01 | established | PAY-07, HOD-02 | câu khẳng định | conflict: ...`), `CHAPTERS` (mỗi chương `## c01 TÊN` rồi `ROLE:`, `CARD:`, `BUDGET:`, `PURPOSE:`, `FACTS:`, `SHOW:`), `TARGET WORDS:`.

## 4. Mô hình: Antigravity CLI là mặc định

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

## 5. Ý nghĩa các thông báo kiểm tra

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

## 6. Tệp được ghi

Trong `projects/<dự-án>/script/`:

| Tệp | Nội dung |
|---|---|
| `outline.json`, `narration.json` | Dàn ý và lời dẫn, kèm khối `approval` (sha1 của nội dung đã duyệt). Mã dòng (`b0001`, ...) và mã chương, dữ kiện không bao giờ bị đánh số lại hay dùng lại. |
| `outline.prev.json`, `narration.prev.json` | Bản trước của lần ghi gần nhất (một bản). |
| `last_paste.txt`, `last_paste_outline.txt` | Bản dán lỗi gần nhất, hoặc câu trả lời lỗi của mô hình. Tự xóa khi lưu thành công. |
| `brief_options.json` | Mục tiêu số từ, tốc độ đọc, sách dịch máy được phép dùng, ghi chú chung. |

Giai đoạn trong danh sách dự án: "Đã duyệt dàn ý" (dàn ý đã duyệt, còn khớp), "Có kịch bản" (lời dẫn đã duyệt, còn khớp). Sửa bất cứ chữ nào sau khi duyệt thì giai đoạn lùi lại.

## 7. Chạy thử nhanh không cần khóa

Chọn mô hình **Mock**. Trong ô ghi chú có thể gõ các dấu hiệu để thử các tình huống: `[mock:bad c02]` (lần viết đầu của chương c02 có ký hiệu lỗi, lần thử lại đúng), `[mock:alwaysbad c02]` (luôn lỗi, tác vụ dừng), `[mock:badoutline]` (dàn ý lần đầu không đọc được), `[mock:slow]` (chạy chậm khoảng 10 giây, để thử Hủy), `[mock:ratelimit]` (báo hết lượt).
