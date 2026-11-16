# Báo cáo kiểm thử giao diện: bước 5 "Dựng hình" (storyboard)

Người kiểm thử độc lập (vòng 2). Server riêng cổng 8565, dữ liệu sao chép tại `.scratch/uitest2/projects`.
(Báo cáo được ghi dần; các mục dưới đây là những gì đã tái hiện hai lần.)

## Bảng đếm theo mức độ

| Mức độ | Số lỗi | Mã |
|---|---|---|
| Blocker (mất dữ liệu) | 1 | U2-003 |
| Major | 10 | U2-001, 002, 006, 007, 008, 009, 013, 014, 015, 016 |
| Minor | 5 | U2-004 (chưa xác nhận), 005, 010, 011, 012 |
| Tổng | 16 | |

| Khu vực | Mã |
|---|---|
| Timeline (nhấp, kéo ranh giới, gộp) | U2-001, 007, 016 |
| Xem trước và tay cầm | U2-009, 012, 015 |
| Biểu mẫu tham số | U2-004, 005, 008 |
| Slot hình và gán hình | U2-013, 014 |
| Tab Hình và vùng | U2-006 |
| Lưu và trạng thái | U2-003 |
| Phím tắt và hộp thoại | U2-002 |
| Đề xuất | U2-010 |
| Inspector (chữ) | U2-011 |

Ghi chú: coordinator nhắc 14 mục; thực tế báo cáo có 16 mục (015 và 016 viết sau). Lệnh chạy kiểm tra e2e: `node tests/e2e/storyboard/run.mjs` (cả 16 mã U2-001..U2-016 đều có kiểm tra; 15 FAIL hôm nay, U2-004 PASS vì chưa tái hiện được trong e2e).


## Bảng 71 kỹ thuật

