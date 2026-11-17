// The stages UI checks (steps 3, 4, 6 and the draft panel), driven in a real browser against the second instance on the server.
// One PASS or FAIL line per check, named after a bug id (SU-nnn); each asserts the CORRECT behaviour. Exit code = number failing.
// Usage: node run.mjs [--keep-server]     (starts the server through remote.mjs when none is up, and stops it again)
import { up, down, readState } from './remote.mjs';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
import { clickExact, makePng, setFile, leftovers, go, settle, openBrowser, makeApi, check, finish, bodyText, has, rawLooking, snap, both, sleep, pipeline, stepsOf, stepperDom } from './common.mjs';

const onlyExtras = process.argv.includes('--only-extras');
const keep = process.argv.includes('--keep-server');
const started = !readState();
const st = await up({ doDeploy: started });
const base = st.base; const api = makeApi(base);
const br = await openBrowser();
const p = await br.newPage();
// one Chrome at a time, and it never outlives this process (closed by its own process id, never by a name pattern)
const closeAll = () => { try { br.close(); } catch {} };
process.on('exit', closeAll);
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { closeAll(); process.exit(130); });
process.on('uncaughtException', (e) => { console.error(e); closeAll(); process.exit(99); });
const argPid = process.argv.includes('--pid') ? process.argv[process.argv.indexOf('--pid') + 1] : null;
const PID = argPid || 'lm-' + Date.now().toString(36).slice(-5);
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} did not run to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const text = () => bodyText(p);
const waitText = (needle, ms = 15000) => p.waitFor(`document.body.innerText.includes(${JSON.stringify(needle)})`, ms);

if (!argPid) await step('A1 home and library', async () => {
  await go(p, base, '#/');
  await snap(p, 'a1-home');
  check('home shows projects', has(await text(), 'Dự án', '+ Tạo video mới'));
  await p.click('a, button', '+ Tạo video mới'); await settle(p);
  await snap(p, 'a1-library');
  check('library lists artworks', has(await text(), 'Tác phẩm'));
});

if (!argPid) await step('A2 choose artwork and create project', async () => {
  await go(p, base, '#/library/artwork/velazquez-las-meninas');
  await snap(p, 'a2-artwork');
  await p.click('button', 'Tạo dự án'); await sleep(500);
  await snap(p, 'a2-create-dialog');
  await p.eval(`(() => { const i = document.querySelector('.dlg-field input'); i.focus(); i.select(); })()`);
  await p.insert(PID);
  await p.click('footer button.primary', 'Tạo dự án');
  const ok = await p.waitFor(`location.hash.includes(${JSON.stringify(PID)})`, 20000);
  await settle(p);
  check('create project opens it', ok, await p.eval('location.hash'));
  const pl = await pipeline(api, PID);
  check('pipeline answers for the new project', pl && pl.steps?.length === 6, JSON.stringify(pl)?.slice(0, 200));
  await snap(p, 'a2-after-create');
});

if (!argPid) await step('A3 script: outline and narration with mock', async () => {
  await go(p, base, `#/project/${PID}/script`);
  await snap(p, 'a3-script-start');
  console.log((await text()).slice(0, 300).replace(/\n/g, ' | '));
  await p.click('button', 'Lập dàn ý'); await sleep(500); await p.click('footer button.primary', 'Chạy');
  const done = await p.waitFor(`document.body.innerText.includes('Duyệt dàn ý') && !!Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Duyệt dàn ý') && !b.disabled)`, 60000);
  check('outline appears with mock', done);
  await snap(p, 'a3-outline');
  await p.click('button', 'Duyệt dàn ý'); await sleep(1200);
  await p.click('button', 'Viết lời dẫn'); await sleep(500); await p.click('footer button.primary', 'Chạy');
  const done2 = await p.waitFor(`!!Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Duyệt lời dẫn') && !b.disabled)`, 120000);
  check('narration appears with mock', done2);
  await snap(p, 'a3-narration');
  await p.click('button', 'Duyệt lời dẫn'); await sleep(1500);
  const pl = await pipeline(api, PID);
  const s = stepsOf(pl);
  check('after approving narration steps 3 and 4 open', s.voice?.state !== 'locked' && s.picks?.state !== 'locked', JSON.stringify([s.voice, s.picks]));
  await snap(p, 'a3-approved');
});


