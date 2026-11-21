// More UI checks (U1-010 and on): what the first tester could not reach, found and fixed by the front-end fixer.
//   BTI_SSH_HOST=winbox-cmd node tests/e2e/shell_library_script/run_extra.mjs [U1-010 ...]
// Same rules as run.mjs: a second instance of the app on the server (remote_server.mjs: temp COPY of projects/ and library/, the two mock agents, no network).
// U1-015 (the old "other model" dialog after a rate limit) is not here any more: the quota message with its ONE button is checked by tests/e2e/agent/agent_select.mjs.
import { launchChrome, sleep } from './lib.mjs';
import { startServer, closeServer } from './remote_server.mjs';
const srv = await startServer(); const B = srv.base;
const br = await launchChrome({ width: 1700, height: 1000 });
const J = async (m, u, b) => { const r = await fetch(B + u, { method: m, headers: { 'content-type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }); const t = await r.text(); try { return JSON.parse(t); } catch { return t; } };
const results = [];
const only = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const check = async (id, title, fn) => { if (only.length && !only.includes(id)) return; let ok = false, note = ''; try { const r = await fn(); ok = r === true; note = ok ? '' : String(r); } catch (e) { note = 'ERROR ' + e.message; } results.push({ id, ok, note }); console.log(`${ok ? 'PASS' : 'FAIL'} ${id} ${title} ${note}`); };
const job = async (id) => { for (let i = 0; i < 100; i++) { const j = await J('GET', '/api/jobs/' + id); if (['done', 'error', 'cancelled'].includes(j.state)) return j; await sleep(300); } };
const mk = async (slug, key = 'munch-the-scream', { outline = true, narration = true } = {}) => { await J('POST', '/api/library/projects', { artwork_key: key, slug });
  if (outline) { const r = await J('POST', `/api/projects/${slug}/outline/generate`, { model: 'mock' }); await job(r.job_id); const o = await J('GET', `/api/projects/${slug}/outline`); await J('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev }); }
  if (narration) { const r = await J('POST', `/api/projects/${slug}/narration/generate`, { model: 'mock' }); await job(r.job_id); } };
const open = async (p, hash, sel = '#view') => { await p.goto('about:blank', 200); await p.goto(B + '/' + hash, 800); await p.eval(`document.querySelector('#toast-root')?.replaceChildren()`); await p.waitFor(`!!document.querySelector(${JSON.stringify(sel)})`, 10000); await sleep(300); };
// the model select is gone: the agent select decides, and "Gemini 3.8 Flash" is the agent that runs the mock model on this instance (it is also the default)
const useMock = async (p) => { await p.waitFor(`(() => { const s = document.querySelector('#agent-pick-host select'); return !!s && s.options.length >= 2 && !s.disabled; })()`, 20000);
  await p.eval(`(()=>{const s=document.querySelector('#agent-pick-host select'); if (s.value !== 'gemini') { s.value='gemini'; s.dispatchEvent(new Event('change', { bubbles: true })); }})()`); };
const SHOTS = new URL('../../../.scratch/fix_shell/shots/', import.meta.url).pathname;
const caretAt = (p, sel, n) => p.eval(`(()=>{const t=document.querySelector(${JSON.stringify(sel)}); t.scrollIntoView({block:'center'}); t.focus(); t.setSelectionRange(${n < 0 ? 't.value.length' : n},${n < 0 ? 't.value.length' : n})})()`);
const rectOf = (p, expr) => p.eval(`(()=>{const e=${expr}; e.scrollIntoView({block:'center'}); const b=e.getBoundingClientRect(); return {x:b.x+b.width/2,y:b.y+b.height/2}})()`);
try {
  await mk('e-main'); await mk('e-big', 'munch-the-scream', { narration: false }); await mk('e-low', 'hemessen-self-portrait', { outline: false, narration: false });
  await J('POST', '/api/projects/e-low/brief/options', {});   // harmless: low-trust-only project keeps include_low empty
  const p = await br.newPage();

  await check('U1-010', 'a 500 KB script (800+ lines) opens and redraws in seconds, not half a minute', async () => {
    const para = 'This is a pasted sentence with exactly twenty words in it so that the counter and the parser have real work to do today ok. ';
    let big = '## c01 COLD OPEN\n'; while (big.length < 500 * 1024) big += para.repeat(5).trim() + '\n\n';
    const r = await J('POST', '/api/projects/e-big/narration/import', { text: big }); if (!r.ok) return 'import refused ' + JSON.stringify(r).slice(0, 100);
    const t0 = Date.now(); await open(p, '#/project/e-big/script', '.beat textarea'); const opened = Date.now() - t0;
    const n = await p.count('.beat'); const ms = await p.eval(`(async()=>{ const t=performance.now(); window.__scr.renderAll(); await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); return Math.round(performance.now()-t) })()`);
    return (n > 700 && ms < 3000 && opened < 15000) || `beats ${n}, redraw ${ms} ms, open ${opened} ms`; });

  await check('U1-011', 'two tabs: edits in different places merge, the same place asks, nothing typed is lost', async () => {
    const A = await br.newPage(), Bp = await br.newPage();
    await open(A, '#/project/e-main/script', '#out-thesis'); await open(Bp, '#/project/e-main/script', '#out-thesis');
    await caretAt(A, '#out-thesis', 0); await A.insert('TAB-A '); await A.key('s', 'KeyS', 4); await sleep(1200);
    await caretAt(Bp, '[data-ocard="c02"] input.ttl', 0); await Bp.insert('TAB-B-'); await Bp.key('s', 'KeyS', 4); await sleep(1800);
    const s1 = await J('GET', '/api/projects/e-main/outline');
    if (!s1.outline.thesis.startsWith('TAB-A ') || !s1.outline.chapters[1].title.startsWith('TAB-B-')) return 'merge lost something: ' + s1.outline.thesis.slice(0, 12) + ' / ' + s1.outline.chapters[1].title;
    if (await Bp.eval(`window.__scr.dirty.outline`)) return 'B still dirty after the merge and save';
    await caretAt(A, '#out-thesis', 0); await A.insert('A2 '); await A.key('s', 'KeyS', 4); await sleep(1200);
    await caretAt(Bp, '#out-thesis', 0); await Bp.insert('B2 '); await Bp.key('s', 'KeyS', 4); await sleep(1800);
    const radios = await Bp.count('#modal-root input[type=radio]'); await Bp.shot(SHOTS + 'U1-011_conflict.png');
    if (radios !== 2) return 'no conflict dialog (radios ' + radios + ')';
    if (!(await Bp.eval(`window.__scr.D.outline.thesis.startsWith('B2 ')`))) return 'B draft lost while the dialog is open';
    await Bp.click('#modal-root footer button.primary'); await sleep(1800);       // default: keep mine
    const s2 = await J('GET', '/api/projects/e-main/outline');
    return s2.outline.thesis.startsWith('B2 ') || 'kept version not saved: ' + s2.outline.thesis.slice(0, 10); });

  await check('U1-012', 'at 125% zoom the script step fits: frame not widened, toolbar buttons reachable', async () => {
    await p.resize(1280, 800, 1.25); await open(p, '#/project/e-main/script', '.beat textarea');
    const m = await p.eval(`(()=>{const R=(s)=>document.querySelector(s).getBoundingClientRect(); const v=document.querySelector('#view'); return {shell: R('#shell').right, win: innerWidth, health: R('#health').right, approve: R('#btn-approve').right, viewOver: v.scrollWidth - v.clientWidth}})()`);
    await p.shot(SHOTS + 'U1-012_after.png'); await p.resize(1700, 1000, 1);
    return (m.shell <= m.win && m.health <= m.win + 1 && m.approve <= m.win && m.viewOver <= 0) || JSON.stringify(m); });

  await check('U1-013', 'library search finds the same with and without accents (Dürer = durer, Đức = duc)', async () => {
    await open(p, '#/library', '.works');
    // the server is behind an ssh tunnel: wait for the answer to what was typed (the request with that `q`), then let the table draw
    const count = async (q) => { p.clearLogs(); await p.eval(`(()=>{const i=document.querySelector('.toolbar input[type=search]'); i.focus(); i.select()})()`); await p.key('Backspace', 'Backspace'); if (q) await p.insert(q);
      const want = (r) => /\/api\/library\/artworks\?/.test(r.url) && r.status === 200 && (q ? decodeURIComponent(r.url).includes('q=' + q) : !/[?&]q=[^&]/.test(r.url));
      for (let t0 = Date.now(); Date.now() - t0 < 8000 && !p.net.some(want);) await sleep(200);
      await sleep(900); return p.eval(`document.querySelectorAll('table.works tbody tr').length`); };
    const a = await count('Dürer'), b = await count('durer'), c = await count('DÜRER'), all = await count('');
    const d = await count('đức'), e = await count('duc');
    return (a > 0 && a === b && b === c && a < all && d === e) || `Dürer ${a}, durer ${b}, DÜRER ${c}, all ${all}, đức ${d}, duc ${e}`; });

  await check('U1-014', 'the check list can take you to an outline issue (fact card), a beat and a chapter', async () => {
    await open(p, '#/project/e-main/script', '.beat textarea'); await p.click('#btn-check'); await sleep(300);
    const links = await p.eval(`[...document.querySelectorAll('#modal-root .issue-row')].map((r,i)=>({i, go: !!r.querySelector('a.goto'), t: r.innerText}))`);
    const fact = links.find((l) => /Dữ kiện f\d+ chưa chương nào dùng/.test(l.t)); if (!fact) return 'no unused-fact issue in this project: ' + links.length + ' rows';
    const r = await rectOf(p, `document.querySelectorAll('#modal-root .issue-row')[${fact.i}].querySelector('a.goto')`); await p.clickXY(r.x, r.y); await sleep(700);
    const ok = await p.eval(`!document.querySelector('#modal-root .modal') && !!document.querySelector('[data-fact].flash')`);
    return ok || 'no jump to the fact card'; });

  await check('U1-016', 'a project with only machine-translated sources says so and does not run a model on nothing', async () => {
    await open(p, '#/project/e-low/script', '#btn-outline'); await useMock(p);
    await p.waitFor(`!!document.querySelector('#src-body .conf[role=alert]')`, 15000);          // the sources panel is drawn after the toolbar (the server is behind an ssh tunnel)
    const alert = await p.eval(`!!document.querySelector('#src-body .conf[role=alert]')`);
    await p.click('#btn-outline'); await sleep(500);
    const dlg = await p.count('#modal-root .modal'); const toast = await p.eval(`document.querySelector('#toast-root').innerText`);
    return (alert && dlg === 0 && /nguồn/.test(toast)) || JSON.stringify({ alert, dlg, toast }); });

  await check('U1-017', 'the page-image lightbox is a dialog: Esc closes it, Tab stays on its button', async () => {
    await open(p, '#/library/work/payne_gae/15', '.pages img'); await sleep(800);
    const r = await rectOf(p, `document.querySelector('.panel .pages img')`); await p.clickXY(r.x, r.y); await sleep(900);
    const a = await p.eval(`(()=>{const l=document.querySelector('.lightbox'); return !!l && l.getAttribute('role')==='dialog' && l.getAttribute('aria-modal')==='true'})()`);
    for (let i = 0; i < 3; i++) await p.key('Tab', 'Tab');
    const inside = await p.eval(`!!document.activeElement.closest('.lightbox')`); await p.key('Escape', 'Escape'); await sleep(300);
    const gone = (await p.count('.lightbox')) === 0;
    return (a && inside && gone) || JSON.stringify({ a, inside, gone }); });

  await check('U1-018', 'fact certainty select shows its whole label', async () => {
    await open(p, '#/project/e-main/script', '.beat textarea'); const w = await p.eval(`document.querySelector('[data-fact] select').getBoundingClientRect().width`);
    return w >= 120 || `select is ${Math.round(w)} px wide`; });

  await check('U1-019', 'Enter in a dialog text field presses its main button', async () => {
    await open(p, '#/library/artwork/munch-the-scream', 'h1.lib-h'); await p.click('button', 'Tạo dự án'); await sleep(300);
    await p.focus('#modal-root input[type=text]'); await p.insert('Bad Slug'); await p.key('Enter', 'Enter');
    await p.waitFor(`/slug/i.test(document.querySelector('#modal-root .note')?.textContent || '')`, 10000);          // the answer comes through the ssh tunnel
    const t = await p.text('#modal-root .note'); return /slug/i.test(t || '') || `Enter did nothing: "${t}"`; });

  await check('U1-020', 'Tách splits where the cursor is, also after a lone dash', async () => {
    await open(p, '#/project/e-main/script', '.beat textarea'); const id = await p.eval(`window.__scr.D.narr.chapters[1].beats[0].id`);
    const sel = `#beat-${id} textarea`; await p.eval(`(()=>{const t=document.querySelector(${JSON.stringify(sel)}); t.focus(); t.select()})()`); await p.key('Backspace', 'Backspace'); await p.insert('alpha — beta gamma delta'); await sleep(200);
    await p.eval(`(()=>{const t=document.querySelector(${JSON.stringify(sel)}); t.setSelectionRange(8,8)})()`);     // right after "alpha — "
    await p.click(`#beat-${id} .tools button`, 'Tách'); await sleep(1800);
    const beats = await p.eval(`window.__scr.D.narr.chapters[1].beats.slice(0,2).map(b=>b.text)`);
    return (beats[0] === 'alpha —' && beats[1] === 'beta gamma delta') || JSON.stringify(beats); });

  await check('U1-021', 'Lưu with nothing to save does not claim it saved', async () => {
    await open(p, '#/project/e-main/script', '.beat textarea'); await p.waitFor(`!!document.querySelector('#btn-save')`, 10000); await p.click('#btn-save'); await sleep(500);
    const t = await p.eval(`document.querySelector('#toast-root').innerText`); return (!/Đã lưu/.test(t) && /Không có gì/.test(t)) || t; });

  await check('U1-022', 'text pasted into the paste box survives a stray click on the backdrop and closing', async () => {
    await open(p, '#/project/e-main/script', '.beat textarea'); await p.click('#btn-paste'); await p.waitFor(`!!document.querySelector('#modal-root textarea.big')`, 4000);
    await p.click('#modal-root textarea.big'); await p.insert('this took a long time to paste'); await p.clickXY(5, 5); await sleep(300);
    const stays = (await p.count('#modal-root .modal')) === 1; await p.key('Escape', 'Escape'); await sleep(300);
    await p.click('#btn-paste'); await sleep(400); const v = await p.eval(`document.querySelector('#modal-root textarea.big').value`);
    return (stays && v === 'this took a long time to paste') || JSON.stringify({ stays, v }); });

  const runSlow = async (btn, notesText) => { await useMock(p); await p.click(btn); await p.waitFor(`!!document.querySelector('#modal-root textarea')`, 4000); await p.click('#modal-root textarea'); await p.insert(notesText); await p.click('#modal-root footer button.primary'); await sleep(1500); };
  const idle = (ms = 40000) => p.waitFor(`document.querySelector('#st-job')?.innerText.includes('Không có tác vụ')`, ms);

  await check('U1-023', 'a narration job runs; saving ANOTHER chapter meanwhile is kept and the job result is merged', async () => {
    await mk('e-job'); await open(p, '#/project/e-job/script', '.beat textarea');
    await p.eval(`document.querySelector('#chap-c03 .tools button[title="Chuyển lên"]')?.scrollIntoView()`);
    await p.click('#chap-c03 .chap-h button', 'Viết lại chương'); await p.waitFor(`!!document.querySelector('#modal-root textarea')`, 4000); await p.click('#modal-root textarea'); await p.insert('[mock:slow]'); await p.click('#modal-root footer button.primary'); await sleep(1500);
    await caretAt(p, '#chap-c05 .beat textarea', 0); await p.insert('SAVED-DURING '); await p.key('s', 'KeyS', 4); await sleep(1800);
    const mid = await J('GET', '/api/projects/e-job/narration'); const savedMid = mid.narration.chapters.find((c) => c.id === 'c05').beats[0].text.startsWith('SAVED-DURING');
    if (!savedMid) return 'the save made during the job did not reach the server';
    if (!(await idle())) return 'job did not end'; await sleep(1000);
    const fin = await J('GET', '/api/projects/e-job/narration'); const c05 = fin.narration.chapters.find((c) => c.id === 'c05').beats[0].text;
    const ui = await p.eval(`({c05: window.__scr.D.narr.chapters.find(c=>c.id==='c05').beats[0].text, dirty: window.__scr.dirty.narr, modal: !!document.querySelector('#modal-root .modal')})`);
    return (c05.startsWith('SAVED-DURING') && ui.c05.startsWith('SAVED-DURING') && !ui.dirty && !ui.modal) || JSON.stringify({ srv: c05.slice(0, 20), ui }); });

  await check('U1-024', 'a beat locked and saved while the job runs is kept, and the owner is told it was skipped', async () => {
    await open(p, '#/project/e-job/script', '.beat textarea'); const id = await p.eval(`window.__scr.D.narr.chapters.find(c=>c.id==='c03').beats[0].id`);
    const before = await p.eval(`window.__scr.D.narr.chapters.find(c=>c.id==='c03').beats[0].text`);
    await p.click('#chap-c03 .chap-h button', 'Viết lại chương'); await p.waitFor(`!!document.querySelector('#modal-root textarea')`, 4000); await p.click('#modal-root textarea'); await p.insert('[mock:slow]'); await p.click('#modal-root footer button.primary'); await sleep(1500);
    await p.click(`#beat-${id} label.chk input`); await p.key('s', 'KeyS', 4); await sleep(1800);
    if (!(await idle())) return 'job did not end'; await sleep(1000);
    const b = (await J('GET', '/api/projects/e-job/narration')).narration.chapters.find((c) => c.id === 'c03').beats.find((x) => x.id === id);
    const toast = await p.eval(`document.querySelector('#toast-root').innerText`);
    return (b && b.locked && b.text === before && /khóa/.test(toast)) || JSON.stringify({ found: !!b, locked: b?.locked, same: b?.text === before, toast }); });

  await check('U1-025', 'outline job: typing is held until it ends; an outline saved elsewhere meanwhile is never overwritten and the model text is offered', async () => {
    await mk('e-out', 'munch-the-scream', { narration: false }); await open(p, '#/project/e-out/script', '#out-thesis');
    await p.click('#btn-outline'); await p.waitFor(`!!document.querySelector('#modal-root textarea')`, 4000); await useMock(p); await p.click('#modal-root textarea'); await p.insert('[mock:slow]'); await p.click('#modal-root footer button.primary'); await sleep(1500);
    await caretAt(p, '#out-thesis', 0); await p.insert('HELD '); await p.key('s', 'KeyS', 4); await sleep(800);
    const puts = p.net.filter((r) => r.method === 'PUT' && /\/outline$/.test(r.url)).length;
    // another tab saves the outline while the model is still writing
    const o = await J('GET', '/api/projects/e-out/outline'); o.outline.thesis = 'OTHER TAB ' + o.outline.thesis;
    const put = await fetch(B + '/api/projects/e-out/outline', { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ outline: o.outline, base_rev: o.rev }) });
    // the owner's held text and the other tab's save changed the same thesis: the page asks (keep mine) before the job is over
    if (!(await p.waitFor(`document.querySelectorAll('#modal-root input[type=radio]').length === 2`, 40000))) return 'no question about the two versions of the thesis';
    await p.click('#modal-root footer button.primary');
    if (!(await idle())) return 'job did not end'; await sleep(1500);
    const srv = (await J('GET', '/api/projects/e-out/outline')).outline.thesis;
    const dlg = await p.eval(`document.querySelector('#modal-root')?.innerText || ''`);
    const ui = await p.eval(`({t: window.__scr.D.outline.thesis.slice(0, 30), dirty: window.__scr.dirty.outline, paste: (window.__scr.ST.outline.last_paste||'').length})`);
    return (puts === 0 && put.ok && srv.startsWith('OTHER TAB') && ui.t.startsWith('HELD') && ui.paste > 0 && /Dán/.test(dlg)) || JSON.stringify({ puts, put: put.status, srv: srv.slice(0, 15), ui, dlg: dlg.slice(0, 80) }); });

  console.log('console errors seen:', p.logs.length, p.logs.slice(0, 3));
} finally { br.close(); await closeServer(); }
const failed = results.filter((r) => !r.ok).length; console.log(`${results.length - failed} pass, ${failed} fail`); process.exit(failed);
