# Sửa lỗi giao diện bước "Dựng hình" (storyboard)

Người sửa: front-end, vòng sửa 2026-11-16. Báo cáo lỗi gốc: `docs/qa/BUGS_ui_storyboard.md`.
Kiểm tra: `node tests/e2e/storyboard/run.mjs` (Chrome thật, chuột và phím thật, dữ liệu chép tạm, không mạng) và `node --test tests/editor_frontend/*.test.mjs`.

Kết quả cuối: e2e **34/34 PASS** với `BE=1` (32 không cần backend mới + 2 kiểm tra `BE-*` đã đạt sau khi backend sửa xong; 16 kiểm tra gốc của người kiểm thử, chạy không sửa; 8 kiểm tra cho phát hiện mới; 8 kiểm tra độ phủ), test đơn vị JS 99/99, pytest `tests/script tests/editor tests/library` 383/383. `run.mjs` chỉ được thêm (bắt hộp thoại và lỗi trang, kiểm tra mới); các kiểm tra `BE-*` cần backend mới và chỉ chạy khi gọi tên hoặc `BE=1`.

Đường dẫn tệp trong bảng tính từ `bti/editor/static/js/`.

## Bảng 16 lỗi

| Mã | Mức | Nguyên nhân (một dòng) | Cách sửa (một dòng) | Tệp | Kiểm tra e2e gốc đạt |
|---|---|---|---|---|---|
| U2-001 | major | Gộp nối mảng lớp phủ hai shot mà không cấp lại id (`o1` hai lần), `findOverlay` tìm theo id nên luôn thấy cái đầu. | `edit.dedupeIds` chạy sau gộp (người giữ id trước giữ nguyên, trùng thì cấp id mới chưa dùng); cùng hàm chạy khi mở dự án và áp dụng đề xuất (là một sửa đổi hoàn tác được). | edit.js, views/storyboard.js | có |
| U2-002 | major | Phím tắt chỉ miễn ô nhập; không biết hộp thoại, chế độ chọn, nút đang giữ tiêu điểm. | Một hàm thuần `shortcuts.resolveShortcut` quyết định cho mọi phím (hộp thoại mở, đang gõ, control, pick, giữ phím); `storyboard.js` chỉ chạy hành động; dùng `util.modalOpen()` của shell. | shortcuts.js (mới), views/storyboard.js | có |
| U2-003 | blocker | `markSaved` thay cả bản nháp bằng bản server trả về, đè mọi sửa đổi sau khi gửi. | `Store.beginSave/finishSave`: mốc đã lưu là bản server, bản nháp giữ sửa đổi sau khi gửi (dấu chưa lưu đúng sự thật); `approvals` thuộc server (không tính chưa lưu); lưu xếp hàng; `approve` chỉ đặt approvals; câu trả lời kiểm tra cũ bị bỏ bằng `editVersion`. | store.js, views/storyboard.js | có |
| U2-004 | minor | **Thật** (tái hiện 100% trên mã cũ khi gõ lại số ngoài khoảng, xem U2-004b): ô chỉ đồng bộ khi store phát sự kiện; giá trị ép trùng giá trị đang lưu thì không có sự kiện, và hàng đang có tiêu điểm bị bỏ qua khi đồng bộ. | Rời ô thì ô hiện giá trị đã lưu kèm "đã ép về N"; min và max được ép riêng từng cận. | formui.js, formgen.js | có |
| U2-005 | minor | Không có kiểm tra điểm nằm ngoài ảnh. | `checks.outsideIssues` (cảnh báo, theo hệ tọa độ của tham số) hợp nhất với kết quả của server. | checks.js (mới), views/storyboard.js | có |
| U2-006 | major | Tab Hình ghi vùng thẳng lên server (`putRegions`) ngoài Lưu/Hoàn tác; vùng đang dùng thì bản nháp vẫn đổi dù server từ chối; đổi tên bằng `prompt()`. | Vùng là sửa đổi của bản nháp (`actions.addRegion/patchRegion/deleteRegion/renameRegion`; không gọi endpoint vùng): Hoàn tác, dấu chưa lưu, chỉ ghi khi Lưu; vùng đang dùng thì không xóa (nêu mục, nút "Tới"); đổi tên hỏi cập nhật tham chiếu; hộp thoại của ứng dụng; thêm kéo để dời và đổi cỡ vùng. | media.js, actions.js, slots.js | có |
| U2-007 | major | Vùng bắt ranh giới cố định ±5 px (bằng nửa dải ở zoom Vừa) và nhấn xuống đó bắt đầu kéo ranh giới thay vì dời đầu phát. | Vùng bắt = min(5 px, 15 % bề rộng shot hẹp hơn); nhấn luôn chọn shot và dời đầu phát, chỉ kéo thật (hơn 3 px) mới đổi ranh giới. | timeline.js, logic.js | có (22/22) |
| U2-008 | major | Widget `box` đọc/ghi `{x,y,w,h}`; registry là mảng `[x0,y0,x1,y1]`. | `coords.boxToRect/normBox`; widget bốn ô x0 y0 x1 y1 ghi đúng mảng (nút "Bỏ khung" cho khung tùy chọn); xem trước vẽ và kéo khung theo hệ của tham số. | coords.js (mới), formui.js, formgen.js, preview.js | có |
| U2-009 | major | Có nhiều ý niệm tọa độ: mọi `point(s)` bị coi là px ảnh nguồn. | `coords.js` là nơi duy nhất đổi giữa màn hình, canvas, ảnh nguồn và tỉ lệ khung; `paramSpace` nói tham số ở hệ nào (đọc từ engine; có điều kiện: `origin_space`, `space`, `background`); tay cầm, kéo, "Chọn trên ảnh" và khung quản lý vùng đều qua nó. | coords.js, preview.js, formui.js, inspector.js, media.js, logic.js | có |
| U2-010 | minor | Trang bỏ qua `proposal.stale`; danh sách im lặng bỏ tệp hỏng. | Dải "dựa trên bản cũ" và xác nhận trước khi áp dụng; danh sách đọc `{items, skipped}` nếu server báo (backend nay trả `skipped: [{file, reason}]`, trang liệt kê tên tệp và lý do; kiểm tra `U2-010b`). | proposals.js | có (cả hai nửa) |
| U2-011 | minor | `Element.append(null)` viết chữ "null". | Gom con qua `kids()` lọc null; cùng lỗi ở `media.js` (nguồn ảnh) và `proposals.js` (`replaceChildren`). | inspector.js, media.js, proposals.js | có |
| U2-012 | minor | Xem trước hiện mã trạng thái trần khi dựng khung lỗi. | `preview.frameError` nêu lý do (mục chưa đủ, hay thông điệp của server); khung hợp lệ mà chưa đủ ghi "khung tạm, thiếu ...". | preview.js | có |
| U2-013 | major | Tab Lớp phủ không có hàng slot. | `slotRow` dùng chung cho shot và lớp phủ (`overlay.slots`); `image` của lớp phủ mặc định là hình của shot ("theo shot"); chọn, bỏ, thiếu đều thấy. | inspector.js, actions.js, media.js | có |
| U2-014 | major | `setShotTechnique` gán hình cũ vào slot mới theo thứ tự, bỏ qua loại slot. | `slots.carrySlots`: giữ slot cùng tên khi loại hợp, bức tranh chỉ vào slot ảnh, không bao giờ vào video hay mask; picker chỉ liệt kê hình đúng loại; `assignSlot` từ chối loại sai. | slots.js (mới), actions.js, media.js | có |
| U2-015 | major | Chọn lớp phủ không dời đầu phát; tay cầm vẽ theo shot đã chọn lên ảnh của shot khác. | `A.selectItem` và một người nghe `select` đưa đầu phát vào mục được chọn; ngược lại dời đầu phát thì chọn lại shot; tay cầm vẽ theo shot dưới đầu phát. | actions.js, views/storyboard.js, timeline.js, inspector.js, preview.js | có |
| U2-016 | major | **Nguyên nhân tìm được trước khi sửa:** `anchorFromTime` luôn bám đầu từ gần nhất dù ở xa. Quanh 80,01 s có khoảng lặng dài (hai thẻ chữ): từ gần nhất của mọi thời điểm trong đó là từ #189 ở 80,15 s, nên ranh giới nhảy sang phải rồi đứng yên. (Test đơn vị dùng dữ liệu thật của arnolfini_edit và chứng minh cả hai đầu.) | Chỉ bám từ trong `SNAP_S` = 0,35 s, xa hơn thì neo `{t}` đi theo con trỏ; các nút "từ gần nhất" vẫn bám vô hạn. | logic.js (+ chỗ gọi: edit.js, formui.js, inspector.js) | có |

