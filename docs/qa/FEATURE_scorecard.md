# Phase 0: Bảng chấm chất lượng, tờ ảnh và hồ sơ dựng video (`bti/scorecard/`)

Triển khai Mục 6 của [docs/design/2026-11-27-unified-pipeline.md](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/docs/design/2026-11-27-unified-pipeline.md) làm thước đo chất lượng thống nhất cho cả dự án dùng storyboard cũ (`storyboard.json` + `picks.json` + `timing.json`) lẫn dự án dùng `visual.json` (`bti.visual/1`). Kết quả lưu ở `<project>/scorecard/` (`scorecard.json`, `scorecard.md`, `record.json`, `record.md`, `sheets/sheet_XX.jpg`), đồng bộ ra `output/<artwork key>/7_quality/`, tự tạo ở cuối `bti/export/run.py`, gọi được qua `POST /api/projects/{pid}/scorecard/make` (`scorecard.make`), xem tại `GET /api/projects/{pid}/scorecard`, và hiển thị trên trang Xuất video. Bảng chấm không chặn bước nào.

## 1. Định nghĩa 12 chỉ số

Mục tiêu đọc từ khối `quality` trong [style/gae/style.json](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/style/gae/style.json) (`DEFAULT_TARGETS` trong [targets.py](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/bti/scorecard/targets.py)).

1. **`small_painting_share`**: Tỷ lệ thời lượng video mà tranh chính bị thu nhỏ giữa hai dải đen (tỷ lệ phủ khung từ camera `< 0.70`, mục tiêu `<= 6%`).
2. **`marks_per_minute`**: Tổng số dấu chỉ điểm (`HI-01`, `X-HI-01`, `AN-01`) chia tổng phút video (mục tiêu `<= 3,0/phút`).
3. **`biggest_mark`**: Dấu chỉ lớn nhất theo chiều cao trên khung hình `1080px` có xét phóng to camera; liệt kê mọi dấu `> 30%` (mục tiêu `<= 30%`).
4. **`marks_on_person`**: Số dấu chỉ đặt lên vùng thuộc nhân vật người trong `picks.subjects`/`names` hoặc `visual.cast` (mục tiêu `0`).
5. **`name_strips`**: Số nhãn tên (`X-ANN-01`), số nhãn có dòng phụ `sub` lặp lại chính tên đó (mục tiêu `0`), và số nhãn đặt lên đồ vật thường (mục tiêu `0`).
6. **`borrowed_pictures`**: Số hình mượn ngoài tranh chính, tổng giây, tỷ lệ thời lượng, khoảng trống dài nhất không có hình mượn (mục tiêu `<= 120s`), và số cảnh `< 3,0s` (mục tiêu `0`).
7. **`short_shots`**: Số cảnh thường (không phải cảnh chương trình/nhãn hiệu/mở đầu) có thời lượng `< 2,5s` (mục tiêu `0`).
8. **`repeated_regions`**: Năm vùng của tranh chính được dùng nhiều cảnh nhất (mục tiêu tối đa `4 lần/vùng`).
9. **`subject_not_shown`**: Số dòng hoặc moment có chủ thể cụ thể nhắc tới nhưng khung hình không chiếu chủ thể đó (`VC._subject_not_on_screen` hoặc `moments_subject_not_shown`, mục tiêu `0`).
10. **`unfilled_identity`**: Số cảnh mốc chương (`ID-MARK-*`) hoặc nhận diện (`ID-BRAND-*`) có độ phủ khung `< 0.95` (mục tiêu `0`).
11. **`loudness`**: Độ lớn tiếng tổng thể (LUFS, LRA, true peak) sau xuất video từ `export.json` / `measure_loudness` (mục tiêu `-15,0 ± 1,5 LUFS`).
12. **`pause_vs_speech`**: Độ chênh mức RMS dBFS giữa khoảng lặng giữa lời nói (`>= 0,5s`, cắt mép `0,15s`) và phần có lời nói đo trực tiếp từ MP4 xuất bằng `ffmpeg` (mục tiêu `6–22 dB` dưới lời).

## 2. Kết quả nghiệm thu dữ liệu thật

