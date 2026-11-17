import { openBrowser, readBase, makeApi, bodyText, snap, sleep, go, settle, pipeline } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); process.on('exit', () => br.close()); const p = await br.newPage();
await go(p, base, `#/project/${PID}/voice`);
console.log('start', (await bodyText(p)).includes('Đang chạy'));
const r = await api.post(`/api/projects/${PID}/voice/generate`, { scope: 'all' }); console.log(r.status);
for (const t of [3,6,9]) { await sleep(3000); console.log(`t+${t}s page running?`, (await bodyText(p)).includes('Đang chạy'), 'stepper:', await p.eval(`Array.from(document.querySelectorAll('.step')).map(e=>e.innerText.replace(/\\n/g,' ')).slice(2,3)[0]`), 'api:', (await api.get(`/api/projects/${PID}/voice`)).json.state); }
await snap(p, 'c3-other-tab');