| Mã | Loại | Chọn từ thư viện | Biểu mẫu (số ô / số tham số) | Xem trước (std, không trống) | Kiểm tra | Slot cần | Clip 10 s | Lưu và tải lại | Kết luận |
|---|---|---|---|---|---|---|---|---|---|
| CAM-01 | base | ok | 2/2 | dựng được, std 19.2 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| CAM-02 | base | ok | 7/7 | dựng được, std 18.1 | sạch | foreground*,background*,mask* | phát được | chưa kiểm tra | dùng được |
| CAM-03 | base | ok | 2/2 | dựng được, std 18.7 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| CAM-04 | base | ok | 2/2 | dựng được, std 18.7 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| CAM-05 | base | ok | 2/2 | dựng được, std 20.1 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| CAM-06 | base | ok | 16/16 | dựng được, std 23.2 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| TR-01 | transition | ok | chọn ở mục Chuyển cảnh | dựng được, std 17.6 | sạch | from*,to* | chưa thử | chưa kiểm tra | dùng được |
| TR-02 | transition | ok | chọn ở mục Chuyển cảnh | dựng được, std 21.7 | sạch | anchor*,incoming* | chưa thử | chưa kiểm tra | dùng được |
| TR-03 | transition | ok | chọn ở mục Chuyển cảnh | dựng được, std 19.9 | sạch | - | chưa thử | chưa kiểm tra | có lỗi: U2-008 (ô khung hỏng) |
| TR-04 | transition | ok | chọn ở mục Chuyển cảnh | dựng được, std 18.6 | sạch | whole*,detail* | chưa thử | chưa kiểm tra | dùng được |
| LAY-01 | base | ok | 13/13 | dựng được, std 23.2 | sạch | left*,right* | phát được | chưa kiểm tra | có lỗi: U2-012 (nháy lỗi 500 tới khi điền slot) |
| LAY-02 | base | ok | 19/19 | dựng được, std 22.8 | sạch | tile_1*,tile_2*,tile_3*,tile_4* | phát được | chưa kiểm tra | dùng được |
| LAY-03 | base | ok | 15/15 | dựng được, std 19 | sạch | tile_1*,tile_2* | phát được | chưa kiểm tra | dùng được |
| LAY-04 | base | ok | 15/15 | dựng được, std 22.7 | sạch | image*,inset:video* | phát được | chưa kiểm tra | có lỗi: U2-014 (slot video nhận ảnh tĩnh) |
| LAY-05 | base | ok | 8/8 | dựng được, std 12 | sạch | image*,mask*,background_1* | phát được | chưa kiểm tra | có lỗi: U2-014 (mask nhận tranh) |
| LAY-06 | base | ok | 14/14 | dựng được, std 18.8 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| LAY-07 | base | ok | 16/16 | dựng được, std 22 | thiếu slot object tới khi điền (điền được qua Chọn) | tile_1*,object* | phát được | chưa kiểm tra | dùng được |
| LAY-08 | base | ok | 5/5 | dựng được, std 22.2 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| HI-01 | overlay | ok | 7/7 | dựng được, std 5.2 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| HI-02 | base | ok | 10/10 | dựng được, std 20.6 | sạch | room_plate*,figure_groups*,mask_1* | phát được | chưa kiểm tra | dùng được |
| HI-03 | overlay | ok | 4/4 | dựng được, std 18.6 | sạch | image*,mask* | chưa thử | chưa kiểm tra | có lỗi: U2-013 (mask không điền được, không có tác dụng) |
| AN-01 | overlay | ok | 8/8 | dựng được, std 19.1 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| AN-02 | overlay | ok | 11/11 | dựng được, std 18.6 | sạch | image* | chưa thử | chưa kiểm tra | có lỗi: U2-013 (mask tùy chọn không điền được), U2-009 |
| AN-03 | overlay | ok | 12/12 | dựng được, std 24.8 | sạch | image* | chưa thử | chưa kiểm tra | có lỗi: U2-009 |
| AN-04 | overlay | ok | 25/25 | dựng được, std 8.7 | sạch | - | chưa thử | chưa kiểm tra | có lỗi: U2-009 |
| AN-05 | overlay | ok | 8/8 | dựng được, std 23.3 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| AN-06 | overlay | ok | 17/17 | dựng được, std 27.8 | sạch | image* | chưa thử | chưa kiểm tra | có lỗi: U2-009 |
| AN-07 | base | ok | 17/17 | dựng được, std 60.6 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| TXT-01 | card | ok | 21/21 | dựng được, std 25.5 | sạch | - | phát được | chưa kiểm tra | dùng được |
| TXT-02 | overlay | ok | 15/15 | dựng được, std 22.9 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| STATIC-01 | base | ok | 2/2 | dựng được, std 18.6 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| STATIC-02 | overlay | ok | 6/6 | dựng được, std 19.2 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| STATIC-04 | overlay | ok | 21/21 | dựng được, std 15.3 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| STATIC-05 | overlay | ok | 12/12 | dựng được, std 22.8 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| STATIC-06 | base | ok | 11/11 | dựng được, std 10.4 | sạch | - | phát được | chưa kiểm tra | có lỗi: U2-011 |
| STATIC-07 | base | ok | 18/18 | dựng được, std 29 | sạch | image* | phát được | chưa kiểm tra | dùng được |
| STATIC-08 | overlay | ok | 7/7 | dựng được, std 18.6 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| STATIC-09 | overlay | ok | 9/9 | dựng được, std 23.4 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| DIA-01 | base | ok | 20/20 | dựng được, std 24.9 | sạch | image* | phát được | chưa kiểm tra | có lỗi: U2-008 (ô khung hỏng) |
| DIA-02 | base | ok | 11/11 | dựng được, std 18.4 | sạch | image* | phát được | chưa kiểm tra | có lỗi: U2-008 (ô khung hỏng) |
| DIA-03 | base | ok | 24/24 | dựng được, std 22 | sạch | - | phát được | chưa kiểm tra | có lỗi: U2-008 (ô khung hỏng) |
| DIA-04 | base | ok | 7/7 | dựng được, std 22 | sạch | figure* | phát được | chưa kiểm tra | dùng được |
| DIA-05 | base | ok | 4/4 | dựng được, std 43.4 | sạch | image*,mask* | chưa thử | chưa kiểm tra | có lỗi: U2-014 (mask nhận tranh) |
| DIA-06 | base | ok | 19/19 | dựng được, std 20.8 | sạch | uv_detail* | chưa thử | chưa kiểm tra | có lỗi: U2-008 (ô khung hỏng) |
| DIA-07 | base | ok | 5/5 | dựng được, std 21.5 | sạch | - | chưa thử | chưa kiểm tra | có lỗi: U2-011 |
| CMP-01 | base | ok | 11/11 | dựng được, std 20.8 | sạch | colour* | chưa thử | chưa kiểm tra | dùng được |
| CMP-02 | base | ok | 15/15 | dựng được, std 22.1 | sạch | finished* | chưa thử | chưa kiểm tra | có lỗi: U2-008 (ô khung hỏng) |
| CMP-03 | base | ok | 10/10 | dựng được, std 38.5 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| CMP-04 | base | ok | 10/10 | dựng được, std 18.9 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| CMP-05 | base | ok | 7/7 | dựng được, std 24.7 | sạch | state_a*,state_b* | chưa thử | chưa kiểm tra | dùng được |
| FOOT-01 | base | ok | 28/28 | dựng được, std 18.9 | sạch | footage:video* | phát được | chưa kiểm tra | có lỗi: U2-014 (slot video nhận ảnh tĩnh) |
| SHORT-01 | base | ok | 8/8 | dựng được, std 11.3 | sạch | strip_1*,strip_2*,strip_3* | chưa thử | chưa kiểm tra | dùng được |
| SHORT-02 | base | ok | 7/7 | dựng được, std 15 | sạch | image* | chưa thử | chưa kiểm tra | có lỗi: U2-009 |
| SHORT-03 | base | ok | 12/12 | dựng được, std 28.4 | sạch | background* | chưa thử | chưa kiểm tra | dùng được |
| SHORT-04 | overlay | ok | 12/12 | dựng được, std 25.2 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| SHORT-05 | base | ok | 11/11 | dựng được, std 17.4 | sạch | palette* | chưa thử | chưa kiểm tra | dùng được |
| X-TR-01 | transition | ok | chọn ở mục Chuyển cảnh | dựng được, std 18.6 | sạch | from*,to* | chưa thử | chưa kiểm tra | dùng được |
| X-CARD-01 | card | ok | 10/10 | dựng được, std 0 | sạch | - | chưa thử | chưa kiểm tra | có lỗi: U2-011 (chữ null) |
| X-CARD-02 | card | ok | 6/6 | dựng được, std 22.7 | sạch | background* | chưa thử | chưa kiểm tra | dùng được |
| X-CARD-03 | card | ok | 17/17 | dựng được, std 17.6 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| X-CARD-04 | card | ok | 16/16 | dựng được, std 17.9 | sạch | - | chưa thử | chưa kiểm tra | dùng được |
| X-ANN-01 | overlay | ok | 10/10 | dựng được, std 23.4 | sạch | text:text* | chưa thử | chưa kiểm tra | dùng được |
| X-ANN-02 | overlay | ok | 12/12 | dựng được, std 23.5 | sạch | title:text*,artist_year:text* | chưa thử | chưa kiểm tra | dùng được |
| X-ANN-03 | overlay | ok | 7/7 | dựng được, std 18.6 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| X-ANN-04 | overlay | ok | 20/20 | dựng được, std 18.6 | sạch | image* | chưa thử | chưa kiểm tra | có lỗi: U2-013 (mask tùy chọn không điền được) |
| X-ANN-05 | overlay | ok | 20/20 | dựng được, std 8.7 | sạch | - | chưa thử | chưa kiểm tra | có lỗi: U2-009 |
| X-LAY-01 | base | ok | 2/2 | dựng được, std 18.8 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |
| X-CMP-01 | base | ok | 21/21 | dựng được, std 22.8 | sạch | anchor*,swap_1* | chưa thử | chưa kiểm tra | dùng được |
| X-CMP-02 | base | ok | 10/10 | dựng được, std 23.9 | sạch | state_a*,state_b* | chưa thử | chưa kiểm tra | dùng được |
| X-TR-02 | transition | ok | chọn ở mục Chuyển cảnh | dựng được, std 21.4 | sạch | - | chưa thử | chưa kiểm tra | có lỗi: U2-008 (ô khung hỏng) |
| X-HI-01 | overlay | ok | 9/9 | dựng được, std 11.8 | sạch | image* | chưa thử | chưa kiểm tra | dùng được |

