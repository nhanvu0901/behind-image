// The ONE place that turns an error into a message for the owner (Vietnamese).
// describeHttp(status, body) -> { text, detail }: `text` is the sentence shown, `detail` the raw server text kept under
// "chi tiết" when the sentence is not the same as what the server said. Reads `detail`, `reason`, `error`, `issues` of the body
// and survives a body it does not recognise. issueText(issue) does the same for the validation issues ({code, message, ...}).
// jobErrorText(job) does it for a failed model job. Pure; tested in tests/editor_frontend/errmsg.test.mjs.

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
export const isVietnamese = (s) => VI.test(String(s || ''));
const unquote = (s) => String(s).trim().replace(/^'(.*)'$/s, '$1').replace(/^"(.*)"$/s, '$1');
const STALE = 'Bản này đã đổi ở nơi khác (tab khác hoặc tác vụ nền) kể từ lúc bạn mở.';
const list = (s) => String(s || '').split(/\s*,\s*/).filter(Boolean).join(', ');

/** [pattern, builder(match, body) | string]. The first pattern that matches the raw text wins. */
const CATALOG = [
  // stale revisions
  [/changed since you loaded|base_rev does not match|rev is not the current revision|changed on disk/i, STALE + ' Hãy tải lại phần này rồi sửa lại.'],
  [/base_rev.*required/i, 'Thiếu mã phiên bản của bản đang sửa. Hãy tải lại trang.'],
  // models and jobs
  [/\bmodel\b.*\b(is )?required\b|\bmissing\b.*\bmodel\b|\bmodel\b.*\bmissing\b/i, 'Chưa chọn mô hình. Chọn một mô hình ở ô trên thanh công cụ rồi thử lại.'],
  [/^unknown model/i, 'Không có mô hình này trong danh sách.'],
  [/another model job is running/i, 'Dự án này đang có một tác vụ mô hình chạy. Chờ nó xong hoặc bấm Hủy.'],
  [/this model is not available/i, 'Mô hình này chưa dùng được (thiếu khóa hoặc chưa cấu hình).'],
  [/^job not found/i, 'Không tìm thấy tác vụ này (có thể máy chủ đã khởi động lại).'],
  [/phase must be/i, 'Loại prompt không đúng (chỉ có dàn ý hoặc lời dẫn).'],
  [/unknown chapter\(s\): (.+)/i, (m) => `Chương không có trong dàn ý: ${list(m[1])}.`],
  [/locked beats would be replaced \((.*?)\)/i, (m) => `Có dòng đang khóa sẽ bị viết lại (${list(m[1])}). Mở khóa các dòng đó hoặc chọn viết lại cả dòng khóa.`],
  [/there is no outline yet/i, 'Chưa có dàn ý. Hãy lập hoặc dán dàn ý trước.'],
  [/no outline to approve/i, 'Chưa có dàn ý để duyệt.'],
  [/no narration to approve|no narration yet/i, 'Chưa có lời dẫn.'],
  [/the outline has errors/i, 'Dàn ý còn lỗi nên chưa duyệt được. Xem hộp "Kiểm tra".'],
  [/the narration has errors/i, 'Lời dẫn còn lỗi nên chưa duyệt được. Xem hộp "Kiểm tra".'],
  [/the outline could not be read|outline could not be read/i, 'Không đọc được dàn ý từ văn bản đã dán. Chưa có gì bị ghi đè.'],
  [/the script could not be (read|placed)|script could not be (read|placed)/i, 'Không xếp được lời dẫn từ văn bản đã dán. Chưa có gì bị ghi đè.'],
  [/^(beat|chapter) \S+ (not found|is locked)|beat .* is locked|a locked beat|cannot split|nothing to merge|cannot be moved after itself|is not in chapter|bad operation|unknown operation/i, (m, b, raw) => opError(raw)],
  // library and projects
  [/^artwork not found|^artwork .* not found/i, 'Không có tác phẩm này trong thư viện.'],
  [/^work not found|^work \S+ not found/i, 'Không có mục sách này.'],
  [/^book not found|unknown book/i, 'Không có sách này.'],
  [/book not catalogued/i, 'Sách này chưa có trong danh mục thư viện. Cần dựng lại danh mục (python -m bti.library build).'],
  [/^dossier not found/i, 'Tác phẩm này chưa có hồ sơ.'],
  [/^source not found|source text missing/i, 'Không tìm thấy nguồn hoặc văn bản của nguồn này.'],
  [/book PDF is missing/i, 'Thiếu tệp PDF của sách.'],
  [/^page not found|page is not part of this entry/i, 'Trang này không có trong mục đã chọn.'],
  [/image is not part of this entry/i, 'Hình này không có trong mục đã chọn.'],
  [/slug must match/i, 'Tên thư mục (slug) chỉ gồm chữ thường a-z, số 0-9, dấu - và _, bắt đầu bằng chữ hoặc số, dài tối đa 64 ký tự.'],
  [/slug may not start with/i, 'Tên thư mục không được bắt đầu bằng lab_ hoặc demo_ (dành cho dự án thử).'],
  [/slug must be a string/i, 'Tên thư mục không hợp lệ.'],
  [/project '?([^']+?)'? already exists/i, (m) => `Đã có dự án tên "${m[1]}". Hãy chọn tên khác.`],
  [/^project not found/i, 'Không có dự án này.'],
  [/is protected and cannot be deleted/i, (m, b, raw) => `Dự án này được bảo vệ, không xóa được.`],
  [/a model job is running for this project; cancel it first/i, 'Dự án đang có một tác vụ mô hình chạy. Hủy nó (hoặc chờ nó xong) rồi mới xóa được.'],
  [/a preview is being rendered/i, 'Dự án đang dựng xem thử. Chờ xong rồi mới xóa được.'],
  [/internal error/i, 'Máy chủ gặp lỗi bất ngờ. Xem "chi tiết".'],
  [/symbolic link/i, 'Thư mục dự án là liên kết tượng trưng, từ chối xóa.'],
  [/invalid project path/i, 'Đường dẫn dự án không hợp lệ.'],
  [/type the project id/i, 'Gõ đúng mã dự án để xác nhận xóa.'],
  [/work_ids must be a non-empty list|work_id is required/i, 'Chưa chọn mục sách nào.'],
  [/duplicate work ids/i, 'Có mục sách bị chọn hai lần.'],
  [/pick at most one entry per book/i, 'Mỗi sách chỉ được chọn một mục.'],
  [/give artwork_key or work_ids/i, 'Chọn tác phẩm hoặc chọn mục sách, không chọn cả hai.'],
  [/invalid work id/i, 'Mã mục sách không hợp lệ.'],
  [/exclude must be a list/i, 'Danh sách nguồn bỏ không hợp lệ.'],
  [/key and with/i, 'Thiếu tác phẩm cần gộp.'],
  [/cannot merge an artwork with itself/i, 'Không gộp một tác phẩm với chính nó.'],
  [/artwork has only one source/i, 'Tác phẩm này chỉ có một nguồn nên không tách được.'],
  // storyboard, media, previews
  [/^validation failed|cannot approve while there are errors|save refused/i, 'Storyboard còn lỗi nên chưa lưu hoặc duyệt được. Xem danh sách lỗi.'],
  [/^storyboard not found/i, 'Dự án chưa có storyboard.'],
  [/storyboard\.json is corrupt/i, 'Tệp storyboard.json bị hỏng.'],
  [/^style not found/i, 'Không có kiểu (style) này.'],
  [/^no audio file/i, 'Dự án chưa có tệp âm thanh.'],
  [/unknown technique|technique is required/i, 'Kỹ thuật không có trong danh sách.'],
  [/^shot not found/i, 'Không tìm thấy cảnh này.'],
  [/^asset not found/i, 'Không tìm thấy hình này.'],
  [/^proposal not found|proposal file was corrupt|proposal has no storyboard/i, 'Đề xuất này không mở được.'],
  [/file too large/i, 'Tệp quá lớn.'],
  [/unsupported file type/i, 'Loại tệp này chưa hỗ trợ.'],
  [/cannot make a thumbnail|cannot extract this image/i, 'Không tạo được ảnh nhỏ từ tệp này.'],
  [/render failed|audio decode failed|ffmpeg failed|audio mux failed/i, 'Dựng hình hoặc âm thanh thất bại trên máy chủ.'],
  [/a preview is limited|width must be|bins must be|w must be|t out of range|t must be a number|t0 and t1|t1 must be|width and fps/i, 'Thông số xem thử không hợp lệ.'],
  [/regions .* required|needs numeric x and y|source and source_id are required|\(object\) is required|storyboard must be an object/i, 'Dữ liệu gửi lên thiếu hoặc không đúng dạng.'],
  [/^not found$/i, 'Không tìm thấy mục này.'],
];

