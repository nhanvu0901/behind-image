import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, clickExact, makePng, setFile, stepsOf } from './common.mjs';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
const pk = async () => (await api.get(`/api/projects/${PID}/picks`)).json.picks;
await go(p, base, `#/project/${PID}/picks`);
await settle(p);
await snap(p, 'p7-main-chosen');
let d = await pk(); console.log('main', d.main_asset);

console.log((await bodyText(p)).split('\n').slice(24,40).join(' | '));
// regions
await clickExact(p, 'Vùng trên tranh'); await sleep(2000); await snap(p, 'p7-regions');
const box = await p.eval(`(() => { const s = document.querySelector('.pk-reg-svg'); const r = s.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height} })()`);
console.log('svg box', JSON.stringify(box));
const cx = box.x + box.w*0.5, cy = box.y + box.h*0.4;
await p.mouse('mouseMoved', cx, cy, {buttons:0}); await p.mouse('mousePressed', cx, cy);
for (let i=1;i<=6;i++) await p.mouse('mouseMoved', cx+i*10, cy+i*6, {buttons:1});
await p.mouse('mouseReleased', cx+60, cy+36);
await sleep(300); await snap(p, 'p7-regions-drawn');
await p.focus('.pk-reg-side input[type=text]'); await p.insert('D1');
await clickExact(p, 'Thêm vùng này'); await sleep(300);
await snap(p, 'p7-regions-added');
await clickExact(p, 'Lưu các vùng'); await sleep(2000);
d = await pk(); console.log('regions', JSON.stringify(Object.values(d.assets)[0].regions));
console.log(await leftovers(p), p.logs, p.bad().filter(x=>!/thumb|\/x\/|CRDImages/.test(x)), p.dialogs);
br.close();
