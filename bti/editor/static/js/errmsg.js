// The ONE place that turns an error into a message for the owner (Vietnamese).
// describeHttp(status, body) -> { text, detail }: `text` is the sentence shown, `detail` the raw server text kept under
// "chi tiết" when the sentence is not the same as what the server said. Reads `detail`, `reason`, `error`, `issues` of the body
// and survives a body it does not recognise. issueText(issue) does the same for the validation issues ({code, message, ...}).
// jobErrorText(job) does it for a failed model job. Pure; tested in tests/editor_frontend/errmsg.test.mjs.

import { storyboardIssueText } from './sbissues.js';

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
  /* worker dscript */
  [/at least one source must stay/i, 'Phải giữ lại ít nhất một nguồn sách.'],
  [/key and with/i, 'Thiếu tác phẩm cần gộp.'],
  [/cannot merge an artwork with itself/i, 'Không gộp một tác phẩm với chính nó.'],
  [/artwork has only one source/i, 'Tác phẩm này chỉ có một nguồn nên không tách được.'],
  // storyboard, media, previews
  [/^licence |licence is missing|object is not public domain/i, (m, b, raw) => licenceText(raw).text],
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
  /* worker idapply: PUT /api/projects/{pid}/identity */
  [/unknown identity style/i, 'Kiểu mở đầu này không có trong danh sách. Hãy chọn lại ở ô "Kiểu mở đầu và mốc chương".'],
  [/style \(string\) is required/i, 'Chưa chọn kiểu mở đầu và mốc chương.'],
  [/no `?identity`? block|identity styles/i, 'Kiểu dựng của video này chưa có các kiểu mở đầu và mốc chương.'],
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