Tổng: 48/71 kỹ thuật dùng được trọn vẹn từ trang (chọn, điền slot, sửa tham số, dựng khung, kiểm tra sạch). 71/71 đều chọn được từ thư viện (không mục nào xám; APP_GUIDE nói "khoảng 47 kỹ thuật còn lại hiện xám", mô tả đó đã lỗi thời: registry báo cả 71 `engine.available = true`, 60 `done`, 11 `partial`). Cột "Clip 10 s" là nút "Xem thử 10 giây" trên shot của technique_lab (các kỹ thuật lớp phủ và chuyển cảnh chưa thử; số kỹ thuật clip phát được: 24). Cột "Lưu và tải lại" chưa kiểm tra từng kỹ thuật (xem "Chưa kiểm thử").
Phương pháp: mỗi kỹ thuật chọn bằng chuột thật trong thư viện trên shot `s0031` của technique_lab (nền/thẻ), thêm làm lớp phủ (overlay), hoặc chọn ở mục Chuyển cảnh; slot bắt buộc điền qua nút "Chọn" khi trống; dựng khung bằng POST /frame. Dữ liệu thô: `.scratch/uitest2/sweep.jsonl`, `sweep2.jsonl`; ảnh `.scratch/uitest2/shots/sw_<id>.png`.


## Lỗi


### U2-001 (major, Timeline/Gộp) Gộp hai shot có lớp phủ cùng id tạo id trùng; sửa lớp phủ thứ hai lại sửa lớp phủ thứ nhất

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-001`: đạt.

- Các bước (arnolfini_edit): mở `#/project/arnolfini_edit/edit`; bấm giữa shot `s0041` trên timeline; bấm "Gộp trước" (s0040 và s0041 đều có lớp phủ `o1`); mở tab "Lớp phủ"; bấm dòng thứ hai trong danh sách; gõ vào ô "text".
- Thấy: cả hai dòng đều sáng (cùng id `o1`), ô text hiện chữ của lớp phủ thứ nhất ("Straw hat"), gõ "XX" làm đổi lớp phủ thứ nhất ("Straw hatXX"). Lớp phủ thứ hai ("Silk velvet tabard") không sửa được. Kiểm tra báo lỗi `duplicate overlay id 'o1'` và Lưu trả 422, trang mở tab Lỗi.
- Đáng ra: nối lớp phủ của hai shot (APP_GUIDE bước 7 "Gộp") phải cấp lại id duy nhất, để chọn/sửa/xóa đúng mục và lưu được. Nguồn gốc: `edit.js mergeWithPrev` nối mảng mà không đổi id; `findOverlay` tìm theo id nên luôn thấy lớp phủ đầu.
- Ảnh: `.scratch/uitest2/shots/b5_a.png`. Tái hiện: mọi lần (2/2). Kiểm tra e2e: `U2-001`.


