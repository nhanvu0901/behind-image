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

// ---- grovint: the three trust levels of a source (normal, restored, low)
/** The words for the level of a source. Normal shows no tag in the lists (as before); the words are for tooltips. */
export const TRUST_LEVEL = { normal: 'Tin cậy', restored: 'Bản khôi phục', low: 'Tin cậy thấp' };
/** The level of a source from the `trust` field of the server: nothing means normal (an old file), a word that is none of the three counts as low. */
export const trustOf = (v) => (v === undefined || v === null || v === '' ? 'normal' : Object.prototype.hasOwnProperty.call(TRUST_LEVEL, v) ? v : 'low');
export const trustLabel = (v) => TRUST_LEVEL[trustOf(v)];
/** What a restored source is and what it does not promise (the server sends the same words as `trust_note`). */
export const RESTORED_NOTE = 'Bản khôi phục từ bản dịch máy, đã rà soát: dùng được cho ý và mô tả; số liệu, năm và trích dẫn phải có nguồn khác xác nhận.';
export const trustNote = (level, fromServer) => fromServer || (level === 'restored' ? RESTORED_NOTE : level === 'low' ? LOW_TRUST : '');
export const RESTORED_TEXT = 'Dấu […] là chỗ bản khôi phục chưa đọc ra được. Chú thích hình không được đưa vào.';
/** Said wherever no source of the painting is a normal one (every source is restored and/or low). */
export const NO_NORMAL_SOURCE = 'Chưa có nguồn tin cậy đầy đủ cho tác phẩm này.';
/** True when there is at least one source and none is a normal one; `levels` are `trust` values. */
export const noNormalSource = (levels) => levels.length > 0 && levels.every((v) => trustOf(v) !== 'normal');

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
export const TEXT_SOURCE = { clean: 'đã làm sạch', layer: 'lớp chữ gốc của PDF', mixed: 'lẫn hai loại', restored: 'bản khôi phục' };
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
  path: { fast: 'sửa nhanh', deep: 'sửa sâu', agent: 'agent chọn hình' },
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
// --- d-camera: camera frames on the source view ("Ảnh gốc") and the selected key in the form (preview.js, formui.js)
export const CAMERA_LABELS = {
  undo: 'Kéo khung camera',
  pick: 'Camera:',
  pickHint: 'Camera đang vẽ trên ảnh gốc (kỹ thuật này có nhiều camera, mỗi camera nhìn một ảnh)',
  key: (i, zoom) => `K${i + 1}  zoom ${zoom}`,
  keyHint: 'Kéo trong khung để dời tâm, kéo góc để đổi zoom. Bấm vào khung để chọn khóa.',
  selected: 'đang chọn trên ảnh',
  needSource: 'Bật "Ảnh gốc" để kéo khung camera của kỹ thuật này.',
};
// --- idapply: the selector "Kiểu mở đầu và mốc chương" (step 5) and its line in step 6 (identitylogic.js, identitypick.js, views/export.js)
export const IDENTITY_LABELS = {
  title: 'Kiểu mở đầu và mốc chương',
  titleHint: 'Cách video mở đầu, lúc hiện tên kênh và các mốc chương. Đổi xong video đổi ngay; có nút Hoàn tác.',
  old: 'Kiểu cũ',
  oldNote: 'Video đang dùng kiểu cũ (thẻ tiêu đề và thẻ chương). Chọn một kiểu để đổi.',
  loading: 'Đang tải...',
  busy: 'Đang đổi kiểu...',
  done: (label, n) => (n ? `Đã đổi sang kiểu "${label}" (${n} chỗ).` : `Video đã ở kiểu "${label}", không có gì phải đổi.`),
  undo: 'Hoàn tác',
  undoHint: 'Trả storyboard về như trước khi đổi kiểu.',
  undone: 'Đã trả về như trước khi đổi kiểu.',
  undoFail: 'Không hoàn tác được: ',
  chooseFail: 'Không đổi được kiểu: ',
  loadFail: 'Không đọc được kiểu mở đầu: ',
  tookIn: 'Đã đổi kiểu mở đầu và mốc chương.',
  tookInMerged: 'Đã đổi kiểu và ghép với các sửa chưa lưu của bạn. Hoàn tác không quay lại trước lúc ghép.',
  tookInFail: 'Không tải được storyboard mới: ',
  skippedLead: 'Chưa đổi được:',
  close: 'Đóng',
  // what a skipped item was, and why (reason codes of PUT /identity)
  what: { open: 'phần mở đầu', label: 'nhãn tên tác phẩm', brand: 'đoạn hiện tên kênh', mark: 'mốc chương', opening: 'phần mở đầu' },
  skip: {
    locked: (what, n) => (n ? `Cảnh ${n} (${what}) đang khóa nên giữ nguyên.` : `Có cảnh đang khóa nên ${what} giữ nguyên.`),
    no_title_slot: () => 'Video chưa có thẻ tiêu đề nên chưa có đoạn hiện tên kênh.',
    extra_title: (what, n) => `Cảnh ${n || '?'} là thẻ tiêu đề thứ hai nên giữ nguyên.`,
    no_title: (what, n) => `Cảnh ${n || '?'} chưa có chữ tiêu đề nên giữ nguyên.`,
    too_short: (what, n) => `Cảnh ${n || '?'} ngắn quá (dưới 1,5 giây) cho kiểu mới nên giữ nguyên.`,
    no_room: (what) => `Không có cảnh nào đủ dài (3 giây) cho ${what}.`,
    no_time: (what, n) => `Không đọc được thời điểm của cảnh ${n || '?'}.`,
    other: (what, n) => `Một chỗ (${what}) chưa đổi được.`,
  },
  export: { label: 'Kiểu mở đầu và mốc chương', old: 'Kiểu cũ (chưa chọn kiểu mới, đổi ở bước Dựng hình)', none: 'Chưa có' },
};
// --- agentpick: the agent select of steps 2 and 5, the quota message and the settings box's default agent (agentlogic.js, agentpick.js, settings.js)
export const AGENT_LABELS = {
  label: 'Agent',
  titleHint: 'Agent làm việc ở bước này của dự án này. Đổi xong có hiệu lực ngay, không cần xác nhận.',
  loading: 'Đang tải...',
  sourceStep: 'Riêng cho bước này',
  sourceProject: 'Theo dự án',
  sourceDefault: 'Theo mặc định',
  whole: 'Dùng cho cả dự án',
  wholeHint: 'Mọi bước của dự án này dùng agent này, không cần chọn lại ở từng bước.',
  wholeDone: (label) => `${label} là agent của cả dự án. Các bước sau dùng agent này, không cần chọn lại.`,
  unavailableOption: (label) => `${label} (chưa dùng được)`,
  outside: (label) => `${label} (theo cài đặt nâng cao)`,
  unavailable: (label, reason) => `${label} chưa dùng được${reason ? ': ' + reason : '.'}`,
  loadFail: 'Không đọc được agent của dự án: ',
  changeFail: 'Không đổi được agent: ',
  noneYet: 'Chưa biết agent nào sẽ chạy.',
  runWith: (label) => `Agent: ${label}`,
  doneBy: (label) => `Agent: ${label}.`,
  // the quota message (contract section 6): one sentence naming the agent and the time, one button
  quota: {
    sentence: (label, when) => `${label} đã hết hạn mức, ${when}`,
    after: (span) => `mở lại sau khoảng ${span}.`,
    atTime: (hm) => `mở lại lúc ${hm}.`,
    atDate: (hm, date) => `mở lại lúc ${hm} ngày ${date}.`,
    reopened: 'có thể đã mở lại, bạn thử lại được.',
    unknown: 'chưa rõ khi nào mở lại.',
    switchTo: (label) => `Chuyển sang ${label} và chạy lại`,
    switching: 'Đang chuyển...',
    otherDown: (label, reason) => `${label} cũng chưa dùng được${reason ? ': ' + reason : '.'}`,
    noOther: 'Chưa có agent khác để chuyển sang.',
    fail: 'Không chuyển được agent: ',
    rerunFail: 'Đã chuyển agent nhưng chưa chạy lại được: ',
    scriptTitle: 'Agent đã hết hạn mức',
    scriptKept: 'Phần đã viết xong được giữ lại. Hệ thống không tự đổi agent: bạn bấm nút dưới đây nếu muốn.',
    minutes: (n) => `${n} phút`, hours: (n) => `${n} giờ`, days: (n) => `${n} ngày`,
  },
  settings: {
    title: 'Cài đặt',
    defaultTitle: 'Agent mặc định cho dự án mới',
    defaultHint: 'Dự án chưa chọn agent thì dùng agent này. Mỗi dự án vẫn đổi được agent của mình ở từng bước.',
    saved: 'Đã lưu agent mặc định.',
    saveFail: 'Không lưu được agent mặc định: ',
    advanced: 'Nâng cao',
    advancedHint: 'Chỉ dùng khi dự án và mặc định đều chưa chọn agent.',
    rolesTitle: 'Mô hình cho từng việc',
  },
  // worker followups: who wrote a proposal (the list of proposals, agentlogic.js authorLabel)
  author: { you: 'Bạn', auto: 'Dựng tự động', agent: (what) => `Agent ${what}` },
};

