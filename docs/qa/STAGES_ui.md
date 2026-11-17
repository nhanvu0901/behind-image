# STAGES_ui: tìm lỗi giao diện các bước 3, 4, 6 và khung bản nháp (tester độc lập)

Chạy trên máy chủ Windows (một bản thứ hai của ứng dụng, cổng 8562, dữ liệu sao chép trong thư mục tạm, mọi thứ chậm hoặc bên ngoài đều giả), trình duyệt là Chrome headless trên máy Mac qua đường hầm ssh. Mã kiểm tra: `tests/e2e/stages/` (`launch.py` chạy trên máy chủ, `remote.mjs`, `run.mjs`). Ảnh chụp: `.scratch/stages_ui/shots/`.

## Cách chạy
- Mã của cây làm việc được đóng gói bằng `tools/deploy/deploy_windows.sh --pack-only` rồi giải nén vào một thư mục tạm riêng trên máy chủ (không dùng thư mục `D:\code\behind-the-image`, vì mỗi lần triển khai của agent khác sao lưu đè cả cây và lúc 23:09 đã đè lên bản của tôi bằng bản cũ hơn). Dùng lại `.venv`, `books`, `projects`, `library` của máy chủ ở chế độ chỉ đọc; dữ liệu được SAO CHÉP.
- Đồ giả đã chọn: giọng `fake`, máy đo từ `even`, mô hình `mock`, bản nháp `auto` (agy bị giấu khỏi PATH, `agy models` không bao giờ được gọi), gợi ý `FakeProvider`, Commons và Met qua dữ liệu mẫu `tests/media/fixtures`, engine/ffmpeg của bước xuất qua `fake_tools_wrap.py` (không dựng thật dù chỉ 5 khung hình: engine trên máy chủ chậm gấp 4 lần và điểm cần xem là trang, không phải điểm ảnh; ffprobe thật vẫn dùng cho tệp âm thanh thật), khóa nặng chỉ trong tiến trình.
- Ảnh thu nhỏ từ Wikimedia là địa chỉ ngoài nên Chrome bị chặn mạng ngoài (ảnh nhỏ hỏng là do thử nghiệm, không phải lỗi).

## Lỗi

Các mục dưới đây đều tái hiện ít nhất hai lần trừ khi ghi "chưa xác nhận". Tên kiểm tra nằm trong `tests/e2e/stages/run.mjs` (mỗi kiểm tra khẳng định hành vi ĐÚNG nên FAIL khi lỗi còn).

### SU-001 (minor) Chữ "null" hiện trên màn hình ở bước 3, 4, 6 và hộp Bản nháp
- Trang: Giọng đọc (cạnh nút "Tạo giọng đọc"/"Hủy", có khi hiện "nullnull"), Chọn hình (cạnh "Duyệt chọn hình"), Xuất video ("nullnullnull" dưới phần mô tả đầu trang và một "null" cuối hộp), hộp "Bản nháp" của dự án cũ.
- Cách làm tay: mở `#/project/<id>/voice` (hoặc picks, export) ở bất kỳ dự án nào đã duyệt lời dẫn.
- Mong đợi: không có chữ thừa. Thực tế: `null` (chụp `.scratch/stages_ui/shots/voice-done-1280.png`, `picks-done-1280.png`, `export-done-1280.png`). Không có lỗi console.
- Nguyên nhân: `Element.append(null)` / `replaceChildren(..., null)` in chữ "null" (hàm `h()` bỏ qua null nhưng `append` trực tiếp thì không): `bti/editor/static/js/views/voice.js:103-107` (`acts.append(... run ? ... : null ...)`), `views/picks.js:119-123` (`top.replaceChildren(... : null)`), `views/export.js` (các `append` có `? :  null`).
- Kiểm tra: `SU-001 ... no stray "null" or "undefined" text` (nhiều dòng, mỗi trang một dòng).

### SU-002 (major) Việc đọc giọng chết giữa chừng trên Windows: PermissionError WinError 5 khi đổi tên `.wav.part` thành `.wav`
- Cách làm tay (không ổn định, thấy 2 trong khoảng 8 lần): ở bước 3 bấm "Tạo giọng đọc" (hoặc "Đọc lại toàn bộ") với giọng giả; có lần kèm lưu "Tốc độ" trong lúc đang chạy.
- Mong đợi: job xong. Thực tế: job lỗi `part_failed`, "Bước "Đọc phần 1/3" bị lỗi: PermissionError: [WinError 5] Access is denied: ...\voice\chunks\<id>.wav.part -> ...\<id>.wav"; trang chỉ nói "Một bước bị lỗi bất ngờ. Bấm chạy lại để thử tiếp." (câu này ổn, bấm chạy lại thì xong). Trạng thái sau đó báo "Lời dẫn đã đổi: 47 câu cần đọc lại" (xem SU-004).
- Nguyên nhân nghi ngờ: `os.replace` không thử lại khi Windows (trình quét virus hoặc một tiến trình đang mở tệp) giữ tệp: `bti/voice/providers/fake.py:33`, `bti/voice/providers/chatterbox.py:99`, `bti/voice/assemble.py:120,157`.
- Kiểm tra: `SU-002 voice job ends done (no PermissionError)` (chạy mới nhất lại đạt; lỗi không ổn định).