### U2-002 (major, Phím tắt/Hộp thoại) Phím Delete, S, Space vẫn chạy khi hộp thoại "Đề xuất" đang mở: xóa shot phía sau hộp thoại

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-002`: đạt.

- Các bước (demo_stub): mở dự án, bấm "Đề xuất" (hộp thoại mở, tiêu điểm nằm ở nút "Đề xuất"), nhấn Delete.
- Thấy: shot đang chọn (s0001) bị xóa phía sau hộp thoại (10 -> 9 shot), bản nháp thành "chưa lưu"; Space bắt đầu phát (`ctx.playing = true`); S cắt shot. Chỉ ô nhập (input/textarea/select) được miễn, hộp thoại thì không.
- Đáng ra: khi một hộp thoại đang mở, phím tắt của timeline không chạy (APP_GUIDE mục 9: "hộp thoại đang mở" thuộc trạng thái phải được tách; người dùng bấm Delete để thao tác trong hộp thoại, không phải để xóa shot).
- Ảnh: `.scratch/uitest2/shots/b6.png`. Tái hiện: mọi lần (2/2). Kiểm tra e2e: `U2-002`.


### U2-003 (blocker theo định nghĩa "mất dữ liệu", khả năng gặp thấp) Sửa gõ trong lúc đang Lưu bị bỏ lặng lẽ, ô vẫn hiện giá trị đã gõ và dấu "chưa lưu" tắt

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-003`: đạt.

- Các bước (arnolfini_edit): chọn lớp phủ `s0004/o1` (HI-01), tab "Lớp phủ"; gõ rx = 310; bấm Lưu (`#btn-save`); trong vòng khoảng 50 ms gõ ry = 200 (bằng sự kiện bàn phím/chuột thật).
- Thấy: sau khi lưu xong, ô ry vẫn hiện 200, nhưng bản nháp có ry = 440 (giá trị cũ), `dirty = false`, chấm "chưa lưu" tắt, đĩa cũng ry = 440. Sửa đổi mất mà không có thông báo. Lưu mất khoảng 76 ms trên máy này; máy chậm hoặc dự án lớn hơn thì cửa sổ rộng hơn.
- Nguyên nhân: `views/storyboard.js save()` gọi `st.markSaved(r.storyboard, r.rev)`, thay cả bản nháp bằng bản server trả về, đè lên mọi sửa đổi xảy ra sau khi gửi.
- Đáng ra: chỉ coi bản đã gửi là đã lưu (so sánh với ảnh chụp lúc gửi) và giữ phần sửa thêm là chưa lưu; hoặc khóa chỉnh sửa trong lúc lưu.
- Ảnh: không có (lỗi nằm ở trạng thái, xem log `.scratch/uitest2/b10.mjs`). Tái hiện: 2/2 (độ trễ 0 ms). Kiểm tra e2e: `U2-003`.

### U2-004 (minor, Biểu mẫu tham số) Số gõ ngoài khoảng được ép về min/max trong bản nháp nhưng ô vẫn hiện số đã gõ, kể cả sau khi rời ô

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-004`: đạt.

- Các bước: chọn lớp phủ `s0004/o1`, ô rx (min 5, max 5000): gõ -5, nhấn Tab.
- Thấy: giá trị lưu là 5, ô vẫn hiện "-5" (gõ 99999 thì lưu 5000, ô hiện 5000 vì thanh trượt kéo theo; gõ "1e3" vào floor (max 1) lưu 1, ô hiện "1e3"). Không có dấu đỏ/thông báo (ô chỉ đồng bộ lại khi chọn lại mục).
- Đáng ra: ô phản ánh giá trị thực được lưu (hoặc báo "đã ép về 5").
- Tái hiện: 2/2 trong script tạm (`.scratch/uitest2/b7.mjs`, `b8.mjs`), nhưng KHÔNG tái hiện trong kiểm tra e2e `U2-004` (tải mới, gõ -5, Tab: ô hiện 5), nên coi là chưa xác nhận, chưa rõ điều kiện (có thể cần gõ giá trị khác trước đó trong cùng phiên). Kiểm tra e2e `U2-004` hiện PASS.

### U2-005 (minor, Kiểm tra) Điểm ngoài ảnh không bị cảnh báo

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-005`: đạt.

- Các bước: lớp phủ HI-01, ô "at": gõ `5000, 99999` hoặc `-10,-10` trên ảnh 4386x6000. Chờ kiểm tra 2,5 s.
- Thấy: không có lỗi hay cảnh báo, xem trước dựng ra khung với vòng ngoài ảnh. Tên vùng sai thì được báo rõ ("region 'abc xyz' is not defined on asset 'A'").
- Đáng ra (gợi ý): cảnh báo điểm nằm ngoài ảnh nguồn. Tái hiện: 2/2.