/* worker c3picks: "Để agent chọn hình" on the pictures page (views/picks_auto.js, views/picks_logic.js). The failures of the job are in errmsg.js. */
export const PICKS_AUTO_LABELS = {
  title: 'Agent chọn hình',
  intro: 'Agent đọc lời dẫn, nhìn bức tranh chính rồi đề xuất hình cho từng dòng. Bạn chỉ cần sửa và duyệt: agent không bao giờ tự duyệt và không dùng dịch vụ trả tiền.',
  button: 'Để agent chọn hình',
  again: 'Chọn lại phần còn thiếu',
  cancel: 'Dừng',
  starting: 'Đang bắt đầu...',
  working: 'Agent đang chọn hình.',
  waiting: 'Đang chờ máy rảnh...',
  disabled: { running: 'Agent đang làm việc.', narration: 'Cần duyệt lời dẫn trước.', main: 'Chọn tranh chính trước.', agent: 'Agent đang chọn chưa dùng được.' },
  confirmRedo: { title: 'Chọn lại tất cả?', message: 'Mọi dòng đã có hình hoặc chọn hình đã được duyệt. Agent sẽ chọn lại tất cả và thay hình hiện có (hoàn tác được). Chọn hình phải duyệt lại sau đó.', ok: 'Chọn lại tất cả' },
  confirmApproved: { title: 'Chọn hình đã được duyệt', message: 'Agent sẽ ghi vào các dòng còn thiếu và chọn hình phải duyệt lại sau đó.', ok: 'Tiếp tục' },
  lineWhy: (text) => `Agent: ${text}`,
  lineWhyTitle: 'Lý do agent đưa ra cho dòng này. Bạn sửa hình hoặc ghi chú thì dòng này không còn là của agent.',
  detail: { pictures: (n) => `${n} hình mới`, regions: (n) => `${n} vùng chi tiết`, clips: (n) => `${n} clip`, kept: (n) => `${n} đoạn dùng lại hình trước`, others: (n) => `${n} đoạn bạn đã chọn trong lúc đó, agent không đụng tới` },
  withoutTitle: (n) => `${n} đoạn chưa có hình phù hợp`,
  withoutLine: (no, why) => `Đoạn ${no}: ${why}`,
  missingTitle: 'Hình agent chưa tìm được',
  stopped: { time: 'Hết thời gian của lần chạy này; bấm "Chọn lại phần còn thiếu" để làm tiếp.', cancelled: 'Đã dừng.' },
  cancelled: 'Đã dừng. Phần đã làm xong được giữ lại; bấm "Để agent chọn hình" để làm tiếp.',
  failed: (text) => `Agent chưa chọn xong: ${text}`,
  startFail: 'Không bắt đầu được: ',
  cancelFail: 'Không dừng được: ',
  limits: (l) => `Mỗi lượt của agent tối đa ${l.minutes} phút và ${l.steps} bước.`,
};

// ---- compbase: the words of the choices of TIME-01, TREE-01 and STATE-01 (the words of their row fields are added after ITEM_FIELD, below)
Object.assign(VALUE, { up: 'Phía trên', down: 'Phía dưới', descent: 'Con cháu (từ cha mẹ xuống con)', marriage: 'Hôn nhân', link: 'Quan hệ khác', a: 'Hình a (thứ nhất)', b: 'Hình b (thứ hai)' });

// ---- mapbuild: rows of the list editor (parameter type `items`, formui.js) and the words of MAP-01's choices
Object.assign(VALUE, {
  blue_grey: 'Xanh xám', fit: 'Vừa các địa điểm', manual: 'Tự đặt', curve: 'Đường cong', straight: 'Thẳng', dot: 'Chấm chạy',
  n: 'Bắc', ne: 'Đông bắc', e: 'Đông', se: 'Đông nam', s: 'Nam', sw: 'Tây nam', w: 'Tây', nw: 'Tây bắc',
});
export const ITEMS_UI = {
  add: '+ Thêm mục', remove: 'Xóa', up: 'Lên', down: 'Xuống', empty: 'Chưa có mục nào.', row: (n, name) => `Mục ${n}${name ? ': ' + name : ''}`,
  atSeconds: 'giây', atWord: 'từ', atHere: '= đầu phát', atHereTitle: 'Gắn vào từ tại đầu phát', atUnit: 'giây kể từ đầu phần này',
  minTitle: (n) => `Cần ít nhất ${n} mục`, maxTitle: (n) => `Tối đa ${n} mục`, yes: 'có', lonlatHint: 'kinh độ, vĩ độ',
};
export const ITEM_FIELD = {
  id: 'Mã', name: 'Tên', lonlat: 'Kinh độ, vĩ độ', at: 'Thời điểm', label_side: 'Phía đặt nhãn', from: 'Từ', to: 'Đến', via: 'Điểm uốn',
  shape: 'Dạng đường', draw_s: 'Thời gian vẽ', head: 'Đầu chạy',
};
// compbase: the fields of the rows of TIME-01 (date, label, side, at, accent) and TREE-01 (id, name, sub, row, col, at, strong; from, to, kind, label, at)
Object.assign(ITEM_FIELD, { date: 'Năm', label: 'Chữ ghi', side: 'Phía', accent: 'Nhấn mạnh', sub: 'Dòng nhỏ', row: 'Hàng (-1 là tự xếp)', col: 'Cột (-1 là tự xếp)', strong: 'Nổi bật', kind: 'Loại quan hệ' });
// A field name that means one thing in one list and another in a second list gets its word from ITEM_FIELD_OF (keyed by the name of the list param), not from ITEM_FIELD.
export const ITEM_FIELD_OF = {};
export const itemFieldLabel = (name, list) => ITEM_FIELD_OF[list]?.[name] || ITEM_FIELD[name] || name;

