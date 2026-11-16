// Library page: book shelf, works list, work detail, create-project dialog, projects view. Plain ES modules.
import { h, $, toast, modal } from './util.js';

const main = $('#lib-main');
const J = async (url, opts) => {
  const r = await fetch(url, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(body.detail || r.statusText), { status: r.status });
  return body;
};
const KIND = { chapter_per_artwork: 'mỗi chương một tác phẩm', fixed_spread: 'mỗi tác phẩm một đoạn trang cố định', short_entries: 'mục ngắn', themed_chapter: 'chương theo chủ đề' };
const RIGHTS = { pd_likely: 'Có thể hết bản quyền', copyright_likely: 'Có thể còn bản quyền', unknown: 'Chưa rõ bản quyền' };
const STAGE = { selected: 'Đã chọn', outlined: 'Đã duyệt dàn ý', script: 'Có kịch bản', voiced: 'Có giọng đọc', storyboard: 'Có storyboard', approved: 'Đã duyệt', rendered: 'Đã dựng xong' };
const BOOKNAME = {};
const esc = encodeURIComponent;

const rightsTag = (r) => h('span', { class: 'tag ' + r.status, title: `Ước lượng tự động, chỉ để tham khảo. Căn cứ: ${r.basis}`, text: RIGHTS[r.status] + ' (ước lượng)' });
const stageTag = (s) => h('span', { class: 'tag stage ' + s, text: STAGE[s] || s });
const centuryLabel = (c) => (c === null || c === undefined ? '' : c <= 0 ? 'trước CN' : `TK ${c}`);
const yearTxt = (w) => w.year || '';

function nav(active) {
  document.querySelectorAll('#lib-nav a').forEach((a) => a.classList.toggle('active', a.dataset.nav === active));
}
const setMain = (...k) => { main.replaceChildren(...k.filter(Boolean)); window.scrollTo(0, 0); };
const crumb = (...parts) => h('div', { class: 'crumb' }, ...parts.flatMap((p, i) => (i ? [' / ', p] : [p])));

// ------------------------------------------------------------------ shelf
async function shelf() {
  nav('shelf');
  const books = await J('/api/library/books');
  books.forEach((b) => { BOOKNAME[b.id] = b.title; });
  setMain(h('h1', { class: 'lib-h', text: 'Kệ sách' }),
    h('div', { class: 'muted', text: 'Chọn một cuốn sách, mở một tác phẩm, rồi tạo dự án video từ nó.' }),
    h('div', { class: 'shelf' }, books.map((b) => h('div', { class: 'book-card', onclick: () => { location.hash = `#/book/${b.id}`; } },
      h('div', { class: 'cover' }, h('img', { src: b.cover_url, alt: b.title, loading: 'lazy' })),
      h('div', { class: 'meta' },
        h('h3', { text: b.title }),
        h('div', { class: 'muted', text: b.author }),
        h('div', { class: 'tags' },
          h('span', { class: 'tag ' + b.pdf_type, text: b.pdf_type === 'scan' ? 'bản scan (OCR)' : 'bản số' }),
          h('span', { class: 'tag', text: `${b.n_works} ${b.unit === 'themed_chapter' ? 'chương' : 'mục'}` }),
          h('span', { class: 'tag', text: `${b.n_with_project} đã có dự án` })),
        h('div', { class: 'sub', text: KIND[b.unit] || b.unit }))))));
}