const jobOf = async (kind) => ((await api.get(`/api/projects/${PID}/longjobs?kind=${kind}`)).json?.items || [])[0];
const btn = (t) => `Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().includes(${JSON.stringify(t)}) && b.offsetParent)`;
const noLeft = async (name) => { const l = await leftovers(p); check(`SU-001 ${name}: no stray "null" or "undefined" text`, l.length === 0, JSON.stringify(l)); };


const stepperTexts = () => p.eval(`Array.from(document.querySelectorAll('.step')).map(e => e.innerText.replace(/\\n/g, ' ').trim())`);
/** What the stepper shows must agree with GET /pipeline: a done step shows "XONG", a locked one "KHÓA", a running one "ĐANG CHẠY". */
async function stepperAgrees(name) {
  const pl = await pipeline(api, PID); const dom = await stepperTexts();
  const want = { done: 'XONG', locked: 'KHÓA', current: 'HIỆN TẠI', available: 'MỞ ĐƯỢC', waiting: 'CHỜ BƯỚC TRƯỚC' };
  const bad = [];
  pl.steps.forEach((s, i) => {
    let w = want[s.state] || '';
    if (s.work === 'running') w = 'ĐANG CHẠY'; else if (s.work === 'stale' && s.state !== 'locked' && s.state !== 'waiting') w = 'CẦN LÀM LẠI';
    if (s.state === 'locked') w = 'KHÓA';
    if (w && !String(dom[i]).toUpperCase().includes(w)) bad.push(`${s.id}: api ${s.state}/${s.work} but page "${dom[i]}"`);
  });
  check(`SU-005 ${name}: stepper agrees with /pipeline`, bad.length === 0, bad.join(' ; '));
}