function opError(raw) {
  let m;
  if ((m = /beat (\S+) not found/i.exec(raw))) return `Không có dòng ${m[1]} (có thể đã bị bỏ). Hãy tải lại.`;
  if ((m = /beat (\S+) is locked/i.exec(raw))) return `Dòng ${m[1]} đang khóa, không sửa được. Bỏ khóa trước.`;
  if (/a locked beat cannot be merged/i.test(raw)) return 'Không gộp được dòng đang khóa.';
  if (/cannot split/i.test(raw)) return 'Không tách được ở vị trí này. Đặt con trỏ vào giữa lời dẫn.';
  if (/nothing to merge/i.test(raw)) return 'Đây là dòng đầu của chương, không có dòng phía trên để gộp.';
  if (/chapter (\S+) not found/i.test(raw)) return `Không có chương ${/chapter (\S+) not found/i.exec(raw)[1]}.`;
  if (/is not in chapter/i.test(raw)) return 'Vị trí đặt dòng không còn nữa. Hãy tải lại.';
  return 'Thao tác này không làm được ở trạng thái hiện tại.';
}

const BY_STATUS = {
  400: 'Máy chủ không hiểu yêu cầu này.',
  401: 'Máy chủ từ chối: chưa được phép.',
  403: 'Máy chủ không cho làm việc này.',
  404: 'Không tìm thấy mục này.',
  405: 'Máy chủ không hỗ trợ thao tác này.',
  408: 'Máy chủ chờ quá lâu.',
  409: 'Việc này xung đột với trạng thái hiện tại của dữ liệu.',
  413: 'Dữ liệu gửi lên quá lớn.',
  415: 'Máy chủ không xử lý được loại tệp này.',
  422: 'Dữ liệu gửi lên không hợp lệ.',
  429: 'Máy chủ đang bận hoặc bị giới hạn lượt gọi. Thử lại sau.',
};
const GENERIC = 'Có lỗi không rõ từ máy chủ. Bản gốc của thông báo nằm ở "chi tiết".';

