import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact, stepsOf } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
await go(p, base, `#/project/${PID}/edit`);
await clickExact(p, 'Dựng tự động (không dùng agent)');
for (let i=0;i<40;i++){ await sleep(1500); const t=await bodyText(p); if (/Mở đề xuất|Áp dụng|lỗi/i.test(t)) break; }
await snap(p, 'p12-draft-done');
console.log((await bodyText(p)).split('\n').slice(24,60).join(' | '));
console.log(JSON.stringify((await pipeline(api, PID)).steps.map(s=>[s.id,s.state,s.work,s.detail])));
console.log(await leftovers(p), p.logs.slice(-3), p.bad());
br.close();