### U2-006 (major, Tab Hình/Quản lý vùng) Sửa vùng (xóa, đổi tên, vẽ) ghi thẳng vào đĩa, không qua Lưu/Hoàn tác; vùng đang được dùng thì trang vẫn đổi bản nháp dù server từ chối

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-006`: đạt.

- Các bước A (vùng không dùng): arnolfini_edit, tab "Hình", chọn hình `A`, bấm "Xóa" ở vùng `BRUSH` (không lớp phủ nào dùng); không bấm Lưu. Sau đó bấm Hoàn tác.
- Thấy A: ngay sau khi xóa, `storyboard.json` trên đĩa đã mất BRUSH (rev đổi) trong khi chấm "chưa lưu" bật. Bấm Hoàn tác thì bản nháp có lại BRUSH và `dirty = false` (trang tưởng không còn gì cần lưu), nhưng đĩa vẫn thiếu BRUSH. Chỉ khi bấm Lưu thì đĩa mới có lại. Đóng tab ở thời điểm đó là mất vùng dù đã "hoàn tác".
- Các bước B (vùng đang dùng): xóa `R2` hoặc đổi tên `MIRROR` thành `GLASS` (hộp thoại `prompt()` của trình duyệt).
- Thấy B: server trả 422 (kiểm tra: 4 lớp phủ còn trỏ `MIRROR`), trang chỉ hiện toast "Không lưu được vùng lên server: 422" không nêu lý do hay danh sách lớp phủ; bản nháp vẫn đổi (vùng biến mất, lớp phủ báo 4 lỗi "region 'MIRROR' is not defined"), đĩa giữ nguyên: bản nháp và đĩa lệch nhau. Đổi tên không cập nhật các lớp phủ đang trỏ vùng đó.
- Đáng ra: thay đổi vùng đi theo Lưu/Hoàn tác như mọi sửa đổi khác (hoặc không chạm đĩa tới khi Lưu); chặn trước và nêu lý do khi vùng đang được dùng; đổi tên phải cập nhật tham chiếu. Đổi tên dùng `prompt()` trong khi APP_GUIDE mục 9 nói ứng dụng không dùng hộp thoại của trình duyệt.
- Ảnh: `.scratch/uitest2/shots/b12.png`. Tái hiện: mọi lần (A 2/2, B 3/3). Kiểm tra e2e: `U2-006`.


### U2-007 (major, Timeline) Ở mức zoom "Vừa" (82 shot), nhấp vào dải shot để dời đầu phát thất bại một nửa số lần

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-007`: đạt.

- Các bước (arnolfini_edit, tải mới, mức zoom mặc định 2,07 px/s): nhấp chuột thật vào dải shot tại 44 vị trí cách đều 37 px.
- Thấy: 22/44 cú nhấp chỉ chọn shot (hoặc ranh giới) mà không dời đầu phát (`ctx.t` giữ nguyên). Nhấp vào thước thời gian thì 44/44 dời được. Nguyên nhân: vùng bắt ranh giới rộng +-5 px (`hitBoundary`) so với bề rộng shot trung bình khoảng 20 px, nên gần nửa dải là "ranh giới" và nhấn xuống đó bắt đầu kéo ranh giới thay vì dời đầu phát.
- Đáng ra: thiết kế mục 10 "Click to move the playhead"; nhấp không kéo phải dời đầu phát (chỉ kéo thật sự mới đổi ranh giới).
- Ảnh: `.scratch/uitest2/shots/b17.png`. Tái hiện: mọi lần (b16: 3/3 lần nhấp gần ranh giới, b17: 22/44). Kiểm tra e2e: `U2-007`.


### U2-008 (major, Biểu mẫu tham số/kiểu "box") Ô "khung" (box) không hiểu dạng mảng [x0,y0,x1,y1] của registry: ô trống, gõ vào tạo giá trị sai khiến không lưu được; tay cầm xem trước báo NaN

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-008`: đạt.

- Các bước (technique_lab): chọn shot `s0047` (CMP-02), xem ô `finished_box` trong tab Shot; gõ 500 vào ô đầu tiên; bấm Lưu.
- Thấy: 4 ô số đều trống (registry mặc định `[520, 40, 1520, 1040]`, tức mảng); mở shot là console báo lỗi `<rect> attribute x/y/width/height: Expected length, "NaN"` (preview.js vẽ box như {x,y,w,h}). Gõ 500 tạo `{"x":500,"y":0,"w":0,"h":0}`; kiểm tra báo `finished_box: must be [x0, y0, x1, y1]`, Lưu bị chặn (422), trang mở tab Lỗi. Ảnh hưởng 7 tham số của 7 kỹ thuật: TR-03 box, DIA-01 grid_box, DIA-02 box_a/box_b, DIA-03 section_box, DIA-06 room_box/painting_box/uv_box, CMP-02 finished_box, X-TR-02 target_box.
- Đáng ra: APP_GUIDE nói biểu mẫu hỗ trợ kiểu "khung" sinh từ registry; widget phải đọc/ghi đúng dạng `[x0,y0,x1,y1]` và không sinh NaN.
- Ảnh: `.scratch/uitest2/shots/c2_box.png`. Tái hiện: mọi lần (3/3). Kiểm tra e2e: `U2-008`.


### U2-009 (major, Tay cầm xem trước/điểm) Danh sách điểm theo tỉ lệ khung hoặc pixel canvas được vẽ và ghi như pixel ảnh nguồn

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-009`: đạt.

