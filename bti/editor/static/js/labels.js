// ONE set of Vietnamese labels for the whole app.

/** Stage of a project (the `stage` field of /api/projects and of the pipeline). */
export const STAGE = { selected: 'Đã chọn tác phẩm', outlined: 'Đã duyệt dàn ý', script: 'Có kịch bản', voiced: 'Có giọng đọc', picked: 'Đã chọn hình', storyboard: 'Có storyboard', approved: 'Đã duyệt storyboard', rendered: 'Đã dựng xong' };
export const stageLabel = (s) => STAGE[s] || s || '';

/** Short state of a step of the stepper. */
export const STEP_STATE = { done: 'Xong', current: 'Hiện tại', available: 'Mở được', locked: 'Khóa', not_built: 'Chưa xây dựng', no_data: 'Không có dữ liệu' };

export const RIGHTS = { pd_likely: 'Có thể hết bản quyền', copyright_likely: 'Có thể còn bản quyền', unknown: 'Chưa rõ bản quyền' };
export const KIND = { chapter_per_artwork: 'mỗi chương một tác phẩm', fixed_spread: 'mỗi tác phẩm một đoạn trang cố định', short_entries: 'mục ngắn', themed_chapter: 'chương theo chủ đề' };
export const SHORT_BOOK = { payne_gae: 'Payne', hodge_aid: 'Hodge', hagen_wgps: 'Hagen', grovier_nws: 'Grovier', brookehitching_mad: 'Brooke-Hitching', dasal_artcurious: 'Dasal' };
export const shortBook = (id) => SHORT_BOOK[id] || id;
export const LOW_TRUST = 'bản dịch máy, không dùng làm nguồn sự kiện';

/** Messages for the validation codes of the script step. */
export const CODE = {
  chapter_missing: 'Thiếu chương', empty_beat: 'Dòng trống', markup_in_text: 'Có ký hiệu trong lời đọc', words_under: 'Quá ngắn (dưới 70% mục tiêu)',
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

/** What each step that is not built yet will do. Shown as an honest placeholder, with no controls. */
export const PLANNED = {
  voice: {
    title: 'Giọng đọc',
    will: [
      'Máy chủ giọng đọc đọc lời dẫn đã duyệt ở bước Kịch bản, từng dòng một.',
      'Bạn nghe thử từng dòng, chọn lại giọng hoặc đọc lại dòng chưa vừa ý.',
      'Kết quả là một tệp âm thanh duy nhất (`audio/mix.m4a`) và `timing.json` ghi thời điểm của từng từ.',
      'Duyệt xong, dự án chuyển sang giai đoạn "Có giọng đọc".',
    ],
    meanwhile: 'Hiện chưa có gì để bấm ở đây. Dự án chỉ có giọng đọc nếu được nhập từ bản dựng trước.',
  },
  picks: {
    title: 'Chọn hình',
    will: [
      'Với mỗi dòng lời dẫn, bạn chọn thứ sẽ hiện trên hình (gợi ý nằm ở ô "cho xem" của bước Kịch bản) và thêm cảnh.',
      'Hình lấy từ thư viện của dự án, Wikimedia Commons hoặc The Met, theo giấy phép.',
      'Duyệt xong, hệ thống soạn một đề xuất storyboard để bạn sửa tiếp ở bước Dựng hình.',
    ],
    meanwhile: 'Hiện chưa có gì để bấm ở đây. Hình vẫn có thể được chọn tay trong bước Dựng hình (tab Hình), với dự án đã có storyboard.',
  },
  export: {
    title: 'Xuất video',
    will: [
      'Máy chủ dựng video cuối chất lượng cao từ storyboard đã duyệt và giọng đọc.',
      'Bạn xem tiến độ, xem lại tệp đã dựng và biết tệp nằm ở đâu.',
      'Dự án chuyển sang giai đoạn "Đã dựng xong".',
    ],
    meanwhile: 'Hiện chưa có nút dựng bản cuối. "Xem thử 10 giây" ở bước Dựng hình vẫn dùng được để kiểm tra từng đoạn.',
  },
};
