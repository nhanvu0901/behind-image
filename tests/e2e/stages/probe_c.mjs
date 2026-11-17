import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage(); const p2 = await br.newPage();
const toasts = (pg) => pg.eval(`Array.from(document.querySelectorAll('.toast, [class*=toast]')).map(e=>e.innerText).join(' || ')`);
const vstate = async () => { const d = (await api.get(`/api/projects/${PID}/voice`)).json; return `${d.state}|${d.detail}`; };
await go(p, base, `#/project/${PID}/voice`);
await go(p2, base, `#/project/${PID}/voice`);
// tab A: reread everything (confirm dialog)
await clickExact(p, 'Đọc lại toàn bộ'); await sleep(700);
await p.eval(`(()=>{const b=Array.from(document.querySelectorAll('footer button')).find(b=>/Đọc lại tất cả/.test(b.textContent)); b.click()})()`);
await sleep(2500);
console.log('A after start', await vstate(), '| toast:', await toasts(p));
await snap(p, 'c-A-running');
// tab B: reload page mid-run
await p2.eval('location.reload()'); await settle(p2); await sleep(1500);
await snap(p2, 'c-B-mid');
console.log('B text', (await bodyText(p2)).split('\n').filter(x=>x.trim()).slice(14,32).join(' | ').slice(0,500));
// B: try to start second job
const btns = await p2.eval(`Array.from(document.querySelectorAll('button')).filter(b=>b.offsetParent).map(b=>b.textContent.trim()+(b.disabled?'(disabled)':'')).slice(0,14).join(' | ')`);
console.log('B buttons', btns);
const second = await api.post(`/api/projects/${PID}/voice/generate`, {scope:'all'}); console.log('second generate', second.status, JSON.stringify(second.json));
// delete while running
const del = await api.del(`/api/projects/${PID}?confirm=${PID}`); console.log('delete while running', del.status, JSON.stringify(del.json));
// cancel from A
await clickExact(p, 'Hủy'); await sleep(3000);
console.log('A after cancel', await vstate(), '| toast:', await toasts(p));
for (let i=0;i<20;i++){ const s = await vstate(); if (!s.startsWith('running')) break; await sleep(1500); }
await sleep(3000); await snap(p, 'c-A-cancelled'); await snap(p2, 'c-B-after');
console.log('A text', (await bodyText(p)).split('\n').filter(x=>x.trim()).slice(14,34).join(' | ').slice(0,600));
console.log('B text', (await bodyText(p2)).split('\n').filter(x=>x.trim()).slice(14,34).join(' | ').slice(0,600));
console.log('final', await vstate(), JSON.stringify((await pipeline(api, PID)).steps.slice(2,3)));
console.log(await leftovers(p), p.logs.slice(-3), p.bad());
br.close();