- Các bước (technique_lab): chọn shot `s0031`, tab "Lớp phủ", "+ Thêm lớp phủ" chọn AN-03 (tia phối cảnh); nhìn khung xem trước; kéo một chấm của `origins` bằng chuột thật.
- Thấy: 9 điểm `origins` mặc định là tỉ lệ khung (`[0,0.98]`, `[0.12,1]`...) nhưng được vẽ như pixel ảnh nguồn nên cả 9 chấm chồng lên một điểm ở góc trên trái ảnh (cùng toạ độ màn hình 468,187). Kéo chấm đó thêm (+60,+40) px ghi `[829,552]` (pixel nguồn) vào phần tử cuối của danh sách vốn là tỉ lệ 0..1; kiểm tra không báo gì, tia sẽ bay ra ngoài khung. Cùng lỗi với các kiểu `points` khác không khai báo đơn vị: AN-06 shape_points, DIA-02/SHORT-02 to_quad, AN-04 places (pixel canvas), X-ANN-05 points; `preview.js itemHandles` chỉ bỏ qua khi `unit` chứa "canvas|screen".
- Đáng ra: APP_GUIDE "kéo chấm vàng để dời": tay cầm phải đúng chỗ và ghi đúng hệ toạ độ của tham số (hoặc không vẽ tay cầm khi không biết hệ toạ độ).
- Ảnh: `.scratch/uitest2/shots/c3_an03.png`. Tái hiện: mọi lần (2/2). Kiểm tra e2e: `U2-009`.


### U2-010 (minor, Đề xuất) Đề xuất cũ (base_rev không còn khớp) mở ra không có cảnh báo; tệp hỏng trong thư mục proposals bị bỏ qua lặng lẽ

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-010` và `U2-010b` (tệp hỏng được nêu tên trong bảng đề xuất): đạt, sửa trọn.

- Các bước (demo_stub): lưu một sửa đổi bất kỳ (rev đổi), bấm "Đề xuất", mở `p_demo_001`.
- Thấy: API `GET /proposals/{id}` trả `proposal.stale = true`, nhưng trang không hiện dấu nào (không chữ "cũ", không cảnh báo) và cho áp dụng như bình thường. Hai tệp hỏng đặt vào `proposals/` (`p_bad_001.json` không phải JSON, `p_bad_002.json` thiếu storyboard) không xuất hiện trong danh sách và không có thông báo nào cho người dùng biết có đề xuất bị bỏ.
- Đáng ra: nêu rõ "đề xuất dựa trên bản cũ" trước khi áp dụng (APP_GUIDE mục Đề xuất nói đề xuất áp lên bản đã lưu); nên báo số tệp không đọc được.
- Ảnh: `.scratch/uitest2/shots/e1_detail.png`. Tái hiện: mọi lần (2/2). Kiểm tra e2e: `U2-010`.


### U2-011 (minor, Inspector) Chữ "null" hiện trong tab Shot với kỹ thuật không có slot hình

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-011`: đạt.

- Các bước (technique_lab): chọn shot `s0058` (X-CARD-01), `s0035` (STATIC-06) hoặc `s0045` (DIA-07), nhìn tab Shot giữa hàng "Ý đồ" và mục "BẮT ĐẦU".
- Thấy: một dòng chữ trần "null" (nút văn bản thừa do `body.append(... null ...)` trong `inspector.js renderShot`; `Element.append(null)` chèn chuỗi "null"). Tái hiện 3/3 shot không có slot, 0 lần ở shot có slot.
- Đáng ra: không hiện gì. Ảnh: `.scratch/uitest2/shots/sw_X-CARD-01.png`. Kiểm tra e2e: `U2-011`.

### U2-012 (minor, Xem trước) Thiếu slot bắt buộc làm khung xem trước báo "lỗi dựng khung: 500", không nêu nguyên nhân

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-012`: đạt.

- Các bước (technique_lab): chọn shot `s0031`, chọn LAY-01 từ thư viện (slot `right` còn trống).
- Thấy: thanh phía trên khung ghi "lỗi dựng khung: 500" (máy chủ trả 500 Internal Server Error), trong khi tab Lỗi/kiểm tra nói rõ "required slot 'right' is missing". Xem trước không cho biết cần điền slot. Cũng xảy ra ở mọi kỹ thuật nhiều slot khi slot bắt buộc chưa điền (gặp ở LAY-01; hai lần).
- Đáng ra: thông báo "thiếu slot right" (hoặc 4xx kèm lý do) trong khung xem trước. Ảnh: `.scratch/uitest2/shots/f1_lay01.png`. Tái hiện: 2/2. Kiểm tra e2e: `U2-012`.


### U2-013 (major, Lớp phủ/slot) Lớp phủ cần slot riêng (mặt nạ) không có chỗ điền; thêm vào không có tác dụng và kiểm tra vẫn sạch

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-013`: đạt.

- Các bước (technique_lab): chọn shot `s0031`, tab "Lớp phủ", "+ Thêm lớp phủ" chọn HI-03 (registry: slot `mask` bắt buộc). So khung tại đầu shot + 2 s trước và sau khi thêm.
- Thấy: tab Lớp phủ không có hàng slot nào (0 hàng), không có chữ mask/slot; khung hình sau khi thêm giống hệt khung trước (mean 24.6, std 18.5 cả hai); kiểm tra không báo lỗi. Hàng slot chỉ có ở tab Shot (cho kỹ thuật nền). Cùng tình trạng với AN-02 (mask), X-ANN-04 (mask_1..6): khung giống hệt nền. Người dùng không có cách điền mặt nạ cho lớp phủ từ trang.
- Đáng ra: thiết kế mục 10 "Each slot shows the chosen asset and a 'choose' button"; ít nhất kiểm tra phải báo thiếu mặt nạ.
- Tái hiện: 2/2 (HI-03). Kiểm tra e2e: `U2-013`.

