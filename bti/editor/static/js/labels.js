// ONE set of Vietnamese labels for the whole app.

/** Stage of a project (the `stage` field of /api/projects and of the pipeline). */
export const STAGE = { selected: 'Đã chọn tác phẩm', outlined: 'Đã duyệt dàn ý', script: 'Có kịch bản', voiced: 'Có giọng đọc', picked: 'Đã chọn hình', storyboard: 'Có storyboard', approved: 'Đã duyệt storyboard', rendered: 'Đã dựng xong' };
export const stageLabel = (s) => STAGE[s] || s || '';

/** Short state of a step of the stepper. */
export const STEP_STATE = { done: 'Xong', current: 'Hiện tại', available: 'Mở được', locked: 'Khóa', not_built: 'Chưa xây dựng', no_data: 'Không có dữ liệu', waiting: 'Chờ bước trước' };
/** What a stage package says about its step (`step.work`), shown beside the state when it needs attention. */
/** A step that already has output but waits on an earlier step (`state: 'waiting'`, `blocked_by`): what is going on, in plain words,
 * by [step][blocked_by]. The last key is the fallback for any other blocker. */
const WAIT_TEXT = {
  voice: { script: 'Lời dẫn đang được sửa và chưa được duyệt lại. Giọng đọc hiện có được làm từ bản đã duyệt trước. Duyệt lại lời dẫn để biết những câu nào cần đọc lại.' },
  picks: { script: 'Lời dẫn đang được sửa và chưa được duyệt lại. Các hình đã chọn gắn với bản lời dẫn đã duyệt trước. Duyệt lại lời dẫn để biết dòng nào cần chọn lại hình.' },
  edit: {
    script: 'Lời dẫn đang được sửa và chưa được duyệt lại. Storyboard hiện có được dựng từ bản đã duyệt trước. Duyệt lại lời dẫn, rồi làm lại giọng đọc và hình nếu cần, để biết phần nào của storyboard phải dựng lại.',
    voice: 'Giọng đọc chưa khớp với lời dẫn hiện tại. Storyboard hiện có được dựng từ giọng đọc cũ. Làm lại giọng đọc trước, rồi kiểm tra lại storyboard.',
    picks: 'Phần chọn hình chưa được duyệt lại. Storyboard hiện có được dựng từ các hình đã duyệt trước. Duyệt lại phần chọn hình, rồi kiểm tra lại storyboard.',
  },
  export: {
    script: 'Lời dẫn đang được sửa và chưa được duyệt lại. Video đã xuất được làm từ bản đã duyệt trước. Duyệt lại lời dẫn để biết có phải xuất lại không.',
    voice: 'Giọng đọc chưa khớp với lời dẫn hiện tại. Video đã xuất dùng giọng đọc cũ. Làm lại giọng đọc rồi xuất lại.',
    picks: 'Phần chọn hình chưa được duyệt lại. Video đã xuất dùng các hình đã duyệt trước. Duyệt lại rồi xuất lại.',
    edit: 'Storyboard đã đổi và chưa được duyệt lại. Video đã xuất được làm từ bản đã duyệt trước. Duyệt lại storyboard rồi xuất lại.',
  },
};
export const waitText = (stepId, blockedBy) => WAIT_TEXT[stepId]?.[blockedBy] || 'Một bước trước đang được sửa và chưa được duyệt lại. Kết quả hiện có được làm từ bản đã duyệt trước.';
export const OPEN_STEP = (label) => `Mở bước ${label}`;

export const STEP_WORK = { running: 'Đang chạy', stale: 'Cần làm lại' };

export const RIGHTS = { pd_likely: 'Có thể hết bản quyền', copyright_likely: 'Có thể còn bản quyền', unknown: 'Chưa rõ bản quyền' };
export const KIND = { chapter_per_artwork: 'mỗi chương một tác phẩm', fixed_spread: 'mỗi tác phẩm một đoạn trang cố định', short_entries: 'mục ngắn', themed_chapter: 'chương theo chủ đề' };
export const SHORT_BOOK = { payne_gae: 'Payne', hodge_aid: 'Hodge', hagen_wgps: 'Hagen', grovier_nws: 'Grovier', brookehitching_mad: 'Brooke-Hitching', dasal_artcurious: 'Dasal' };
export const shortBook = (id) => SHORT_BOOK[id] || id;
export const LOW_TRUST = 'bản dịch máy, không dùng làm nguồn sự kiện';