// ---------------------------------------------------------------- codes of the long-job runner and of the stage routes
// Answers carry `{detail, code}`; the sentence comes from the code, never from `detail`. One table per stage because a few codes
// (busy, stale, not_found) mean different things in different stages; the views ask `stageErrorText(stage, e)`. Codes that are
// unique to one stage are also found by describeHttp, so any other view that meets them still speaks Vietnamese.
const CLAUDE_OUTDATED_HEAD = 'Claude Code trên máy chủ quá cũ cho mô hình này';        // worker followups: "Claude Code is too old for this model", code claude_outdated (not a quota)
const LONGJOB_CODES = {
  longjob_missing: 'Máy chủ thiếu bộ chạy việc dài.',
  longjob_not_found: 'Không tìm thấy việc này (có thể máy chủ đã khởi động lại).',
  longjob_running: 'Dự án đang có một việc dài chạy (giọng đọc, bản nháp, xuất video...). Chờ xong hoặc bấm Hủy rồi thử lại.',
  part_timeout: 'Một bước chạy quá lâu nên bị dừng. Bấm chạy lại để làm tiếp, phần đã xong được giữ lại.',
  part_failed: 'Một bước bị lỗi bất ngờ. Bấm chạy lại để thử tiếp.',
  part_stuck: 'Một bước không dừng lại được. Bấm chạy lại sau ít phút.',
  interrupted: 'Máy chủ đã khởi động lại giữa chừng. Bấm chạy lại để làm tiếp, phần đã xong được giữ lại.',
  heavy_unavailable: 'Máy đang bận việc khác nên chưa chạy được. Hãy báo cho chủ máy nếu việc này kéo dài.',
  project_gone: 'Dự án đã bị xóa.',
  longjob_internal: 'Việc bị lỗi không mong đợi trên máy chủ.',
  accept_all_required: 'Dự án chưa có storyboard: chỉ chấp nhận được cả đề xuất, không chọn từng thay đổi.',
  // --- draft and edit (page)
  real_models_off: 'Bản ứng dụng này đang chạy ở chế độ thử nên không gọi mô hình hay dịch vụ bên ngoài. Hãy dùng bản chính.',
};
export const STAGE_CODES = {
  longjob: LONGJOB_CODES,
  voice: {
    narration_missing: 'Chưa có lời dẫn. Hãy làm bước Kịch bản trước.',
    narration_not_approved: 'Lời dẫn chưa được duyệt. Hãy duyệt ở bước Kịch bản rồi quay lại.',
    nothing_to_say: 'Lời dẫn chưa có câu nào để đọc.',
    voice_not_configured: 'Máy này chưa cài giọng đọc. Hãy dùng máy chủ giọng đọc (Windows).',
    voice_busy: 'Giọng đọc của dự án này đang chạy rồi. Chờ nó xong hoặc bấm Hủy.',
    voice_worker_failed: 'Máy đọc giọng bị dừng giữa chừng. Bấm tạo lại để đọc tiếp, các câu đã đọc được giữ lại.',
    voice_chunks_failed: 'Có câu máy chưa đọc được. Bấm tạo lại để thử tiếp.',
    voice_chunks_missing: 'Lời dẫn đã đổi trong lúc đọc. Hãy chạy lại để đọc phần mới.',
    voice_assemble_failed: 'Không ghép được tệp âm thanh.',
    voice_align_failed: 'Không đo được thời điểm từng từ.',
    no_voice: 'Chưa có tệp âm thanh để nghe.',
    no_chunk: 'Câu này chưa được đọc.',
    bad_scope: 'Yêu cầu đọc không hợp lệ.',
    bad_tempo: 'Tốc độ phải nằm trong khoảng cho phép.',
    bad_pad: 'Nhạc nền chỉ có bật hoặc tắt.',
    bad_pronounce: 'Bảng phát âm có dòng không hợp lệ (cần chữ viết và cách đọc, mỗi ô không quá dài).',
  },
  picks: {
    stale: 'Chọn hình đã đổi ở nơi khác (tab khác hoặc tác vụ nền). Đang tải lại bản mới nhất.',
    source_unreachable: 'Nguồn ảnh đang bận hoặc không trả lời. Thử lại sau vài giây.',
    source_error: 'Nguồn ảnh báo lỗi. Thử lại hoặc chọn nguồn khác.',
    not_found: 'Không tìm thấy ảnh này ở nguồn.',
    unknown_source: 'Nguồn ảnh này không có trong danh sách.',
    query_required: 'Gõ từ khóa để tìm.',
    narration_not_approved: 'Lời dẫn chưa được duyệt (hoặc đã đổi sau khi duyệt). Duyệt lời dẫn ở bước Kịch bản trước.',
    picks_have_errors: 'Chọn hình còn lỗi nên chưa duyệt được. Bấm "Kiểm tra" để xem.',
    image_empty: 'Tệp ảnh trống.', image_unreadable: 'Tệp này không phải ảnh đọc được.', image_truncated: 'Tệp ảnh bị cắt dở, không đọc hết được. Tải lại tệp đầy đủ.',
    region_name: 'Tên vùng không hợp lệ (chữ, số, dấu cách, - hoặc _; tối đa 40 ký tự).', region_shape: 'Vùng không hợp lệ.', region_outside: 'Tâm vùng nằm ngoài bức ảnh.',
    confirm_required: 'Cần bạn xác nhận chi phí trước khi chạy.', suggest_off: 'Gợi ý thêm đang tắt trong cấu hình.', suggest_no_key: 'Chưa có khóa You.com trên máy chủ.',
    suggest_failed: 'You.com không trả lời được. Thử lại sau.', suggest_key_refused: 'You.com từ chối khóa của máy chủ. Cần kiểm tra khóa.',
    suggest_quota: 'Tài khoản You.com hết hạn mức hoặc cần thanh toán.', suggest_timeout: 'You.com trả lời quá chậm (hết thời gian chờ). Thử lại sau.',
    suggest_bad_answer: 'You.com từ chối yêu cầu hoặc trả lời sai dạng.', busy: 'Đang có một lượt gợi ý chạy cho dự án này.', too_many: 'Chọn tối đa 40 dòng một lần.',
    video_bad_url: 'Đường dẫn không phải link YouTube hợp lệ (youtube.com/watch?v=... hoặc youtu.be/...).',
    video_bad_range: 'Khoảng thời gian cắt không hợp lệ (từ 0,5 đến 120 giây).',
    video_unreadable: 'Tệp này không phải video đọc được hoặc bị hỏng.',
    video_fetch_failed: 'Không lấy hoặc cắt được đoạn video này.',
    video_timeout: 'Tải đoạn video quá lâu nên đã dừng. Thử lại với đoạn ngắn hơn.',
    video_not_main: 'Video không đặt làm tranh chính được; hãy dùng ảnh tĩnh cho tranh chính.',
    youcom_key_missing: 'Chưa có khóa You.com (YDC_API_KEY) trên máy chủ.',
    tool_missing: 'Máy chủ thiếu công cụ yt-dlp hoặc ffmpeg để xử lý video.',
    // --- dsources
    source_no_key: 'Nguồn này chưa có khóa API trên máy chủ.',
  },
  export: {
    no_storyboard: 'Chưa có storyboard. Hãy dựng hình ở bước "Dựng hình" trước.',
    not_approved: 'Storyboard chưa được duyệt. Mở bước "Dựng hình" và bấm Duyệt.',
    approval_stale: 'Storyboard đã đổi sau khi duyệt. Mở bước "Dựng hình" và duyệt lại.',
    storyboard_unreadable: 'Không đọc được tệp storyboard của dự án.',
    no_audio: 'Chưa có tệp giọng đọc. Hãy làm bước "Giọng đọc" trước.',
    no_timing: 'Chưa có tệp thời điểm của từng từ (timing). Hãy làm bước "Giọng đọc" trước.',
    busy: 'Dự án này đang xuất video rồi. Chờ xong hoặc bấm Hủy.',
    render_failed: 'Dựng hình bị dừng giữa chừng. Bấm "Xuất video" lần nữa để làm tiếp: những đoạn đã dựng xong được giữ lại.',
    frames_mismatch: 'Số khung hình của video không đúng với kế hoạch, nên đã dừng để không tạo ra tệp sai.',
    join_failed: 'Không ghép được các đoạn video lại với nhau.',
    part_missing: 'Thiếu một đoạn video đã dựng. Bấm "Xuất video" lần nữa.',
    mux_failed: 'Không ghép được tiếng và mục lục vào video.',
    plan_failed: 'Không lên được kế hoạch xuất. Storyboard có thể đang có lỗi: thử mở bước "Dựng hình".',
  },
  draft: {
    draft_not_ready: 'Chưa đủ dữ liệu để dựng bản nháp: xong bước Giọng đọc và Chọn hình trước.',
    agy_missing: 'Máy này chưa có chương trình agy hoặc chưa đăng nhập. Dùng "Dựng tự động" hoặc cài và đăng nhập agy.',
    scope_needs_storyboard: 'Dựng lại một chương cần storyboard có sẵn. Hãy dựng cả video trước.',
    bad_provider: 'Cách dựng bản nháp không hợp lệ.',
    bad_model: 'Mô hình này không có trong danh sách.',
    bad_chapters: 'Danh sách chương không hợp lệ.',
    unknown_chapter: 'Có chương không nằm trong lời dẫn.',
    busy: 'Dự án này đang dựng bản nháp rồi. Chờ xong hoặc bấm Dừng.',
    picks_missing: 'Chưa có danh sách hình đã duyệt. Làm bước Chọn hình trước.',
    timing_missing: 'Chưa có tệp thời điểm từng từ. Làm bước Giọng đọc trước.',
    picks_no_main: 'Chưa chọn tranh chính ở bước Chọn hình.',
    draft_tampered: 'Lần dựng bị bỏ vì agent đã đổi tệp ngoài thư mục làm việc của nó. Không có gì được lấy từ lần đó.',
    draft_no_output: 'Agent không viết ra tệp nào để dùng. Thử dựng lại hoặc dùng "Dựng tự động".',
    agy_auth: 'Chương trình agy chưa đăng nhập. Đăng nhập agy trên máy chủ (trong phiên làm việc của bạn) rồi thử lại.',
    agy_busy: 'Agent đang bận với một lần dựng khác. Chờ xong rồi thử lại.',
    agy_config: 'Chương trình agy trên máy này quá cũ hoặc thiếu tùy chọn cần dùng.',
    agy_error: 'Agent báo lỗi khi dựng. Thử lại, hoặc dùng "Dựng tự động".',
    agy_model: 'Mô hình đã chọn không dùng được. Chọn mô hình khác.',
    agy_no_result: 'Agent kết thúc mà không trả kết quả. Xem bản ghi của lần chạy rồi thử lại.',
    agy_rate_limit: 'Agent bị giới hạn lượt dùng hoặc hết hạn mức. Thử lại sau.',
    agy_timeout: 'Agent chạy quá thời gian cho phép nên bị dừng. Thử dựng từng chương.',
    /* worker claudeprov: the second runner, Claude Code (`claude`) */
    claude_missing: 'Chưa cài Claude Code (lệnh `claude`) trên máy chủ. Cài Claude Code, đăng nhập một lần bằng lệnh `claude auth login`, rồi thử lại.',
    claude_auth: 'Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại.',
    claude_rate_limit: 'Hạn mức của gói Claude Code đã dùng hết hoặc bị giới hạn. Đợi hết chu kỳ hoặc chọn agent khác.',
    claude_model: 'Claude Code không nhận ra tên mô hình này. Chọn mô hình khác.',
    claude_config: 'Claude Code trên máy chủ không dùng được cho việc này (quá cũ hoặc không chạy được). Chạy `claude update` trên máy chủ rồi thử lại.',
    claude_outdated: `${CLAUDE_OUTDATED_HEAD}. Chạy \`claude update\` trên máy chủ rồi thử lại.`,        // worker followups: the server's own sentence adds the versions (stageJobErrorText)
    claude_error: 'Claude Code báo lỗi khi chạy. Thử lại, hoặc dùng "Dựng tự động".',
    claude_no_result: 'Claude Code dừng mà không trả kết quả. Xem bản ghi của lần chạy rồi thử lại.',
    claude_timeout: 'Agent chạy quá thời gian cho phép nên bị dừng. Thử dựng từng chương.',
    edit_outside_scope: 'Agent đã thay đổi phần ngoài phạm vi được chỉ định hoặc cảnh đang khóa.',
    edit_no_storyboard: 'Chỉ sửa bằng prompt khi dự án đã có storyboard.',
    edit_bad_scope: 'Phạm vi sửa không hợp lệ (cần chọn cảnh, chương hoặc cả video).',
    edit_empty_instruction: 'Chưa nhập yêu cầu sửa (hãy gõ hướng dẫn cho agent).',
    edit_needs_agy: 'Sửa bằng prompt cần dùng agent agy, không dùng được chế độ tự động.',
    edit_no_change: 'Agent không thay đổi gì trong storyboard.',
    compile_error: 'Không thể ghép các cảnh do có lỗi thông số hoặc cú pháp.',
    edit_degraded: 'Lần sửa bị từ chối vì có cảnh bị hạ cấp hoặc không đầy đủ.',
    // --- dsources: draft turn and undo error codes
    bad_action: 'Thao tác không hợp lệ.',
    not_needs_choice: 'Lượt sửa này không cần chọn tiếp.',
    turn_data_lost: 'Dữ liệu của lượt sửa này không còn lưu.',
    already_undone: 'Lượt sửa này đã được hoàn tác trước đó rồi.',
    turn_not_applied: 'Lượt sửa này chưa được áp dụng nên không hoàn tác được.',
    undo_unavailable: 'Bản nháp trước lượt này không còn lưu.',
    undo_conflict: 'Không hoàn tác được vì một số cảnh đã bị thay đổi sau lượt này.',
    undo_failed: 'Hoàn tác lượt sửa thất bại.',
    escalate: 'Yêu cầu này cần xem kỹ hơn hoặc sửa nhiều hơn phần đã chọn. Hãy chọn phần rộng hơn hoặc nói cụ thể hơn.',
    // --- draft and edit (page)
    stale_revision: 'Storyboard đã đổi ở nơi khác kể từ lúc bạn mở. Tải lại trang rồi gửi lại.',
    edit_locked_changed: 'Có cảnh đang khóa bị đổi, nên lần sửa bị bỏ. Mở khóa cảnh đó rồi thử lại.',
    compile_empty: 'Agent không đưa ra cảnh nào để ghép.',
    main_asset_unreadable: 'Không đọc được tranh chính của dự án.',
    picks_shape: 'Danh sách hình đã chọn bị sai cấu trúc. Làm lại bước Chọn hình.',
    project_missing: 'Không tìm thấy dự án này.',
    spec_invalid: 'Agent trả về các cảnh sai cấu trúc nên không ghép được.',
    storyboard_corrupt: 'Tệp storyboard của dự án bị hỏng.',
    template_missing: 'Máy chủ thiếu tệp lời nhắc cho việc này.',
    timing_shape: 'Tệp thời điểm từng từ sai cấu trúc. Làm lại bước Giọng đọc.',
    workspace_invalid: 'Thư mục làm việc của agent không dùng được. Thử lại.',
    cancelled: 'Việc đã bị dừng.',
    edit_failed: 'Lần sửa này không làm xong vì một lỗi không rõ. Thử lại, hoặc nói rõ hơn.',
  },
  // --- draft and edit (page): the model settings
  settings: {
    invalid_payload: 'Cài đặt gửi lên không hợp lệ.',
    unknown_role: 'Có việc không có trong danh sách việc.',
    invalid_model: 'Có việc chưa chọn mô hình.',
    agentic_role_needs_agy: 'Việc dựng và sửa sâu cần mô hình chạy qua agy hoặc qua Claude Code.',      // worker claudeprov: Claude Code now counts
    unknown_model: 'Có mô hình không có trong danh sách.',
    /* worker agentpick: the agent select and the default agent */
    unknown_agent: 'Agent này không có trong danh sách agent.',
    unknown_step: 'Bước này không có trong danh sách bước.',
    agent_unavailable: 'Agent đang chọn chưa dùng được trên máy này.',
  },
  /* worker c1state: the refusals every page can meet (the server now gives each one a code, see bti/editor/hints.py). Where the server's
     own text already has an exact sentence (it names the beat, the shot, the field), BY_CODE_HTTP below keeps that one and uses these
     only when the text has none. */
  /* worker join: the refusals of the typed operations (bti/ops, docs/OPS.md) that the instruction box shows to a person. The operations are made
     by a model, so every sentence says what could not be done and what to say or choose instead; none shows an id. */
  ops: {
    unknown_op: 'Yêu cầu sửa này dùng một thao tác không có nên chưa làm. Hãy nói lại yêu cầu.',
    unknown_shot: 'Không có cảnh này trong storyboard. Chọn lại cảnh cần sửa.',
    unknown_overlay: 'Cảnh này không có lớp phủ đó. Chọn lại lớp phủ cần sửa.',
    unknown_beat: 'Không có đoạn lời dẫn này. Chọn lại đoạn cần sửa.',
    unknown_asset: 'Không có hình này trong dự án. Chọn hình khác, hoặc nhập hình trước.',
    unknown_region: 'Hình này không có vùng đó. Thêm vùng trước, hoặc chọn vùng khác.',
    unknown_param: 'Kỹ thuật này không có thông số đó. Chọn thông số khác.',
    unknown_slot: 'Kỹ thuật này không có chỗ đặt hình đó. Chọn chỗ khác.',
    wrong_technique_kind: 'Kỹ thuật này không dùng được ở chỗ này: cảnh và lớp phủ dùng hai loại kỹ thuật khác nhau. Chọn kỹ thuật khác.',
    technique_unavailable: 'Kỹ thuật này chưa dựng được. Chọn kỹ thuật khác.',
    slot_kind_mismatch: 'Hình này không hợp với chỗ đặt: chỗ đó cần loại khác (ảnh, video hoặc mặt nạ). Chọn hình khác.',
    unknown_ref: 'Yêu cầu nhắc tới một thứ chưa được tạo ở bước trước. Hãy nói lại yêu cầu.',
    duplicate_ref: 'Yêu cầu đặt hai thứ mới cùng một tên. Hãy nói lại yêu cầu.',
    shot_too_short: 'Chỗ cắt này làm một cảnh ngắn hơn 0,2 giây. Chọn thời điểm khác.',
    not_consecutive: 'Các cảnh được chọn không nằm kề nhau. Chọn các cảnh liền nhau.',
    span_mismatch: 'Các cảnh mới không khớp với khoảng thời gian của các cảnh bị thay. Hãy nói lại yêu cầu.',
    locked: 'Cảnh hoặc lớp phủ này đang khóa nên không sửa được. Mở khóa trước.',
    out_of_scope: 'Yêu cầu này chạm tới phần ngoài phạm vi bạn đã chọn nên chưa làm. Chọn phạm vi rộng hơn, hoặc nói cụ thể hơn.',
    undo_conflict: 'Không hoàn tác được vì có phần đã bị sửa tiếp sau lần sửa này. Hoàn tác các lần sửa sau trước, hoặc để nguyên phần đó.',
    undo_unavailable: 'Không hoàn tác được lần sửa này vì bản lưu của nó đã bị xóa bớt. Hãy sửa lại bằng một yêu cầu mới.',
    batch_not_found: 'Không tìm thấy lần sửa này trong lịch sử thay đổi.',
    import_failed: 'Không nhập được hình này vào dự án. Chọn hình khác hoặc nguồn khác.',
    audio_decode_failed: 'Không đọc được tệp âm thanh của dự án. Hãy làm lại bước "Giọng đọc".',
    image_too_small: 'Ảnh này quá nhỏ để dùng. Chọn ảnh lớn hơn.',
  },
  api: {
    project_not_found: 'Không có dự án này.',
    storyboard_not_found: 'Dự án chưa có storyboard.',
    validation_failed: 'Storyboard còn lỗi nên chưa lưu hoặc duyệt được. Xem danh sách lỗi.',
    save_refused: 'Storyboard còn lỗi nên chưa lưu hoặc duyệt được. Xem danh sách lỗi.',
    storyboard_has_errors: 'Storyboard còn lỗi nên chưa làm tiếp được. Xem danh sách lỗi, sửa rồi thử lại.',
    storyboard_incomplete: 'Còn cảnh chưa đủ hình hoặc đoạn phim nên chưa duyệt được. Xem danh sách lỗi để biết cảnh nào.',
    style_not_found: 'Không có kiểu (style) này.',
    nothing_to_restore: 'Storyboard vẫn đọc được bình thường nên không có gì để khôi phục.',
    no_history_copy: 'Trong lịch sử của dự án không còn bản storyboard nào đọc được. Hãy dựng bản nháp mới ở bước "Dựng hình".',
    history_file_not_found: 'Không thấy bản lưu này trong lịch sử của dự án. Chọn bản khác.',
    history_file_unreadable: 'Bản lưu này trong lịch sử không đọc được. Chọn bản khác.',
    unknown_technique: 'Kỹ thuật không có trong danh sách.',
    shot_not_found: 'Không tìm thấy cảnh này.',
    no_audio_file: 'Dự án chưa có tệp âm thanh. Hãy làm bước "Giọng đọc" trước.',
    preview_too_long: 'Đoạn xem thử quá dài. Chọn đoạn ngắn hơn.',
    preview_too_many_frames: 'Đoạn xem thử có quá nhiều khung hình. Chọn đoạn ngắn hơn.',
    job_not_found: 'Không tìm thấy tác vụ này (có thể máy chủ đã khởi động lại).',
    asset_not_found: 'Không tìm thấy hình này.',
    licence_rejected: 'Giấy phép của ảnh này không được chấp nhận. Chọn ảnh khác.',
    unsupported_file_type: 'Loại tệp này chưa hỗ trợ. Chọn ảnh (jpg, png, webp) hoặc video (mp4, mov, webm, m4v).',
    file_too_large: 'Tệp quá lớn (tối đa 80 MB). Chọn tệp nhỏ hơn.',
    thumbnail_failed: 'Không tạo được ảnh nhỏ từ tệp này.',
    proposal_not_found: 'Không tìm thấy đề xuất này.',
    proposal_corrupt: 'Tệp đề xuất này bị hỏng nên đã được cất đi. Hãy dựng bản nháp mới.',
    proposal_malformed: 'Đề xuất này sai cấu trúc nên không dùng được. Hãy dựng bản nháp mới.',
    proposal_has_errors: 'Storyboard trong đề xuất còn lỗi nên chưa nhận được. Hãy dựng bản nháp mới.',
    unknown_change_ids: 'Có thay đổi không còn trong đề xuất. Mở lại đề xuất rồi chọn lại.',
    turn_not_found: 'Không tìm thấy lượt sửa này.',
    turn_frame_not_found: 'Không có ảnh của cảnh này cho lượt sửa. Bản lưu của lượt đó có thể không còn.',
    edit_running: 'Đang có một yêu cầu sửa chạy nên chưa xóa được lịch sử. Hãy hủy tác vụ trước.',
    export_file_not_found: 'Không tìm thấy tệp này trong thư mục xuất. Có thể nó đã bị xóa.',
    model_unavailable: 'Mô hình này chưa dùng được trên máy này (thiếu khóa hoặc chưa cài). Chọn mô hình khác.',
    model_invalid: 'Tên mô hình gửi lên không hợp lệ. Chọn một mô hình ở ô trên thanh công cụ rồi thử lại.',
    prompt_error: 'Chưa tạo được lời nhắc từ dàn ý và lời dẫn hiện có. Kiểm tra hai phần đó rồi thử lại.',
    outline_unreadable: 'Không đọc được dàn ý từ văn bản đã dán. Chưa có gì bị ghi đè.',
    narration_unreadable: 'Không xếp được lời dẫn từ văn bản đã dán. Chưa có gì bị ghi đè.',
    document_invalid: 'Dữ liệu gửi lên sai cấu trúc nên chưa lưu được. Hãy tải lại trang rồi sửa lại.',
    outline_has_errors: 'Dàn ý còn lỗi nên chưa duyệt được. Xem hộp "Kiểm tra".',
    narration_has_errors: 'Lời dẫn còn lỗi nên chưa duyệt được. Xem hộp "Kiểm tra".',
    locked_beats: 'Có dòng đang khóa sẽ bị viết lại. Mở khóa các dòng đó hoặc chọn viết lại cả dòng khóa.',
    op_invalid: 'Thao tác này không làm được ở trạng thái hiện tại. Hãy tải lại rồi làm lại.',
    merge_refused: 'Không gộp được hai tác phẩm này. Hãy chọn hai tác phẩm khác nhau.',
    split_refused: 'Không tách được mục này ra khỏi tác phẩm.',
    project_create_refused: 'Chưa tạo được dự án. Kiểm tra tên thư mục và các mục sách đã chọn rồi thử lại.',
    project_source_missing: 'Thiếu tệp nguồn của tác phẩm này trong thư viện. Hãy báo cho người quản lý máy.',
    picks_error: 'Phần chọn hình gặp lỗi. Thử lại, hoặc xem "chi tiết".',
    bad_text_character: 'Văn bản có ký tự lạ nên chưa lưu được. Hãy xóa ký tự đó rồi gửi lại.',
    source_unavailable: 'Nguồn bên ngoài đang bận hoặc không trả lời. Thử lại sau vài giây.',
    source_timeout: 'Nguồn bên ngoài trả lời quá chậm. Thử lại sau.',
    invalid_field: 'Dữ liệu gửi lên không hợp lệ.',
    // only a program meets these (a wrong route or method, a body of the wrong shape): one shared sentence
    route_not_found: 'Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy.',
    method_not_allowed: 'Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy.',
    invalid_request: 'Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy.',
    accept_invalid: 'Yêu cầu gửi lên máy chủ không đúng dạng. Hãy tải lại trang rồi thử lại. Nếu vẫn lỗi, báo cho người quản lý máy.',
  },
};
const AMBIGUOUS = new Set(['busy', 'stale', 'not_found']);
const UNIQUE_CODES = (() => {
  const out = {};
  for (const table of Object.values(STAGE_CODES)) for (const [k, v] of Object.entries(table)) if (!AMBIGUOUS.has(k) && !(k in out)) out[k] = () => v;
  return out;
})();
/** The Vietnamese sentence of an error of stage `stage` (voice | picks | export | draft) by its `code`; other errors go through describeError. */
export function stageErrorText(stage, e) {
  const code = e?.body && typeof e.body === 'object' ? e.body.code : null;
  const t = typeof code === 'string' ? STAGE_CODES[stage]?.[code] || LONGJOB_CODES[code] : null;
  return t ? { text: t, detail: '' } : describeError(e);
}
/** The same for a failed long job (`job.error_code`); falls back to jobErrorText. */
export function stageJobErrorText(stage, job) {
  if (job?.error_code === 'claude_outdated' && typeof job.error === 'string' && job.error.startsWith(CLAUDE_OUTDATED_HEAD)) return { text: job.error, detail: '' };       // the server's sentence names the versions the answer stated
  const t = job?.error_code && (STAGE_CODES[stage]?.[job.error_code] || LONGJOB_CODES[job.error_code]);
  return t ? { text: t, detail: '' } : jobErrorText(job);
}

