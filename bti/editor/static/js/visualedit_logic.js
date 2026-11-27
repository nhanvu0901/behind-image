// Pure helpers for Step 5 ("Dựng hình") on the unified visual path:
// moment spoken words per shot, grouped Vietnamese compose notes, and review findings.
// No DOM, no network. Tested in tests/editor_frontend/visualpage.test.mjs.
import { VISUAL_PAGE_LABELS as VL } from './labels.js';
import { issueText } from './errmsg.js';
import { spokenText } from './shotlist.js';
import { momentWordsText } from './visualpage_logic.js';

const clean = (v) => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : '');

/** Whether the storyboard / project uses the composed visual path rather than legacy drafts. */
export function isVisualStoryboard({ storyboard = null, visual = null } = {}) {
  if (visual && typeof visual === 'object' && Array.isArray(visual.moments)) return true;
  if (storyboard?.made_from?.visual) return true;
  if (Array.isArray(storyboard?.compose_notes)) return true;
  return (storyboard?.shots || []).some((s) => typeof s?.moment === 'string' && s.moment);
}

/** Map momentId -> { lineNumber (1-based), beatId } using narration chapters or timing beats. */
export function momentLineMap(visual, narration = null, timingBeats = []) {
  const lineOrder = new Map();
  let n = 0;
  for (const ch of narration?.chapters || []) {
    for (const b of ch?.beats || []) {
      if (b?.id && !lineOrder.has(b.id)) lineOrder.set(b.id, ++n);
    }
  }
  if (!lineOrder.size) {
    for (const b of timingBeats || []) {
      if (b?.id && !lineOrder.has(b.id)) lineOrder.set(b.id, ++n);
    }
  }
  const out = new Map();
  for (const m of visual?.moments || []) {
    if (!m?.id) continue;
    const lineNo = lineOrder.get(m.line) || null;
    out.set(m.id, { lineNumber: lineNo, beatId: m.line || null });
  }
  return out;
}

/** Map shot.id -> spoken words of its moment (empty for program cards without speech). */
export function momentWordsMap({ storyboard = null, visual = null, words = [] } = {}) {
  const byMoment = new Map((visual?.moments || []).map((m) => [m.id, m]));
  const out = new Map();
  for (const s of storyboard?.shots || []) {
    if (!s?.id) continue;
    if (s.moment && byMoment.has(s.moment)) {
      const span = momentWordsText(byMoment.get(s.moment), words);
      if (span.text) { out.set(s.id, span.text); continue; }
    }
    if (s.intent !== 'structure' && Number.isFinite(s._t0) && Number.isFinite(s._t1)) {
      const fallback = spokenText(words, s._t0, s._t1, 140);
      if (fallback) { out.set(s.id, fallback); continue; }
    }
    out.set(s.id, '');
  }
  return out;
}

const RULE_KIND = {
  C1: 'timing',
  C2: 'pair',
  C3: 'camera',
  C4: 'intro',
  C5: 'caption',
  C6: 'mark',
  C7: 'device',
  C8: 'boundary',
};

export const NOTE_GROUP_ORDER = ['timing', 'pair', 'camera', 'intro', 'caption', 'mark', 'device', 'boundary'];

/** Group key for a composer rule code (C1..C8). */
export function composeNoteKind(rule) {
  return RULE_KIND[String(rule || '').toUpperCase()] || 'boundary';
}

