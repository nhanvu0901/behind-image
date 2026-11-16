from pathlib import Path
import re
p=Path('docs/research/great-art-explained/corpus/EFFECTS_CATALOG.md');old=p.read_text(); rows={}
for l in old.splitlines():
 m=re.match(r'^\| ((?:CAM|TR|LAY|HI|AN|TXT|DIA|CMP|STATIC|SHORT)-\d+)\b',l)
 if m:
  cells=[x.strip() for x in l.strip('|').split('|')];rows[m.group(1)]=cells
rows.pop('STATIC-03',None)
clips={'CAM-01':'crCPVoPsTtk-815-push-in','TR-01':'crCPVoPsTtk-695-dissolve','TR-02':'cuHgxPe3J7I-1892-slide-in-out','TXT-02':'cuHgxPe3J7I-1095-scroll-text','AN-01':'M4IUt7QZh6U-775-circle-draw','HI-02':'eKyYPSpiC9g-1194-figure-reveal','HI-01':'9x0tsuS4dk0-1352-spotlight','TR-03':'vBG621XEegk-733-panel-opening','DIA-01':'ceKSyMJjniU-1255-projection-rays','DIA-02':'ceKSyMJjniU-1314-skull-view','DIA-03':'ElWG0_kjy_Y-498-diagram-light'}
for id,f in clips.items(): rows[id][1]+=f' [clip](../../../../research_media/great-art-explained/effect-excerpts/{f}.mp4).'
def add(id,title,body,certainty):rows[id]=[id+' '+title,body,certainty]
def extra(id,txt):rows[id][1]+=' '+txt
extra('LAY-01','Thêm [so sánh phim và tranh, HOPPER-CINEMA-01](visual-b/mQVC0qJGJ_c.md) ~00:42–01:02; [tranh và footage địa hình](visual-a/3wfWuVne0LU.md) 200.200–220.220s.')
extra('LAY-04','Biến thể toàn tranh cạnh nhiều ô chi tiết và vòng đánh dấu: `2zfjf4uD94s` 730.730–750.750s [A-V03](visual-a/2zfjf4uD94s.md); là bố cục tĩnh.')
extra('AN-01','Hai vòng giao nhau được vẽ: `H8fGd3fCJbg` 1660.025–1664.530s [A-N07](visual-a/H8fGd3fCJbg.md), dense-1660.')
extra('TXT-01','Biến thể thẻ chữ nâu nền trắng: `T9JvUDrrXmY` 190.190s, 350.350s [A-T9-02](visual-a/T9JvUDrrXmY.md); trạng thái tĩnh.')
extra('CAM-03','Thêm pull-out `lKIbT-4UFaE` ~00:00–00:20 [NIGHTHAWKS-01](visual-b/lKIbT-4UFaE.md), chuỗi 1fps.')
extra('CAM-05','Thêm `SNhmSdLDmto` ~05:20–05:40 [KISS-04](visual-b/SNhmSdLDmto.md) dịch ngang kèm zoom; `yUq9qMm9NtI` 20.020–39.539s [A-CAM-06](visual-a/camera_examples.md) tiến về trên-phải; không gọi là pan thuần.')
extra('TR-01','Thêm footage cửa hàng chồng/hòa tranh `mQVC0qJGJ_c` ~07:40–07:45 [HOPPER-CINEMA-02](visual-b/mQVC0qJGJ_c.md), chuỗi 1fps.')
extra('TR-04','Thêm `T15Kv6dtYO0` ~04:39–04:41 [ARNOLFINI-04](visual-b/T15Kv6dtYO0.md), mẫu 1fps không loại trừ transition ngắn.')
add('HI-03','Giữ màu trên nền đơn sắc','Nhân vật còn màu trong khi phần còn lại đen trắng; cần ảnh và vùng xử lý màu. `wDjq2gPGIHk` 343.143–360.360s [A-wDj-02](visual-a/wDjq2gPGIHk.md).','Trạng thái; không suy phương pháp mask hay thời gian hiện.')
add('AN-07','Trường chấm dày dần','Chấm màu mờ tăng mật độ thành trường chấm; cần nền và lớp chấm với các trạng thái. `AJr2T1ko3Is` 0–19.520s [A-AJr-05](visual-a/AJr2T1ko3Is.md), dense-0/10; [clip 5–17s](../../../../research_media/great-art-explained/effect-excerpts/AJr2T1ko3Is-5-point-field.mp4).','Motion cao; không suy cách tạo hoặc chuyển thành tranh.')
add('CMP-04','Mảng màu và gạch đối chiếu','Hình giản lược thành mảng màu, hoặc ô gạch cạnh chi tiết tranh; cần ảnh và hình/ô so sánh. `z2hgtFBBbxk` 570.570s, 640.640s [A-z2-05](visual-a/z2hgtFBBbxk.md).','Tĩnh, trung bình; không suy animation.')
add('CMP-05','Hai trạng thái màu cảnh','Cùng cảnh cầu xanh và ngả vàng; cần hai ảnh đối chiếu. `fd-Me3EBGYY` 690.690–700.700s [A-fd-04](visual-a/fd-Me3EBGYY.md).','Hai trạng thái; chưa xác định transition.')
add('DIA-06','Mô hình phòng và ảnh UV','Minh họa phòng với tranh và ảnh chi tiết có nhãn UV; cần asset sơ đồ phòng hoặc ảnh ghi nhận, và ảnh tư liệu UV. `fsz6bkkIHzQ` 490.490s, 540.540s, 600.600s [A-fsz-03](visual-a/fsz6bkkIHzQ.md).','Tĩnh; mô hình biểu kiến không chứng minh 3D số hay loại thiết bị.')
add('DIA-07','Sơ đồ mắt và thị giác','Ba hình và sơ đồ mắt có nhãn; cần hình minh họa và chữ. `ElWG0_kjy_Y` ~25:27–25:47 [MONA-06](visual-b/ElWG0_kjy_Y.md).','Tĩnh; không suy animation hay độ chính xác y học.')
add('FOOT-01','Footage vật liệu, thao tác và palette','Xen footage tranh, quy trình, trang sách thật hoặc bảng màu kèm nhãn. `YFI6cQF1ros` ~15:52–16:12 [MENINAS-05](visual-b/YFI6cQF1ros.md); `Bgo6H0tzszA` 3.036–50.050s [A-P01](visual-a/Bgo6H0tzszA.md).','Tư liệu nguồn; không quy chuyển động của nó thành hiệu ứng dựng.')
add('LAY-08','Hình lặp / đối xứng','Hình bánh xe lặp đối xứng; cần asset lặp tương ứng. `Bj7FJGrxtXY` 370.370–390.390s [A-D04](visual-a/Bj7FJGrxtXY.md).','Trạng thái; chưa biết là đặc tính ảnh nguồn hay dựng.')
headers=[('CAM','Camera và khung nhìn'),('TR','Chuyển ảnh và lộ hình'),('LAY','Bố cục và ghép lớp'),('HI','Nhấn vùng / lộ nhân vật'),('AN','Nét chú thích và hình học'),('TXT','Typography'),('STATIC','Yếu tố tĩnh / nhãn / bản đồ'),('DIA','Sơ đồ và biểu diễn không gian'),('CMP','Ảnh đối chiếu và tư liệu kỹ thuật'),('FOOT','Footage và chất liệu nguồn'),('SHORT','Shorts: bằng chứng riêng')]
s=['# Great Art Explained — danh mục thị giác và chuyển động','', 'Đã xem mẫu có hệ thống **86/86 MP4 sẵn có**, không phải mọi frame; 7 ID thiếu nêu trong [REVIEW_STATUS](REVIEW_STATUS.md). Documentary dài, Cities, talk/live và Shorts là các ngữ cảnh khác nhau. Danh mục là những kỹ thuật/yếu tố được ghi nhận trong mẫu, không khẳng định phát hiện mọi hiệu ứng của kênh. Mốc `~` là gần đúng; các báo cáo dẫn tới sheet gốc, clip cục bộ không âm thanh. Motion đã thấy khi có chuỗi gần nhau; trạng thái tĩnh không chứng minh animation. Không suy phần mềm, kỹ thuật mask, 3D số hay nguồn vật liệu nếu bằng chứng chưa đủ.','', 'Mỗi dòng là một record duy nhất; các ví dụ cùng kỹ thuật không được đếm thêm. Thông tin theo từng video, ngày đăng khi có, thời lượng/resolution và trạng thái xem mẫu nằm tại [manifest](manifest.tsv).']
for prefix,title in headers:
 s+=['',f'## {title}','','| Record | Hành vi, asset và bằng chứng | Giới hạn / kiểm chứng |','|---|---|---|']
 for k in sorted(rows):
  if k.split('-')[0]!=prefix:continue
  row=rows[k]; c=row+[""]*(3-len(row));s.append('| '+' | '.join(c[:3])+' |')
