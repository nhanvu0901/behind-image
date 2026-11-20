// The one switch of the web search of the automatic choice of pictures in the settings dialog (GET/PUT /api/settings/web-search, saved at once):
// "Tìm hình trên web khi chọn hình tự động". Off unless the owner switched it on; it is the owner's standing permission for a paid search (You.com).
// The words are WEBSEARCH_LABELS of labels.js; a failure is told in a sentence (stageErrorText), never as the server's own text.
import { api } from './api.js';
import { h, toast } from './util.js';
import { stageErrorText } from './errmsg.js';
import { WEBSEARCH_LABELS as T } from './labels.js';

/** What the switch shows for the server's answer `{auto_web_search, auto_web_search_max}`: on only when the answer says "on". */
export const webSearchChecked = (info) => info?.auto_web_search === 'on';

/** The sentence under the switch: what it costs, with the number of searches one run may make. */
export const webSearchHint = (info) => T.hint(Number.isInteger(info?.auto_web_search_max) ? info.auto_web_search_max : 80);

export function webSearchSwitchBox() {
  const box = h('div', { class: 'settings-websearch', 'data-settings-websearch': '' }, h('div', { class: 'hint', text: T.loading }));
  load();
  return box;

  async function load() {
    let info;
    try { info = await api.get('/api/settings/web-search'); }
    catch (e) { box.replaceChildren(h('div', { class: 'banner warn', text: T.loadFail + stageErrorText('settings', e).text })); return; }
    paint(info);
  }

  function paint(info) {
    const cb = h('input', { type: 'checkbox', id: 'settings-websearch-on', class: 'settings-websearch-on', checked: webSearchChecked(info), onchange: () => save(cb.checked) });
    box.replaceChildren(h('h4', { text: T.title }), h('div', { class: 'row settings-websearch-row' }, cb, h('label', { for: cb.id, text: T.on })), h('div', { class: 'hint', text: webSearchHint(info) }));
    let last = cb.checked;
    async function save(flag) {
      cb.disabled = true;
      try { await api.put('/api/settings/web-search', { auto_web_search: flag ? 'on' : 'off' }); last = flag; toast(T.saved, 'ok', 2500); }
      catch (e) { cb.checked = last; toast(T.saveFail + stageErrorText('settings', e).text, 'err', 8000); }
      finally { cb.disabled = false; }
    }
  }
}