**U2-004 là thật.** Chạy trên mã cũ (cây git HEAD): gõ -5, Tab (ô 5, đạt); gõ 99999 (lưu 5000, ô hiện 99999); gõ -5 lần nữa (lưu 5, ô hiện -5); gõ -9 vào ry rồi bấm chỗ khác (lưu 5, ô hiện -9). Kiểm tra gốc chỉ gõ một lần trên trang mới nên đạt. Kiểm tra mới `U2-004b` gõ ba lần và FAIL trên mã cũ.

## Họ lỗi: các anh em đã tìm và sửa

- **Bản server đè trạng thái cục bộ (họ U2-003)**:
  - `save`: sửa gốc.
  - `approve`: coi cả bản nháp là "đã lưu", nên sửa gõ trong lúc Duyệt bị tắt dấu chưa lưu (U2-020, chạy trên mã cũ cho `dirty = false`); nay chỉ đặt `approvals`.
  - `putRegions` đặt `store.rev` từ giữa chừng: bỏ cùng U2-006.
  - Kết quả `validate` đến muộn ghi đè danh sách vấn đề của bản nháp mới hơn: bỏ câu trả lời cũ bằng `editVersion`.
  - `setShotTechnique` dùng slot chụp trước khi chờ mặc định: tính lại sau khi chờ.
  - `refitCamera` đè camera người dùng vừa kéo: bỏ qua nếu camera đã đổi; gán hình rồi đặt lại camera nay là một bước hoàn tác (trước là hai).
  - `applied()` (đề xuất) và 409 "Tải lại" chỉ chạy sau khi người dùng xác nhận bằng hộp thoại của ứng dụng (trước là `confirm()`).
  - Kiểm tra mọi nơi khác gán `store.draft`/`rev`: chỉ còn `load` (mở, áp dụng đề xuất, tải lại sau 409) và `finishSave`.
