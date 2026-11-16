# S — So sánh lời kể: kênh mình và đối thủ (2026-11-12)

**Dữ liệu.** Kênh mình có 4 narration đã đăng, lấy chỉ-đọc từ server: `narration.json`, `word_timestamps.json` và `audio.wav` (bản chỉ có giọng, dùng để đo khoảng lặng). Đối thủ có 77 transcript đăng từ 29/09 đến 03/11, gọi là "recent". Đây là bộ duy nhất có ngày đăng, nên không lọc được mốc 01/09 cho phần còn lại. Ngoài ra có 3.808 transcript cũ ("archive"), dùng quartile view **đã bù tuổi video** trong từng kênh, tính từ audit 01/10. Script: `analyze_scripts.py`; kết quả: `metrics.json`, `run.log`; nhãn đọc tay: `hand_labels_first_sentence.json`. Mọi phân loại câu mở/câu kết đều là heuristic từ khóa trên text ASR.

## Bảng so sánh

| Nhóm | n | View trung vị | Từ câu 1 | Mở bằng câu hỏi | "What if" | Nói số issue | Từ/giây | Từ <3 s | Từ <10 s | Trung vị độ dài câu | Câu >25 từ | FK | Có slang | Câu kết CTA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Mình (4)** | 4 | 1.638 | 17 | 75% | 50% | **100%** | **2,96** | 9 | **29,5** | 23,5 | 43% | 10,7 | 0% | **75%** |
| ↳ CA 2099 (thắng) | 1 | 8.216 | 14 | ✓ | ✓ | ✓ | 3,28 | 11 | 33 | 25 | 43% | 10,6 | – | ✓ |
| ↳ Iron Man 11 | 1 | 1.931 | 18 | ✓ | – | ✓ | 2,95 | 9 | 31 | 22 | 43% | 12,9 | – | – |
| ↳ Abs. Superman 25 | 1 | 1.345 | 19 | – | – | ✓ | 2,98 | 9 | 28 | 20 | 12% | 9,4 | – | ✓ |
| ↳ Doomquest 5 | 1 | 1.311 | 16 | ✓ | ✓ | ✓ | 2,80 | 9 | 27 | 28 | 57% | 10,7 | – | ✓ |
| ComicsUnlocked recent | 7 | 28.600 | 18 | 14% | 0 | 0 | 3,49 | 11 | 36 | 20 | 12% | 10,6 | 0% | 0 |
| ComicCandid recent | 34 | 13.398 | 15,5 | 6% | 0 | 0 | 3,46 | 10 | 35 | 15 | 0% | 7,9 | 32% | 0 |
| Comic_Escape recent | 32 | 21.773 | 14,5 | 3% | 0 | 0 | 3,99 | 11 | 38 | 25 | 50% | 13,6 | 9% | 0 |
| comiczyt / GiyeSears recent | 2 / 2 | 13.708 / 10.961 | 52 / 9 | 0 / 50% | 0 | 0 | 3,65 / 3,54 | 10 / 8,5 | 36 / 32 | 32 / 16 | – | – | – | 0 |
| **Đối thủ recent, gộp** | 77 | 15.928 | 16 | 7% | 0% | **0%** | **3,61** | 11 | **36** | 18 | 11% | 9,1 | 18% | **0%** |
| Recent, top quartile | 22 | 29.295 | 17 | 4% | 0 | 0 | 3,63 | 11 | 36,5 | 17,5 | 11% | 8,7 | 18% | 0 |
| Recent, bottom quartile | 19 | 6.016 | 14 | 5% | 0 | 0 | 3,55 | 11 | 37 | 16 | 7% | 8,9 | 21% | 0 |
| Archive gộp | 3.808 | 52.000 | 14 | 19% | 2% | 0,8% | 3,29 | 9 | 32 | 21 | 29% | 10,9 | 15% | 0% |
| Archive top / bottom (bù tuổi) | 922 / 927 | – | 14 / 14 | 18% / 21% | 1% / 2% | 1% / 1% | 3,29 / 3,29 | 10 / 9 | 32 / 32 | 20,5 / 21 | 25% / 29% | 10,9 / 10,9 | 15% / 16% | 0 / 0 |

**Đối thủ kể đúng câu chuyện mình đã làm:**