/** Vietnamese message for an HTTP error. Never returns an empty text. */
const BY_CODE_HTTP = {
  ...UNIQUE_CODES,
  too_large: () => 'Dữ liệu gửi lên quá lớn (trên 8 MB) nên máy chủ không nhận. Thu nhỏ tệp hoặc bớt nội dung rồi thử lại.',
  project_busy: () => 'Dự án đang được lưu hoặc xử lý ở chỗ khác nên chưa xóa được. Đợi vài giây rồi thử lại.',
  too_deep: () => 'Dữ liệu gửi lên có cấu trúc lồng quá sâu nên máy chủ từ chối.',
  project_file_damaged: () => 'Tệp project.json của dự án này bị hỏng nên ứng dụng không xóa được. Hãy sửa hoặc xóa thư mục dự án bằng tay trong máy chủ.',
  undrawable: () => 'Storyboard có chỗ không vẽ được nên chưa duyệt được. Xem danh sách các shot bị lỗi.',
  render_failed: (b) => renderFailText(b),
  /* worker dscript */
  at_least_one_source: () => 'Phải giữ lại ít nhất một nguồn sách.',
  /* worker mediafix */
  source_rate_limited: (b) => sourceLimitText(b),
  /* worker mediafix3: a map was asked for without a place (an old or damaged source id): never drawn for a guessed place */
  map_place_unknown: () => 'Không biết bản đồ này ở đâu nên không vẽ được. Hãy tìm lại địa điểm rồi chọn lại.',
  /* worker agentpick: the server's own sentence says which agent cannot run and why (Vietnamese, from the agent's check) */
  agent_unavailable: (b) => (typeof b?.detail === 'string' && isVietnamese(b.detail) ? b.detail : STAGE_CODES.settings.agent_unavailable),
};
/* worker c1state: the codes the server now adds to refusals it used to send without one. A sentence made from the server's own text
   (it names the beat, the shot, the field) is exact, so it stays; the code's own sentence answers when the text has none. */