### SU-003 (minor) Sửa lời dẫn sau khi có giọng, hình, storyboard và bản xuất: các trang không nói giọng cũ sẽ lỗi thời
- Cách làm tay: dự án đã xuất xong; ở bước 2 sửa một câu lời dẫn (chưa duyệt lại). Mở bước 3.
- Mong đợi: trang giải thích bản giọng đã có sẽ phải đọc lại một phần. Thực tế: "Bước này đang khóa. Cần duyệt lời dẫn ở bước Kịch bản trước." và không có nút tới bước Kịch bản; bước Dựng hình và Xuất video vẫn hiện "Xong" và "Đã xuất video" (chỉ sau khi duyệt lại lời dẫn mới hiện "Lời dẫn đã đổi: 1 câu" và sau khi đọc lại mới hiện "Cần xuất lại: giọng đọc đã đổi"). Khi đã duyệt lại và đọc lại thì mọi trang nói thật (đã kiểm tra).
- Nguyên nhân: `bti/editor/pipeline_api.py` (bước khóa không mang `work`/lý do về dữ liệu cũ), `static/js/views/placeholder.js`.
- Kiểm tra: `SU-003 ...`.

### SU-004 (minor) Đổi bảng phát âm bị báo là "Lời dẫn đã đổi"
- Cách làm tay: bước 3 đã xong; thêm dòng "Velázquez → Ve-las-kes", bấm "Lưu bảng phát âm".
- Mong đợi: "Bảng phát âm đã đổi: 17 câu cần đọc lại". Thực tế: "Lời dẫn đã đổi: 17 câu cần đọc lại." (lời dẫn không đổi). Cũng thấy ngay sau "Đọc lại câu này": hộp vàng "Lời dẫn đã đổi sau lần đọc trước".
- Nguyên nhân: lý do `narration_changed` dùng chung cho mọi câu đổi: `bti/voice/status.py` (chuỗi `Lời dẫn đã đổi`), `static/js/views/voice.js` `REASON_TEXT`.
- Kiểm tra: `SU-004 a pronunciation change is not reported as "Lời dẫn đã đổi"`.

### SU-007 (minor) Số cảnh của khung Bản nháp và của đề xuất khác nhau
- Cách làm tay: bước 5, "Dựng tự động". Khung ghi "Xong. Có 54 cảnh" (lần khác 56), hộp đề xuất ghi "Bản nháp tự động: 48 cảnh" (lần khác 50); trình biên tập sau khi áp dụng có 54 shot.
- Nguyên nhân nghi ngờ: tóm tắt đếm khác `n_shots` (thẻ chương/tiêu đề không được đếm): `bti/draft/providers/auto.py` (summary) so với `bti/draft/run.py` (`n_shots`).
- Kiểm tra: `SU-007 ...`.

### SU-008 (minor) Trang bước bị khóa không có nút đi tới bước cần làm
- Cách làm tay: dự án chưa duyệt lời dẫn, mở bước 3, 4, 5 hoặc 6; hoặc mở `#/project/arnolfini/export` (dự án cũ, bước Dựng hình mở được).
- Mong đợi: nút như "Mở bước Kịch bản" / "Mở bước Dựng hình". Thực tế: chỉ có "Về danh sách dự án" (ảnh `export-ready-1700.png`, `e-old-export-1700.png`).
- Nguyên nhân: `static/js/views/placeholder.js` (chỉ có nút Tiếp tục cho kiểu `locked` khi có bước kế).
- Kiểm tra: `SU-008 ...` (2 dòng).

### SU-009 (minor) Trang đang mở không biết việc nặng vừa bắt đầu ở thẻ khác
- Cách làm tay: mở bước 3 ở thẻ A (đang "Xong"); ở thẻ B bấm "Đọc lại toàn bộ". Thẻ A giữ nguyên "Xong", không có "Hủy", thanh các bước vẫn "XONG" ít nhất 9 giây (quan sát 5 lần), nút "Tạo lại nếu thiếu" vẫn bấm được (bấm sẽ ra 409 `voice_busy`, trang có xử lý).
- Nguyên nhân: `views/voice.js` `load()` chỉ dò job khi tải trang; không có vòng dò khi rảnh.
- Kiểm tra: `SU-009 ...`.

### SU-010 (cosmetic) Dự án nhập từ bản cũ: tiêu đề trên cùng in "null"
- Cách làm tay: mở `#/project/arnolfini/edit`. Thanh trên ghi "The Arnolfini Portrait null Có storyboard" (ảnh `e-old-draft-dialog-1280.png`). Nguyên nhân nghi ngờ: nghệ sĩ/năm `null` nối chuỗi trong `static/js/app.js`/`stepper.js` (phần tiêu đề dự án).
- Kiểm tra: `SU-010 ...`.