- **Phím tắt không tôn trọng trạng thái (họ U2-002)**: mọi hộp thoại (Đề xuất, thư viện kỹ thuật, xác nhận, xem thử, 409, danh sách chưa đủ); Ctrl+S sau hộp thoại (mở "lưu trang" của trình duyệt); chế độ "Chọn trên ảnh" và chọn hình cho slot (Delete xóa shot phía sau); ô `select` (chữ cái tìm nhanh kích hoạt S, L); giữ phím Delete xóa liên tiếp nhiều shot. Tất cả qua một hàm. Thêm bỏ tiêu điểm sau khi bấm nút của thanh công cụ.
- **Id không duy nhất sau thao tác (họ U2-001)**: gộp (sửa); cắt, thêm lớp phủ, xóa giữ id duy nhất (có test); đề xuất và nhập có thể mang id trùng nên `dedupeIds` chạy sau khi tải. Trang không có dán hay nhân đôi.
- **Nhiều ý niệm tọa độ (họ U2-008/009)**: khung quản lý vùng (`media.js`) và xem trước mock (`placeholder.js`) từng tự tính ánh xạ; nay đều qua `coords.makeSpaces` (`logic.makeMapping` chỉ còn là lớp mỏng). "Chọn trên ảnh" trước luôn trả px ảnh nguồn kể cả khi ô là tọa độ khung; nay theo hệ của ô. `AN-03`, `AN-06`, `AN-04`, `X-ANN-05` đổi hệ theo tham số khác (`origin_space`, `space`, `background`): tính theo giá trị hiện tại. Đã kiểm với ảnh rộng (4386 x 1200), ảnh cao (1200 x 4300), kích cỡ mặt nạ (1097 x 1500, "matte") và shot nền không có camera (có canvas và frame, không có source).
- **Chữ "null"** cũng nằm ở `media.js` (nguồn ảnh trống) và `proposals.js`.
- **Picker slot**: nút "Chọn" liệt kê hình mọi loại; nay lọc theo loại slot.
- **Slot chữ**: chữ của kỹ thuật là tham số cùng tên, hàng slot chữ ở tab Shot là ô thứ hai không có tác dụng (U2-017).

