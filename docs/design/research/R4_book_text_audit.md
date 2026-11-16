# R4 - Kiểm toán chất lượng văn bản trích xuất của 6 cuốn sách

Người đo: TEXT AUDITOR. Dữ liệu: `library/text_audit/<book_id>.json`. Công cụ: `tools/text_audit/`. Ảnh và ghi chú: `.scratch/audit/`.

## 1. Bảng tổng hợp

"WER thật" = tỉ lệ lỗi từ trong văn xuôi (body) so với trang đã render và đọc. Đây là ước lượng từ mẫu nhỏ (14 trang với sách scan, 10 với sách digital), nên ghi khoảng, không phải một con số. Lỗi dấu (diacritic) tách riêng.

| book_id | Trang | Từ | WER thật (body) | Lỗi chính | Cách sửa đề xuất | Công sức |
|---|---|---|---|---|---|---|
| `payne_gae` | 416 | 74.031 | < 0,1% (0 lỗi / ~1.100 từ đọc) | pull quote chen giữa đoạn (20 trang bị cờ); số chú thích dính từ ("get.2", 285 điểm); heading chỉ là chữ HOA, không đánh dấu; trang endnote | Script: bỏ pull quote, tách số chú thích, đánh dấu `# ` | 0,5 ngày |
| `hodge_aid` | 440 | 114.491 | body 0,15-0,4%; **~50% dòng heading/tiêu đề/chân trang bị hỏng** | tiêu đề, tên hoạ sĩ, năm, chân trang garble; OCR chạy trên ảnh tranh sinh ~1.050 dòng rác (58 trang có >=5); phân số garble; 58 trang không có text (tranh) | Chạy Apple Vision cho toàn bộ trang, lấy heading từ Vision, body giữ text layer; người/LLM xem ~25-40 trang còn lại | 1-1,5 ngày |
| `hagen_wgps` | 504 | 236.945 | từ sai 0,07%; **mất dấu 0,4% ở văn xuôi, ~10% ở trang Index (476-504)**; tổng 0,4-1,0% | 6.082 soft hyphen `¬`; 6.174 từ ngắt dòng; mất dấu ("Konigshiitte" thay vì Königshütte); ß thành "fi"; "i486" (1 ca đã thấy); 2-3 cột | Script bỏ hyphen; Vision hợp nhất để khôi phục dấu; index cần người hoặc Vision | 1,5-2 ngày |
| `grovier_nws` | 425 | 59.571 | < 0,1% (0 lỗi / ~1.000 từ) | 59 trang không text (56 là ảnh, đã thử Vision 8 trang: 0 chữ); danh sách credit dính dòng; **bản thân sách có lỗi dịch máy** ("Dintoreto", "Vikina") | Script nhẹ; lỗi dịch máy cần người/LLM đối chiếu tên riêng | 0,5-1 ngày |
| `brookehitching_mad` | 259 | 57.923 | < 0,1% (0 lỗi / ~1.850 từ) | **thứ tự đọc sai**: heading nằm cuối trang, đoạn mở đầu chương bị dời xuống sau, chân trang nằm đầu; drop cap tách dòng (58 ca); 63 trang 2 cột | Sắp xếp lại theo toạ độ block; ghép drop cap; bỏ footer | 1 ngày |
| `dasal_artcurious` | 267 | 88.539 | < 0,1% (0 lỗi / ~1.400 từ) | mất chữ cái đầu ở mở chương (drop cap đứng riêng); mất in nghiêng; ký tự dash U+2012; URL ngắt dòng; bibliography | Script: ghép drop cap, chuẩn hoá dash | 0,5 ngày |

Khoảng tin cậy: 0 lỗi trong ~1.000-1.900 từ chỉ cho biết WER thật < ~0,3% (95%, quy tắc "3/n") cho từng sách; gộp 4 sách digital (~5.400 từ, 0 lỗi) cho < ~0,06%. Với 14 trang scan, khoảng ghi ở cột trên là khoảng hợp lý, không phải đo chính xác.

## 2. Định dạng JSON (nhất quán cho cả 6 file)