/** Text the server said, whatever the shape of the body. */
export function rawDetail(status, body) {
  if (body && typeof body === 'object') {
    const d = body.detail;
    if (typeof d === 'string' && d) return d;
    if (Array.isArray(d)) return d.map((x) => (x && typeof x === 'object' ? [(x.loc || []).join('.'), x.msg].filter(Boolean).join(': ') : String(x))).join('; ');
    if (d && typeof d === 'object') return String(d.reason || d.message || d.error || JSON.stringify(d));
    for (const k of ['reason', 'error', 'message']) if (typeof body[k] === 'string' && body[k]) return body[k];
    return '';
  }
  if (typeof body === 'string') return body.trim().slice(0, 400);
  return '';
}

/** Vietnamese message for an HTTP error. Never returns an empty text. */
const DATA_ERROR = { timing: 'Tệp thời gian (timing) của dự án bị thiếu hoặc hỏng.', storyboard: 'Tệp storyboard của dự án bị hỏng hoặc thiếu.', script: 'Tệp dàn ý hoặc lời dẫn của dự án bị hỏng. Bản dán gần nhất (nếu có) vẫn được giữ.', style: 'Không đọc được kiểu (style) mà dự án dùng.' };
export function describeHttp(status, body) {
  const raw = rawDetail(status, body);
  const s = unquote(raw);
  if (body && typeof body === 'object' && typeof body.data_error === 'string') return { text: DATA_ERROR[body.data_error] || 'Dữ liệu của dự án không dùng được.', detail: raw };
  if (s) {
    for (const [re, out] of CATALOG) {
      const m = re.exec(s);
      if (!m) continue;
      let text = typeof out === 'function' ? out(m, body, s) : out;
      if (status === 422 && Array.isArray(body?.issues) && body.issues.length && /còn lỗi|Storyboard còn lỗi/.test(text)) {
        const n = body.issues.filter((i) => !i.level || i.level === 'error').length || body.issues.length;
        text = text.replace(/ nên chưa/, ` (${n} lỗi) nên chưa`);
      }
      return { text, detail: s !== text ? raw : '' };
    }
    const g = GATES.find(([re]) => re.test(s));
    if (g) return { text: BUILD[g[1]]({}, s), detail: raw };
    if (isVietnamese(s)) return { text: s, detail: '' };       // the server already speaks Vietnamese here
  }
  const text = BY_STATUS[status] || (status >= 500 ? `Máy chủ gặp lỗi (mã ${status}).` : GENERIC);
  return { text, detail: raw };
}

