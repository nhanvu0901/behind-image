// Vietnamese text for the validation issues of a STORYBOARD ({level, code, path, message, args?, shot?, overlay?}).
// Used by errmsg.js `issueText` (the one entry point for every issue of the app). Pure; tested in
// tests/editor_frontend/sbissues.test.mjs.
//
// An issue is translated by its stable `code` when the engine gave one and the table knows it, else by the shape of the
// English `message`. A code or message nobody knows still gives a Vietnamese sentence that names the shot and the field;
// the English text is then only in "chi tiết" (`detail`), flagged with `generic: true`.
import { valueLabel } from './labels.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const isVi = (s) => VI.test(String(s || ''));

// ---------------------------------------------------------------- where an issue is
const FIELD = {
  start: 'thời điểm bắt đầu', end: 'điểm kết thúc', dur: 'thời lượng', technique: 'kỹ thuật', intent: 'ý đồ', note: 'ghi chú', locked: 'khóa', source: 'nguồn',
  id: 'mã', params: 'tham số', slots: 'chỗ đặt hình', overlays: 'lớp phủ', transition_in: 'chuyển cảnh', canvas: 'khung hình', fps: 'tốc độ khung hình', assets: 'danh sách hình',
  regions: 'vùng', file: 'tệp', credit: 'ghi nguồn', kind: 'loại', width: 'chiều rộng', height: 'chiều cao', label: 'nhãn', ease: 'kiểu chuyển động', at: 'thời điểm',
  audio: 'âm thanh', approvals: 'phần duyệt', schema: 'phiên bản định dạng', project: 'tên dự án', shots: 'danh sách shot', title: 'tiêu đề', fade_s: 'thời gian mờ dần',
  asset: 'hình', w: 'chiều rộng', h: 'chiều cao', x: 'x', y: 'y', cx: 'tâm ngang', cy: 'tâm dọc', zoom: 'độ phóng',
};
const SHOT_PATH = /^shots\[(\d+)\](?:\.overlays\[(\d+)\])?(?:\.(.+))?$/;

/** { shot, overlay, tail }: the parts of the issue's path. `shot` is "shot s0013" (or "shot thứ 13"), `overlay` "lớp phủ ..." or ''. */
export function whereOf(issue) {
  const path = String(issue?.path || ''), a = issue?.args || {};
  const m = SHOT_PATH.exec(path);
  const sid = issue?.shot || a.shot || null, oid = issue?.overlay || a.overlay || null;
  if (!m && !sid) return { shot: '', overlay: '', tail: path, loc: '' };
  const shot = `shot ${sid || 'thứ ' + (m ? Number(m[1]) + 1 : '?')}`;
  const overlay = m && m[2] != null ? `lớp phủ ${oid || 'thứ ' + (Number(m[2]) + 1)}` : oid ? `lớp phủ ${oid}` : '';
  return { shot, overlay, tail: m ? m[3] || '' : '', loc: overlay ? `${overlay} của ${shot}` : shot };
}
const lastKey = (tail) => { const s = String(tail || '').replace(/\[\d+\]/g, '').split('.').filter(Boolean); return s[s.length - 1] || ''; };
/** The field an issue is about, in words ("thời điểm bắt đầu"); a param name stays as the form shows it. */
export function fieldOf(issue) {
  const w = whereOf(issue), tail = w.loc ? w.tail : String(issue?.path || '');
  const k = lastKey(tail);
  if (/(^|\.)params\./.test(tail)) return k;
  return FIELD[k] || k;
}
const assetKey = (issue) => (/^assets\.([^.]+)/.exec(String(issue?.path || '')) || [])[1] || '';