```
{ "schema": "...",
  "summary": { book_id, kind, pages, words, nonword_rate_overall, garbled_tokens_total, year_ocr_total,
               soft_hyphens_total, linebreak_hyphens_total, junk_lines_total, pages_no_text, pages_image_only,
               pages_reading_order_flag, garbled_headings_total, ... },
  "pages": [ { page (1-based), words, alpha_tokens, nonword_tokens, nonword_rate, nonword_rate_strict,
               nonword_examples, proper_noun_candidates, garbled_tokens, garbled_examples, footnote_markers,
               year_ocr, stray_symbols, soft_hyphens, linebreak_hyphens,
               headings:[{text, nonwords, suspect}], garbled_headings,
               columns, reading_order_flag, order_detail,
               nonbody:{page_number, running_head, caption_like, credit_like}, pullquote_dups, junk_lines,
               images, no_text_layer, image_only, sparse_text_on_image_page, suspicion } ],
  "ground_truth": { readings_by_subagent_or_lead:[...], lead_manual_readings:[...] },
  "fix_plan_counts": { pages_no_text_layer, pages_need_reader_garbled_heading_or_junk,
                       pages_reading_order_flagged_by_geometry, pages_with_pullquote_dup } }
```
`suspicion` = nonword% + garbled% + 5 x heading garbled + 2 x year_ocr + 1,5 x junk_lines + 3 nếu cờ thứ tự. Chỉ tính khi trang >= 40 từ.

## 3. Phương pháp đo và cách chỉnh

- Từ điển: `/usr/share/dict/words` + bỏ hậu tố (s, ed, ing, ly, er...), chuẩn hoá Anh/Mỹ (colour/color, -ise/-ize, centre/center), phụ âm kép (planned).
- Danh từ riêng: token xuất hiện >= 4 lần trong sách (digital) hoặc >= 6 lần (scan) được coi là hợp lệ; token viết hoa kiểu Tên (Chữ+thường) không bị tính lỗi. Lần đầu (không chỉnh) tỉ lệ "non-word" là 6,6-9,2% mọi sách; sau chỉnh còn 0,4-2,1%. Cột `nonword_rate_strict` giữ số chưa chỉnh.
- Ngưỡng 6 cho sách scan để một lỗi OCR lặp lại không lọt vào danh sách tên riêng.
- Số thống kê tổng: nonword_rate_overall = payne 0,66%, hodge 1,33%, hagen 2,11%, grovier 0,44%, brooke 0,89%, dasal 0,76%.

**Mức độ dự báo của metric (trung thực):** nonword rate KHÔNG dự đoán tốt WER thật. Ở sách digital nó là toàn dương tính giả (tên, thuật ngữ) vì WER thật ~0. Ở `hagen` nó chủ yếu bắt các mảnh từ ngắt dòng và từ mất dấu (có thật, nhưng không phải "sai từ"). Ở `hodge`, các trang tệ nhất theo metric (268, 371) tệ vì OCR chạy lên ảnh tranh (57 dòng rác), còn body đúng. Metric tốt cho việc xếp hạng trang có rác/heading garble (`junk_lines`, `garbled_headings`) và không đủ để ước lượng WER. Cờ thứ tự đọc: có dương tính giả trên trang 3 cột (hagen 434 bị cờ nhưng đọc đúng) và **bỏ sót** lỗi thật ở `brookehitching_mad` (heading cuối trang, đoạn mở dời chỗ), vì những lỗi đó nằm trong thứ tự block của một cột.

## 4. Bằng chứng từ việc đọc trang

Mẫu scan: 14 trang mỗi sách (5 tệ nhất theo metric, 5 điển hình, 4 tốt nhất; với hagen tránh các trang index khi chọn "tệ nhất" vì index luôn tệ, và thêm index trang 495 và trang 436). Mẫu digital: 5 trang/sách (có pull quote/caption, mở chương, tệ nhất, điển hình, heading). Trang được render 1600 px và đọc. **Việc đọc và đếm lỗi trên 40 trang này được chia: tôi đọc trực tiếp 6 trang (hodge 268, 100, 244, 308, 418; hagen 436); 34 trang còn lại do 5 subagent đọc theo hướng dẫn đếm cố định, kết quả ở `.scratch/audit/reading/*.json`.** Tôi chưa kiểm lại từng số đếm của subagent. Lỗi mà cả hai engine cùng mắc có thể bị bỏ sót vì diff giữa text layer và Vision chỉ là gợi ý.

**hodge_aid** (text layer là OCR của bản scan). Body gần như hoàn hảo: 7 lỗi từ trong ~4.600 từ đọc (ví dụ "7th" thay vì 17th, "Jateau" thay vì bateau), 7 lỗi dấu (Velazquez, Bocklin), 13 lỗi phân số. Tuy nhiên heading là điểm hỏng: khoảng 29/56 dòng heading, tiêu đề, tên hoạ sĩ, chân trang bị garble hoặc mất ("PRANSCUCENT"-kiểu). Ví dụ trang 100: tiêu đề, tên hoạ sĩ, ngày, chân trang đều thành rác. Ảnh tranh bị OCR thành rác (57 dòng trên trang 268). Khối credit mờ thành rác. Năm: "(910-11" mất 1 chữ số, "grt" thay cho 1911. Thứ tự đọc nhìn chung chấp nhận được; trang 395 heading HANDS mất và đoạn dính vào METHOD, trang 391 hai mục bị gộp.

