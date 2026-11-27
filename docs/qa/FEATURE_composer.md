# Composer QA

## Constants

| Setting | Value |
|---|---:|
| `shot_min_s` | 2.5 |
| `borrowed_min_s` | 3.0 |
| `device_min_s` | 3.0 |
| `strip_line_min_s` | 1.5 |
| `strip_extra_word_s` | 0.3 |
| `strip_base_words` | 3 |
| `strip_max_s` | 4.0 |
| `strip_main_s` | 3.0 |
| `strip_fade_s` | 0.0 |
| `mark_side_max` | 0.4 |
| `mark_height_max` | 0.3 |
| `mark_area_max` | 0.08 |
| `spotlight_floor` | 0.6 |
| `ring_min_frame_width` | 0.012 |
| `ring_max_frame_height` | 0.15 |

## Scheduler

Equal adjacent SHOWs are joined first. A borrowed picture is moved toward the sentence start while the previous view retains its minimum. If it is too short, remaining backward room to that start is used, then forward slack, then remaining backward slack. Two neighbouring pictures of the same sentence can become a pair, with both images and captions visible from the first frame; the pair covers the sentence by shifting or joining neighbouring views, subject to program boundaries. Otherwise an adjacent ordinary view is joined into the borrowed picture before dropping it. The scheduler partitions at program card boundaries, and any dropped picture is noted. Introduction timing may extend forward or join the next non-borrowed view. Every unsuccessful repair removes an entry or marks an unavailable introduction, so the loop is bounded. A video shorter than the minimum cannot satisfy the minimum; it is retained and noted.

## Real-data scorecards

The source project documents and their referenced media were copied into the isolated Windows snapshot. The saved originals and the composed versions were scored and rendered with the scorecard still renderer. The original project directories were read-only. Engine validation of both composed copies returned zero errors.

### Arnolfini before

| Chỉ số | Kết quả | Mục tiêu | Đánh giá |
|---|---|---|---|
| Tranh chính nhỏ giữa hai dải đen | 11,4% (76,6 giây / 21 cảnh) | Tối đa 6% | Ngoài mục tiêu |
| Số dấu chỉ mỗi phút (đèn rọi / vòng tròn) | 4,46/phút (50 dấu: 27 vòng tròn, 23 đèn rọi) | Tối đa 3,0/phút | Ngoài mục tiêu |
| Dấu chỉ lớn nhất so với chiều cao khung | 267,6% (31 dấu > 30%) | Không quá 30% | Ngoài mục tiêu |
| Dấu chỉ đặt lên người | 9 | 0 | Ngoài mục tiêu |
| Nhãn tên trên màn hình | 9 nhãn (2 lặp tên, 1 trên vật thường) | 0 lặp tên, 0 vật thường | Ngoài mục tiêu |
| Hình mượn ngoài tranh | 5 hình (20,4 giây, 3,0%; khoảng trống dài nhất 554,2 giây; 0 hình < 3 giây) | Mỗi hình >= 3,0 giây, không trống quá 120 giây | Ngoài mục tiêu |
| Cảnh thường ngắn dưới 2,5 giây | 0 | 0 | Đạt |
| Vùng tranh lặp lại nhiều nhất | nhiều nhất 5 lần (Full-width band: ceiling, heads, mirror) | Tối đa 4 lần/vùng | Ngoài mục tiêu |
| Đoạn nhắc tới chủ thể nhưng không chiếu | 40 | 0 | Ngoài mục tiêu |
| Mốc chương hoặc đoạn tên kênh chưa phủ kín khung | 5 | 0 | Ngoài mục tiêu |
| Độ lớn tiếng tổng thể | Chưa có (chưa xuất video) | -15,0 ± 1,5 LUFS | Chưa áp dụng |
| Độ chênh nhạc trong khoảng lặng so với lời nói | Chưa có (chưa xuất video) | 6–22 dB dưới lời | Chưa áp dụng |

### Arnolfini after