// ---------------------------------------------------------------- values inside messages
const KIND_VI = { image: 'hình ảnh', video: 'video', mask: 'mặt nạ' };
const kindList = (s) => String(s).split(/ or |, /).map((k) => KIND_VI[k.trim()] || k.trim()).join(' hoặc ');
const q = (s) => `"${s}"`;
const unq = (s) => String(s).replace(/^['"]|['"]$/g, '');

/** The reason of a parameter that does not fit the registry, after "name: ". */
export function paramReason(name, raw) {
  let m;
  const s = String(raw).trim();
  if (isVi(s)) return s.replace(/[.\s]+$/, '');                    // the registry's own hint (pattern_hint)
  if (/^must be a number/i.test(s)) return 'phải là một số';
  if ((m = /^must be >= (\S+)/i.exec(s))) return `không được nhỏ hơn ${m[1]}`;
  if ((m = /^must be <= (\S+)/i.exec(s))) return `không được lớn hơn ${m[1]}`;
  if ((m = /^must be one of (.+)$/i.exec(s))) return 'phải là một trong: ' + m[1].split(/\s*,\s*/).map((v) => valueLabel(v, name)).join(', ');
  if (/^must be true or false/i.test(s)) return 'phải là bật hoặc tắt';
  if (/^must be a string/i.test(s)) return 'phải là chữ';
  if (/^must be a #rrggbb colou?r/i.test(s)) return 'phải là màu dạng #rrggbb';
  if (/^must be a region name or \[x, y\]/i.test(s)) return 'phải là tên một vùng của hình hoặc hai số x, y';
  if (/^empty region name/i.test(s)) return 'tên vùng đang trống';
  if ((m = /^coordinates must be within \+-(\d+)/i.exec(s))) return `tọa độ phải nằm trong khoảng ±${m[1]}`;
  if (/^must be a list of points/i.test(s)) return 'phải là danh sách các điểm';
  if (/^must be a list of strings/i.test(s)) return 'phải là danh sách các dòng chữ';
  if ((m = /^item (\d+): (.*)$/i.exec(s))) return `mục thứ ${Number(m[1]) + 1}: ${paramReason(name, m[2])}`;
  if ((m = /^needs (at least|at most|exactly) (\d+) items? \(got (\d+)\)/i.exec(s))) return `cần ${{ 'at least': 'ít nhất', 'at most': 'nhiều nhất', exactly: 'đúng' }[m[1].toLowerCase()]} ${m[2]} mục (hiện có ${m[3]})`;
  if (/^must be \[x0, y0, x1, y1\]/i.test(s)) return 'phải là một khung gồm bốn số';
  if (/^must lie inside/i.test(s)) return 'phải nằm trong khung hình, góc trên trái phải nhỏ hơn góc dưới phải';
  if (/^camera|camera key/i.test(s)) return 'có đường đi camera chưa đúng (mỗi mốc cần vị trí, tâm và độ phóng)';
  if (/^must be an asset key/i.test(s)) return 'phải chọn một hình';
  if (/^null is not allowed/i.test(s)) return 'không được để trống';
  if (/does not have the required form/i.test(s)) return 'chưa đúng dạng cần nhập';
  return 'chưa hợp lệ';
}

// ---------------------------------------------------------------- the table
// [codes, pattern of the English message, (issue, match, where) => sentence WITHOUT the location prefix]
// `codes` are the stable codes of the engine (docs/qa/ROUND2_FIXES_engine.md); the pattern is the fallback.
const T = [
  [['project_name_differs'], /^project (.+) differs from the folder name (.+)$/i, (i, m) => `Tên dự án ghi trong storyboard (${q(unq(m[1]))}) khác tên thư mục (${q(unq(m[2]))}). Không ảnh hưởng việc dựng.`],
  [['canvas_size'], /renderers are tuned for 1920x1080/i, () => 'Khung hình khác 1920x1080. Ứng dụng luôn dựng ở 1080p.'],
  [['schema'], /^schema must be/i, () => 'Phiên bản định dạng của storyboard không đúng.'],
  [['canvas_shape'], /^canvas must be an object/i, () => 'Khung hình (canvas) phải gồm chiều rộng w và chiều cao h.'],
  [['canvas_dim'], /^(w|h) must be a positive number/i, (i, m) => `${m[1] === 'w' ? 'Chiều rộng' : 'Chiều cao'} khung hình phải là số dương.`],
  [['canvas_fps', 'fps_range'], /^fps must be a number from (\d+) to (\d+)/i, (i, m) => `Tốc độ khung hình (fps) phải là số từ ${m[1]} đến ${m[2]}.`],
  [['not_string'], /^(\w+) must be a string$/i, (i, m, w) => (w.loc ? `${cap(FIELD[m[1]] || m[1])} phải là chữ.` : `Mục ${q(FIELD[m[1]] || m[1])} phải là chữ.`)],
  [['approvals_shape'], /^approvals must be an object/i, () => 'Phần ghi nhận duyệt của storyboard bị hỏng.'],
  [['audio_path'], /^audio must be a file path inside the project|^audio .* must be a file inside the project/i, () => 'Tệp âm thanh phải là một tệp nằm trong thư mục dự án.'],
  [['audio_missing'], /^audio file (.+) does not exist/i, (i, m) => `Tệp âm thanh ${q(unq(m[1]))} không có trong dự án.`],
  [['assets_shape'], /^assets must be an object/i, () => 'Danh sách hình của storyboard bị hỏng.'],
  [['asset_shape'], /^asset must be an object/i, (i) => `Hình ${q(assetKey(i))} bị hỏng.`],
  [['asset_kind'], /^kind must be image, video or mask/i, (i) => `Loại của hình ${q(assetKey(i))} phải là hình ảnh, video hoặc mặt nạ.`],
  [['asset_file_required'], /^file is required/i, (i) => `Hình ${q(assetKey(i))} chưa có tệp.`],
  [['asset_file_path'], /^file (.+) must be a path inside the project/i, (i) => `Tệp của hình ${q(assetKey(i))} phải nằm trong thư mục dự án.`],
  [['asset_file_missing'], /^file (.+) does not exist/i, (i) => `Tệp của hình ${q(assetKey(i))} không có trong dự án.`],
  [['asset_file_bad'], /^file (.+) (is not|cannot|could not|has)\b/i, (i) => `Tệp của hình ${q(assetKey(i))} không dùng được.`],
  [['asset_credit_shape'], /^credit must be an object/i, (i) => `Phần ghi nguồn của hình ${q(assetKey(i))} bị hỏng.`],
  [['asset_dim'], /^(width|height) must be a positive number/i, (i, m) => `${m[1] === 'width' ? 'Chiều rộng' : 'Chiều cao'} của hình ${q(assetKey(i))} phải là số dương.`],
  [['regions_shape'], /^regions must be an object/i, (i) => `Danh sách vùng của hình ${q(assetKey(i))} bị hỏng.`],
  [['region_xy'], /^region needs numeric x and y/i, (i) => `Một vùng của hình ${q(assetKey(i))} thiếu tọa độ x, y (phải là số).`],
  [['region_size'], /^(\w+) must be a number >= 0/i, (i) => `Kích thước một vùng của hình ${q(assetKey(i))} phải là số không âm.`],
  [['slots_shape'], /^slots must be an object/i, () => 'Phần chỗ đặt hình bị hỏng.'],
  [['unknown_slot'], /^unknown slot (.+?) for (\S+)/i, (i, m) => `Kỹ thuật ${m[2]} không có chỗ đặt hình tên ${q(unq(m[1]))}.`],
  [['asset_undefined'], /^asset (.+) is not defined/i, (i, m) => `Hình ${q(unq(m[1]))} chưa có trong dự án.`],
  [['slot_kind'], /^slot (.+?) takes (.+?) but asset (.+?) is an? (\w+)/i, (i, m) => `Chỗ đặt hình ${q(unq(m[1]))} cần ${kindList(m[2])}, nhưng hình ${q(unq(m[3]))} là ${KIND_VI[m[4]] || m[4]}.`],
  [['slot_shape'], /^a slot must be an object/i, () => 'Một chỗ đặt hình bị hỏng.'],
  [['locked_type'], /^locked must be true or false/i, () => 'Dấu khóa phải là bật hoặc tắt.'],
  [['unknown_source'], /^unknown source (.+?) \(/i, (i, m) => `Nguồn ${q(unq(m[1]))} không có trong danh sách (nhập từ bản cũ, đề xuất tự động, bạn sửa tay).`],
  [['unknown_intent'], /^unknown intent (.+)$/i, (i, m) => `Ý đồ ${q(unq(m[1]))} không có trong danh sách.`],
  [['intent_type'], /^intent must be a string/i, () => 'Ý đồ phải là chữ.'],
  [['region_needs_image'], /^region (.+?) needs an image on the shot/i, (i, m) => `Vùng ${q(unq(m[1]))} cần shot có hình để lấy vùng.`],
  [['region_undefined'], /^region (.+?) is not defined on asset (.+)$/i, (i, m) => `Vùng ${q(unq(m[1]))} không có trên hình ${q(unq(m[2]))}.`],
  [['end_required'], /^end anchor is required/i, () => 'Storyboard chưa có điểm kết thúc.'],
  [['end_fade'], /^fade_s must be a number >= 0/i, () => 'Thời gian mờ dần ở cuối phải là số không âm.'],
  [['end_before_start'], /^end is not after the last shot start/i, () => 'Điểm kết thúc phải sau thời điểm bắt đầu của shot cuối.'],
  [['end_after_audio'], /^end ([\d.]+) s is after the audio\/timing duration ([\d.]+) s/i, (i, m) => `Điểm kết thúc (${m[1]} giây) nằm sau hết âm thanh (${m[2]} giây).`],
  [['shots_shape'], /^shots must be a list/i, () => 'Danh sách shot bị hỏng.'],
  [['no_shots'], /^a storyboard needs at least one shot/i, () => 'Storyboard cần có ít nhất một shot.'],
  [['start_required'], /^start anchor is required/i, () => 'Chưa có thời điểm bắt đầu.'],
  [['anchor_rel'], /^'rel' anchors are only allowed/i, () => 'Thời điểm bắt đầu phải tính bằng giây, không tính theo tỉ lệ.'],
  [['start_negative'], /^start must be >= 0 s/i, () => 'Thời điểm bắt đầu không được âm.'],
  [['first_shot_late'], /^the first shot starts at ([\d.]+) s/i, (i, m) => `Bắt đầu ở giây ${m[1]}, nên phần đầu của video chưa có hình.`],
  [['shot_shape'], /^shot must be an object/i, () => 'Bị hỏng, không đọc được.'],
  [['id_required'], /^id is required|^id must be a non-empty string/i, () => 'Chưa có mã.'],
  [['duplicate_shot_id', 'duplicate_overlay_id'], /^duplicate (shot|overlay) id (.+)$/i, (i, m) => `Mã ${q(unq(m[2]))} bị dùng hai lần.`],
  [['shot_too_short'], /^shot is shorter than ([\d.]+) s/i, (i, m) => `Ngắn hơn ${m[1]} giây.`],
  [['shot_order'], /^shots must be in time order/i, () => 'Các shot phải xếp theo thời gian; shot này bắt đầu trước shot đứng trước nó.'],
  [['unknown_technique'], /^unknown (?:transition )?technique (.+)$/i, (i, m) => `Kỹ thuật ${unq(m[1])} không có trong danh sách.`],
  [['technique_kind'], /^(\S+) is an? (\w+) technique; (?:a shot needs kind base or card|an overlay needs kind overlay)/i, (i, m) => `${m[1]} không dùng được ở đây: ${/overlay needs/i.test(i.message) ? 'lớp phủ cần một kỹ thuật lớp phủ' : 'shot cần một kỹ thuật cảnh nền hoặc thẻ chữ'}.`],
  [['technique_unavailable'], /^(\S+) is not available in the engine yet/i, (i, m) => `Kỹ thuật ${m[1]} chưa dùng được trong bộ dựng hình.`],
  [['not_transition'], /^(\S+) is not a transition/i, (i, m) => `${m[1]} không phải kỹ thuật chuyển cảnh.`],
  [['camera_at'], /^camera keys must be in strictly increasing time order/i, () => 'Các mốc camera phải theo thứ tự thời gian tăng dần.'],
  [['camera_rel'], /^rel must be between 0 and 1/i, () => 'Vị trí tương đối của mốc camera phải từ 0 đến 1.'],
  [['unknown_ease'], /^unknown ease (.+)$/i, (i, m) => `Kiểu chuyển động ${q(unq(m[1]))} không có trong danh sách.`],
  [['transition_dur'], /^dur must be a number >= 0/i, () => 'Thời lượng chuyển cảnh phải là số không âm.'],
  [['transition_long'], /^transition is longer than the shot/i, () => 'Chuyển cảnh dài hơn shot.'],
  [['transition_first'], /^the first shot has nothing to transition from/i, () => 'Đây là shot đầu nên không có cảnh nào để chuyển từ.'],
  [['overlays_shape'], /^overlays must be a list/i, () => 'Danh sách lớp phủ bị hỏng.'],
  [['overlay_shape'], /^overlay must be an object/i, () => 'Bị hỏng, không đọc được.'],
  [['label_no_position'], /^neither `at` nor `screen` is set/i, () => 'Nhãn chưa có vị trí nên sẽ không được vẽ.'],
  [['overlay_dur'], /^dur must be a number > 0/i, () => 'Thời lượng phải lớn hơn 0.'],
  [['overlay_starts_outside'], /^overlay starts outside its shot \(([\d.]+) s; shot spans ([\d.]+)-([\d.]+) s\)/i, (i, m) => `Bắt đầu ngoài shot (giây ${m[1]}; shot chạy từ ${m[2]} đến ${m[3]}).`],
  [['overlay_ends_outside'], /^overlay ends outside its shot \(([\d.]+) s > ([\d.]+) s\)/i, (i, m) => `Kết thúc sau khi shot đã hết (giây ${m[1]}, shot hết ở giây ${m[2]}).`],
  [['overlay_ends_before'], /^overlay ends before it starts/i, () => 'Kết thúc trước khi bắt đầu.'],
  [['params_shape'], /^params must be an object/i, () => 'Phần tham số bị hỏng.'],
  [['unknown_param'], /^unknown parameter (.+?) for (\S+)/i, (i, m) => `Kỹ thuật ${m[2]} không có tham số ${q(unq(m[1]))}.`],
  [['incomplete'], /^incomplete: required (?:(slot|parameter) )?(.+?)(?: of (\S+))? is not set/i, (i, m) => `Chưa điền ${m[1] === 'slot' ? 'hình cho chỗ' : 'tham số'} ${q(unq(m[2]))}${m[3] ? ' của ' + m[3] : ''}.`],
  [['structure_unreadable'], /^the storyboard has a structure the checks cannot read/i, () => 'Storyboard có cấu trúc mà bộ kiểm tra không đọc được.'],
  [['not_object'], /^storyboard must be an object/i, () => 'Storyboard phải là một đối tượng.'],
];
/** Templates by the engine's stable `code`, using `args` (bti.engine.storyboard.ISSUE_CODES lists every code; a unit test fails when one is missing). */
const num = (x) => (typeof x === 'number' ? String(Math.round(x * 1000) / 1000) : String(x ?? ''));
/** "Mốc camera thứ 3: " when the issue is about one key of a camera (args.index), else nothing. */
const key = (a) => (a.index != null ? `Mốc camera thứ ${Number(a.index) + 1}: ` : '');
const item = (a) => (a.index != null ? ` (mục thứ ${Number(a.index) + 1})` : '');
const P = (a) => (a.param ? `Tham số ${q(a.param)}` : 'Một tham số');
const list = (v) => (Array.isArray(v) ? v : String(v ?? '').split(/\s*,\s*/)).filter(Boolean);
const FIELD_NAME = { w: 'chiều rộng', h: 'chiều cao', width: 'chiều rộng', height: 'chiều cao', at: 'thời điểm', cx: 'tâm ngang', cy: 'tâm dọc', zoom: 'độ phóng', rx: 'bán kính ngang', ry: 'bán kính dọc' };
const fld = (f) => FIELD_NAME[f] || FIELD[f] || String(f ?? '');
const BY_ARGS = {
  undrawable: (i, a) => (a.asset ? `Không vẽ được hình của mục này vì hình ${q(a.asset)} có vấn đề (tệp hỏng, không đọc được hoặc không còn). Thay bằng hình khác ở tab Hình.` : 'Không vẽ được hình của mục này với các giá trị hiện tại. Sửa tham số của nó hoặc đổi sang kỹ thuật khác.'),
  incomplete: (i, a) => `Chưa điền ${a.what === 'slot' ? 'hình cho chỗ' : 'tham số'} ${q(a.name ?? '')}${a.technique ? ' của ' + a.technique : ''}.`,
  not_an_object: () => 'Storyboard phải là một đối tượng.',
  unreadable_structure: () => 'Storyboard có cấu trúc mà bộ kiểm tra không đọc được.',
  wrong_schema: () => 'Phiên bản định dạng của storyboard không đúng.',
  canvas_not_object: () => 'Khung hình (canvas) phải gồm chiều rộng w và chiều cao h.',
  canvas_size: (i, a) => `${cap(fld(a.field))} khung hình phải là số dương.`,
  canvas_fps: (i, a) => `Tốc độ khung hình (fps) phải là số từ ${a.min ?? 1} đến ${a.max ?? 60}.`,
  canvas_not_1080p: () => 'Khung hình khác 1920x1080. Ứng dụng luôn dựng ở 1080p.',
  not_a_string: (i, a) => `${cap(fld(a.field))} phải là chữ.`,
  approvals_not_object: () => 'Phần ghi nhận duyệt của storyboard bị hỏng.',
  project_name_differs: (i, a) => `Tên dự án ghi trong storyboard (${q(a.project ?? '')}) khác tên thư mục (${q(a.folder ?? '')}). Không ảnh hưởng việc dựng.`,
  audio_invalid: () => 'Tệp âm thanh phải là một đường dẫn tệp hợp lệ.',
  audio_outside_project: (i, a) => `Tệp âm thanh ${q(a.file ?? '')} nằm ngoài thư mục dự án.`,
  audio_missing: (i, a) => `Tệp âm thanh ${q(a.file ?? '')} không có trong dự án.`,
  assets_not_object: () => 'Danh sách hình của storyboard bị hỏng.',
  asset_not_object: (i) => `Hình ${q(assetKey(i))} bị hỏng.`,
  asset_kind: (i) => `Loại của hình ${q(assetKey(i))} phải là hình ảnh, video hoặc mặt nạ.`,
  asset_file_required: (i) => `Hình ${q(assetKey(i))} chưa có tệp.`,
  asset_file_outside_project: (i, a) => `Tệp ${q(a.file ?? '')} của hình ${q(assetKey(i))} nằm ngoài thư mục dự án.`,
  asset_file_missing: (i, a) => `Tệp ${q(a.file ?? '')} của hình ${q(assetKey(i))} không có trong dự án.`,
  asset_file_truncated: (i, a) => `Tệp ${q(a.file ?? '')} của hình ${q(assetKey(i))} bị cắt dở hoặc hỏng một phần, nên không hiện đủ ảnh. Tải lại ảnh hoặc thay bằng ảnh khác.`,
  asset_video_unreadable: (i, a) => `Tệp ${q(a.file ?? '')} của video ${q(assetKey(i))} không mở được. Tải lại video hoặc thay bằng tệp khác.`,
  asset_file_unreadable: (i, a) => `Tệp ${q(a.file ?? '')} của hình ${q(assetKey(i))} không đọc được như một ảnh.`,
  credit_not_object: (i) => `Phần ghi nguồn của hình ${q(assetKey(i))} bị hỏng.`,
  asset_size: (i, a) => `${cap(fld(a.field))} của hình ${q(assetKey(i))} phải là số dương.`,
  regions_not_object: (i) => `Danh sách vùng của hình ${q(assetKey(i))} bị hỏng.`,
  region_xy: (i, a) => `Vùng ${q(a.region ?? '')} của hình ${q(assetKey(i))} thiếu tọa độ x, y (phải là số).`,
  region_radius: (i, a) => `Vùng ${q(a.region ?? '')} của hình ${q(assetKey(i))}: ${fld(a.field)} phải là số không âm.`,
  slots_not_object: () => 'Phần chỗ đặt hình bị hỏng.',
  unknown_slot: (i, a) => `Kỹ thuật ${a.technique ?? ''} không có chỗ đặt hình tên ${q(a.slot ?? '')}.`,
  asset_undefined: (i, a) => `Hình ${q(a.asset ?? '')} chưa có trong dự án.`,
  slot_asset_kind: (i, a) => (a.slot && a.takes && a.got ? `Chỗ đặt hình ${q(a.slot)} cần ${kindList(Array.isArray(a.takes) ? a.takes.join(' or ') : a.takes)}, nhưng hình ${q(a.asset ?? '')} là ${KIND_VI[a.got] || a.got}.` : 'Hình đã chọn không đúng loại mà chỗ đặt hình này cần.'),
  slot_not_object: (i, a) => `Chỗ đặt hình ${q(a.slot ?? '')} bị hỏng.`,
  locked_not_bool: () => 'Dấu khóa phải là bật hoặc tắt.',
  unknown_source: (i, a) => `Nguồn ${q(a.source ?? '')} không có trong danh sách (nhập từ bản cũ, đề xuất tự động, bạn sửa tay).`,
  unknown_intent: (i, a) => `Ý đồ ${q(a.intent ?? '')} không có trong danh sách.`,
  region_undefined: (i, a) => `Vùng ${q(a.region ?? '')} không có trên hình ${q(a.asset ?? '')}${a.param ? ` (tham số ${q(a.param)})` : ''}.`,
  end_required: () => 'Storyboard chưa có điểm kết thúc.',
  anchor_invalid: (i, a) => key(a) + 'Mốc thời gian này không xác định được (sai dạng, số thứ tự từ không có, hoặc tính theo tỉ lệ khi chưa có shot).',
  end_fade: () => 'Thời gian mờ dần ở cuối phải là số không âm.',
  shots_not_list: () => 'Danh sách shot bị hỏng.',
  no_shots: () => 'Storyboard cần có ít nhất một shot.',
  start_required: () => 'Chưa có thời điểm bắt đầu.',
  rel_anchor_not_allowed: () => 'Thời điểm bắt đầu phải tính bằng giây hoặc theo từ, không tính theo tỉ lệ.',
  start_negative: (i, a) => `Thời điểm bắt đầu không được âm (hiện là ${num(a.start)} giây).`,
  first_shot_late: (i, a) => `Shot đầu bắt đầu ở giây ${num(a.start)}, nên phần đầu của video chưa có hình.`,
  shot_not_object: () => 'Bị hỏng, không đọc được.',
  id_required: () => 'Chưa có mã.',
  duplicate_shot_id: (i, a) => `Mã ${q(a.id ?? '')} bị dùng hai lần.`,
  stale_anchor: (i, a) => key(a) + 'Mốc gắn vào một từ của lời đọc, nhưng từ ở vị trí đó đã khác (lời đọc đã đổi). Hãy gắn lại mốc.',
  shot_too_short: (i, a) => `Ngắn hơn ${num(a.min)} giây (hiện ${num(a.got)} giây).`,
  shots_out_of_order: () => 'Các shot phải xếp theo thời gian; shot này bắt đầu trước shot đứng trước nó.',
  unknown_technique: (i, a) => `Kỹ thuật ${a.technique ?? ''} không có trong danh sách.`,
  wrong_technique_kind: (i, a) => `${a.technique ?? ''} không dùng được ở đây: ${a.needs === 'overlay' ? 'lớp phủ cần một kỹ thuật lớp phủ' : a.needs === 'transition' ? 'chuyển cảnh cần một kỹ thuật chuyển cảnh' : 'shot cần một kỹ thuật cảnh nền hoặc thẻ chữ'}.`,
  technique_unavailable: (i, a) => `Kỹ thuật ${a.technique ?? ''} chưa dùng được trong bộ dựng hình.`,
  camera_keys_order: (i, a) => (a.index != null ? `${key(a)}đến sớm hơn hoặc cùng lúc với mốc trước nó; các mốc camera phải theo thứ tự thời gian tăng dần.` : 'Các mốc camera phải theo thứ tự thời gian tăng dần.'),
  camera_rel_range: (i, a) => key(a) + 'Vị trí tương đối của mốc camera phải từ 0 đến 1.',
  unknown_ease: (i, a) => `${key(a)}Kiểu chuyển động ${q(valueLabel(a.ease ?? ''))} không có trong danh sách.`,
  transition_dur: () => 'Thời lượng chuyển cảnh phải là số không âm.',
  transition_too_long: (i, a) => `Chuyển cảnh dài ${num(a.dur)} giây, hơn cả shot (${num(a.shot_dur)} giây).`,
  first_shot_transition: () => 'Đây là shot đầu nên không có cảnh nào để chuyển từ.',
  overlays_not_list: () => 'Danh sách lớp phủ bị hỏng.',
  overlay_not_object: () => 'Bị hỏng, không đọc được.',
  duplicate_overlay_id: (i, a) => `Mã ${q(a.id ?? '')} bị dùng hai lần.`,
  label_without_position: () => 'Nhãn chưa có vị trí nên sẽ không được vẽ.',
  overlay_dur: () => 'Thời lượng phải lớn hơn 0.',
  overlay_outside_shot: (i, a) => `${a.start != null ? `Bắt đầu ngoài shot (giây ${num(a.start)}` : `Kết thúc sau khi shot đã hết (giây ${num(a.end)}`}; shot chạy từ ${num(a.shot_start)} đến ${num(a.shot_end)}).`,
  overlay_ends_before_start: () => 'Kết thúc trước khi bắt đầu.',
  end_before_last_start: () => 'Điểm kết thúc phải sau thời điểm bắt đầu của shot cuối.',
  end_after_audio: (i, a) => `Điểm kết thúc (${num(a.end)} giây) nằm sau hết âm thanh (${num(a.duration)} giây).`,
  style_unusable: () => 'Không đọc được kiểu (style) mà dự án dùng.',
  timing_unusable: () => 'Tệp thời gian (timing) của dự án bị thiếu hoặc hỏng.',
  params_not_object: () => 'Phần tham số bị hỏng.',
  unknown_param: (i, a) => `Kỹ thuật ${a.technique ?? ''} không có tham số ${q(a.param ?? '')}.`,
  param_null: (i, a) => `${P(a)}: không được để trống.`,
  param_not_number: (i, a) => `${P(a)}: phải là một số.`,
  param_below_min: (i, a) => `${P(a)}: không được nhỏ hơn ${num(a.min)}.`,
  param_above_max: (i, a) => `${P(a)}: không được lớn hơn ${num(a.max)}.`,
  param_not_in_values: (i, a) => `${P(a)}: phải là một trong: ${list(a.values).map((v) => valueLabel(v, a.param)).join(', ')}.`,
  param_not_bool: (i, a) => `${P(a)}: phải là bật hoặc tắt.`,
  param_not_string: (i, a) => `${P(a)}: phải là chữ.`,
  param_bad_form: (i, a) => `${P(a)}${a.index != null ? ` (dòng ${Number(a.index) + 1})` : ''}: ${isVi(a.hint) ? String(a.hint).replace(/[.\s]+$/, '') : 'chưa đúng dạng cần nhập'}.`,
  param_bad_color: (i, a) => `${P(a)}: phải là màu dạng #rrggbb.`,
  param_not_points: (i, a) => `${P(a)}: phải là danh sách các điểm.`,
  param_not_lines: (i, a) => `${P(a)}: phải là danh sách các dòng chữ.`,
  param_item_count: (i, a) => {
    const lo = a.min, hi = a.max, got = a.got;
    if (lo == null && hi == null) return `${P(a)}: số mục chưa đúng.`;
    const need = lo != null && lo === hi ? `đúng ${lo}` : hi == null || got < lo ? `ít nhất ${lo}` : `nhiều nhất ${hi}`;
    return `${P(a)}: cần ${need} mục${got != null ? ` (hiện có ${got})` : ''}.`;
  },
  param_bad_box: (i, a) => `${P(a)}: phải là một khung gồm bốn số.`,
  param_box_range: (i, a) => `${P(a)}: khung phải nằm trong khung hình ${a.w ?? 1920} x ${a.h ?? 1080}, góc trên trái nhỏ hơn góc dưới phải, mỗi cạnh dài ít nhất ${a.min_px ?? 16} px.`,
  param_not_asset: (i, a) => `${P(a)}: phải chọn một hình.`,
  point_bad_form: (i, a) => `${P(a)}${item(a)}: phải là tên một vùng của hình hoặc hai số x, y.`,
  point_empty_region: (i, a) => `${P(a)}${item(a)}: tên vùng đang trống.`,
  point_out_of_range: (i, a) => `${P(a)}${item(a)}: tọa độ phải nằm trong khoảng ±${num(a.limit)}.`,
  point_numeric_only: (i, a) => `${P(a)}${item(a)}: chỉ nhập được hai số x, y, không dùng tên vùng.`,
  camera_empty: (i, a) => `${P(a)}: camera cần ít nhất một mốc.`,
  camera_key_not_object: (i, a) => `${P(a)}: mốc camera thứ ${Number(a.index ?? 0) + 1} bị hỏng.`,
  camera_key_missing_field: (i, a) => `${P(a)}: mốc camera thứ ${Number(a.index ?? 0) + 1} thiếu ${fld(a.field)}.`,
  camera_key_numbers: (i, a) => `${P(a)}: mốc camera thứ ${Number(a.index ?? 0) + 1}: tâm và độ phóng phải là số, độ phóng lớn hơn 0.`,
  camera_key_range: (i, a) => `${P(a)}: mốc camera thứ ${Number(a.index ?? 0) + 1} nằm quá xa (tâm trong khoảng ±${num(a.limit)}, độ phóng tối đa ${num(a.zoom_max)}).`,
  camera_key_anchor: (i, a) => `${P(a)}: thời điểm của mốc camera thứ ${Number(a.index ?? 0) + 1} không xác định được.`,
  // --- idapply: the channel identity of the storyboard (the selector "Kiểu mở đầu và mốc chương" of step 5)
  identity_style_unknown: () => 'kiểu mở đầu và mốc chương của video không hợp lệ. Hãy chọn lại ở ô "Kiểu mở đầu và mốc chương" của bước Dựng hình.',
  element_too_short: (i, a) => {
    const t = String(a.technique || ''), vn = (x) => num(x).replace('.', ',');
    const what = /^ID-OPEN-/.test(t) ? 'phần mở đầu' : /^ID-LABEL-/.test(t) ? 'nhãn tên tác phẩm' : /^ID-BRAND-/.test(t) ? 'đoạn hiện tên kênh' : /^ID-MARK-/.test(t) ? 'mốc chương' : 'phần này của kiểu mở đầu';
    const need = a.min != null ? `${vn(a.min)} giây` : 'đủ lâu', has = a.got != null ? ` (hiện chỉ ${vn(a.got)} giây)` : '';
    return `${what} cần dài ít nhất ${need}${has}. Kéo dài nó, hoặc bỏ nó đi.`;
  },
  identity_technique_mismatch: () => 'chưa theo kiểu mở đầu và mốc chương đã chọn cho video (còn là thẻ tiêu đề hoặc thẻ chương kiểu khác). Chọn lại kiểu để đổi một lượt; nếu shot đang khóa thì mở khóa trước.',
  // --- sizefollow: a picture recorded with a size that is not the size of its stored file (the warning has no shot: the sentence stands alone).
  // The advice (worker followups): a re-draft now takes the size of the stored file from the picks, so it clears the warning (tests/draft/test_size_follow.py).
  asset_size_mismatch: (i, a) => `Hình ${q(a.asset ?? assetKey(i))} được ghi là ${num(a.width)} x ${num(a.height)} nhưng tệp đã lưu là ${num(a.stored_width)} x ${num(a.stored_height)}, nên khung hình sẽ lệch. Dựng nháp lại để cập nhật kích thước hình.`,
};
/** Codes of the table: the unit test compares them with ISSUE_CODES. */
export const TEMPLATE_CODES = Object.keys(BY_ARGS);
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const BY_CODE = new Map();
for (const e of T) for (const c of e[0]) BY_CODE.set(c, e);
export const KNOWN_CODES = [...BY_CODE.keys(), ...TEMPLATE_CODES];

/** "<param>: <reason>" issues of the registry check, path `...params.<param>`. */
function paramIssue(issue, w) {
  const raw = String(issue.message || ''), pm = /(?:^|\.)params\.([^.\[]+)/.exec(String(issue.path || ''));
  if (!pm) return null;
  const name = pm[1], mm = new RegExp('^' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ': (.*)$', 's').exec(raw);
  if (!mm) return null;
  return `Tham số ${q(name)}: ${paramReason(name, mm[1])}.`;
}

/** The sentence for a storyboard issue. Never English: an unknown issue is described by its place. */
export function storyboardIssueText(issue) {
  const raw = String(issue?.message || ''), w = whereOf(issue);
  let body = null, hit = false;
  const e = issue?.code && BY_CODE.get(issue.code);
  if (issue?.code && BY_ARGS[issue.code]) { try { body = BY_ARGS[issue.code](issue, issue.args || {}, w); hit = body !== undefined && body !== null; } catch { body = null; } }
  if (!hit && e) { const m = e[1].exec(raw); if (m || !raw) { try { body = e[2](issue, m || [], w); hit = true; } catch { /* fall through */ } } }
  if (!hit) body = paramIssue(issue, w);
  if (body === null || body === undefined) {
    for (const [, re, fn] of T) { const m = re.exec(raw); if (m) { try { body = fn(issue, m, w); } catch { body = null; } if (body) break; } }
  }
  if (body) return { text: (w.loc ? `${cap(w.loc)}: ` : '') + body, detail: raw };
  if (isVi(raw)) return { text: raw, detail: '' };
  const f = fieldOf(issue);
  return { text: cap(`${w.loc ? cap(w.loc) + ': ' : ''}có một điểm chưa đúng${f ? ` ở mục "${f}"` : ''}. Xem "chi tiết".`), detail: raw, generic: true };
}

// ---------------------------------------------------------------- where a click on an issue leads (R3U-003)
const slotsHold = (slots, key) => Object.values(slots || {}).some((v) => v?.asset === key);
/** Ids of the shots that use asset `key` (a slot of the shot or of one of its overlays holds it), in timeline order. */
export function shotsUsingAsset(draft, key) {
  return (draft?.shots || []).filter((s) => slotsHold(s.slots, key) || (s.overlays || []).some((o) => slotsHold(o.slots, key))).map((s) => s.id);
}
/** What a click on an issue does. Pure.
 *  { kind: 'shot', shot: index, overlay: index|null }   the issue names a shot (path or id): go to it
 *  { kind: 'asset', asset, shots: [ids] }               about a picture: the first shot that uses it (`shots` has them all), or the pictures tab when none does
 *  { kind: 'none' }                                     no place: the owner stays where he is and only sees the detail */
export function issueTarget(issue, draft) {
  const shots = draft?.shots || [];
  const m = SHOT_PATH.exec(String(issue?.path || ''));
  if (m && shots[Number(m[1])]) return { kind: 'shot', shot: Number(m[1]), overlay: m[2] != null ? Number(m[2]) : null };
  const sid = issue?.shot || issue?.args?.shot;
  if (sid) {
    const i = shots.findIndex((s) => s.id === sid);
    if (i >= 0) {
      const oid = issue?.overlay || issue?.args?.overlay;
      const oi = oid ? (shots[i].overlays || []).findIndex((o) => o.id === oid) : -1;
      return { kind: 'shot', shot: i, overlay: oi >= 0 ? oi : null };
    }
  }
  const key = issue?.args?.asset || assetKey(issue);
  if (key && draft?.assets?.[key]) return { kind: 'asset', asset: key, shots: shotsUsingAsset(draft, key) };
  return { kind: 'none' };
}