/** Any thrown value: an ApiError (has status and body), a network failure, or something else. */
export function describeError(e) {
  if (e && typeof e === 'object' && 'status' in e && 'body' in e) return describeHttp(e.status, e.body);
  const msg = String(e?.message ?? e ?? '');
  if (e?.name === 'TypeError' || /failed to fetch|networkerror|load failed/i.test(msg)) return { text: 'Không kết nối được máy chủ. Kiểm tra máy chủ còn chạy không rồi thử lại.', detail: msg };
  if (isVietnamese(msg)) return { text: msg, detail: '' };
  return { text: msg ? 'Có lỗi: ' + (msg.length > 160 ? 'xem "chi tiết".' : msg) : GENERIC, detail: msg && msg.length > 160 ? msg : '' };
}
export const errorText = (e) => describeError(e).text;

// ---------------------------------------------------------------- failed model jobs
export function jobErrorText(job) {
  const raw = String(job?.error || '');
  const kind = job?.error_kind;
  const num = (re) => (re.exec(raw) || [])[1];
  let text;
  switch (kind) {
    case 'timeout': text = 'Mô hình không trả lời kịp.'; break;
    case 'rate_limit': text = 'Mô hình bị giới hạn lượt gọi hoặc đã hết hạn mức.'; break;
    case 'auth': text = 'Nhà cung cấp mô hình từ chối khóa truy cập. Kiểm tra khóa và quyền của nó.'; break;
    case 'config': text = isVietnamese(raw) ? raw : 'Mô hình này chưa được cấu hình (thiếu khóa hoặc chưa cài công cụ).'; break;
    case 'http': text = isVietnamese(raw) ? raw : 'Lỗi khi gọi mô hình (mạng hoặc dữ liệu trả về không đúng).'; break;
    case 'empty': text = 'Mô hình không trả về chữ nào.'; break;
    case 'blocked': text = 'Mô hình từ chối yêu cầu (nội dung bị chặn).'; break;
    case 'parse': text = 'Không đọc được câu trả lời của mô hình thành dàn ý, kể cả sau một lần thử lại. Câu trả lời cuối được giữ trong ô "Dán".'; break;
    case 'validation': { const c = num(/Chapter (\S+) failed validation twice/i); text = `${c ? 'Chương ' + c : 'Một chương'} không đạt kiểm tra hai lần liên tiếp. Các chương đã viết xong được giữ lại; câu trả lời cuối nằm trong ô "Dán".`; break; }
    case 'conflict': text = /outline/i.test(raw) && /saved|edited|changed/i.test(raw) && /model/i.test(raw) ? 'Dàn ý đã đổi trong lúc mô hình viết nên không bị ghi đè. Câu trả lời của mô hình được giữ trong ô "Dán".' : issueText({ code: '', message: raw }).text; break;
    case 'cancelled': text = 'Tác vụ đã bị hủy.'; break;
    case 'interrupted': text = 'Tác vụ bị gián đoạn vì máy chủ đã khởi động lại. Các chương đã viết xong được giữ lại; chạy lại để viết tiếp.'; break;
    default: text = isVietnamese(raw) ? raw : 'Tác vụ mô hình thất bại.';
  }
  return { text, detail: raw && raw !== text ? raw : '' };
}