// ---- compover: words of KEY-01 (labels), NUM-01 (rows of figures) and DOC-01 (lit lines): the choices and the fields of their rows
Object.assign(VALUE, { italic: 'Nghiêng', regular: 'Thường', caps: 'Chữ hoa nhỏ', hairline: 'Nét mảnh' });
Object.assign(PARAM_VALUE, { leader: { none: 'Không có nét nối', hairline: 'Nét mảnh cho mọi nhãn', auto: 'Chỉ khi nhãn bị đẩy xa chi tiết' } });
Object.assign(ITEM_FIELD, {
  text: 'Chữ', ref: 'Chi tiết của tranh', style: 'Kiểu chữ', value: 'Con số', units: 'Đơn vị', count: 'Số chấm',
  box: 'Khung trong ảnh gốc', hold_s: 'Giữ sáng (giây)',
});
// `side` and `label` are also fields of TIME-01 ("Phía", "Chữ ghi"): here they mean the side of the detail where the text goes, and the small caption over a figure
Object.assign(ITEM_FIELD_OF, { labels: { side: 'Phía đặt chữ' }, rows: { label: 'Nhãn nhỏ' } });

// ---- worker c5cli: the switch "Cho agent tự chạy dự án này" (autologic.js, autoswitch.js). The owner decides which gates an agent may approve in one project;
// spending money is never an agent's, so there is no box for it, only the line that says so.
export const AUTO_LABELS = {
  title: 'Cho agent tự chạy dự án này',
  button: { off: 'Agent tự chạy: tắt', on: 'Agent tự chạy: bật' },
  buttonTitle: { off: 'Cho phép agent trong terminal tự duyệt một số cổng của dự án này', on: 'Agent trong terminal đang được tự duyệt một số cổng của dự án này' },
  switchLabel: 'Cho agent tự chạy dự án này',
  gatesTitle: 'Agent được tự duyệt',
  gate: { outline: 'Duyệt dàn ý', narration: 'Duyệt lời dẫn', picks: 'Duyệt chọn hình', storyboard: 'Duyệt storyboard' },
  gateShort: { outline: 'dàn ý', narration: 'lời dẫn', picks: 'chọn hình', storyboard: 'storyboard' },
  summary: { off: 'Tắt: mọi cổng do bạn duyệt trên trang.', on: (names) => `Bật: agent được tự duyệt ${names.join(', ')}.`, onNone: 'Bật nhưng chưa cho cổng nào: mọi cổng vẫn do bạn duyệt.' },
  hint: 'Các ô chỉ có tác dụng khi công tắc đang bật.',
  money: 'Việc tốn tiền luôn cần bạn.',
  loading: 'Đang tải...',
  saved: 'Đã lưu.',
  saveFail: 'Không lưu được: ',
  loadFail: 'Không đọc được cài đặt tự chạy: ',
};

// ---- c2box: the prompt box on typed operations (step 5 "Sửa video bằng lời", step 4 "Sửa chọn hình bằng lời") and the list of changes.
// A turn that was applied shows the sentences of its batch (written by the server, in Vietnamese); a request the fast path cannot do says why
// and offers the slower way (step 5) or the search by hand (step 4).
export const BOX_LABELS = {
  status: { escalate: 'Cần làm kỹ hơn' },
  escalate: 'Yêu cầu này cần agent làm kỹ hơn.',
  slow: {
    button: 'Làm kỹ hơn',
    hint: 'Agent làm việc từng bước và nhìn kỹ tranh. Việc này mất vài phút.',
    takes: 'Việc này sẽ mất vài phút.',
    limits: (minutes, repairs) => `Agent tự dừng sau tối đa ${minutes} phút và chỉ được làm lại tối đa ${repairs} lần. Bạn bấm Dừng lúc nào cũng được.`,
  },
  sentencesLead: 'Đã đổi:',
  lines: { more: (n) => `và ${n} thay đổi khác` },
  pictures: {
    title: 'Sửa chọn hình bằng lời',
    placeholder: 'Bạn muốn đổi gì? Ví dụ: dòng này chỉ cho xem khuôn mặt rồi cả bức tranh.',
    send: 'Gửi',
    scopeLead: 'Sẽ sửa:',
    scopeBeats: 'Dòng',
    scopeChapter: 'Chương',
    scopeAll: 'Cả video',
    noLineChosen: 'Chưa chọn dòng nào.',
    chapterHere: 'Chưa có chương cho dòng đang chọn.',
    multi: 'Chọn nhiều dòng',
    multiHint: 'Bật lên, rồi bấm vào các dòng ở cột bên trái để thêm vào phần sẽ sửa.',
    multiOn: 'Bấm các dòng ở cột bên trái để thêm.',
    dropLine: (n) => `Bỏ dòng ${n}`,
    lineAt: (n) => `Dòng ${n}`,
    linesWords: (n, list) => (n === 1 ? `Dòng ${list} đang chọn` : `${n} dòng đang chọn (${list})`),
    noNarration: 'Dự án chưa có lời dẫn để chọn hình.',
    thread: 'Các lần sửa',
    threadEmpty: 'Chưa có lần sửa nào. Gõ điều bạn muốn đổi ở ô trên.',
    applied: 'Đã sửa xong và đưa vào chọn hình.',
    undoHint: 'Đưa các dòng này về như trước lần sửa.',
    escalate: 'Việc này cần một hình mà dự án chưa có. Bạn có thể để agent chọn hình tìm và chọn cho các dòng này, hoặc tự tìm hình bằng tay.',
    escalateButton: 'Tìm hình bằng tay',
    // worker join2: the card of a request that needs a new picture hands the same lines to the pictures agent ("Để agent chọn hình")
    agentButton: 'Để agent chọn hình',
    agentHint: 'Agent tìm hình ở các nguồn miễn phí, nhìn kỹ rồi chọn cho các dòng này. Việc này mất vài phút.',
    agentTakes: 'Agent đang chọn hình cho các dòng này. Việc này mất vài phút; bạn bấm Dừng lúc nào cũng được.',
    agentDone: 'Agent đã chọn hình cho các dòng này.',
    agentUndoHint: 'Muốn đưa về như trước, dùng "Lịch sử thay đổi" bên dưới: mỗi lần agent ghi là một mục.',
    agentWithout: (nums) => `Chưa có hình phù hợp cho ${nums.length === 1 ? 'dòng' : 'các dòng'} ${nums.join(', ')}. Bạn có thể tìm hình bằng tay cho ${nums.length === 1 ? 'dòng' : 'các dòng'} này.`,
    agentUnusable: 'Agent đang chọn chưa dùng được. Chọn agent khác ở trên, hoặc tìm hình bằng tay.',
    tookIn: 'Đã cập nhật chọn hình theo lần sửa vừa xong.',
    tookInFail: 'Không tải được chọn hình mới: ',
    stale: 'Chọn hình đã đổi ở nơi khác. Tải lại trang rồi gửi lại.',
    dirty: 'Chọn hình đang có chỗ chưa lưu. Chờ lưu xong rồi gửi lại.',
    unit: { line: 'dòng' },
  },
  changes: {
    title: 'Lịch sử thay đổi',
    empty: 'Chưa có thay đổi nào.',
    you: 'Bạn',
    tool: 'Công cụ ngoài',
    agent: 'Agent',
    undo: 'Hoàn tác',
    undoHint: 'Đưa phần này về như trước lần sửa đó.',
    undone: 'đã hoàn tác',
    undoOf: 'Hoàn tác một lần sửa',
    undoDone: 'Đã hoàn tác.',
    loadFail: 'Không tải được lịch sử thay đổi: ',
    note: (t) => `Yêu cầu: ${t}`,
    today: (hm) => hm,
    other: (hm, date) => `${hm} ngày ${date}`,
  },
};

