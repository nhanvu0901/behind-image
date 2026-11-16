# Ví dụ camera và thay đổi khung hình — Visual A

Các PTS là thời gian nguồn; chuỗi contact sheet đã xem trực tiếp tại `research_media/great-art-explained/analysis-a/<id>/dense-<start>/`. Mẫu chuỗi cách khoảng 0,25–0,6 giây, không phải phát liên tục từng frame; mô tả phương hướng theo vùng tranh được lộ ra. Không đo easing.

| ID | Kỹ thuật | Bằng chứng PTS và hướng | Tin cậy |
|---|---|---|---|
| A-CAM-01 | Zoom-out / pull-back 2D | `83ggxS21mFM` 30.030 → 40.007 → 49.516: đầu sọ và hoa thu nhỏ đều quanh vùng giữa, thêm nền trời và sừng xuất hiện; sau đó mép tranh hiện trên matte đen. Hai sheet `dense-30`, `dense-40`. | Cao trong phạm vi mẫu |
| A-CAM-02 | Pan dọc lên | `lAjVuUB9AkI` 930.029 → 935.034 → 939.539: cùng chân dung nét gạch, khung dần lộ vùng mắt/trán phía trên, cằm dịch ra dưới; `dense-930`. Tỷ lệ xấp xỉ ổn định. | Trung bình–cao |
| A-CAM-03 | Zoom-in + dịch khung | `TU3dRcqik3I` 1011.010 → 1016.015 → 1020.770: cặp nhân vật lớn dần; cây và nhân vật đổi vị trí tương đối với viền khung, khung tiến về cặp ở phía trái của bố cục. `dense-1011` hai sheet. | Cao cho zoom và dịch khung; chưa tách chính xác pan khỏi tâm zoom |
| A-CAM-04 | Giữ khung + chữ xuất hiện | `lHePKNTRmdI` 0–9.600 cùng tranh ở giữa matte, nhãn trắng xuất hiện khoảng 6–7.2; `dense-0`. | Cao |
| A-CAM-05 | Zoom-in | `crCPVoPsTtk` 816.015–822.021, khung Starry Night tiến gần ~1,12×; `9x0tsuS4dk0` 1358.023–1361.026 ~1,046×; đã ghi trong `two-samples.md`. | Cao |

Chưa có ví dụ đủ rõ đã kiểm chuỗi cho pan ngang hoặc pan chéo thuần; không suy diễn từ các ảnh cách 10 giây. Ví dụ giữ khung rồi cut-in được kiểm bổ sung bên dưới.
# Bổ sung: crop chuyển động và cut-in

| ID | Ví dụ đã xem dày | Quan sát | Tin cậy |
|---|---|---|
| A-CAM-06 | `yUq9qMm9NtI` 20.020–39.539s; `dense-20/sheet-01.jpg`, `dense-30/sheet-01.jpg` | Cùng một tranh phóng dần; cột buồm đi sang trái và nhân vật ra hiệu tiến gần trung tâm, khung hình tiến về vùng trên-phải của tranh. Đây là zoom kết hợp đổi vị trí, không đủ tách riêng pan thuần. | Cao |
| A-CAM-07 | `AJr2T1ko3Is` 485.018–490.023s; `dense-485/sheet-01.jpg` | Giữ toàn tranh trên đen qua 489.522; tới 490.023 chuyển đột ngột sang crop nhóm người. Chuỗi mẫu 0,5s xác nhận thay đổi bố cục dạng cut-in, thời điểm chính xác trong khoảng giữa hai mẫu. | Cao |

