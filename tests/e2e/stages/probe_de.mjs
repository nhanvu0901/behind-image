import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact, rawLooking } from './common.mjs';
import { ctl } from './remote.mjs';
const base = readBase(); const api = makeApi(base);
const br = await openBrowser(); const p = await br.newPage();
const dump = async (tag, n = 700) => { const t = (await bodyText(p)).split('\n').filter(x=>x.trim()); const i = t.findIndex(x=>/^Xuất video$/.test(x)); console.log(`--- ${tag}:`, t.slice(i+2, i+2+30).join(' | ').slice(0, n), '| raw:', rawLooking(t.join('\n'))); };
try {
  // D: refusals via API on a project with no approved narration
  const E = 'arnolfini-from-books';
  for (const [n, p_, b] of [['voice', `/api/projects/${E}/voice/generate`, {scope:'all'}], ['draft auto', `/api/projects/${E}/draft/start`, {provider:'auto'}], ['draft agy', `/api/projects/${E}/draft/start`, {provider:'agy'}], ['export', `/api/projects/${E}/export/start`, {}], ['picks suggest', `/api/projects/${E}/picks/suggest`, {beats:['b0001'], confirm_paid:true}], ['picks approve', `/api/projects/${E}/picks/approve`, {}]]) { const r = await api.post(p_, b); console.log('API', n, r.status, JSON.stringify(r.json).slice(0,160)); }
  for (const st of ['voice','picks','edit','export']) { await go(p, base, `#/project/${E}/${st}`); await sleep(1000); await snap(p, `d-early-${st}`); await dump(`early ${E} ${st}`); }
  // E: the old project
  for (const st of ['artwork','script','voice','picks','edit','export']) { await go(p, base, `#/project/arnolfini/${st}`); await sleep(1500); await both(p, `e-old-${st}`); await dump(`old arnolfini ${st}`, 500); }
  await go(p, base, `#/project/arnolfini/edit`);
  await sleep(2000);
  console.log('old edit buttons:', await p.eval(`Array.from(document.querySelectorAll('button')).filter(b=>b.offsetParent).map(b=>b.textContent.trim()).join(' | ')`));
  await clickExact(p, 'Bản nháp'); await sleep(2500); await both(p, 'e-old-draft-dialog');
  console.log('draft dialog:', (await p.eval(`document.querySelector('.modal, dialog')?.innerText`))?.replace(/\n/g,' | ').slice(0,700));
  console.log(await leftovers(p), p.logs.slice(-3));
} finally { br.close(); process.exit(0); }
