// Step 1 of an existing project: the dossier of the chosen painting and the sources included (the brief the script step uses).
import { api } from '../api.js';
import { h } from '../util.js';
import { LOW_TRUST } from '../labels.js';
import { nextOpenable } from '../stepper.js';
import { projectHash } from '../router.js';

export async function mount(host, { shell, scope, pipeline }) {
  const pid = pipeline.project;
  const root = h('div', { class: 'artv' });
  host.append(root);
  root.append(h('div', { class: 'muted', text: 'Đang tải hồ sơ...' }));
  const b = await api.get(`/api/projects/${encodeURIComponent(pid)}/brief`);
  const p = b.painting, next = nextOpenable(pipeline.steps, 'artwork');
  const paraText = (s) => s.paragraphs.map((x) => (x.section && x.n === 1 ? x.section + '\n' : '') + x.text).join('\n\n');
  const src = (s) => {
    const box = h('pre', { class: 'text', hidden: true });
    const tog = h('button', { class: 'small', text: 'Xem văn bản', onclick: () => { box.hidden = !box.hidden; tog.textContent = box.hidden ? 'Xem văn bản' : 'Ẩn văn bản'; if (!box.textContent) box.textContent = paraText(s); } });
    const [bid, n] = s.work_id.split('/');
    return h('div', { class: 'srcrow', 'data-code': s.code },
      h('div', null, h('b', { text: s.book_title }), ' ', h('span', { class: 'sub', text: `${s.code} · ${s.author || ''} · ${s.words} từ · ${s.paragraphs.length} đoạn` }),
        h('div', null, s.low_trust ? h('span', { class: 'tag lowtrust', title: s.trust_note, text: LOW_TRUST }) : null,
          h('span', { class: 'tag', style: { marginLeft: s.low_trust ? '6px' : '0' }, text: s.included ? 'đang dùng làm nguồn' : 'không dùng làm nguồn' })),
        s.sections?.length ? h('div', { class: 'sub', text: 'Các mục: ' + s.sections.slice(0, 8).join(' · ') + (s.sections.length > 8 ? ' ...' : '') }) : null, box),
      h('div', { style: { display: 'flex', gap: '8px' } }, tog, h('a', { class: 'lnk', href: `#/library/work/${bid}/${Number(n)}`, text: 'Mở mục trong thư viện' })));
  };
  root.replaceChildren(...[
    h('h1', { text: p.title }),
    h('div', { class: 'muted', text: [p.artist, p.year].filter(Boolean).join(', ') + ` · ${b.totals.included}/${b.totals.sources} nguồn đang dùng · ${b.totals.paragraphs} đoạn · ${b.totals.words} từ` }),
    h('div', { class: 'acts' },
      next ? h('button', { class: 'primary', text: `Tiếp tục: ${next.label}`, onclick: () => shell.go(projectHash(pid, next.id)) }) : null,
      pipeline.artwork_key ? h('a', { class: 'lnk', href: `#/library/artwork/${encodeURIComponent(pipeline.artwork_key)}`, text: 'Xem hồ sơ đầy đủ trong thư viện', style: { alignSelf: 'center' } }) : null,
      h('a', { class: 'lnk', href: '#/library', text: 'Chọn tác phẩm khác (video mới)', style: { alignSelf: 'center' } })),
    b.conflicts.length ? h('div', { class: 'panel' }, h('h4', { text: 'Các nguồn không thống nhất' }),
      b.conflicts.map((c) => h('div', { class: 'conflict', text: `${c.field}: ` + c.values.map((v) => `${v.src || v.work_id} ghi "${v.value}"`).join(' / ') }))) : null,
    b.details.length ? h('div', { class: 'panel' }, h('h4', { text: `Chi tiết có tên (${b.details.length})` }), h('div', { class: 'sub', text: b.details.map((d) => `${d.id} ${d.name}`).join(' · ') })) : null,
    h('div', { class: 'panel' }, h('h4', { text: `Nguồn (${b.sources.length})` }), b.sources.map(src)),
    h('div', { class: 'muted', text: 'Hồ sơ này là bản sao đã chép vào dự án lúc tạo. Chọn sách nào làm nguồn: ở bước Kịch bản, cột Nguồn.' })].filter(Boolean));
  return {};
}
