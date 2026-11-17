// Shared set-up for the round 3 checks: one server, one Chrome, helpers. Reuses the round 1 harness.
import { startServer, launchChrome, sleep } from '../shell_library_script/lib.mjs';
import fs from 'node:fs';
import path from 'node:path';
export { sleep, fs, path };
export const SHOTS = new URL('../../../.scratch/round3_ui/shots/', import.meta.url).pathname;
export async function setup(size = [1700, 1000]) {
  const srv = await startServer(); const B = srv.base;
  const br = await launchChrome({ width: size[0], height: size[1] });
  const J = async (m, u, b, base = B) => { const r = await fetch(base + u, { method: m, headers: { 'content-type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }); const t = await r.text(); let j; try { j = JSON.parse(t); } catch { j = t; } return j; };
  const JS = async (m, u, b, base = B) => { const r = await fetch(base + u, { method: m, headers: { 'content-type': 'application/json' }, body: b ? JSON.stringify(b) : undefined }); const t = await r.text(); let j; try { j = JSON.parse(t); } catch { j = t; } return { status: r.status, body: j }; };
  const job = async (id, base = B) => { for (let i = 0; i < 100; i++) { const j = await J('GET', '/api/jobs/' + id, undefined, base); if (['done', 'error', 'cancelled'].includes(j.state)) return j; await sleep(300); } };
  const extra = [];
  const cleanup = () => { for (const s of extra) { try { s.stop(); } catch {} } try { br.close(); } catch {} try { srv.stop(); } catch {} };
  process.on('exit', cleanup); process.on('SIGINT', () => process.exit(130));
  const openEdit = async (p, pid, base = B, hash = 'edit') => { await p.goto('about:blank', 150); await p.goto(base + '/#/project/' + pid + '/' + hash, 1500); await p.waitFor('!!window.__bti', 20000); await sleep(1200); };
  const open = async (p, hash, ready = '#view', base = B) => { await p.goto('about:blank', 150); await p.goto(base + '/' + hash, 1200); await p.waitFor(`!!document.querySelector(${JSON.stringify(ready)})`, 15000); await sleep(400); };
  const own = async () => { const s = await startServer(); extra.push(s); return s; };
  const pages = async () => { while (br.pages.length > 1) { const p = br.pages.pop(); p.close(); } };
  return { srv, B, br, J, JS, job, extra, openEdit, open, own, cleanup };
}