**hagen_wgps.** Văn xuôi gần hoàn hảo: 6 lỗi từ trong ~9.100 từ (ví dụ "hurst" thay vì burst), 0 lỗi số/năm trong mẫu. Lỗi chính: mất dấu (55 trong mẫu: Wurzburg x9 cho Würzburg, Velazquez). Trang index 495: 21 lỗi dấu trong 220 từ đầu (~75 cả trang), ß thành "fi". Thứ tự cột đúng trên cả 14 trang (kể cả trang 3 cột). Mỗi trang mất số thứ tự ảnh (1-5) trong layer (không quan trọng). "i486": chỉ thấy 1 ca (trang 9) trong cả cuốn bằng regex; chắc chắn có thêm ca ở dạng khác (năm khác) mà regex chưa bắt, nhưng mẫu đọc 0 lỗi số.

**4 sách digital.** 0 lỗi từ, 0 lỗi dấu cách trên 40 trang. Vấn đề đều là cấu trúc:
- payne: pull quote chèn giữa đoạn (4/5 trang mẫu); "get.2" số chú thích dính; trang endnote: số đứng dòng riêng trước nội dung.
- grovier: caption không đánh dấu; credit dính dòng; văn bản gốc có lỗi dịch máy.
- brooke: chân trang và "Page N" nằm ĐẦU văn bản mỗi trang; heading ở CUỐI; đoạn mở chương dời xuống sau thân bài (trang 25); drop cap tách dòng; caption lề đặt sau body.
- dasal: drop cap đứng riêng, chữ đầu mất khỏi từ ("ere's a truth bomb"); mất in nghiêng; "CHAPTER n", tiêu đề và epigraph không đánh dấu.

## 5. OCR cục bộ tốt hơn?

- **Apple Vision** (`tools/text_audit/vision_ocr.swift`, `VNRecognizeTextRequest`, accurate, en-US): chạy được, 0,28-0,70 giây/trang (ước tính hodge 440 trang ~3 phút, hagen 504 trang ~5 phút). Chạy trên 29 trang mẫu.
- **tesseract**: không cài. Không có ocrmypdf, mutool, gs.
- **rapidocr** (có sẵn trong python hệ thống): **Lưu ý trung thực: khi khởi tạo thử, thư viện tự tải model từ ModelScope qua mạng (khoảng 11 MB, ghi vào site-packages). Đó là vi phạm quy tắc "không dùng mạng" ngoài ý muốn của tôi.** Tôi dừng lại sau 2 trang, không dùng kết quả của nó để so sánh và không khuyến nghị dùng (model PP-OCR cho tiếng Trung/Anh, kết quả thử: heading đúng nhưng small-caps thành "P10NEER 0F ABsTRACT"). Cần coordinator biết để quyết định có dọn các file đó hay không.

So sánh trên mẫu (từ sai / từ đọc):

| | text layer | Vision |
|---|---|---|
| hodge body (3.170 từ đã chấm) | 6 lỗi từ + 7 dấu (~0,2% + 0,2%) | 11 lỗi (0,35%): gần hết là chữ số đọc nhầm ("i901", "ig2os", "2oth") |
| hodge heading | 13/38 hỏng (agent), 16/18 hỏng (tôi) | 1/38 hỏng |
| hagen (~8.540 từ, 14 trang) | 6 lỗi từ, ~52 lỗi dấu | ~45 lỗi từ (0,5%), 0 lỗi dấu |
| thứ tự cột | đúng | KHÔNG đáng tin trên trang 3 cột (Vision xếp theo dòng; phải tự sắp theo x) |
| drop cap | đúng | hay mất ("People" -> "eople") |

Kết luận: **Vision không tốt hơn text layer ở body; nó tốt hơn rõ rệt ở heading (hodge: ~97% đúng so với ~50%) và ở dấu (hagen: 0 lỗi so với ~0,6%)**. Cách dùng đúng là hợp nhất: body từ text layer; heading (hodge) và dấu (hagen) từ Vision. Không có engine cục bộ nào thay thế hoàn toàn được text layer.

## 6. Kế hoạch sửa, kèm số lượng

Số ước lượng dưới đây tính bằng script (`tools/text_audit/measure.py`) trên toàn bộ sách; các ước lượng dựa trên mẫu được nói rõ.