## Phát hiện mới (U2-017 trở đi, cũng ghi trong báo cáo lỗi)

Mỗi mục có kiểm tra e2e cùng tên. Đã chạy trên mã cũ (cây git HEAD) để biết là lỗi thật: FAIL trên cũ, PASS trên mới (`.scratch/fix_storyboard/old_new_checks.txt`).

| Mã | Mức | Phát hiện | Cách sửa | Kiểm tra |
|---|---|---|---|---|
| U2-004b | minor | Dạng thật của U2-004 (xem trên). | như U2-004 | PASS (cũ: FAIL) |
| U2-017 | minor | TXT-01, X-CARD-03, X-CARD-04, FOOT-01: hàng "slot chữ" ở tab Shot ghi `slots.<tên>.text` mà engine không đọc (chữ đi qua tham số `title`, `credit_text`, `text`, `label`): hai ô cho một việc, ô slot không có tác dụng. Lộ rõ khi làm slot cho lớp phủ: X-ANN-01/02 có slot chữ bắt buộc nên 29 lớp phủ của arnolfini_edit bị coi là "chưa đủ". | Không còn hàng slot chữ; slot chữ bắt buộc được thỏa bằng tham số cùng tên; ô tham số bắt buộc để trống bị tô đỏ. | PASS (cũ: FAIL) |
| U2-018 | major | Dời đầu phát khi đang phát (nhấp thước, chọn mục) bị vòng phát kéo lại về đồng hồ/âm thanh cũ (cũ: nhấp tới 300 s, 1,5 s sau đầu phát ở 2,3 s). | `resyncPlay` khi có sự kiện `time` lúc đang phát. | PASS (cũ: FAIL) |
| U2-020 | major | Sửa gõ trong lúc Duyệt đang chạy bị coi là đã lưu (cùng gốc U2-003). | `approve` chỉ đặt `approvals`. | PASS (cũ: FAIL) |
| U2-021 | minor | Áp dụng đề xuất khi bản nháp chưa lưu dùng `confirm()` của trình duyệt, trái APP_GUIDE mục 9. | `confirmDialog` của ứng dụng. | PASS (cũ: FAIL) |
| U2-002b | major | Phím tắt vẫn chạy khi chọn hình cho slot và khi ô `select` có tiêu điểm (cũ: shot bị đổi). | như U2-002 | PASS (cũ: FAIL) |
| U2-006b | major | U2-006 đầy đủ: vùng đang dùng không xóa được và nêu mục, đổi tên bằng hộp thoại ứng dụng và cập nhật tham chiếu, Hoàn tác trả vùng lại, đĩa chỉ đổi khi Lưu. | như U2-006 | PASS (cũ: FAIL) |

Một nghi vấn **không** thành lỗi: "Space sau khi bấm nút thanh công cụ nhấn lại nút" không tái hiện trên mã cũ với phím tổng hợp; giữ lại làm kiểm tra độ phủ `COV-space-button` và vẫn bỏ tiêu điểm sau khi bấm nút.

### Kiểm tra độ phủ (những chỗ người kiểm thử chưa tới)

