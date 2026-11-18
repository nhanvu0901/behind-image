// The settings dialog "Mô hình cho từng việc": one dropdown per role from GET /api/settings/models, one dropdown to use a single
// model for all, save with PUT. Opened from the top bar ("Cài đặt") and from the link in the edit box.
import { api } from './api.js';
import { h, modal, toast, fillSelect } from './util.js';
import { stageErrorText } from './errmsg.js';
import { SETTINGS_LABELS as T } from './labels.js';
import { modelRows, modelChanges, applyAllModels, modelListState, modelOptionText } from './editlogic.js';

export function openModelSettings() {
  const body = h('div', { class: 'body settings-body', style: { width: 'min(760px, 94vw)' } }, h('div', { class: 'hint', text: T.loading }));
  const dlg = modal({ title: T.title, body });
  load();
  return dlg;

  async function load() {
    let resp;
    try { resp = await api.get('/api/settings/models'); }
    catch (e) { body.replaceChildren(h('div', { class: 'banner warn', text: T.loadFail + stageErrorText('settings', e).text })); return; }
    paint(resp);
  }

  function paint(resp) {
    const rows = modelRows(resp);
    const nameOf = (id) => modelOptionText(resp.models, id);
    const down = modelListState(resp) === 'down';       // agy gave no list: one line on top, not a note on every row
    const values = Object.fromEntries(rows.map((r) => [r.role, r.value]));
    const selects = {};
    const save = h('button', { class: 'primary settings-save', text: T.save, onclick: () => doSave() });

    const roleRows = rows.map((r) => {
      const sel = h('select', { class: 'settings-model', 'data-role': r.role, 'aria-label': T.role[r.role] || r.serverLabel,
        onchange: (e) => { values[r.role] = e.target.value; } });
      fillSelect(sel, down && r.value && !r.options.includes(r.value) ? [...r.options, r.value] : r.options, r.value, nameOf);
      selects[r.role] = sel;
      return h('div', { class: 'settings-row' },
        h('label', { text: T.role[r.role] || r.serverLabel }),
        sel,
        h('span', { class: 'muted settings-src', text: r.fromSetting ? T.fromSetting : T.fromDefault }),
        r.agentic ? h('div', { class: 'hint settings-note', text: T.deepNote }) : null);
    });

    const allIds = [...new Set(rows.flatMap((r) => r.options))];
    const allSel = h('select', { class: 'settings-all', 'aria-label': T.all }, h('option', { value: '', text: T.allPick }),
      ...allIds.map((id) => h('option', { value: id, text: nameOf(id) })));
    const allBtn = h('button', { class: 'small settings-all-apply', text: T.allApply, onclick: () => {
      if (!allSel.value) return;
      const next = applyAllModels(rows, values, allSel.value);
      for (const r of rows) { values[r.role] = next[r.role]; selects[r.role].value = next[r.role]; }
    } });

    body.replaceChildren(
      h('div', { class: 'hint', text: T.intro }),
      ...(down ? [h('div', { class: 'banner warn settings-down', text: T.agyDown })] : []),
      h('div', { class: 'settings-row settings-all-row' }, h('label', { text: T.all }), allSel, allBtn),
      h('div', { class: 'settings-list' }, ...roleRows),
      h('div', { class: 'settings-foot' }, h('span', { class: 'grow' }), save));

    async function doSave() {
      const changes = modelChanges(rows, values);
      if (!Object.keys(changes).length) { toast(T.noChange, '', 2500); return; }
      save.disabled = true; save.textContent = T.saving;
      try { await api.put('/api/settings/models', changes); toast(T.saved, 'ok', 3000); dlg.close(); }
      catch (e) { toast(T.saveFail + stageErrorText('settings', e).text, 'err', 8000); save.disabled = false; save.textContent = T.save; }
    }
  }
}