| Chỉ số | Kết quả | Mục tiêu | Đánh giá |
|---|---|---|---|
| Tranh chính nhỏ giữa hai dải đen | 5,2% (35,0 giây / 10 cảnh) | Tối đa 6% | Đạt |
| Số dấu chỉ mỗi phút (đèn rọi / vòng tròn) | 0,36/phút (4 dấu: 0 vòng tròn, 4 đèn rọi) | Tối đa 3,0/phút | Đạt |
| Dấu chỉ lớn nhất so với chiều cao khung | 24,6% (0 dấu > 30%) | Không quá 30% | Đạt |
| Dấu chỉ đặt lên người | 0 | 0 | Đạt |
| Nhãn tên trên màn hình | 7 nhãn (0 lặp tên, 0 trên vật thường) | 0 lặp tên, 0 vật thường | Đạt |
| Hình mượn ngoài tranh | 5 hình (23,6 giây, 3,5%; khoảng trống dài nhất 554,2 giây; 0 hình < 3 giây) | Mỗi hình >= 3,0 giây, không trống quá 120 giây | Ngoài mục tiêu |
| Cảnh thường ngắn dưới 2,5 giây | 0 | 0 | Đạt |
| Vùng tranh lặp lại nhiều nhất | nhiều nhất 5 lần (Full-width band: ceiling, heads, mirror) | Tối đa 4 lần/vùng | Ngoài mục tiêu |
| Đoạn nhắc tới chủ thể nhưng không chiếu | 40 | 0 | Ngoài mục tiêu |
| Mốc chương hoặc đoạn tên kênh chưa phủ kín khung | 0 | 0 | Đạt |
| Độ lớn tiếng tổng thể | Chưa có (chưa xuất video) | -15,0 ± 1,5 LUFS | Chưa áp dụng |
| Độ chênh nhạc trong khoảng lặng so với lời nói | Chưa có (chưa xuất video) | 6–22 dB dưới lời | Chưa áp dụng |

### Eligius before

| Chỉ số | Kết quả | Mục tiêu | Đánh giá |
|---|---|---|---|
| Tranh chính nhỏ giữa hai dải đen | 2,2% (14,0 giây / 3 cảnh) | Tối đa 6% | Đạt |
| Số dấu chỉ mỗi phút (đèn rọi / vòng tròn) | 0,37/phút (4 dấu: 2 vòng tròn, 2 đèn rọi) | Tối đa 3,0/phút | Đạt |
| Dấu chỉ lớn nhất so với chiều cao khung | 38,8% (3 dấu > 30%) | Không quá 30% | Ngoài mục tiêu |
| Dấu chỉ đặt lên người | 0 | 0 | Đạt |
| Nhãn tên trên màn hình | 14 nhãn (0 lặp tên, chưa xét) | 0 lặp tên, 0 vật thường | Đạt |
| Hình mượn ngoài tranh | 34 hình (214,5 giây, 33,1%; khoảng trống dài nhất 76,5 giây; 0 hình < 3 giây) | Mỗi hình >= 3,0 giây, không trống quá 120 giây | Đạt |
| Cảnh thường ngắn dưới 2,5 giây | 0 | 0 | Đạt |
| Vùng tranh lặp lại nhiều nhất | 0 | Tối đa 4 lần/vùng | Đạt |
| Đoạn nhắc tới chủ thể nhưng không chiếu | 0 | 0 | Đạt |
| Mốc chương hoặc đoạn tên kênh chưa phủ kín khung | 0 | 0 | Đạt |
| Độ lớn tiếng tổng thể | Chưa có (chưa xuất video) | -15,0 ± 1,5 LUFS | Chưa áp dụng |
| Độ chênh nhạc trong khoảng lặng so với lời nói | Chưa có (chưa xuất video) | 6–22 dB dưới lời | Chưa áp dụng |

### Eligius after

| Chỉ số | Kết quả | Mục tiêu | Đánh giá |
|---|---|---|---|
| Tranh chính nhỏ giữa hai dải đen | 63,5% (412,1 giây / 33 cảnh) | Tối đa 6% | Ngoài mục tiêu |
| Số dấu chỉ mỗi phút (đèn rọi / vòng tròn) | 0,37/phút (4 dấu: 0 vòng tròn, 4 đèn rọi) | Tối đa 3,0/phút | Đạt |
| Dấu chỉ lớn nhất so với chiều cao khung | 15,8% (0 dấu > 30%) | Không quá 30% | Đạt |
| Dấu chỉ đặt lên người | 0 | 0 | Đạt |
| Nhãn tên trên màn hình | 0 nhãn (0 lặp tên, chưa xét) | 0 lặp tên, 0 vật thường | Đạt |
| Hình mượn ngoài tranh | 32 hình (205,2 giây, 31,6%; khoảng trống dài nhất 76,5 giây; 0 hình < 3 giây) | Mỗi hình >= 3,0 giây, không trống quá 120 giây | Đạt |
| Cảnh thường ngắn dưới 2,5 giây | 0 | 0 | Đạt |
| Vùng tranh lặp lại nhiều nhất | 0 | Tối đa 4 lần/vùng | Đạt |
| Đoạn nhắc tới chủ thể nhưng không chiếu | 0 | 0 | Đạt |
| Mốc chương hoặc đoạn tên kênh chưa phủ kín khung | 0 | 0 | Đạt |
| Độ lớn tiếng tổng thể | Chưa có (chưa xuất video) | -15,0 ± 1,5 LUFS | Chưa áp dụng |
| Độ chênh nhạc trong khoảng lặng so với lời nói | Chưa có (chưa xuất video) | 6–22 dB dưới lời | Chưa áp dụng |

