// Re-runnable UI checks for the storyboard view. Run:  node tests/e2e/storyboard/run.mjs [U2-001 U2-007 ...]
// Starts its own server (free port, temp copy of the data, no network) and its own headless Chrome (real input events over CDP).
// Each check is named after a bug id in docs/qa/BUGS_ui_storyboard.md and asserts the CORRECT behaviour: it FAILS while the bug exists.
import { spawn, execSync } from 'node:child_process';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import net from 'node:net';
const REPO = path.resolve(new URL('../../..', import.meta.url).pathname);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const freePort = () => new Promise((res) => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PY = fs.existsSync(path.join(REPO, '.venv/bin/python')) ? path.join(REPO, '.venv/bin/python') : 'python3';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sbtest-'));
const root = path.join(tmp, 'projects'); fs.mkdirSync(root);
for (const id of ['arnolfini_edit', 'technique_lab', 'demo_stub']) execSync(`rsync -a --exclude cache --exclude history "${REPO}/projects/${id}" "${root}/"`);
const keep = {}; for (const id of ['arnolfini_edit', 'technique_lab', 'demo_stub']) keep[id] = fs.readFileSync(path.join(root, id, 'storyboard.json'));
const restore = () => { for (const id of Object.keys(keep)) fs.writeFileSync(path.join(root, id, 'storyboard.json'), keep[id]); fs.rmSync(path.join(root, 'demo_stub', 'proposals', 'x'), { force: true }); };

const sport = await freePort(), cport = await freePort();
const server = spawn(PY, ['-m', 'uvicorn', 'bti.editor.app:create_app', '--factory', '--host', '127.0.0.1', '--port', String(sport)], { cwd: REPO, env: { ...process.env, BTI_PROJECTS_ROOT: root }, stdio: 'ignore' });
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--autoplay-policy=no-user-gesture-required', `--remote-debugging-port=${cport}`, `--user-data-dir=${path.join(tmp, 'prof')}`, '--window-size=1700,1000', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { server.kill(); chrome.kill(); } catch {} try { fs.rmSync(tmp, { recursive: true, force: true }); } catch {} };
process.on('exit', cleanup); process.on('SIGINT', () => process.exit(130));
const B = `http://127.0.0.1:${sport}`;
for (let i = 0; i < 100; i++) { try { if ((await fetch(B + '/api/health')).ok) break; } catch {} await sleep(300); }
let targets; for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${cport}/json`)).json(); if (targets.find((t) => t.type === 'page')) break; } catch {} await sleep(200); }
const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map(); const dialogs = [], pageErrors = [];
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); } else if (d.method === 'Page.javascriptDialogOpening') { dialogs.push(d.params.type); send('Page.handleJavaScriptDialog', { accept: true, promptText: 'X' }); }
  else if (d.method === 'Runtime.exceptionThrown') pageErrors.push((d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text).slice(0, 160))
  else if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') pageErrors.push('console.error ' + d.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 160)); };
for (const m of ['Runtime', 'Page']) await send(m + '.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1700, height: 1000, deviceScaleFactor: 1, mobile: false });
const ev = async (e) => { const r = await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true }); if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'eval'); return r.result.result.value; };
const mouse = (type, x, y, o = {}) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, ...o });
const click = async (x, y) => { await mouse('mouseMoved', x, y, { buttons: 0 }); await mouse('mousePressed', x, y); await mouse('mouseReleased', x, y); };
const drag = async (x0, y0, x1, y1, n = 10) => { await mouse('mousePressed', x0, y0); for (let i = 1; i <= n; i++) { await mouse('mouseMoved', x0 + ((x1 - x0) * i) / n, y0 + ((y1 - y0) * i) / n); await sleep(15); } await mouse('mouseReleased', x1, y1); };
const key = async (k, code, mods = 0) => { await send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code, modifiers: mods, windowsVirtualKeyCode: k.length === 1 ? k.toUpperCase().charCodeAt(0) : ({ Delete: 46, Tab: 9, Enter: 13 }[k] || 0) }); await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, modifiers: mods }); };
const type = (t) => send('Input.insertText', { text: t });
const J = (x) => JSON.stringify(x);
async function open(pid) {
  restore(); await send('Page.navigate', { url: `${B}/?all=1#/project/${pid}/edit` }); await sleep(600); await send('Page.reload');
  await ev(`new Promise(async r=>{for(let i=0;i<100&&!window.__bti;i++) await new Promise(x=>setTimeout(x,200));r()})`); await sleep(1800);
}
const rect = (sel, txt = '') => ev(`(()=>{const e=[...document.querySelectorAll(${J(sel)})].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(${J(txt)}===''||e.textContent.includes(${J(txt)}))})[0];if(!e)return null;if(e.closest('#tab-body'))e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
const clickSel = async (sel, txt) => { const r = await rect(sel, txt); if (!r) throw new Error('missing ' + sel + ' ' + (txt || '')); await click(r.x, r.y); };
const setInput = async (sel, text) => { const r = await rect(sel); if (!r) throw new Error('missing ' + sel); await mouse('mouseMoved', r.x, r.y, { buttons: 0 }); await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: r.x, y: r.y, button: 'left', buttons: 1, clickCount: 3 }); await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: r.x, y: r.y, button: 'left', buttons: 0, clickCount: 3 }); await type(text); await sleep(150); };
const tlXY = async (t, band = 'shot', dy = 20) => JSON.parse(await ev(`JSON.stringify((()=>{const r=document.querySelector('#tl-canvas').getBoundingClientRect();return {x:r.left+__tl.X(${t}),y:r.top+__tl.Y.${band}+${dy}}})())`));
const field = (label, kind = 'number') => `#tab-body .form > .row:has(> label[title^="${label}"]) input[type=${kind}]`;
async function pickTech(techId, overlay = false) {
  if (overlay) { await clickSel('#tabs button', 'Lớp phủ'); await sleep(300); await clickSel('button', '+ Thêm lớp phủ'); } else await clickSel('.tech-card');
  await sleep(500);
  const q = JSON.parse(await ev(`JSON.stringify((()=>{const c=[...document.querySelectorAll('.gcard')].find(c=>c.querySelector('.tid')?.textContent===${J(techId)});c.scrollIntoView({block:'center'});const b=c.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+20}})())`));
  await click(q.x, q.y); await sleep(2500);
}
const settle = (ms = 2500) => sleep(ms);

const checks = {
  async 'U2-001'() { // merging shots with overlays of the same id must keep ids unique
    await open('arnolfini_edit');
    const t = await ev(`__bti.store.shotById('s0041')._t0+0.5`); const q = await tlXY(t); await click(q.x, q.y); await sleep(400);
    await clickSel('#tl-merge'); await sleep(500);
    const ids = JSON.parse(await ev(`JSON.stringify(__bti.store.shotById('s0040').overlays.map(o=>o.id))`));
    return [new Set(ids).size === ids.length, 'overlay ids after merge: ' + ids];
  },
  async 'U2-002'() { // Delete must not change the storyboard while a dialog is open
    await open('demo_stub'); const n0 = await ev('__bti.store.draft.shots.length');
    await clickSel('#btn-proposals'); await sleep(900); await key('Delete', 'Delete'); await sleep(300);
    const n1 = await ev('__bti.store.draft.shots.length'); return [n0 === n1, `shots ${n0} -> ${n1}`];
  },
  async 'U2-002b'() { // the same gate for every dialog and field: the technique gallery, the picker banner, a focused select
    await open('demo_stub'); const n0 = await ev('__bti.store.draft.shots.length'), notes = [];
    const frozen = async (label) => { for (const [k, c] of [['Delete', 'Delete'], ['s', 'KeyS'], [' ', 'Space'], ['l', 'KeyL'], ['Backspace', 'Backspace']]) await key(k, c); await sleep(300);
      const same = (await ev('__bti.store.draft.shots.length')) === n0 && !(await ev('__bti.ctx.playing')) && !(await ev('__bti.store.dirty')); notes.push(label + (same ? ' ok' : ' CHANGED')); return same; };
    await clickSel('.tech-card'); await sleep(600); const a = await frozen('gallery'); await key('Escape', 'Escape'); await sleep(300);
    await clickSel('#tab-body .slot button', 'Chọn'); await sleep(400); const b = await frozen('slot picker'); await key('Escape', 'Escape'); await sleep(300);
    const sel = await rect('#tab-body select'); await click(sel.x, sel.y); await sleep(200); await key('Escape', 'Escape');
    await ev(`document.querySelector('#tab-body select').focus()`); const c = await frozen('focused select');
    await ev(`document.activeElement.blur()`); await key(' ', 'Space'); await sleep(300); const works = await ev('__bti.ctx.playing'); if (works) await key(' ', 'Space');
    return [a && b && c && works, notes.join(', ') + `; Space on the page plays again: ${works}`];
  },
  // ---- these two need the backend rules 1 and 2 of the fix round (incomplete = warn/"incomplete", saved normally, neutral still); they FAIL against a server that predates them
  async 'BE-incomplete-save'() { // a shot with an empty required slot is incomplete: Lưu works, the server answers with a warning coded "incomplete"
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('LAY-01'); await sleep(1500);
    await clickSel('#btn-save'); await sleep(2500);
    const dirty = await ev('__bti.store.dirty'), inc = await ev(`JSON.stringify(__bti.ctx.serverIssues.filter(i=>i.code==='incomplete').map(i=>i.level+' '+i.path))`), errs = await ev(`__bti.ctx.serverIssues.filter(i=>i.level==='error').length`);
    return [!dirty && errs === 0 && inc !== '[]', `dirty after Lưu ${dirty}, server errors ${errs}, server "incomplete" warnings ${inc}`];
  },
  async 'BE-incomplete-frame'() { // the engine answers the still of an incomplete item with a neutral placeholder, not an error
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('LAY-01'); await sleep(1500);
    const r = await ev(`(async()=>{try{const b=await __bti.api.frame(__bti.ctx.pid, __bti.store.shot._t0+0.6, 480, __bti.ctx.draftPlain());return 'ok '+b.size}catch(e){return 'error '+e.status}})()`);
    return [/^ok/.test(r), 'frame of an incomplete shot: ' + r];
  },
  async 'U2-003'() { // an edit typed while a save is in flight must not be lost
    await open('arnolfini_edit'); await ev(`__bti.store.select('s0004','o1')`); await sleep(300); await clickSel('#tabs button', 'Lớp phủ'); await sleep(400);
    await setInput(field('rx'), '310'); await sleep(300);
    await ev(`document.querySelector('#btn-save').click()`); await setInput(field('ry'), '200'); await sleep(3000);
    const ry = await ev(`__bti.store.shotById('s0004').overlays[0].params.ry`), dirty = await ev('__bti.store.dirty');
    return [ry === 200 || dirty, `ry in draft ${ry}, dirty ${dirty}, input shows ${await ev(`document.querySelector(${J(field('ry'))}).value`)}`];
  },
  async 'U2-004'() { // the field must show the value that is stored (clamped)
    await open('arnolfini_edit'); await ev(`__bti.store.select('s0004','o1')`); await sleep(300); await clickSel('#tabs button', 'Lớp phủ'); await sleep(400);
    await setInput(field('rx'), '-5'); await key('Tab', 'Tab'); await sleep(700);
    const st = await ev(`__bti.store.shotById('s0004').overlays[0].params.rx`), shown = await ev(`document.querySelector(${J(field('rx'))}).value`);
    return [Number(shown) === st, `stored ${st}, shown ${shown}`];
  },
  async 'U2-005'() { // a point outside the image must be reported
    await open('arnolfini_edit'); await ev(`__bti.store.select('s0004','o1')`); await sleep(300); await clickSel('#tabs button', 'Lớp phủ'); await sleep(400);
    await setInput(field('at', 'text'), '5000, 99999'); await key('Tab', 'Tab'); await settle(3000);
    const n = await ev('__bti.ctx.issues.length'); return [n > 0, `issues after out-of-image point: ${n}`];
  },
  async 'U2-006'() { // deleting a region must not touch the file before Save
    await open('arnolfini_edit'); await clickSel('#tabs button', 'Hình'); await sleep(700); await clickSel('.asset-card', 'A:'); await sleep(500);
    const b = JSON.parse(await ev(`JSON.stringify((()=>{const it=[...document.querySelectorAll('#tab-body .list-item')].find(e=>e.querySelector('b')?.textContent==='BRUSH');const x=[...it.querySelectorAll('button')].find(b=>b.textContent==='Xóa');x.scrollIntoView({block:'center'});const q=x.getBoundingClientRect();return {x:q.x+q.width/2,y:q.y+q.height/2}})())`));
    await click(b.x, b.y); await sleep(1500);
    const disk = JSON.parse(fs.readFileSync(path.join(root, 'arnolfini_edit/storyboard.json'), 'utf8')).assets.A.regions;
    return ['BRUSH' in disk, 'BRUSH on disk before Save: ' + ('BRUSH' in disk)];
  },
  async 'U2-007'() { // a plain click on the shot band must move the playhead
    await open('arnolfini_edit'); const R = JSON.parse(await ev(`JSON.stringify((()=>{const r=document.querySelector('#tl-canvas').getBoundingClientRect();return {l:r.left,t:r.top,y:__tl.Y.shot+20}})())`));
    let moved = 0, tot = 0;
    for (let x = 40; x < 1660; x += 74) { await ev(`__bti.seek(0)`); await sleep(30); await click(R.l + x, R.t + R.y); await sleep(40); tot++; if ((await ev('__bti.ctx.t')) > 0.001) moved++; }
    return [moved === tot, `${moved}/${tot} clicks moved the playhead`];
  },
  async 'U2-008'() { // the box widget must write the registry format and raise no error
    await open('technique_lab'); await ev(`__bti.store.select('s0047')`); await sleep(1000);
    await setInput(`#tab-body .form > .row:has(> label[title^="finished_box"]) input`, '500'); await settle(3000);
    const iss = JSON.parse(await ev(`JSON.stringify(__bti.ctx.issues.filter(i=>i.level==='error').map(i=>i.message))`));
    return [iss.length === 0, 'errors: ' + iss.join('; ')];
  },
  async 'U2-009'() { // point handles must not stack on one spot (AN-03 origins are frame fractions)
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('AN-03', true); await sleep(1500);
    const pts = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#handles circle.hpt')].map(c=>{const b=c.getBoundingClientRect();return Math.round(b.x)+','+Math.round(b.y)}))`));
    return [new Set(pts).size > Math.ceil(pts.length / 2), `${pts.length} handles, ${new Set(pts).size} distinct positions`];
  },
  async 'U2-010'() { // a stale proposal must be flagged
    await open('demo_stub'); await ev(`document.querySelector('#tl-lock').click()`); await sleep(300); await clickSel('#btn-save'); await sleep(2000);
    await clickSel('#btn-proposals'); await sleep(900); await clickSel('.modal .list-item'); await sleep(1200);
    const txt = await ev(`document.querySelector('.modal .body').innerText`); return [/cũ|stale|lỗi thời/i.test(txt), 'detail mentions stale: ' + /cũ|stale|lỗi thời/i.test(txt)];
  },
  async 'U2-010b'() { // an unreadable proposal file is named in the panel and does not hide the good proposals
    await open('demo_stub'); fs.writeFileSync(path.join(root, 'demo_stub/proposals/p_bad_e2e.json'), '{ not json');
    await clickSel('#btn-proposals'); await sleep(1200);
    const txt = await ev(`document.querySelector('.modal .body').innerText`), good = await ev(`document.querySelectorAll('.modal .list-item').length`);
    fs.rmSync(path.join(root, 'demo_stub/proposals/p_bad_e2e.json'), { force: true });
    return [good >= 1 && /p_bad_e2e/.test(txt) && /không đọc được/.test(txt), `good proposals listed ${good}; banner names the bad file: ${/p_bad_e2e/.test(txt)}`];
  },
  async 'U2-011'() { // no stray "null" text in the Shot tab
    await open('technique_lab'); await ev(`__bti.store.select('s0058')`); await sleep(600);
    const has = await ev(`[...document.querySelector('#tab-body').childNodes].some(n=>n.nodeType===3&&n.textContent==='null')`); return [!has, 'stray null text: ' + has];
  },
  async 'U2-012'() { // missing slot: the preview must say why instead of "500"
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('LAY-01'); await sleep(1500);
    const s = await ev(`document.querySelector('#frame-state').textContent`); return [!/500/.test(s), 'frame-state: ' + s];
  },
  async 'U2-013'() { // an overlay that needs a mask slot must offer a slot row
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('HI-03', true); await sleep(800);
    const n = await ev(`document.querySelectorAll('#tab-body .slot').length`); return [n > 0, 'slot rows in the overlay tab: ' + n];
  },
  async 'U2-014'() { // switching technique must not put a still image into a video slot
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('LAY-04'); await sleep(800);
    const k = await ev(`(()=>{const a=__bti.store.shot.slots.inset?.asset;return a?__bti.store.draft.assets[a].kind:'empty'})()`); return [k !== 'image', 'kind of asset in slot "inset": ' + k];
  },
  async 'U2-015'() { // selecting an overlay on the timeline must bring the playhead into its shot
    await open('arnolfini_edit'); let hit = false;
    for (let dy = 4; dy < 50 && !hit; dy += 14) { const q = await tlXY(39.0, 'ov', dy); await click(q.x, q.y); await sleep(250); hit = !!(await ev('__bti.store.sel.overlay')); }
    const r = JSON.parse(await ev(`JSON.stringify({t:__bti.ctx.t,a:__bti.store.shot._t0,b:__bti.store.shot._t1,sel:__bti.store.sel})`));
    return [hit && r.t >= r.a && r.t < r.b, `playhead ${r.t}, selected shot span ${r.a}-${r.b}`];
  },
  async 'U2-016'() { // dragging a boundary to the left must move it left (observed: jumps right and sticks)
    await open('arnolfini_edit'); await ev(`(()=>{__tl.view.pps=120;__tl.view.t0=76;__tl.drawNow()})()`); await sleep(400);
    const a = await tlXY(80.01), b = await tlXY(78.0); await drag(a.x, a.y, b.x, a.y, 12); await sleep(500);
    const t0 = await ev(`__bti.store.shotById('s0011')._t0`); return [t0 < 80.01, 'boundary after dragging left: ' + t0];
  },

  // ---------------------------------------------------------------- findings of the fix round (U2-017 onwards) and coverage of what the tester could not reach
  async 'U2-004b'() { // the same out-of-range value typed twice: the field must still end up showing the stored value
    await open('arnolfini_edit'); await ev(`__bti.store.select('s0004','o1')`); await sleep(300); await clickSel('#tabs button', 'Lớp phủ'); await sleep(400);
    for (const v of ['-5', '99999', '-5']) { await setInput(field('rx'), v); await key('Tab', 'Tab'); await sleep(700); }
    const st = await ev(`__bti.store.shotById('s0004').overlays[0].params.rx`), shown = await ev(`document.querySelector(${J(field('rx'))}).value`);
    return [Number(shown) === st, `stored ${st}, shown ${shown} after typing -5, 99999, -5`];
  },
  async 'U2-006b'() { // regions are draft edits: undo, unsaved marker, disk only on Lưu; a region in use cannot be deleted; rename can update references
    await open('arnolfini_edit'); await clickSel('#tabs button', 'Hình'); await sleep(700); await clickSel('.asset-card', 'A:'); await sleep(500);
    const regionBtn = async (name, label) => { const b = JSON.parse(await ev(`JSON.stringify((()=>{const it=[...document.querySelectorAll('#tab-body .list-item')].find(e=>e.querySelector('b')?.textContent===${J(name)});const x=[...it.querySelectorAll('button')].find(b=>b.textContent===${J(label)});x.scrollIntoView({block:'center'});const q=x.getBoundingClientRect();return {x:q.x+q.width/2,y:q.y+q.height/2}})())`)); await click(b.x, b.y); await sleep(500); };
    const diskRegions = () => JSON.parse(fs.readFileSync(path.join(root, 'arnolfini_edit/storyboard.json'), 'utf8')).assets.A.regions;
    const draft = () => ev(`JSON.stringify(Object.keys(__bti.store.draft.assets.A.regions))`).then(JSON.parse);
    const notes = [];
    await regionBtn('MIRROR', 'Xóa');                                                   // in use by s0004/o1
    const dlg = await ev(`document.querySelector('.modal.ask')?.innerText||''`);
    notes.push('in-use delete: ' + (/MIRROR/.test(dlg) && /s0004/.test(dlg) ? 'refused with the items listed' : 'NOT refused: ' + dlg.slice(0, 60)));
    const refused = /MIRROR/.test(dlg) && /s0004/.test(dlg) && (await draft()).includes('MIRROR');
    await key('Escape', 'Escape'); await sleep(300);
    await regionBtn('BRUSH', 'Đổi tên'); await setInput('.modal.ask input', 'BRUSH2'); await clickSel('.modal.ask footer button', 'Đổi tên'); await sleep(600);
    const renamed = (await draft()).includes('BRUSH2') && !(await draft()).includes('BRUSH') && (await ev('__bti.store.dirty')) && 'BRUSH' in diskRegions();
    notes.push('rename in draft only: ' + renamed);
    await ev('__bti.store.undo()'); await sleep(400);
    const undone = (await draft()).includes('BRUSH') && !(await draft()).includes('BRUSH2') && !(await ev('__bti.store.dirty'));
    notes.push('undo restores it and clears the marker: ' + undone);
    await regionBtn('MIRROR', 'Đổi tên'); await setInput('.modal.ask input', 'GLASS'); await clickSel('.modal.ask footer button', 'Đổi tên'); await sleep(500);
    const askUpd = await ev(`document.querySelector('.modal.ask')?.innerText||''`);
    await clickSel('.modal.ask footer button', 'cập nhật'); await sleep(600);
    const at = await ev(`__bti.store.shotById('s0004').overlays[0].params.at`);
    notes.push('rename with references: dialog ' + /cập nhật/.test(askUpd) + ', overlay now points at ' + at);
    return [refused && renamed && undone && at === 'GLASS' && 'MIRROR' in diskRegions(), notes.join('; ')];
  },
  async 'U2-017'() { // a text "slot" is a parameter (the engine reads p["title"]); the Shot tab must not offer a second, dead input for it
    await open('technique_lab'); const id = await ev(`__bti.store.draft.shots.find(s=>['TXT-01','X-CARD-04','X-CARD-03'].includes(s.technique))?.id`);
    await ev(`__bti.store.select(${J(id)})`); await sleep(700);
    const n = await ev(`document.querySelectorAll('#tab-body .slot input[type=text]').length`), made = await ev(`JSON.stringify(Object.keys(__bti.store.shot.slots||{}))`);
    return [n === 0, `shot ${id}: ${n} text inputs among the slot rows (slots: ${made})`];
  },
  async 'U2-018'() { // moving the playhead while playing must stick (the play loop used to pull it back)
    await open('technique_lab'); await ev(`__bti.play()`); await sleep(800);
    const q = await tlXY(300, 'ruler', 8); await click(q.x, q.y); await sleep(1500);
    const t = await ev('__bti.ctx.t'); await ev(`document.querySelector('#t-play').click()`);
    return [t > 299, `playhead ${t.toFixed(2)} 1.5 s after a click at 300 s while playing`];
  },
  async 'COV-space-button'() { // after pressing a toolbar button, Space is "play", not "press the button again" (not a bug on the old code with synthetic keys; kept as coverage)
    await open('arnolfini_edit'); await clickSel('#tl-zin'); await sleep(300);
    const p1 = await ev('__tl.view.pps'); await key(' ', 'Space'); await sleep(500);
    const p2 = await ev('__tl.view.pps'), playing = await ev('__bti.ctx.playing'); if (playing) await key(' ', 'Space');
    return [Math.abs(p1 - p2) < 1e-9 && playing, `zoom ${p1.toFixed(2)} -> ${p2.toFixed(2)} px/s, playing ${playing}`];
  },
  async 'U2-020'() { // an edit made while Duyệt is in flight must stay unsaved
    await open('arnolfini_edit'); await ev(`__bti.store.commit('note', d=>{ d.shots[0].note='race'; })`); await clickSel('#btn-save'); await sleep(2500);
    const was = await ev(`document.querySelector('#btn-approve').disabled`);
    await ev(`document.querySelector('#btn-approve').click(); __bti.store.commit('typed', d=>{ d.shots[1].note='typed during approve'; }); 1`); await sleep(2500);
    const dirty = await ev('__bti.store.dirty'), kept = await ev(`__bti.store.draft.shots[1].note`);
    return [dirty && kept === 'typed during approve' && !was, `approve button was ${was ? 'disabled' : 'enabled'}; dirty ${dirty}, note ${kept}`];
  },
  async 'U2-021'() { // the app never uses the browser's confirm()/prompt()/alert()
    await open('demo_stub'); dialogs.length = 0;
    await ev(`__bti.store.commit('x', d=>{ d.shots[0].note='dirty'; })`); await clickSel('#btn-proposals'); await sleep(900); await clickSel('.modal .list-item'); await sleep(1200);
    await clickSel('.modal button.primary', 'Áp dụng'); await sleep(900);
    const ask = await ev(`!!document.querySelector('.modal.ask')`);
    return [dialogs.length === 0 && ask, `browser dialogs ${dialogs.length}, in-app confirm ${ask}`];
  },
  async 'COV-zoom'() { // zoom to both ends: clamps, nothing breaks, a click on a shot still seeks
    await open('arnolfini_edit'); const notes = [];
    for (let i = 0; i < 8; i++) await ev(`document.querySelector('#tl-zout').click()`);
    const lo = JSON.parse(await ev(`JSON.stringify({pps:__tl.view.pps,t0:__tl.view.t0,min:__tl.W/__bti.ctx.duration()})`));
    for (let i = 0; i < 25; i++) await ev(`document.querySelector('#tl-zin').click()`);
    const hi = JSON.parse(await ev(`JSON.stringify({pps:__tl.view.pps,t0:__tl.view.t0,d:__bti.ctx.duration(),W:__tl.W})`));
    await ev(`__bti.seek(0)`); const q = await tlXY(hi.t0 + 1.0); await click(q.x, q.y); await sleep(200); const t = await ev('__bti.ctx.t');
    await ev(`document.querySelector('#tl-fit').click()`); const q2 = await tlXY(100); await click(q2.x, q2.y); await sleep(200); const t2 = await ev('__bti.ctx.t');
    const ok = Math.abs(lo.pps - lo.min) < 1e-6 && lo.t0 === 0 && hi.pps === 500 && hi.t0 >= 0 && hi.t0 <= hi.d - hi.W / 500 + 1e-6 && Math.abs(t - (hi.t0 + 1)) < 0.05 && Math.abs(t2 - 100) < 0.6;
    return [ok, `min ${lo.pps.toFixed(3)} (floor ${lo.min.toFixed(3)}), max ${hi.pps}, click at max zoom -> ${t.toFixed(2)} (want ${(hi.t0 + 1).toFixed(2)}), click at fit -> ${t2.toFixed(2)}`];
  },
  async 'COV-minimap'() { // the minimap centres the view on a click, follows a drag, and never leaves the timeline
    await open('arnolfini_edit'); for (let i = 0; i < 3; i++) await ev(`document.querySelector('#tl-zin').click()`);
    const g = JSON.parse(await ev(`JSON.stringify({l:document.querySelector('#tl-canvas').getBoundingClientRect().left,t:document.querySelector('#tl-canvas').getBoundingClientRect().top,y:__tl.Y.mini+6,W:__tl.W,d:__bti.ctx.duration(),pps:__tl.view.pps})`));
    const mk = (g.W - 8) / g.d, x25 = g.l + 4 + g.d * 0.25 * mk;
    await click(x25, g.t + g.y); await sleep(200); const c1 = await ev(`__tl.view.t0 + __tl.W/__tl.view.pps/2`);
    await drag(x25, g.t + g.y, g.l + g.W + 300, g.t + g.y, 6); await sleep(200); const t0r = await ev('__tl.view.t0');
    await drag(g.l + g.W - 50, g.t + g.y, g.l - 300, g.t + g.y, 6); await sleep(200); const t0l = await ev('__tl.view.t0');
    const ok = Math.abs(c1 - g.d * 0.25) < 1 && Math.abs(t0r - (g.d - g.W / g.pps)) < 0.01 && t0l === 0;
    return [ok, `click 25% centres at ${c1.toFixed(1)} s (want ${(g.d * 0.25).toFixed(1)}); drag past right t0 ${t0r.toFixed(1)} (max ${(g.d - g.W / g.pps).toFixed(1)}); past left ${t0l}`];
  },
  async 'COV-pick'() { // "Chọn trên ảnh" gives a value in the space of the field: source px (region name or x,y) and canvas px
    await open('arnolfini_edit'); await ev(`__bti.store.select('s0004','o1')`); await sleep(300); await clickSel('#tabs button', 'Lớp phủ'); await sleep(500);
    const box = async () => JSON.parse(await ev(`JSON.stringify((()=>{const r=document.querySelector('#handles').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})())`));
    await clickSel('#tab-body button', 'Chọn trên ảnh'); await sleep(300); const b = await box(); const space1 = await ev('__bti.ctx.pick&&__bti.ctx.pick.space');
    await click(b.x + b.w * 0.3, b.y + b.h * 0.4); await sleep(500); const at = await ev(`__bti.store.shot.overlays[0].params.at`);
    await clickSel('#tab-body button', 'Chọn trên ảnh'); await sleep(300); await key('Escape', 'Escape'); await sleep(200); const cancelled = !(await ev('!!__bti.ctx.pick'));
    await open('technique_lab'); await ev(`__bti.store.select('s0035')`); await sleep(700);
    await clickSel('#tab-body button', 'Chọn trên ảnh'); await sleep(300); const b2 = await box(); const space2 = await ev('__bti.ctx.pick&&__bti.ctx.pick.space');
    await click(b2.x + b2.w * 0.25, b2.y + b2.h * 0.5); await sleep(500); const fp = await ev(`__bti.store.shot.params.from_point`);
    const ok = space1 === 'source' && (Array.isArray(at) || typeof at === 'string') && cancelled && space2 === 'canvas' && Math.abs(fp[0] - 480) <= 8 && Math.abs(fp[1] - 540) <= 8;
    return [ok, `source field: space ${space1}, value ${JSON.stringify(at)}, Esc cancels ${cancelled}; canvas field: space ${space2}, value ${JSON.stringify(fp)} (want about [480,540])`];
  },
  async 'COV-noimage'() { // a shot without a picture: no error, the view says so, canvas-space handles still work
    await open('technique_lab'); pageErrors.length = 0;
    await ev(`__bti.store.select('s0058')`); await sleep(800); await clickSel('#tabs button', 'Lớp phủ'); await sleep(300);
    await ev(`document.querySelector('#view-source').click()`); await sleep(400); const noteSrc = await ev(`document.querySelector('#map-note').textContent`);
    await ev(`document.querySelector('#view-source').click()`); await ev(`document.querySelector('#view-regions').click()`); await sleep(300); await ev(`document.querySelector('#view-regions').click()`);
    await ev(`__bti.store.select('s0035')`); await sleep(900); const handles = await ev(`document.querySelectorAll('#handles circle.hpt').length`);
    return [pageErrors.length === 0 && /không có ảnh/i.test(noteSrc) && handles === 3, `source view note "${noteSrc}", canvas-space handles on STATIC-06: ${handles}, page errors: ${pageErrors.join('; ') || 'none'}`];
  },
  async 'COV-mock'() { // ?mock=1: the editing view works on the in-browser fixtures
    restore(); await send('Page.navigate', { url: `${B}/?mock=1#/project/arnolfini-mock/edit` }); await sleep(600); await send('Page.reload'); pageErrors.length = 0;
    await ev(`new Promise(async r=>{for(let i=0;i<100&&!window.__bti;i++) await new Promise(x=>setTimeout(x,200));r()})`); await sleep(2200);
    const n = await ev('__bti.store.draft.shots.length'); const q = await tlXY(30); await click(q.x, q.y); await sleep(300);
    const sel = await ev('__bti.store.sel.shot'); await clickSel('#btn-save'); await sleep(1500); const dirty = await ev('__bti.store.dirty');
    await clickSel('#btn-approve'); await sleep(800); const dlg = await ev(`document.querySelector('.modal.ask')?.innerText||''`); await key('Escape', 'Escape');
    return [n > 3 && !!sel && !dirty && pageErrors.length === 0, `${n} shots, selected ${sel}, dirty after save ${dirty}, approve says "${dlg.split('\n')[0]}", page errors: ${pageErrors.join('; ') || 'none'}`];
  },
  async 'COV-kinds'() { // the slot picker offers only assets of the slot's kind, and an overlay can be given its mask
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('HI-03', true); await sleep(900);
    const rows = await ev(`[...document.querySelectorAll('#tab-body .slot .nm')].map(e=>e.textContent).join()`);
    await ev(`document.querySelector('.banner button')?.click()`); await sleep(300);
    // open the picker of `mask`
    const r = JSON.parse(await ev(`JSON.stringify((()=>{const row=[...document.querySelectorAll('#tab-body .slot')].find(e=>e.querySelector('.nm').textContent.startsWith('mask'));const b=[...row.querySelectorAll('button')].find(b=>b.textContent==='Chọn');b.scrollIntoView({block:'center'});const q=b.getBoundingClientRect();return {x:q.x+q.width/2,y:q.y+q.height/2}})())`));
    await click(r.x, r.y); await sleep(500);
    const cards = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('.asset-card .t')].map(e=>e.textContent.split(':')[0]))`));
    const kinds = JSON.parse(await ev(`JSON.stringify(Object.fromEntries(Object.entries(__bti.store.draft.assets).map(([k,a])=>[k,a.kind||'image'])))`));
    const onlyMasks = cards.length > 0 && cards.every((k) => kinds[k] === 'mask');
    await clickSel('.asset-card', cards[0]); await sleep(900);
    const got = await ev(`JSON.stringify(__bti.store.overlay.slots)`), inc = await ev(`JSON.stringify(__bti.ctx.incompleteOf(__bti.store.sel.shot, __bti.store.sel.overlay))`);
    return [onlyMasks && /mask/.test(rows) && got.includes(cards[0]) && inc === 'null', `overlay slot rows: ${rows}; the mask picker offers ${cards.length} assets, all masks: ${onlyMasks}; after choosing: ${got}, incomplete: ${inc}`];
  },
  async 'COV-incomplete'() { // incomplete is not invalid: marked on the timeline and in the inspector, saved, approval refused with the list
    await open('technique_lab'); await ev(`__bti.store.select('s0031')`); await sleep(400); await pickTech('HI-03', true); await sleep(1200);
    const inc = await ev(`JSON.stringify([...__bti.ctx.incomplete])`), banner = await ev(`document.querySelector('#tab-body .banner.warn')?.innerText||''`);
    const chip = await ev(`document.querySelector('#incomplete-state')?.hidden===false`);
    await clickSel('#btn-save'); await sleep(2500); const dirty = await ev('__bti.store.dirty'), errs = await ev(`__bti.ctx.issues.filter(i=>i.level==='error').length`);
    await clickSel('#btn-approve'); await sleep(900); const dlg = await ev(`document.querySelector('.modal.ask')?.innerText||''`);
    const ap = await ev(`JSON.stringify(__bti.store.draft.approvals)`);
    return [/mask/.test(inc) && /thiếu: mask/.test(banner) && chip && !dirty && errs === 0 && /mask/.test(dlg) && /chưa đủ/i.test(dlg), `incomplete ${inc}; banner "${banner.slice(0, 40)}"; chip ${chip}; saved (dirty ${dirty}, errors ${errs}); approve dialog lists mask: ${/mask/.test(dlg)}`];
  },
  async 'COV-regionimage'() { // changing the picture of a shot whose overlays point at named regions: asked, converted in one undo step
    await open('arnolfini_edit'); await ev(`__bti.store.select('s0004')`); await sleep(600);
    await clickSel('#tabs button', 'Shot'); await sleep(300); await clickSel('.slot button', 'Chọn'); await sleep(500); await clickSel('.asset-card', 'bruges:'); await sleep(900);
    const dlg = await ev(`document.querySelector('.modal.ask')?.innerText||''`);
    await clickSel('.modal.ask button', 'Đổi thành tọa độ'); await sleep(1500);
    const slot = await ev(`__bti.store.shot.slots.image.asset`), ats = await ev(`JSON.stringify(__bti.store.shot.overlays.map(o=>o.params.at))`), errs = await ev(`__bti.ctx.issues.filter(i=>/region/.test(i.message)).length`);
    await ev(`__bti.store.undo()`); await sleep(300);
    const slot2 = await ev(`__bti.store.shot.slots.image.asset`), ats2 = await ev(`JSON.stringify(__bti.store.shot.overlays.map(o=>o.params.at))`);
    return [/MIRROR/.test(dlg) && slot === 'bruges' && /\[\d+,\d+\]/.test(ats) && errs === 0 && slot2 === 'A' && ats2.includes('MIRROR'), `dialog names MIRROR: ${/MIRROR/.test(dlg)}; after: ${slot} ${ats}; region errors ${errs}; one undo: ${slot2} ${ats2}`];
  },
};

const only = process.argv.slice(2); let failed = 0, passed = 0;
for (const [name, fn] of Object.entries(checks)) {
  if (only.length && !only.includes(name)) continue;
  if (!only.length && name.startsWith('BE-') && !process.env.BE) continue;   // checks that need the new backend run with BE=1 or by name
  let ok = false, note = '';
  try { [ok, note] = await fn(); } catch (e) { note = 'exception: ' + String(e.message).slice(0, 160); }
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}  ${note}`); ok ? passed++ : failed++;
}
console.log(`\n${passed} passed, ${failed} failed (every FAIL is a known bug in docs/qa/BUGS_ui_storyboard.md)`);
process.exit(failed ? 1 : 0);