| Câu chuyện | Video | View | Câu mở | Từ/giây | Từ <10 s | Nói issue | CTA |
|---|---|---:|---|---:|---:|---|---|
| Cap 2099 | Comic_Escape `vexIhVcTz2w` | 251.000 | "What would have happened if Captain America woke up in the year 2099?" | 3,97 | 37 | không | không |
| Cap 2099 | Mình | 8.216 | "What if Captain America stayed frozen in the ice until the year twenty ninety-nine?" | 3,28 | 33 | có (4,2–6,3 s) | có |
| Doomquest | Comic_Escape `07QVv_xRnkc` | 9.283 | "This is how Mr. Fantastic ended up kissing Dr. Doom." (10 từ) | 4,00 | 38 | không | không |
| Doomquest | Mình | 1.311 | "What if Doctor Doom got trapped in the Invisible Woman's body…?" (16 từ) | 2,80 | 27 | có (5,7–8,1 s) | có |

## Các khác biệt, xếp theo khả năng làm người xem lướt đi sớm hoặc không xem hết

1. **Sự kiện đầu tiên của truyện đến muộn (7–10 giây).** *Đo được:* ở 3/4 video của mình, sự kiện có thật đầu tiên bắt đầu ở 6,95 s (CA), 10,0 s (Iron Man) và 10,4 s (Doom); riêng Brainiac ở 0,4 s. Trong 10 giây đầu, mình dành 4–7 s cho hook rồi 2,1–2,5 s cho câu dẫn issue. Theo nhãn đọc tay, 70% (54/77) video đối thủ recent đã nêu một sự kiện cụ thể ngay câu 1; mốc tự động có trung vị 2,2 s. Câu 1 của mình chỉ nêu sự kiện ở 1/4 video. *Suy luận:* đây là khác biệt có nhiều khả năng ảnh hưởng tới tỉ lệ chọn xem so với lướt qua. **Độ tin cậy: trung bình.**
2. **Nói chậm hơn, nên 10 giây đầu ít nội dung hơn.** *Đo được:* mình nói 2,96 từ/giây, đối thủ recent 3,61 và archive 3,29. Mình chậm hơn 95% video đối thủ recent; trong 10 giây đầu mình nói được 27–33 từ, đối thủ 36. Video nhanh nhất của mình (CA, 3,28) cũng là video nhiều view nhất; video chậm nhất (Doom, 2,80, giọng machiavelli với exaggeration 0,35) ít view nhất. *Lưu ý:* trong corpus đối thủ, tốc độ nói không liên quan tới view sau khi bù tuổi (ρ≈0,008; top và bottom đều 3,29). **Độ tin cậy: đo chắc chắn, còn tác động thì thấp–trung bình.**
3. **Mở bằng câu hỏi hoặc "what if" cho một chuyện có thật.** *Đo được:* 75% câu mở của mình là câu hỏi, 50% là "what if". Đối thủ recent có 7% câu hỏi và 0% "what if"; archive có 19% và 2%; top và bottom không khác nhau (18% so với 21%). Cách này hợp với CA, vốn đúng là truyện *What If* và đối thủ cũng mở y như vậy. Với Doom, chuyện đã thật sự xảy ra lại bị kể như giả định, trong khi đối thủ kể cùng chuyện bằng một câu khẳng định 10 từ. **Độ tin cậy: thấp–trung bình.**
4. **Câu kết luôn là "Make sure to subscribe for more…".** *Đo được:* 3/4 video của mình kết như vậy (Iron Man thì không), mất 1,9–2,4 s, tức 4–5% thời lượng. Đối thủ: **0/3.885** transcript có CTA. Cả 8 kết quả regex ban đầu đều là "like if" nằm trong câu chuyện. *Suy luận:* câu này báo hiệu video đã hết trước khi video thật sự hết, và khiến cuối video không nối vòng về đầu. **Độ tin cậy: thấp–trung bình.**
5. **Câu dẫn issue nằm ở câu 2 trong mọi video.** *Đo được:* mình 4/4, đối thủ recent 0/77, archive 31/3.885 (0,8%). Khi đối thủ có nói issue, thời điểm cũng tương tự mình (trung vị khoảng 6,5 s), và các video ComicsUnlocked có nói issue không hề ít view (trung vị khoảng 1M, n=16). Vì vậy bản thân việc nói issue chưa chắc gây hại; điều có thể gây hại là nó đẩy sự kiện ra sau (xem mục 1). **Độ tin cậy: thấp.**
6. **Những khác biệt nhỏ hoặc không khác.** Câu dài: mình có 43% câu trên 25 từ, đối thủ 11%. Nhưng Comic_Escape, kênh mạnh nhất trong nhóm recent, có 50% câu trên 25 từ, và cùng câu chuyện họ viết câu dài 37–59 từ, nên câu dài không phân biệt được. Tương tự với độ khó FK, tỉ lệ dùng "you" (0 so với 7%), từ cảm xúc (0,6 so với 0,8 trên 100 từ) và số từ trước tên nhân vật đầu tiên (2 so với 1). Slang và chi tiết hài: mình 0%, ComicCandid 32%; trong archive, hài xuất hiện ở 20% top và 19% bottom, nên không liên quan. Câu kết bằng bài học (Iron Man) chiếm khoảng 9–10% ở cả top lẫn bottom. **Độ tin cậy: thấp.**
7. **Lỗi trong text đã đưa vào TTS của Iron Man.** `narration.json` (đã được hash TTS) có "Negative Zone orever. once and for all", "his fragile go" và một câu 51 từ. Bản đăng dài 56,8 s, còn audio.wav dài 61,3 s, nên chưa xác nhận được bản đăng có giữ những lỗi này không.

