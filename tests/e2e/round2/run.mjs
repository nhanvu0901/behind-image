// Round 2 UI checks. Run alone:  node tests/e2e/round2/run.mjs [R2U-001 ...]
// One PASS or FAIL line per check; exit code = number of FAIL. Each check asserts the CORRECT behaviour, so it FAILS while its bug exists.
// Reuses the harness of round 1 (tests/e2e/shell_library_script/lib.mjs): own server on a free port with temp COPIES of projects/ and
// library/, mock model only, own headless Chrome. No network, no real model.
import { startServer, launchChrome, sleep } from '../shell_library_script/lib.mjs';
import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

const srv = await startServer(); const B = srv.base;
const SIZE = (process.argv.find((a) => /^--size=\d+x\d+$/.test(a)) || '--size=1700x1000').slice(7).split('x').map(Number);   // --size=1280x720 for the screenshots
const br = await launchChrome({ width: SIZE[0], height: SIZE[1] });
const J = async (m, u, b, base = B) => { const r = await fetch(base + u, { method: m, headers: { 'content-type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }); const t = await r.text(); try { return JSON.parse(t); } catch { return t; } };
const job = async (id, base = B) => { for (let i = 0; i < 100; i++) { const j = await J('GET', '/api/jobs/' + id, undefined, base); if (['done', 'error', 'cancelled'].includes(j.state)) return j; await sleep(300); } };
const extra = [];                                  // other servers started by checks
const cleanup = () => { for (const s of extra) { try { s.stop(); } catch {} } try { br.close(); } catch {} try { srv.stop(); } catch {} };
process.on('exit', cleanup); process.on('SIGINT', () => process.exit(130));
const only = process.argv.slice(2).filter((a) => !a.startsWith('--'));
let failed = 0;
const check = async (id, title, fn) => {
  if (only.length && !only.includes(id)) return;
  let ok = false, note = '';
  try { const r = await fn(); ok = r === true; note = ok ? '' : String(r); } catch (e) { note = 'ERROR ' + String(e.message).slice(0, 200); }
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id} ${title}${note ? '  -> ' + note : ''}`); if (!ok) failed++;
};
const open = async (p, hash, ready = '#view') => { await p.goto('about:blank', 150); await p.goto(B + '/' + hash, 1200); await p.waitFor(`!!document.querySelector(${JSON.stringify(ready)})`, 15000); await sleep(400); };
const openEdit = async (p, pid, base = B) => { await p.goto('about:blank', 150); await p.goto(base + '/#/project/' + pid + '/edit', 1500); await p.waitFor('!!window.__bti', 20000); await sleep(1200); };
const SHOTS = new URL('../../../.scratch/round2_ui_fix/shots/', import.meta.url).pathname;

try {
  // ---- a second, disposable server for checks that stop it
  const own = async () => { const s = await startServer(); extra.push(s); return s; };

  await check('R2U-001', 'storyboard: server unreachable -> Vietnamese message, never "Failed to fetch"', async () => {
    const s = await own(); const p = await br.newPage();
    await openEdit(p, 'arnolfini_edit', s.base);
    await p.eval(`__bti.store.commit('note', d=>{ d.shots[3].note='offline'; }); 1`);
    s.stop(); await sleep(800);
    await p.eval(`document.querySelector('#toast-root').replaceChildren()`);
    await p.click('#btn-save'); await sleep(2000);
    const t = await p.eval(`document.querySelector('#toast-root').innerText`);
    await p.eval(`__bti.seek(30)`); await sleep(1500);
    const fs = await p.eval(`document.querySelector('#frame-state')?.textContent||''`);
    const dirty = await p.eval('__bti.store.dirty');
    return (!/Failed to fetch/i.test(t + fs) && /không kết nối/i.test(t) && dirty) || `toast "${t.replace(/\n/g, ' ')}", frame-state "${fs}", dirty ${dirty}`; });

  await check('R2U-002', 'storyboard: validation issues are shown in Vietnamese (arnolfini_edit has one warning from the first load)', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    await p.click('#tabs button', 'Lỗi'); await sleep(500);
    const txt = await p.eval(`document.querySelector('#tab-body').innerText`);
    const lines = txt.split('\n').filter((l) => /differs|must be|folder name/i.test(l));
    return lines.length === 0 || 'English issue text on screen: ' + lines.join(' | '); });

  await check('R2U-003', 'storyboard: the 409 dialog has no raw "(409)", does not promise an export that does not exist, and the draft can still be saved', async () => {
    const a = await br.newPage(), b = await br.newPage();
    await openEdit(a, 'arnolfini_edit'); await openEdit(b, 'arnolfini_edit');
    await a.eval(`__bti.store.commit('note', d=>{ d.shots[4].note='A'; }); 1`); await a.click('#btn-save'); await sleep(2000);
    // both tabs touch the SAME shot: not automatic (a note on another shot is merged: see R2U-003b)
    await b.eval(`__bti.store.commit('note', d=>{ d.shots[4].note='B'; }); 1`); await b.click('#btn-save'); await sleep(2000);
    const t = await b.eval(`document.querySelector('#modal-root').innerText`);
    const buttons = await b.eval(`[...document.querySelectorAll('#modal-root .modal footer button')].map(x=>x.textContent)`);
    const bad = /\(409\)/.test(t) || /xuất ra/.test(t) || buttons.length < 3;
    if (bad) return `dialog "${t.replace(/\n+/g, ' / ').slice(0, 260)}", buttons ${buttons}`;
    // "Để sau" keeps the draft; the next save asks again (never stuck); "Ghi đè" asks once more and then saves
    await b.click('#modal-root .modal footer button', 'Để sau'); await sleep(500);
    const keep = await b.eval('__bti.store.dirty && __bti.store.draft.shots[4].note');
    await b.click('#btn-save'); await sleep(1800);
    const again = await b.eval(`document.querySelectorAll('#modal-root .modal footer button').length>=3`);
    await b.click('#modal-root .modal footer button', 'Ghi đè bằng bản của tôi'); await sleep(600);
    const asked = await b.eval(`/Ghi đè/.test(document.querySelector('#modal-root').innerText) && !!document.querySelector('#modal-root .modal footer button.danger')`);
    await b.click('#modal-root .modal footer button.danger'); await sleep(2500);
    const dirty = await b.eval('__bti.store.dirty'), note = await b.eval('__bti.store.draft.shots[4].note');
    const srv = await J('GET', '/api/projects/arnolfini_edit');
    return (keep === 'B' && again && asked && !dirty && srv.storyboard.shots[4].note === 'B' && note === 'B') || `keep ${keep}, again ${again}, asked ${asked}, dirty ${dirty}, server note ${srv.storyboard.shots[4].note}`; });

  await check('R2U-003b', 'storyboard: notes on two different shots from two tabs are merged and saved, one line tells what came from the other tab', async () => {
    const s = await own();
    const a = await br.newPage(), b = await br.newPage();
    await openEdit(a, 'arnolfini_edit', s.base); await openEdit(b, 'arnolfini_edit', s.base);
    await a.eval(`__bti.store.commit('note', d=>{ d.shots[4].note='from A'; }); 1`); await a.click('#btn-save'); await sleep(2000);
    await b.eval(`__bti.store.commit('note', d=>{ d.shots[6].note='from B'; }); 1`);
    await b.eval(`document.querySelector('#toast-root').replaceChildren()`);
    await b.click('#btn-save'); await sleep(3000);
    const t = await b.eval(`document.querySelector('#toast-root').innerText`);
    const modal = await b.eval(`!!document.querySelector('#modal-root .modal')`);
    const dirty = await b.eval('__bti.store.dirty');
    const mine = await b.eval('[__bti.store.draft.shots[4].note, __bti.store.draft.shots[6].note]');
    const srv = await J('GET', '/api/projects/arnolfini_edit', undefined, s.base);
    const sn = [srv.storyboard.shots[4].note, srv.storyboard.shots[6].note];
    return (!modal && !dirty && /ghép/i.test(t) && !/409/.test(t) && mine[0] === 'from A' && mine[1] === 'from B' && sn[0] === 'from A' && sn[1] === 'from B') || `modal ${modal}, dirty ${dirty}, toast "${t.replace(/\n/g, ' ')}", draft ${mine}, server ${sn}`; });

  await check('R2U-004', 'storyboard: the intent list shows words an owner can read, not raw ids like point_at / explain_mechanism', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    const opts = await p.eval(`(()=>{const l=[...document.querySelectorAll('#tab-body .row')].find(r=>/ý đồ|intent/i.test(r.textContent)); return l? [...l.querySelectorAll('option')].map(o=>o.textContent.replace(/[ *]+$/,'')) : []})()`);
    const raw = opts.filter((o) => /^[a-z]+(_[a-z]+)+$/.test(o));
    return (opts.length > 0 && raw.length === 0) || `raw ids in the intent list: ${raw.join(', ')} (of ${opts.length})`; });

  // ------------------------------------------------------------------ neighbours of the four bugs, and the small items
  await check('R2U-001b', 'storyboard: with the server down, the clip preview and the proposals box also speak Vietnamese', async () => {
    const s = await own(); const p = await br.newPage();
    await openEdit(p, 'arnolfini_edit', s.base);
    s.stop(); await sleep(800);
    await p.eval(`document.querySelector('#toast-root').replaceChildren()`);
    await p.click('#btn-clip'); await sleep(1800);
    const t1 = await p.eval(`document.querySelector('#toast-root').innerText`);
    await p.click('#btn-proposals'); await sleep(1500);
    const t2 = await p.eval(`document.querySelector('#modal-root').innerText`);
    const all = t1 + ' ' + t2;
    return (!/Failed to fetch|TypeError|NetworkError/i.test(all) && /không kết nối/i.test(t1) && /không kết nối/i.test(t2)) || `clip "${t1.replace(/\n/g, ' ')}", proposals "${t2.replace(/\n/g, ' ').slice(0, 200)}"`; });

  await check('R2U-002b', 'storyboard: the issues tab and its counters speak Vietnamese for an unknown parameter and an unknown intent', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    await p.eval(`__bti.store.commit('x', d=>{ d.shots[1].params = { ...(d.shots[1].params||{}), zzz: 1 }; d.shots[1].intent = 'dance'; }); 1`);
    await p.click('#btn-check'); await sleep(1800);
    const txt = await p.eval(`document.querySelector('#tab-body').innerText`);
    const english = txt.split('\n').filter((l) => /\b(unknown|must|allowed|differs|not defined|is required)\b/i.test(l));
    await p.shot?.(SHOTS + SIZE[0] + '_r2_issues.png');
    return (english.length === 0 && /zzz/.test(txt) && /dance/.test(txt)) || `english: ${english.join(' | ')}; text ${txt.slice(0, 200)}`; });

  await check('R2U-004b', 'storyboard: no dropdown of the shot tab shows a raw id (ease, treatment, sides...), and the source chip is Vietnamese', async () => {
    const p = await br.newPage(); await openEdit(p, 'technique_lab');
    let raw = [], n = 0;
    for (let i = 0; i < 12; i++) {
      await p.eval(`(()=>{const s=__bti.store.draft.shots[${i}]; if(s) __bti.store.select(s.id)})()`); await sleep(250);
      const r = await p.eval(`(()=>[...document.querySelectorAll('#tab-body select')].flatMap(s=>[...s.options].map(o=>o.textContent.replace(/[ *]+$/,''))).concat([...document.querySelectorAll('#tab-body .chip')].map(c=>c.textContent)))()`);
      n += r.length; raw.push(...r.filter((o) => /^[a-z0-9]+(_[a-z0-9]+)+$|^(import|agent|human|linear)$/.test(o)));
    }
    return (n > 20 && raw.length === 0) || `raw words: ${[...new Set(raw)].join(', ')} (of ${n})`; });

  await check('R2U-S1', 'small: a project without audio asks for neither /audio nor /waveform', async () => {
    const p = await br.newPage(); await p.send('Network.enable'); p.clearLogs();
    await openEdit(p, 'technique_lab'); await sleep(800);
    const urls = p.net.map((r) => r.url);
    const bad = urls.filter((u) => /\/audio|\/waveform/.test(u));
    return bad.length === 0 || 'requests: ' + bad.join(', '); });

  await check('R2U-S1b', 'small: a project with audio still gets its waveform', async () => {
    const p = await br.newPage(); await p.send('Network.enable'); p.clearLogs();
    await openEdit(p, 'arnolfini_edit'); await sleep(800);
    return p.net.some((r) => /\/waveform/.test(r.url) && r.status === 200) || 'no waveform request'; });

  await check('R2U-S2', 'small: Backspace deletes the selected shot (like Delete) and Ctrl+Z brings it back', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    const n0 = await p.eval('__bti.store.draft.shots.length');
    await p.eval(`document.activeElement?.blur?.(); __bti.store.select(__bti.store.draft.shots[3].id)`); await sleep(300);
    await p.key('Backspace', 'Backspace'); await sleep(500);
    const ask = await p.eval(`!!document.querySelector('#modal-root .modal')`);
    if (ask) { await p.click('#modal-root .modal footer button.danger, #modal-root .modal footer button.primary'); await sleep(500); }
    const n1 = await p.eval('__bti.store.draft.shots.length');
    await p.eval(`__bti.store.undo()`); const n2 = await p.eval('__bti.store.draft.shots.length');
    return (n1 === n0 - 1 && n2 === n0) || `before ${n0}, after Backspace ${n1}, after undo ${n2}`; });

  await check('R2U-S3', 'small: the engine/media badge follows the server within seconds after the first request that works again', async () => {
    const s = await own(); const port = new URL(s.base).port;
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit', s.base);
    s.stop(); await sleep(800);
    try { await p.eval(`__bti.api.projects().catch(()=>0)`); } catch {}
    await sleep(700);
    const down = await p.eval(`document.querySelector('#health').textContent`);
    const s2 = await startServer({ port: Number(port) }); extra.push(s2);
    await p.eval(`__bti.api.projects().catch(()=>0)`);
    const up = await p.waitFor(`/engine:/.test(document.querySelector('#health').textContent)`, 4000);
    return (/không phản hồi/.test(down) && up) || `down badge "${down}", recovered ${up}`; });

  await check('R2U-S4', 'small: garbage typed into a camera field never reaches the preview as NaN', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    const has = await p.eval(`(()=>{ const i=__bti.store.draft.shots.findIndex(s=>Array.isArray(s.params?.camera)); if(i<0) return false; __bti.store.select(__bti.store.draft.shots[i].id); return true; })()`);
    if (!has) return 'no shot with a camera in arnolfini_edit';
    await sleep(600); p.clearLogs();
    for (const v of ['abc', '', '0', '-5', '1e999']) {
      await p.eval(`(()=>{ const g=[...document.querySelectorAll('#tab-body .kf-grid input')]; const zoom=g[2]; zoom.value=${JSON.stringify(v)}; zoom.dispatchEvent(new Event('change',{bubbles:true})); })()`); await sleep(200);
    }
    await sleep(600);
    const cam = await p.eval(`__bti.store.shot.params.camera.map(k=>[k.cx,k.cy,k.zoom])`);
    const finite = cam.flat().every((x) => Number.isFinite(x)) && cam.every((k) => k[2] > 0);
    const nan = p.logs.filter((l) => /NaN/.test(l));
    const svgBad = await p.eval(`[...document.querySelectorAll('svg *')].some(e=>[...e.attributes].some(a=>/NaN/.test(a.value)))`);
    return (finite && nan.length === 0 && !svgBad) || `camera ${JSON.stringify(cam)}, NaN logs ${nan.length}, svg ${svgBad}`; });

  await check('R2U-S5', 'small: the columns of the project rows on the home page line up', async () => {
    const p = await br.newPage(); await open(p, '#/', '.prow');
    const xs = await p.eval(`(()=>{ const rows=[...document.querySelectorAll('.prow')]; return rows.map(r=>[...r.children].map(c=>Math.round(c.getBoundingClientRect().x))); })()`);
    const same = xs.length > 1 && xs.every((r) => r.length === xs[0].length && r.every((x, i) => x === xs[0][i]));
    return same || 'column x per row: ' + JSON.stringify(xs); });

  // ------------------------------------------------------------------ part 2: what the backend fixes ask of the page
  await check('R2U-P1', 'home: a project whose project.json is damaged is a damaged row, cannot be opened, and Delete explains why it is refused', async () => {
    const s = await own();
    fs.mkdirSync(path.join(s.projects, 'zz_broken'), { recursive: true });
    fs.writeFileSync(path.join(s.projects, 'zz_broken', 'project.json'), '[1]');
    const p = await br.newPage();
    await p.goto('about:blank', 150); await p.goto(s.base + '/#/', 1500); await p.waitFor(`!!document.querySelector('.prow[data-pid="zz_broken"]')`, 15000); await sleep(500);
    await p.shot(SHOTS + SIZE[0] + '_p2_home_damaged.png');
    const row = await p.eval(`(()=>{const r=document.querySelector('.prow[data-pid="zz_broken"]'); const b=[...r.querySelectorAll('button')].find(x=>/Tiếp tục/.test(x.textContent)); return { text: r.innerText, openDisabled: !b || b.disabled, others: document.querySelectorAll('.prow').length }})()`);
    const pick = await p.eval(`[...document.querySelectorAll('#project-pick option')].filter(o=>/zz_broken/.test(o.textContent)).map(o=>[o.textContent,o.disabled])`);
    await p.goto('about:blank', 150); await p.goto(s.base + '/#/project/zz_broken', 1500); await sleep(1500);
    const deep = await p.eval(`document.querySelector('#view').innerText`);
    await p.goto('about:blank', 150); await p.goto(s.base + '/#/', 1500); await p.waitFor(`!!document.querySelector('.prow[data-pid="zz_broken"]')`, 15000);
    await p.click('.prow[data-pid="zz_broken"] button.danger'); await sleep(400);
    await p.eval(`(()=>{const i=document.querySelector('#modal-root input'); i.value='zz_broken'; i.dispatchEvent(new Event('input',{bubbles:true}));})()`); await sleep(200);
    await p.click('#modal-root footer button.danger'); await sleep(1500);
    const dlg = await p.eval(`document.querySelector('#modal-root').innerText`);
    await p.shot(SHOTS + SIZE[0] + '_p2_delete_damaged.png');
    const still = fs.existsSync(path.join(s.projects, 'zz_broken'));
    const ok = /Dự án hỏng/.test(row.text) && row.openDisabled && row.others >= 2 && pick.length === 1 && pick[0][1] && /hỏng/.test(deep) && /sửa hoặc xóa thư mục/.test(dlg) && !/damaged|\b409\b/.test(dlg) && still;
    return ok || `row ${JSON.stringify(row)}, picker ${JSON.stringify(pick)}, deep "${deep.slice(0, 120)}", dialog "${dlg.replace(/\n/g, ' ').slice(0, 200)}", folder kept ${still}`; });

  await check('R2U-P2', 'storyboard: Duyệt shows it is working, a second click does nothing, and an undrawable refusal lists the shots with a way to jump to them', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    await p.eval(`(()=>{ window.__calls = 0; const id = __bti.store.draft.shots[2].id; const real = __bti.api; __bti.api.approve = async () => { window.__calls++; await new Promise(r=>setTimeout(r,1800)); const e = new Error('x'); e.status = 422; e.body = { detail: 'approval refused: some shots cannot be drawn', code: 'undrawable', undrawable: true, issues: [{ level: 'error', code: 'undrawable', path: 'shots[2]', shot: id, args: { shot: id, technique: __bti.store.draft.shots[2].technique }, message: 'could not draw' }] }; throw e; }; 1 })()`);
    await p.eval(`document.querySelector('#btn-approve').disabled = false; 1`);
    await p.click('#btn-approve'); await sleep(500);
    const busy = await p.eval(`({ text: document.querySelector('#btn-approve').textContent, dis: document.querySelector('#btn-approve').disabled, status: document.querySelector('#frame-status')?.textContent })`);
    await p.eval(`document.querySelector('#btn-approve').click(); document.querySelector('#btn-approve').click(); 1`);
    await sleep(2200);
    const calls = await p.eval('window.__calls');
    const dlg = await p.eval(`document.querySelector('#modal-root').innerText`);
    await p.shot(SHOTS + SIZE[0] + '_p2_undrawable.png');
    const id = await p.eval('__bti.store.draft.shots[2].id');
    await p.click('#modal-root .list-item'); await sleep(600);
    const sel = await p.eval('__bti.store.sel.shot');
    const after = await p.eval(`document.querySelector('#btn-approve').textContent`);
    const ok = /Đang duyệt/.test(busy.text) && busy.dis && /kiểm tra/.test(busy.status || '') && calls === 1 && /không vẽ được/.test(dlg) && dlg.includes(id) && !/\b422\b|undrawable/.test(dlg) && sel === id && after === 'Duyệt';
    return ok || `busy ${JSON.stringify(busy)}, calls ${calls}, dialog "${dlg.replace(/\n/g, ' ').slice(0, 220)}", selected ${sel} (want ${id}), button after "${after}"`; });

  await check('R2U-P3', 'storyboard: a frame or a thumbnail that cannot be drawn (422 render_failed) says which shot, the page keeps working', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    const sid = await p.eval(`__bti.store.draft.shots[0].id`);
    await p.eval(`(()=>{ const f = window.fetch; window.fetch = (u, o) => { const url = String(u); if (/\\/frame/.test(url) || /__nope/.test(url)) return Promise.resolve(new Response(JSON.stringify({ detail: 'x', code: 'render_failed', shot: ${JSON.stringify(sid)}, technique: 'CAM-01' }), { status: 422, headers: { 'content-type': 'application/json' } })); return f(u, o); };
      __bti.api.thumbUrl = () => '/api/__nope.png'; 1 })()`);
    await p.eval(`__bti.seek(0.4); 1`); await sleep(1800);
    const fs1 = await p.eval(`document.querySelector('#frame-state').textContent`);
    await p.eval(`__bti.ctx.renderKey = 'k2'; __bti.seek(0.6); window.dispatchEvent(new Event('resize')); 1`); await sleep(2200);
    const fails = await p.eval(`[...__bti.ctx.thumbFails.values()]`);
    const failed = await p.eval(`[...__bti.ctx.thumbFails.keys()][0].split('|')[0]`);      // the thumbnails are drawn for the wide shots only
    await p.eval(`__bti.store.select(${JSON.stringify(failed)}); 1`); await p.click('#tabs button', 'Shot'); await sleep(600);
    const banner = await p.eval(`document.querySelector('#tab-body .render-fail')?.textContent || ''`);
    await p.shot(SHOTS + SIZE[0] + '_p2_render_failed.png');
    const alive = await p.eval(`!!document.querySelector('#timeline canvas') && __bti.store.draft.shots.length > 0`);
    const ok = fs1.includes(sid) && /không dựng được/i.test(fs1) && !/422|render_failed/.test(fs1) && fails.length >= 1 && fails[0].includes(sid) && banner.length > 10 && alive;
    return ok || `frame-state "${fs1}", thumb fails ${JSON.stringify(fails)}, banner "${banner}", alive ${alive}`; });

  await check('R2U-P4', 'storyboard form: a string with a pattern shows its hint and is marked when wrong; a list with fixed size cannot grow or shrink', async () => {
    const p = await br.newPage(); await openEdit(p, 'technique_lab');
    const found = await p.eval(`(()=>{ const reg=__bti.ctx.reg.list; const sh=__bti.store.draft.shots; for (const t of reg) { const def=t.params.find(d=>d.pattern_hint && (d.type==='string'||d.type==='text')); if (!def) continue; const i=sh.findIndex(s=>s.technique===t.id); if (i>=0) return {i, tech:t.id, name:def.name, hint:def.pattern_hint}; } return null; })()`);
    if (!found) return 'no shot of technique_lab uses a technique with a pattern_hint';
    await p.eval(`__bti.store.select(__bti.store.draft.shots[${found.i}].id); 1`); await p.click('#tabs button', 'Shot'); await sleep(700);
    const note = await p.eval(`[...document.querySelectorAll('#tab-body .row')].filter(r=>r.querySelector('label')?.textContent===${JSON.stringify(found.name)}).map(r=>r.querySelector('.field-note')?.textContent||'')[0]`);
    await p.eval(`(()=>{ const r=[...document.querySelectorAll('#tab-body .row')].find(r=>r.querySelector('label')?.textContent===${JSON.stringify(found.name)}); const i=r.querySelector('input[type=text],textarea'); i.value='@@ bad @@'; i.dispatchEvent(new Event('input',{bubbles:true})); })()`); await sleep(700);
    const marked = await p.eval(`(()=>{ const r=[...document.querySelectorAll('#tab-body .row')].find(r=>r.querySelector('label')?.textContent===${JSON.stringify(found.name)}); return r ? { cls: r.className, note: r.querySelector('.field-note')?.textContent } : null })()`);
    return (note === found.hint && marked && /field-problem/.test(marked.cls) && marked.note.length > 0) || `hint shown "${note}" (want "${found.hint}"), after bad value ${JSON.stringify(marked)}`; });


  await check('R2U-P5', 'script: after the outline changes, the approved narration says why it no longer stands; a refused approval lists the differing chapters', async () => {
    const s = await own(); const slug = 'r2u_p5';
    const A = (m, u, b) => J(m, u, b, s.base);
    await A('POST', '/api/library/projects', { artwork_key: 'munch-the-scream', slug });
    let r = await A('POST', `/api/projects/${slug}/outline/generate`, { model: 'mock' }); await job(r.job_id, s.base);
    let o = await A('GET', `/api/projects/${slug}/outline`); await A('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev });
    r = await A('POST', `/api/projects/${slug}/narration/generate`, { model: 'mock' }); await job(r.job_id, s.base);
    let n = await A('GET', `/api/projects/${slug}/narration`); const ap = await A('POST', `/api/projects/${slug}/narration/approve`, { rev: n.rev });
    if (ap.approved !== true) return 'narration approve failed: ' + JSON.stringify(ap).slice(0, 200);
    // the outline changes (thesis edited), then it is approved again: the narration approval must not stand
    o = await A('GET', `/api/projects/${slug}/outline`);
    const doc = o.outline; doc.thesis = (doc.thesis || 'x') + ' (đã sửa)';
    const put = await A('PUT', `/api/projects/${slug}/outline`, { outline: doc, base_rev: o.rev });
    o = await A('GET', `/api/projects/${slug}/outline`); await A('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev });
    const p = await br.newPage();
    await p.goto('about:blank', 150); await p.goto(s.base + '/#/project/' + slug + '/script', 1500); await p.waitFor(`!!document.querySelector('#nar-badge')`, 15000); await sleep(1500);
    const badge = await p.eval(`document.querySelector('#nar-badge').textContent`);
    const note = await p.eval(`document.querySelector('.approval-note')?.innerText || ''`);
    await p.shot(SHOTS + SIZE[0] + '_p2_script_outline_changed.png');
    const ok1 = /dàn ý đã đổi/.test(badge) && /đã được duyệt cho một bản dàn ý cũ/.test(note) && !/outline_changed/.test(badge + note);
    // chapters that differ: drop a chapter from the narration through the API, then approve from the page
    n = await A('GET', `/api/projects/${slug}/narration`);
    const nd = n.narration; nd.chapters.push({ id: 'c99', title: 'THỪA', card: false, beats: [{ id: 'b9999', text: 'Một dòng thừa.', facts: [], show: [], note: '', locked: false }] });
    const put2 = await A('PUT', `/api/projects/${slug}/narration`, { narration: nd, base_rev: n.rev });
    await p.goto('about:blank', 150); await p.goto(s.base + '/#/project/' + slug + '/script', 1500); await p.waitFor(`!!document.querySelector('#nar-badge')`, 15000); await sleep(1500);
    await p.click('#btn-approve'); await sleep(2500);
    const dlg = await p.eval(`document.querySelector('#modal-root').innerText`);
    await p.shot(SHOTS + SIZE[0] + '_p2_script_chapter_diff.png');
    const ok2 = /c99/.test(dlg) && /không có trong dàn ý/.test(dlg) && !/not_in_outline|chapter_diff/.test(dlg);
    return (ok1 && ok2) || `badge "${badge}", note "${note.slice(0, 160)}", dialog "${dlg.replace(/\n/g, ' ').slice(0, 220)}", put ${JSON.stringify(put).slice(0, 80)} ${JSON.stringify(put2).slice(0, 80)}`; });

  await check('R2U-P6', 'script: when the Antigravity command does not answer, the model list says so and "Thử lại" asks the server again (?refresh=1)', async () => {
    const models = await J('GET', '/api/models');
    const bad = models.find((m) => m.agy && m.agy.ok === false);
    const p = await br.newPage(); await p.send('Network.enable'); p.clearLogs();
    await open(p, '#/project/arnolfini-from-books/script', '#model-pick'); await sleep(800);
    const note = await p.eval(`({ hidden: document.querySelector('#model-note').hidden, text: document.querySelector('#model-note').innerText })`);
    await p.shot(SHOTS + SIZE[0] + '_p2_models_note.png');
    if (!bad) return note.hidden || 'note shown although every model answered';
    if (note.hidden || !/Antigravity/.test(note.text)) return 'no note although agy is not ok: ' + JSON.stringify(note);
    p.clearLogs(); await p.click('#btn-models-retry'); await sleep(8000);
    const asked = p.net.some((r) => /\/api\/models\?refresh=1/.test(r.url));
    return (asked && !/timeout|config/.test(note.text)) || `refresh asked ${asked}, note "${note.text}"`; });

  await check('R2U-P6b', 'script: with a model list that carries agy {ok: false}, the note shows and "Thử lại" clears it when the next answer is fine', async () => {
    const p = await br.newPage(); await p.send('Network.enable'); p.clearLogs();
    await open(p, '#/', '.prow');
    await p.eval(`(()=>{ const f = window.fetch; window.fetch = async (u, o) => { const r = await f(u, o); if (!/\\/api\\/models(\\?|$)/.test(String(u)) || /refresh=1/.test(String(u))) return r; const j = await r.json(); const a = j.find((m) => /antigravity|agy/i.test(m.id)) || j[0]; a.agy = { ok: false, reason: 'timeout' }; return new Response(JSON.stringify(j), { status: 200, headers: { 'content-type': 'application/json' } }); }; location.hash = '#/project/arnolfini-from-books/script'; 1 })()`);
    await p.waitFor(`!!document.querySelector('#model-note') && !document.querySelector('#model-note').hidden`, 10000); await sleep(500);
    const t1 = await p.eval(`document.querySelector('#model-note').innerText`);
    await p.shot(SHOTS + SIZE[0] + '_p2_models_flag.png');
    p.clearLogs(); await p.click('#btn-models-retry');
    await p.waitFor(`document.querySelector('#model-note').hidden`, 20000);      // the server may really ask the command (up to its time limit)
    const asked = p.net.some((r) => /\/api\/models\?refresh=1/.test(r.url));
    const hidden = await p.eval(`document.querySelector('#model-note').hidden`);
    return (/Antigravity.*không trả lời kịp/.test(t1) && asked && hidden) || `note "${t1}", refresh asked ${asked}, hidden after ${hidden}`; });
} finally { /* cleanup runs on exit */ }
console.log(failed ? `\n${failed} check(s) FAIL` : '\nall checks PASS');
process.exit(failed);