Chạy trên bản sao read-only của `arnolfini-v3` và `eligius` trong `D:\code\behind-the-image\run\snap-scorecard\real_data\` (đầu ra đồng bộ sang `real_output\<key>\7_quality\`, tổng cộng 10 tệp cho mỗi dự án: `scorecard.json`, `scorecard.md`, `record.json`, `record.md`, `sheets\sheet_01..06.jpg`).

### 2.1. `arnolfini-v3` (*The Arnolfini Portrait*, 117 cảnh, 11 phút 13 giây — **3/12 đạt**)

| Chỉ số | Kết quả | Mục tiêu | Đánh giá |
|---|---|---|---|
| Tranh chính nhỏ giữa hai dải đen | 11,4% (76,6 giây / 21 cảnh) | Tối đa 6% | Ngoài mục tiêu |
| Số dấu chỉ mỗi phút | 4,46/phút (50 dấu: 27 vòng tròn, 23 đèn rọi) | Tối đa 3,0/phút | Ngoài mục tiêu |
| Dấu chỉ lớn nhất so với chiều cao khung | 267,6% (31 dấu > 30%; 5 dấu > 100%) | Không quá 30% | Ngoài mục tiêu |
| Dấu chỉ đặt lên người | 9 | 0 | Ngoài mục tiêu |
| Nhãn tên trên màn hình | 9 nhãn (2 lặp tên, 1 trên vật thường) | 0 lặp tên, 0 vật thường | Ngoài mục tiêu |
| Hình mượn ngoài tranh | 5 hình (20,4 giây, 3,0%; trống dài nhất 554,2 giây; 0 < 3 giây) | `>= 3,0s/hình`, trống `<= 120s` | Ngoài mục tiêu |
| Cảnh thường ngắn dưới 2,5 giây | 0 | 0 | Đạt |
| Vùng tranh lặp lại nhiều nhất | 5 lần (`FULL_UPPER`, `WOMAN_HEAD`) | Tối đa 4 lần/vùng | Ngoài mục tiêu |
| Đoạn nhắc chủ thể nhưng không chiếu | 5 | 0 | Ngoài mục tiêu |
| Mốc chương / tên kênh chưa phủ kín khung | 5 | 0 | Ngoài mục tiêu |
| Độ lớn tiếng tổng thể | -14,1 LUFS (LRA 3,1; đỉnh -1,2 dB) | -15,0 ± 1,5 LUFS | Đạt |
| Độ chênh khoảng lặng so với lời nói | 16,8 dB dưới lời (lời -13,2 dB; lặng -30,0 dB; 102 khoảng lặng / 69,0s) | 6–22 dB dưới lời | Đạt |

### 2.2. `eligius` (*St. Eligius*, 110 cảnh, 10 phút 49 giây — **10/11 đạt**, 1 chưa áp dụng)

| Chỉ số | Kết quả | Mục tiêu | Đánh giá |
|---|---|---|---|
| Tranh chính nhỏ giữa hai dải đen | 2,2% (14,0 giây / 3 cảnh) | Tối đa 6% | Đạt |
| Số dấu chỉ mỗi phút | 0,37/phút (4 dấu: 2 vòng tròn, 2 đèn rọi) | Tối đa 3,0/phút | Đạt |
| Dấu chỉ lớn nhất so với chiều cao khung | 38,8% (3 dấu > 30%) | Không quá 30% | Ngoài mục tiêu |
| Dấu chỉ đặt lên người | 0 | 0 | Đạt |
| Nhãn tên trên màn hình | 14 nhãn (0 lặp tên; chưa xét vật thường vì thiếu `subjects`) | 0 lặp tên, 0 vật thường | Đạt |
| Hình mượn ngoài tranh | 34 hình (214,5 giây, 33,1%; trống dài nhất 76,5 giây; 0 < 3 giây) | `>= 3,0s/hình`, trống `<= 120s` | Đạt |
| Cảnh thường ngắn dưới 2,5 giây | 0 | 0 | Đạt |
| Vùng tranh lặp lại nhiều nhất | 0 (storyboard chỉ đặt `params.camera`, không gắn `slots.image.region`) | Tối đa 4 lần/vùng | Đạt |
| Đoạn nhắc chủ thể nhưng không chiếu | Chưa có dữ liệu (`no_subjects`) | 0 | Chưa áp dụng |
| Mốc chương / tên kênh chưa phủ kín khung | 0 | 0 | Đạt |
| Độ lớn tiếng tổng thể | -15,0 LUFS (LRA 3,0; đỉnh -1,6 dB) | -15,0 ± 1,5 LUFS | Đạt |
| Độ chênh khoảng lặng so với lời nói | 20,5 dB dưới lời (lời -14,2 dB; lặng -34,7 dB; 95 khoảng lặng / 68,7s) | 6–22 dB dưới lời | Đạt |

## 3. Đối chiếu số đo `arnolfini-v3` với đếm tay

| Hạng mục | Đếm tay (`TASK.md`) | Scorecard | Giải thích chênh lệch (nếu có) |
|---|---|---|---|
| Tổng số cảnh | 117 | 117 | Khớp chính xác. |
| Tranh chính nhỏ | 73 s (10,8%) | 76,6 s (11,4%, 21 cảnh) | Khớp rất sát ở ngưỡng `small_painting_cover_threshold = 0.70` (đã nâng từ `0.60` sau khi xem tờ ảnh thấy các cảnh `0.621–0.682` vẫn lộ hai dải đen lớn). |
| Vòng tròn / đèn rọi | 27 vòng, 23 rọi | 27 vòng tròn, 23 đèn rọi (4,46/phút) | Khớp chính xác. |
| Vòng tròn khổng lồ | 4 (0:02, 0:18, 4:40, 8:40) | 5 `> 100%` (thêm `s0350 CHANDELIER` 157,4% ở 4:49), tổng 31 dấu `> 30%` | Scorecard đếm cả vòng tròn quanh đèn chùm phóng to vượt chiều cao khung; 4 cảnh đếm tay đều nằm trong top 5 (`s0477`, `s0382`, `s0471`, `s0489`). |
| Dấu đặt lên người | Vòng tròn quanh mặt ở 0:12, 3:24 | 9 dấu (`WOMAN_FIGURE`, `DOORWAY_FIGURES`, các roundel Chúa Kitô) | `HUSBAND_FACE` (0:12) và `STRAW_HAT` (3:24) chưa gắn vùng `kind: "person"` trong `picks.subjects` nên không tự nhận là người; ngược lại `ROUNDELS_*` và `CRUCIFIXION_ROUNDEL` có `Christ` là `person`. |
| Nhãn tên (`name_strips`) | 9 nhãn, 2 lặp tên, 1 vật thường (`Carved saint`) | 9 nhãn, 2 lặp tên (`Giovanni Arnolfini`, `Costanza Trenta`), 1 vật thường (`Carved saint`) | Khớp chính xác sau khi bỏ đối chiếu `also` trong `_strip_sub_repeats` (tránh báo nhầm `Philip the Good` / `Duke of Burgundy`). |
| Hình mượn | 5 hình, 20,4 s, trống 1:38–10:52 | 5 hình, 20,36 s (3,0%), trống 554,2 s (1:38 đến 10:52) | Khớp chính xác. |
| Mốc chương / tên kênh chưa phủ kín | Chương 3 và 7 cột hẹp | 5 cảnh: `ID-BRAND-04` (0:50, 37,5%) và các chương `ID-MARK-01` số 3, 5, 6, 7 (59,6%) | Phát hiện đầy đủ cả mở bài `ID-BRAND-04` lẫn các chương đứng giữa khung hẹp (`< 95%`). |
| Loudness & pause | -14,1 LUFS, pause ~12 dB dưới lời | -14,1 LUFS; pause trung bình -30,0 dB vs lời -13,2 dB (**16,8 dB**) | `loudness` khớp tuyệt đối. Chênh lệch ~4,8 dB ở `pause_vs_speech` đến từ cách lọc khoảng lặng `>= 0,5s` cắt mép `0,15s` và RMS toàn dải trên MP4 (`find_exported_video` chấp nhận video đã xuất khi chỉ `music_sig` thay đổi). |

## 4. Quan sát từ tờ ảnh (`sheet_01..06.jpg`) và lỗi còn sót ở video thật

Cả hai dự án đều xuất 6 tờ ảnh `5x4` (`2400px` rộng, tile `480x270`, huy hiệu `#cảnh · mm:ss`, lấy mẫu từ video MP4 tại `first_mark_start + 1.3s` hoặc điểm giữa cảnh):

