import { openBrowser, readBase, makeApi, bodyText, snap, sleep, go, settle, leftovers, clickExact, rawLooking } from './common.mjs';
import { ctl } from './remote.mjs';
const base = readBase();
const br = await openBrowser(); const p = await br.newPage();
const toasts = () => p.eval(`Array.from(document.querySelectorAll('.toast, [class*=toast], .box.err, .banner')).map(e=>e.innerText).join(' || ')`);
const PID = process.argv[2];
try {
  await go(p, base, `#/project/${PID}/voice`);
  await go(p, base, `#/project/${PID}/picks`);
  console.log(await ctl('/stop-keep')); await sleep(4000);
  // picks page: click things
  await clickExact(p, 'Tìm').catch(()=>{}); await sleep(3000); console.log('picks search while down:', await toasts(), rawLooking(await toasts())); await snap(p, 'gone-picks-search');
  await clickExact(p, 'Kiểm tra').catch(e=>console.log(e.message)); await sleep(3000); console.log('picks check while down:', await toasts()); await snap(p, 'gone-picks-check');
  await go(p, base, `#/project/${PID}/voice`).catch(()=>{}); await sleep(3000); await snap(p, 'gone-voice');
  console.log('voice nav while down:', (await bodyText(p)).split('\n').filter(x=>x.trim()).slice(0,30).join(' | ').slice(0,500), '| toasts:', await toasts());
  await go(p, base, `#/project/${PID}/export`).catch(()=>{}); await sleep(3000); await snap(p, 'gone-export');
  console.log('export nav while down:', (await bodyText(p)).split('\n').filter(x=>x.trim()).slice(8,30).join(' | ').slice(0,500), '| toasts:', await toasts());
  console.log('LOGS', p.logs.slice(-4));
  console.log(await ctl('/start'));
  await sleep(2000); await p.eval('location.reload()'); await settle(p); await sleep(1500);
  console.log('after restart:', (await bodyText(p)).split('\n').filter(x=>x.trim()).slice(8,20).join(' | ').slice(0,300));
} finally { br.close(); process.exit(0); }