if (!onlyExtras) await step('A4 voice', async () => {
  await go(p, base, `#/project/${PID}/voice`);
  await noLeft('voice page');
  await both(p, 'voice-before');
  await stepperAgrees('voice before');
  const vs0 = (await api.get(`/api/projects/${PID}/voice`)).json;
  if (vs0.state === 'done') console.log('  (voice already done: skipping the first click)'); else await p.click('button.primary', vs0.state === 'stale' ? 'Đọc lại phần đã đổi' : vs0.counts.cached ? 'Tạo lại nếu thiếu' : 'Tạo giọng đọc');
  const sawRun = await p.waitFor(`document.body.innerText.includes('Đang chạy')`, 20000);
  await snap(p, 'a4-voice-running');
  if (vs0.state !== 'done') check('voice page shows "Đang chạy" after the click', sawRun);
  const fin = await p.waitFor(`!document.body.innerText.includes('Đang chạy') && /Xong|Lỗi|Đã hủy/.test(document.querySelector('.vc-head')?.innerText || '')`, 240000);
  await settle(p); await sleep(1500);
  const job = await jobOf('voice');
  check('SU-002 voice job ends done (no PermissionError)', job?.state === 'done', JSON.stringify({ s: job?.state, e: job?.error_code, m: (job?.error || '').slice(0, 160) }));
  await stepperAgrees('voice done');
  await noLeft('voice page done');
  await both(p, 'voice-done');
  // listen controls: one sentence plays, the whole mix is served with ranges
  await p.click('.vc-play'); await sleep(1500);
  const playing = await p.eval(`document.querySelector('.vc-play').textContent`);
  check('one sentence starts playing (button turns into stop)', playing === '■', playing);
  await p.click('.vc-play');
  const rg = await fetch(base + `/api/projects/${PID}/voice/mix`, { headers: { Range: 'bytes=0-99' } });
  check('the mix answers a range request with 206', rg.status === 206, rg.status);
  // one sentence re-read
  const before = (await api.get(`/api/projects/${PID}/voice`)).json.chunks[3].id;
  await p.eval(`document.querySelectorAll('.vc-again')[3].scrollIntoView({block:'center'})`);
  const rr = await p.eval(`(() => { const r = document.querySelectorAll('.vc-again')[3].getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2} })()`);
  await p.clickXY(rr.x, rr.y);
  await sleep(1500);
  for (let i = 0; i < 90; i++) { if (!['running'].includes((await api.get(`/api/projects/${PID}/voice`)).json.state)) break; await sleep(1500); }
  await sleep(2500); await settle(p);
  const vd = (await api.get(`/api/projects/${PID}/voice`)).json;
  check('SU-004 after re-reading one sentence the voice is done, not "narration changed"', vd.state === 'done', `${vd.state} ${vd.detail} ${JSON.stringify(vd.reasons)}`);
  // pronunciation table: one row, saved
  await clickExact(p, 'Thêm dòng');
  const inputs = await p.eval(`Array.from(document.querySelectorAll('.vc-rows input')).length`);
  await p.focus('.vc-rows input'); await p.insert('Velázquez');
  await p.eval(`document.querySelectorAll('.vc-rows input')[1].focus()`); await p.insert('Ve-las-kes');
  await clickExact(p, 'Lưu bảng phát âm'); await sleep(1500);
  const v2 = (await api.get(`/api/projects/${PID}/voice`)).json;
  check('pronunciation table saved', JSON.stringify(v2.pronounce).includes('Ve-las-kes'), JSON.stringify(v2.pronounce));
  check('only sentences with that word become stale', v2.counts.changed > 0 && v2.counts.changed < v2.counts.total, JSON.stringify(v2.counts));
  check('SU-004 a pronunciation change is not reported as "Lời dẫn đã đổi" (the narration did not change)', !/Lời dẫn đã đổi/.test(v2.detail || ''), v2.detail);
  console.log('  pronunciation: state', v2.state, v2.detail, JSON.stringify(v2.counts));
  await snap(p, 'a4-pronounce');
  if (v2.counts.changed) { await clickExact(p, v2.state === 'stale' ? 'Đọc lại phần đã đổi' : 'Tạo lại nếu thiếu'); await sleep(1500); for (let i = 0; i < 90; i++) { if ((await api.get(`/api/projects/${PID}/voice`)).json.state !== 'running') break; await sleep(1500); } await sleep(2500); }
  // tempo
  await p.eval(`(() => { const i = document.querySelector('#vc-set input[type=number]'); i.focus(); i.select(); })()`);
  await p.insert('1.1');
  await clickExact(p, 'Lưu cài đặt'); await sleep(1500);
  const v3 = (await api.get(`/api/projects/${PID}/voice`)).json;
  check('tempo saved', v3.settings.tempo === 1.1, JSON.stringify(v3.settings));
  console.log('  tempo: state', v3.state, v3.detail);
  if (v3.state !== 'done') { await clickExact(p, 'Đọc lại phần đã đổi').catch(() => clickExact(p, 'Tạo lại nếu thiếu')); await sleep(1500); for (let i = 0; i < 120; i++) { if ((await api.get(`/api/projects/${PID}/voice`)).json.state !== 'running') break; await sleep(1500); } await sleep(2500); }
  check('voice is done again after the remix', (await api.get(`/api/projects/${PID}/voice`)).json.state === 'done', JSON.stringify((await api.get(`/api/projects/${PID}/voice`)).json.detail));
});