## Arnolfini small-painting views

The final scorecard reports 5.2% (35.0 seconds) versus 11.4% before. The opening deliberately shows the whole work; explicit whole SHOWs stay whole. A detail may start on a wider prior frame, and small sources can soften when the composer raises zoom to fill the frame. Each counted shot and its source follows:

- `s0000` at 0.00s: program opening intentionally shows the whole painting (1.65s counted).
- `s_m0001` at 1.65s: the script explicitly asks for the whole painting (5.83s counted).
- `s_m0010` at 62.63s: the script explicitly asks for the whole painting (3.49s counted).
- `s_m0012` at 77.24s: the script explicitly asks for the whole painting (2.68s counted).
- `s_m0047` at 283.12s: the script explicitly asks for the whole painting (4.36s counted).
- `s_m0057` at 360.55s: the script explicitly asks for the whole painting (1.91s counted).
- `s_m0061` at 393.77s: the script explicitly asks for the whole painting (5.46s counted).
- `s_m0082` at 523.84s: the script explicitly asks for the whole painting (4.19s counted).
- `s_m0095` at 611.98s: the script explicitly asks for the whole painting (2.15s counted).
- `s_m0108` at 664.73s: the script explicitly asks for the whole painting (3.25s counted).

## Frame inspection

I inspected all six Arnolfini and all four Eligius composed contact sheets, plus saved-version sheets. Arnolfini frames 1–2 have the actual artwork title, artist and year; frames 3–4 name the two people without the old giant rings. Frame 11 shows the ident and frame 12 a chapter mark over a filling frame. In Eligius the converted visual script contains 66 whole SHOWs because old shots without a region were converted to whole; the after sheet visibly repeats the whole painting and the small-painting share worsens from 2.2% to 63.5%. Its converted pool lacks captions for many borrowed images, so they remain uncaptioned and generate notes. The composer cannot infer missing source captions or invent new details.

Five note choices checked against the Arnolfini frames:

- m0009, frame 10: raising the region zoom gives a frame-filling view of both figures; the note correctly warns that a small source may soften.
- m0002, frame 3: omitting the HUSBAND_FACE mark is right; dropping the repeating subtitle removes the cautious wording, so the displayed name looks more certain than the source intended.
- m0003, frame 4: omitting the WOMAN_FIGURE mark is right; the same loss of caution remains in its subtitle.
- m0048, frame 52: omitting a mark on the large chandelier avoids a giant light; the much smaller candle remains the useful target.
- m0105, frame 112: extending the picture makes the Diego Velázquez strip visible; the original overlong subtitle was omitted, so its explanation is lost.

## All Arnolfini compose notes

### C1

- `m0016` (frame 19): extended backward toward sentence start
- `m0015` (frame 18): shortened to make room for the following picture
- `m0043` (frame joined): joined into m0042
- `m0105` (frame 112): extended backward toward sentence start
- `m0104` (frame 111): shortened to make room for the following picture
- `m0101` (frame joined): joined into m0100
- `m0106` (frame joined): joined into m0105 to fit introduction

### C3