// ---------------------------------------------------------------- validation issues
const w = (s) => (s ? s : '');
const BUILD = {
  no_thesis: () => 'Câu hỏi chính (thesis) đang trống: hãy viết một câu hỏi mà video này trả lời.',
  no_chapters: () => 'Dàn ý chưa có chương nào.',
  duplicate_chapter: (i) => `Mã chương ${w(i.chapter) || '(trống)'} bị trống hoặc dùng hai lần.`,
  chapter_no_title: (i) => `Chương ${w(i.chapter)} chưa có tên.`,
  chapter_no_budget: (i) => `Chương ${w(i.chapter)} chưa có ngân sách số từ.`,
  duplicate_fact: () => 'Hai dữ kiện đang dùng chung một mã.',
  fact_no_source: (i) => `Dữ kiện ${w(i.fact)} chưa dẫn đoạn nguồn nào.`,
  unknown_source_id: (i, r) => { const m = /cites (.+?),? (?:not in|which is not)/i.exec(r); return `Dữ kiện ${w(i.fact)} dẫn ${m ? m[1] : 'một mã'} không có trong tập sách.`; },
  disputed_no_conflict: (i) => `Dữ kiện ${w(i.fact)} đang ghi là tranh cãi nhưng chưa mô tả chỗ mâu thuẫn.`,
  unknown_fact: (i, r) => { const f = (/\b(f\d+)\b/i.exec(r) || [])[1]; return i.beat ? `Dòng ${i.beat} dẫn dữ kiện ${f || ''} không có trong dàn ý.` : `${i.chapter ? 'Chương ' + i.chapter + ' dùng' : 'Có dòng dùng'} dữ kiện ${f || ''} không có trong bảng dữ kiện.`; },
  fact_unused: (i) => `Dữ kiện ${w(i.fact)} chưa chương nào dùng.`,
  no_hook_choice: () => 'Chưa chọn câu mở đầu.',
  budget_sum: (i, r) => { const m = /add up to (\d+) words; the target is (\d+)/i.exec(r); return m ? `Tổng ngân sách các chương là ${m[1]} từ, lệch so với mục tiêu ${m[2]} từ.` : 'Tổng ngân sách các chương lệch so với mục tiêu.'; },
  outline_missing: () => 'Chưa có dàn ý: lời dẫn được viết theo một dàn ý đã duyệt.',
  outline_not_approved: () => 'Dàn ý chưa duyệt. Hãy duyệt dàn ý trước khi duyệt lời dẫn.',
  outline_stale: () => 'Dàn ý đã đổi sau khi được duyệt. Hãy duyệt lại dàn ý.',
  chapter_missing: (i) => `Lời dẫn còn thiếu chương ${w(i.chapter)}.`,
  unknown_chapter: (i) => `Chương ${w(i.chapter)} có trong lời dẫn nhưng không có trong dàn ý.`,
  empty_beat: (i) => `Dòng ${w(i.beat)}${i.chapter ? ' (chương ' + i.chapter + ')' : ''} đang trống.`,
  markup_in_text: (i, r) => { const m = /has (.+?) in its text/i.exec(r); return `Dòng ${w(i.beat)} có ký hiệu${m ? ' ' + m[1] : ''} trong lời đọc; lời đọc chỉ gồm chữ để đọc.`; },
  spoken_chars: (i) => `Dòng ${w(i.beat)} có dấu câu mà giọng đọc không ngắt được (; : ( ) hoặc gạch ngang). Dùng dấu phẩy và dấu chấm.`,
  beat_too_long: (i, r) => { const m = /has (\d+) words/i.exec(r); return `Dòng ${w(i.beat)} dài ${m ? m[1] + ' từ' : 'quá'} (trên 90), nên tách ra.`; },
  no_show: (i) => `Dòng ${w(i.beat)} chưa có gợi ý hình sẽ hiện.`,
  words_under: (i, r) => { const m = /Only (\d+) words, under 70% of the target (\d+)/i.exec(r); return m ? `Mới có ${m[1]} từ, dưới 70% mục tiêu ${m[2]} từ.` : 'Lời dẫn quá ngắn so với mục tiêu.'; },
  words_off_target: (i, r) => { const m = /(\d+) words; the target is (\d+)/i.exec(r); return m ? `Có ${m[1]} từ, mục tiêu ${m[2]} từ (lệch hơn 15%).` : 'Số từ lệch mục tiêu quá 15%.'; },
  chapter_off_budget: (i, r) => { const m = /has (\d+) words; its budget is (\d+)/i.exec(r); return m ? `Chương ${w(i.chapter)} có ${m[1]} từ, ngân sách ${m[2]} từ (lệch hơn 30%).` : `Chương ${w(i.chapter)} lệch ngân sách quá 30%.`; },
  length: (i, r) => { const m = /(\d+) words, about ([\d.]+) minutes at ([\d.]+)/i.exec(r); return m ? `${m[1]} từ, khoảng ${m[2]} phút ở ${m[3]} từ/giây.` : 'Độ dài lời dẫn.'; },
  source_share: (i, r) => `Phần đoạn nguồn đứng sau các dữ kiện đã dùng: ${(/facts: (.+?)\.?$/i.exec(r) || [])[1] || ''}.`,
  overlap: (i, r) => { const m = /(\d+%)/.exec(r); return `${m ? m[1] : 'Một phần'} số từ nằm trong các đoạn chép từ 8 từ trở lên từ nguồn (chỉ để biết).`; },
  // paste (parse) issues
  chapter_by_position: (i, r) => { const m = /heading "(.*)" was matched to (\S+)/i.exec(r); return m ? `Tiêu đề chương "${m[1]}" được ghép với ${m[2]} theo vị trí.` : 'Một tiêu đề chương được ghép theo vị trí.'; },
  chapter_twice: (i) => `Chương ${w(i.chapter)} xuất hiện hai lần trong văn bản; các đoạn đã được nối lại.`,
  meta_orphan: () => 'Có dòng ">>" không đi kèm đoạn nào phía trên; đã bỏ qua.',
  no_chapter_lines: () => 'Văn bản không có dòng tiêu đề chương; tất cả đoạn được đặt vào cùng một chương.',
  preamble_dropped: (i, r) => { const m = /(\d+) paragraph/i.exec(r); return `${m ? m[1] + ' đoạn' : 'Một số đoạn'} trước dòng chương đầu tiên đã bị bỏ vì là lời bình.`; },
  chapter_empty: (i) => `Chương ${w(i.chapter)} chưa có đoạn nào.`,
  budget_defaulted: (i, r) => { const m = /set to (\d+)/i.exec(r); return `Chương ${w(i.chapter)} chưa có ngân sách; đặt tạm ${m ? m[1] : ''} từ.`; },
  no_facts: () => 'Dàn ý không có bảng dữ kiện.',
  hook_defaulted: (i, r) => { const m = /; (\S+) was chosen/i.exec(r); return `Không có câu mở được chọn hợp lệ; tự chọn ${m ? m[1] : 'câu đầu'}.`; },
};
const GATES = [[/There is no outline/i, 'outline_missing'], [/not approved/i, 'outline_not_approved'], [/Stale outline approval|changed after it was approved/i, 'outline_stale']];