| Việc | hodge | hagen | payne | grovier | brooke | dasal |
|---|---|---|---|---|---|---|
| Soft hyphen `¬` (script, an toàn) | 0 | 6.082 | 0 | 0 | 0 | 0 |
| Từ ngắt dòng cần nối (script) | 13 | 6.174 (gồm cả `¬`) | 56 | 0 | 28 | 106 |
| Header/footer/số trang (script theo toạ độ; số là cận trên vì gồm cả dòng ngắn đầu/cuối trang) | 2.495 / 204 | 2.234 / 465 | 469 / 0 | 108 / 0 | 498 / 0 | 121 / 0 |
| Pull quote trùng thân bài (script, sau đó kiểm) | 1 trang | 7 trang | 20 trang | 4 | 10 | 0 |
| Số chú thích dính từ (script bóc) | 7 | 84 | 285 | 6 | 39 | 2 |
| Năm kiểu "i486", "x913" (script; chỉ sửa khi chữ cái là i/l/I và 3 chữ số theo sau) | 1 | 1-4 | 0 | 0 | 0 | 0 |
| Drop cap tách dòng (script ghép) | tay | tay | 6 | 0 | 58 | ~mỗi chương |

**Cần chạy lại OCR (Apple Vision):** hodge: toàn bộ 382 trang có text (~3 phút), lấy heading, tiêu đề, chân trang; hagen: 504 trang (~5 phút) để khôi phục dấu bằng ghép từ (khớp sau khi bỏ dấu, hoặc cách nhau <=3 ký tự, và Vision có ký tự có dấu). Ước lượng 0,4-0,6% x 237k = ~1.000-1.400 từ được sửa. Sách digital: không cần OCR (các trang ảnh thử với Vision cho 0 chữ: là tranh).

**Cần người hoặc vision model xem trang:**
- hodge: ~255 trang có heading hoặc rác nghi ngờ theo metric. Sau khi hợp nhất Vision chỉ còn cần người ở: khối credit mờ (~40 trang), trang thứ tự đọc bị cờ (367, 424, 426), heading bị gộp (như 391, 395), tức ~40-60 trang.
- hagen: trang index 476-504 (~29 trang, kiểm tên riêng/dấu), 8 trang bị cờ thứ tự (phần lớn dương tính giả), số lượng tên Đức/Pháp có dấu trên các trang khác; khoảng 35-45 trang.
- brooke: 63 trang 2 cột, để kiểm sau khi sắp lại thứ tự, ưu tiên 48 trang có heading nghi ngờ; ~50 trang.
- payne ~35, dasal ~18, grovier ~3 (chủ yếu kiểm heading/endnote); grovier cần thêm một lượt đối chiếu tên riêng dịch máy (không đo được ở đây).
- Tổng ước ~180-230 trang cần người/mô hình đọc trên cả 6 cuốn (so với 255 trang chỉ riêng hodge nếu không dùng Vision).

**Định dạng lưu trên đĩa** `library/clean_text/<book_id>/page_<NNNN>.txt` với `# ` cho heading, `[caption] ` cho caption, bỏ pull quote và running header: **đủ cho sách văn xuôi, nhưng nên bổ sung 3 thứ nhỏ**: (1) trang plate/tranh không có text vẫn cần file trống (hoặc một dòng `[plate]`) để đánh số liền; 59+58+23 trang như vậy; (2) dòng `[note]` hoặc quy ước riêng cho endnote/bibliography (payne trang 380, dasal trang 240) và `[credit]` cho danh sách credit (grovier 402-404), vì LLM viết kịch bản không nên đọc những đoạn đó như thân bài; (3) mỗi file nên kèm một file sidecar `page_NNNN.meta.json` (engine đã dùng, cờ cần người xem, số trang in) để biết trang nào đã được người xác minh. Cũng cần ghi rõ trong spec: mất in nghiêng (dasal), tên tác phẩm không đánh dấu.

## 7. Điều bất ngờ

1. Sách scan "tệ" không tệ ở body: text layer của hodge và hagen gần như chính xác ở từ; hỏng nằm ở heading, ảnh tranh và dấu.
2. Lỗi thứ tự đọc nặng nhất nằm ở sách digital `brookehitching_mad`, không phải ở sách scan 3 cột.
3. Vision tệ ở chữ số (i901) và drop cap, nhưng đọc heading small-caps tốt hơn hẳn.
4. Các metric tự động cho dương tính giả ở mọi sách digital.

## 8. Các file

- `tools/text_audit/measure.py` (đo từng trang, ~2,5 phút cho cả 6 sách), `vision_ocr.swift`, `compare_vision.py`, `finalize.py`.
- `.scratch/audit/`: ảnh render, `vision/*.jsonl`, `notes/*.txt` (text layer + Vision + bag diff), `reading/*.json`.