/** Messages for the validation codes of the script step. */
export const CODE = {
  chapter_missing: 'Thiếu chương', empty_chapter: 'Chương chưa có chữ', chapter_order: 'Chương xếp sai thứ tự', empty_beat: 'Dòng trống', markup_in_text: 'Có ký hiệu trong lời đọc', words_under: 'Quá ngắn (dưới 70% mục tiêu)',
  outline_stale: 'Dàn ý đã đổi sau khi duyệt', outline_not_approved: 'Dàn ý chưa duyệt', outline_missing: 'Chưa có dàn ý',
  words_off_target: 'Lệch mục tiêu quá 15%', chapter_off_budget: 'Chương lệch ngân sách quá 30%', beat_too_long: 'Dòng quá dài (trên 90 từ)',
  unknown_fact: 'Mã dữ kiện không có trong dàn ý', no_show: 'Dòng chưa có gợi ý hình', unknown_chapter: 'Chương không có trong dàn ý',
  spoken_chars: 'Dấu câu giọng đọc không ngắt được', length: 'Độ dài', sentence_profile: 'Nhịp câu', source_share: 'Phần nguồn đã dùng',
  overlap: 'Trùng với văn bản nguồn', no_thesis: 'Chưa có câu hỏi chính', no_chapters: 'Chưa có chương', duplicate_chapter: 'Trùng mã chương',
  chapter_no_title: 'Chương chưa có tên', chapter_no_budget: 'Chương chưa có ngân sách từ', duplicate_fact: 'Trùng mã dữ kiện',
  fact_no_source: 'Dữ kiện không dẫn đoạn nguồn', unknown_source_id: 'Mã đoạn nguồn không có trong tập sách', disputed_no_conflict: 'Dữ kiện tranh cãi chưa mô tả mâu thuẫn',
  fact_unused: 'Dữ kiện chưa chương nào dùng', no_hook_choice: 'Chưa chọn câu mở', budget_sum: 'Tổng ngân sách lệch mục tiêu',
};
export const LEVEL = { error: 'Lỗi', warning: 'Cảnh báo', info: 'Thông tin' };

// ---------------------------------------------------------------- storyboard: intents, eases, sources, enum values
/** What a shot is for (`intent`). The raw id stays available as a tooltip. */
export const INTENT = {
  establish: 'Giới thiệu bối cảnh', explore: 'Khám phá bức tranh', point_at: 'Chỉ vào một chi tiết', isolate: 'Tách riêng một phần', reveal: 'Hé lộ',
  compare: 'So sánh', explain_mechanism: 'Giải thích cách hoạt động', quote: 'Trích lời', context: 'Bối cảnh', quantify: 'Nêu con số', structure: 'Nêu cấu trúc', transition: 'Chuyển ý',
};
export const intentLabel = (v) => INTENT[v] || (v ? String(v).replace(/_/g, ' ') : '');

/** Who wrote an item of the storyboard (`source`). */
export const SOURCE = { import: 'nhập từ bản cũ', agent: 'đề xuất tự động', human: 'bạn sửa tay' };
export const sourceLabel = (v) => SOURCE[v || 'import'] || String(v);

/** Trust of the text taken from a book page (`text_source`): the library shows these. */
export const TEXT_SOURCE = { clean: 'đã làm sạch', layer: 'lớp chữ gốc của PDF', mixed: 'lẫn hai loại' };
export const textSourceLabel = (v) => TEXT_SOURCE[v] || String(v || '');

