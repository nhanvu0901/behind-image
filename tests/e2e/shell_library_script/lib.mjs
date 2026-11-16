// Minimal CDP driver + server launcher for the shell/library/script UI checks. No dependencies (Node 22+).
import { spawn, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, '../../..');
export const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function freePort() {
  return new Promise((res) => { const s = net.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });
}

/** Copy the data to a temp dir and start the editor on a free port. LIB_DIR is redirected to the copy from a launcher
 *  (the product has no environment variable for it), so merge/split never touch the real library. */
export async function startServer({ port, projectsSrc, libSrc, tmp } = {}) {
  tmp = tmp || fs.mkdtempSync(path.join(os.tmpdir(), 'bti-e2e-'));
  const projects = path.join(tmp, 'projects'), lib = path.join(tmp, 'library');
  fs.mkdirSync(projects, { recursive: true });
  for (const d of fs.readdirSync(projectsSrc || path.join(REPO, 'projects'))) {
    execSync(`rsync -a --exclude cache --exclude history "${path.join(projectsSrc || path.join(REPO, 'projects'), d)}" "${projects}/"`);
  }
  execSync(`rsync -a "${libSrc || path.join(REPO, 'library')}/" "${lib}/"`);
  port = port || (await freePort());
  const py = fs.existsSync(path.join(REPO, '.venv/bin/python')) ? path.join(REPO, '.venv/bin/python') : 'python3';
  const launcher = path.join(tmp, 'serve.py');
  fs.writeFileSync(launcher, `import sys, pathlib\nfrom bti.library import config\nconfig.LIB_DIR = pathlib.Path(sys.argv[1]).resolve()\nimport uvicorn\nfrom bti.editor.app import create_app\nuvicorn.run(create_app(), host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")\n`);
  const env = { ...process.env, BTI_PROJECTS_ROOT: projects, PYTHONPATH: REPO, BTI_ENV_FILE: path.join(tmp, 'no.env') };
  delete env.OPENROUTER_API_KEY;
  const proc = spawn(py, [launcher, lib, String(port)], { env, cwd: REPO, stdio: ['ignore', fs.openSync(path.join(tmp, 'server.log'), 'w'), 2] });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 60; i++) { try { if ((await fetch(base + '/api/health')).ok) break; } catch {} await sleep(300); }
  return { base, port, tmp, projects, lib, stop: () => { proc.kill(); } };
}

