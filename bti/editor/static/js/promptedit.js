// Prompt-based storyboard editing in Step 5 ("Sửa video bằng prompt", design 7.4).
// Mounted under the preview in the storyboard view:
//   const unmount = mountPromptEdit(container, { pid, scope, save, onProposal, onJobEnd });
import { api } from './api.js';
import { h, toast, confirmDialog } from './util.js';
import { stageErrorText, stageJobErrorText } from './errmsg.js';
import { ctx, bus } from './ctx.js';
import { wordIndexAt } from './logic.js';

const ACTIVE = new Set(['queued', 'waiting', 'running']);

export function mountPromptEdit(container, { pid, scope = null, save = null, onProposal = null, onJobEnd = null } = {}) {
  let dead = false, timer = null, jobId = null, job = null;
  let models = null, defaultModel = 'gemini-pro-orchestrator-g1-pro';
  let thread = [];
  let userScopeChoice = 'auto'; // 'auto' | 'shots' | 'chapter' | 'all'
  let selectedShotIds = new Set();
  let explicitMultiShots = false;

  const root = h('div', { class: 'prompt-edit' });
  container.replaceChildren(root);

  const formBox = h('div', { class: 'prompt-form' });
  const progressBox = h('div', { class: 'prompt-progress-container' });
  const threadBox = h('div', { class: 'prompt-thread-wrap' });
  root.append(formBox, progressBox, threadBox);

  // Form controls
  const ta = h('textarea', {
    class: 'prompt-instruction',
    placeholder: 'Bạn muốn sửa gì? (ví dụ: ở đoạn nói về chiếc gương, zoom chậm hơn và thêm vòng sáng quanh gương)',
    rows: 2,
    onkeydown: (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        submit();
      }
    },
  });

  const scopeSel = h('select', {
    class: 'prompt-scope',
    onchange: (e) => {
      userScopeChoice = e.target.value;
      updateScopeUi();
    },
  },
    h('option', { value: 'shots', text: '0 shot đang chọn' }),
    h('option', { value: 'chapter', text: 'Chương tại đầu phát' }),
    h('option', { value: 'all', text: 'Cả video' })
  );

  const modelSel = h('select', { class: 'prompt-model' },
    h('option', { value: '', text: `Mặc định (${defaultModel})` })
  );

  const followupChk = h('label', { class: 'chk prompt-followup-label', title: 'Tiếp tục chuỗi yêu cầu trước đó' },
    h('input', { type: 'checkbox', class: 'prompt-followup', checked: false }),
    h('span', { text: 'Tiếp tục hội thoại trước' })
  );

  const btnSubmit = h('button', {
    class: 'primary prompt-btn-submit',
    onclick: submit,
    text: 'Gửi cho agent',
    title: 'Gửi yêu cầu sửa (Ctrl+Enter)',
  });

  const shotsChipsWrap = h('div', { class: 'prompt-shots-chips', style: { display: 'none' } });

  formBox.append(
    h('div', { class: 'prompt-input-row' }, ta),
    h('div', { class: 'prompt-controls-row' },
      h('div', { class: 'prompt-ctl-group' },
        h('span', { class: 'prompt-ctl-label', text: 'Phạm vi: ' }),
        scopeSel,
        h('span', { class: 'prompt-ctl-label', text: 'Mô hình: ' }),
        modelSel,
        followupChk
      ),
      btnSubmit
    ),
    shotsChipsWrap
  );

  const poll = () => {
    clearTimeout(timer);
    if (!dead) timer = setTimeout(tick, 1500);
  };

  scope?.add?.(() => unmount());

  // Listen to store events and timeline playhead
  const offStore = ctx.store.on((kind) => {
    if (kind === 'select') {
      if (!explicitMultiShots && ctx.store.sel?.shot) {
        selectedShotIds = new Set([ctx.store.sel.shot]);
      }
      updateScopeUi();
    } else if (kind === 'draft' || kind === 'load') {
      updateScopeUi();
    }
  });

  const offBus = bus.on('time', () => updateScopeUi());

  scope?.add?.(() => {
    offStore?.();
    offBus?.();
  });

  async function loadThread() {
    try {
      const r = await api.get(`/api/projects/${encodeURIComponent(pid)}/draft/thread`);
      thread = r.turns || [];
      if (r.active_job_id && !jobId) {
        jobId = r.active_job_id;
        renderProgress();
        tick();
      }
      const chk = followupChk.querySelector('input');
      if (chk && !chk.dataset.userToggled) {
        chk.checked = thread.length > 0;
      }
    } catch {
      thread = [];
    }
    if (!dead) renderThread();
  }

  async function loadModels() {
    try {
      const r = await api.get(`/api/projects/${encodeURIComponent(pid)}/draft/models`);
      models = r.models || [];
      if (r.default) defaultModel = r.default;
      modelSel.replaceChildren(
        h('option', { value: '', text: `Mặc định (${defaultModel})` }),
        ...(models || []).map((m) => h('option', { value: m.slug, text: m.label ? `${m.label} (${m.slug})` : m.slug }))
      );
    } catch {
      models = [];
    }
  }

  async function tick() {
    if (dead || !jobId) return;
    try {
      job = await api.get(`/api/longjobs/${encodeURIComponent(jobId)}`);
    } catch {
      if (!dead) poll();
      return;
    }
    if (dead) return;
    if (!ACTIVE.has(job.state)) {
      jobId = null;
      renderProgress();
      setFormDisabled(false);
      await loadThread();
      onJobEnd?.();
      return;
    }
    renderProgress();
    poll();
  }

  function getScopeInfo() {
    const allShots = ctx.store?.draft?.shots || [];
    const validIds = new Set(allShots.map((s) => s.id));

    // Cleanup any removed shots
    for (const sid of selectedShotIds) {
      if (!validIds.has(sid)) selectedShotIds.delete(sid);
    }

    if (!explicitMultiShots && selectedShotIds.size === 0 && ctx.store?.sel?.shot && validIds.has(ctx.store.sel.shot)) {
      selectedShotIds.add(ctx.store.sel.shot);
    }

    const selShots = Array.from(selectedShotIds);
    const hasShots = selShots.length > 0;
    const shotsLabel = hasShots ? `${selShots.length} shot đang chọn` : '0 shot đang chọn';

    const chapters = ctx.store?.timing?.chapters || [];
    const t = ctx.t || 0;
    let curChap = chapters.find((c) => c.start != null && c.end != null && c.start <= t && t < c.end);
    if (!curChap && chapters.length) {
      const words = ctx.words();
      const wIdx = wordIndexAt(words, t);
      curChap = chapters.find((c) => c.w0 <= wIdx && wIdx < c.w1) || chapters[0];
    }
    const chapName = curChap ? (curChap.name || curChap.id) : '';
    const chapLabel = chapName ? `Chương ${chapName}` : 'Chương tại đầu phát';

    return { selShots, hasShots, shotsLabel, curChap, chapLabel, allShots };
  }

  function updateScopeUi() {
    if (dead) return;
    const { selShots, hasShots, shotsLabel, chapLabel, allShots } = getScopeInfo();

    const optShots = scopeSel.querySelector('option[value="shots"]');
    const optChap = scopeSel.querySelector('option[value="chapter"]');
    if (optShots) {
      optShots.textContent = shotsLabel;
      optShots.disabled = !hasShots;
    }
    if (optChap) {
      optChap.textContent = chapLabel;
    }

    const effectiveScope = userScopeChoice === 'auto' ? (hasShots ? 'shots' : 'chapter') : userScopeChoice;
    scopeSel.value = effectiveScope;

    // Render multi-shot selector chips when scope is 'shots'
    if (effectiveScope === 'shots') {
      shotsChipsWrap.style.display = 'flex';
      const chips = selShots.map((sid) => {
        const sObj = allShots.find((s) => s.id === sid);
        const lk = sObj?.locked ? ' [Khóa]' : '';
        return h('span', { class: 'prompt-shot-chip' },
          h('span', { text: `${sid}${lk}` }),
          h('button', {
            type: 'button',
            class: 'prompt-shot-chip-del',
            title: `Bỏ chọn shot ${sid}`,
            onclick: (e) => {
              e.preventDefault();
              selectedShotIds.delete(sid);
              explicitMultiShots = true;
              updateScopeUi();
            },
            text: '×'
          })
        );
      });

      // Add-shot selector for additional shots
      const remainingShots = allShots.filter((s) => !selectedShotIds.has(s.id));
      let addSelect = null;
      if (remainingShots.length > 0) {
        addSelect = h('select', {
          class: 'prompt-add-shot',
          title: 'Thêm shot vào phạm vi sửa',
          onchange: (e) => {
            const val = e.target.value;
            if (val) {
              selectedShotIds.add(val);
              explicitMultiShots = true;
              updateScopeUi();
            }
          }
        },
          h('option', { value: '', text: '+ Thêm shot...' }),
          ...remainingShots.map((s) => h('option', { value: s.id, text: `${s.id} (${s.technique || 'shot'})` }))
        );
      }

      shotsChipsWrap.replaceChildren(
        h('span', { class: 'prompt-ctl-label', text: 'Cảnh đã chọn: ' }),
        ...chips,
        ...(addSelect ? [addSelect] : [])
      );
    } else {
      shotsChipsWrap.style.display = 'none';
      shotsChipsWrap.replaceChildren();
    }
  }

  function setFormDisabled(disabled) {
    ta.disabled = disabled;
    scopeSel.disabled = disabled;
    modelSel.disabled = disabled;
    btnSubmit.disabled = disabled;
    followupChk.querySelector('input').disabled = disabled;
    const addSel = shotsChipsWrap.querySelector('select');
    if (addSel) addSel.disabled = disabled;
    shotsChipsWrap.querySelectorAll('button').forEach((b) => { b.disabled = disabled; });
  }

  async function submit() {
    const text = ta.value.trim();
    if (!text) {
      toast('Hãy nhập yêu cầu muốn sửa.', 'warn', 4000);
      ta.focus();
      return;
    }
    if (text.length > 2000) {
      toast('Yêu cầu không được quá 2000 ký tự.', 'warn', 4000);
      return;
    }

    // Save unsaved draft changes first if present
    if (ctx.store && ctx.store.snap() !== ctx.store.savedSnap) {
      const ok = await confirmDialog('Bạn có thay đổi chưa lưu trên storyboard. Lưu lại trước khi gửi cho agent?', {
        title: 'Lưu thay đổi trước khi sửa',
        ok: 'Lưu và tiếp tục',
      });
      if (!ok) return;
      if (typeof save === 'function') {
        await save();
        if (ctx.store && ctx.store.snap() !== ctx.store.savedSnap) {
          toast('Không lưu được storyboard. Hãy kiểm tra lỗi trước khi gửi.', 'err', 5000);
          return;
        }
      }
    }

    const { selShots, hasShots, curChap } = getScopeInfo();
    const effectiveScope = userScopeChoice === 'auto' ? (hasShots ? 'shots' : 'chapter') : userScopeChoice;

    let scopePayload;
    if (effectiveScope === 'shots') {
      if (!hasShots) {
        toast('Chưa chọn shot nào trong phạm vi sửa.', 'warn', 4000);
        return;
      }
      scopePayload = { shots: selShots };
    } else if (effectiveScope === 'chapter') {
      const chapters = ctx.store?.timing?.chapters || [];
      const chapIdx = curChap ? chapters.indexOf(curChap) : -1;
      const normalizedId = curChap?.id || `c${String(Math.max(0, chapIdx) + 1).padStart(2, '0')}`;
      scopePayload = { chapter: normalizedId };
    } else {
      scopePayload = { all: true };
    }

    const model = modelSel.value || undefined;
    const followup = Boolean(followupChk.querySelector('input')?.checked);
    const base_rev = ctx.store?.rev;

    setFormDisabled(true);

    try {
      const res = await api.post(`/api/projects/${encodeURIComponent(pid)}/draft/edit`, {
        instruction: text,
        scope: scopePayload,
        model,
        followup,
        base_rev,
      });
      jobId = res.job_id;
      ta.value = '';
      renderProgress();
      await loadThread();
      tick();
    } catch (e) {
      toast('Không gửi được: ' + stageErrorText('draft', e).text, 'err', 8000);
      setFormDisabled(false);
    }
  }

  async function cancel() {
    if (!jobId) return;
    try {
      await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {});
      tick();
    } catch (e) {
      toast('Không dừng được: ' + stageErrorText('draft', e).text, 'err', 8000);
    }
  }

  async function clearHistory() {
    try {
      await api.del(`/api/projects/${encodeURIComponent(pid)}/draft/thread`);
      thread = [];
      renderThread();
      toast('Đã xóa lịch sử hội thoại.', 'ok');
    } catch (e) {
      toast('Không xóa được: ' + stageErrorText('draft', e).text, 'err', 8000);
    }
  }

  function fmtTime(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  }

  function renderProgress() {
    const running = Boolean(jobId && job && ACTIVE.has(job.state)) || Boolean(jobId && !job);
    if (running) {
      const parts = (job?.parts || []).map((p) =>
        h('div', { class: 'hint' }, `${p.title}: ${p.state}${p.note ? ' - ' + p.note : ''}`)
      );
      progressBox.replaceChildren(
        h('div', { class: 'prompt-progress-banner banner' },
          h('div', { class: 'row', style: { width: '100%', alignItems: 'center' } },
            h('b', { text: 'Agent đang sửa video...' }),
            h('progress', { class: 'prompt-progress', max: 1, value: job?.progress ?? 0, style: { flex: 1, minWidth: '100px' } }),
            h('button', { class: 'small prompt-btn-cancel', onclick: cancel, text: 'Hủy' })
          ),
          ...parts
        )
      );
    } else if (job && job.state === 'error') {
      progressBox.replaceChildren(
        h('div', { class: 'banner warn' },
          h('span', { text: stageJobErrorText('draft', job).text })
        )
      );
    } else {
      progressBox.replaceChildren();
    }
  }

  function renderThread() {
    const threadItems = thread.map((t) => {
      let badgeCls = 'partial';
      let badgeText = 'Đang xử lý';
      if (t.status === 'done') {
        badgeCls = 'ok';
        badgeText = t.accepted === 'applied' ? 'Đã duyệt áp dụng' : (t.accepted === 'partially_applied' ? 'Áp dụng một phần' : 'Đã có đề xuất');
      } else if (t.status === 'no_change') {
        badgeCls = 'partial';
        badgeText = 'Không đổi';
      } else if (t.status === 'refused') {
        badgeCls = 'missing';
        badgeText = 'Từ chối (ngoài phạm vi)';
      } else if (t.status === 'cancelled' || (t.status === 'error' && t.error === 'cancelled')) {
        badgeCls = 'missing';
        badgeText = 'Đã hủy';
      } else if (t.status === 'error') {
        badgeCls = 'missing';
        badgeText = t.error === 'interrupted' ? 'Bị gián đoạn' : 'Lỗi';
      }

      const itemKids = [
        h('div', { class: 'prompt-turn-head' },
          h('span', { class: 'chip ' + badgeCls, text: badgeText }),
          h('span', { class: 'chip', text: t.scope_words || 'cả video' }),
          h('span', { class: 'muted prompt-turn-time', text: fmtTime(t.at) }),
          h('span', { class: 'grow' }),
          t.proposal_id && onProposal
            ? h('button', {
                class: 'small primary prompt-btn-open',
                onclick: () => onProposal(t.proposal_id),
                text: 'Mở đề xuất',
              })
            : null
        ),
        h('div', { class: 'prompt-turn-instruction' },
          h('b', { text: 'Bạn: ' }),
          h('span', { text: t.instruction })
        ),
      ];

      if (t.notes) {
        itemKids.push(
          h('div', { class: 'prompt-turn-notes' },
            h('b', { text: 'Agent: ' }),
            h('span', { text: t.notes })
          )
        );
      }

      if (t.error) {
        const errObj = stageErrorText('draft', { body: { code: t.error } });
        itemKids.push(
          h('div', { class: 'prompt-turn-error hint warn' },
            h('span', { text: `Lỗi: ${errObj.text}` })
          )
        );
      }

      return h('div', { class: 'prompt-turn-card' }, ...itemKids);
    });

    const threadHeader = h('div', { class: 'prompt-thread-header' },
      h('h5', { text: `Lịch sử sửa bằng prompt (${thread.length})` }),
      h('span', { class: 'grow' }),
      thread.length > 0
        ? h('button', {
            class: 'small text-btn',
            onclick: clearHistory,
            text: 'Xóa lịch sử',
            title: 'Xóa danh sách các lượt hội thoại trước',
          })
        : null
    );

    threadBox.replaceChildren(
      threadHeader,
      thread.length
        ? h('div', { class: 'prompt-thread-list' }, ...threadItems)
        : h('div', { class: 'empty muted', style: { padding: '8px 4px' }, text: 'Chưa có yêu cầu nào. Gõ yêu cầu vào ô trên để agent sửa.' })
    );
  }

  function unmount() {
    dead = true;
    clearTimeout(timer);
    offStore?.();
    offBus?.();
    root.remove();
  }

  // Initial setup
  followupChk.querySelector('input')?.addEventListener('change', (e) => {
    e.target.dataset.userToggled = 'true';
  });

  updateScopeUi();
  loadModels();
  loadThread();

  return unmount;
}
