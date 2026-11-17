import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline, leftovers, stepsOf } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
await go(p, base, `#/project/${PID}/voice`);
const state = async () => { const d = (await api.get(`/api/projects/${PID}/voice`)).json; return { s: d.state, det: d.detail, reasons: d.reasons, counts: d.counts }; };
console.log('start', JSON.stringify(await state()));
// play one sentence
await p.click('.vc-play'); await sleep(1500);
console.log('playing?', await p.eval(`document.querySelector('.vc-play').textContent`));
await sleep(500);
await p.click('.vc-play'); // stop
// reread
const before = (await api.get(`/api/projects/${PID}/voice`)).json.chunks[1];
await p.click('.vc-again', undefined);
await sleep(300);
const rows = await p.eval(`Array.from(document.querySelectorAll('.vc-again')).length`);
console.log('again btn count', rows);
await sleep(300);
await snap(p, 'p5-after-reread-click');
console.log((await bodyText(p)).slice(0, 300).split('\n').join('|'));
await p.waitFor(`!document.body.innerText.includes('Đang chạy')`, 60000);
await settle(p);
console.log('after reread', JSON.stringify(await state()), 'first chunk id', before.id, (await api.get(`/api/projects/${PID}/voice`)).json.chunks[0].id);
// tempo
await p.eval(`(() => { const i = document.querySelector('#vc-set input[type=number]'); i.focus(); i.select(); })()`);
await p.insert('1.15');
await p.click('#vc-set button', 'Lưu cài đặt'); await sleep(1500);
console.log('after tempo', JSON.stringify(await state()));
await snap(p, 'p5-after-tempo');
console.log((await bodyText(p)).split('\n').slice(28, 50).join(' | '));
console.log(JSON.stringify((await pipeline(api, PID)).steps.slice(2,3)));
console.log(await leftovers(p), p.logs, p.bad(), p.dialogs);
br.close();
