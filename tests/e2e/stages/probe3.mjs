import { openBrowser, readBase, makeApi, bodyText, snap, both, sleep, go, settle, pipeline } from './common.mjs';
const base = readBase(); const api = makeApi(base);
const PID = process.argv[2];
const br = await openBrowser(); const p = await br.newPage();
for (const st of ['voice','picks','export']) {
  await go(p, base, `#/project/${PID}/${st}`);
  console.log('=====', st); console.log((await bodyText(p)).split('\n').slice(40).join(' | ').slice(0, 1500));
  await snap(p, 'probe-'+st);
}
console.log(JSON.stringify((await pipeline(api, PID)).steps.map(s=>[s.id,s.state,s.work,s.reason,s.detail])));
console.log(p.logs, p.bad());
br.close();