### U2-014 (major, Chọn kỹ thuật/slot) Đổi kỹ thuật tự điền bức tranh vào slot mask và slot video; kiểm tra không báo

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-014`: đạt.

- Các bước (technique_lab): chọn shot `s0031` (STATIC-01 với hình `arn_A`), chọn lần lượt LAY-04, FOOT-01, LAY-05, DIA-05 từ thư viện; xem hàng "Slot hình" trong tab Shot.
- Thấy: LAY-04 `inset` (video, bắt buộc) = `arn_A` (ảnh tĩnh); FOOT-01 `footage` (video) = `arn_A`; LAY-05 `mask` = `arn_A`; DIA-05 `mask` = `arn_A`. Nút "Chọn" thì chặn đúng ("Slot này cần video"), nhưng đường đổi kỹ thuật (`actions.js setShotTechnique`) gán theo thứ tự bất kể loại slot. Kiểm tra trả sạch (0 vấn đề), khung vẫn dựng ra, nên người dùng tưởng đã xong.
- Đáng ra: không gán ảnh vào slot video/mask; để trống và báo "cần video/mặt nạ".
- Ảnh: bản ghi sweep `.scratch/uitest2/sweep.jsonl` (slots_empty_before). Tái hiện: 4/4 kỹ thuật. Kiểm tra e2e: `U2-014`.


### U2-015 (major, Xem trước/Timeline) Chọn lớp phủ trên timeline không dời đầu phát: khung hình là shot cũ nhưng tay cầm của shot mới vẽ đè lên

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-015`: đạt.

- Các bước (arnolfini_edit, tải mới, đầu phát ở 0:00): nhấp chuột thật vào chip lớp phủ HI-01 của shot `s0004` (khoảng 0:39) trên dải lớp phủ của timeline.
- Thấy: lựa chọn chuyển sang `s0004/o1` và tab "Lớp phủ" mở, nhưng đầu phát vẫn ở 0:00 (`ctx.t = 0`, "khung 0:00.00"), nên khung xem trước vẫn là ảnh của shot `s0001` (cả bức tranh), trong khi 3 khung camera K1..K3 và chấm/elip "at: MIRROR" của `s0004` vẽ đè lên ảnh đó, sai chỗ. Kéo các tay cầm này sửa đúng tham số nhưng người dùng nhìn vào ảnh sai (APP_GUIDE: "Khung xem trước: ảnh thật tại vị trí đầu phát"; "khung bạn đặt phải là khung bạn nhận"). Chọn dòng lớp phủ trong danh sách của tab Lớp phủ cũng không dời đầu phát. (Chọn lỗi trong tab Lỗi thì có dời.)
- Đáng ra: chọn một lớp phủ/shot từ timeline đưa đầu phát tới trong shot đó (hoặc ảnh xem trước dựng theo thời điểm của mục chọn).
- Ảnh: `.scratch/uitest2/shots/h1_1280.png`, `.scratch/uitest2/shots/h2.png`. Tái hiện: mọi lần (3/3). Kiểm tra e2e: `U2-015`.


### U2-016 (major, Timeline/Kéo ranh giới) Kéo ranh giới shot sang trái làm ranh giới nhảy sang phải rồi đứng yên (chưa rõ nguyên nhân)

> **Trạng thái: ĐÃ SỬA** (2026-11-16, xem `FIXES_ui_storyboard.md`). Kiểm tra e2e `U2-016`: đạt.

- Các bước (arnolfini_edit, tải mới): đặt zoom 120 px/s, đầu hiển thị 76 s (`__tl.view.pps=120; __tl.view.t0=76`); nhấn chuột thật tại ranh giới 80,01 s giữa `s0010` và `s0011`; kéo sang trái tới 78,0 s (hoặc 76,5 s) rồi thả.
- Thấy: ranh giới `s0011` thành 80,15 s (về bên phải điểm bắt đầu) ngay từ bước di chuyển đầu tiên và không đổi dù con trỏ đi tiếp sang trái (đo từng bước: 79,5 / 79 / 78,5 / 78 / 77,6 / 77,3 / 76,5 s đều cho 80,150). Kéo sang phải 40 px ở mức zoom khác (b2) thì chạy đúng.
- Đáng ra: ranh giới bám theo con trỏ (bám đầu từ), tối đa tới `đầu shot trước + 0,2 s`.
- Chưa phân tích nguyên nhân; có thể do cách tính trúng ranh giới (`hitBoundary`) hoặc chọn từ gần nhất. Tái hiện: 3/3 (i1, i2 và e2e). Kiểm tra e2e: `U2-016`.


## Phát hiện mới của vòng sửa (U2-017 trở đi)

Mỗi mục có kiểm tra e2e cùng tên trong `tests/e2e/storyboard/run.mjs`; đã FAIL trên mã cũ, PASS trên mã mới. Tất cả đã sửa (chi tiết trong `FIXES_ui_storyboard.md`).

