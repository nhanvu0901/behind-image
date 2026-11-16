// Proposals panel: list, open one, accept/reject each change, apply.
import { h, modal, toast } from './util.js';
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
    let items = [];
    try { items = await api.proposals(ctx.pid); } catch (e) { body.replaceChildren(h('div', { class: 'empty', text: 'Không tải được danh sách đề xuất: ' + (e.status || e.message) })); return; }
    ctx.proposalsCount = items.length; bus.emit('proposals');
    body.replaceChildren(items.length ? h('div', { class: 'list' }, ...items.map((p) => h('div', { class: 'list-item', onclick: () => open(p.id) },
      h('div', { style: { flex: 1, minWidth: 0 } }, h('div', { style: { fontWeight: 600 }, text: p.summary || p.id }), h('div', { class: 'hint', text: `${p.author} | ${p.created_at} | ${p.id}` })),
      h('span', { class: 'chip', text: `${p.n_changes} thay đổi` }), h('button', { class: 'small primary', text: 'Mở' })))) : h('div', { class: 'empty', text: 'Chưa có đề xuất nào.' }));
  }
  async function open(id) {
    body.replaceChildren(h('div', { class: 'hint', text: 'Đang tải đề xuất...' }));
    let data;
    try { data = await api.proposal(ctx.pid, id); } catch (e) { toast('Không mở được đề xuất: ' + (e.status || e.message), 'err'); return list(); }
    const decision = {};
    for (const c of data.changes) c.op = normOp(c.op);
    for (const c of data.changes) decision[c.id] = c.blocked_by_lock ? null : 'accept';
    const nOk = () => Object.values(decision).filter((v) => v === 'accept').length;
    const applyBtn = h('button', { class: 'primary', onclick: () => apply(nOk() === Object.keys(decision).filter((k) => decision[k] !== null).length ? 'all' : Object.keys(decision).filter((k) => decision[k] === 'accept')) });
    const refreshBtn = () => { applyBtn.textContent = `Áp dụng ${nOk()} thay đổi đã chấp nhận`; applyBtn.disabled = nOk() === 0; };
    async function apply(accept) {
      if (ctx.store.dirty && !confirm('Bản nháp chưa lưu sẽ bị thay bằng bản sau khi áp dụng đề xuất (đề xuất áp lên bản đã lưu). Tiếp tục?')) return;
      applyBtn.disabled = true;
      try {
        const res = await api.applyProposal(ctx.pid, id, accept);
        toast('Đã áp dụng đề xuất', 'ok'); dlg.close(); onApplied(res);
      } catch (e) { toast('Áp dụng thất bại: ' + (e.status || '') + ' ' + (e.body?.detail?.message || e.message), 'err'); applyBtn.disabled = false; }
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
    body.replaceChildren(
      h('div', { style: { display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px' } }, h('button', { class: 'small', text: '< Danh sách', onclick: list }),
        h('div', { style: { flex: 1 } }, h('b', { text: data.proposal.summary || data.proposal.id }), h('div', { class: 'hint', text: `${data.proposal.author} | ${data.proposal.created_at}` })), applyBtn),
      ...rows);
    refreshBtn();
  }
  if (openId) open(openId); else list();
  return dlg;
}
