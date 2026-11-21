import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
await go(p, base, `#/project/${PID}/export`);
await both(p, 'export-ready');
console.log((await bodyText(p)).split('\n').slice(24,70).join(' | '));
await clickExact(p, 'Xuất video'); await sleep(1500); await snap(p, 'p18-running');
for (let i=0;i<60;i++){ await sleep(2000); const t = await bodyText(p); if (/Phiếu kiểm tra|Chép mô tả|lỗi/i.test(t)) break; }
await settle(p); await sleep(1500);
await both(p, 'export-done');
console.log((await bodyText(p)).split('\n').slice(24,120).join(' | '));
console.log(JSON.stringify((await pipeline(api, PID)).steps.map(s=>[s.id,s.state,s.work,s.detail])));
console.log(await leftovers(p), p.logs.slice(-5), p.bad());
br.close();