/** Words of the enum params of the technique registry. A few words mean different things in different params: PARAM_VALUE says so. */
export const EASE = { linear: 'Đều', in_quad: 'Chậm rồi nhanh (nhẹ)', out_quad: 'Nhanh rồi chậm (nhẹ)', in_cubic: 'Chậm rồi nhanh', out_cubic: 'Nhanh rồi chậm', inout_sine: 'Mượt hai đầu (nhẹ)', inout_cubic: 'Mượt hai đầu' };
export const VALUE = {
  ...EASE,
  log: 'Theo tỉ lệ (log)', upper_all: 'In hoa toàn bộ', upper: 'In hoa', as_is: 'Giữ nguyên', as_typed: 'Như đã gõ',
  right: 'Phải', left: 'Trái', top: 'Trên', bottom: 'Dưới',
  all: 'Tất cả', cross: 'Chữ thập', frame: 'Khung hình', cover: 'Phủ kín (cắt bớt)', stretch: 'Kéo giãn', contain: 'Vừa trong khung',
  none: 'Không', contrast: 'Tương phản', white: 'Trắng', sepia: 'Nâu cũ', grey: 'Xám', warm: 'Ấm',
  bottom_left: 'Góc dưới trái', bottom_right: 'Góc dưới phải', top_left: 'Góc trên trái', top_right: 'Góc trên phải',
  source: 'Ảnh gốc', procedural: 'Nền tự vẽ', image: 'Ảnh', auto: 'Tự chọn', base: 'Nền của shot',
  rect: 'Chữ nhật', circle: 'Tròn', ellipse: 'Elip', triangle: 'Tam giác', white_card: 'Thẻ trắng', blurred_image: 'Ảnh mờ',
  sans_bold: 'Không chân, đậm', bold: 'Đậm', serif: 'Có chân', serif_it: 'Có chân, nghiêng', reg: 'Thường',
  left_to_right: 'Từ trái sang phải', right_to_left: 'Từ phải sang trái', slow: 'Chậm dần', hold: 'Giữ nguyên', loop: 'Lặp lại',
  black: 'Đen', matte: 'Nền mờ tối', blur: 'Ảnh mờ', lightness: 'Theo độ sáng', cluster: 'Theo nhóm màu', hue: 'Theo sắc',
  clear: 'Xóa đi', keep: 'Giữ lại', slide: 'Trượt', dissolve: 'Hòa tan', cut: 'Cắt thẳng',
};
export const PARAM_VALUE = { connector_mode: { frame: 'Chỉ khung' }, space: { frame: 'Theo khung hình', image: 'Theo ảnh' }, origin_space: { frame: 'Theo khung hình', source: 'Theo ảnh gốc' }, anchor_fit: { matte: 'Nền mờ tối' }, background: { image: 'Ảnh' } };
/** Label of one enum value; `param` (the param name) picks a meaning where the same word is used in two ways. Unknown values show as they are. */
export function valueLabel(v, param) { return PARAM_VALUE[param]?.[v] || VALUE[v] || String(v ?? ''); }

// ---------------------------------------------------------------- the model list
/** Why the Antigravity command did not answer (the model entry then carries `agy: {ok: false, reason}`), in words; null when it answered. */
const AGY_WHY = { timeout: 'không trả lời kịp', config: 'chưa cài hoặc chưa cấu hình', auth: 'từ chối quyền truy cập' };
export const agyProblem = (models) => { const m = (models || []).find((x) => x.agy && x.agy.ok === false); return m ? (AGY_WHY[m.agy.reason] || 'không trả lời') : null; };

// ---------------------------------------------------------------- dropdowns built from a list (R3U-001)
export const NOT_IN_LIST = '(không có trong danh sách)';
export const UNSET = '— chưa chọn —';
/** The options of a dropdown built from a list, so that it ALWAYS shows the stored value.
 * A value the list does not know gets its own entry, first, marked NOT_IN_LIST; an empty value (when '' is not one of the
 * choices) gets a disabled UNSET entry. Returns { options: [{value, text, title, state, disabled}], selected }.
 * Pure: nothing is written anywhere; the stored value changes only when the owner picks something else. */
export function dropdownOptions(values, current, labelOf = String) {
  const list = (values || []).map((v) => ({ value: String(v), text: labelOf(v), title: String(v), state: 'ok' }));
  const empty = current === null || current === undefined || current === '';
  if (empty) {
    if (!list.some((o) => o.value === '')) list.unshift({ value: '', text: UNSET, title: '', state: 'unset', disabled: true });
    return { options: list, selected: '' };
  }
  const cur = String(current);
  if (!list.some((o) => o.value === cur)) list.unshift({ value: cur, text: `${labelOf(current)} ${NOT_IN_LIST}`, title: cur, state: 'foreign' });
  return { options: list, selected: cur };
}

