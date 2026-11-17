import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
const steps = async () => (await pipeline(api, PID)).steps.map(s=>`${s.id}:${s.state}/${s.work||''}:${(s.reason||s.detail||'').slice(0,80)}`);
const page = async (st, tag) => { await go(p, base, `#/project/${PID}/${st}`); await sleep(1500); await snap(p, `b-${tag}-${st}`); const t = (await bodyText(p)).split('\n').filter(x=>x.trim()); const i = t.findIndex(x=>/Xuất video/.test(x) && false); console.log(`--- ${tag} ${st}:`, t.slice(14, 34).join(' | ').slice(0, 700)); };
console.log('START', (await steps()).join('\n  '));
// B1 change narration
const n = (await api.get(`/api/projects/${PID}/narration`)).json;
const doc = n.narration; doc.chapters[0].beats[0].text = doc.chapters[0].beats[0].text + ' An extra sentence was added by the owner.';
const r = await api.put(`/api/projects/${PID}/narration`, { narration: doc, base_rev: n.rev });
console.log('PUT narration', r.status, JSON.stringify(r.json).slice(0,200));
console.log('AFTER NARRATION EDIT', (await steps()).join('\n  '));
for (const st of ['script','voice','picks','edit','export']) await page(st, 'narr');
console.log(await leftovers(p), p.logs.slice(-3), p.bad());
br.close();