- **U2-004b (minor)** Dạng thật của U2-004: gõ lại số ngoài khoảng (-5, 99999, -5) thì ô giữ số đã gõ.
- **U2-017 (minor)** Hàng "slot chữ" ở tab Shot (TXT-01, X-CARD-03/04, FOOT-01) ghi `slots.<tên>.text` mà engine không đọc; chữ đi qua tham số cùng tên.
- **U2-018 (major)** Dời đầu phát khi đang phát bị vòng phát kéo lại.
- **U2-020 (major)** Sửa gõ trong lúc Duyệt chạy bị coi là đã lưu (cùng gốc U2-003).
- **U2-021 (minor)** Áp dụng đề xuất dùng `confirm()` của trình duyệt.
- **U2-002b (major)** Phím tắt vẫn chạy khi chọn hình cho slot và khi ô `select` có tiêu điểm.
- **U2-006b (major)** Quản lý vùng đầy đủ: vùng đang dùng không xóa được, đổi tên cập nhật tham chiếu, Hoàn tác, đĩa chỉ đổi khi Lưu.

## Đã kiểm thử và thấy ổn

- Ranh giới shot, kéo sang phải bám từ, hoàn tác về đúng bản gốc (so sánh chuỗi JSON).
- Khung camera: khung K1/K2 trên xem trước khớp với ảnh dựng thật (so sánh với ảnh gốc cắt theo cx, cy, zoom: sai khác 2,1 đến 2,5 so với 13 đến 26 khi lệch 5%); kéo thân và núm đổi cx, cy, zoom đúng.
- Cắt shot: camera hai nửa liên tục, lớp phủ bị cắt hợp lệ; hoàn tác và làm lại đúng; cắt dưới 0,2 s bị từ chối kèm thông báo; gộp shot đầu bị từ chối kèm thông báo; xóa shot cuối giữ nguyên `end`.
- Kéo chip lớp phủ (thân và hai mép) bị giữ trong shot của nó, đoạn tối thiểu 0,1 s, bám từ; Alt cho neo `{t}`.
- Phát bằng Space: âm thanh và đầu phát lệch dưới 15 ms trong 6 s; phát tới hết dừng ở cuối; Space ở cuối quay về đầu; tìm vị trí khi đang phát đúng (qua thước).
- Xung đột 409 giữa hai tab: hộp thoại đúng, "Giữ bản nháp" giữ nguyên, "Tải lại" lấy bản server.
- Duyệt: Chưa duyệt, Đã duyệt, Duyệt cũ (đã sửa), hoàn tác về bản đã lưu trở lại Đã duyệt, nút Tiếp tục hiện đúng lúc.
- Rời màn hình khi chưa lưu: hộp thoại ba nút, Ở lại, Bỏ thay đổi, nút Quay lại của trình duyệt.
- Đề xuất: áp dụng một phần (từ chối một thay đổi), mục khóa không bị chạm, danh sách và chi tiết đúng.
- Xung đột phiên bản và lỗi 422 khi lưu: mở tab Lỗi, thông báo rõ.
- Số, enum, chuỗi, màu, danh sách điểm, cột nhập: số ngoài khoảng bị ép về min/max khi lưu; tên vùng sai được báo lỗi rõ ("region 'x' is not defined on asset 'A'").
- Mọi 71 kỹ thuật chọn được từ thư viện và dựng ra khung có nội dung; 20 clip xem thử 10 giây phát được (640x360, 10 s).
- Bố cục ở 1280 và 1920 px: không tràn ngang, không chữ bị cắt ở thanh công cụ và tab.
- Máy chủ từ chối xóa vùng đang được lớp phủ dùng (422), tệp đề xuất hỏng không làm sập danh sách.

## Chưa kiểm thử và lý do

- Phiên dài 30 phút (tăng bộ nhớ, DOM, số yêu cầu): không làm, hết thời gian được giao.
- Tab Hình: tìm kiếm Wikimedia Commons (giới hạn 3 truy vấn), nhập 1 ảnh, tải lên có/không giấy phép, ảnh quá nhỏ: chưa chạy (không dùng mạng trong vòng này). Chỉ kiểm tra danh sách hình, quản lý vùng (xóa, đổi tên; vẽ vùng bằng kéo chưa thử), gán vào slot.
- Lưu rồi tải lại từng kỹ thuật trong 71: chưa làm riêng; chỉ kiểm tra lưu/tải lại ở các luồng khác.
- Clip 10 s: 20 kỹ thuật nền/thẻ thử, chưa thử lớp phủ, chuyển cảnh và các kỹ thuật sau DIA-04 trong bảng.
- Đổi hình của shot có lớp phủ trỏ vùng đặt tên, truyền lại camera sau khi khóa, khóa rồi dời ranh giới: chưa thử.
- Chọn qua chip lớp phủ chồng nhau, thu phóng tới hai đầu, bản đồ nhỏ, "Ảnh gốc", "Hiện vùng", "Chọn trên ảnh" (pick), shot không có ảnh, camera nhiều khóa: chỉ quan sát qua mã nguồn và ảnh chụp, chưa thao tác hệ thống.
- Hai thao tác xóa lớp phủ bằng nút "Xóa lớp phủ này": nút nằm ngoài khung nhìn 1000 px cao khi tab dài, chưa kiểm chứng riêng (cuộn được).
- Xóa shot đã khóa hoặc có lớp phủ khóa: Delete xóa ngay không hỏi (đã thấy ở `s0005`); coi là câu hỏi thiết kế, không liệt kê thành lỗi vì thiết kế mục 6 chỉ cấm đề xuất của agent đổi mục khóa.
- Chế độ `?mock=1`: không thử.
