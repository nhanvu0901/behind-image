import { openBrowser, readBase, makeApi, bodyText, snap, sleep, go, settle, pipeline, leftovers, clickExact } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); process.on('exit', () => br.close()); const p = await br.newPage();
const toasts = () => p.eval(`Array.from(document.querySelectorAll('.toast, [class*=toast]')).map(e=>e.innerText).join(' || ')`);
const st = async (k) => { const j = ((await api.get(`/api/projects/${PID}/longjobs?kind=${k}`)).json.items||[])[0]; return j && `${j.state}|${j.error_code||''}|${(j.parts||[]).map(x=>x.state).join(',')}`; };
// 1 voice: start by API, cancel by UI promptly
await go(p, base, `#/project/${PID}/voice`);
await api.post(`/api/projects/${PID}/voice/generate`, { scope: 'all' });
await p.waitFor(`!!Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Hủy')`, 15000);
await clickExact(p, 'Hủy'); await sleep(4000);
console.log('voice after cancel:', await st('voice'), '| toast', await toasts());
await snap(p, 'c2-voice-cancelled');
console.log((await bodyText(p)).split('\n').filter(x=>x.trim()).slice(12,30).join(' | ').slice(0,600));
const vs = (await api.get(`/api/projects/${PID}/voice`)).json; console.log('voice state', vs.state, vs.detail, JSON.stringify(vs.counts));
// reload mid-run after restart
await clickExact(p, vs.state==='done' ? 'Tạo lại nếu thiếu' : (vs.state==='stale'?'Đọc lại phần đã đổi':'Tạo giọng đọc')).catch(e=>console.log('no start button', e.message));
await sleep(1500); await p.eval('location.reload()'); await settle(p); await sleep(1500);
console.log('after reload mid-run:', (await bodyText(p)).includes('Đang chạy'), await st('voice'));
for (let i=0;i<60;i++){ if (!(await st('voice')||'').startsWith('running')) break; await sleep(2000); }
await sleep(3000); console.log('end', await st('voice'), (await bodyText(p)).includes('Đang chạy'));
// 2 export: start, cancel, start again
await go(p, base, `#/project/${PID}/export`);
const ex = (await api.get(`/api/projects/${PID}/export`)).json; console.log('export state', ex.state, ex.detail);
const label = ex.state==='done' ? 'Xuất lại video' : 'Xuất video';
await clickExact(p, label).catch(e=>console.log(e.message)); await sleep(1500);
await snap(p, 'c2-export-running');
console.log('export running page:', (await bodyText(p)).split('\n').filter(x=>x.trim()).slice(12,30).join(' | ').slice(0,500));
const dup = await api.post(`/api/projects/${PID}/export/start`, {}); console.log('2nd export start', dup.status, JSON.stringify(dup.json).slice(0,200));
const del = await api.del(`/api/projects/${PID}?confirm=${PID}`); console.log('delete during export', del.status, JSON.stringify(del.json).slice(0,200));
await clickExact(p, 'Hủy').catch(e=>console.log('cancel btn', e.message)); await sleep(5000);
console.log('export after cancel', await st('export'), '| page running?', (await bodyText(p)).includes('Đang chạy'));
await snap(p, 'c2-export-cancelled');
console.log((await bodyText(p)).split('\n').filter(x=>x.trim()).slice(12,34).join(' | ').slice(0,600));
await clickExact(p, 'Xuất video').catch(async()=>clickExact(p,'Xuất lại video')).catch(e=>console.log(e.message));
for (let i=0;i<60;i++){ await sleep(2000); const s = await st('export')||''; if (!s.startsWith('running')) break; }
console.log('export after restart', await st('export'), JSON.stringify((await pipeline(api, PID)).steps[5]));
console.log(await leftovers(p), p.logs.slice(-3));