// ------------------------------------------------------------------ works list
async function worksList(bid) {
  nav('shelf');
  const books = await J('/api/library/books');
  books.forEach((b) => { BOOKNAME[b.id] = b.title; });
  const book = books.find((b) => b.id === bid);
  if (!book) throw new Error('Không có sách này');
  const f = { q: '', century: '', rights: '', multi: false };
  const body = h('div');
  const q = h('input', { type: 'search', placeholder: 'Tìm theo tên tranh, hoạ sĩ, năm...', oninput: (e) => { f.q = e.target.value; refresh(); } });
  const cen = h('select', { onchange: (e) => { f.century = e.target.value; refresh(); } }, h('option', { value: '', text: 'Mọi thế kỷ' }),
    h('option', { value: '0', text: 'Trước Công nguyên' }), ...Array.from({ length: 21 }, (_, i) => h('option', { value: String(i + 1), text: `Thế kỷ ${i + 1}` })));
  const rig = h('select', { onchange: (e) => { f.rights = e.target.value; refresh(); } }, h('option', { value: '', text: 'Mọi bản quyền (ước lượng)' }),
    ...Object.entries(RIGHTS).map(([k, v]) => h('option', { value: k, text: v })));
  const mul = h('input', { type: 'checkbox', onchange: (e) => { f.multi = e.target.checked; refresh(); } });
  const count = h('span', { class: 'muted' });
  let timer;
  async function refresh() {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const p = new URLSearchParams();
      if (f.q) p.set('q', f.q); if (f.century !== '') p.set('century', f.century); if (f.rights) p.set('rights', f.rights); if (f.multi) p.set('multi', 'true');
      let ws;
      try { ws = await J(`/api/library/books/${bid}/works?${p}`); } catch (e) { toast(e.message, 'err'); return; }
      count.textContent = `${ws.length} / ${book.n_works}`;
      body.replaceChildren(ws.length ? worksTable(ws) : h('div', { class: 'empty', text: 'Không có mục nào khớp bộ lọc.' }));
    }, 120);
  }
  setMain(crumb(h('a', { href: '#/books', text: 'Kệ sách' }), book.title),
    h('h1', { class: 'lib-h', text: book.title }), h('div', { class: 'muted', text: `${book.author} · ${book.pages} trang · ${book.pdf_type === 'scan' ? 'bản scan, văn bản qua OCR' : 'bản số'}` }),
    h('div', { class: 'sub', text: book.notes }),
    h('div', { class: 'toolbar' }, q, cen, rig, h('label', { class: 'chk' }, mul, 'Có trong từ 2 sách trở lên'), h('span', { class: 'grow' }), count),
    body);
  refresh();
}

function worksTable(ws) {
  return h('table', { class: 'works' },
    h('thead', null, h('tr', null, h('th'), h('th', { text: 'Tác phẩm' }), h('th', { text: 'Hoạ sĩ' }), h('th', { text: 'Năm' }),
      h('th', { class: 'num', text: 'Số từ' }), h('th', { text: 'Cũng có trong' }), h('th', { text: 'Bản quyền (ước lượng)' }), h('th', { text: 'Dự án' }))),
    h('tbody', null, ws.map((w) => h('tr', { class: 'wrow', onclick: () => { location.hash = w.artwork_key ? `#/artwork/${w.artwork_key}` : `#/work/${w.book_id}/${w.n}`; } },
      h('td', { class: 'thumb' }, h('img', { src: w.thumb_url, loading: 'lazy', alt: '' })),
      h('td', null, h('div', { class: 'ttl', text: `${w.n}. ${w.title}` }), w.headline ? h('div', { class: 'sub', text: w.headline }) : null,
        h('div', { class: 'sub', text: `trang PDF ${w.pdf_pages[0]}-${w.pdf_pages[1]}` })),
      h('td', { text: w.artist || '' }), h('td', { text: yearTxt(w) }), h('td', { class: 'num', text: w.words }),
      h('td', null, h('div', { class: 'badges' }, w.also_in.map((o) => h('span', { class: 'tag also', title: 'Mở mục này', text: shortBook(o.book_id),
        onclick: (e) => { e.stopPropagation(); location.hash = `#/work/${o.book_id}/${o.n}`; } })))),
      h('td', null, rightsTag(w.rights)),
      h('td', null, w.projects.length ? w.projects.map((p) => stageTag(p.stage)) : h('span', { class: 'muted', text: '-' }))))));
}
const SHORT = { payne_gae: 'Payne', hodge_aid: 'Hodge', hagen_wgps: 'Hagen', grovier_nws: 'Grovier', brookehitching_mad: 'Brooke-Hitching', dasal_artcurious: 'Dasal' };
const shortBook = (id) => SHORT[id] || id;

// ------------------------------------------------------------------ work detail
function lightbox(url) {
  const lb = h('div', { class: 'lightbox', onclick: () => lb.remove() }, h('img', { src: url }));
  const k = (e) => { if (e.key === 'Escape') { lb.remove(); document.removeEventListener('keydown', k); } };
  document.addEventListener('keydown', k);
  document.body.append(lb);
}

