// Shared plumbing for the storyboard end-to-end scripts that are NOT the tester's bug checks (run.mjs keeps its own copy):
// own server on a free port with a temp copy of the data, own headless Chrome, real input events over CDP. No network.
import { spawn, execSync } from 'node:child_process';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import net from 'node:net';
export const REPO = path.resolve(new URL('../../..', import.meta.url).pathname);
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const freePort = () => new Promise((res) => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PY = fs.existsSync(path.join(REPO, '.venv/bin/python')) ? path.join(REPO, '.venv/bin/python') : 'python3';

export async function boot(projects = ['arnolfini_edit', 'technique_lab', 'demo_stub', 'lab_annot']) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sbe2e-'));
  const root = path.join(tmp, 'projects'); fs.mkdirSync(root);
  for (const id of projects) execSync(`rsync -a --exclude cache --exclude history "${REPO}/projects/${id}" "${root}/"`);
  const keep = {}; for (const id of projects) keep[id] = fs.readFileSync(path.join(root, id, 'storyboard.json'));
  const restore = (id) => { for (const k of id ? [id] : Object.keys(keep)) fs.writeFileSync(path.join(root, k, 'storyboard.json'), keep[k]); };
  const sport = await freePort(), cport = await freePort();
  const server = spawn(PY, ['-m', 'uvicorn', 'bti.editor.app:create_app', '--factory', '--host', '127.0.0.1', '--port', String(sport)], { cwd: REPO, env: { ...process.env, BTI_PROJECTS_ROOT: root }, stdio: 'ignore' });
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--autoplay-policy=no-user-gesture-required', `--remote-debugging-port=${cport}`, `--user-data-dir=${path.join(tmp, 'prof')}`, '--window-size=1700,1000', 'about:blank'], { stdio: 'ignore' });
  const stop = () => { try { server.kill(); chrome.kill(); } catch {} try { fs.rmSync(tmp, { recursive: true, force: true }); } catch {} };
  process.on('exit', stop); process.on('SIGINT', () => process.exit(130));
  const B = `http://127.0.0.1:${sport}`;
  for (let i = 0; i < 100; i++) { try { if ((await fetch(B + '/api/health')).ok) break; } catch {} await sleep(300); }
  let targets; for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${cport}/json`)).json(); if (targets.find((t) => t.type === 'page')) break; } catch {} await sleep(200); }
  const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
  let id = 0; const pend = new Map(); const logs = [];
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
    else if (d.method === 'Page.javascriptDialogOpening') { logs.push('DIALOG ' + d.params.type); send('Page.handleJavaScriptDialog', { accept: true, promptText: 'X' }); }
    else if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') logs.push('console.error: ' + d.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 200));
    else if (d.method === 'Runtime.exceptionThrown') logs.push('EXC ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text).slice(0, 200)); };
  for (const m of ['Runtime', 'Page']) await send(m + '.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1700, height: 1000, deviceScaleFactor: 1, mobile: false });
  const ev = async (e) => { const r = await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true }); if (!r.result) throw new Error('eval: ' + JSON.stringify(r.error)); if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'eval'); return r.result.result.value; };
  const waitApp = async () => { await sleep(400); for (let i = 0; i < 150; i++) { try { if (await ev('!!(window.__bti&&window.__bti.store.draft&&window.__tl)')) break; } catch { /* the page is still loading */ } await sleep(200); } await sleep(1200); };
  const open = async (pid, q = '') => { await send('Page.navigate', { url: `${B}/?all=1${q}#/project/${pid}/edit` }); await sleep(500); await send('Page.reload'); await waitApp(); };
  const reload = async () => { await send('Page.reload'); await waitApp(); };
  const shot = async (file) => { const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(file, Buffer.from(r.result.data, 'base64')); };
  return { B, root, restore, ev, open, reload, shot, send, logs, stop };
}