// ---------------------------------------------------------------- the stages: voice (3), picks (4), draft (5), export (6)
export const VOICE_LABELS = {
  state: { none: 'Chưa tạo', running: 'Đang chạy', stale: 'Cần làm lại', done: 'Xong' },
  job: { queued: 'Đang chờ', waiting: 'Chờ máy rảnh', running: 'Đang chạy', done: 'Xong', error: 'Lỗi', cancelled: 'Đã hủy', interrupted: 'Bị gián đoạn' },
  reason: {
  never_built: 'Chưa tạo giọng đọc cho lời dẫn này.',
  narration_changed: 'Lời dẫn đã đổi sau lần đọc trước. Chỉ các câu đã đổi sẽ được đọc lại.',
  pronounce_changed: 'Bảng phát âm đã đổi sau lần đọc trước. Chỉ các câu có chữ đó sẽ được đọc lại.',
  reread: 'Bạn đã yêu cầu đọc lại một số câu bằng một lần đọc khác.',
  voice_changed: 'Cài đặt giọng đã đổi, nên phải đọc lại.',
  mix_settings_changed: 'Tốc độ hoặc nhạc nền đã đổi. Chỉ cần ghép lại, không đọc lại.',
  files_missing: 'Thiếu tệp âm thanh hoặc tệp thời gian. Bấm tạo lại.',
},
};
export const PICKS_LABELS = {
  flag: { rejected: 'Giấy phép bị hạn chế', unknown: 'Chưa rõ giấy phép', small: 'Ảnh nhỏ' },
  flagHelp: {
    rejected: 'Giấy phép của ảnh này hạn chế việc dùng lại. Vẫn dùng được; hãy tự cân nhắc khi đăng video.',
    unknown: 'Chưa rõ giấy phép của ảnh này. Vẫn dùng được; mô tả video sẽ ghi nguồn.',
    small: 'Ảnh dưới 1200 px ở cạnh ngắn, có thể bị mờ khi phóng to. Vẫn dùng được.',
  },
  role: { main: 'Cả bức tranh', detail: 'Chi tiết', context: 'Bối cảnh', compare: 'So sánh', document: 'Tài liệu', map: 'Bản đồ', video: 'Video' },
  tabs: { main: 'Tranh chính', search: 'Tìm kiếm', books: 'Sách', suggest: 'Gợi ý', video: 'Video', upload: 'Tải lên' },
  issue: {
    no_main: 'Chưa chọn tranh chính.', asset_file_missing: (i) => `Thiếu tệp ảnh của hình ${i.asset}.`,
    unknown_asset: (i) => `Dòng ${i.beat} dùng hình ${i.asset} không còn trong danh sách.`,
    unknown_region: (i) => `Dòng ${i.beat} dùng vùng "${i.region}" của hình ${i.asset}, vùng này không còn.`,
    beat_no_pick: (i) => `Dòng ${i.beat} chưa có hình: bản nháp sẽ dùng tranh chính ở đó.`,
    beat_unknown: (i) => `Có hình cho dòng ${i.beat} nhưng dòng này không còn trong lời dẫn.`,
    asset_flag: (i) => `Hình ${i.asset}: ${PICKS_LABELS.flag[i.flag] || i.flag}.`,
  },
  reason: { picks_edited: 'Chọn hình đã đổi sau khi duyệt.', narration_changed: 'Lời dẫn đã đổi sau khi duyệt hình.', narration_not_approved: 'Lời dẫn chưa được duyệt.' },
};
export const FLAG = PICKS_LABELS.flag;          // advisory flags of an image: rejected | unknown | small
export const flagLabel = (f) => FLAG[f] || '';
export const FLAG_HELP = PICKS_LABELS.flagHelp;
export const DRAFT_LABELS = {
  title: 'Bản nháp storyboard',
  intro: 'Agent đọc lời dẫn đã có giọng đọc và các hình bạn đã chọn, rồi dựng sẵn từng cảnh. Kết quả là một đề xuất: bạn xem và chấp nhận từng thay đổi, không có gì tự đổi.',
  voice: 'Giọng đọc',
  picks: 'Chọn hình',
  model: 'Mô hình',
  modelDefault: 'Mặc định',
  start: 'Dựng bản nháp',
  startAuto: 'Dựng tự động (không dùng agent)',
  cancel: 'Dừng',
  open: 'Mở đề xuất',
  running: 'Đang dựng bản nháp...',
  waiting: 'Đang chờ...',
  notReady: 'Chưa đủ dữ liệu: xong bước Giọng đọc và Chọn hình trước.',
  confirmReplace: 'Dự án đã có storyboard. Bản nháp mới chỉ là một đề xuất, không ghi đè gì cho đến khi bạn chấp nhận. Dựng bản nháp?',
  stale: 'Bản nháp này dựng từ giọng đọc hoặc danh sách hình đã đổi.',
  last: 'Lần dựng gần nhất',
  tampered: 'Lần dựng bị bỏ vì agent đã đổi tệp ngoài thư mục làm việc.',
  doneNote: 'Xong. Có %n cảnh.',
  doneSplit: 'Xong. Có %n cảnh: %c cảnh nội dung, %k thẻ.',
  issues: '%n mục còn dở, xem trong đề xuất.',
  loadingModels: 'Đang tải danh sách mô hình...',
  noModels: 'Chưa lấy được danh sách mô hình (agy chưa đăng nhập?). Dùng mô hình mặc định.',
  partState: { queued: 'chờ', waiting: 'chờ máy', running: 'đang chạy', done: 'xong', error: 'lỗi', cancelled: 'đã dừng', interrupted: 'bị ngắt' },
};
export const EXPORT_LABELS = {
  parts: { queued: 'Chờ', waiting: 'Chờ máy rảnh', running: 'Đang chạy', done: 'Xong', error: 'Lỗi', cancelled: 'Đã hủy', interrupted: 'Bị gián đoạn' },
  job: { queued: 'Đang chờ', waiting: 'Đang chờ máy rảnh', running: 'Đang xuất', done: 'Đã xong', error: 'Bị lỗi', cancelled: 'Đã hủy', interrupted: 'Bị gián đoạn vì máy chủ khởi động lại' },
  report: {
    video: 'Loại video', audio_length: 'Độ dài tiếng đọc (giây)', chapters_merged: 'Mục lục ngắn đã gộp (dưới 10 giây)', duration: 'Độ dài (giây)', frames: 'Số khung hình', audio: 'Âm thanh', loudness: 'Độ lớn tiếng (LUFS)',
    true_peak: 'Đỉnh âm lớn nhất (dB)', chapters: 'Số mục lục', size: 'Dung lượng',
  },
  reportHelp: {
    frames: 'phải bằng độ dài nhân 30', audio_length: 'phải khớp độ dài video (lệch tối đa 0,5 giây)', chapters_merged: 'chỉ gộp trong tệp mục lục và mô tả', loudness: 'mục tiêu khoảng -15', true_peak: 'nên dưới -1', chapters: 'từ 2 mục trở lên',
  },
  status: { ok: 'Đạt', warn: 'Xem lại', fail: 'Lỗi' },
  stale: { storyboard: 'Storyboard đã đổi sau lần xuất trước, nên video này không còn khớp.', audio: 'Giọng đọc đã đổi sau lần xuất trước, nên video này không còn khớp.', files: 'Một số tệp của lần xuất trước không còn nữa.' },
  files: { video: 'Video (MP4)', description: 'Mô tả video', chapters: 'Mục lục (chapters.txt)' },
};

