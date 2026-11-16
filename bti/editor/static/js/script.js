// "Kịch bản" page: sources | outline | narration. Plain ES modules, no build step.
import { h, $, toast, modal } from './util.js';

const S = { pid: null, brief: null, models: [], model: null, tab: null, search: '', hl: [], focus: 'narr' };
const D = { outline: null, narr: null };                       // drafts (what is on screen)
const R = { outline: null, narr: null };                       // saved revisions
const ST = { outline: {}, narr: {} };                          // approved, stale, issues, last_paste
const dirty = { outline: false, narr: false };
const hist = { outline: { past: [], future: [], key: '', at: 0 }, narr: { past: [], future: [], key: '', at: 0 } };
let jobPoll = null, currentJob = null;

const J = async (url, opts) => {
  const r = await fetch(url, opts);
  const text = await r.text();
  let body = {};
  try { body = JSON.parse(text); } catch { body = { detail: text.slice(0, 300) }; }
  if (!r.ok) throw Object.assign(new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)), { status: r.status, body });
  return body;
};
const send = (method, url, body) => J(url, { method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}) });
const P = () => `/api/projects/${S.pid}`;
const words = (t) => (String(t).match(/\S*\w\S*/g) || []).length;
const ids = (s) => String(s).split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
const clone = (o) => JSON.parse(JSON.stringify(o));
const fit = (ta) => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight + 2, 520) + 'px'; };
const fitAll = (root) => requestAnimationFrame(() => root.querySelectorAll('textarea:not(.big)').forEach(fit));