s+=['','## Ngữ cảnh và các phần còn chờ','', '- **Documentary chính:** đa số ví dụ crop, so sánh, đồ họa phân tích và chapter thuộc phim dài; các ví dụ trong bảng ghi rõ video.','- **Great Art Cities:** dùng thêm footage địa điểm/phỏng vấn và bản đồ, ví dụ [Venice](visual-b/f8OIYzV5Npo.md).','- **Talk/live:** [live](visual-a/live-cgTvoB6XHdA.md) và [talk](visual-a/tEEq5DTRXr0.md) được xem mẫu riêng, không mặc định cùng nhịp documentary.','- **Shorts:** [13 Shorts có local](visual-shorts/coverage.md) đã xem mẫu tỉ lệ gốc; phần Shorts trên là các bằng chứng riêng, không mặc định áp dụng phim dài.','- **Intro/sponsor/outro:** là vị trí sử dụng các primitive, không tính thành hiệu ứng dựng riêng; phân biệt hình ghi sách/vật thể thật với đồ họa.','', 'Các nhánh pan ngang/chéo thuần, wipe, quỹ đạo camera liên tục, timing cut chính xác và easing chưa có bằng chứng đủ; pan lên, pull-back, zoom kèm dịch đã có chuỗi. Bảy video chưa có MP4 không được suy đoán.']
p.write_text('\n'.join(s)+'\n');print('records',len(rows),'families',len(headers))
