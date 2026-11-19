// The second instance of the app for the OLD browser probes (shell/library/script, round 2, round 3 fixes): on the Windows server, through the same
// ssh tunnel and launcher as the stages and agent probes (tests/e2e/stages/remote.mjs, tests/e2e/agent/launch_agent.py wrapping tests/e2e/stages/launch.py:
// BTI_NO_REAL_MODELS=1, its own port, temp COPIES of the data, the two MOCK agents "Gemini 3.8 Flash" (runs the mock model) and "Opus 5.5 High").
// Those probes used to start a fresh local server per check (lib.mjs `startServer`) and write into its folders. This file gives them the same calls:
//   const srv = await startServer();        the instance (started once; a second call returns the same one)   srv.base
//   const s = await own();                  "a server of my own": the same instance with the data started over (`POST /api/_e2e/reset`)
//   s.writeFile('arnolfini_edit/media/durer.jpg', 'text')  s.exists('zz_broken')   s.stop()  s.restart()   (what the old checks did to a local folder)
//   await closeServer();                    stops the instance, the tunnel and the daemon (call it when the probe ends)
// BTI_SSH_HOST=winbox-cmd (away from the home network). Two workers at once: BTI_STAGES_PORT and BTI_STAGES_SUFFIX (see remote.mjs).
process.env.BTI_STAGES_LAUNCH ||= 'tests\\e2e\\agent\\launch_agent.py';              // before remote.mjs is loaded: it reads it once
const R = await import('../stages/remote.mjs');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// the ssh tunnel drops a connection now and then ("fetch failed"): a GET is asked again (up to 4 times); nothing else is repeated
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (url, opts = {}) => {
  const get = !opts.method || String(opts.method).toUpperCase() === 'GET';
  for (let i = 0; ; i++) {
    try { return await nativeFetch(url, opts); } catch (e) { if (!get || i >= 3) throw e; await sleep(1500); }
  }
};

let state = null;
let handle = null;
const call = async (method, p, body) => {
  const r = await fetch(state.base + p, { method, headers: body ? { 'content-type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch {}
  return { status: r.status, json: j, text: t };
};
let stopped = false;
const server = () => ({
  base: state.base,
  tmp: state.tmp,
  stop: async () => { stopped = true; return R.ctl('/stop-keep'); },       // the app stops, the data stays (the old checks stopped their own local server to see the page without one)
  restart: async () => { const r = JSON.parse(await R.ctl('/start')); if (!r.ok) throw new Error('the instance did not come back'); stopped = false; },
  ensureUp: async () => { if (stopped) await handle.restart(); },          // call after a check that stopped it
  writeFile: async (rel, text) => { const r = await call('PUT', '/api/_e2e/file', { path: rel, text }); if (r.status !== 200) throw new Error('writeFile ' + r.text.slice(0, 120)); },
  exists: async (rel) => (await call('POST', '/api/_e2e/exists', { path: rel })).json?.exists === true,
});

/** Start the instance (or return the one this process started). An instance left by another run is stopped first (the mock agents must be the ones of
 *  launch_agent.py), unless `--reuse-server` is on the command line (while a check is being worked on); `--keep-server` leaves it up at the end. */
export async function startServer() {
  if (handle) return handle;
  const reuse = process.argv.includes('--reuse-server') && R.readState();
  if (R.readState() && !reuse) await R.down();
  state = reuse ? R.readState() : await R.up({ doDeploy: true });
  handle = server();
  // what the settings box does for "new projects start on Gemini": without a machine default a script job runs the ROLE's model (the real `agy` one, refused here),
  // and the agent select shows "(theo cài đặt nâng cao)"; with it, every project resolves to the mock agent "Gemini 3.8 Flash" unless the page chooses another
  if (!reuse) { const r = await call('PUT', '/api/settings/agent', { agent: 'gemini' }); if (r.status !== 200) throw new Error('machine default agent: ' + r.text.slice(0, 120)); }
  return handle;
}

/** "A server of my own": the same instance, with the projects folder started over (the base projects as copied at the start). */
export async function own() {
  await startServer();
  await handle.ensureUp();
  const r = await call('POST', '/api/_e2e/reset');
  if (r.status !== 200) throw new Error('reset ' + r.text.slice(0, 120));
  return handle;
}

export async function closeServer() {
  if (!handle) return;
  handle = null;
  if (process.argv.includes('--keep-server')) return;
  try { await R.down(); } catch {}
}
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, async () => { await closeServer(); process.exit(130); });