### SU-011 (cosmetic) Khung Bản nháp: chữ giới thiệu nhỏ và dính vào dòng "Giọng đọc"
- Cách làm tay: bước 5 chưa có storyboard (ảnh `draft-panel-1700.png`): đoạn "Agent đọc lời dẫn..." cỡ rất nhỏ và dòng cuối của nó chạm vào dòng nhãn "xong Giọng đọc:" ngay dưới. Chưa kiểm tra bằng máy.

## Chưa xác nhận
- Thanh các bước hiện "Dựng hình ĐANG CHẠY" một lần trong khi khung Bản nháp đã ghi "Xong. Có 54 cảnh" (tải trang đúng lúc job kết thúc); tải lại thì đúng. Không tái hiện lại được.
- Dữ liệu tạm trên máy chủ mất một lần sau `stop-keep` rồi khởi động lại (lỗi nằm ở công cụ thử của tôi hoặc đường dẫn, không xác định được; sau đó `stop-keep` và khởi động lại giữ dữ liệu đúng, thử lại hai lần).

## Tried and found sound
- Toàn bộ hành trình trong một phiên trình duyệt: trang chủ, thư viện, chọn tác phẩm (Las Meninas), tạo dự án, bước 2 (dàn ý và lời dẫn bằng mock, duyệt), bước 3 (tạo giọng giả, "Đang chạy" hiện ra, nghe một câu, phát mix có Range 206, đọc lại một câu, bảng phát âm chỉ làm lỗi thời 17 câu, tốc độ 1.1 chỉ ghép lại), bước 4 (tìm bằng dữ liệu mẫu, chọn tranh chính, vẽ vùng bằng chuột thật, chọn hình cho dòng, tải ảnh lên, các tab Sách/Gợi ý/Tìm kiếm/Tranh chính, hộp tốn tiền hỏi xác nhận, duyệt), bước 5 (dựng tự động, mở đề xuất, áp dụng tất cả thành storyboard đầu tiên, trình biên tập có 54 shot và sóng âm, lưu, duyệt), bước 6 (xuất với đồ giả, tiến trình, phiếu kiểm tra, mô tả, tải bốn tệp). Thanh các bước khớp `/pipeline` ở mọi điểm kiểm tra.
- Tải lên tệp không phải ảnh: "Loại tệp này chưa hỗ trợ." / "Tệp này không phải ảnh đọc được." (tiếng Việt, 422 được trang xử lý).
- Máy chủ ngừng giữa chừng: mọi nút cho câu "Không kết nối được máy chủ. Kiểm tra máy chủ còn chạy không rồi thử lại."; sau khi chạy lại cùng dữ liệu trang hoạt động bình thường.
- Nút bấm quá sớm (API): giọng khi chưa có lời dẫn (409 `narration_missing`), bản nháp khi chưa có giọng/hình (409 `draft_not_ready`), xuất khi chưa có storyboard (409 `no_storyboard`); các trang bước 3, 4, 5, 6 của dự án mới giải thích lý do khóa bằng tiếng Việt.
- Việc nặng: hai việc cùng loại (409 `voice_busy`), xóa dự án khi đang chạy (409 `longjob_running`), hủy đang chạy, tải lại trang giữa chừng, thẻ thứ hai tải sau khi job bắt đầu thấy tiến trình, nút bị tắt đúng lúc chạy.
- Dự án cũ `arnolfini`: bước 1 đến 4 giải thích "nhập từ bản dựng trước", bước 5 hoạt động như trước, hộp "Bản nháp" báo "Chưa đủ dữ liệu" hợp lý.
- Lỗi thời: sau khi duyệt lại lời dẫn, bước 3 và 4 báo "Lời dẫn đã đổi" và "Cần duyệt lại"; sau khi đọc lại, bước 6 báo "Cần xuất lại: giọng đọc đã đổi" và hộp bản nháp báo đề xuất cũ.
- Console: không có exception chưa bắt; 4xx duy nhất là 422 của tệp tải lên sai, được xử lý.

## Not tested, and why
- Hủy việc xuất giữa chừng, sửa storyboard sau khi xuất, đổi hình sau khi có bản nháp rồi quan sát từng trang: có công cụ (`probe_c2.mjs`) nhưng chưa chạy xong vì thời gian; lỗi thời của bản nháp chỉ kiểm tra qua API.
- Hai thẻ cùng làm bước 3 và 4 song song: chỉ kiểm tra khóa theo từng bước, không chạy đồng thời hai thẻ chỉnh sửa.
- Xuất thật (engine và ffmpeg thật): không dùng theo quy tắc; video giả nên thẻ video không phát được.
- Ảnh thu nhỏ từ Wikimedia/Met: mạng ngoài bị chặn nên ảnh hỏng (do thử nghiệm). Kích thước tranh chọn ở bước 4 lấy từ dữ liệu mẫu (4386x6000) khác tệp thật (1400x1300).
- Bản nháp bằng `agy`: giấu `agy` khỏi PATH theo quy tắc; chỉ thấy câu "agy chưa đăng nhập?" trong danh sách mô hình.
- Chụp ảnh ở 1280x720 cho mọi hộp thoại: đã chụp các trang chính và vài hộp thoại, chưa đủ từng hộp thoại.
