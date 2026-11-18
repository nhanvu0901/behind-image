// Server half of the stages UI run: deploys the code (through tools/deploy/deploy_windows.sh, which takes the lock), starts
// tests/e2e/stages/launch.py on the Windows server over ssh, opens an ssh tunnel to a free local port, waits for /api/health,
// and tears everything down on exit.
//
//   node remote.mjs up [--no-ship]   start in the background (a daemon keeps ssh + tunnel); writes .scratch/stages_ui/state.json
//   node remote.mjs down               stop the instance (its temp folder is removed by launch.py), the tunnel and the daemon
//   node remote.mjs status
//   import { ensureServer } from './remote.mjs'  -> { base, ctl(path) } ; run.mjs calls it (and does `down` itself when it started the server)
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { freePort, sleep } from '../shell_library_script/lib.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../..');
export const SCRATCH = path.join(REPO, '.scratch/stages_ui');
const STATE = path.join(SCRATCH, 'state.json');
// The server's own folder is mirrored from the Mac tree by every deploy, and another agent deploys a different snapshot there.
// So this run does not use it: the working tree is packed with `deploy_windows.sh --pack-only` (no server action, no lock) and
// unpacked into a folder of its own in the server's temp directory (removed by `down`). The server's .venv, books, projects and
// library are used read-only (the data is COPIED into another temp folder by launch.py).
const W_REPO = 'C:\\Users\\ADMIN\\AppData\\Local\\Temp\\bti-stages-repo';
const REMOTE_PY = `D:\\code\\behind-the-image\\.venv\\Scripts\\python.exe ${W_REPO}\\tests\\e2e\\stages\\launch.py`;
const SSH = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'ServerAliveInterval=30'];
const PORT = 8562;
const HOST = process.env.BTI_SSH_HOST || 'winbox-lan';        // away from the home network: BTI_SSH_HOST=winbox-cmd (the Tailscale route)

export function deploy() {
  const r = spawnSync(path.join(REPO, 'tools/deploy/deploy_windows.sh'), [], { cwd: REPO, encoding: 'utf8' });
  if (r.status !== 0) throw new Error('deploy failed: ' + (r.stdout + r.stderr).slice(-600));
}

export function ship() {
  const O = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20'];
  const r = spawnSync(path.join(REPO, 'tools/deploy/deploy_windows.sh'), ['--pack-only'], { cwd: REPO, encoding: 'utf8' });
  const m = /id (\S+?)\)/.exec(r.stdout || '');
  if (r.status !== 0 || !m) throw new Error('pack failed: ' + ((r.stdout || '') + (r.stderr || '')).slice(-400));
  const tgz = path.join(REPO, '.scratch/deploy/out', `code-${m[1]}.tgz`);
  const sh = (c) => spawnSync('ssh', [...O, HOST, c], { encoding: 'utf8' });
  sh(`rmdir /s /q ${W_REPO}`);
  const cp = spawnSync('scp', ['-q', ...O, tgz, `${HOST}:C:/Users/ADMIN/AppData/Local/Temp/bti-stages-repo.tgz`]);
  if (cp.status !== 0) throw new Error('scp failed');
  const x = sh(`mkdir ${W_REPO} && tar -xzf C:\\Users\\ADMIN\\AppData\\Local\\Temp\\bti-stages-repo.tgz -C ${W_REPO}`);
  if (x.status !== 0) throw new Error('unpack failed: ' + x.stdout + x.stderr);
  fs.rmSync(tgz, { force: true });
}
export function unship() {
  spawnSync('ssh', ['-o', 'BatchMode=yes', HOST, `rmdir /s /q ${W_REPO} & del /q C:\\Users\\ADMIN\\AppData\\Local\\Temp\\bti-stages-repo.tgz`]);
}

function startRemote(tmp) {
  const cmd = REMOTE_PY + ` --port ${PORT}` + (tmp ? ` --tmp "${tmp}"` : '');
  const proc = spawn('ssh', [...SSH, HOST, cmd], { stdio: ['pipe', 'pipe', 'pipe'] });
  const h = { proc, tmp: tmp || null, pid: null, ready: false, exited: false, out: '' };
  proc.stdout.setEncoding('utf8');
  proc.stdout.on('data', (d) => {
    h.out += d;
    for (const l of d.split(/\r?\n/)) {
      if (l.startsWith('TMP=')) h.tmp = l.slice(4).trim();
      if (l.startsWith('PID=')) h.pid = l.slice(4).trim();
      if (l.startsWith('READY')) h.ready = true;
    }
  });
  proc.stderr.on('data', (d) => { h.out += d; });
  proc.on('exit', () => { h.exited = true; });
  return h;
}

async function waitHealth(base, ms = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { if ((await fetch(base + '/api/health')).ok) return true; } catch {}
    await sleep(500);
  }
  return false;
}