if (!onlyExtras) await step('A5 picks', async () => {
  await go(p, base, `#/project/${PID}/picks`);
  await noLeft('picks page');
  await both(p, 'picks-before');
  if (!(await api.get(`/api/projects/${PID}/picks`)).json.picks.main_asset) {
  await clickExact(p, 'Tìm'); await p.waitFor(`document.body.innerText.includes('Làm tranh chính')`, 20000); await settle(p);
  const rr = await p.eval(`(() => { const b = Array.from(document.querySelectorAll('button')).filter(b => b.textContent.trim() === 'Làm tranh chính')[1]; b.scrollIntoView({block:'center'}); const r = b.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2} })()`);
  await p.clickXY(rr.x, rr.y);
  await p.waitFor(`!document.body.innerText.includes('Chưa chọn tranh chính')`, 30000); await settle(p); await sleep(1500);
  }
  let d = (await api.get(`/api/projects/${PID}/picks`)).json.picks;
  check('main painting chosen from fixture search', !!d.main_asset, JSON.stringify(d.main_asset));
  // region
  await clickExact(p, 'Vùng trên tranh'); await sleep(2000);
  const box = await p.eval(`(() => { const r = document.querySelector('.pk-reg-svg').getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height} })()`);
  const cx = box.x + box.w * 0.5, cy = box.y + box.h * 0.4;
  await p.mouse('mouseMoved', cx, cy, { buttons: 0 }); await p.mouse('mousePressed', cx, cy);
  for (let i = 1; i <= 6; i++) await p.mouse('mouseMoved', cx + i * 10, cy + i * 6, { buttons: 1 });
  await p.mouse('mouseReleased', cx + 60, cy + 36);
  await p.focus('.pk-reg-side input[type=text]'); await p.insert('D1');
  await clickExact(p, 'Thêm vùng này'); await sleep(300);
  await clickExact(p, 'Lưu các vùng'); await sleep(2000);
  d = (await api.get(`/api/projects/${PID}/picks`)).json.picks;
  check('region D1 saved', !!Object.values(d.assets)[0]?.regions?.D1, JSON.stringify(Object.values(d.assets)[0]?.regions));
  // beats: whole painting on b0002, region on b0003, upload on b0004
  for (const [b, label] of [['b0002', '+ Cả tranh chính'], ['b0003', '+ The Infanta']]) {
    await p.click('button.pk-beat', b); await sleep(500);
    await clickExact(p, label); await sleep(800);
  }
  await p.click('button.pk-beat', 'b0004'); await sleep(500);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'stg-'));
  await clickExact(p, 'Tải lên'); await sleep(500);
  fs.writeFileSync(path.join(tmp, 'notes.txt'), 'this is not an image');
  await setFile(p, 'form input[type=file]', [path.join(tmp, 'notes.txt')]);
  await p.eval(`document.querySelector('form').requestSubmit()`); await sleep(2500);
  const t1 = await p.eval(`Array.from(document.querySelectorAll('.toast, [class*=toast]')).map(e => e.innerText).join(' || ')`);
  check('SU-006 a non-image upload is refused in Vietnamese', /chưa hỗ trợ|không phải ảnh/i.test(t1) && !rawLooking(t1).length, t1);
  await setFile(p, 'form input[type=file]', [makePng(path.join(tmp, 'mine.png'))]);
  await p.eval(`document.querySelector('form').requestSubmit()`); await sleep(3000);
  d = (await api.get(`/api/projects/${PID}/picks`)).json.picks;
  check('upload of a real image lands in the beat', (d.beats.b0004?.items || []).some((i) => i.asset === 'mine'), JSON.stringify(d.beats.b0004));
  for (const tab of ['Sách', 'Gợi ý', 'Tìm kiếm', 'Tranh chính']) { await clickExact(p, tab); await sleep(1200); await noLeft('picks tab ' + tab); }
  await clickExact(p, 'Gợi ý'); await sleep(500); await snap(p, 'a5-tab-suggest');
  await clickExact(p, 'Duyệt chọn hình'); await sleep(900);
  await p.eval(`(()=>{const b=Array.from(document.querySelectorAll('footer button')).find(b=>/^Duyệt$/.test(b.textContent.trim())); b && b.click()})()`);
  await sleep(2500);
  const pl = await pipeline(api, PID);
  check('picks step done after approving', stepsOf(pl).picks.state === 'done', JSON.stringify(stepsOf(pl).picks));
  await stepperAgrees('picks done');
  await both(p, 'picks-done');
});