const NOTE_EXACT = {
  'extended backward toward sentence start': 'hình mượn được kéo dài về đầu câu',
  'shortened to make room for the following picture': 'cảnh trước được rút ngắn để nhường chỗ cho hình kế tiếp',
  'extended forward': 'hình mượn được kéo dài thêm về phía sau',
  'shortened to make room for the preceding picture': 'cảnh sau được rút ngắn để nhường chỗ cho hình trước',
  'extended backward': 'hình mượn được kéo dài thêm về phía trước',
  'extended forward for introduction': 'kéo dài cảnh để kịp hiện hết nhãn giới thiệu tên',
  'start moved later to fit the previous introduction': 'dời đầu cảnh lại để nhường thời gian cho nhãn tên trước đó',
  'extended forward for introduction by joining the next moment': 'gộp thêm khoảnh khắc kế tiếp để đủ thời gian hiện nhãn tên',
  'introduction has too little time after the spoken word': 'sau từ được nhắc còn quá ít thời gian nên chưa hiện được nhãn tên',
  'picture dropped after no room for a pair': 'bỏ bớt một hình mượn vì không đủ thời lượng để ghép đôi',
  'pair starts after the sentence because a program boundary occupies it': 'cảnh ghép đôi bắt đầu muộn hơn đầu câu do gặp mốc chương',
  'pair ends before the sentence because a program boundary occupies it': 'cảnh ghép đôi kết thúc sớm hơn cuối câu do gặp mốc chương',
  'start moved to the end of the pair\'s sentence': 'dời đầu cảnh tới cuối câu của cảnh ghép đôi',
  'picture dropped because the pair occupies the sentence': 'bỏ hình mượn khác vì cả câu đã dùng cặp hình ghép đôi',
  'entire available duration is shorter than the minimum': 'khoảng thời gian hiện có ngắn hơn thời lượng tối thiểu của một cảnh',
  'start moved after a chapter mark': 'dời đầu cảnh ra sau mốc chuyển chương',
  'unknown wanted picture; used its recorded fallback': 'không nhận ra mục hình cần tìm, đang dùng hình dự phòng đã ghi',
  'map record contains only a centre; other place coordinates were not invented': 'bản đồ chỉ có một tâm điểm, giữ nguyên không tự suy tọa độ nơi khác',
  'map has no resolved place coordinates; used a recorded fallback': 'bản đồ chưa có tọa độ địa danh nên dùng hình dự phòng đã ghi',
  'raised region zoom to fill the frame; a small source may look softer': 'tăng độ phóng vùng tranh để phủ kín khung hình (ảnh nhỏ có thể hơi mờ)',
  'framed the union of listed point targets': 'mở khung hình bao trọn tất cả các chi tiết được chỉ đến',
  'subtitle omitted because it repeats the name or exceeds six words': 'bỏ dòng phụ của nhãn tên vì lặp tên hoặc dài quá sáu từ',
  'intro omitted because its cast member is missing': 'bỏ nhãn giới thiệu vì nhân vật chưa có trong danh sách',
  'intro omitted because its spoken word precedes the shot': 'bỏ nhãn giới thiệu vì từ được nhắc nằm trước đầu cảnh',
  'intro could not fit or its cast member has no strip': 'không đặt được nhãn giới thiệu (quá ngắn hoặc đối tượng không bật nhãn)',
  'pair picture has no caption': 'một hình trong cặp ghép đôi chưa có chú thích',
  'picture has no caption': 'hình mượn chưa có chú thích',
  'intent omitted because this picture cannot show it': 'bỏ bớt lớp phủ vì hình đang chiếu không dùng được kỹ thuật này',
  'overlay removed at chapter boundary': 'bỏ lớp phủ nằm vượt sang mốc chương tiếp theo',
  'covered by an owner-locked shot': 'khoảnh khắc được giữ nguyên theo cảnh bạn đã khóa',
  'assigned a new id because the old id belongs to a locked shot': 'giữ riêng cảnh mới vì mã cũ thuộc cảnh bạn đã khóa',
  'joined into previous view before a locked shot': 'gộp vào cảnh trước đó để tránh cảnh quá ngắn trước cảnh đã khóa',
  'overlay shortened or omitted at a locked boundary': 'rút ngắn hoặc bỏ lớp phủ vì chạm ranh giới cảnh đã khóa',
  'ring omitted: target exceeds maximum radius': 'bỏ vòng khoanh vì vùng mục tiêu quá lớn so với khung hình',
};

/** Translate a single English compose_note string from bti.compose into plain Vietnamese. */
export function translateComposeNoteText(rawWhat) {
  const what = clean(rawWhat);
  if (!what) return '';
  if (NOTE_EXACT[what]) return NOTE_EXACT[what];
  if (/^joined into .+ to fit introduction$/.test(what)) {
    return 'được gộp vào cảnh trước để kịp hiện nhãn giới thiệu tên';
  }
  if (/^joined into .+ to keep the picture$/.test(what)) {
    return 'được gộp vào cảnh liền kề để giữ đủ thời lượng cho hình mượn';
  }
  if (/^joined into pair .+ to cover the sentence$/.test(what)) {
    return 'được gộp vào cặp hình ghép đôi để phủ trọn cả câu';
  }
  if (/^joined into /.test(what)) {
    return 'được gộp vào cảnh liền kề để giữ đủ thời lượng';
  }
  if (/^paired with /.test(what)) {
    return 'được ghép đôi cạnh nhau trong cùng một câu';
  }
  if (/^mark .+ omitted: person, large, outside frame, or too late$/.test(what)) {
    return 'bỏ dấu chỉ chi tiết (chi tiết đã lớn rõ, nằm trên người, ngoài khung hoặc quá muộn)';
  }
  if (/^ring .+ fades before sentence end because the engine caps its hold$/.test(what)) {
    return 'vòng khoanh tắt sớm hơn cuối câu do chạm mức giữ tối đa';
  }
  if (/^reading omitted: region .+ is missing$/.test(what)) {
    return 'bỏ khung đọc chữ vì không còn vùng tương ứng trên tranh';
  }
  if (/^label omitted: text or label count exceeds the engine limit$/.test(what)) {
    return 'bỏ bớt nhãn chi tiết vì vượt quá giới hạn chữ hoặc số lượng nhãn';
  }
  if (/^label omitted: region .+ is missing$/.test(what)) {
    return 'bỏ một nhãn chi tiết vì không còn vùng tương ứng trên tranh';
  }
  if (/^number omitted: text exceeds the engine limit$/.test(what)) {
    return 'bỏ khung con số vì chữ quá dài so với giới hạn hiển thị';
  }
  if (/omitted because its minimum duration does not fit$/.test(what)) {
    return 'bỏ lớp phủ vì thời lượng cảnh không đủ mức tối thiểu';
  }
  if (/removed at chapter boundary because it no longer fits$/.test(what)) {
    return 'bỏ lớp phủ ở ranh giới chương vì không còn đủ thời lượng';
  }
  return 'đã điều chỉnh bố cục hoặc thời lượng cảnh cho phù hợp quy chuẩn';
}