/* worker c6auto: "Chạy tự động" (bti/auto_run/): the button next to the switch "Agent tự chạy", the progress line, and the one sentence that says where a run
   stopped and why (the server writes that sentence, bti/auto_run/reasons.py; the words here are the page's own and the fallbacks for a record without one). */
export const AUTORUN_LABELS = {
  button: 'Chạy tự động',
  buttonTitle: {
    ready: 'Để ứng dụng tự đi tiếp từ chỗ dự án đang đứng đến khi xuất xong video, chỉ trong phạm vi bạn đã cho phép. Gặp việc cần bạn thì dừng lại và nói rõ.',
    off: 'Hãy bật "Agent tự chạy" trước: chạy tự động chỉ đi qua các cổng bạn cho phép ở đó.',
    running: 'Đang chạy tự động. Bấm "Dừng" nếu muốn dừng.',
  },
  starting: 'Đang bắt đầu chạy tự động...',
  running: (stepLabel, n, of) => (stepLabel ? `Đang chạy tự động: ${stepLabel}${n && of ? ` (${n}/${of})` : ''}` : 'Đang chạy tự động...'),
  stop: 'Dừng',
  stopping: 'Đang dừng...',
  close: 'Đóng',
  link: (stepLabel) => `Mở bước "${stepLabel}"`,
  failed: (action) => `Việc "${action}" không làm được: `,
  startFail: 'Chưa bắt đầu chạy tự động được: ',
  stopFail: 'Chưa dừng được: ',
  heading: { done: 'Xong', needs_owner: 'Cần bạn', nothing_to_do: 'Chưa có việc để chạy', failed: 'Bị lỗi', cancelled: 'Đã dừng', limit: 'Đã dừng vì hết giới hạn', interrupted: 'Đã dừng' },
  fallback: {
    done: 'Chạy tự động đã xong.',
    needs_owner: 'Chạy tự động dừng lại vì cần bạn. Hãy xem dự án rồi bấm "Chạy tự động" lại.',
    nothing_to_do: 'Chạy tự động chưa có việc nào để làm lúc này.',
    failed: 'Chạy tự động bị lỗi. Hãy xem dự án rồi bấm "Chạy tự động" lại.',
    cancelled: 'Đã dừng chạy tự động. Bấm "Chạy tự động" để làm tiếp; phần đã xong được giữ lại.',
    limit: 'Chạy tự động đã dừng vì hết giới hạn. Bấm "Chạy tự động" để làm tiếp.',
    interrupted: 'Máy chủ đã dừng khi đang chạy tự động. Bấm "Chạy tự động" để làm tiếp; phần đã xong được giữ lại.',
  },
};

// ---- c4pages: the two simple pages, step 4 "Chọn hình" and step 5 "Dựng hình" (views/picks_rows.js, sbsimple.js and their *logic.js modules). The hand tools keep their own words.
// SHOT_WORDS: the parts of the one plain sentence of a shot (shotsentence.js). The registry's Vietnamese name of a technique (`label_vi`) is the fallback of every
// entry; a short phrase here only makes it read as "what happens". No id, no file name and no parameter name is ever put into a sentence.
export const SHOT_WORDS = {
  unknown: 'Một cảnh',
  joiner: ' · ',
  whole: 'cả bức tranh',
  painting: 'bức tranh',
  detail: 'một chi tiết của tranh',
  other: (title) => (title ? `ảnh “${title}”` : 'một hình khác'),
  clip: (title, sec) => `clip${title ? ` “${title}”` : ''}${sec ? `, ${sec} giây` : ''}`,
  quoted: (label) => `“${label}”`,
  andMore: (n) => `và ${n} lớp khác`,
  moreImages: (n) => `và ${n} ảnh khác`,
  morePlaces: (n) => `và ${n} nơi khác`,
  twoOf: (a, b) => `${a} và ${b}`,
  several: (n) => `${n} ảnh`,
  // base techniques of the camera family and the held picture: { lead, use, prep?, otherwise?, tail? }. use: 'focus' (the region the camera ends on, else the picture),
  // 'target' (the picture as it is in the slot), 'whole' (always the whole painting).
  camera: {
    'CAM-01': { lead: 'Zoom vào', use: 'focus' },
    'CAM-03': { lead: 'Kéo ra, thấy', use: 'whole' },
    'CAM-04': { lead: 'Lia lên', use: 'focus' },
    'CAM-05': { lead: 'Zoom kèm dịch', use: 'focus', prep: 'tới', otherwise: 'trên' },
    'CAM-06': { lead: 'Giữ yên', use: 'target', tail: ', hiện nhãn' },
    'STATIC-01': { lead: 'Giữ yên', use: 'target' },
    'X-LAY-01': { lead: 'Ảnh tĩnh:', use: 'target' },
  },
  // what an explainer is called in the list ("Trục thời gian: 6 mốc"); the others use `label_vi`
  names: {
    'MAP-01': 'Bản đồ', 'STATIC-06': 'Bản đồ và tuyến', 'TIME-01': 'Trục thời gian', 'TREE-01': 'Sơ đồ quan hệ', 'STATE-01': 'Một tranh, hai trạng thái',
  },
  count: {
    moments: (n) => `${n} mốc`, people: (n) => `${n} người`, places: (n) => `${n} nơi`, labels: (n) => `${n} nhãn`, rows: (n) => `${n} con số`, lines: (n) => `${n} dòng`,
  },
  route: (a, b) => `${a} tới ${b}`,
  states: (a, b) => `${a} và ${b}`,
  title: (t) => t,
  // text cards: "Thẻ tiêu đề: <title>"
  card: { 'X-CARD-01': 'Thẻ chương', 'X-CARD-02': 'Thẻ tiêu đề', 'X-CARD-03': 'Credit cuối phim', 'X-CARD-04': 'Thẻ câu hỏi', 'TXT-01': 'Tiêu đề chương', 'ID-MARK-01': 'Mốc chương', 'ID-MARK-02': 'Mốc chương',
    'ID-BRAND-01': 'Tên kênh', 'ID-BRAND-02': 'Tên kênh', 'ID-BRAND-03': 'Tên kênh và tựa video', 'ID-BRAND-04': 'Tên kênh và tựa video' },
  // overlays: a short phrase each ("vòng sáng"); the others use the lower-case `label_vi`
  overlay: {
    'HI-01': 'vòng sáng', 'AN-01': 'khoanh tròn', 'AN-02': 'viền quanh', 'AN-03': 'tia phối cảnh', 'AN-05': 'thước kích thước', 'AN-06': 'lưới', 'X-ANN-01': 'nhãn chi tiết',
    'X-ANN-02': 'nhãn tác phẩm', 'X-ANN-03': 'nhãn tóm tắt', 'X-ANN-04': 'viền từng nhóm', 'X-ANN-05': 'chấm bản đồ', 'AN-04': 'bản đồ có đường đi', 'X-HI-01': 'làm tối xung quanh',
    'STATIC-02': 'nhãn nguồn', 'STATIC-04': 'trích dẫn', 'STATIC-05': 'nhãn tên người', 'STATIC-08': 'nhãn tên', 'STATIC-09': 'năm', 'HI-03': 'giữ màu chủ thể', 'TXT-02': 'chữ chạy ngang',
    'KEY-01': 'nhãn các phần của tranh', 'NUM-01': 'con số lớn', 'DOC-01': 'làm sáng dòng chữ', 'SHORT-04': 'nhãn vàng', 'ID-OPEN-01': 'mở đầu vệt sáng', 'ID-OPEN-02': 'mở đầu tối lại',
    'ID-LABEL-01': 'nhãn tác phẩm',
  },
  count2: (n, phrase) => `${n} ${phrase}`,
};