- `m0002` (frame 3): raised region zoom to fill the frame; a small source may look softer
- `m0009` (frame 10): raised region zoom to fill the frame; a small source may look softer
- `m0011` (frame 14): raised region zoom to fill the frame; a small source may look softer
- `m0017` (frame 20): raised region zoom to fill the frame; a small source may look softer
- `m0024` (frame 28): raised region zoom to fill the frame; a small source may look softer
- `m0036` (frame 40): raised region zoom to fill the frame; a small source may look softer
- `m0037` (frame 42): raised region zoom to fill the frame; a small source may look softer
- `m0042` (frame 47): framed the union of listed point targets
- `m0048` (frame 52): framed the union of listed point targets
- `m0049` (frame 53): raised region zoom to fill the frame; a small source may look softer
- `m0052` (frame 57): raised region zoom to fill the frame; a small source may look softer
- `m0058` (frame 63): raised region zoom to fill the frame; a small source may look softer
- `m0062` (frame 68): raised region zoom to fill the frame; a small source may look softer
- `m0063` (frame 69): framed the union of listed point targets
- `m0064` (frame 70): framed the union of listed point targets
- `m0077` (frame 84): raised region zoom to fill the frame; a small source may look softer
- `m0083` (frame 90): raised region zoom to fill the frame; a small source may look softer
- `m0087` (frame 94): raised region zoom to fill the frame; a small source may look softer
- `m0089` (frame 97): raised region zoom to fill the frame; a small source may look softer
- `m0093` (frame 101): framed the union of listed point targets
- `m0093` (frame 101): raised region zoom to fill the frame; a small source may look softer
- `m0096` (frame 104): raised region zoom to fill the frame; a small source may look softer
- `m0097` (frame 105): framed the union of listed point targets
- `m0103` (frame 110): raised region zoom to fill the frame; a small source may look softer

### C4

- `m0105` (frame 112): extended forward for introduction
- `m0106` (frame joined): start moved later to fit the previous introduction
- `m0105` (frame 112): extended forward for introduction by joining the next moment
- `m0002` (frame 3): subtitle omitted because it repeats the name or exceeds six words
- `m0003` (frame 4): subtitle omitted because it repeats the name or exceeds six words
- `m0016` (frame 19): subtitle omitted because it repeats the name or exceeds six words
- `m0031` (frame 35): intro could not fit or its cast member has no strip
- `m0104` (frame 111): subtitle omitted because it repeats the name or exceeds six words
- `m0105` (frame 112): subtitle omitted because it repeats the name or exceeds six words

### C6

- `m0002` (frame 3): mark HUSBAND_FACE omitted: person, large, outside frame, or too late
- `m0003` (frame 4): mark WOMAN_FIGURE omitted: person, large, outside frame, or too late
- `m0005` (frame 6): mark DOG omitted: person, large, outside frame, or too late
- `m0006` (frame 7): mark DOORWAY_FIGURES omitted: person, large, outside frame, or too late
- `m0007` (frame 8): mark DOORWAY_GLOW omitted: person, large, outside frame, or too late
- `m0027` (frame 31): mark BLUE_HEM omitted: person, large, outside frame, or too late
- `m0033` (frame 37): mark STRAW_HAT omitted: person, large, outside frame, or too late
- `m0034` (frame 38): mark BOOTS omitted: person, large, outside frame, or too late
- `m0035` (frame 39): mark JEWELLERY omitted: person, large, outside frame, or too late
- `m0040` (frame 45): mark BENCH_CUSHION omitted: person, large, outside frame, or too late
- `m0042` (frame 47): mark CARVED_SAINT omitted: person, large, outside frame, or too late
- `m0043` (frame joined): mark CARVED_SAINT omitted: person, large, outside frame, or too late
- `m0044` (frame 48): mark RUG omitted: person, large, outside frame, or too late
- `m0045` (frame 49): mark ORANGES omitted: person, large, outside frame, or too late
- `m0046` (frame 50): mark WINDOW omitted: person, large, outside frame, or too late
- `m0047` (frame 51): mark CHERRY_TREE omitted: person, large, outside frame, or too late
- `m0048` (frame 52): mark CHANDELIER omitted: person, large, outside frame, or too late
- `m0050` (frame 54): mark MIRROR omitted: person, large, outside frame, or too late
- `m0054` (frame 59): mark DOORWAY_GLOW omitted: person, large, outside frame, or too late
- `m0055` (frame 60): mark RAISED_HAND omitted: person, large, outside frame, or too late
- `m0060` (frame 65): mark ROUNDELS_MAN omitted: person, large, outside frame, or too late
- `m0062` (frame 68): mark CRUCIFIXION_ROUNDEL omitted: person, large, outside frame, or too late
- `m0063` (frame 69): mark ROUNDELS_MAN omitted: person, large, outside frame, or too late
- `m0063` (frame 69): mark ROUNDELS_WOMAN omitted: person, large, outside frame, or too late
- `m0064` (frame 70): mark ROUNDEL_DEPOSITION omitted: person, large, outside frame, or too late
- `m0064` (frame 70): mark ROUNDEL_ENTOMBMENT omitted: person, large, outside frame, or too late
- `m0064` (frame 70): mark ROUNDEL_RISING omitted: person, large, outside frame, or too late
- `m0064` (frame 70): mark ROUNDEL_DESCENT omitted: person, large, outside frame, or too late
- `m0064` (frame 70): mark ROUNDELS_WOMAN omitted: person, large, outside frame, or too late
- `m0065` (frame 71): mark ROUNDELS_WOMAN omitted: person, large, outside frame, or too late
- `m0071` (frame 77): mark JOINED_HANDS omitted: person, large, outside frame, or too late
- `m0076` (frame 83): mark ORANGES omitted: person, large, outside frame, or too late
- `m0077` (frame 84): mark ORANGES omitted: person, large, outside frame, or too late
- `m0080` (frame 87): mark DOG omitted: person, large, outside frame, or too late
- `m0081` (frame 88): mark TABARD omitted: person, large, outside frame, or too late
- `m0082` (frame 89): mark CARVED_SAINT omitted: person, large, outside frame, or too late
- `m0084` (frame 91): mark DOG omitted: person, large, outside frame, or too late
- `m0085` (frame 92): mark CARVED_SAINT omitted: person, large, outside frame, or too late
- `m0086` (frame 93): mark JOINED_HANDS omitted: person, large, outside frame, or too late
- `m0093` (frame 101): mark CHANDELIER omitted: person, large, outside frame, or too late
- `m0093` (frame 101): mark WHITE_HEADDRESS omitted: person, large, outside frame, or too late
- `m0094` (frame 102): mark SILL_ORANGE_REFLECTION omitted: person, large, outside frame, or too late
- `m0095` (frame 103): mark SILL_ORANGE_REFLECTION omitted: person, large, outside frame, or too late
- `m0097` (frame 105): mark ROUNDELS_WOMAN omitted: person, large, outside frame, or too late
- `m0098` (frame 106): mark DOG omitted: person, large, outside frame, or too late