Tất cả PASS trên mã mới: `COV-zoom` (hai đầu zoom: sàn bằng "Vừa", trần 500 px/s, nhấp vào shot ở cả hai đầu vẫn dời đầu phát), `COV-minimap` (nhấp căn giữa, kéo, không vượt hai đầu), `COV-pick` ("Chọn trên ảnh" theo hệ: ảnh nguồn trả tên vùng hay x, y; px khung hình trả [480,540] khi bấm 25 % ngang; Esc hủy), `COV-noimage` (shot không có ảnh: không lỗi trang, thông báo đúng, tay cầm theo px khung hình của STATIC-06 vẫn có), `COV-mock` (`?mock=1`), `COV-kinds` (picker mask chỉ có 9 mặt nạ, chọn xong lớp phủ hết "chưa đủ"), `COV-incomplete` (đánh dấu, lưu được, từ chối duyệt kèm danh sách), `COV-regionimage` (đổi hình của shot có lớp phủ trỏ vùng MIRROR/INSCR: hỏi, "Đổi thành tọa độ" ghi [x,y] của vùng cũ, một lần Hoàn tác trả lại cả hình lẫn tham chiếu), `COV-space-button`.

## Lưu rồi tải lại cho 71 kỹ thuật

`node tests/e2e/storyboard/techniques71.mjs save` (kết quả thô `.scratch/fix_storyboard/techniques71.json`). Với mỗi kỹ thuật của registry: đặt lên shot `s0031` (hoặc chuyển cảnh vào `s0032`) của technique_lab bằng chính hành động của trang (cùng đường với thư viện), điền slot bắt buộc bằng hình đúng loại của dự án (ảnh, mặt nạ hay video), điền chữ bắt buộc, kiểm tra, bấm Lưu thật, tải lại trang, so bản nháp trước và sau (và tệp trên đĩa), dựng một khung.

**Kết quả: 71/71 kỹ thuật lưu và tải lại đúng** (62 nền và thẻ, 4 chuyển cảnh... xem tệp thô; không lỗi mức error, không cảnh báo, khung dựng được, không lỗi console, dự án có đủ hình mọi loại cần nên không kỹ thuật nào thiếu hình).

Clip xem thử 10 giây, mẫu 10 mục (nút "Xem thử 10 giây" thật): lớp phủ HI-01, AN-01, TXT-02, STATIC-02, X-ANN-01 và chuyển cảnh TR-01, TR-04, X-TR-01, X-TR-02, TR-03: **10/10** phát được (640 x 360, 10 s). `node tests/e2e/storyboard/techniques71.mjs clips`.

## Phụ thuộc vào backend

**Cập nhật sau khi backend sửa xong:** đã chạy lại với server mới. `BE-incomplete-save` và `BE-incomplete-frame` PASS (Lưu không 422, cảnh báo `incomplete`, `/frame` trả 200). Trang dùng thêm `render_key` cho URL ảnh thu nhỏ của timeline, và hiện trạng thái 409 `corrupt`/`data_error` kèm nút "Khôi phục bản gần nhất" (`POST .../storyboard/restore`). Trang tự phân loại slot nên không cần `slots` của `/defaults`. Phần dưới là mô tả trước khi backend xong, giữ làm bối cảnh.

