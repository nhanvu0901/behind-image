// Shared helpers of the stages UI run: the browser (real mouse and keyboard through lib.mjs), the API of the second instance,
// screenshots under .scratch/stages_ui/shots, and one PASS or FAIL line per check.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchChrome, sleep } from '../shell_library_script/lib.mjs';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, '../../..');
export const SHOTS = path.join(REPO, '.scratch/stages_ui/shots');
export { sleep };

export function readBase() { return JSON.parse(fs.readFileSync(path.join(REPO, '.scratch/stages_ui/state.json'), 'utf8')).base; }

export async function openBrowser({ width = 1700, height = 1000 } = {}) {
  process.env.CHROME = path.join(HERE, 'chrome_wrap.sh');
  const br = await launchChrome({ width, height });
  return br;
}

export function makeApi(base) {
  const call = async (method, p, body, raw) => {
    // the ssh tunnel to the server drops a connection now and then ("fetch failed"): GETs are asked again, up to 4 times
    let r;
    for (let i = 0; ; i++) {
      try { r = await fetch(base + p, { method, headers: body ? { 'content-type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined }); break; }
      catch (e) { if (method !== 'GET' || i >= 3) throw e; await sleep(1500); }
    }
    const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch {}
    return { status: r.status, json: j, text: t };
  };
  return { get: (p) => call('GET', p), post: (p, b) => call('POST', p, b || {}), put: (p, b) => call('PUT', p, b), del: (p) => call('DELETE', p), base };
}

export const results = [];
export function check(name, ok, detail = '') {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok || !detail ? '' : '  -- ' + String(detail).replace(/\s+/g, ' ').slice(0, 300)}`);
  return !!ok;
}
export function finish() { const n = results.filter((r) => !r.ok).length; console.log(`\n${results.length - n} pass, ${n} fail`); return n; }

/** Text of the whole app view, for assertions about wording. */
export const bodyText = (p) => p.eval(`document.body.innerText`);
const FOLD = (s) => s.normalize('NFC');
export const has = (text, ...needles) => needles.every((n) => FOLD(text).includes(FOLD(n)));
/** Untranslated or raw: English words, a status number, JSON braces. Returns what was found. */
export function rawLooking(text) {
  const out = [];
  if (/\b(HTTP|status)\s*\d{3}\b/i.test(text)) out.push('status number');
  if (/\b[45]\d\d\b (Not Found|Bad Request|Conflict|Internal|Unprocessable)/i.test(text)) out.push('http phrase');
  if (/\{\s*"[a-z_]+"\s*:/.test(text)) out.push('json');
  if (/\b(Traceback|undefined|\[object Object\]|NaN|Failed to fetch|TypeError|Unexpected token)\b/.test(text)) out.push('js leftovers');
  return out;
}
export async function snap(p, name, size) { const f = path.join(SHOTS, `${name}${size ? '-' + size : ''}.png`); await p.shot(f); return f; }
export async function both(p, name) { await p.resize(1700, 1000); await sleep(400); await snap(p, name, '1700'); await p.resize(1280, 720); await sleep(400); await snap(p, name, '1280'); await p.resize(1700, 1000); await sleep(200); }
export const pipeline = async (api, pid) => (await api.get(`/api/projects/${pid}/pipeline`)).json;
export const stepsOf = (pl) => Object.fromEntries((pl?.steps || []).map((s) => [s.id, s]));
/** Visible stepper: [{id, text, classes}] */
export const stepperDom = (p) => p.eval(`Array.from(document.querySelectorAll('.step, [data-step]')).map(e => ({id: e.dataset.step || '', text: e.innerText.replace(/\\s+/g,' ').trim(), cls: e.className}))`);

/** Wait for the view to have content and no "Đang tải" / spinner, then a short quiet moment (the server is slow, so no fixed sleeps). */
export async function settle(p, ms = 25000) {
  await sleep(250);
  const ok = await p.waitFor(`(() => { const v = document.querySelector('#view'); if (!v) return false; const t = v.innerText.trim(); return t.length > 15 && !/Đang tải|Đang mở/.test(t) && !v.querySelector('.loading, .spinner') })()`, ms);
  await sleep(250);
  return ok;
}
/** Go to a hash route in the same document (first call: a real navigation). */
export async function go(p, base, hash) {
  const cur = await p.eval(`location.href`).catch(() => '');
  if (!cur.startsWith(base)) await p.send('Page.navigate', { url: base + '/' + hash });
  else await p.eval(`(() => { if (location.hash === ${JSON.stringify(hash)}) location.reload(); else location.hash = ${JSON.stringify(hash)}; })()`);
  return settle(p);
}

/** Text nodes that are exactly a JS leftover (a null passed to Element.append prints "null"), plus raw strings. */
export const leftovers = (p) => p.eval(`(() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { const t = n.textContent.trim(); if (/^(null|undefined|NaN|\\[object Object\\]|nullnull|undefinedundefined)$/.test(t) || /(^|\\s)(undefined|NaN)(\\s|$)/.test(t) && t.length < 60) out.push(t + ' @ ' + (n.parentElement?.className || n.parentElement?.tagName)); } return out; })()`);

import zlib from 'node:zlib';
/** A valid PNG of w x h (diagonal gradient), written to `file`. */
export function makePng(file, w = 1600, h = 1200) {
  const row = (y) => { const b = Buffer.alloc(1 + w * 3); for (let x = 0; x < w; x++) { b[1 + x * 3] = (x * 255 / w) | 0; b[2 + x * 3] = (y * 255 / h) | 0; b[3 + x * 3] = 128; } return b; };
  const raw = Buffer.concat(Array.from({ length: h }, (_, y) => row(y)));
  const crcT = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (t, d) => { const len = Buffer.alloc(4); len.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]));
  return file;
}
/** Put a local file into <input type=file> that matches `sel` (real file chooser path through the DevTools protocol). */
export async function setFile(p, sel, files) {
  const { result } = await p.send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(sel)})` });
  const nid = await p.send('DOM.describeNode', { objectId: result.result.objectId });
  await p.send('DOM.setFileInputFiles', { files, backendNodeId: nid.result.node.backendNodeId });
}

/** Real mouse click on the visible element (default button) whose trimmed text is EXACTLY `t` (optionally inside `within`). */
export async function clickExact(p, t, sel = 'button', within = 'document') {
  const r = await p.eval(`(() => { const e = Array.from(${within}.querySelectorAll(${JSON.stringify(sel)})).find((e) => e.textContent.trim() === ${JSON.stringify(t)} && e.offsetParent !== null && !e.disabled); if (!e) return null; e.scrollIntoView({block:'center'}); const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })()`);
  if (!r) throw new Error('clickExact: not found ' + t);
  await p.clickXY(r.x, r.y); await sleep(150); return r;
}