if (!onlyExtras) await step('A6 draft', async () => {
  await go(p, base, `#/project/${PID}/edit`);
  await both(p, 'draft-panel');
  await noLeft('draft panel');
  for (const [w, h] of [[1700, 1000], [1280, 720]]) {
    await p.resize(w, h); await sleep(400);
    const dp = await p.eval(`(() => { const hint = document.querySelector('.draft-panel .hint'); const next = hint?.nextElementSibling; if (!next) return null; const a = hint.getBoundingClientRect(), b = next.getBoundingClientRect(); return { fs: parseFloat(getComputedStyle(hint).fontSize), gap: Math.round(b.top - a.bottom), right: Math.round(a.right), vw: innerWidth }; })()`);
    check(`SU-011 the draft panel introduction has normal text size and room before the next row (${w}x${h})`, dp && dp.fs >= 13.5 && dp.gap >= 6 && dp.right <= dp.vw, JSON.stringify(dp));
  }
  await p.resize(1700, 1000);
  await clickExact(p, 'Dựng tự động (không dùng agent)');
  const ok = await p.waitFor(`!!Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Mở đề xuất')`, 120000);
  check('draft with the no-model provider finishes', ok);
  await sleep(1500);
  await stepperAgrees('draft done');
  const dr = (await api.get(`/api/projects/${PID}/draft`)).json;
  const props = (await api.get(`/api/projects/${PID}/proposals`)).json.items;
  const shown = /Có (\d+) cảnh/.exec(await text());
  check('SU-007 the draft panel and the proposal agree on the number of shots', !shown || props[0]?.summary.includes(`${shown[1]} cảnh`), `panel ${shown?.[0]} / proposal "${props[0]?.summary}" / last_run ${dr.last_run?.n_shots}`);
  await clickExact(p, 'Mở đề xuất'); await sleep(2500); await both(p, 'proposal-box');
  const rr = await p.eval(`(() => { const b = Array.from(document.querySelectorAll('button')).find(b => /^Áp dụng/.test(b.textContent.trim())); b.scrollIntoView(); const r = b.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2} })()`);
  await p.clickXY(rr.x, rr.y);
  await p.waitFor(`!!Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Lưu')`, 60000); await settle(p); await sleep(3000);
  const sb = await api.get(`/api/projects/${PID}/storyboard`);
  check('accept all gives the first storyboard', (await pipeline(api, PID)).has_storyboard === true, '');
  await both(p, 'editor-new');
  await clickExact(p, 'Lưu'); await sleep(2500);
  await clickExact(p, 'Duyệt');
  const ap = await (async () => { for (let i = 0; i < 90; i++) { await sleep(2000); if (stepsOf(await pipeline(api, PID)).edit.state === 'done') return true; } return false; })();
  check('storyboard approved from the editor', ap);
  await stepperAgrees('storyboard approved');
});

if (!onlyExtras) await step('A7 export', async () => {
  await go(p, base, `#/project/${PID}/export`);
  await noLeft('export page');
  await both(p, 'export-before');
  await clickExact(p, 'Xuất video');
  const sawRun = await p.waitFor(`document.body.innerText.includes('Đang chạy') || document.body.innerText.includes('Hủy')`, 20000);
  await snap(p, 'a7-export-running');
  check('export page shows progress while it runs', sawRun);
  const done = await p.waitFor(`document.body.innerText.includes('PHIẾU KIỂM TRA') || document.body.innerText.includes('Phiếu kiểm tra')`, 180000);
  await settle(p); await sleep(1500);
  check('export ends with the report card', done);
  await noLeft('export done');
  await stepperAgrees('export done');
  await both(p, 'export-done');
  const t = await text();
  check('export shows description, copy button and file links', has(t, 'Chép mô tả', 'Tải về'), '');
  const files = (await api.get(`/api/projects/${PID}/export`)).json.files || [];
  for (const f of files.slice(0, 4)) { const r = await fetch(base + `/api/projects/${PID}/export/files/${f.name}`); check(`export file ${f.name} downloads`, r.status === 200, r.status); }
});


