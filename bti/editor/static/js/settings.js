// The settings dialog ("Cài đặt"): on top the agent a NEW project starts on (GET /api/agents, PUT /api/settings/agent, saved at once); under a
// collapsed "Nâng cao" the table of models per role from GET /api/settings/models (one dropdown per role, one to use a single model for all,
// save with PUT), which only matters when neither the project nor the default chose an agent. Opened from the top bar ("Cài đặt").
import { api } from './api.js';
import { h, modal, toast, fillSelect } from './util.js';
import { stageErrorText } from './errmsg.js';
import { SETTINGS_LABELS as T, AGENT_LABELS as AL } from './labels.js';
import { modelRows, modelChanges, applyAllModels, modelListState, modelOptionText } from './editlogic.js';
import { defaultView, findAgent } from './agentlogic.js';
import { loadAgents } from './agentpick.js';
import { outputSwitchBox } from './outputswitch.js';          // outfolder: the switch of the output folder
import { webSearchSwitchBox } from './websearchswitch.js';  // websearch: the switch of the web search of the automatic choice of pictures

export function openModelSettings() {
  const agentBox = h('div', { class: 'settings-agent', 'data-settings-agent': '' }, h('div', { class: 'hint', text: T.loading }));
  const advBody = h('div', { class: 'settings-adv-body' }, h('div', { class: 'hint', text: T.loading }));
  const adv = h('details', { class: 'settings-advanced' }, h('summary', { text: AL.settings.advanced }),
    h('div', { class: 'hint settings-adv-hint', text: AL.settings.advancedHint }), advBody);
  const body = h('div', { class: 'body settings-body', style: { width: 'min(760px, 94vw)' } }, agentBox, outputSwitchBox(), webSearchSwitchBox(), adv);          // outfolder: + the switch; websearch: + the switch
  const dlg = modal({ title: AL.settings.title, body });
  loadAgentBox();
  load();
  return dlg;

  async function loadAgentBox() {
    let info;
    try { info = await loadAgents(); }
    catch (e) { agentBox.replaceChildren(h('div', { class: 'banner warn', text: AL.settings.saveFail + stageErrorText('settings', e).text })); return; }
    paintAgentBox(info);
  }

  function paintAgentBox(info) {
    const v = defaultView(info);
    const note = h('div', { class: 'hint warn settings-agent-why', hidden: true });
    const sel = h('select', { id: 'settings-agent-default', class: 'settings-agent-default', 'aria-label': AL.settings.defaultTitle, disabled: v.disabled || null,
      onchange: () => save(sel.value) });
    sel.replaceChildren(...v.options.map((o) => h('option', { value: o.value, text: o.text })));
    sel.value = v.value;
    const why = () => { const a = findAgent(info, sel.value); note.hidden = !(a && a.available === false); note.textContent = a ? AL.unavailable(a.label, a.reason) : ''; };
    why();
    agentBox.replaceChildren(h('h4', { text: AL.settings.defaultTitle }), h('div', { class: 'row settings-agent-row' }, h('label', { for: sel.id, text: AL.label + ':' }), sel),
      h('div', { class: 'hint', text: AL.settings.defaultHint }), note);
    let last = v.value;
    async function save(id) {
      sel.disabled = true;
      try { info = await api.put('/api/settings/agent', { agent: id }); last = id; toast(AL.settings.saved, 'ok', 2500); }
      catch (e) { sel.value = last; toast(AL.settings.saveFail + stageErrorText('settings', e).text, 'err', 8000); }
      finally { sel.disabled = false; why(); }
    }
  }

  async function load() {
    let resp;
    try { resp = await api.get('/api/settings/models'); }
    catch (e) { advBody.replaceChildren(h('div', { class: 'banner warn', text: T.loadFail + stageErrorText('settings', e).text })); return; }
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

    advBody.replaceChildren(
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
