import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
const steps = async () => (await pipeline(api, PID)).steps.map(s=>`${s.id}:${s.state}/${s.work||''}`).join(' ');
await go(p, base, `#/project/${PID}/edit`); await sleep(2500);
await clickExact(p, 'Lưu'); await sleep(2500);
await clickExact(p, 'Duyệt'); for (let i=0;i<60;i++){ await sleep(2000); if ((await pipeline(api, PID)).steps.find(x=>x.id==='edit').state==='done') break; }
await snap(p, 'p17-approved');
console.log('after approve', await steps());
console.log(await p.eval(`Array.from(document.querySelectorAll('.step')).map(e=>e.innerText.replace(/\\n/g,' ')).join(' | ')`));
await go(p, base, `#/project/${PID}/export`);
await both(p, 'export-ready');
console.log((await bodyText(p)).split('\n').slice(24,60).join(' | '));
console.log(await leftovers(p), p.logs.slice(-5), p.bad());
br.close();