## CA 2099 khác ba video thường ở đâu (n=1 so với 3, chỉ có tính giai thoại)

CA nói nhanh nhất (3,28 so với 2,80–2,98 từ/giây) và nói nhiều từ nhất trong 3 s và 10 s đầu (11 và 33, so với 9 và 27–31). Hook của CA ngắn nhất (14 từ) và premise "what if" đúng với loại truyện. Video ngắn nhất (46,6 s), twist Red Skull đến ở giây 36 (78%), kết bằng kết cục. Template thì giống hệt ba video kia: có câu dẫn issue, có CTA. Đối thủ đã đạt 251k với chính câu chuyện này, nên chủ đề có lẽ giải thích chênh lệch nhiều hơn câu chữ (audit 01/10: "chủ đề quan trọng hơn câu chữ").

## Hai câu mở viết lại (giữ đủ dữ kiện; câu dẫn issue rút gọn và dời ra sau sự kiện đầu)

**Doomquest 5** (khoảng 36 từ đầu ≈ 10 s ở tốc độ 3,6 từ/giây; sự kiện nằm ngay ở câu 1):
> Doctor Doom made Galactus run away while trapped in the Invisible Woman's body. A time-traveling Doom has his mind swapped into Susan Storm right as the Silver Surfer arrives with Galactus. He quickly masters her force fields, builds solid force-field robots and knocks the Silver Surfer aside. That's Doomquest issue five. …

**Iron Man 11** (dùng hook "This is how", dạng mà audit 01/10 ghi nhận +6,7 điểm % ở top quartile; sự kiện ở từ thứ 11, khoảng 3 s, thay vì 10 s):
> This is how Iron Man planned to beat the Fantastic Four. Reed and Sue Storm take Tony on a double date to confront him about what he's been doing. It turns into a battle of imagined fights, each man picturing how he'd beat the other. When Reed imagines stretching all the way around Iron Man, Tony switches on a device in his armor that freezes him solid. That's Iron Man issue eleven. …

Cả hai bản đều trái với luật hiện hành trong prompt ("câu ngay sau hook phải nêu issue"). Vì vậy chỉ nên dùng làm biến thể A/B, không thay luật ngay.

## Chưa xác định được

- Retention và tỉ lệ chọn xem/lướt qua của mình và đối thủ: không có số liệu, nên mọi mối liên hệ ở trên đều là suy luận, không phải nhân quả.
- Text thật sự được nói trong bản đăng: không có phụ đề YouTube. Riêng Iron Man, thời lượng bản đăng không khớp audio.wav.
- Ngày đăng của archive: không có, nên dùng view đã bù tuổi theo vị trí. Bộ recent chỉ có 7/2/2 video của CU/comiczyt/GiyeSears, và quartile recent chỉ có n=22/19.
- Khoảng lặng của đối thủ: không đo được vì audio có nhạc. Khoảng hở giữa các cue ASR chỉ khoảng 2–3%, còn mình là 3–10% (7–14 lần dừng, trung bình 0,25–0,35 s); cách đo khác nhau nên không so được.
- Script của 36 video cũ hơn của mình chưa được đo, nên chưa biết template thay đổi theo thời gian ra sao.
- Thời điểm sự kiện đầu tiên của đối thủ là đo tự động (danh sách động từ) cộng nhãn đọc tay câu 1. Mốc thời gian của mình là word timestamp nội suy trong từng scene, sai số khoảng ±0,3 s.