/** Group compose_notes by kind with Vietnamese sentences prefixed by "câu N: ...". */
export function groupComposeNotes(notes, { visual = null, storyboard = null, narration = null, timingBeats = [] } = {}) {
  const byMoment = momentLineMap(visual, narration, timingBeats);
  const shots = storyboard?.shots || [];
  const shotByMoment = new Map();
  const shotNumById = new Map();
  shots.forEach((s, idx) => {
    if (s?.id) shotNumById.set(s.id, idx + 1);
    if (s?.moment && !shotByMoment.has(s.moment)) shotByMoment.set(s.moment, s.id);
  });

  const groupsMap = new Map(NOTE_GROUP_ORDER.map((k) => [k, []]));
  const seen = new Set();
  for (const n of notes || []) {
    if (!n || typeof n !== 'object') continue;
    const kind = composeNoteKind(n.rule);
    const body = translateComposeNoteText(n.what);
    if (!body) continue;
    const mid = clean(n.moment);
    const lineInfo = mid ? byMoment.get(mid) : null;
    const shotId = mid ? (shotByMoment.get(mid) || null) : null;
    const shotNo = shotId ? shotNumById.get(shotId) : null;
    const prefix = lineInfo?.lineNumber
      ? VL.step5.linePrefix(lineInfo.lineNumber)
      : shotNo
        ? VL.step5.shotPrefix(shotNo)
        : '';
    const sentence = prefix ? `${prefix}: ${body}` : body.charAt(0).toUpperCase() + body.slice(1);
    const dedup = `${kind}|${sentence}`;
    if (seen.has(dedup)) continue;
    seen.add(dedup);
    groupsMap.get(kind).push({
      kind,
      sentence,
      momentId: mid || null,
      shotId,
      shotNumber: shotNo,
      lineNumber: lineInfo?.lineNumber || null,
    });
  }

  return NOTE_GROUP_ORDER
    .map((kind) => ({
      kind,
      title: VL.step5.notesGroup[kind] || kind,
      items: groupsMap.get(kind),
    }))
    .filter((g) => g.items.length > 0);
}

/** Extract and format remaining viewer-review findings into Vietnamese items. */
export function extractReviewFindings({ issues = [], reviewReport = null, shots = [] } = {}) {
  const shotIndex = new Map();
  (shots || []).forEach((s, idx) => { if (s?.id) shotIndex.set(s.id, idx + 1); });

  const combined = [];
  for (const i of issues || []) {
    if (i && String(i.code || '').startsWith('review_')) combined.push(i);
  }
  for (const w of reviewReport?.warnings || []) {
    if (w && String(w.code || '').startsWith('review_')) combined.push(w);
  }

  const out = [];
  const seen = new Set();
  for (const raw of combined) {
    const shotId = raw.shot || raw.args?.shot || null;
    const shotNumber = shotId ? (shotIndex.get(shotId) || null) : null;
    const args = { ...(raw.args || {}), ...(shotId ? { shot: shotNumber ? `cảnh ${shotNumber}` : shotId } : {}) };
    const translated = issueText({ ...raw, args });
    const text = translated.text;
    const key = `${raw.code}|${shotId || ''}|${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      code: raw.code,
      shotId,
      shotNumber,
      text,
    });
  }
  return out;
}