const c1stateTextSentence = (b) => { const t = describeHttp(0, { detail: b?.detail }).text; return t === GENERIC || t === BY_STATUS[404] ? null : t; };
// these answer with their own sentence whatever the text says: only a program meets the first four (one shared sentence); for the others the code is
// certain and its sentence says what to do, where the older sentence of the text only says what is wrong
const C1STATE_OWN = ['route_not_found', 'method_not_allowed', 'file_too_large', 'unsupported_file_type', 'preview_too_long',
  'preview_too_many_frames', 'proposal_not_found', 'proposal_corrupt', 'proposal_malformed', 'no_audio_file', 'model_unavailable'];
for (const [k, v] of Object.entries(STAGE_CODES.api)) BY_CODE_HTTP[k] = C1STATE_OWN.includes(k) ? () => v : (b) => c1stateTextSentence(b) || v;
for (const k of ['stale_revision', 'unknown_chapter', 'unknown_model', 'storyboard_corrupt']) {      // codes the stage tables already had: the text still wins
  const own = BY_CODE_HTTP[k];
  BY_CODE_HTTP[k] = (b) => c1stateTextSentence(b) || own(b);
}
for (const [k, status] of Object.entries({ bad_request: 400, forbidden: 403, conflict: 409, unsupported_media: 415 })) BY_CODE_HTTP[k] = () => BY_STATUS[status];
/* worker join: the operations' own sentences (STAGE_CODES.ops) answer describeHttp, also where a stage table has the same code (`undo_conflict`
   and `undo_unavailable` of a draft turn: the draft views read their own table through stageErrorText, which is not changed). */
