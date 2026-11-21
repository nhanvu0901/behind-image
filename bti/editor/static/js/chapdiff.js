// The differences between the chapters of the narration and of the outline (`chapter_diff` of the server), as a list the page
// can show with one action per difference. Pure; tested in tests/editor_frontend/chapdiff.test.mjs.
//
// An item: { kind, chapter, text, actions: [{id, label}] }.
//   kind 'extra'    the narration has a chapter the outline does not      -> drop (asks once)
//   kind 'missing'  the outline has a chapter the narration does not      -> write | add_empty
//   kind 'empty'    the narration has the chapter but with no text        -> write | add_beat
//   kind 'order'    the narration's chapters are in another order         -> order
export const ACTION = {
  drop: 'Xóa chương này khỏi lời dẫn',
  write: 'Viết chương này',
  add_empty: 'Thêm chương trống',
  add_beat: '+ Dòng',
  order: 'Sắp xếp theo dàn ý',
};
const act = (...ids) => ids.map((id) => ({ id, label: ACTION[id] }));
const title = (outline, id) => (outline?.chapters || []).find((c) => c.id === id)?.title || '';
const name = (outline, id) => `${id}${title(outline, id) ? ' ' + title(outline, id) : ''}`;

export function chapterDiffItems(diff, outline = null, narration = null) {
  const out = [];
  const ttl = (id) => (narration?.chapters || []).find((c) => c.id === id)?.title || '';
  for (const id of diff?.not_in_outline || []) out.push({ kind: 'extra', chapter: id, text: `Chương ${id}${ttl(id) ? ' ' + ttl(id) : ''} có trong lời dẫn nhưng không có trong dàn ý.`, actions: act('drop') });
  for (const id of diff?.missing_in_narration || []) out.push({ kind: 'missing', chapter: id, text: `Chương ${name(outline, id)} có trong dàn ý nhưng lời dẫn chưa có.`, actions: act('write', 'add_empty') });
  for (const id of diff?.empty_in_narration || []) out.push({ kind: 'empty', chapter: id, text: `Chương ${name(outline, id)} chưa có chữ nào trong lời dẫn.`, actions: act('write', 'add_beat') });
  if (diff?.order) out.push({ kind: 'order', chapter: null, text: 'Các chương của lời dẫn xếp khác thứ tự trong dàn ý.', actions: act('order') });
  return out;
}
/** What the Viết chương này button of a chapter header should say and whether to show the drop button. */
export function headerRole(chapterId, outline) {
  if (!outline) return { inOutline: true };
  return { inOutline: (outline.chapters || []).some((c) => c.id === chapterId) };
}
