// Re-runnable UI checks:  BTI_SSH_HOST=winbox-cmd node tests/e2e/shell_library_script/run.mjs
// Starts a second instance of the app ON THE SERVER (remote_server.mjs: its own port, temp COPY of projects/ and library/, the two MOCK agents, no network)
// through an ssh tunnel, and headless Chrome on this machine. Each check named U1-xxx asserts the correct behaviour. Exit code = number of failing checks.
import { launchChrome, sleep } from './lib.mjs';
import { startServer, closeServer } from './remote_server.mjs';
const srv = await startServer(); const B = srv.base;
const br = await launchChrome({ width: 1700, height: 1000 });
const J = async (m, u, b) => { const r = await fetch(B + u, { method: m, headers: { 'content-type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }); return r.json().catch(() => ({})); };
const results = [];
const only = process.argv.slice(2).filter((a) => !a.startsWith('--'));                  // node run.mjs U1-008 ...  runs only those
const check = async (id, title, fn) => { if (only.length && !only.includes(id)) return; let ok = false, note = ''; try { const r = await fn(); ok = r === true; note = ok ? '' : String(r); } catch (e) { note = 'ERROR ' + e.message; } results.push({ id, ok, note }); console.log(`${ok ? 'PASS' : 'FAIL'} ${id} ${title} ${note}`); };
const job = async (id) => { for (let i = 0; i < 100; i++) { const j = await J('GET', '/api/jobs/' + id); if (['done', 'error', 'cancelled'].includes(j.state)) return j; await sleep(300); } };
// A project with an approved outline and a Mock narration
const mk = async (slug) => { await J('POST', '/api/library/projects', { artwork_key: 'munch-the-scream', slug });
  let r = await J('POST', `/api/projects/${slug}/outline/generate`, { model: 'mock' }); await job(r.job_id);
  const o = await J('GET', `/api/projects/${slug}/outline`); await J('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev });
  r = await J('POST', `/api/projects/${slug}/narration/generate`, { model: 'mock' }); await job(r.job_id); };
const open = async (p, hash, sel = '#view') => { await p.goto('about:blank', 200); await p.goto(B + '/' + hash, 800); await p.eval(`document.querySelector('#toast-root')?.replaceChildren()`); await p.waitFor(`!!document.querySelector(${JSON.stringify(sel)})`, 10000); await sleep(300); };
// the model select is gone: the agent select decides, and "Gemini 3.8 Flash" is the agent that runs the mock model on this instance (it is also the default)
const useMock = async (p) => { await p.waitFor(`(() => { const s = document.querySelector('#agent-pick-host select'); return !!s && s.options.length >= 2 && !s.disabled; })()`, 20000);
  await p.eval(`(()=>{const s=document.querySelector('#agent-pick-host select'); if (s.value !== 'gemini') { s.value='gemini'; s.dispatchEvent(new Event('change', { bubbles: true })); }})()`); };
const SHOTS = new URL('../../../.scratch/uitest1/shots/', import.meta.url).pathname;
try {
  await mk('t-main'); await mk('t-del');
  const p = await br.newPage();
  await check('U1-001', 'q=đ must not behave like an empty search', async () => { const n = (await J('GET', '/api/library/artworks?kind=artwork&q=%C4%91')).length; const all = (await J('GET', '/api/library/artworks?kind=artwork')).length; return n < all || `q=đ returned ${n} of ${all}`; });
  await check('U1-002', 'server errors are Vietnamese in the create dialog', async () => {
    await open(p, '#/library/artwork/munch-the-scream', 'h1'); await p.click('button', 'Tạo dự án'); await sleep(300);
    await p.focus('#modal-root input[type=text]'); await p.insert('Bad Slug'); await p.click('#modal-root footer button.primary'); await sleep(1200);
    const t = await p.text('#modal-root .note'); await p.shot(SHOTS + 'U1-002.png'); return !/must match|already exists/.test(t || '') || `note: ${t}`; });
  await check('U1-003', 'double click on ↑ must not give a 409', async () => {
    await open(p, '#/project/t-main/script', '.beat textarea'); await useMock(p); await sleep(300);
    const id = await p.eval(`window.__scr.D.narr.chapters[0].beats[5].id`); p.clearLogs();
    const r = await p.rect(`#beat-${id} .tools button[title="Chuyển lên"]`); await p.clickXY(r.x, r.y); await p.clickXY(r.x, r.y); await sleep(1500);
    await p.shot(SHOTS + 'U1-003.png'); const bad = p.bad().filter((x) => x.startsWith('409')); return bad.length === 0 || bad.join(','); });
  await check('U1-004', 'Vietnamese word counter equals 9', async () => {
    await open(p, '#/project/t-main/script', '.beat textarea');
    await p.eval(`(()=>{const t=document.querySelector('.beat textarea'); t.focus(); t.select()})()`); await p.key('Backspace', 'Backspace'); await p.insert('Đó là ở đây để ý. Việt Nam ơi!'); await sleep(300);
    const w = await p.text('.beat .wcn'); return w.trim() === '9 từ' || `counter shows "${w}"`; });
  await check('U1-005', 'text typed during a job survives Hủy', async () => {
    await open(p, '#/project/t-main/script', '.beat textarea'); await useMock(p);
    await p.click('#btn-write'); await p.waitFor(`!!document.querySelector('#modal-root textarea')`, 4000); await p.click('#modal-root textarea'); await p.insert('[mock:slow]'); await p.click('#modal-root footer button.primary'); await sleep(1200);
    await p.eval(`(()=>{const t=document.querySelector('.beat textarea'); t.focus(); t.setSelectionRange(0,0)})()`); await p.insert('KEEPME '); await sleep(200);
    await p.click('#st-job button', 'Hủy'); await p.waitFor(`document.querySelector('#st-job')?.innerText.includes('Không có tác vụ')`, 20000); await sleep(800);
    const v = await p.eval(`document.querySelector('.beat textarea').value`); await p.shot(SHOTS + 'U1-005.png'); return v.startsWith('KEEPME') || 'typed text was discarded'; });
  await check('U1-006', 'empty paste gives feedback', async () => {
    await open(p, '#/project/t-main/script', '.beat textarea'); await p.click('#btn-paste'); await p.waitFor(`!!document.querySelector('#modal-root textarea.big')`, 4000);
    const before = await p.eval(`document.querySelector('#modal-root').innerText`); await p.click('#modal-root footer button.primary'); await sleep(500);
    const after = await p.eval(`document.querySelector('#modal-root').innerText`); const toast = await p.eval(`document.querySelector('#toast-root').innerText`); console.log('U1-006 debug', JSON.stringify({ same: before === after, toast })); await p.shot(SHOTS + 'U1-006.png'); return before !== after || toast.length > 0 || 'no feedback'; /*DBG*/ });
  // note: U1-006 diff is logged below for the report

  await check('U1-007', 'Tab stays inside a dialog', async () => {
    await open(p, '#/project/t-main/script', '.beat textarea'); await p.eval(`(()=>{const t=document.querySelector('.beat textarea'); t.focus(); t.setSelectionRange(0,0)})()`); await p.insert('x');
    await p.click('#stepper .step[data-step=artwork]'); await sleep(400); const out = [];
    for (let i = 0; i < 6; i++) { await p.key('Tab', 'Tab'); out.push(await p.eval(`!!document.activeElement.closest('#modal-root')`)); }
    await p.shot(SHOTS + 'U1-007.png'); return out.every(Boolean) || `focus inside modal per Tab: ${out}`; });
  await check('U1-008', 'project picker drops a deleted project', async () => {
    await open(p, '#/', '.prow'); await p.waitFor(`!!document.querySelector('.prow[data-pid="t-del"] button.danger')`, 8000); await p.click('.prow[data-pid="t-del"] button.danger'); await sleep(300); await p.insert('t-del'); await p.key('Enter', 'Enter'); await sleep(1500);
    const has = await p.eval(`[...document.querySelectorAll('#project-pick option')].some(o=>o.value==='t-del')`); await p.shot(SHOTS + 'U1-008.png'); return !has || 'deleted project still in picker'; });
  await check('U1-009', 'chapter word budget rejects negative / fractional values', async () => {
    await open(p, '#/project/t-main/script', '#out-body input[type=number]'); await p.eval(`(()=>{const i=document.querySelectorAll('#out-body input[type=number]')[1]; i.focus(); i.select()})()`); await p.insert('-5'); await p.key('Tab', 'Tab'); await sleep(300);
    const v = await p.eval(`window.__scr.D.outline.chapters[0].word_budget`); return v >= 0 && Number.isInteger(v) || `budget accepted: ${v}`; });
  console.log('console errors seen:', p.logs.length);
} finally { br.close(); await closeServer(); }
const failed = results.filter((r) => !r.ok).length; console.log(`${results.length - failed} pass, ${failed} fail`); process.exit(failed);