// c4pages: step 5, the words of the page itself (sbsimple.js) and of its list (shotlist.js)
export const EDIT_PAGE_LABELS = {
  title: 'Dựng hình',
  shots: (n) => `${n} cảnh`,
  noShots: 'Chưa có cảnh nào.',
  loading: 'Đang tải danh sách cảnh...',
  listTitle: 'Các cảnh',
  listHint: 'Ctrl hoặc Shift + bấm: chọn nhiều cảnh · Phím /: gõ yêu cầu',
  shotNo: (n) => `Cảnh ${n}`,
  locked: 'đã khóa',
  lockedHint: 'Cảnh này đã khóa: không ai sửa được cho đến khi bạn mở khóa ở Chỉnh tay.',
  frameFail: 'Chưa vẽ được khung này',
  chapter: {
    n: (i) => `Chương ${i}`,
    named: (i, name) => `Chương ${i} · ${name}`,
    from: (n, t) => `${n} cảnh · từ ${t}`,
    selectAll: 'Chọn cả chương',
    selectAllHint: 'Chọn mọi cảnh của chương này để sửa bằng lời.',
    collapse: 'Thu gọn chương',
    expand: 'Mở chương',
  },
  top: {
    hand: 'Chỉnh tay',
    handHint: 'Mở trình biên tập: dòng thời gian, bảng thiết lập từng cảnh, thư viện kỹ thuật và phím tắt.',
    approve: 'Duyệt',
    approved: 'Đã duyệt',
    approving: 'Đang duyệt...',
    approveFix: (n) => `Còn ${n} cảnh cần sửa nên chưa duyệt được.`,
    approveSave: 'Lưu rồi mới duyệt được.',
    dirty: 'Có chỗ sửa chưa lưu',
    save: 'Lưu',
    next: (label) => `Tiếp tục: ${label}`,
    cannotApprove: 'Chưa duyệt được: video còn chỗ chưa đúng. Bấm "Chỉnh tay" để xem chi tiết.',
  },
  problems: {
    count: (n) => `${n} cảnh cần sửa`,
    general: (n) => `${n} vấn đề chung của video`,
    see: 'Xem',
    first: 'Tới cảnh đầu tiên cần sửa',
    title: 'Những chỗ cần sửa',
    close: 'Đóng',
    none: 'Không có chỗ nào cần sửa.',
    stageNote: (n, text) => `Cảnh ${n} chưa vẽ được: ${text}.`,
    at: (n, text, overlay = false) => `Cảnh ${n}${overlay ? ', lớp phủ' : ''}: ${text}.`,
    line: (text, overlay = false) => (overlay ? `Lớp phủ ${text}` : text[0].toUpperCase() + text.slice(1)),
    inEditor: 'Sửa ở Chỉnh tay',
    text: {
      incomplete: 'còn thiếu một hình hoặc một thông tin bắt buộc',
      undrawable: 'chưa vẽ được hình với thiết lập hiện tại',
      asset: 'dùng một hình bị thiếu hoặc không đọc được',
      region: 'dùng một vùng của tranh không còn nữa',
      short: 'ngắn hơn mức cho phép',
      outside: 'có một lớp phủ vượt ra ngoài cảnh',
      time: 'có thời điểm chưa đúng',
      other: 'có một điểm chưa đúng, xem chi tiết ở Chỉnh tay',
    },
    generalText: 'có một điểm chưa đúng chung cho cả video, xem chi tiết ở Chỉnh tay',
  },
  now: {
    several: (n, list) => `${n} cảnh đang chọn (${list})`,
    spoken: 'Lời đang đọc:',
    noSpoken: 'Cảnh này chưa có lời đọc.',
    time: (a, b) => `${a} – ${b}`,
    hand: 'Sửa cảnh này ở Chỉnh tay',
    none: 'Chọn một cảnh trong danh sách để xem và sửa.',
  },
  hand: {
    back: 'Danh sách cảnh',
    backHint: 'Về trang đơn giản: video và danh sách các cảnh bằng lời thường.',
  },
};