export async function launchChrome({ width = 1700, height = 1000, zoom = 1 } = {}) {
  const port = await freePort();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'bti-chrome-'));
  const proc = spawn(CHROME, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${port}`, `--user-data-dir=${dir}`, `--window-size=${width},${height}`, 'about:blank'], { stdio: 'ignore' });
  let targets;
  for (let i = 0; i < 60; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (targets.find((t) => t.type === 'page')) break; } catch {} await sleep(200); }
  const br = { port, proc, dir, pages: [], close() { try { proc.kill(); } catch {} try { fs.rmSync(dir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch {} } };
  br.newPage = async (opts = {}) => {
    let t;
    if (!br.pages.length) t = targets.find((x) => x.type === 'page');
    else t = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
    const p = await makePage(t.webSocketDebuggerUrl, { width, height, ...opts });
    br.pages.push(p); return p;
  };
  return br;
}

async function makePage(wsUrl, { width, height }) {
  const ws = new WebSocket(wsUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const pend = new Map();
  const logs = [], net = [], dialogs = []; let dialogAnswer = true; const reqs = new Map();
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); return; }
    const P = d.params || {};
    if (d.method === 'Page.javascriptDialogOpening') { dialogs.push({ type: P.type, message: P.message }); send('Page.handleJavaScriptDialog', { accept: dialogAnswer }); }
    else if (d.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(P.type)) logs.push(P.type + ': ' + P.args.map((a) => a.value ?? a.description).join(' '));
    else if (d.method === 'Runtime.exceptionThrown') logs.push('EXCEPTION: ' + (P.exceptionDetails.exception?.description || P.exceptionDetails.text));
    else if (d.method === 'Log.entryAdded' && P.entry.level === 'error') logs.push('LOG: ' + P.entry.text + ' ' + (P.entry.url || ''));
    else if (d.method === 'Network.requestWillBeSent') reqs.set(P.requestId, { method: P.request.method, url: P.request.url, body: P.request.postData });
    else if (d.method === 'Network.responseReceived') { const r = reqs.get(P.requestId); if (r) { r.status = P.response.status; net.push(r); } }
    else if (d.method === 'Network.loadingFailed') { const r = reqs.get(P.requestId); if (r && !P.canceled) net.push({ ...r, status: 0, err: P.errorText }); }
  };
  for (const m of ['Runtime', 'Log', 'Page', 'Network']) await send(m + '.enable');
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
  const page = {
    send, logs, net, dialogs,
    setDialog(accept) { dialogAnswer = accept; },
    clearLogs() { logs.length = 0; net.length = 0; dialogs.length = 0; },
    bad() { return net.filter((r) => r.status >= 400 || r.status === 0).map((r) => `${r.status} ${r.method} ${r.url.replace(/^https?:\/\/[^/]+/, '')}`); },
    async resize(w, h, zoom = 1) { await send('Emulation.setDeviceMetricsOverride', { width: Math.round(w / zoom), height: Math.round(h / zoom), deviceScaleFactor: zoom, mobile: false }); },
    async goto(url, ms = 1200) { await send('Page.navigate', { url }); await sleep(ms); await page.idle(); },
    async idle(timeout = 8000) { const t0 = Date.now(); while (Date.now() - t0 < timeout) { const v = await page.eval(`(() => { const v = document.querySelector('#view'); return !!v && !/^\\s*Đang tải/.test(v.textContent) && !v.querySelector('.loading') })()`).catch(() => false); if (v) return; await sleep(150); } },
    async eval(expr) { const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'eval error'); return r.result.result.value; },
    async rect(sel) { return page.eval(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null; e.scrollIntoView({block:'center'}); const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height } })()`); },
    async mouse(type, x, y, extra = {}) { await send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, ...extra }); },
    async clickXY(x, y) { await page.mouse('mouseMoved', x, y, { buttons: 0 }); await page.mouse('mousePressed', x, y); await page.mouse('mouseReleased', x, y); },
    /** Real mouse click on the first element matching a CSS selector (or the first whose text matches, via {sel, text}). */
    async click(sel, text) {
      const s = text ? `Array.from(document.querySelectorAll(${JSON.stringify(sel)})).find((e) => e.textContent.trim().includes(${JSON.stringify(text)}) && e.offsetParent !== null)` : `document.querySelector(${JSON.stringify(sel)})`;
      const r = await page.eval(`(() => { const e = ${s}; if (!e) return null; e.scrollIntoView({block:'center'}); const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })()`);
      if (!r) throw new Error('click: not found ' + sel + (text ? ' / ' + text : ''));
      await page.clickXY(r.x, r.y); await sleep(120); return r;
    },
    async key(key, code, mods = 0) { await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key, code, modifiers: mods, windowsVirtualKeyCode: KEYS[key] || key.toUpperCase().charCodeAt(0) }); await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, modifiers: mods, windowsVirtualKeyCode: KEYS[key] || key.toUpperCase().charCodeAt(0) }); },
    async type(text) { for (const ch of text) { await send('Input.dispatchKeyEvent', { type: 'char', text: ch, key: ch }); } },
    async insert(text) { await send('Input.insertText', { text }); },
    async focus(sel) { await page.eval(`document.querySelector(${JSON.stringify(sel)}).focus()`); },
    async shot(file) { fs.mkdirSync(path.dirname(file), { recursive: true }); const r = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(file, Buffer.from(r.result.data, 'base64')); return file; },
    async text(sel) { return page.eval(`document.querySelector(${JSON.stringify(sel)})?.textContent ?? null`); },
    async count(sel) { return page.eval(`document.querySelectorAll(${JSON.stringify(sel)}).length`); },
    async waitFor(expr, ms = 8000) { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await page.eval(expr)) return true; } catch {} await sleep(150); } return false; },
    close() { try { ws.close(); } catch {} },
  };
  return page;
}
export const KEYS = { Enter: 13, Escape: 27, Tab: 9, Backspace: 8, Delete: 46, ArrowLeft: 37, ArrowUp: 38, ArrowRight: 39, ArrowDown: 40, Home: 36, End: 35 };
export const MOD = { alt: 1, ctrl: 2, meta: 4, shift: 8 };