- **`arnolfini-v3`** ([sheet_01](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/.scratch/scorecard/sheets/arnolfini-v3/sheet_01.jpg) – [sheet_06](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/.scratch/scorecard/sheets/arnolfini-v3/sheet_06.jpg)):
  - `#2 · 0:04` (`BAND_TOP` 115%) và `#4 · 0:19` (`WOMAN_FIGURE` 268%): vòng tròn khổng lồ cắt ngang đầu/mặt nhân vật và mép trên/dưới khung hình; `#4` đồng thời mang nhãn lặp tên `"COSTANZA TRENTA / PROBABLY COSTANZA TRENTA..."`.
  - `#11 · 0:55`: chữ `"RAKING LIGHT"` dịch sát cạnh trên, đè nhẹ huy hiệu thời gian và nằm trên nền tối kéo dài.
  - `#10 · 0:47`, `#12 · 1:01`, `#13 · 1:06`, `#14 · 1:13`, `#28 · 2:28`, `#40 · 3:40`, `#42 · 3:47`, `#54 · 4:59`, `#58 · 5:24`, `#98 · 9:29`, `#117 · 11:08`: nhiều cảnh dùng toàn khung bức tranh hẹp giữa hai dải đen lớn ở hai bên (chính xác là nhóm `0.375–0.682` bị chỉ số #1 bắt được).
  - `#35 · 3:15` (`TABARD`) đặt nhãn tên sát mép dưới vùng cắt quần áo; `#47 · 4:17` (`CARVED SAINT`) gắn nhãn lên tượng chạm khắc (vật thường).
  - `#69 · 6:47` (các vòng quanh gương) và `#102 · 9:56` (`Brass chandelier` / `Mirror glass`): chữ `KEY-01` nhỏ, mảnh trên nền tối/nền tranh, khó đọc ở kích thước thumbnail.

- **`eligius`** ([sheet_01](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/.scratch/scorecard/sheets/eligius/sheet_01.jpg) – [sheet_06](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/.scratch/scorecard/sheets/eligius/sheet_06.jpg)):
  - Chất lượng cắt cảnh tốt hơn rõ rệt (10/11 đạt), tuy nhiên vẫn lộ các lỗi ảnh mượn và tỉ lệ: `#29 · 2:35` (đồng xu nền trắng gắt), `#32 · 2:51` (di vật có bảng thước đo màu `ColorChecker` ở góc dưới trái), `#42 · 3:46` (`MEDIEVAL FINGER RING` có thước đo bảo tàng trắng to ở hai cạnh), `#72 · 6:55` (chú thích dài gần chạm mép phải), `#10 · 0:45`, `#26 · 2:22`, `#36 · 3:14`, `#101 · 9:56`, `#109 · 10:37`, `#110 · 10:44` còn dải đen hai bên, và `#81 · 7:51` ghép đôi hai tranh để viền đen dưới mỗi ô.

## 5. Kết quả kiểm thử và kiểm tra tài liệu

- **Tạo lại tài liệu**: đã chạy `bti.cli.docgen` ([skills/export/SKILL.md](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/skills/export/SKILL.md)) và `bti.editor.hints` ([docs/AGENT_API.md](file:///Users/nhanvu/Documents/code/behind-the-image/.worktrees/scorecard/docs/AGENT_API.md)).
- **Doc `--check` trên `winbox-cmd`**: `bti.cli.docgen --check`, `bti.ops.doc --check`, `bti.editor.hints --check` đều thoát mã `0`.
- **Mac (`node`)**:
  - `node --check bti/editor/static/js/labels.js bti/editor/static/js/errmsg.js bti/editor/static/js/scorecardlogic.js bti/editor/static/js/views/export.js`: qua (mã `0`).
  - `node --test tests/editor_frontend/*.test.mjs tests/picks/*.test.mjs tests/output/*.test.mjs`: `508` tests (`507 passed, 0 failed, 1 skipped` — `sbissues.test.mjs` skip mặc định trong worktree).
- **Server `winbox-cmd` (`pytest` theo từng thư mục liên quan)**:
  - `tests/scorecard`: `12 passed`
  - `tests/output`: `81 passed`
  - `tests/export`: `87 passed, 2 skipped`
  - `tests/editor`: `534 passed`
  - `tests/ops`: `561 passed`
  - `tests/auto`: `270 passed`
  - `tests/cli`: `132 passed`
  - `tests/state/test_docs.py`: `4 passed`
  - `tests/draft`: `643 passed`
  - `tests/picks`: `506 passed`
  - `tests/identity`: `106 passed`
  - `tests/music`: `34 passed`
  - `tests/engine -m "not slow"`: `854 passed, 14 skipped, 168 deselected`
- **Ghi chú phạm vi**: Không chạm vào mã `music` sẵn có trên nhánh nền (`tests/state/test_errors.py` lỗi `music_invalid` từ `bti/export/run.py:259` và `tests/state/test_state.py` thiếu `music.set`/`music.clear` và `scorecard.make` trong `EXPECTED`). Các thư mục không liên quan như `tests/script` / `tests/voice` / `tests/outline` không bị ảnh hưởng bởi `bti/scorecard/`.
