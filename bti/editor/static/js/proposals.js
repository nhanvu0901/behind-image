// Proposals panel: list, open one, accept/reject each change, apply.
import { h, modal, toast, errorToast, errorInto, confirmDialog } from './util.js';
import { describeHttp } from './errmsg.js';
import { ctx, bus } from './ctx.js';
import { api } from './api.js';

const OP_VI = { add: 'thêm', remove: 'xóa', change: 'đổi' };
const normOp = (op) => ({ added: 'add', removed: 'remove', changed: 'change' }[op] || op);
const show = (v) => (v === null || v === undefined ? '(không có)' : JSON.stringify(v, null, 1));

export async function openProposals(onApplied, openId = null) {
  const body = h('div', { class: 'body', style: { width: 'min(860px, 92vw)', minHeight: '320px' } });
  const dlg = modal({ title: 'Đề xuất từ agent', body });
  async function list() {
    body.replaceChildren(h('div', { class: 'hint', text: 'Đang tải...' }));
    let items = [], skipped = [];
    try {
      const res = await api.proposals(ctx.pid);
      if (Array.isArray(res)) items = res; else { items = res?.items || []; skipped = Array.isArray(res?.skipped) ? res.skipped : []; }   // files the server could not read: [{file, reason}]
    } catch (e) { const box = h('div', { class: 'empty' }); errorInto(box, e, 'Không tải được danh sách đề xuất: '); body.replaceChildren(box); return; }
    ctx.proposalsCount = items.length; bus.emit('proposals');
    const skipNote = skipped.length ? h('div', { class: 'banner warn skipped-note', style: { flexDirection: 'column', alignItems: 'flex-start' } }, h('div', { text: `${skipped.length} tệp đề xuất không đọc được nên không có trong danh sách:` }), ...skipped.map((k) => h('div', { class: 'hint', title: k.reason || '', text: `${k.file}: ${describeHttp(422, { detail: k.reason || '' }).text}` }))) : null;
    body.replaceChildren(...[skipNote, items.length ? h('div', { class: 'list' }, ...items.map((p) => h('div', { class: 'list-item', onclick: () => open(p.id) },
      h('div', { style: { flex: 1, minWidth: 0 } }, h('div', { style: { fontWeight: 600 }, text: p.summary || p.id }), h('div', { class: 'hint', text: `${p.author} | ${p.created_at} | ${p.id}` })),
      h('span', { class: 'chip', text: `${p.n_changes} thay đổi` }), h('button', { class: 'small primary', text: 'Mở' })))) : h('div', { class: 'empty', text: 'Chưa có đề xuất nào.' })].filter(Boolean));
  }
  async function open(id) {
    body.replaceChildren(h('div', { class: 'hint', text: 'Đang tải đề xuất...' }));
    let data;
    try { data = await api.proposal(ctx.pid, id); } catch (e) { errorToast(e, 'Không mở được đề xuất: '); return list(); }
    const decision = {};
    for (const c of data.changes) c.op = normOp(c.op);
    for (const c of data.changes) decision[c.id] = c.blocked_by_lock ? null : 'accept';
    const nOk = () => Object.values(decision).filter((v) => v === 'accept').length;
    const applyBtn = h('button', { class: 'primary', onclick: () => apply(nOk() === Object.keys(decision).filter((k) => decision[k] !== null).length ? 'all' : Object.keys(decision).filter((k) => decision[k] === 'accept')) });
    const refreshBtn = () => { applyBtn.textContent = `Áp dụng ${nOk()} thay đổi đã chấp nhận`; applyBtn.disabled = nOk() === 0; };
    async function apply(accept) {
      if (data.proposal.stale && !(await confirmDialog('Đề xuất này dựa trên một bản cũ của storyboard (đã có lần lưu khác kể từ khi agent soạn). Áp dụng có thể chồng lên sửa đổi mới hơn. Vẫn áp dụng?', { title: 'Đề xuất dựa trên bản cũ', ok: 'Vẫn áp dụng', danger: true }))) return;
      if (ctx.store.dirty && !(await confirmDialog('Bản nháp chưa lưu sẽ bị thay bằng bản sau khi áp dụng đề xuất (đề xuất áp lên bản đã lưu). Tiếp tục?', { title: 'Bản nháp chưa lưu', ok: 'Thay bản nháp', danger: true }))) return;
      applyBtn.disabled = true;
      try {
        const res = await api.applyProposal(ctx.pid, id, accept);
        toast('Đã áp dụng đề xuất' + (res.skipped_locked?.length ? `; ${res.skipped_locked.length} mục khóa được giữ nguyên` : ''), 'ok'); dlg.close(); onApplied(res);
      } catch (e) { errorToast(e, 'Áp dụng thất bại: '); applyBtn.disabled = false; }
    }
    const rows = data.changes.map((c) => {
      const blocked = !!c.blocked_by_lock;
      const acc = h('input', { type: 'radio', name: 'd' + c.id, checked: !blocked, disabled: blocked, onchange: () => { decision[c.id] = 'accept'; refreshBtn(); } });
      const rej = h('input', { type: 'radio', name: 'd' + c.id, checked: false, disabled: blocked, onchange: () => { decision[c.id] = 'reject'; refreshBtn(); } });
      return h('div', { class: 'change' + (blocked ? ' blocked' : '') },
        h('span', { class: 'op op-' + c.op, text: OP_VI[c.op] || c.op }),
        h('div', { style: { minWidth: 0 } }, h('div', { class: 'mono', style: { fontSize: '12px' }, text: c.path }),
          blocked ? h('div', { class: 'hint warn', text: 'Bị khóa: mục này đã khóa, không bao giờ được áp dụng.' }) : null,
          h('div', { class: 'ba' }, c.op !== 'add' ? h('div', null, h('h6', { text: 'Trước' }), h('pre', { text: show(c.before) })) : h('div'), c.op !== 'remove' ? h('div', null, h('h6', { text: 'Sau' }), h('pre', { text: show(c.after) })) : h('div'))),
        blocked ? h('span', { class: 'chip partial', text: 'khóa' }) : h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, h('label', { class: 'chk' }, acc, 'Chấp nhận'), h('label', { class: 'chk' }, rej, 'Từ chối')));
    });
    body.replaceChildren(...[
      data.proposal.stale ? h('div', { class: 'banner warn stale-note', text: `Đề xuất dựa trên bản cũ (base ${String(data.proposal.base_rev || '?').slice(0, 8)}): storyboard đã lưu đã đổi kể từ khi agent soạn. Xem kỹ trước khi áp dụng.` }) : null,
      h('div', { style: { display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px' } }, h('button', { class: 'small', text: '< Danh sách', onclick: list }),
        h('div', { style: { flex: 1 } }, h('b', { text: data.proposal.summary || data.proposal.id }), h('div', { class: 'hint', text: `${data.proposal.author} | ${data.proposal.created_at}` })), applyBtn),
      ...rows].filter(Boolean));
    refreshBtn();
  }
  if (openId) open(openId); else list();
  return dlg;
}