for (const [k, v] of Object.entries(STAGE_CODES.ops)) BY_CODE_HTTP[k] = () => v;
/* worker mediafix: a picture source answered "too many requests". `b` is the error body or a search error entry
   ({code: 'source_rate_limited', retry_after: seconds | null}); the time is rounded UP to whole minutes, and left out when the source gave none. */
export function sourceLimitText(b) {
  const s = Number(b?.retry_after);
  return Number.isFinite(s) && s > 0 ? `Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng ${Math.max(1, Math.ceil(s / 60))} phút.` : 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau.';
}
/** "Không dựng được shot s0012 (CAM-01): ..." from the 422 `render_failed` body ({shot, overlay, technique}). */
export function renderFailText(b) {
  const where = b?.shot ? `shot ${b.shot}${b.overlay ? `, lớp phủ ${b.overlay}` : ''}` : 'một shot';
  const asset = b?.asset ? `, hình ${b.asset}` : '';
  if (b?.asset) return `Không dựng được hình của ${where}${asset}: tệp ảnh bị hỏng hoặc không đọc được. Thay bằng ảnh khác ở tab Hình.`;
  return `Không dựng được hình của ${where}${b?.technique ? ` (kỹ thuật ${b.technique})` : ''} với các giá trị hiện tại. Sửa tham số của nó hoặc đổi sang kỹ thuật khác.`;
}
const DATA_ERROR = { project: 'Tệp project.json của dự án bị hỏng hoặc sai dạng.', source: 'Văn bản nguồn của dự án bị hỏng hoặc không đọc được (không phải UTF-8).', library: 'Một tệp của thư viện sách bị hỏng.', timing: 'Tệp thời gian (timing) của dự án bị thiếu hoặc hỏng.', storyboard: 'Tệp storyboard của dự án bị hỏng hoặc thiếu.', script: 'Tệp dàn ý hoặc lời dẫn của dự án bị hỏng. Bản dán gần nhất (nếu có) vẫn được giữ.', voice: 'Tệp giọng đọc của dự án bị hỏng.', picks: 'Tệp chọn hình (picks.json) của dự án bị hỏng.', export: 'Tệp kết quả xuất video của dự án bị hỏng.', draft: 'Tệp bản nháp của dự án bị hỏng.', style: 'Không đọc được kiểu (style) mà dự án dùng.' };
export function describeHttp(status, body) {
  const raw = rawDetail(status, body);
  const s = unquote(raw);
  const byCode = body && typeof body === 'object' && typeof body.code === 'string' ? BY_CODE_HTTP[body.code] : null;
  if (byCode) return { text: byCode(body), detail: body.code === 'render_failed' ? '' : raw };   // the sentence comes from the code, the shot and the asset; the server's own text is never shown
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
    case 'rate_limit': text = /Claude Code/.test(raw) && isVietnamese(raw) ? raw : 'Mô hình bị giới hạn lượt gọi hoặc đã hết hạn mức.'; break;       // worker claudeprov: Claude Code's own sentence carries the time it opens again
    case 'auth': text = /Claude Code/.test(raw) && isVietnamese(raw) ? raw : 'Nhà cung cấp mô hình từ chối khóa truy cập. Kiểm tra khóa và quyền của nó.'; break;
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
  /* worker dscript */
  source_excluded: (i) => i.level === 'error' ? `Dữ kiện ${w(i.fact)} có mọi nguồn đều đã bị bỏ.` : `Dữ kiện ${w(i.fact)} dẫn nguồn đã bị bỏ khỏi dự án.`,
  disputed_no_conflict: (i) => `Dữ kiện ${w(i.fact)} đang ghi là tranh cãi nhưng chưa mô tả chỗ mâu thuẫn.`,
  unknown_fact: (i, r) => { const f = (/\b(f\d+)\b/i.exec(r) || [])[1]; return i.beat ? `Dòng ${i.beat} dẫn dữ kiện ${f || ''} không có trong dàn ý.` : `${i.chapter ? 'Chương ' + i.chapter + ' dùng' : 'Có dòng dùng'} dữ kiện ${f || ''} không có trong bảng dữ kiện.`; },
  fact_unused: (i) => `Dữ kiện ${w(i.fact)} chưa chương nào dùng.`,
  no_hook_choice: () => 'Chưa chọn câu mở đầu.',
  budget_sum: (i, r) => { const m = /add up to (\d+) words; the target is (\d+)/i.exec(r); return m ? `Tổng ngân sách các chương là ${m[1]} từ, lệch so với mục tiêu ${m[2]} từ.` : 'Tổng ngân sách các chương lệch so với mục tiêu.'; },
  outline_missing: () => 'Chưa có dàn ý: lời dẫn được viết theo một dàn ý đã duyệt.',
  outline_not_approved: () => 'Dàn ý chưa duyệt. Hãy duyệt dàn ý trước khi duyệt lời dẫn.',
  outline_stale: () => 'Dàn ý đã đổi sau khi được duyệt. Hãy duyệt lại dàn ý.',
  chapter_missing: (i) => `Lời dẫn còn thiếu chương ${w(i.chapter)}.`,
  chapter_order: () => 'Các chương của lời dẫn xếp khác thứ tự trong dàn ý. Bấm "Sắp xếp theo dàn ý".',
  empty_chapter: (i) => `Chương ${w(i.chapter)} chưa có chữ nào trong lời dẫn.`,
  unknown_chapter: (i) => `Chương ${w(i.chapter)} có trong lời dẫn nhưng không có trong dàn ý.`,
  empty_beat: (i) => `Dòng ${w(i.beat)}${i.chapter ? ' (chương ' + i.chapter + ')' : ''} đang trống.`,
  markup_in_text: (i, r) => { const m = /has (.+?) in its text/i.exec(r); return `Dòng ${w(i.beat)} có ký hiệu${m ? ' ' + m[1] : ''} trong lời đọc; lời đọc chỉ gồm chữ để đọc.`; },
  spoken_chars: (i) => `Dòng ${w(i.beat)} có dấu câu mà giọng đọc không ngắt được (; : ( ) hoặc gạch ngang). Dùng dấu phẩy và dấu chấm.`,
  beat_too_long: (i, r) => { const m = /has (\d+) words/i.exec(r); return `Dòng ${w(i.beat)} dài ${m ? m[1] + ' từ' : 'quá'} (trên 90), nên tách ra.`; },
  /* worker dscript */
  long_sentence: (i, r) => { const m = /with (\d+) words/i.exec(r); return `Dòng ${w(i.beat)} có câu dài ${m ? m[1] + ' từ' : 'quá'} (trên 28 từ); nên tách ra.`; },
  no_show: (i) => `Dòng ${w(i.beat)} chưa có gợi ý hình sẽ hiện.`,
  words_under: (i, r) => { const m = /Only (\d+) words, under 70% of the target (\d+)/i.exec(r); return m ? `Mới có ${m[1]} từ, dưới 70% mục tiêu ${m[2]} từ.` : 'Lời dẫn quá ngắn so với mục tiêu.'; },
  words_off_target: (i, r) => { const m = /(\d+) words; the target is (\d+)/i.exec(r); return m ? `Có ${m[1]} từ, mục tiêu ${m[2]} từ (lệch hơn 15%).` : 'Số từ lệch mục tiêu quá 15%.'; },
  chapter_off_budget: (i, r) => { const m = /has (\d+) words; its budget is (\d+)/i.exec(r); return m ? `Chương ${w(i.chapter)} có ${m[1]} từ, ngân sách ${m[2]} từ (lệch hơn 30%).` : `Chương ${w(i.chapter)} lệch ngân sách quá 30%.`; },
  length: (i, r) => { const m = /(\d+) words, about ([\d.]+) minutes at ([\d.]+)/i.exec(r); return m ? `${m[1]} từ, khoảng ${m[2]} phút ở ${m[3]} từ/giây.` : 'Độ dài lời dẫn.'; },
  /* worker dscript */
  sentence_median: (i, r) => { const m = /Median sentence length: ([\d.]+) words/i.exec(r); return `Độ dài câu trung vị của kịch bản: ${m ? m[1] + ' từ' : 'đạt yêu cầu'}.`; },
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

/** A storyboard issue: it points into the storyboard document (shots, assets, canvas...) or came from the storyboard checks. */
const SB_PATH = /^(shots\b|assets\b|canvas\b|end\b|audio\b|schema\b|approvals\b|project\b|title\b|style\b|regions\b|overlays\b)|^$/;
const isStoryboardIssue = (i) => !!i && (!!i.shot || (typeof i.path === 'string' && SB_PATH.test(i.path) && !i.chapter && !i.beat && !i.fact));

/** Vietnamese sentence for a validation issue. `detail` holds the server's English text when no builder knows the code. */
export function issueText(issue) {
  const raw = String(issue?.message || '');
  let code = issue?.code;
  if (!code || !BUILD[code]) { const g = GATES.find(([re]) => re.test(raw)); if (g) code = g[1]; }
  const fn = BUILD[code];
  if (fn) { try { return { text: fn(issue || {}, raw), detail: raw }; } catch { /* fall through */ } }
  if (isStoryboardIssue(issue)) return storyboardIssueText(issue);       // sbissues.js: by code, else by the shape of the message
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

// ---------------------------------------------------------------- licence of an image
/** Vietnamese reason why the licence gate refused an image (the server's `licence_reason`). */
export function licenceText(raw) {
  const s = String(raw || ''), name = (/licen[cs]e '(.*?)'/i.exec(s) || [])[1];
  const q = name ? ` "${name}"` : '';
  let text;
  if (/licence is missing/i.test(s)) text = 'Hình này không ghi giấy phép. Vẫn dùng được; hãy ghi nguồn khi đăng.';
  else if (/non-commercial/i.test(s)) text = `Giấy phép${q} không cho dùng thương mại. Vẫn nhập được; hãy tự cân nhắc khi đăng.`;
  else if (/no-derivatives/i.test(s)) text = `Giấy phép${q} cấm sửa đổi. Vẫn nhập được; hãy tự cân nhắc khi đăng.`;
  else if (/not public domain/i.test(s)) text = 'Tác phẩm này không thuộc phạm vi công cộng. Vẫn nhập được; hãy tự cân nhắc khi đăng.';
  else if (/allow-list/i.test(s)) text = `Giấy phép${q} chưa nằm trong danh sách ưu tiên (điều khoản hạn chế hoặc không rõ). Vẫn dùng được.`;
  else text = isVietnamese(s) ? s : 'Giấy phép của hình này có hạn chế. Vẫn dùng được.';
  return { text, detail: s !== text ? s : '' };
}

// ---------------------------------------------------------------- a failed preview clip (job of /preview)
/** Vietnamese reason why a preview job failed. `job.error` is the server's text. */
export function jobFailText(job) {
  const raw = String(job?.error || '');
  if (job?.error_code === 'render_failed') return { text: renderFailText(job), detail: '' };
  const d = describeHttp(422, { detail: raw });
  if (d.text === BY_STATUS[422] || !raw) return { text: 'Máy chủ không dựng được clip này.', detail: raw };
  return d;
}

/** The same sentence for the same place is shown once with a count (keys of one camera that cannot be told apart). */
export function groupIssues(list) {
  const seen = new Map(), out = [];
  for (const i of list) {
    const k = i.level + '|' + issueText(i).text;
    if (seen.has(k)) seen.get(k).n++; else { const g = { issue: i, n: 1 }; seen.set(k, g); out.push(g); }
  }
  return out;
}
