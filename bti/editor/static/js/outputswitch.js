// The one switch of the output folder in the settings dialog: clean the working folder's caches after a successful export (GET/PUT /api/settings/output, saved at once).
// The words are OUTPUT_LABELS of labels.js; a failure is told in a sentence (stageErrorText), never as the server's own text.
import { api } from './api.js';
import { h, toast } from './util.js';
import { stageErrorText } from './errmsg.js';
import { OUTPUT_LABELS as T } from './labels.js';

/** What the switch shows for the server's answer `{clean_after_export}` (on unless the answer says it is off). */
export const cleanChecked = (info) => info?.clean_after_export !== false;

export function outputSwitchBox() {
  const box = h('div', { class: 'settings-output', 'data-settings-output': '' }, h('div', { class: 'hint', text: T.loading }));
  load();
  return box;

  async function load() {
    let info;
    try { info = await api.get('/api/settings/output'); }
    catch (e) { box.replaceChildren(h('div', { class: 'banner warn', text: T.loadFail + stageErrorText('settings', e).text })); return; }
    paint(info);
  }

  function paint(info) {
    const cb = h('input', { type: 'checkbox', id: 'settings-output-clean', class: 'settings-output-clean', checked: cleanChecked(info), onchange: () => save(cb.checked) });
    box.replaceChildren(h('h4', { text: T.title }), h('div', { class: 'row settings-output-row' }, cb, h('label', { for: cb.id, text: T.clean })), h('div', { class: 'hint', text: T.hint }));
    let last = cb.checked;
    async function save(flag) {
      cb.disabled = true;
      try { await api.put('/api/settings/output', { clean_after_export: flag }); last = flag; toast(T.saved, 'ok', 2500); }
      catch (e) { cb.checked = last; toast(T.saveFail + stageErrorText('settings', e).text, 'err', 8000); }
      finally { cb.disabled = false; }
    }
  }
}
