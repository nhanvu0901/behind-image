// State-driven request box for visual.edit (shared by Step 4 and Step 5 on the visual path).
// Reads the action from GET /api/projects/{pid}/state -> next_actions; hidden when absent.
import { api } from './api.js';
import { h, kids, toast } from './util.js';
import { describeError, jobErrorText } from './errmsg.js';
import { VISUAL_PAGE_LABELS as VL } from './labels.js';
import { visualEditAction, needsHint } from './visualpage_logic.js';

const ACTIVE = new Set(['queued', 'waiting', 'running']);

export function mountVisualBox(container, { pid, scope, state = null, getScope = null, onDone = null } = {}) {
  let dead = false, curState = state, busy = false, jobId = null, timer = null, prog = 0;

  function render() {
    if (dead || !container) return;
    const action = visualEditAction(curState);
    if (!action) {
      container.hidden = true;
      container.replaceChildren();
      return;
    }
    container.hidden = false;
    const W = VL.editBox;
    const sc = getScope ? getScope() : { text: W.scopeAll, payload: { all: true } };
    const why = !action.ready ? needsHint(action.needs) : '';
    const ta = h('textarea', {
      class: 'vbox-input',
      rows: 3,
      placeholder: W.placeholder,
      disabled: busy || !action.ready ? true : null,
      'aria-label': W.title,
    });
    const sendBtn = h('button', {
      type: 'button',
      class: 'primary small',
      text: busy ? W.sending : W.send,
      disabled: busy || !action.ready ? true : null,
      onclick: () => submit(ta, action),
    });
    const cancelBtn = jobId
      ? h('button', { type: 'button', class: 'small', text: W.cancel, onclick: cancel })
      : null;

    const box = h('div', { class: 'vbox', 'data-visual-box': '' },
      h('h3', { text: W.title }),
      ta,
      h('div', { class: 'vbox-scope', text: sc?.text || W.scopeAll }),
      why ? h('div', { class: 'hint warn', text: why }) : null,
      busy && jobId ? h('div', { class: 'vbox-prog' },
        h('span', { text: W.running }),
        h('progress', { max: 1, value: prog }),
        cancelBtn) : null,
      h('div', { class: 'vbox-row' }, h('span', { class: 'grow' }), sendBtn));
    container.replaceChildren(box);
  }

  async function submit(ta, action) {
    if (busy || dead || !action?.ready) return;
    const instruction = String(ta.value || '').trim();
    if (!instruction) { toast(VL.editBox.empty, 'warn', 4000); ta.focus(); return; }
    if (instruction.length > 2000) { toast(VL.editBox.tooLong, 'warn', 4000); return; }
    const sc = getScope ? getScope() : { payload: { all: true } };
    const baseBody = action.body_template || action.body || {};
    const body = { ...baseBody, instruction, scope: sc.payload || { all: true } };
    busy = true; prog = 0; render();
    try {
      const res = await api.send(action.method || 'POST', action.path, body);
      if (res?.job_id) {
        jobId = res.job_id;
        render();
        tick();
      } else {
        busy = false; jobId = null;
        toast(VL.editBox.done, 'ok');
        await onDone?.(res);
        render();
      }
    } catch (e) {
      busy = false; jobId = null;
      toast(VL.editBox.failed + describeError(e).text, 'err', 8000);
      render();
    }
  }

  async function tick() {
    if (dead || !jobId) return;
    try {
      const j = await api.get(`/api/longjobs/${encodeURIComponent(jobId)}`);
      if (dead) return;
      if (ACTIVE.has(j.state)) {
        prog = Number.isFinite(j.progress) ? j.progress : 0;
        render();
        timer = setTimeout(tick, 1200);
        return;
      }
      busy = false; jobId = null;
      if (j.state === 'done') {
        toast(VL.editBox.done, 'ok');
        await onDone?.(j.result || {});
      } else if (j.state !== 'cancelled') {
        toast(VL.editBox.failed + jobErrorText(j).text, 'err', 8000);
      }
      render();
    } catch {
      if (!dead) timer = setTimeout(tick, 1500);
    }
  }

  async function cancel() {
    if (!jobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {}); } catch { /* ignore */ }
  }

  scope?.add?.(() => { dead = true; clearTimeout(timer); });
  render();
  return {
    get visible() { return Boolean(visualEditAction(curState)); },
    updateState(nextState) { curState = nextState; render(); },
    updateScope() { if (!busy) render(); },
    unmount() { dead = true; clearTimeout(timer); container?.replaceChildren(); },
  };
}