await step('B/C/E extras', async () => {
  // B: the narration is edited after the voice, the storyboard and an export exist
  const n = (await api.get(`/api/projects/${PID}/narration`)).json;
  n.narration.chapters[0].beats[0].text += ' An extra sentence by the owner.';
  await api.put(`/api/projects/${PID}/narration`, { narration: n.narration, base_rev: n.rev });
  await go(p, base, `#/project/${PID}/voice`);
  const vt = await text();
  check('SU-003 after the narration is edited, the voice page says the existing voice is out of date (not only "locked")', /đã đổi|cũ|đọc lại/i.test(vt.split('Giọng đọc').slice(-1)[0] || ''), vt.slice(vt.indexOf('3. Giọng đọc'), vt.indexOf('3. Giọng đọc') + 200));
  // SU-003 / SU-008: every step that has output still opens, says it waits, and takes the owner to the step to act on
  const s3 = stepsOf(await pipeline(api, PID));
  const wantWaiting = ['voice', 'picks', 'edit', 'export'];
  check('SU-003 steps with output wait on the script (not "done", not "locked") and have_output / blocked_by are in the pipeline', wantWaiting.every((id) => s3[id].state === 'waiting' && s3[id].blocked_by === 'script' && s3[id].has_output === true), JSON.stringify(wantWaiting.map((id) => [id, s3[id].state, s3[id].blocked_by, s3[id].has_output])));
  const dom3 = await stepperTexts();
  check('SU-003 the stepper shows steps 3 to 6 as waiting on an earlier step (not "Xong", not "Khóa")', [2, 3, 4, 5].every((i) => /CHỜ BƯỚC TRƯỚC/i.test(dom3[i]) && !/XONG|KHÓA/i.test(dom3[i])), JSON.stringify(dom3));
  for (const id of wantWaiting) {
    await go(p, base, `#/project/${PID}/${id}`);
    const bn = await p.eval(`(() => { const b = document.querySelector('#step-banner'); return b && !b.hidden ? { text: b.innerText.replace(/\\s+/g, ' '), btn: Array.from(b.querySelectorAll('button')).map((x) => x.textContent.trim()) } : null; })()`);
    check(`SU-003 the ${id} page keeps its content and shows ONE banner that says what is going on and offers "Mở bước Kịch bản"`, bn && /Lời dẫn đang được sửa và chưa được duyệt lại/.test(bn.text) && bn.btn.includes('Mở bước Kịch bản') && !/null|undefined/.test(bn.text), JSON.stringify(bn));
    const body = await text();
    check(`SU-003 the ${id} page is not the "locked" page`, !/Bước này đang khóa/.test(body), body.slice(0, 160).replace(/\n/g, ' '));
    if (id === 'voice') await both(p, 'waiting-voice');
    if (id === 'export') await both(p, 'waiting-export');
  }
  await clickExact(p, 'Mở bước Kịch bản'); await settle(p);
  check('SU-008 the banner button goes to the script step', (await p.eval('location.hash')).endsWith('/script'), await p.eval('location.hash'));
  const rv = (await api.get(`/api/projects/${PID}/narration`)).json.rev;
  await api.post(`/api/projects/${PID}/narration/approve`, { rev: rv });
  // C: a page opened before a job starts elsewhere must notice it
  await go(p, base, `#/project/${PID}/voice`);
  await api.post(`/api/projects/${PID}/voice/generate`, { scope: 'all' });
  const noticed = await p.waitFor(`document.body.innerText.includes('Đang chạy')`, 12000);
  check('SU-009 a voice page open in one tab notices a job started in another tab', noticed);
  const followed = await p.waitFor(`/ĐANG CHẠY/i.test(document.querySelectorAll('.step')[2]?.innerText || '')`, 6000);
  check('SU-009 and the stepper follows (step 3 says "Đang chạy" within a few seconds)', followed, JSON.stringify(await stepperTexts()));
  for (let i = 0; i < 160; i++) { if ((await api.get(`/api/projects/${PID}/voice`)).json.state !== 'running') break; await sleep(1500); }
  await sleep(3500);
  check('after the job ended the stepper no longer says "Đang chạy" (asked once more a moment later)', !/ĐANG CHẠY/i.test((await stepperTexts())[2] || ''), JSON.stringify(await stepperTexts()));
  await stepperAgrees('voice after the job started elsewhere');
  // the same for an export started elsewhere
  await go(p, base, `#/project/${PID}/export`);
  const ex = await api.post(`/api/projects/${PID}/export/start`, {});
  if (ex.status === 200 || ex.status === 202) {
    // the fake export is quick: the page either shows the running job ("Hủy") or, when it ended between two looks, no longer says the old video is out of date
    const seen = await p.waitFor(`!!Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Hủy') || !document.body.innerText.includes('Cần xuất lại.')`, 20000);
    check('SU-009 an export page notices an export started in another tab', seen, ex.text.slice(0, 120));
    await p.waitFor(`document.body.innerText.includes('Phiếu kiểm tra')`, 180000);
  } else console.log('  (export could not start here, skipping its SU-009 check):', ex.status, ex.text.slice(0, 160));
  // and for a draft started elsewhere, with the dialog of the editor open
  await go(p, base, `#/project/${PID}/edit`);
  await clickExact(p, 'Bản nháp'); await sleep(1200);
  const dr = await api.post(`/api/projects/${PID}/draft/start`, { provider: 'auto' });
  if (dr.status === 200 || dr.status === 202) {
    const seen = await p.waitFor(`/Đang dựng bản nháp|Dừng/.test(document.querySelector('.modal')?.innerText || '')`, 15000);
    check('SU-009 the draft panel notices a draft started in another tab', seen, dr.text.slice(0, 120));
    await both(p, 'draft-running');
    for (let i = 0; i < 60; i++) { if (!['running'].includes(((await api.get(`/api/projects/${PID}/draft`)).json.state || {}).state)) break; await sleep(1500); }
    await sleep(3500);
  } else console.log('  (draft could not start here, skipping its SU-009 check):', dr.status, dr.text.slice(0, 160));
  await p.eval(`document.querySelector('.modal header button, .modal .close')?.click()`);
  // E: the old project
  await go(p, base, `#/project/arnolfini/export`);
  const hasLink = await p.eval(`!!Array.from(document.querySelectorAll('#view a, #view button')).find(e => /Dựng hình/.test(e.textContent) || /\\/edit/.test(e.getAttribute('href') || ''))`);
  check('SU-008 the locked export page of an old project offers a way to the storyboard step', hasLink);
  await go(p, base, `#/project/arnolfini/edit`);
  const hd = await p.eval(`document.querySelector('header, .topbar, #top')?.innerText || document.body.innerText.slice(0, 300)`);
  check('SU-010 the header of an imported project does not print "null"', !/\bnull\b/.test(hd), hd.replace(/\n/g, ' ').slice(0, 160));
  const lock = (await text());
  await go(p, base, `#/project/arnolfini-from-books/voice`);
  const lt = await text();
  check('SU-008 a locked step page offers a way to the step that unlocks it', await p.eval(`!!Array.from(document.querySelectorAll('#view a, #view button')).find(e => /Kịch bản/.test(e.textContent) || /\\/script/.test(e.getAttribute('href') || ''))`), '');
});

console.log(p.logs, p.bad());
br.close();
if (!keep && started) await down();
process.exit(finish());