// ------------------------------------------------------------------ messages for the validation codes (Vietnamese)
const CODE = {
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
const LEVEL = { error: 'Lỗi', warning: 'Cảnh báo', info: 'Thông tin' };

// ------------------------------------------------------------------ history
function mutate(kind, fn, key = '') {
  const hs = hist[kind], now = Date.now();
  if (!(key && hs.key === key && now - hs.at < 1500)) { hs.past.push(JSON.stringify(D[kind])); if (hs.past.length > 200) hs.past.shift(); hs.future = []; }
  hs.key = key; hs.at = now; S.focus = kind;
  fn();
  setDirty(kind, true);
}
function undoRedo(dir) {
  const kind = S.focus, hs = hist[kind];
  const from = dir < 0 ? hs.past : hs.future, to = dir < 0 ? hs.future : hs.past;
  if (!from.length || !D[kind]) return toast('Không còn gì để ' + (dir < 0 ? 'hoàn tác' : 'làm lại'));
  to.push(JSON.stringify(D[kind]));
  D[kind] = JSON.parse(from.pop()); hs.key = '';
  setDirty(kind, true); renderAll();
}
function setDirty(kind, v) { dirty[kind] = v; refreshChrome(); }

// ------------------------------------------------------------------ loading
async function loadAll() {
  S.brief = await J(`${P()}/brief`);
  applyOutline(await J(`${P()}/outline`), true); applyNarr(await J(`${P()}/narration`), true);
  if (!S.tab || !S.brief.sources.some((s) => s.code === S.tab)) S.tab = S.brief.sources[0]?.code || null;
  renderAll();
}
function applyOutline(r, quiet) {
  D.outline = r.outline; R.outline = r.rev; ST.outline = r; dirty.outline = false; if (!quiet) renderAll();
}
function applyNarr(r, quiet) {
  D.narr = r.narration; R.narr = r.rev; ST.narr = r; dirty.narr = false; if (!quiet) renderAll();
}
async function saveKind(kind) {
  if (!D[kind] || !dirty[kind]) return true;
  try {
    if (kind === 'outline') applyOutline(await send('PUT', `${P()}/outline`, { outline: D.outline, base_rev: R.outline }));
    else applyNarr(await send('PUT', `${P()}/narration`, { narration: D.narr, base_rev: R.narr }));
    return true;
  } catch (e) {
    if (e.status === 409) toast('Tệp đã đổi ở nơi khác. Tải lại trang rồi sửa lại.', 'err', 8000); else toast(e.message, 'err');
    return false;
  }
}
const saveAll = async () => { const a = await saveKind('outline'); const b = await saveKind('narr'); if (a && b) toast('Đã lưu', 'ok', 1500); return a && b; };

// ------------------------------------------------------------------ top bar
const approvedFlag = (k) => !!ST[k].approved && !dirty[k];
function refreshChrome() {
  $('#dirty-dot').hidden = !(dirty.outline || dirty.narr);
  const iss = [...(ST.outline.issues || []), ...(ST.narr.issues || [])].filter((i) => i.level !== 'info');
  const c = $('#issue-count'); c.textContent = iss.length; c.className = 'count' + (iss.some((i) => i.level === 'error') ? ' err' : iss.length ? ' warnc' : '');
  const badge = (el, k, label) => {
    const st = ST[k];
    if (!D[k]) { el.textContent = 'chưa có'; el.className = 'badge none'; return; }
    if (dirty[k]) { el.textContent = 'đang sửa, chưa lưu'; el.className = 'badge warn'; }
    else if (st.approved) { el.textContent = 'đã duyệt'; el.className = 'badge ok'; }
    else if (st.stale) { el.textContent = 'duyệt đã cũ'; el.className = 'badge warn'; }
    else { el.textContent = 'chưa duyệt'; el.className = 'badge'; }
  };
  badge($('#out-badge'), 'outline'); badge($('#nar-badge'), 'narr');
  const next = !approvedFlag('outline') ? 'outline' : 'narr';
  const b = $('#btn-approve'); b.textContent = next === 'outline' ? 'Duyệt dàn ý' : 'Duyệt lời dẫn';
  b.disabled = !D[next] || !!currentJob; b.dataset.kind = next;
  $('#approve-state').textContent = approvedFlag('narr') ? 'Lời dẫn đã duyệt' : approvedFlag('outline') ? 'Dàn ý đã duyệt' : 'Chưa duyệt gì';
  $('#approve-state').className = 'badge' + (approvedFlag('narr') ? ' ok' : '');
  $('#btn-write').disabled = !!currentJob; $('#btn-outline').disabled = !!currentJob;
  renderStatus();
}

// ------------------------------------------------------------------ sources column
function srcBody() {
  const b = S.brief, body = $('#src-body'), src = b.sources.find((s) => s.code === S.tab);
  $('#src-note').textContent = `${b.totals.paragraphs} đoạn, ${b.totals.words} từ`;
  const kids = [];
  const p = b.painting;
  kids.push(h('h3', { class: 'sh', text: 'Tác phẩm' }), h('div', null, h('b', { text: p.title }), h('div', { class: 'muted', text: [p.artist, p.year].filter(Boolean).join(', ') })));
  kids.push(h('div', { class: 'fieldrow', style: { marginTop: '8px' } },
    h('label', { text: 'Mục tiêu (từ)' }), h('input', { type: 'number', min: 300, max: 20000, step: 50, value: b.options.target_words, onchange: (e) => setOption({ target_words: Number(e.target.value) }) }),
    h('label', { text: 'Từ/giây' }), h('input', { type: 'number', min: 0.5, max: 6, step: 0.01, value: b.options.wps, onchange: (e) => setOption({ wps: Number(e.target.value) }) })));
  if (b.conflicts.length) {
    kids.push(h('h3', { class: 'sh', text: 'Các nguồn không thống nhất' }));
    for (const c of b.conflicts) kids.push(h('div', { class: 'conf', text: `${c.field}: ` + c.values.map((v) => `${v.src || v.work_id} ghi "${v.value}"`).join(' / ') }));
  }
  kids.push(h('h3', { class: 'sh', text: 'Chi tiết có tên' }),
    h('div', null, b.details.length ? b.details.map((d) => h('span', { class: 'det', title: d.where.map((w) => `${w.src}: ${w.paras.join(', ')}`).join('; '), onclick: () => focusParas(d.where.flatMap((w) => w.paras)) }, h('b', { text: d.id }), d.name)) : h('span', { class: 'muted', text: 'Không có' })));
  kids.push(h('h3', { class: 'sh', text: 'Sách' }),
    h('div', { class: 'tabs' }, b.sources.map((s) => h('button', { class: (s.code === S.tab ? 'active ' : '') + (s.low_trust ? 'low' : ''), onclick: () => { S.tab = s.code; renderSources(); }, text: `${s.code} ${s.book_id.split('_')[0]}` }))));
  if (src) {
    kids.push(h('div', { class: 'src-head' }, h('b', { text: src.book_title }), h('span', { class: 'muted', text: `${src.paragraphs.length} đoạn, ${src.words} từ` }),
      src.low_trust ? h('span', { class: 'tag lowtrust', title: src.trust_note, text: 'bản dịch máy, không dùng làm nguồn sự kiện' }) : null),
      src.low_trust ? h('label', { class: 'chk', style: { display: 'flex', gap: '6px', marginBottom: '6px' } }, h('input', { type: 'checkbox', checked: src.included, onchange: (e) => tickLow(src, e.target.checked) }), 'Dùng sách này làm nguồn (đã đọc và chấp nhận rủi ro)') : null,
      h('input', { type: 'search', placeholder: 'Tìm trong sách này', value: S.search, style: { width: '100%', marginBottom: '8px' }, oninput: (e) => { S.search = e.target.value; renderParas(); } }),
      h('div', { id: 'paras' }));
  }
  body.replaceChildren(...kids.filter(Boolean));
  renderParas();
}
function renderParas() {
  const box = $('#paras'); if (!box) return;
  const src = S.brief.sources.find((s) => s.code === S.tab), q = S.search.trim().toLowerCase();
  const out = []; let cur = null;
  for (const p of src.paragraphs) {
    if (q && !p.text.toLowerCase().includes(q) && !p.id.toLowerCase().includes(q)) continue;
    if (p.section !== cur) { cur = p.section; if (cur) out.push(h('div', { class: 'para-sec', text: cur })); }
    const tx = h('span', { class: 'tx' });
    if (q && p.text.toLowerCase().includes(q)) { const i = p.text.toLowerCase().indexOf(q); tx.append(p.text.slice(0, i), h('mark', { text: p.text.slice(i, i + q.length) }), p.text.slice(i + q.length)); } else tx.textContent = p.text;
    out.push(h('div', { class: 'para' + (p.kind === 'quote' ? ' quote' : '') + (S.hl.includes(p.id) ? ' hl' : ''), id: 'para-' + p.id }, h('span', { class: 'pid mono', text: p.id, title: 'Bấm để chép mã vào bộ nhớ tạm', onclick: () => navigator.clipboard?.writeText(p.id).catch(() => {}) }), tx));
  }
  box.replaceChildren(...(out.length ? out : [h('div', { class: 'muted', text: 'Không có đoạn nào khớp.' })]));
}
const renderSources = srcBody;
function focusParas(list) {
  S.hl = list.filter(Boolean);
  if (!S.hl.length) return;
  const code = S.hl[0].split('-')[0];
  if (S.brief.sources.some((s) => s.code === code) && S.tab !== code) { S.tab = code; S.search = ''; }
  srcBody();
  const el = document.getElementById('para-' + S.hl[0]);
  if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  else toast(`Không thấy đoạn ${S.hl[0]} trong nguồn`, 'warn');
}
const factSources = (fid) => (D.outline?.facts.find((f) => f.id === fid)?.sources) || [];
async function setOption(o) { try { S.brief.options = await send('PUT', `${P()}/brief/options`, o); toast('Đã lưu', 'ok', 1000); S.brief = await J(`${P()}/brief`); renderAll(); } catch (e) { toast(e.message, 'err'); } }
async function tickLow(src, on) {
  const cur = new Set(S.brief.options.include_low); on ? cur.add(src.book_id) : cur.delete(src.book_id);
  await setOption({ include_low: [...cur] });
}

// ------------------------------------------------------------------ outline column
const chip = (cls, text, fn, title) => h('span', { class: 'chip ' + cls, text, title, onclick: fn });
const srcChips = (list) => h('div', { class: 'chips' }, list.map((s) => chip('src', s, () => focusParas([s]), 'Xem đoạn nguồn')));
const factChips = (list) => h('div', { class: 'chips' }, list.map((f) => chip(D.outline?.facts.some((x) => x.id === f) ? 'fact' : 'bad', f, () => focusParas(factSources(f)), 'Xem các đoạn nguồn của dữ kiện này')));
function issueFor(kind, pred) { return (ST[kind].issues || []).filter((i) => i.level !== 'info' && pred(i)); }

function outBody() {
  const body = $('#out-body'), o = D.outline;
  if (!o) {
    body.replaceChildren(h('div', { class: 'empty' }, 'Chưa có dàn ý.', h('br'), 'Bấm "Lập dàn ý" để mô hình viết, hoặc "Dán" để dán dàn ý đã nhờ Gemini viết.', h('br'),
      h('button', { class: 'primary', onclick: () => runDialog('outline'), text: 'Lập dàn ý' }), h('button', { onclick: () => pasteDialog('outline'), text: 'Dán dàn ý' })));
    return;
  }
  const kids = [];
  kids.push(h('h3', { class: 'sh', text: 'Câu hỏi chính (thesis)' }), h('textarea', { value: o.thesis, rows: 2, oninput: (e) => { fit(e.target); mutate('outline', () => { o.thesis = e.target.value; }, 'thesis'); } }));
  kids.push(h('h3', { class: 'sh' }, 'Câu mở đầu (chọn một)'));
  o.hook_options.forEach((hk) => kids.push(h('div', { class: 'hookrow' },
    h('input', { type: 'radio', name: 'hook', checked: o.hook_choice === hk.id, title: 'Chọn câu này', onchange: () => mutate('outline', () => { o.hook_choice = hk.id; }) }),
    h('textarea', { value: hk.text, rows: 2, oninput: (e) => mutate('outline', () => { hk.text = e.target.value; }, 'hook' + hk.id) }),
    h('button', { class: 'small danger', text: 'x', title: 'Xóa', onclick: () => { mutate('outline', () => { o.hook_options = o.hook_options.filter((x) => x !== hk); if (o.hook_choice === hk.id) o.hook_choice = o.hook_options[0]?.id || null; }); outBody(); } }))));
  kids.push(h('button', { class: 'small', text: '+ Thêm câu mở', onclick: () => { mutate('outline', () => { const n = Math.max(0, ...o.hook_options.map((x) => Number(x.id.replace(/\D/g, '')) || 0)) + 1; o.hook_options.push({ id: 'h' + n, text: '' }); if (!o.hook_choice) o.hook_choice = 'h' + n; }); outBody(); } }));

  const tw = o.chapters.reduce((a, c) => a + (Number(c.word_budget) || 0), 0);
  kids.push(h('h3', { class: 'sh' }, 'Các chương', h('span', { class: 'muted', style: { textTransform: 'none' }, text: `ngân sách ${tw} / mục tiêu ` }), h('input', { type: 'number', value: o.target_words, style: { width: '80px', padding: '1px 5px' }, onchange: (e) => { mutate('outline', () => { o.target_words = Number(e.target.value) || 0; }); outBody(); } })));
  o.chapters.forEach((c, i) => {
    const is = issueFor('outline', (x) => x.chapter === c.id);
    kids.push(h('div', { class: 'card' + (is.some((x) => x.level === 'error') ? ' err' : '') },
      h('div', { class: 'r' }, h('span', { class: 'small-id mono', text: c.id }),
        h('input', { type: 'text', class: 'ttl', value: c.title, oninput: (e) => mutate('outline', () => { c.title = e.target.value; }, 'ct' + c.id) }),
        h('button', { class: 'small', text: '↑', disabled: i === 0, onclick: () => { mutate('outline', () => { [o.chapters[i - 1], o.chapters[i]] = [o.chapters[i], o.chapters[i - 1]]; }); outBody(); } }),
        h('button', { class: 'small', text: '↓', disabled: i === o.chapters.length - 1, onclick: () => { mutate('outline', () => { [o.chapters[i + 1], o.chapters[i]] = [o.chapters[i], o.chapters[i + 1]]; }); outBody(); } }),
        h('button', { class: 'small danger', text: 'Xóa', onclick: () => { if (confirm(`Xóa chương ${c.id} khỏi dàn ý?`)) { mutate('outline', () => { o.chapters = o.chapters.filter((x) => x !== c); }); outBody(); } } })),
      h('div', { class: 'r' }, h('label', { text: 'Vai trò' }),
        h('select', { onchange: (e) => mutate('outline', () => { c.role = e.target.value; }) }, ['cold_open', 'chapter', 'closing'].map((r) => h('option', { value: r, selected: c.role === r, text: { cold_open: 'mở đầu', chapter: 'chương', closing: 'kết' }[r] }))),
        h('label', { class: 'chk', style: { display: 'inline-flex', gap: '4px', width: 'auto', whiteSpace: 'nowrap' }, title: 'Hiện thẻ tiêu đề chương trong video' }, h('input', { type: 'checkbox', checked: c.card, onchange: (e) => mutate('outline', () => { c.card = e.target.checked; }) }), 'thẻ chương')),
      h('div', { class: 'r' }, h('label', { text: 'Số từ' }), h('input', { type: 'number', value: c.word_budget, style: { width: '110px', flex: 'none' }, onchange: (e) => { mutate('outline', () => { c.word_budget = Number(e.target.value) || 0; }); outBody(); } }), h('span', { class: 'muted', text: `khoảng ${(c.word_budget / (S.brief.options.wps || 2.41) / 60).toFixed(1)} phút` })),
      h('div', { class: 'r' }, h('label', { text: 'Mục đích' }), h('textarea', { value: c.purpose, rows: 2, oninput: (e) => mutate('outline', () => { c.purpose = e.target.value; }, 'cp' + c.id) })),
      h('div', { class: 'r' }, h('label', { text: 'Dữ kiện' }), h('input', { type: 'text', value: c.facts.join(', '), onchange: (e) => { mutate('outline', () => { c.facts = ids(e.target.value); }); outBody(); } })), factChips(c.facts),
      h('div', { class: 'r' }, h('label', { text: 'Cho xem' }), h('input', { type: 'text', value: c.show.join('; '), title: 'Ngăn cách bằng dấu ;', onchange: (e) => mutate('outline', () => { c.show = e.target.value.split(';').map((x) => x.trim()).filter(Boolean); }) })),
      is.length ? h('div', { class: 'hint warn', text: is.map((x) => x.message).join(' ') }) : null));
  });
  kids.push(h('button', { class: 'small', text: '+ Thêm chương', onclick: () => { mutate('outline', () => { const n = Math.max(0, o.chapters.length, ...o.chapters.map((x) => Number(x.id.replace(/\D/g, '')) || 0), o.counters?.chapter || 0) + 1; o.chapters.push({ id: 'c' + String(n).padStart(2, '0'), role: 'chapter', title: 'CHƯƠNG MỚI', card: true, purpose: '', word_budget: 200, facts: [], show: [] }); }); outBody(); } }));

  kids.push(h('h3', { class: 'sh', text: 'Bảng dữ kiện' }));
  o.facts.forEach((f) => {
    const is = issueFor('outline', (x) => x.fact === f.id);
    kids.push(h('div', { class: 'card' + (f.certainty === 'disputed' ? ' warnc' : '') },
      h('div', { class: 'r' }, h('span', { class: 'small-id mono', text: f.id }),
        h('select', { style: { width: '120px' }, onchange: (e) => { mutate('outline', () => { f.certainty = e.target.value; }); outBody(); } }, ['established', 'likely', 'disputed'].map((c) => h('option', { value: c, selected: f.certainty === c, text: { established: 'chắc chắn', likely: 'nhiều khả năng', disputed: 'tranh cãi' }[c] }))),
        h('input', { type: 'text', value: f.sources.join(', '), placeholder: 'mã đoạn nguồn, ví dụ PAY-07, HOD-02', onchange: (e) => { mutate('outline', () => { f.sources = ids(e.target.value).map((x) => x.toUpperCase()); }); outBody(); } }),
        h('button', { class: 'small danger', text: 'Xóa', onclick: () => { mutate('outline', () => { o.facts = o.facts.filter((x) => x !== f); }); outBody(); } })),
      srcChips(f.sources),
      h('textarea', { value: f.claim, rows: 2, oninput: (e) => mutate('outline', () => { f.claim = e.target.value; }, 'fc' + f.id) }),
      h('div', { class: 'r', style: { marginTop: '4px' } }, h('label', { text: 'Mâu thuẫn' }), h('input', { type: 'text', value: f.conflict || '', placeholder: 'để trống nếu các nguồn thống nhất', oninput: (e) => mutate('outline', () => { f.conflict = e.target.value || null; }, 'fx' + f.id) })),
      is.length ? h('div', { class: 'hint warn', text: is.map((x) => x.message).join(' ') }) : null));
  });
  kids.push(h('button', { class: 'small', text: '+ Thêm dữ kiện', onclick: () => { mutate('outline', () => { const n = Math.max(0, o.counters?.fact || 0, ...o.facts.map((x) => Number(x.id.replace(/\D/g, '')) || 0)) + 1; o.counters = { ...(o.counters || {}), fact: n }; o.facts.push({ id: 'f' + String(n).padStart(2, '0'), claim: '', sources: [], certainty: 'likely', conflict: null }); }); outBody(); } }));
  if (o.source?.kind) kids.push(h('div', { class: 'hint', style: { marginTop: '14px' }, text: `Nguồn dàn ý: ${{ model: 'mô hình ' + (o.source.model || ''), paste: 'dán vào', manual: 'viết tay' }[o.source.kind] || o.source.kind}, ${(o.source.created_at || '').slice(0, 16).replace('T', ' ')}` }));
  body.replaceChildren(...kids);
  fitAll(body);
}

// ------------------------------------------------------------------ narration column
function narBody() {
  const body = $('#nar-body'), n = D.narr;
  if (!n) {
    body.replaceChildren(h('div', { class: 'empty' }, 'Chưa có lời dẫn.', h('br'), approvedFlag('outline') ? 'Dàn ý đã duyệt. Bấm "Viết lời dẫn" hoặc dán bản đã viết.' : 'Cần duyệt dàn ý trước, rồi mô hình mới viết lời dẫn.', h('br'),
      h('button', { class: 'primary', onclick: () => runDialog('narration'), disabled: !approvedFlag('outline'), text: 'Viết lời dẫn' }), h('button', { onclick: () => pasteDialog('narration'), text: 'Dán lời dẫn' })));
    return;
  }
  const kids = [], stats = ST.narr.stats;
  for (const ch of n.chapters) {
    const cs = stats?.chapters.find((c) => c.id === ch.id);
    const wc = ch.beats.reduce((a, b) => a + words(b.text), 0);
    const bud = cs?.budget || D.outline?.chapters.find((c) => c.id === ch.id)?.word_budget || 0;
    kids.push(h('div', { class: 'chap' },
      h('div', { class: 'chap-h' }, h('span', { class: 'cid mono', text: ch.id }), h('span', { class: 'ttl', text: ch.title }),
        ch.card ? h('span', { class: 'tag', text: 'thẻ chương' }) : null,
        h('span', { class: 'wc mono', text: `${wc}${bud ? ' / ' + bud : ''} từ` }),
        h('button', { class: 'small', text: 'Viết lại chương', title: 'Mô hình viết lại chương này, kèm ghi chú của bạn', onclick: () => runDialog('narration', ch.id) }),
        h('button', { class: 'small', text: '+ Dòng', onclick: () => doOp({ op: 'insert', chapter: ch.id, after: ch.beats.at(-1)?.id || null }) })),
      ...ch.beats.map((b, i) => beatEl(ch, b, i))));
  }
  const missing = (D.outline?.chapters || []).filter((c) => !n.chapters.some((x) => x.id === c.id));
  if (missing.length) kids.push(h('div', { class: 'card warnc' }, `Chưa có chương: ${missing.map((c) => c.id + ' ' + c.title).join(', ')}. `, h('button', { class: 'small', text: 'Viết các chương còn thiếu', onclick: () => runDialog('narration', missing.map((c) => c.id)) })));
  if (n.source?.kind) kids.push(h('div', { class: 'hint', text: `Nguồn lời dẫn: ${{ model: 'mô hình ' + (n.source.model || ''), paste: 'dán vào', manual: 'viết tay' }[n.source.kind] || n.source.kind}, ${(n.source.created_at || '').slice(0, 16).replace('T', ' ')}` }));
  body.replaceChildren(...kids);
  fitAll(body);
}
function beatEl(ch, b, i) {
  const is = issueFor('narr', (x) => x.beat === b.id);
  const lvl = is.some((x) => x.level === 'error') ? ' err' : is.length ? ' warnb' : '';
  const wcn = h('span', { class: 'wcn mono' });
  const upd = () => { const w = words(b.text); wcn.textContent = `${w} từ`; wcn.className = 'wcn mono' + (w > 90 ? ' over' : ''); };
  const ta = h('textarea', { value: b.text, disabled: b.locked, spellcheck: true, oninput: (e) => { mutate('narr', () => { b.text = e.target.value; }, 'bt' + b.id); fit(e.target); upd(); renderStatus(); } });
  const el = h('div', { class: 'beat' + lvl + (b.locked ? ' locked' : ''), id: 'beat-' + b.id },
    ta,
    h('div', { class: 'tools' }, h('span', { class: 'bid mono', text: b.id }), wcn,
      h('button', { class: 'small', text: 'Tách', title: 'Tách thành hai dòng tại vị trí con trỏ', disabled: b.locked, onclick: () => { const at = words(ta.value.slice(0, ta.selectionStart)); if (at <= 0 || at >= words(ta.value)) return toast('Đặt con trỏ vào giữa câu rồi bấm Tách', 'warn'); doOp({ op: 'split', beat: b.id, at_word: at }); } }),
      h('button', { class: 'small', text: 'Gộp lên', title: 'Gộp với dòng phía trên', disabled: b.locked || i === 0, onclick: () => doOp({ op: 'merge', beat: b.id }) }),
      h('button', { class: 'small danger', text: 'Bỏ', title: 'Bỏ dòng này (mã không bị dùng lại)', disabled: b.locked, onclick: () => doOp({ op: 'drop', beat: b.id }) }),
      h('button', { class: 'small', text: 'Chèn dưới', onclick: () => doOp({ op: 'insert', chapter: ch.id, after: b.id }) }),
      h('button', { class: 'small', text: '↑', title: 'Chuyển lên', onclick: () => moveBeat(ch, i, -1) }),
      h('button', { class: 'small', text: '↓', title: 'Chuyển xuống', onclick: () => moveBeat(ch, i, 1) }),
      h('label', { class: 'chk', title: 'Khóa: không sửa, không bị viết lại' }, h('input', { type: 'checkbox', checked: b.locked, onchange: (e) => { mutate('narr', () => { b.locked = e.target.checked; }); narBody(); } }), 'khóa')),
    h('div', { class: 'meta' }, h('span', { class: 'l', text: 'dữ kiện' }), h('input', { type: 'text', value: b.facts.join(', '), onchange: (e) => { mutate('narr', () => { b.facts = ids(e.target.value).map((x) => x.toLowerCase()); }); narBody(); } }),
      h('span', { class: 'l', text: 'cho xem' }), h('input', { type: 'text', value: b.show.join('; '), title: 'Ngăn cách bằng dấu ;', onchange: (e) => mutate('narr', () => { b.show = e.target.value.split(';').map((x) => x.trim()).filter(Boolean); }) })),
    b.facts.length ? factChips(b.facts) : null,
    h('div', { class: 'meta' }, h('span', { class: 'l', text: 'ghi chú' }), h('input', { type: 'text', value: b.note, placeholder: 'ghi chú riêng, không đọc lên', oninput: (e) => mutate('narr', () => { b.note = e.target.value; }, 'bn' + b.id) })),
    ...is.map((x) => h('div', { class: 'iss ' + (x.level === 'error' ? 'e' : ''), text: (CODE[x.code] || x.code) + ': ' + x.message })));
  if (b.facts.length) el.querySelector('.chips')?.classList.add('flat');
  upd();
  return el;
}
function moveBeat(ch, i, dir) {
  const chs = D.narr.chapters, ci = chs.indexOf(ch);
  if (dir < 0) {
    if (i > 0) return doOp({ op: 'move', beat: ch.beats[i].id, to_chapter: ch.id, after: i > 1 ? ch.beats[i - 2].id : null });
    if (ci > 0) return doOp({ op: 'move', beat: ch.beats[i].id, to_chapter: chs[ci - 1].id, after: chs[ci - 1].beats.at(-1)?.id || null });
  } else {
    if (i < ch.beats.length - 1) return doOp({ op: 'move', beat: ch.beats[i].id, to_chapter: ch.id, after: ch.beats[i + 1].id });
    if (ci < chs.length - 1) return doOp({ op: 'move', beat: ch.beats[i].id, to_chapter: chs[ci + 1].id, after: null });
  }
  toast('Không thể chuyển xa hơn', 'warn');
}
async function doOp(op) {
  if (!(await saveKind('narr'))) return;
  hist.narr.past.push(JSON.stringify(D.narr)); hist.narr.future = []; S.focus = 'narr';
  try {
    const r = await send('POST', `${P()}/narration/ops`, { base_rev: R.narr, ops: [op] });
    applyNarr(r);
    const id = r.results?.[0]?.id;
    if (id && op.op !== 'merge') setTimeout(() => { const t = document.querySelector(`#beat-${id} textarea`); t?.scrollIntoView({ block: 'center' }); t?.focus(); }, 30);
  } catch (e) { hist.narr.past.pop(); toast(e.message, 'err'); }
}

// ------------------------------------------------------------------ status bar
function renderStatus() {
  const n = D.narr, o = D.outline, wps = S.brief?.options.wps || 2.41;
  const total = n ? n.chapters.reduce((a, c) => a + c.beats.reduce((x, b) => x + words(b.text), 0), 0) : 0;
  const target = o?.target_words || S.brief?.options.target_words || 0;
  $('#st-totals').innerHTML = '';
  $('#st-totals').append(h('div', null, h('b', { text: `${total}` }), ` từ, khoảng `, h('b', { text: (total / wps / 60).toFixed(1) }), ' phút'), h('div', { class: 'muted', text: `mục tiêu ${target} từ (${(target / wps / 60).toFixed(1)} phút), ${wps} từ/giây` }));
  const bars = [];
  for (const c of o?.chapters || []) {
    const ch = n?.chapters.find((x) => x.id === c.id), w = ch ? ch.beats.reduce((a, b) => a + words(b.text), 0) : 0, bud = Number(c.word_budget) || 0;
    const r = bud ? w / bud : 0, cls = !ch ? '' : Math.abs(r - 1) > 0.3 ? 'far' : Math.abs(r - 1) > 0.15 ? 'off' : '';
    bars.push(h('div', { class: 'bar ' + cls, title: `${c.id} ${c.title}: ${w} / ${bud} từ` }, h('div', { class: 't', text: c.id + ' ' + c.title }), h('div', { class: 'tr' }, h('i', { style: { width: Math.min(100, (r / 1.6) * 100) + '%' } }), h('b'))));
  }
  $('#st-bars').replaceChildren(...bars);
  const jb = $('#st-job'); jb.replaceChildren();
  const j = currentJob;
  if (j) {
    jb.append(h('div', null, h('b', { text: j.kind === 'outline' ? 'Đang lập dàn ý' : 'Đang viết lời dẫn' }), ` (${j.model}) `, j.state === 'running' || j.state === 'queued' ? h('button', { class: 'small danger', text: 'Hủy', onclick: () => send('POST', `/api/jobs/${j.id}/cancel`).catch((e) => toast(e.message, 'err')) }) : null),
      h('div', null, j.chapters.map((c) => h('span', { class: 'jc ' + c.state, title: `${c.id} ${c.title}: ${c.state}${c.attempts > 1 ? ', thử lần ' + c.attempts : ''} ${c.message || ''}` }))),
      h('div', { class: 'muted', text: j.chapters.filter((c) => ['running', 'retrying'].includes(c.state)).map((c) => `${c.id}${c.state === 'retrying' ? ' (thử lại: ' + (c.message || '').slice(0, 60) + ')' : ''}`).join(', ') || j.state }));
  } else jb.append(h('span', { class: 'muted', text: 'Không có tác vụ đang chạy' }));
}

// ------------------------------------------------------------------ jobs
async function startJob(kind, body) {
  if (!S.model) return toast('Chưa chọn mô hình', 'err');
  if (!(await saveAll())) return;
  try {
    const r = await send('POST', `${P()}/${kind}/generate`, { model: S.model, ...body });
    watch(r.job_id);
  } catch (e) {
    if (e.status === 409 && e.body?.locked) { if (confirm('Có dòng đang khóa trong chương này. Vẫn viết lại và thay cả dòng khóa?')) return startJob(kind, { ...body, force: true }); }
    else if (e.status === 409 && e.body?.job_id) watch(e.body.job_id);
    else toast(e.message, 'err', 8000);
  }
}
function watch(jid) {
  clearInterval(jobPoll);
  const tick = async () => {
    try {
      const j = await J(`/api/jobs/${jid}`);
      currentJob = j; refreshChrome();
      if (['done', 'error', 'cancelled'].includes(j.state)) { clearInterval(jobPoll); await jobEnded(j); }
    } catch (e) { clearInterval(jobPoll); currentJob = null; toast(e.message, 'err'); refreshChrome(); }
  };
  jobPoll = setInterval(tick, 700); tick();
}
async function jobEnded(j) {
  applyOutline(await J(`${P()}/outline`), true); applyNarr(await J(`${P()}/narration`), true); renderAll();
  if (j.state === 'done') toast(j.kind === 'outline' ? 'Dàn ý đã viết xong. Hãy đọc, sửa rồi duyệt.' : 'Lời dẫn đã viết xong. Hãy đọc, sửa rồi duyệt.', 'ok', 6000);
  else if (j.state === 'cancelled') toast('Đã hủy. Phần đã viết xong được giữ lại.', 'warn');
  else {
    toast(j.error || 'Lỗi', 'err', 12000);
    const alt = (j.alternatives || []).map((id) => S.models.find((m) => m.id === id)).filter(Boolean);
    if (alt.length && ['timeout', 'rate_limit'].includes(j.error_kind)) {
      const m = modal({ title: j.error_kind === 'timeout' ? 'Mô hình không trả lời kịp' : 'Mô hình bị giới hạn lượt gọi', body: h('div', { class: 'body' }, h('p', { text: j.error }), h('p', { text: 'Chương đã viết xong được giữ lại. Chọn mô hình khác để chạy tiếp, hệ thống không tự đổi mô hình.' }), ...alt.map((a) => h('button', { style: { marginRight: '8px' }, text: 'Thử với ' + a.label, onclick: () => { m.close(); S.model = a.id; $('#model-pick').value = a.id; retryLast(j); } }))) });
    }
    if (j.error_kind === 'validation' || j.error_kind === 'parse') { if (D.narr || ST.narr.last_paste || ST.outline.last_paste) toast('Câu trả lời lỗi được giữ trong ô "Dán".', 'warn', 8000); }
  }
  currentJob = null; refreshChrome();
}
let lastRun = null;
function retryLast(j) { if (lastRun) startJob(lastRun.kind, lastRun.body); }

function runDialog(kind, chapters) {
  const model = S.models.find((m) => m.id === S.model);
  if (!model || !model.enabled) return toast((model?.message || 'Chưa chọn mô hình') + ' (xem docs/SCRIPT_GUIDE.md). Có thể chọn "Mock" để thử.', 'err', 9000);
  const chs = chapters ? [].concat(chapters) : null;
  const exists = kind === 'outline' ? !!D.outline : !!D.narr && !chs;
  const notes = h('textarea', { rows: 4, placeholder: kind === 'outline' ? 'Ví dụ: tập trung vào chiếc gương, bỏ phần giả kim thuật' : 'Ví dụ: ngắn hơn, bớt tiểu sử, thêm một cách đọc khác' });
  const title = kind === 'outline' ? 'Lập dàn ý' : chs ? `Viết lại ${chs.join(', ')}` : 'Viết lời dẫn';
  const m = modal({ title, cls: 'wide', body: h('div', { class: 'body' },
    h('p', null, 'Mô hình: ', h('b', { text: model.label })), exists ? h('p', { class: 'hint warn', text: kind === 'outline' ? 'Dàn ý hiện tại sẽ bị thay (bản cũ giữ ở outline.prev.json) và mất trạng thái duyệt.' : 'Lời dẫn hiện tại sẽ bị thay (bản cũ giữ ở narration.prev.json).' }) : null,
    chs ? null : null, h('label', { class: 'lb', text: 'Ghi chú cho mô hình (tùy chọn)' }), notes),
    footer: h('footer', null, h('button', { onclick: () => m.close(), text: 'Hủy' }), h('button', { class: 'primary', text: 'Chạy', onclick: () => { m.close(); lastRun = { kind, body: { notes: notes.value, ...(chs ? { chapters: chs } : {}) } }; startJob(kind, lastRun.body); } })) });
  setTimeout(() => notes.focus(), 30);
}

// ------------------------------------------------------------------ copy prompt and paste dialogs
function copyDialog(phase = 'outline') {
  const notes = h('textarea', { rows: 2, placeholder: 'Ghi chú thêm cho prompt (tùy chọn)' });
  const chap = h('select', null, h('option', { value: '', text: 'Tất cả các chương' }), ...(D.outline?.chapters || []).map((c) => h('option', { value: c.id, text: `${c.id} ${c.title}` })));
  const box = h('textarea', { class: 'big', readOnly: true, spellcheck: false, onfocus: (e) => e.target.select() });
  const info = h('div', { class: 'hint' });
  const tabs = {};
  const setPhase = async (ph) => {
    phase = ph; for (const [k, b] of Object.entries(tabs)) b.classList.toggle('active', k === ph);
    chap.style.display = ph === 'script' ? '' : 'none';
    try {
      const q = new URLSearchParams({ phase: ph, notes: notes.value, chapters: ph === 'script' ? chap.value : '' });
      const r = await fetch(`${P()}/prompt?${q}`); const t = await r.text();
      if (!r.ok) { let d = t; try { d = JSON.parse(t).detail; } catch {} box.value = ''; info.textContent = d; info.className = 'hint err'; return; }
      box.value = t; info.className = 'hint'; info.textContent = `${t.length} ký tự, ${words(t)} từ. Dán vào Gemini, rồi dán câu trả lời của nó vào nút "Dán".`;
    } catch (e) { info.textContent = e.message; info.className = 'hint err'; }
  };
  tabs.outline = h('button', { text: 'Prompt dàn ý', onclick: () => setPhase('outline') });
  tabs.script = h('button', { text: 'Prompt lời dẫn', onclick: () => setPhase('script') });
  notes.addEventListener('change', () => setPhase(phase)); chap.addEventListener('change', () => setPhase(phase));
  const copy = h('button', { class: 'primary', text: 'Sao chép', onclick: async () => {
    box.focus(); box.select();
    try { await navigator.clipboard.writeText(box.value); toast('Đã sao chép vào bộ nhớ tạm', 'ok', 1800); } catch { try { document.execCommand('copy'); toast('Đã sao chép', 'ok', 1800); } catch { toast('Trình duyệt chặn bộ nhớ tạm. Văn bản đã được bôi đen, bấm Ctrl+C (Cmd+C).', 'warn', 7000); } }
  } });
  const m = modal({ title: 'Sao chép prompt', cls: 'wide', body: h('div', { class: 'body' }, h('div', { class: 'tabs' }, tabs.outline, tabs.script, chap), notes, h('div', { style: { height: '8px' } }), box, info), footer: h('footer', null, copy, h('button', { onclick: () => m.close(), text: 'Đóng' })) });
  setPhase(phase);
}
function pasteDialog(kind = 'outline') {
  const stuff = { outline: ST.outline.last_paste || '', narration: ST.narr.last_paste || '' };
  let cur = kind;
  const ta = h('textarea', { class: 'big', placeholder: 'Dán nguyên câu trả lời của mô hình vào đây. Phần mở đầu, danh sách câu mở, bảng kiểm tra và đếm từ sẽ được tự bỏ.', value: stuff[cur] });
  const err = h('div'), merge = h('input', { type: 'checkbox' });
  const mergeLbl = h('label', { class: 'chk' }, merge, 'Chỉ thay các chương có trong bản dán (giữ các chương khác)');
  const tabs = {};
  const setKind = (k) => { stuff[cur] = ta.value; cur = k; ta.value = stuff[k]; err.replaceChildren(); for (const [x, b] of Object.entries(tabs)) b.classList.toggle('active', x === k); mergeLbl.style.display = k === 'narration' ? '' : 'none'; };
  tabs.outline = h('button', { text: 'Dán dàn ý', onclick: () => setKind('outline') }); tabs.narration = h('button', { text: 'Dán lời dẫn', onclick: () => setKind('narration') });
  const go = h('button', { class: 'primary', text: 'Phân tích và lưu', onclick: async () => {
    if (!ta.value.trim()) return;
    if ((cur === 'outline' ? dirty.outline : dirty.narr) && !confirm('Bản đang sửa chưa lưu sẽ bị thay. Tiếp tục?')) return;
    if ((cur === 'outline' ? D.outline : D.narr) && !confirm('Bản hiện có sẽ bị thay bằng bản dán (bản cũ giữ ở tệp .prev.json). Tiếp tục?')) return;
    err.replaceChildren();
    try {
      const r = await send('POST', `${P()}/${cur}/import`, { text: ta.value, merge: cur === 'narration' && merge.checked });
      if (cur === 'outline') applyOutline(r); else applyNarr(r);
      m.close(); toast('Đã đọc và lưu. ' + ((r.parse_issues || []).length ? `Có ${r.parse_issues.length} lưu ý, xem ở nút Kiểm tra.` : ''), 'ok', 5000);
      if (r.parse_issues?.length) showParseIssues(r.parse_issues);
    } catch (e) {
      if (e.status === 422) { stuff[cur] = ta.value; if (cur === 'outline') ST.outline.last_paste = ta.value; else ST.narr.last_paste = ta.value; err.replaceChildren(h('div', { class: 'hint err', text: 'Không đọc được. Văn bản vừa dán đã được giữ lại, sẽ hiện lại khi tải trang. Không có gì bị ghi đè.' }), h('div', { class: 'pre', text: e.message })); }
      else toast(e.message, 'err');
    }
  } });
  const m = modal({ title: 'Dán câu trả lời của mô hình', cls: 'wide', body: h('div', { class: 'body' }, h('div', { class: 'tabs' }, tabs.outline, tabs.narration), ta, h('div', { style: { margin: '6px 0' } }, mergeLbl), err), footer: h('footer', null, h('button', { onclick: () => { stuff[cur] = ta.value; m.close(); }, text: 'Đóng' }), go) });
  setKind(kind);
  setTimeout(() => ta.focus(), 30);
}
function showParseIssues(list) {
  modal({ title: 'Lưu ý khi đọc bản dán', body: h('div', { class: 'body' }, ...list.map((i) => h('div', { class: 'issue-row' }, h('span', { class: 'lv ' + i.level, text: LEVEL[i.level] }), h('span', { text: i.message })))) });
}

// ------------------------------------------------------------------ check list and approve
function checkDialog() {
  const rows = [];
  for (const [k, label] of [['outline', 'Dàn ý'], ['narr', 'Lời dẫn']]) {
    const list = (ST[k].issues || []).slice().sort((a, b) => ['error', 'warning', 'info'].indexOf(a.level) - ['error', 'warning', 'info'].indexOf(b.level));
    rows.push(h('h3', { class: 'sh', text: label + (dirty[k] ? ' (kết quả của bản đã lưu, hãy lưu lại để cập nhật)' : '') }));
    if (!list.length) rows.push(h('div', { class: 'muted', text: 'Không có gì.' }));
    for (const i of list) rows.push(h('div', { class: 'issue-row' }, h('span', { class: 'lv ' + i.level, text: LEVEL[i.level] }), h('span', null, h('b', { text: (CODE[i.code] || i.code) + '. ' }), i.message,
      i.beat ? h('a', { href: '#', style: { marginLeft: '8px', color: 'var(--accent)' }, text: 'đến dòng', onclick: (e) => { e.preventDefault(); document.getElementById('beat-' + i.beat)?.scrollIntoView({ block: 'center' }); } }) : null)));
  }
  modal({ title: 'Kiểm tra', cls: 'wide', body: h('div', { class: 'body' }, ...rows) });
}
async function approve() {
  const kind = $('#btn-approve').dataset.kind;
  if (!(await saveAll())) return;
  try {
    const r = await send('POST', `${P()}/${kind === 'outline' ? 'outline' : 'narration'}/approve`, { rev: kind === 'outline' ? R.outline : R.narr });
    if (kind === 'outline') applyOutline(r); else applyNarr(r);
    toast(kind === 'outline' ? 'Đã duyệt dàn ý' : 'Đã duyệt lời dẫn', 'ok');
  } catch (e) {
    if (e.body?.issues) { if (kind === 'outline') ST.outline.issues = e.body.issues; else ST.narr.issues = e.body.issues; renderAll(); checkDialog(); }
    toast(e.message, 'err', 9000);
  }
}

// ------------------------------------------------------------------ boot
function renderAll() { srcBody(); outBody(); narBody(); refreshChrome(); }
async function boot() {
  const projects = (await J('/api/projects')).filter((p) => p.sources || p.has_storyboard !== undefined);
  const want = new URLSearchParams(location.search).get('project') || localStorage.getItem('bti.script.project');
  S.pid = projects.find((p) => p.id === want)?.id || projects.find((p) => p.sources?.length)?.id || projects[0]?.id;
  const pick = $('#project-pick');
  pick.replaceChildren(...projects.map((p) => h('option', { value: p.id, text: p.title + ' (' + p.id + ')', selected: p.id === S.pid })));
  pick.onchange = () => { localStorage.setItem('bti.script.project', pick.value); location.search = '?project=' + pick.value; };
  if (!S.pid) return $('#smain').replaceChildren(h('div', { class: 'empty' }, 'Chưa có dự án. Vào Thư viện, chọn một tác phẩm và tạo dự án.'));
  localStorage.setItem('bti.script.project', S.pid);
  $('#lnk-editor').href = `/?project=${encodeURIComponent(S.pid)}`;
  S.models = await J('/api/models');
  const saved = localStorage.getItem('bti.script.model');
  S.model = (S.models.find((m) => m.id === saved && m.enabled) || S.models.find((m) => m.default && m.enabled) || S.models.find((m) => m.enabled) || S.models[0])?.id;
  const mp = $('#model-pick');
  mp.replaceChildren(...S.models.map((m) => h('option', { value: m.id, selected: m.id === S.model, text: m.label + (m.enabled ? '' : ' (không dùng được)') })));
  mp.onchange = () => { S.model = mp.value; localStorage.setItem('bti.script.model', S.model); const m = S.models.find((x) => x.id === S.model); if (!m.enabled) toast(m.message || 'Mô hình này chưa dùng được. Xem docs/SCRIPT_GUIDE.md.', 'warn', 9000); if (m.paid) toast('Mô hình này tính tiền theo token.', 'warn', 5000); };
  $('#btn-outline').onclick = () => runDialog('outline');
  $('#btn-write').onclick = () => { if (!approvedFlag('outline')) return toast('Cần duyệt dàn ý trước khi viết lời dẫn.', 'warn'); runDialog('narration'); };
  $('#btn-copy').onclick = () => copyDialog(approvedFlag('outline') && D.outline ? 'script' : 'outline');
  $('#btn-paste').onclick = () => pasteDialog(D.outline && approvedFlag('outline') ? 'narration' : 'outline');
  $('#btn-save').onclick = saveAll; $('#btn-undo').onclick = () => undoRedo(-1); $('#btn-redo').onclick = () => undoRedo(1);
  $('#btn-check').onclick = checkDialog; $('#btn-approve').onclick = approve;
  document.addEventListener('keydown', (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); saveAll(); }
    else if (mod && e.key.toLowerCase() === 'z' && !(e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT')) { e.preventDefault(); undoRedo(e.shiftKey ? 1 : -1); }
  });
  window.addEventListener('beforeunload', (e) => { if (dirty.outline || dirty.narr) { e.preventDefault(); e.returnValue = ''; } });
  await loadAll();
  const jobs = await J(`${P()}/script/jobs`).catch(() => []);
  const run = jobs.find((j) => ['queued', 'running'].includes(j.state));
  if (run) watch(run.id);
  if (ST.outline.last_paste && !D.outline) toast('Có bản dán dàn ý bị lỗi được giữ lại. Mở "Dán" để xem.', 'warn', 6000);
  if (ST.narr.last_paste) toast('Có bản dán lời dẫn bị lỗi được giữ lại. Mở "Dán" để xem.', 'warn', 6000);
  window.__scr = { S, D, R, ST, dirty, mutate, saveAll, doOp, pasteDialog, copyDialog, checkDialog, runDialog };
}
boot().catch((e) => { document.body.prepend(h('pre', { class: 'pre', text: 'Lỗi tải trang: ' + e.message })); });
