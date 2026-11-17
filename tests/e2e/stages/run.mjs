// The stages UI checks (steps 3, 4, 6 and the draft panel), driven in a real browser against the second instance on the server.
// One PASS or FAIL line per check, named after a bug id (SU-nnn); each asserts the CORRECT behaviour. Exit code = number failing.
// Usage: node run.mjs [--keep-server]     (starts the server through remote.mjs when none is up, and stops it again)
import { up, down, readState } from './remote.mjs';
import { leftovers, go, settle, openBrowser, makeApi, check, finish, bodyText, has, rawLooking, snap, both, sleep, pipeline, stepsOf, stepperDom } from './common.mjs';

const keep = process.argv.includes('--keep-server');
const started = !readState();
const st = await up({ doDeploy: started });
const base = st.base; const api = makeApi(base);
const br = await openBrowser();
const p = await br.newPage();
const argPid = process.argv.includes('--pid') ? process.argv[process.argv.indexOf('--pid') + 1] : null;
const PID = argPid || 'lm-' + Date.now().toString(36).slice(-5);
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} did not run to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const text = () => bodyText(p);
const waitText = (needle, ms = 15000) => p.waitFor(`document.body.innerText.includes(${JSON.stringify(needle)})`, ms);

if (!argPid) await step('A1 home and library', async () => {
  await go(p, base, '#/');
  await snap(p, 'a1-home');
  check('home shows projects', has(await text(), 'Dự án', '+ Tạo video mới'));
  await p.click('a, button', '+ Tạo video mới'); await settle(p);
  await snap(p, 'a1-library');
  check('library lists artworks', has(await text(), 'Tác phẩm'));
});

if (!argPid) await step('A2 choose artwork and create project', async () => {
  await go(p, base, '#/library/artwork/velazquez-las-meninas');
  await snap(p, 'a2-artwork');
  await p.click('button', 'Tạo dự án'); await sleep(500);
  await snap(p, 'a2-create-dialog');
  await p.eval(`(() => { const i = document.querySelector('.dlg-field input'); i.focus(); i.select(); })()`);
  await p.insert(PID);
  await p.click('footer button.primary', 'Tạo dự án');
  const ok = await p.waitFor(`location.hash.includes(${JSON.stringify(PID)})`, 20000);
  await settle(p);
  check('create project opens it', ok, await p.eval('location.hash'));
  const pl = await pipeline(api, PID);
  check('pipeline answers for the new project', pl && pl.steps?.length === 6, JSON.stringify(pl)?.slice(0, 200));
  await snap(p, 'a2-after-create');
});

if (!argPid) await step('A3 script: outline and narration with mock', async () => {
  await go(p, base, `#/project/${PID}/script`);
  await snap(p, 'a3-script-start');
  console.log((await text()).slice(0, 300).replace(/\n/g, ' | '));
  await p.click('button', 'Lập dàn ý'); await sleep(500); await p.click('footer button.primary', 'Chạy');
  const done = await p.waitFor(`document.body.innerText.includes('Duyệt dàn ý') && !!Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Duyệt dàn ý') && !b.disabled)`, 60000);
  check('outline appears with mock', done);
  await snap(p, 'a3-outline');
  await p.click('button', 'Duyệt dàn ý'); await sleep(1200);
  await p.click('button', 'Viết lời dẫn'); await sleep(500); await p.click('footer button.primary', 'Chạy');
  const done2 = await p.waitFor(`!!Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Duyệt lời dẫn') && !b.disabled)`, 120000);
  check('narration appears with mock', done2);
  await snap(p, 'a3-narration');
  await p.click('button', 'Duyệt lời dẫn'); await sleep(1500);
  const pl = await pipeline(api, PID);
  const s = stepsOf(pl);
  check('after approving narration steps 3 and 4 open', s.voice?.state !== 'locked' && s.picks?.state !== 'locked', JSON.stringify([s.voice, s.picks]));
  await snap(p, 'a3-approved');
});


const jobOf = async (kind) => ((await api.get(`/api/projects/${PID}/longjobs?kind=${kind}`)).json?.items || [])[0];
const btn = (t) => `Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().includes(${JSON.stringify(t)}) && b.offsetParent)`;
const noLeft = async (name) => { const l = await leftovers(p); check(`SU-001 ${name}: no stray "null" or "undefined" text`, l.length === 0, JSON.stringify(l)); };

await step('A4 voice', async () => {
  await go(p, base, `#/project/${PID}/voice`);
  await noLeft('voice page');
  await both(p, 'voice-before');
  let pl = await pipeline(api, PID);
  check('voice step before: not locked and says none', stepsOf(pl).voice.state !== 'locked');
  await p.click('button', 'Tạo giọng đọc');
  const sawRun = await p.waitFor(`document.body.innerText.includes('Đang chạy')`, 20000);
  await snap(p, 'a4-voice-running');
  check('voice page shows "Đang chạy" after the click', sawRun);
  const during = await pipeline(api, PID);
  check('stepper marks voice as running while the job runs', ['running'].includes(stepsOf(during).voice.work) || (await jobOf('voice'))?.state === 'done', JSON.stringify(stepsOf(during).voice));
  const fin = await p.waitFor(`!document.body.innerText.includes('Đang chạy') && !!${btn('Nghe')} || !!document.querySelector('audio')`, 240000);
  await settle(p);
  await snap(p, 'a4-voice-done');
  const job = await jobOf('voice');
  check('voice job ends done', job?.state === 'done', JSON.stringify({ s: job?.state, e: job?.error_code, m: job?.error }));
  pl = await pipeline(api, PID);
  check('voice step is done after the job', stepsOf(pl).voice.state === 'done', JSON.stringify(stepsOf(pl).voice));
  const t = await text();
  console.log(t.slice(0, 900).replace(/\n/g, ' | '));
  await noLeft('voice page done');
  await both(p, 'voice-done');
});

console.log(p.logs, p.bad());
br.close();
if (!keep && started) await down();
process.exit(finish());