// c4pages: step 4, the words of the page itself (views/picks_rows.js) and of its rows (views/picks_rows_logic.js)
export const PICKS_PAGE_LABELS = {
  title: 'Chọn hình',
  progress: (done, total) => `${done}/${total} đoạn đã có hình`,
  noLines: 'Chưa có đoạn lời dẫn nào.',
  missing: (n) => `${n} đoạn chưa có hình`,
  missingHint: 'Bấm để tới đoạn chưa có hình. Bấm lần nữa để tới đoạn kế tiếp.',
  skipped: (n) => `${n} đoạn bỏ qua`,
  lineNo: (n) => `Đoạn ${n}`,
  rowsHint: 'Bấm vào một đoạn để chọn nó rồi nhờ agent sửa. Giữ Ctrl (hoặc ⌘) để chọn thêm, giữ Shift để chọn một dãy. Nhấn "/" để gõ yêu cầu.',
  loading: 'Đang tải...',
  retry: 'Thử lại',
  chapter: {
    n: (i) => `Chương ${i}`,
    named: (i, name) => `Chương ${i} · ${name}`,
    count: (done, total) => `${done}/${total}`,
    selectAll: 'Chọn cả chương',
    selectAllHint: 'Chọn mọi đoạn của chương này để nhờ agent sửa.',
    collapse: 'Thu gọn',
    expand: 'Mở ra',
  },
  more: 'Xem cả đoạn',
  less: 'Thu gọn',
  empty: 'Chưa có hình. Bản nháp sẽ dùng tranh chính ở đoạn này.',
  skip: 'Bỏ qua: đoạn này không cần hình riêng.',
  add: '+',
  addTitle: 'Thêm một hình vào đoạn này',
  addMenu: { whole: 'Cả bức tranh', detail: (label) => `Cận cảnh: ${label}`, other: 'Tìm hình khác (Tự chọn tay)...' },
  added: (what, n) => `Đã thêm "${what}" vào đoạn ${n}.`,
  undo: 'Hoàn tác',
  undoHint: 'Bỏ hình vừa thêm.',
  undone: 'Đã bỏ hình vừa thêm.',
  undoGone: 'Không hoàn tác được nữa vì đoạn này đã đổi.',
  hand: 'Tự chọn tay',
  handTitle: 'Tìm hình ở các nguồn, lấy từ sách, tải lên, vẽ vùng và các gợi ý (có tính tiền) cho đoạn này.',
  back: 'Về danh sách đoạn',
  backTitle: 'Về trang đơn giản: các đoạn lời dẫn và hình của từng đoạn.',
  caption: {
    whole: 'Cả bức tranh',
    detail: (label) => `Cận cảnh: ${label}`,
    detailAny: 'Cận cảnh: một chi tiết',
    map: (title) => (title ? `Bản đồ: ${title}` : 'Bản đồ'),
    clip: (sec, title) => `Clip${sec ? ` ${sec} giây` : ''}${title ? `: ${title}` : ''}`,
    document: (title) => (title ? `Tài liệu: ${title}` : 'Tài liệu'),
    compare: (title) => (title ? `So sánh: ${title}` : 'So sánh'),
    image: (title) => (title ? `Ảnh: ${title}` : 'Một hình'),
    gone: 'Hình này không còn',
  },
  main: {
    none: 'Chưa chọn tranh chính.',
    noneHelp: 'Hãy chọn bức tranh chính của video trước: agent cần nó để chọn hình cho từng đoạn.',
    choose: 'Chọn tranh chính',
  },
  top: {
    approve: 'Duyệt chọn hình',
    approved: 'Đã duyệt',
    check: 'Kiểm tra',
    checkErrors: (n) => `Kiểm tra (${n} lỗi)`,
  },
  approveWhy: {
    noNarration: 'Cần có lời dẫn đã duyệt ở bước Kịch bản trước.',
    narration: 'Cần duyệt lời dẫn ở bước Kịch bản trước.',
    narrationSoft: 'Lời dẫn chưa được duyệt: bạn vẫn chọn hình được, nhưng chưa duyệt chọn hình được.',
    narrationEdited: 'Lời dẫn đã đổi sau khi duyệt: bạn vẫn chọn hình được, nhưng chưa duyệt chọn hình được.',
    main: 'Cần chọn tranh chính trước.',
    errors: (n) => `Còn ${n} lỗi cần sửa. Bấm "Kiểm tra" để xem.`,
    saving: 'Đang lưu...',
    again: 'Đã duyệt trước đó nhưng cần duyệt lại sau khi sửa.',
    emptyLines: (n) => `Còn ${n} đoạn chưa có hình: bản nháp sẽ dùng tranh chính ở đó.`,
  },
  stages: { narration: 'Mở bước Kịch bản' },
  issue: {                                                                    // the check of the picks in words on the simple page (a line by its number, a picture by its title)
    aLine: 'Một đoạn',
    noMain: 'Chưa chọn tranh chính.',
    noPick: (line) => `${line} chưa có hình: bản nháp sẽ dùng tranh chính ở đó.`,
    unknownAsset: (line) => `${line} dùng một hình không còn trong danh sách.`,
    unknownRegion: (line) => `${line} dùng một vùng của hình không còn nữa.`,
    beatUnknown: 'Có hình cho một đoạn không còn trong lời dẫn.',
    fileMissing: (title) => (title ? `Thiếu tệp ảnh của hình “${title}”.` : 'Thiếu tệp ảnh của một hình.'),
    flag: (title, flag) => `${title ? `Hình “${title}”` : 'Một hình'}: ${PICKS_LABELS.flag[flag] || 'cần xem lại'}.`,
    otherError: 'Có một lỗi trong chọn hình.',
    otherWarn: 'Có một điều cần xem trong chọn hình.',
    noneAtAll: 'Không có gì cần xem. Có thể duyệt.',
  },
  confirmEmpty: (n) => `${n} đoạn chưa có hình. Bản nháp sẽ dùng tranh chính ở những đoạn đó. Vẫn duyệt?`,
  sections: {
    title: 'Hình của dự án',
    regions: 'Vùng của tranh chính',
    context: 'Hình bối cảnh',
    clips: 'Clip',
    none: { regions: 'Chưa có vùng nào trên tranh chính. Agent sẽ đề xuất vùng, hoặc bạn tự vẽ ở "Tự chọn tay".', context: 'Chưa có hình bối cảnh nào.', clips: 'Chưa có clip nào.' },
    usedIn: (nums) => (nums.length ? `Dùng ở đoạn ${nums.length > 6 ? `${nums.slice(0, 6).join(', ')} và ${nums.length - 6} đoạn nữa` : nums.join(', ')}` : 'Chưa đoạn nào dùng'),
    drawRegion: 'Vẽ vùng trên tranh',
    regionUnnamed: 'Chi tiết chưa đặt tên',
    clipLen: (sec) => `${sec} giây`,
  },
  box: {                                                                       // the request box of this step says "đoạn" where the hand tools say "dòng"
    title: 'Nhờ agent sửa hình',
    placeholder: 'Bạn muốn đổi gì? Ví dụ: đoạn này chỉ cho xem khuôn mặt rồi cả bức tranh.',
    scopeBeats: 'Đoạn',
    scopeChapter: 'Chương',
    scopeAll: 'Cả video',
    noLineChosen: 'Chưa chọn đoạn nào.',
    beatsCount: (n) => (n === 1 ? '1 đoạn' : `${n} đoạn`),
    linesWords: (n, list) => (n === 1 ? `Đoạn ${list} đang chọn` : `${n} đoạn đang chọn (${list})`),
    thread: 'Các lần sửa',
    threadEmpty: 'Chưa có lần sửa nào. Gõ điều bạn muốn đổi ở ô trên.',
    lineAt: (n) => `Đoạn ${n}`,
    dropLine: (n) => `Bỏ đoạn ${n}`,
    listWords: (nums) => (nums.length > 6 ? `${nums.slice(0, 6).join(', ')} và ${nums.length - 6} đoạn nữa` : nums.join(', ')),
    chapterHere: 'Chưa có chương cho đoạn đang chọn.',
    noNarration: 'Dự án chưa có lời dẫn để chọn hình.',
  },
};

/* worker fixscript: the labels of the new checks of the script step */
export const CODE_FIXSCRIPT = {
  source_author_named: 'Lời dẫn nêu tên tác giả sách nguồn', source_talk: 'Lời dẫn nói về chính các nguồn',
  fact_for_owner: 'Dữ kiện có lời nhắn cho người duyệt', outline_note: 'Ghi chú của mô hình cho bạn',
};
Object.assign(CODE, CODE_FIXSCRIPT);

// ---- outfolder: the output folder (bti/output/): the one switch in the settings dialog (outputswitch.js)
export const OUTPUT_LABELS = {
  loading: 'Đang tải...',
  title: 'Thư mục output',
  clean: 'Dọn thư mục làm việc sau khi xuất video',
  hint: 'Mỗi tác phẩm có một thư mục riêng trong "output": video, lời dẫn, các cảnh và nhật ký. Khi xuất video xong, ứng dụng xóa các tệp tạm của dự án (bản dựng từng đoạn, ảnh xem thử, bản ghi từng lượt chạy của agent, nhật ký dài) để giải phóng chỗ trống. Tài liệu, hình, giọng đọc, lịch sử sửa và video không bị xóa. Tắt đi nếu bạn muốn giữ các tệp tạm; xuất lại cùng một storyboard sẽ nhanh hơn.',
  saved: 'Đã lưu.',
  saveFail: 'Chưa lưu được: ',
  loadFail: 'Chưa đọc được cài đặt này: ',
};

// ---- worker introflow (2026-11-20): the new opening and "Khớp lại với giọng đọc". One line with a button on the storyboard page (retimeline.js), shown
// only while the state answer lists the action `storyboard.retime`; the same words are what the owner reads in the change log and in shots.md.
export const RETIME_LABELS = {
  line: 'Giọng đọc đã được làm lại nên thẻ chương, tên kênh hoặc điểm cuối của video đang lệch.',
  button: 'Khớp lại với giọng đọc',
  hint: 'Dời thẻ chương, đoạn hiện tên kênh và điểm cuối cho đúng chỗ giọng đọc để lại, thêm hoặc bỏ cảnh mở đầu cả bức tranh. Các cảnh bạn hoặc agent đã dựng giữ nguyên. Có thể hoàn tác.',
  busy: 'Đang khớp lại...',
  done: (n) => (n ? `Đã khớp lại với giọng đọc (${n} cảnh).` : 'Storyboard đã khớp với giọng đọc, không có gì phải đổi.'),
  left: 'Còn chỗ chưa tự khớp được (cảnh đang khóa hoặc số thẻ chương không đúng). Xem lại các thẻ chương.',
  fail: 'Không khớp lại được: ',
  loadFail: 'Không đọc được trạng thái của dự án: ',
  tookInMerged: 'Đã khớp lại và ghép với các sửa chưa lưu của bạn.',
  tookInFail: 'Không tải được storyboard mới: ',
};
// the words the owner reads for the opening shot and the channel-name beat (the Python twin is bti/output/shotwords.py)
export const OPENING_WORDS = { opening: 'Mở đầu: cả bức tranh', brand: 'Tên kênh và tựa video' };
/* worker linekinds: the warning `outside_no_picture` of the picks (a line about something outside the painting that shows only the main painting, because the picture of the
   thing itself was not found). The list "Cảnh báo" reads PICKS_LABELS.issue; the simple page reads PICKS_PAGE_LABELS.issue (its switch in views/picks_rows_logic.js needs a
   `case 'outside_no_picture': return W.issue.outsideNoPicture(line);` line, which that file's owner adds). */
