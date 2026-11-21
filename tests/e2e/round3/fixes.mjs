// Round 3 UI fix checks (own file; run.mjs belongs to the tester). Run alone:  BTI_SSH_HOST=winbox-cmd node tests/e2e/round3/fixes.mjs [F-001 ...]
// The app is a second instance ON THE SERVER (shell_library_script/remote_server.mjs: the two mock agents, temp COPIES of the data); `own()` is the same instance with the projects started over.
import { setup, sleep, fs, path } from './common.mjs';
const SH = new URL('../../../.scratch/round3_ui_fix/shots/', import.meta.url).pathname;
const only = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const SIZE = process.env.SIZE ? process.env.SIZE.split('x').map(Number) : undefined;   // SIZE=1280x720 for the small-screen screenshots
const SUF = SIZE ? '_' + SIZE.join('x') : '';
const T = await setup(SIZE, { remote: true }); const { br, J, job, openEdit, open, own } = T;
let failed = 0;
const check = async (id, title, fn) => {
  if (only.length && !only.includes(id)) return;
  let ok = false, note = '';
  try { const r = await fn(); ok = r === true; note = ok ? '' : String(r); } catch (e) { note = 'ERROR ' + String(e.message).slice(0, 300); }
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id} ${title}${note ? '  -> ' + note : ''}`); if (!ok) failed++;
};
const closeExtra = () => { while (br.pages.length > 1) { const p = br.pages.pop(); p.close(); } };
const modalBtn = (p, text) => p.click('#modal-root button', text);

/** A project whose outline and narration are both approved (mock model); returns the server and slug. */
async function approvedProject(slug) {
  const s = await own(); const A = (m, u, b) => J(m, u, b, s.base);
  await A('POST', '/api/library/projects', { artwork_key: 'munch-the-scream', slug });
  let r = await A('POST', `/api/projects/${slug}/outline/generate`, { model: 'mock' }); await job(r.job_id, s.base);
  let o = await A('GET', `/api/projects/${slug}/outline`); await A('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev });
  r = await A('POST', `/api/projects/${slug}/narration/generate`, { model: 'mock' }); await job(r.job_id, s.base);
  const n = await A('GET', `/api/projects/${slug}/narration`); await A('POST', `/api/projects/${slug}/narration/approve`, { rev: n.rev });
  return { s, A };
}
const reapproveOutline = async (A, slug, mutate) => {
  let o = await A('GET', `/api/projects/${slug}/outline`); const x = mutate(o.outline);
  await A('PUT', `/api/projects/${slug}/outline`, { outline: o.outline, base_rev: o.rev });
  o = await A('GET', `/api/projects/${slug}/outline`); await A('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev });
  return x;
};
const approveState = (p) => p.eval(`document.querySelector('#nar-badge').textContent`);

try {
  await check('F-001', 'dropdowns show the stored value: foreign intent, empty intent, foreign ease; nothing is written', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    await p.eval(`__bti.store.commit('x', d=>{ d.shots[0].intent='dance'; d.shots[1].intent=null; }); 1`);
    const lab = () => p.eval(`(()=>{const r=[...document.querySelectorAll('#tab-body .row')].find(r=>/Ý đồ/.test(r.textContent)); const s=r.querySelector('select'); return [s.selectedOptions[0].textContent, s.value, s.selectedOptions[0].disabled]})()`);
    const out = [];
    for (const i of [0, 1]) { await p.eval(`__bti.store.select(__bti.store.draft.shots[${i}].id)`); await p.click('#tabs button', 'Shot'); await sleep(300); out.push(await lab()); }
    const intents = await p.eval(`[__bti.store.draft.shots[0].intent, __bti.store.draft.shots[1].intent]`);
    await p.shot(SH + 'f001_intent' + SUF + '.png');
    p.close(); closeExtra();
    return (/dance.*không có trong danh sách/.test(out[0][0]) && out[0][1] === 'dance' && out[1][0] === '— chưa chọn —' && out[1][2] === true && intents[0] === 'dance' && intents[1] === null) || JSON.stringify([out, intents]); });

  await check('F-001b', 'a camera key with an unknown ease shows it (not "Đều")', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    const idx = await p.eval(`__bti.store.draft.shots.findIndex(s=>Array.isArray(s.params?.camera)&&s.params.camera.length)`);
    await p.eval(`__bti.store.commit('x', d=>{ d.shots[${idx}].params.camera[0].ease='wobble'; }); __bti.store.select(__bti.store.draft.shots[${idx}].id); 1`);
    await p.click('#tabs button', 'Shot'); await sleep(500);
    const txt = await p.eval(`(()=>{const s=[...document.querySelectorAll('#tab-body .kf select')].find(s=>[...s.options].some(o=>/Đều/.test(o.textContent))); return s.selectedOptions[0].textContent})()`);
    p.close(); closeExtra();
    return /wobble.*không có trong danh sách/.test(txt) || txt; });

  await check('F-002', 'script: a chapter only the narration has is removed from its header, then the narration approves; Hoàn tác brings it back', async () => {
    const { s, A } = await approvedProject('r3_x');
    const last = await reapproveOutline(A, 'r3_x', (o) => o.chapters.pop().id);
    const p = await br.newPage(); await open(p, '#/project/r3_x/script', '#nar-badge', s.base); await sleep(1500);
    await p.click('#btn-approve'); await p.waitFor(`!!document.querySelector('#modal-root [data-diff]')`, 20000);                    // refused: shows the dialog with one action per difference
    const dlg = await p.eval(`[...document.querySelectorAll('#modal-root [data-diff]')].map(r=>r.dataset.diff+':'+r.dataset.chapter+':'+[...r.querySelectorAll('button')].map(b=>b.textContent).join('/'))`);
    await p.shot(SH + 'f002_refused' + SUF + '.png');
    await p.click('#modal-root [data-act="drop"]'); await sleep(500);
    await modalBtn(p, 'Xóa'); await p.waitFor(`!document.querySelector('#chap-${last}')`, 8000); await sleep(500);
    const gone = await p.eval(`!document.querySelector('#chap-${last}')`);
    await p.eval(`document.querySelector('#btn-undo').click(); 1`); await sleep(500);
    const back = await p.eval(`!!document.querySelector('#chap-${last}')`);
    await p.eval(`document.querySelector('#btn-redo').click(); 1`); await sleep(500);
    await p.click('#btn-approve'); await p.waitFor(`/đã duyệt/.test(document.querySelector('#nar-badge').textContent)`, 10000);
    const st = await approveState(p);
    p.close(); closeExtra();
    return (dlg.length === 1 && dlg[0].startsWith('extra:' + last) && gone && back && /đã duyệt/.test(st)) || JSON.stringify({ dlg, gone, back, st }); });

  await check('F-002b', 'script: a missing chapter offers "Thêm chương trống" and "Viết chương này"; an empty one offers writing', async () => {
    const { s, A } = await approvedProject('r3_y');
    const added = await reapproveOutline(A, 'r3_y', (o) => { const c = JSON.parse(JSON.stringify(o.chapters[1])); c.id = 'c90'; c.title = 'CHƯƠNG THÊM'; o.chapters.push(c); return c.id; });
    const p = await br.newPage(); await open(p, '#/project/r3_y/script', '#nar-badge', s.base); await sleep(1500);
    const row = await p.eval(`[...document.querySelectorAll('[data-diff="missing"] button')].map(b=>b.textContent)`);
    await p.click('[data-diff="missing"] [data-act="add_empty"]'); await p.waitFor(`!!document.querySelector('#chap-${added}')`, 8000); await sleep(600);
    const empty = await p.eval(`[...document.querySelectorAll('[data-diff="empty"] button')].map(b=>b.textContent)`);
    await p.shot(SH + 'f002_empty' + SUF + '.png');
    p.close(); closeExtra();
    return (row.includes('Thêm chương trống') && row.includes('Viết chương này') && empty.includes('Viết chương này')) || JSON.stringify({ row, empty }); });

  const corrupt = async () => {
    const s = await own(); const p = await br.newPage(); await openEdit(p, 'arnolfini_edit', s.base);
    await s.writeFile('arnolfini_edit/media/durer.jpg', 'this is not an image');
    return { s, p };
  };
  await check('F-003', 'an issue with no place stays put and only shows its detail; an unused asset opens the pictures tab', async () => {
    const { p } = await corrupt();
    await p.eval(`__bti.store.select('s0005'); 1`); await sleep(500);
    await p.eval(`import('/js/inspector.js').then(m=>{ window.__sel=m.selectIssue; }); 1`); await sleep(500);
    await p.eval(`window.__sel({level:'error', code:'no_shots', path:'canvas', message:'x'}); 1`); await sleep(400);
    const stay = await p.eval('__bti.store.sel.shot');
    await p.eval(`__bti.store.commit('x', d=>{ d.assets.spare = {...d.assets[Object.keys(d.assets)[0]]}; }); 1`);
    await p.eval(`window.__sel({level:'error', code:'asset_file_unreadable', path:'assets.spare.file', message:'x', args:{asset:'spare', file:'media/x.jpg'}}); 1`); await sleep(500);
    const tab = await p.eval(`document.querySelector('#tabs button.active, #tabs button.on')?.textContent||''`);
    const still = await p.eval('__bti.store.sel.shot');
    p.close(); closeExtra();
    return (stay === 's0005' && /Hình/.test(tab) && still === 's0005') || JSON.stringify({ stay, tab, still }); });

  await check('F-004', 'a frame that cannot be drawn: placeholder text on the canvas, no handles, and it recovers', async () => {
    const { s, p } = await corrupt();
    await p.eval(`__bti.store.select('s0080')`); await sleep(2500);
    const handles = await p.eval(`document.querySelector('#handles').children.length`);
    const dark = await p.eval(`(()=>{const c=document.querySelector('#frame'); const x=c.getContext('2d'); const d=x.getImageData(c.width-30,c.height-30,1,1).data; return [d[0],d[1],d[2]]})()`);
    await p.shot(SH + 'f004_failed' + SUF + '.png');
    await p.eval(`__bti.store.select('s0005')`); await sleep(2500);
    const banner = await p.eval(`document.querySelector('#tab-body .render-fail')?.textContent||''`);
    p.close(); closeExtra();
    return (handles === 0 && dark[0] < 60 && banner === '') || JSON.stringify({ handles, dark, banner }); });

  await check('F-005', 'two tabs: after the merge the first Ctrl+Z does nothing, and the notice says so', async () => {
    const s = await own(); const a = await br.newPage(), b = await br.newPage();
    await openEdit(a, 'arnolfini_edit', s.base); await openEdit(b, 'arnolfini_edit', s.base);
    await a.eval(`__bti.store.commit('e', d=>{ d.shots[3].note='a1'; }); 1`); await a.click('#btn-save'); await a.waitFor('!__bti.store.dirty', 20000);       // (the server is behind an ssh tunnel: wait for the save, not a fixed time)
    await b.eval(`__bti.store.commit('e', d=>{ d.shots[9].note='b1'; }); 1`); await b.click('#btn-save');
    await b.waitFor(`/Hoàn tác không quay lại/.test(document.querySelector('#toast-root')?.innerText || '')`, 20000); await sleep(500);
    const toastTxt = await b.eval(`[...document.querySelectorAll('#toast-root .toast')].map(t=>t.textContent).join('|')`);
    await b.shot(SH + 'f005_merged' + SUF + '.png');
    const r = await b.eval(`[__bti.store.canUndo, __bti.store.draft.shots[3].note, __bti.store.draft.shots[9].note]`);
    a.close(); b.close(); closeExtra();
    return (r[0] === false && r[1] === 'a1' && r[2] === 'b1' && /Hoàn tác không quay lại/.test(toastTxt)) || JSON.stringify({ r, toastTxt }); });

  await check('F-006', 'script: the outline and the beats show while /api/agents is still slow; the agent select says it is loading, then fills', async () => {
    // (the old premise, "the buttons wait for the model list", is gone with the model list: the buttons only wait for a running job, the agent select loads by itself)
    const { s } = await approvedProject('r3_z');
    const p = await br.newPage();
    await p.send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => { const f = window.fetch; window.fetch = (u, ...a) => /\\/api\\/agents/.test(String(u)) ? new Promise((r) => setTimeout(r, 9000)).then(() => f(u, ...a)) : f(u, ...a); })()` });
    const t0 = Date.now();
    await p.send('Page.navigate', { url: s.base + '/#/project/r3_z/script' });
    const shown = await p.waitFor(`document.querySelectorAll('#nar-body .beat').length > 0 && document.querySelectorAll('#out-body .card').length > 0`, 7000);
    const ms = Date.now() - t0;
    const early = await p.eval(`(() => { const h = document.querySelector('#agent-pick-host'); const s = h?.querySelector('select'); return [h?.querySelector('.agent-source')?.textContent || '', s?.selectedOptions[0]?.textContent || '', !!s?.disabled, document.querySelector('#btn-write')?.disabled, document.querySelector('#btn-outline')?.disabled]; })()`);
    await p.shot(SH + 'f006_loading' + SUF + '.png');
    const later = await p.waitFor(`(() => { const s = document.querySelector('#agent-pick-host select'); return !!s && s.options.length >= 2 && !s.disabled; })()`, 25000);
    p.close(); closeExtra();
    return (shown && ms < 7500 && /Đang tải/.test(early[0] + early[1]) && early[2] === true && early[3] === false && early[4] === false && later) || JSON.stringify({ shown, ms, early, later }); });

  await check('F-007', 'script: chapters in another order than the outline show one line with "Sắp xếp theo dàn ý", which fixes it', async () => {
    const { s, A } = await approvedProject('r3_o');
    const n = await A('GET', '/api/projects/r3_o/narration'); n.narration.chapters.reverse();
    const put = await A('PUT', '/api/projects/r3_o/narration', { narration: n.narration, base_rev: n.rev });
    const p = await br.newPage(); await open(p, '#/project/r3_o/script', '#nar-badge', s.base); await sleep(1500);
    const row = await p.eval(`[...document.querySelectorAll('[data-diff="order"] button')].map(b=>b.textContent)`);
    await p.shot(SH + 'f007_order' + SUF + '.png');
    await p.click('[data-diff="order"] [data-act="order"]'); await p.waitFor(`!document.querySelector('[data-diff="order"]')`, 8000);
    const ids = await p.eval(`[...document.querySelectorAll('#nar-body .chap')].map(c=>c.id)`);
    p.close(); closeExtra();
    return (row.length === 1 && row[0] === 'Sắp xếp theo dàn ý' && ids[0] === 'chap-c01') || JSON.stringify({ put: put.detail || 'ok', row, ids }); });
} finally { await T.closeServer(); }
console.log(failed ? `\n${failed} check(s) FAIL` : '\nall checks PASS');
process.exit(failed);