async function workDetail(bid, n) {
  nav('shelf');
  const w = await J(`/api/library/works/${bid}/${n}`);
  let art = null;
  try { art = await J(`/api/library/artworks/${esc(w.artwork_key)}`); } catch { /* none */ }
  if (!BOOKNAME[bid]) (await J('/api/library/books')).forEach((b) => { BOOKNAME[b.id] = b.title; });
  const preview = h('div', { class: 'preview-box' });
  const also = (art?.works_detail || []).filter((o) => o.id !== w.id);
  const other = (o) => h('div', { class: 'alsoitem' }, h('img', { src: o.thumb_url, alt: '' }),
    h('div', { style: { flex: 1 } }, h('div', { class: 'ttl', text: BOOKNAME[o.book_id] || o.book_id }), h('div', { class: 'sub', text: `${o.title} · trang PDF ${o.pdf_pages[0]}-${o.pdf_pages[1]}` })),
    h('button', { class: 'small', text: 'Xem nhanh', onclick: () => showPreview(o) }),
    h('button', { class: 'small', text: 'Mở', onclick: () => { location.hash = `#/work/${o.book_id}/${o.n}`; } }));
  async function showPreview(o) {
    preview.replaceChildren(h('div', { class: 'muted', text: 'Đang tải...' }));
    const d = await J(`/api/library/works/${o.book_id}/${o.n}`);
    preview.replaceChildren(h('div', { class: 'ttl', text: `${BOOKNAME[o.book_id]}: ${d.title}` }),
      h('div', { class: 'pages', style: { margin: '8px 0' } }, d.pages.slice(0, 2).map((p) => h('div', null, h('img', { src: p.url, onclick: () => lightbox(p.url.replace('w=900', 'w=1500')) })))),
      d.ocr ? h('div', { class: 'note', text: 'Văn bản OCR, có thể sai chữ.' }) : null,
      h('pre', { class: 'text', text: d.text.slice(0, 2500) + (d.text.length > 2500 ? '\n...' : '') }));
  }
  const mine = w.projects || [];
  setMain(crumb(h('a', { href: '#/books', text: 'Kệ sách' }), h('a', { href: `#/book/${bid}`, text: BOOKNAME[bid] || bid }), `${w.n}. ${w.title}`),
    h('div', { style: { display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' } },
      h('h1', { class: 'lib-h', text: w.title }), h('span', { class: 'grow' }),
      h('button', { class: 'primary', text: 'Tạo dự án', onclick: () => createDialog(w, also) })),
    h('div', { class: 'muted', text: [w.artist, w.year, `trang PDF ${w.pdf_pages[0]}-${w.pdf_pages[1]}`, `${w.words} từ`].filter(Boolean).join(' · ') }),
    w.headline ? h('div', { class: 'sub', text: w.headline }) : null,
    h('div', { class: 'tags', style: { margin: '8px 0' } }, rightsTag(w.rights), ...mine.map((p) => stageTag(p.stage)), h('a', { class: 'lnk', href: `#/artwork/${w.artwork_key}`, text: 'Xem hồ sơ tác phẩm (đã gộp các sách)' })),
    h('div', { class: 'detail' },
      h('div', null,
        h('div', { class: 'panel' }, h('h4', { text: `Các trang của mục (${w.pages.length})` }),
          h('div', { class: 'pages' }, w.pages.map((p) => h('div', null, h('img', { src: p.url, loading: 'lazy', title: 'Bấm để phóng to', onclick: () => lightbox(p.url.replace('w=900', 'w=1600')) }), h('div', { class: 'pagecap', text: `trang PDF ${p.page}` }))))),
        w.images.length ? h('div', { class: 'panel' }, h('h4', { text: `Hình nhúng trong sách (${w.images.length})` }),
          h('div', { class: 'imgs' }, w.images.map((im) => h('div', null, h('img', { src: im.url, loading: 'lazy', onclick: () => lightbox(im.url.replace('w=700', 'w=1600')) }), h('div', { class: 'pagecap', text: `${im.width}x${im.height}, trang ${im.page}` }))))) : null),
      h('div', null,
        h('div', { class: 'panel' }, h('h4', { text: 'Văn bản trích' }, w.ocr ? h('span', { class: 'tag scan', text: 'OCR' }) : h('span', { class: 'tag digital', text: 'lớp chữ gốc' }),
          h('span', { class: 'tag', text: 'nguồn: ' + w.text_source })),
          w.ocr ? h('div', { class: 'note', text: 'Bản scan: văn bản do OCR, có thể sai chữ hoặc mất dấu.' }) : null,
          h('pre', { class: 'text', text: w.text || '(không có chữ)' })),
        w.headings?.length ? h('div', { class: 'panel' }, h('h4', { text: 'Tiêu đề phụ trong mục' }), h('div', { class: 'sub', text: w.headings.join(' · ') })) : null,
        h('div', { class: 'panel' }, h('h4', { text: `Cùng tác phẩm trong sách khác (${also.length})` }),
          also.length ? h('div', { class: 'alsolist' }, also.map(other)) : h('div', { class: 'muted', text: 'Chưa thấy trong sách nào khác (ghép rất thận trọng).' }), preview))));
}

function createDialog(w, also) {
  const all = [w, ...also.map((o) => ({ ...o, book_id: o.book_id }))];
  const checks = all.map((x, i) => ({ x, el: h('input', { type: 'checkbox', checked: true }) }));
  const slug = h('input', { type: 'text', placeholder: 'tự đặt từ tên tác phẩm', spellcheck: false });
  const err = h('div', { class: 'note' });
  const create = h('button', { class: 'primary', text: 'Tạo dự án', onclick: async () => {
    const ids = checks.filter((c) => c.el.checked).map((c) => c.x.id);
    if (!ids.length) { err.textContent = 'Chọn ít nhất một sách.'; return; }
    create.disabled = true; err.textContent = '';
    try {
      const p = await J('/api/library/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ work_ids: ids, slug: slug.value.trim() || null }) });
      m.close(); toast(`Đã tạo dự án ${p.id}`, 'ok'); location.hash = '#/projects';
    } catch (e) { err.textContent = e.message; create.disabled = false; }
  } });
  const m = modal({ title: 'Tạo dự án video từ tác phẩm này', cls: 'dlg',
    body: h('div', { class: 'body', style: { width: '560px' } },
      h('div', { class: 'muted', text: 'Tick các sách có mục cùng tác phẩm để gộp thành một dự án. Dự án chỉ lấy văn bản trích; chưa tạo storyboard.' }),
      h('div', { style: { marginTop: '10px' } }, checks.map(({ x, el }) => h('label', { class: 'ck' }, el, h('span', null, h('b', { text: BOOKNAME[x.book_id] || x.book_id }), h('span', { class: 'sub', text: `  ${x.title} · trang PDF ${x.pdf_pages[0]}-${x.pdf_pages[1]}` }))))),
      h('div', { class: 'dlg-field' }, h('label', { text: 'Tên thư mục dự án (slug: a-z, 0-9, - và _)' }), slug), err),
    footer: h('footer', null, h('button', { text: 'Huỷ', onclick: () => m.close() }), create) });
}

// ------------------------------------------------------------------ projects
async function projectsView() {
  nav('projects');
  const ps = await J('/api/projects');
  const hasStory = ps.filter((p) => p.has_storyboard), none = ps.filter((p) => !p.has_storyboard);
  const row = (p) => h('tr', null,
    h('td', null, h('div', { class: 'ttl', text: p.title }), h('div', { class: 'sub mono', text: p.id })),
    h('td', null, stageTag(p.stage)),
    h('td', null, (p.sources || []).map((s) => h('span', { class: 'tag also', text: shortBook(s.book_id), onclick: () => { location.hash = `#/work/${s.work_id.split('/')[0]}/${Number(s.work_id.split('/')[1])}`; } }))),
    h('td', null, (p.sources || []).length ? h('a', { class: 'lnk', href: `script.html?project=${esc(p.id)}`, text: 'Kịch bản', style: { marginRight: '12px' } }) : null, p.has_storyboard ? h('a', { class: 'lnk', href: `/?project=${esc(p.id)}`, text: 'Mở trong trình biên tập' })
      : h('span', { class: 'nostory', text: 'Chưa có storyboard: bước giọng đọc chưa được xây dựng.' })),
    h('td', { class: 'sub', text: (p.updated_at || '').slice(0, 16).replace('T', ' ') }));
  const tbl = (rows) => h('table', { class: 'works' }, h('thead', null, h('tr', null, h('th', { text: 'Dự án' }), h('th', { text: 'Giai đoạn' }), h('th', { text: 'Nguồn sách' }), h('th', { text: 'Tiếp theo' }), h('th', { text: 'Cập nhật' }))),
    h('tbody', null, rows.map(row)));
  setMain(h('h1', { class: 'lib-h', text: 'Dự án' }), h('div', { class: 'muted', text: `${ps.length} dự án` }),
    h('div', { class: 'panel', style: { marginTop: '12px' } }, h('h4', { text: 'Chưa có storyboard (mới chọn từ sách)' }), none.length ? tbl(none) : h('div', { class: 'muted', text: 'Không có.' })),
    h('div', { class: 'panel' }, h('h4', { text: 'Đã có storyboard' }), hasStory.length ? tbl(hasStory) : h('div', { class: 'muted', text: 'Không có.' })));
}


// ------------------------------------------------------------------ artworks (default view)
const goto = (h_) => { if (location.hash === h_) route(); else location.hash = h_; };
const post = (url, body) => J(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
const bookBadges = (books, low = []) => h('div', { class: 'badges' }, books.map((b) => h('span', { class: 'tag also' + (low.includes(b) ? ' lowtrust' : ''), title: low.includes(b) ? LOWTXT : '', text: shortBook(b) + (low.includes(b) ? ' (dịch máy)' : '') })));
const LOWTXT = 'bản dịch máy, không dùng làm nguồn sự kiện';
const lowTag = (title) => h('span', { class: 'tag lowtrust', title: title || LOWTXT, text: LOWTXT });
const textTag = (t) => (t ? h('span', { class: 'tag ' + (t === 'clean' ? 'digital' : t === 'layer' ? 'scan' : ''), title: 'Nguồn văn bản: clean = đã làm sạch, layer = lớp chữ gốc của PDF', text: t }) : null);
const FILTER = { q: '', sort: 'sources', century: '', project: '', multi: false, themes: false };

async function artworksView() {
  nav('artworks');
  const f = FILTER;
  const body = h('div'), count = h('span', { class: 'muted' });
  const q = h('input', { type: 'search', value: f.q, placeholder: 'Tìm theo tên tranh, hoạ sĩ, năm...', oninput: (e) => { f.q = e.target.value; refresh(); } });
  const sort = h('select', { onchange: (e) => { f.sort = e.target.value; refresh(); } },
    ...[['sources', 'Nhiều sách nhất trước'], ['words', 'Nhiều chữ nhất trước'], ['title', 'Tên A-Z'], ['year', 'Theo thế kỷ']].map(([v, t]) => h('option', { value: v, text: t, selected: f.sort === v })));
  const cen = h('select', { onchange: (e) => { f.century = e.target.value; refresh(); } }, h('option', { value: '', text: 'Mọi thế kỷ' }),
    h('option', { value: '0', text: 'Trước Công nguyên', selected: f.century === '0' }), ...Array.from({ length: 21 }, (_, i) => h('option', { value: String(i + 1), text: `Thế kỷ ${i + 1}`, selected: f.century === String(i + 1) })));
  const pr = h('select', { onchange: (e) => { f.project = e.target.value; refresh(); } },
    ...[['', 'Dự án: tất cả'], ['true', 'Đã có dự án'], ['false', 'Chưa có dự án']].map(([v, t]) => h('option', { value: v, text: t, selected: f.project === v })));
  const mul = h('input', { type: 'checkbox', checked: f.multi, onchange: (e) => { f.multi = e.target.checked; refresh(); } });
  const thm = h('input', { type: 'checkbox', checked: f.themes, onchange: (e) => { f.themes = e.target.checked; refresh(); } });
  let timer;
  function refresh() {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const p = new URLSearchParams({ sort: f.sort, kind: f.themes ? '' : 'artwork' });
      if (f.q) p.set('q', f.q); if (f.century !== '') p.set('century', f.century); if (f.project) p.set('has_project', f.project); if (f.multi) p.set('min_sources', '2');
      let rows;
      try { rows = await J(`/api/library/artworks?${p}`); } catch (e) { toast(e.message, 'err'); return; }
      count.textContent = `${rows.length} tác phẩm`;
      body.replaceChildren(rows.length ? artworksTable(rows) : h('div', { class: 'empty', text: 'Không có tác phẩm nào khớp bộ lọc.' }));
    }, 120);
  }
  setMain(h('h1', { class: 'lib-h', text: 'Tác phẩm' }),
    h('div', { class: 'muted', text: 'Mỗi tác phẩm là một video. Các sách cùng nói về một tranh đã được gộp vào một hồ sơ. Bản quyền chỉ là thông tin ước lượng, không chặn gì.' }),
    h('div', { class: 'toolbar' }, q, sort, cen, pr, h('label', { class: 'chk' }, mul, 'Có trong từ 2 sách'), h('label', { class: 'chk' }, thm, 'Gồm chương chủ đề (ArtCurious)'), h('span', { class: 'grow' }), count), body);
  refresh();
}

function artworksTable(rows) {
  return h('table', { class: 'works' },
    h('thead', null, h('tr', null, h('th'), h('th', { text: 'Tác phẩm' }), h('th', { text: 'Hoạ sĩ' }), h('th', { text: 'Năm' }), h('th', { text: 'Sách' }),
      h('th', { class: 'num', text: 'Số chữ' }), h('th', { text: 'Bản quyền (ước lượng)' }), h('th', { text: 'Dự án' }))),
    h('tbody', null, rows.map((a) => h('tr', { class: 'wrow', onclick: () => { location.hash = `#/artwork/${a.artwork_key}`; } },
      h('td', { class: 'thumb' }, h('img', { src: a.thumb_url, loading: 'lazy', alt: '' })),
      h('td', null, h('div', { class: 'ttl', text: a.title }), a.n_conflicts ? h('div', { class: 'sub conflict', text: `${a.n_conflicts} chỗ các sách ghi khác nhau` }) : null),
      h('td', { text: a.artist || '' }), h('td', { text: a.year || '' }),
      h('td', null, bookBadges(a.books, a.low_trust_books), a.only_low_trust ? h('div', { class: 'sub conflict', text: 'Chỉ có trong bản dịch máy, không dùng làm nguồn sự kiện' }) : null),
      h('td', { class: 'num' }, a.words_normal, a.words_low ? h('div', { class: 'sub', text: `+ ${a.words_low} (dịch máy)` }) : null, textTag(a.text_source)),
      h('td', null, rightsTag(a.rights)),
      h('td', null, a.projects.length ? a.projects.map((p) => stageTag(p.stage)) : h('span', { class: 'muted', text: '-' }))))));
}

// ------------------------------------------------------------------ artwork dossier
async function artworkDetail(key) {
  nav('artworks');
  const a = await J(`/api/library/artworks/${key}`);
  const d = a.dossier;
  if (!d) throw new Error('Chưa có hồ sơ cho tác phẩm này (chạy python -m bti.library dossiers)');
  (await J('/api/library/books')).forEach((b) => { BOOKNAME[b.id] = b.title; });
  const idn = d.identity;
  const conflictFields = new Set(d.conflicts.map((c) => c.field));
  const cell = (label, field, val) => h('div', { class: 'idcell' + (conflictFields.has(field) ? ' conflict' : '') }, h('div', { class: 'sub', text: label }), h('div', { class: 'ttl', text: val || '(chưa rõ)' }),
    conflictFields.has(field) ? h('div', { class: 'sub', text: 'Các sách ghi khác nhau' }) : null);
  const tabs = h('div', { class: 'tabs' }), pane = h('div');
  const showTab = async (i) => {
    [...tabs.children].forEach((b, j) => b.classList.toggle('active', i === j));
    const s = d.sources[i];
    pane.replaceChildren(h('div', { class: 'muted', text: 'Đang tải...' }));
    const t = await J(s.text_url);
    const o = s.outline;
    pane.replaceChildren(...[
      s.trust === 'low' ? h('div', { class: 'note lowbox', text: s.trust_note || LOWTXT }) : null,
      h('div', { class: 'tags', style: { margin: '6px 0' } }, h('span', { class: 'tag', text: `${s.words} chữ` }), s.trust === 'low' ? lowTag(s.trust_note) : null, textTag(s.text_source), s.ocr ? h('span', { class: 'tag scan', text: 'OCR' }) : null,
        s.headline ? h('span', { class: 'tag', text: s.headline }) : null, h('span', { class: 'tag', text: `trang PDF ${s.pdf_pages[0]}-${s.pdf_pages[1]}` }), h('span', { class: 'grow', style: { flex: 1 } }),
        h('button', { class: 'small', text: 'Mở mục này', onclick: () => { location.hash = `#/work/${s.book_id}/${s.n}`; } }),
        d.sources.length > 1 ? h('button', { class: 'small danger', text: 'Tách', title: 'Tách mục này thành tác phẩm riêng', onclick: () => splitDialog(s) }) : null),
      s.title !== idn.title || (s.artist && s.artist !== idn.artist) || (s.year && s.year !== idn.year) ? h('div', { class: 'sub' }, `Sách này ghi: ${[s.title, s.artist, s.year].filter(Boolean).join(' · ')}`) : null,
      h('div', { class: 'two' },
        h('div', null,
          h('div', { class: 'panel' }, h('h4', { text: 'Dàn ý của mục (theo cấu trúc văn bản)' }),
            o.headings.length ? h('ol', { class: 'outline' }, o.headings.map((x) => h('li', { class: 'lv' + x.level, text: x.text + (x.page ? `  (tr. ${x.page})` : '') }))) : h('div', { class: 'muted', text: 'Không có tiêu đề rõ ràng.' }),
            o.meta?.length ? h('div', { class: 'sub', text: 'Thông tin in dưới tiêu đề: ' + o.meta.join(' · ') }) : null),
          o.captions.length ? h('div', { class: 'panel' }, h('h4', { text: `Chú thích hình (${o.captions.length})` }), h('ul', { class: 'caps' }, o.captions.map((c) => h('li', { text: c.text })))) : null,
          h('div', { class: 'panel' }, h('h4', { text: 'Các trang' }), h('div', { class: 'pages' }, s.pages.map((p) => h('div', null, h('img', { src: p.url, loading: 'lazy', onclick: () => lightbox(p.url.replace('w=900', 'w=1600')) }), h('div', { class: 'pagecap', text: `trang PDF ${p.page}` })))))),
        h('div', { class: 'panel' }, h('h4', { text: 'Văn bản (chỉ phần thân bài)' }), s.ocr ? h('div', { class: 'note', text: 'Bản scan: văn bản do OCR, có thể sai chữ.' }) : null, h('pre', { class: 'text', text: t.text })))].filter(Boolean));
  };
  d.sources.forEach((s, i) => tabs.append(h('button', { text: `${BOOKNAME[s.book_id] || s.book_id} (${s.words})${s.trust === 'low' ? ' ⚠' : ''}`, onclick: () => showTab(i) })));
  const mine = a.projects || [];
  setMain(crumb(h('a', { href: '#/', text: 'Tác phẩm' }), idn.title),
    h('div', { style: { display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' } }, h('h1', { class: 'lib-h', text: idn.title }), h('span', { class: 'grow' }),
      h('button', { text: 'Gộp với…', onclick: () => mergeDialog(a) }),
      h('button', { class: 'primary', text: 'Tạo dự án', onclick: () => createArtworkDialog(a) })),
    h('div', { class: 'idrow' }, cell('Tên tác phẩm', 'title', idn.title), cell('Hoạ sĩ', 'artist', idn.artist), cell('Năm', 'year', idn.year)),
    d.conflicts.length ? h('div', { class: 'panel conflictbox' }, h('h4', { text: 'Các sách ghi khác nhau' }),
      d.conflicts.map((c) => h('div', null, h('b', { text: { title: 'Tên', artist: 'Hoạ sĩ', year: 'Năm' }[c.field] + ': ' }),
        c.values.map((v) => h('span', { class: 'tag', title: v.work_id, text: `${shortBook(v.work_id.split('/')[0])}: ${v.value}` }))))) : null,
    h('div', { class: 'tags', style: { margin: '8px 0' } }, rightsTag(d.rights), h('span', { class: 'tag', text: `${d.totals.books} sách · ${d.totals.words_normal} chữ nguồn thường` }), d.totals.words_low ? h('span', { class: 'tag', text: `${d.totals.words_low} chữ dịch máy` }) : null, d.only_low_trust ? lowTag('Tác phẩm này chỉ có trong bản dịch máy') : null, textTag(d.text_source),
      ...mine.map((p) => stageTag(p.stage)), ...(d.kind === 'theme' ? [h('span', { class: 'tag', text: 'chương chủ đề' })] : [])),
    d.details?.length ? h('div', { class: 'panel' }, h('h4', { text: `Các chi tiết có tên (Hodge) (${d.details.length})` }), h('div', { class: 'sub', text: d.details.join(' · ') })) : null,
    h('div', { class: 'panel' }, h('h4', { text: `Nguồn (${d.sources.length})` }), tabs, pane),
    d.images.length ? h('div', { class: 'panel' }, h('h4', { text: `Hình nhúng trong sách số (${d.images.length})` }),
      h('div', { class: 'imgs' }, d.images.map((im) => h('div', null, h('img', { src: im.url, loading: 'lazy', onclick: () => lightbox(im.url.replace('w=700', 'w=1600')) }),
        h('div', { class: 'pagecap', text: `${shortBook(im.work_id.split('/')[0])} · ${im.width}x${im.height} · tr. ${im.page}` }))))) : null);
  showTab(0);
}

function createArtworkDialog(a) {
  const d = a.dossier;
  const allLow = d.sources.every((s) => s.trust === 'low');
  const checks = d.sources.map((s) => ({ s, el: h('input', { type: 'checkbox', checked: allLow || s.trust !== 'low' }) }));
  const slug = h('input', { type: 'text', placeholder: 'tự đặt từ tên tác phẩm', spellcheck: false });
  const err = h('div', { class: 'note' });
  const go = h('button', { class: 'primary', text: 'Tạo dự án', onclick: async () => {
    const ex = checks.filter((c) => !c.el.checked).map((c) => c.s.work_id);
    if (ex.length === checks.length) { err.textContent = 'Giữ lại ít nhất một nguồn.'; return; }
    go.disabled = true; err.textContent = '';
    try { const p = await post('/api/library/projects', { artwork_key: a.artwork_key, exclude: ex, slug: slug.value.trim() || null }); m.close(); toast(`Đã tạo dự án ${p.id}`, 'ok'); location.hash = '#/projects'; }
    catch (e) { err.textContent = e.message; go.disabled = false; }
  } });
  const m = modal({ title: 'Tạo dự án video từ tác phẩm', cls: 'dlg', body: h('div', { class: 'body', style: { width: '560px' } },
    h('div', { class: 'muted', text: 'Mặc định lấy mọi nguồn. Bỏ tick để loại một nguồn. Dự án nhận một bản sao hồ sơ và văn bản; chưa tạo storyboard.' }),
    h('div', { style: { marginTop: '10px' } }, checks.map(({ s, el }) => h('label', { class: 'ck' }, el, h('span', null, h('b', { text: BOOKNAME[s.book_id] || s.book_id }), h('span', { class: 'sub', text: `  ${s.words} chữ · ${s.text_source}` }), s.trust === 'low' ? lowTag(s.trust_note) : null)))),
    h('div', { class: 'dlg-field' }, h('label', { text: 'Tên thư mục dự án (slug: a-z, 0-9, - và _)' }), slug), err),
    footer: h('footer', null, h('button', { text: 'Huỷ', onclick: () => m.close() }), go) });
}

function mergeDialog(a) {
  const res = h('div', { class: 'alsolist', style: { marginTop: '10px', maxHeight: '320px', overflow: 'auto' } });
  const err = h('div', { class: 'note' });
  const input = h('input', { type: 'search', placeholder: 'Tìm tác phẩm cần gộp vào...', style: { width: '100%' } });
  let timer;
  const search = () => { clearTimeout(timer); timer = setTimeout(async () => {
    const rows = await J(`/api/library/artworks?kind=&sort=title&q=${esc(input.value)}`);
    res.replaceChildren(...rows.filter((r) => r.artwork_key !== a.artwork_key).slice(0, 40).map((r) => h('div', { class: 'alsoitem' }, h('img', { src: r.thumb_url, alt: '' }),
      h('div', { style: { flex: 1 } }, h('div', { class: 'ttl', text: r.title }), h('div', { class: 'sub', text: `${r.artist || ''} ${r.year || ''} · ${r.books.map(shortBook).join(', ')}` })),
      h('button', { class: 'small primary', text: 'Gộp', onclick: async () => {
        if (!confirm(`Gộp "${r.title}" vào "${a.dossier.identity.title}"?`)) return;
        try { const o = await post('/api/library/artworks/merge', { key: a.artwork_key, with: r.artwork_key }); m.close(); toast('Đã gộp', 'ok'); goto(`#/artwork/${o.artwork_key}`); }
        catch (e) { err.textContent = e.message; } } }))));
  }, 150); };
  input.oninput = search;
  const m = modal({ title: `Gộp "${a.dossier.identity.title}" với…`, body: h('div', { class: 'body', style: { width: '600px' } },
    h('div', { class: 'muted', text: 'Chọn tác phẩm khác thực ra là cùng một bức tranh. Ghi vào library/overrides/artworks.json.' }), input, res, err),
    footer: h('footer', null, h('button', { text: 'Đóng', onclick: () => m.close() })) });
  search();
}

function splitDialog(s) {
  if (!confirm(`Tách "${BOOKNAME[s.book_id] || s.book_id}: ${s.title}" thành tác phẩm riêng?`)) return;
  post('/api/library/artworks/split', { work_id: s.work_id }).then((o) => { toast('Đã tách', 'ok'); goto(`#/artwork/${o.artwork_key}`); }).catch((e) => toast(e.message, 'err'));
}

// ------------------------------------------------------------------ router
async function route() {
  const hash = location.hash.replace(/^#/, '') || '/';
  const parts = hash.split('/').filter(Boolean);
  try {
    if (!parts.length) await artworksView();
    else if (parts[0] === 'books') await shelf();
    else if (parts[0] === 'artwork' && parts[1]) await artworkDetail(parts.slice(1).join('/'));
    else if (parts[0] === 'book' && parts[1]) await worksList(parts[1]);
    else if (parts[0] === 'work' && parts[2]) await workDetail(parts[1], Number(parts[2]));
    else if (parts[0] === 'projects') await projectsView();
    else await artworksView();
  } catch (e) {
    setMain(h('div', { class: 'empty', text: 'Lỗi: ' + (e.message || e) }));
  }
}
window.addEventListener('hashchange', route);
route();