PICKS_LABELS.issue.outside_no_picture = (i) => `Dòng ${i.beat} nói về thứ ngoài bức tranh nhưng chỉ có tranh chính: chưa tìm được hình của chính thứ đó.`;
PICKS_PAGE_LABELS.issue.outsideNoPicture = (line) => `${line} nói về thứ ngoài bức tranh nhưng chỉ có tranh chính: chưa tìm được hình của chính thứ đó.`;
// ---- websearch: the web search of the automatic choice of pictures (bti/picks/auto/webround.py): the one switch in the settings dialog (websearchswitch.js)
export const WEBSEARCH_LABELS = {
  loading: 'Đang tải...',
  title: 'Chọn hình tự động',
  on: 'Tìm hình trên web khi chọn hình tự động',
  hint: (n) => `Khi bật, lúc agent chọn hình tự động mà Wikipedia và các nguồn ảnh miễn phí chưa có hình đúng, ứng dụng tìm thêm trên web bằng dịch vụ You.com. Việc này tốn tiền: mỗi lần chạy tối đa ${n} lượt tìm. Tắt thì không tốn khoản nào. Hình tìm được trên web chưa rõ giấy phép nên được đánh dấu để bạn xem lại.`,
  saved: 'Đã lưu.',
  saveFail: 'Chưa lưu được: ',
  loadFail: 'Chưa đọc được cài đặt này: ',
};


// ---- worker titlestep (2026-11-20): the video's title on the script page (titlepanel.js, the logic is titlelogic.js). Every sentence the owner reads about the title is here.
Object.assign(SETTINGS_LABELS.role, { 'script.title': 'Tựa video' });
export const TITLE_FORM_WORDS = {
  contradiction: 'Hai thứ trái ngược', question: 'Câu hỏi', hidden: 'Ngay trước mắt mà ít ai thấy', really_is: 'Nó thật ra là gì', object: 'Một vật có quá khứ',
  number: 'Một con số khó tin', other: 'Dạng khác',
};
export const TITLE_LABELS = {
  name: 'Tựa video',
  none: 'Chưa có tựa video.',
  noneHint: 'Sau khi duyệt lời dẫn, agent đọc lời dẫn và viết tựa video.',
  needNarration: 'Duyệt lời dẫn trước, rồi agent mới viết được tựa.',
  stale: 'Lời dẫn đã đổi sau khi agent viết tựa này: nên viết lại.',
  openButton: 'Chọn hoặc sửa tựa',
  openHint: 'Xem các tựa agent đề xuất, chọn một tựa hoặc gõ tựa của bạn.',
  write: 'Viết tựa',
  writeAgain: 'Viết lại tựa',
  writeHint: 'Nhờ agent đọc lời dẫn và viết tựa (khoảng một phút).',
  cancel: 'Dừng',
  working: 'Agent đang viết tựa video...',
  progress: (note) => (note ? `Agent đang viết tựa video: ${note}` : 'Agent đang viết tựa video...'),
  dialogTitle: 'Tựa video',
  intro: 'Một dòng mà người lạ đọc trước khi quyết định xem, và cũng là dòng hiện dưới tên kênh sau đoạn mở đầu.',
  current: 'Tựa đang dùng',
  who: { human: 'Bạn', agent: (label) => `Agent ${label}`, cli: (name) => `Lệnh bti (${name})`, other: (by) => by },
  chosenBy: (who, when) => (when ? `${who}, ${when}` : who),
  candidates: 'Các tựa agent đề xuất',
  noCandidates: 'Agent chưa đề xuất tựa nào.',
  candidateHint: 'Bấm vào một tựa để chọn nó.',
  inUse: 'đang dùng',
  chars: (n) => `${n} ký tự`,
  linesOf: (list) => `Dựa trên: ${list}`,
  scoresOf: (s) => `Tò mò ${s.curiosity ?? '?'} · Cụ thể ${s.concrete ?? '?'} · Trọng tâm ${s.central ?? '?'} · Rõ ${s.clear ?? '?'}`,
  own: 'Tựa của bạn',
  ownHint: (max) => `Một dòng, tối đa ${max} ký tự. Tựa bạn gõ hoặc chọn không bao giờ bị coi là cũ, và chạy tự động không ghi đè lên nó.`,
  ownPlaceholder: 'Gõ tựa video',
  useOwn: 'Dùng tựa này',
  counter: (n, max) => `${n}/${max}`,
  tooLong: (n, max) => `Tựa dài ${n} ký tự, tối đa ${max}.`,
  oneLine: 'Tựa chỉ có một dòng.',
  empty: 'Hãy gõ tựa video.',
  outsideBest: (a, b) => `Nên từ ${a} đến ${b} ký tự.`,
  again: 'Nhờ agent viết lại',
  noteLabel: 'Điều bạn muốn (không bắt buộc)',
  notePlaceholder: 'Ví dụ: nói về tấm gương, không phải chiếc nhẫn',
  noteHint: (max) => `Tối đa ${max} ký tự. Lời nhắn được đưa vào bản hướng dẫn của agent.`,
  history: 'Các tựa đã dùng trước đó',
  confirmReplace: { title: 'Viết lại tựa?', message: 'Tựa bạn đã chọn hoặc gõ sẽ được thay bằng tựa mới của agent. Tựa cũ vẫn nằm trong danh sách các tựa đã dùng trước đó.', ok: 'Viết lại' },
  saved: 'Đã lưu tựa video.',
  generated: (text) => `Agent đã viết tựa: "${text}".`,
  cancelled: 'Đã dừng việc viết tựa.',
  storyboardNone: '',
  loadFail: 'Chưa đọc được tựa video: ',
  saveFail: 'Chưa lưu được tựa: ',
  startFail: 'Chưa bắt đầu viết tựa được: ',
  jobFail: 'Agent chưa viết xong tựa: ',
  cancelFail: 'Không dừng được: ',
};

// ---- worker fixes3 (2026-11-20): the second line of the result of the agent's choice of pictures names the web searches of the run (views/picks_logic.js `autoDetailText`; the
// Python twin of the closing sentence is bti/picks/auto/webround.py `web_sentence`: "Đã tìm trên web 12/80 lần.")
PICKS_AUTO_LABELS.detail.web = (n, max) => (max > 0 ? `tìm trên web ${n}/${max} lần` : `tìm trên web ${n} lần`);
// ---- worker fixes3 (2026-11-20): the same title strip on the storyboard page (views/storyboard.js mounts titlepanel.js there); it says so while the storyboard is off the voice
TITLE_LABELS.offVoice = 'Storyboard đang lệch với giọng đọc nên chưa nhận tựa này. Bấm "Khớp lại với giọng đọc" trước: storyboard sẽ lấy tựa ngay khi khớp xong.';
TITLE_LABELS.tookInMerged = 'Đã cập nhật tựa video và ghép với các sửa chưa lưu của bạn.';
TITLE_LABELS.tookInFail = 'Không tải được storyboard mới: ';
/* worker panelbox (2026-11-20): the warning `content_box_unsure` of the picks (the program found a dark or light band round the main painting that it did not believe, so the whole picture
   is the painted area, as it was before). The list "Cảnh báo" reads PICKS_LABELS.issue; the simple page reads PICKS_PAGE_LABELS.issue (its switch in views/picks_rows_logic.js needs a
   `case 'content_box_unsure': return W.issue.contentBoxUnsure;` line, which that file's owner adds). */