## Fixture paintings

The two 400-by-300 fixture paintings were composed, validated without engine errors and rendered as still sheets. Both scorecards reported 10/10 applicable targets passing. I inspected each sheet: the raised zoom fills the frame, and now distinguish the intended vertical regions, but the views remain visually broad and the tiny source is enlarged past the shared camera sharpness cap. This softening is recorded as C3 notes; a higher-resolution source would help.

## Known limitations and other ownership

- LAY-01 now offers `entrance=together` for pairs. Its default remains `slide`, preserving existing storyboards. A program or locked boundary can prevent a pair from covering a complete sentence; such conflicts are noted.
- The quality target reader currently reads the separate style `quality` block, not `compose`; making the scorecard consume the identical table belongs to the scorecard module, outside this worker’s scope.
- C6 and V8 use the coordinator’s definition: a region named by a person cast member or fully inside one of that member’s regions is a person; names and partial overlaps alone do not decide it.
- The four `tests/state` failures were reproduced against the clean `f11277d` archive: `test_every_code_in_the_source_has_a_hint` reports `music_invalid` at `bti/export/run.py:259`; `drafted` differs at index 24 (`music.set` versus `picks.suggest`); `storyboard_approved` differs at index 23 (`music.set` versus `picks.suggest`); `exported` differs at index 22 (`music.set` versus `export.start`). Each action-list failure reports three additional items. The archive-only run had a fifth fixture failure because the Git archive omitted the ignored demo audio; the normal snapshot has that audio and does not have that fifth failure.
- Very short inputs or conflicts with immutable locked boundaries can make the duration floor impossible. The composer preserves the content and records a note rather than inventing extra time.

## Tests

Final Windows snapshot: compose 39 passed; draft 642 passed and one time-sensitive failure at the server’s midnight passed on immediate rerun (the earlier full run passed all 643); picks 506; editor 534; auto 270; ops 565; cli 132; export 87 passed and 2 skipped; identity 108; music 34; engine 858 passed, 14 skipped and 168 slow deselected; state 323 passed and the four baseline failures described above; scorecard 12; visual 47; output 81. All three documentation generators passed `--check`. Mac: `node --check` passed for the changed labels file; frontend, picks and output JavaScript tests passed 507, with one skipped.