/** Vietnamese sentence for a validation issue. `detail` holds the server's English text when no builder knows the code. */
export function issueText(issue) {
  const raw = String(issue?.message || '');
  let code = issue?.code;
  if (!code || !BUILD[code]) { const g = GATES.find(([re]) => re.test(raw)); if (g) code = g[1]; }
  const fn = BUILD[code];
  if (fn) { try { return { text: fn(issue || {}, raw), detail: raw }; } catch { /* fall through */ } }
  if (isVietnamese(raw)) return { text: raw, detail: '' };
  return { text: 'Có một lưu ý về nội dung mà ứng dụng chưa dịch được. Xem "chi tiết".', detail: raw, generic: true };
}

// ---------------------------------------------------------------- a pasted text that could not be read
/** Vietnamese reason why the paste (outline or script) was refused; takes the server's `error` text (first line is enough). */
export function parseFailText(errorText) {
  const first = String(errorText || '').split('\n')[0];
  const what = /outline/i.test(first) ? 'dàn ý' : 'lời dẫn';
  let m;
  if (/The text is empty/i.test(first)) return `Không đọc được ${what}: văn bản trống.`;
  if (/No narration paragraphs were found/i.test(first)) return 'Không đọc được lời dẫn: không thấy đoạn lời dẫn nào.';
  if ((m = /no chapter lines.*outline has (\d+) chapters/i.exec(first))) return `Không đọc được lời dẫn: văn bản không có dòng tiêu đề chương (## c01 TÊN CHƯƠNG), mà dàn ý có ${m[1]} chương.`;
  if (/match no chapter of the outline/i.test(first)) return `Không đọc được lời dẫn: có tiêu đề chương không khớp chương nào của dàn ý${(/:\s*(.+?)\.?$/.exec(first) || [])[1] ? ' (' + /:\s*(.+?)\.?$/.exec(first)[1] + ')' : ''}.`;
  if (/no narration paragraphs follow/i.test(first)) return 'Không đọc được lời dẫn: có dòng tiêu đề chương nhưng không có đoạn nào theo sau.';
  if (/No chapters were found/i.test(first)) return 'Không đọc được dàn ý: không thấy chương nào (mỗi chương bắt đầu bằng một dòng như: ## c01 MỞ ĐẦU).';
  if (isVietnamese(first)) return first;
  return `Không đọc được ${what} từ văn bản đã dán.`;
}