PICKS_LABELS.issue.content_box_unsure = () => 'Chưa chắc phần nào của tranh chính là mặt tranh (quanh ảnh có dải đen hoặc sáng chưa rõ): dùng cả ảnh như trước. Nếu ảnh có nền đen, hãy đặt vùng tranh cho đúng.';
PICKS_PAGE_LABELS.issue.contentBoxUnsure = 'Chưa chắc phần nào của tranh chính là mặt tranh (quanh ảnh có dải đen hoặc sáng chưa rõ): dùng cả ảnh như trước.';

// ---- worker pointfix: short names for the viewer's checks.
export const POINTFIX_LABELS = {
  small_detail_not_lit: 'Chi tiết nhỏ chưa được rọi sáng',
  highlight_nothing_to_dim: 'Vùng sáng chiếm quá nhiều khung hình',
  text_too_brief: 'Chữ hiện quá nhanh',
};

// ---- worker tightbox (2026-11-21): labels for the second look (`picks.tighten` and tight detail regions on the main painting)
export const PICKS_TIGHTEN_LABELS = {
  button: 'Đo lại khung chi tiết',
  working: 'Agent đang đo lại khung chi tiết...',
  tightTag: 'khít',
};

// ---- worker boxcam (2026-11-21): short names for region framing and arrival checks.
export const BOXCAM_LABELS = {
  camera_off_region: 'Vùng được nhắc bị cắt ngoài khung',
  thing_arrives_late: 'Máy quay tới chi tiết quá muộn',
};
Object.assign(CODE, BOXCAM_LABELS);

// ---- worker partexport (2026-11-21): incremental ~60 s export parts (kept after clean; reused on small edits)
OUTPUT_LABELS.hint = 'Mỗi tác phẩm có một thư mục riêng trong "output": video, lời dẫn, các cảnh và nhật ký. Khi xuất video xong, ứng dụng xóa các tệp tạm của dự án (video ghép tạm, ảnh xem thử, bản ghi từng lượt chạy của agent, nhật ký dài và các đoạn dựng cũ) nhưng giữ lại các đoạn dựng của lần xuất này để khi sửa nhỏ chỉ dựng lại các đoạn đã đổi. Tài liệu, hình, giọng đọc, lịch sử sửa và video không bị xóa. Tắt đi nếu bạn muốn giữ toàn bộ tệp tạm.';
export const PARTEXPORT_LABELS = {
  reusedNote: 'Đã có sẵn, dùng lại',
  renderedNote: 'Đã dựng mới',
  partsPlan: (toRender, reused, total) => (
    toRender === 0
      ? `Dùng lại cả ${total} đoạn (không cần dựng lại)`
      : reused === 0
        ? `Sẽ dựng mới ${total}/${total} đoạn`
        : `Sẽ dựng mới ${toRender} đoạn, dùng lại ${reused} đoạn đã có`
  ),
  partsSummary: (rendered, reused) => (
    rendered === 0
      ? `Đã dùng lại cả ${reused} đoạn (không phải dựng lại).`
      : reused === 0
        ? `Đã dựng mới ${rendered} đoạn (dùng lại 0 đoạn).`
        : `Đã dựng mới ${rendered} đoạn, dùng lại ${reused} đoạn.`
  ),
};
Object.assign(EXPORT_LABELS, PARTEXPORT_LABELS);

// ---- worker namefirst: first presentation of a named figure.
CODE.name_not_shown = "Chưa hiện tên khi giới thiệu";

// ---- worker introrules (2026-11-21): cold-open script checks.
export const CODE_INTRORULES = {
  cold_open_missing_name: 'Mở đầu thiếu tên tranh hoặc họa sĩ',
  cold_open_late_name: 'Mở đầu đọc tên tranh hoặc họa sĩ muộn',
  cold_open_first_line_long: 'Dòng mở đầu quá dài',
  cold_open_no_early_turn: 'Mở đầu chưa đặt mâu thuẫn sớm',
  cold_open_no_closing_question: 'Mở đầu chưa kết bằng câu hỏi mở',
  cold_open_roadmap: 'Mở đầu có câu giới thiệu kế hoạch video',
  cold_open_word_count: 'Độ dài phần mở đầu ngoài 60–145 từ',
};
Object.assign(CODE, CODE_INTRORULES);

// ---- worker idfix (2026-11-21): non-cast strip on main painting without light.
export const CODE_IDFIX = {
  strip_without_light: 'Nhãn vật chưa có đèn rọi',
};
Object.assign(CODE, CODE_IDFIX);

// worker introopen: first sentence identifies the painting and painter.
export const CODE_INTROOPEN = {
  cold_open_first_sentence_names: "Câu đầu thiếu tên tranh hoặc họa sĩ",
};
Object.assign(CODE, CODE_INTROOPEN);

// worker listmark
Object.assign(CODE, { year_already_on_screen: "Năm đã hiện trong nhãn" });

// ---- worker voiceplain (2026-11-22): attribution phrases in narration
export const CODE_VOICEPLAIN = {
  attribution_phrase: 'Lời dẫn dùng cụm quy cho học giả hoặc cách đọc',
};
Object.assign(CODE, CODE_VOICEPLAIN);
// worker viewreview: remaining findings after the viewer review.
Object.assign(CODE, {
  review_picture_mismatch: 'Hình chưa khớp lời dẫn',
  review_text_wrong: 'Chữ trên hình chưa đúng',
  review_context_missing: 'Thiếu lời giới thiệu',
  review_picture_repeated: 'Hình bị lặp',
});
// worker subjdraft: subject visibility and year label.
Object.assign(CODE, {
  subject_not_on_screen: 'Chưa thấy chủ thể được nhắc đến',
  year_already_on_screen: 'Năm đã hiện trong nhãn',
});

// ---- worker pictime (2026-11-26): borrowed picture duration warnings
export const CODE_PICTIME = {
  outside_picture_brief: 'Hình ngoài tranh hiện quá ngắn',
  outside_picture_dropped: 'Dòng phải bỏ bớt hình ngoài tranh vì không đủ thời lượng',
};
Object.assign(CODE, CODE_PICTIME);
// worker musicstep: optional music in the export step.
export const MUSIC_LABELS = {
  title: 'Nhạc', empty: 'Chưa chọn nhạc.', choose: 'Chọn nhạc lại', clear: 'Bỏ nhạc',
  choosing: 'Đang chọn nhạc…', unavailable: 'Thư viện nhạc đang trống hoặc chưa có storyboard.',
  invalid: 'Không đọc được danh sách nhạc. Hãy chọn nhạc lại hoặc bỏ nhạc.',
  chosen: 'Đã chọn nhạc.', cleared: 'Đã bỏ nhạc.', failed: 'Chọn nhạc chưa xong. Hãy thử lại.',
  roles: { bed: 'Nhạc nền', swell: 'Nhạc dâng', ident: 'Tên kênh', ending: 'Kết' },
};
Object.assign(EXPORT_LABELS.stale, { music: 'Nhạc đã thay đổi.' });
// worker subjvis: borrowed picture caption.
Object.assign(CODE, { borrowed_without_caption: 'Hình mượn chưa có ghi chú' });
// worker introsweep: ID-BRAND-04 raking sweep ident variant labels.
Object.assign(VALUE, {
  A: 'Cách A — Quét chéo một nhịp',
  B: 'Cách B — Đèn rọi hai nhịp',
  C: 'Cách C — Đèn hạ góc quét',
});