- **Quy tắc 2** (chưa đủ = cảnh báo `incomplete`, lưu được, khung tạm thay vì 500): trang đã dựng theo quy tắc và tự tính "chưa đủ" từ registry (slot bắt buộc trống), nên đánh dấu và từ chối duyệt chạy với server hiện tại. Cần server mới để kiểm: `BE=1 node tests/e2e/storyboard/run.mjs BE-incomplete-save BE-incomplete-frame` (shot thiếu slot: Lưu không 422 và có cảnh báo `incomplete`; `/frame` trả khung tạm). Tham số bắt buộc trống chỉ biết qua cảnh báo `incomplete` của server (registry không có cờ bắt buộc cho tham số): nhãn "thiếu: at" sẽ hiện khi server gửi.
- **Quy tắc 1** (lớp phủ có `slots`): trang ghi `overlay.slots.<tên>`; server hiện tại không kiểm slot của lớp phủ nên không báo mask thiếu (trang báo). Cần server mới để biết engine thật dựng đúng mặt nạ của lớp phủ (chưa kiểm khung có mask).
- **Quy tắc 3** (loại slot): trang tự nhận `mask` theo `type: "mask"` hoặc tên slot (`mask`, `mask_N`) và `kind` của hình; mong registry khai `type: "mask"` và server từ chối loại sai.
- **Đề xuất**: đã xong, `GET /proposals` trả `{items, skipped}`; U2-010 sửa trọn.
- **Điểm ngoài ảnh** (U2-005): trang tự cảnh báo; nếu server thêm cùng cảnh báo trên cùng đường dẫn thì trang bỏ bản của mình.

## Không sửa, và lý do

- Delete xóa shot đã khóa không hỏi: câu hỏi thiết kế, như báo cáo gốc.
- Camera của kỹ thuật nhiều camera (`camera_left`, `camera_right`) vẫn chỉ sửa bằng ô số (APP_GUIDE "Chưa có").
- Tham số theo tỉ lệ của bảng nội bộ (`to_quad`, `from_quad`) hay là một bước (`strip_step`) không có tay cầm: không có hệ tọa độ trên khung xem trước; có ô số. Tham số theo px ảnh nguồn của shot không có camera (layout) chỉ có ô số hoặc bật "Ảnh gốc".
- Tìm kiếm Commons/The Met, nhập, tải lên (cần mạng, vòng này không dùng). Tải lên chưa chọn được loại `mask` (cần API).
- Phiên dài 30 phút (bộ nhớ) chưa chạy.
- Chữ "null" cạnh tên dự án technique_lab ở khung ứng dụng (nghệ sĩ trống) thuộc người sửa shell.
- Trong lúc kiểm tra tôi đã tắt nhầm máy chủ của người sửa shell ở cổng 8568 (`.scratch/fix_shell/serve.py`, tưởng là tiến trình thừa của mình) và bật lại ngay bằng cùng lệnh (`PYTHONPATH=. .venv/bin/python .scratch/fix_shell/serve.py .scratch/fix_shell/library 8568`); biến môi trường ban đầu của tiến trình đó tôi không biết được.

## Mô-đun dùng chung và mô-đun mới

- Không sửa mô-đun dùng chung (`api.js`, `util.js`, `labels.js`, `lifecycle.js`, `app.js`, `router.js`, `stepper.js`, `nav.js`, CSS chung). Tôi dùng `util.modalOpen`, `ask`, `confirmDialog`, `modal` của shell như đã có.
- `mockapi.js` (chỉ phục vụ `?mock=1`, không thuộc hai danh sách) có sửa nhỏ: kiểm tra mock báo "chưa đủ" dạng cảnh báo và Duyệt trả 422 khi còn chưa đủ.
- Mô-đun mới: `coords.js` (một nơi đổi tọa độ), `slots.js` (loại slot, chưa đủ, vùng đang dùng), `shortcuts.js` (cửa phím tắt), `checks.js` (điểm ngoài ảnh).
- Thêm CSS vào `css/edit.css` (dấu chưa đủ, dải cảnh báo, núm vùng).
- Test đơn vị mới: `tests/editor_frontend/storyboard_fixes.test.mjs` (id, tọa độ, luồng lưu, cửa phím tắt, slot, nguyên nhân U2-016 trên dữ liệu thật, vùng bắt ranh giới, ép số, điểm ngoài ảnh).
- Tài liệu: `docs/APP_GUIDE.md` mục 7 viết lại phần tọa độ, slot theo loại, chưa đủ, phím tắt, vùng, Lưu, Duyệt, đề xuất; bỏ câu "khoảng 47 kỹ thuật còn lại hiện xám" (cả 71 chọn được, 60 `done`, 11 `partial`).
