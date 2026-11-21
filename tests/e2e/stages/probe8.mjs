import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact, makePng, setFile, stepsOf } from './common.mjs';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
const pk = async () => (await api.get(`/api/projects/${PID}/picks`)).json;
await go(p, base, `#/project/${PID}/picks`);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'stg-'));
const png = makePng(path.join(tmp, 'mine.png'), 1600, 1200);
fs.writeFileSync(path.join(tmp, 'notes.txt'), 'this is not an image');
fs.writeFileSync(path.join(tmp, 'fake.jpg'), 'this is text pretending to be a jpg');
// beat 2
await p.click('.pk-beat, [data-beat="b0002"], li', 'b0002').catch(async()=>{ console.log('no beat row selector'); });
await sleep(500);
await clickExact(p, '+ Cả tranh chính'); await sleep(800);
let d = (await pk()).picks; console.log('b0002', JSON.stringify(d.beats.b0002));
await snap(p, 'p8-beat-main');
// tab upload
await clickExact(p, 'Tải lên'); await sleep(500);
await snap(p, 'p8-upload-tab');
console.log(await p.eval(`Array.from(document.querySelectorAll('form input, form select, form button')).map(e=>e.tagName+':'+(e.name||'')+':'+(e.type||'')+':'+(e.textContent||e.placeholder||'').trim().slice(0,30)).join(' | ')`));
for (const f of ['notes.txt','fake.jpg']) {
  await setFile(p, 'form input[type=file]', [path.join(tmp, f)]);
  await p.eval(`document.querySelector('form').requestSubmit()`); await sleep(2500);
  const toast = await p.eval(`Array.from(document.querySelectorAll('.toast, [class*=toast]')).map(e=>e.innerText).join(' || ')`);
  console.log(f, '->', JSON.stringify(toast), '| bad:', p.bad().slice(-2));
  await snap(p, 'p8-upload-'+f);
}
await setFile(p, 'form input[type=file]', [png]);
await p.eval(`document.querySelector('form').requestSubmit()`); await sleep(3000);
d = (await pk()).picks; console.log('b0002 after upload', JSON.stringify(d.beats.b0002), Object.keys(d.assets));
await snap(p, 'p8-upload-ok');
console.log(await leftovers(p), p.logs, p.dialogs);
br.close();