/** The daemon: owns the ssh child, the tunnel, and a tiny control server. */
async function daemon() {
  fs.mkdirSync(SCRATCH, { recursive: true });
  const localPort = await freePort();
  let remote = startRemote(null);
  const tunnel = spawn('ssh', [...SSH, '-N', '-o', 'ExitOnForwardFailure=yes', '-L', `${localPort}:127.0.0.1:${PORT}`, HOST], { stdio: 'ignore' });
  const base = `http://127.0.0.1:${localPort}`;
  const write = () => fs.writeFileSync(STATE, JSON.stringify({ base, localPort, ctl: ctlPort, daemon: process.pid, tunnel: tunnel.pid, remotePid: remote.pid, tmp: remote.tmp, up: true }));
  let ctlPort = 0;
  let closing = false;
  const stopRemote = (keep) => new Promise((res) => {
    if (remote.exited) return res();
    remote.proc.on('exit', () => res());
    try { remote.proc.stdin.write(keep ? 'stop-keep\n' : ''); if (!keep) remote.proc.stdin.end(); } catch {}
    setTimeout(() => { if (!remote.exited) { try { remote.proc.kill(); } catch {} } }, 20000);
  });
  const down = async () => {
    if (closing) return; closing = true;
    await stopRemote(false);
    try { tunnel.kill(); } catch {}
    unship();
    try { fs.unlinkSync(STATE); } catch {}
    process.exit(0);
  };
  const srv = http.createServer(async (req, res) => {
    const u = req.url;
    if (u === '/stop-keep') { await stopRemote(true); write(); res.end(JSON.stringify({ tmp: remote.tmp })); }
    else if (u === '/start') { const keepTmp = remote.tmp; remote = startRemote(keepTmp); remote.tmp = keepTmp; const ok = await waitHealth(base); write(); res.end(JSON.stringify({ ok })); }
    else if (u === '/down') { res.end('bye'); down(); }
    else if (u === '/log') res.end(remote.out);
    else res.end('?');
  });
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  ctlPort = srv.address().port;
  process.on('SIGTERM', down); process.on('SIGINT', down);
  const ok = await waitHealth(base);
  write();
  if (!ok) { console.error('server did not come up\n' + remote.out); }
  remote.proc.on('exit', () => { if (!closing && !remote.keepFlag) { /* leave the daemon up so that a restart can happen */ } });
}

export function readState() { try { return JSON.parse(fs.readFileSync(STATE, 'utf8')); } catch { return null; } }

export async function up({ doDeploy = true } = {}) {
  const s = readState();
  if (s) { try { if ((await fetch(s.base + '/api/health')).ok) return s; } catch {} }
  if (doDeploy) ship();
  fs.mkdirSync(SCRATCH, { recursive: true });
  try { fs.unlinkSync(STATE); } catch {}
  const out = fs.openSync(path.join(SCRATCH, 'daemon.log'), 'a');
  const d = spawn(process.execPath, [fileURLToPath(import.meta.url), 'daemon'], { detached: true, stdio: ['ignore', out, out] });
  d.unref();
  for (let i = 0; i < 240; i++) {
    const st = readState();
    if (st) { try { if ((await fetch(st.base + '/api/health')).ok) return st; } catch {} }
    await sleep(500);
  }
  throw new Error('server did not come up; see ' + path.join(SCRATCH, 'daemon.log'));
}

export async function ctl(p) {
  const s = readState();
  if (!s) throw new Error('no state');
  return (await fetch(`http://127.0.0.1:${s.ctl}${p}`)).text();
}

export async function down() {
  const s = readState();
  if (!s) return;
  try { await ctl('/down'); } catch {}
  for (let i = 0; i < 60 && readState(); i++) await sleep(500);
}

export async function ensureServer(opts) { const s = await up(opts); return { base: s.base, ctl, state: s }; }

const cmd = process.argv[2];
if (import.meta.url === 'file://' + process.argv[1] || process.argv[1] === fileURLToPath(import.meta.url)) {
  if (cmd === 'daemon') await daemon();
  else if (cmd === 'up') { const s = await up({ doDeploy: !process.argv.includes('--no-ship') }); console.log(JSON.stringify(s)); process.exit(0); }
  else if (cmd === 'down') { await down(); console.log('down'); process.exit(0); }
  else if (cmd === 'status') { console.log(JSON.stringify(readState())); process.exit(0); }
}

/** Restart the instance on the SAME temp data, with the newest code and test files (`node remote.mjs restart`). */
export async function restart() {
  const r = await ctl('/stop-keep'); await sleep(1500);
  ship();
  const s = await ctl('/start');
  return r + s;
}
if (process.argv[2] === 'restart' && process.argv[1] === fileURLToPath(import.meta.url)) { console.log(await restart()); process.exit(0); }