// --- picks and clips
export const MOMENT_WHY = {
  chapter: (arg) => `Chương: "${arg || ''}"`,
  subtitle: (arg) => `Phụ đề: "${arg || ''}"`,
  replayed: (arg) => `Xem lại nhiều (${arg || ''})`,
};
export const momentWhy = (why) => {
  if (!why) return '';
  if (typeof why === 'string') return why;
  const fn = MOMENT_WHY[why.code];
  if (fn) return fn(why.title ?? why.text ?? why.value ?? why.arg ?? '');
  return why.code || '';
};

// --- dsources: new sources labels
export const SOURCE_LABELS = {
  commons: 'Wikimedia Commons',
  met: 'The Met',
  pexels: 'Pexels',
  pixabay: 'Pixabay',
  osm: 'OpenStreetMap (Bản đồ)',
};



// --- draft and edit (page): editing the storyboard by a typed instruction (promptedit.js, editlogic.js) and the model settings (settings.js)
export const EDIT_LABELS = {
  title: 'Sửa video bằng lời',
  placeholder: 'Bạn muốn sửa gì? Ví dụ: zoom chậm hơn vào chiếc gương.',
  send: 'Gửi',
  sendHint: 'Gửi yêu cầu (Ctrl+Enter)',
  emptyInstruction: 'Hãy gõ điều bạn muốn sửa.',
  tooLong: 'Yêu cầu dài quá, tối đa 2000 chữ.',
  cancel: 'Dừng',
  scopeLead: 'Sẽ sửa:',
  scopeShots: 'Cảnh',
  scopeChapter: 'Chương',
  scopeAll: 'Cả video',
  chapterHere: 'Chương tại đầu phát',
  noShotChosen: 'Chưa chọn cảnh nào.',
  multi: 'Chọn nhiều cảnh',
  multiHint: 'Bật lên, rồi bấm vào các cảnh trên thanh thời gian để thêm vào phần sẽ sửa.',
  multiOn: 'Bấm các cảnh trên thanh thời gian để thêm.',
  dropShot: (n) => `Bỏ cảnh ${n}`,
  modelLink: 'Mô hình',
  modelLinkHint: 'Mở Cài đặt để đổi mô hình cho từng việc.',
  noStoryboard: 'Dự án chưa có storyboard để sửa.',
  thread: 'Các lần sửa',
  threadEmpty: 'Chưa có lần sửa nào. Gõ điều bạn muốn đổi ở ô trên.',
  clear: 'Xóa lịch sử',
  clearAsk: 'Xóa danh sách các lần sửa? Video không bị đổi, nhưng các nút Hoàn tác của những lần này sẽ mất.',
  clearOk: 'Xóa lịch sử',
  cleared: 'Đã xóa lịch sử các lần sửa.',
  you: 'Bạn',
  status: {
    running: 'Đang làm', applied: 'Đã áp dụng', no_change: 'Không đổi', needs_choice: 'Cần bạn chọn',
    failed: 'Không làm được', cancelled: 'Đã hủy', undone: 'Đã hoàn tác', old: 'Đề xuất cũ',
  },
  path: { fast: 'sửa nhanh', deep: 'sửa sâu' },
  pathEscalated: 'chuyển sang sửa sâu',
  took: (s) => `mất ${s}`,
  secs: (n) => `${String(n).replace('.', ',')} giây`,
  minSecs: (m, s) => `${m} phút ${s} giây`,
  running: 'Đang sửa video...',
  progress: {
    prepare: 'Đang chuẩn bị', think: 'Đang nghĩ...', check: 'Đang kiểm tra...', deep: 'Chuyển sang sửa sâu...',
    agent: 'Đang làm việc', agentStep: (n) => `Đang làm việc (bước ${n})`, write: 'Đang ghi lại...', queued: 'Đang chờ...',
  },
  applied: 'Đã sửa xong và đưa vào storyboard.',
  noChange: 'Không có gì thay đổi.',
  noChangeHelp: 'Hãy nói rõ hơn, hoặc chọn phần khác để sửa.',
  cancelled: 'Đã dừng, không có gì thay đổi.',
  undone: 'Lần sửa này đã được hoàn tác.',
  old: 'Lần sửa từ bản trước, nay không dùng nữa.',
  failedGeneric: 'Lần sửa này không làm xong. Thử lại, hoặc nói rõ hơn.',
  quota: {
    lead: 'Mô hình đã dùng hết hạn mức.',
    opensAt: (when) => `Mở lại ${when}.`,
    opensAfter: (words) => `Mở lại sau khoảng ${words}.`,
    unknown: 'Chưa rõ khi nào mở lại.',
    other: 'Bạn có thể chọn mô hình khác.',
    choose: 'Chọn mô hình khác',
    at: (hm) => `lúc ${hm}`,
    atDate: (hm, date) => `lúc ${hm} ngày ${date}`,
    minutes: (n) => `${n} phút`, hours: (n) => `${n} giờ`, days: (n) => `${n} ngày`,
  },
  change: { changed: 'Đổi', added: 'Thêm', removed: 'Xóa' },
  shotAt: (n, t) => `Cảnh ${n} · ${t}`,
  before: 'Trước',
  after: 'Sau',
  noFrame: 'Không có hình',
  frameFailed: 'Không dựng được hình',
  changesNone: 'Lần sửa này không ghi lại thay đổi nào.',
  preview: 'Xem thử',
  previewHint: 'Dựng một đoạn ngắn ở chỗ vừa sửa để xem.',
  previewFail: 'Không dựng được đoạn xem thử: ',
  undo: 'Hoàn tác',
  undoHint: 'Đưa các cảnh này về như trước lần sửa.',
  undoNone: 'Không còn bản cũ để hoàn tác (chỉ giữ 20 lần gần nhất).',
  undoDone: 'Đã hoàn tác lần sửa.',
  undoConflictLead: (list) => `Sau lần sửa này, bạn đã đổi ${list}. Hoàn tác sẽ bỏ cả các thay đổi đó.`,
  undoConflictTitle: 'Hoàn tác sẽ bỏ sửa đổi của bạn',
  undoForce: 'Vẫn hoàn tác',
  retry: 'Thử lại',
  details: 'chi tiết',
  choiceLead: (list) => `Trong lúc đó bạn cũng sửa ${list}.`,
  choiceLeadAny: 'Trong lúc đó bạn cũng sửa các cảnh này.',
  choiceLeadList: 'Trong lúc đó bạn cũng thêm, bớt hoặc dời cảnh trong phần này.',
  choiceOverwrite: 'Dùng bản của agent',
  choiceOverwriteHelp: 'Các sửa tay của bạn từ lúc đó sẽ mất.',
  choiceDiscard: 'Giữ bản của bạn',
  choiceDiscardHelp: 'Bỏ lần sửa này, không đổi gì.',
  resolved: 'Đã chọn xong.',
  tookIn: 'Đã cập nhật storyboard theo lần sửa vừa xong.',
  tookInMerged: 'Đã ghép lần sửa vừa xong với các sửa chưa lưu của bạn. Hoàn tác không quay lại trước lúc ghép.',
  tookInFail: 'Không tải được storyboard mới: ',
  sendFail: 'Không gửi được: ',
  cancelFail: 'Không dừng được: ',
  actionFail: 'Không làm được: ',
  stale: 'Storyboard đã đổi ở nơi khác. Tải lại trang rồi gửi lại.',
  unit: { shot: 'cảnh' },
};
export const SETTINGS_LABELS = {
  open: 'Cài đặt',
  openHint: 'Cài đặt: mô hình cho từng việc',
  title: 'Mô hình cho từng việc',
  intro: 'Mỗi việc dùng một mô hình. Đổi ở đây thì lần chạy sau dùng mô hình mới.',
  all: 'Dùng một mô hình cho tất cả',
  allPick: 'Chọn mô hình...',
  allApply: 'Áp dụng cho tất cả',
  save: 'Lưu',
  saving: 'Đang lưu...',
  saved: 'Đã lưu cài đặt.',
  loading: 'Đang tải...',
  loadFail: 'Không đọc được cài đặt: ',
  saveFail: 'Không lưu được: ',
  noChange: 'Chưa đổi gì.',
  fromSetting: 'đã chỉnh',
  fromDefault: 'mặc định',
  deepNote: 'Việc này cần mô hình chạy qua agy.',
  notInList: 'Mô hình này không còn trong danh sách.',
  noModels: 'Chưa lấy được danh sách mô hình.',
  agyDown: 'Chưa lấy được danh sách mô hình từ agy.',
  role: {
    'script.outline': 'Dàn ý kịch bản', 'script.narration': 'Lời dẫn kịch bản', draft: 'Dựng storyboard',
    'edit.fast': 'Sửa nhanh bằng lời', 'edit.deep': 'Sửa sâu bằng lời (agent)', picks: 'Chọn hình (để dành)',
  },
};
