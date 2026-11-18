// Browser check of "Sửa video bằng lời" (step 5) and the model settings, against the second instance of the app on the server
// (tests/e2e/stages/launch.py: fakes, BTI_NO_REAL_MODELS=1; the mock model answers an edit with a canned edit built from the prompt).
// One PASS or FAIL line per check; exit code = number failing. Screenshots: .scratch/apage/shots/.
// Usage: node tests/e2e/stages/prompt_edit.mjs [--keep-server]
import { up, down, readState } from './remote.mjs';
import path from 'node:path';
import { openBrowser, makeApi, check, finish, bodyText, rawLooking, leftovers, go, settle, sleep, REPO } from './common.mjs';

const SHOTS = path.join(REPO, '.scratch/apage/shots');
const keep = process.argv.includes('--keep-server');
const started = !readState();
const st = await up({ doDeploy: started });
const base = st.base; const api = makeApi(base);
const br = await openBrowser();
const p = await br.newPage();
const closeAll = () => { try { br.close(); } catch {} };
process.on('exit', closeAll);
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { closeAll(); process.exit(130); });
process.on('uncaughtException', (e) => { console.error(e); closeAll(); process.exit(99); });

const PID = 'arnolfini-live';
const snap = async (name, size) => { await p.eval(`(() => { const l = document.querySelector('.prompt-thread-list'); if (l) l.scrollTop = 0; })()`); await sleep(200); const f = path.join(SHOTS, `${name}${size ? '-' + size : ''}.png`); await p.shot(f); return f; };
const both = async (name) => { await p.resize(1700, 1000); await sleep(500); await snap(name, '1700'); await p.resize(1280, 720); await sleep(500); await snap(name, '1280'); await p.resize(1700, 1000); await sleep(300); };
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} ran to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const ev = (x) => p.eval(x);
const turns = async () => (await api.get(`/api/projects/${PID}/draft/thread`)).json?.turns || [];
const serverBoard = async () => (await api.get(`/api/projects/${PID}`)).json;
const cardOf = (id) => `.prompt-turn-card[data-turn="${id}"]`;
const waitStatus = (id, status, ms = 180000) => p.waitFor(`document.querySelector('${cardOf(id)}')?.dataset.status === '${status}'`, ms);
const newestTurn = async (afterIds) => { const t = (await turns()).filter((x) => !afterIds.includes(x.id)); return t[t.length - 1]; };

/** Real click on the shot-band of the timeline at the middle of shot `i`. */
async function clickShot(i) {
  const pt = await ev(`(() => { const s = __bti.store.draft.shots[${i}]; const r = document.querySelector('#tl-canvas').getBoundingClientRect(); const tl = window.__tl; return { x: r.x + tl.X((s._t0 + s._t1) / 2), y: r.y + tl.Y.shot + tl.R.shot / 2 }; })()`);
  await p.clickXY(pt.x, pt.y); await sleep(300);
}
async function type(text) {
  await ev(`(() => { const t = document.querySelector('.prompt-instruction'); t.value = ''; t.focus(); })()`);
  await p.insert(text); await sleep(100);
}
async function send(text) {
  const before = (await turns()).map((t) => t.id);
  await type(text);
  await p.click('.prompt-btn-submit'); await sleep(600);
  for (let i = 0; i < 60; i++) { const n = await newestTurn(before); if (n) return n; await sleep(500); }
  return null;
}
const scopeText = () => p.text('.prompt-scope-words');
/** At 1280x720, without scrolling: is every action button of the card fully inside the visible part of the history area? */
async function actionsVisibleAt1280(id, expectNames) {
  await p.resize(1280, 720); await sleep(700);
  const r = await ev(`(() => { const l = document.querySelector('.prompt-thread-list').getBoundingClientRect(); const bs = Array.from(document.querySelectorAll('${cardOf(id)} .prompt-turn-actions button')); return { list: [l.top, l.bottom], n: bs.length, names: bs.map((b) => b.textContent.trim()), inside: bs.every((b) => { const x = b.getBoundingClientRect(); return x.top >= l.top - 0.5 && x.bottom <= l.bottom + 0.5 && x.width > 0; }), boxes: bs.map((b) => { const x = b.getBoundingClientRect(); return [Math.round(x.top), Math.round(x.bottom)]; }) }; })()`);
  return { ok: r.inside && r.n >= expectNames.length && expectNames.every((nm) => r.names.includes(nm)), r };
}
const cardText = (id) => ev(`document.querySelector('${cardOf(id)}')?.innerText || ''`);

try {
  await step('open the page', async () => {
    const pr = await api.get(`/api/projects/${PID}`);
    check('the test project is there with a storyboard', pr.status === 200 && pr.json.storyboard?.shots?.length > 3, `${pr.status} ${pr.text.slice(0, 120)}`);
    await p.resize(1700, 1000);
    await go(p, base, `#/project/${PID}/edit`);
    await p.waitFor(`!!window.__bti?.store?.draft && !!document.querySelector('.prompt-edit')`, 30000);
    await sleep(800);
    check('the box "Sửa video bằng lời" and the top-bar "Cài đặt" are on the page', await ev(`!!document.querySelector('.prompt-edit') && !!document.querySelector('#btn-settings') && /Cài đặt/.test(document.querySelector('#btn-settings').textContent)`));
    const t = await bodyText(p);
    check('the idle page has no leftovers and no raw words', !(await leftovers(p)).length && !rawLooking(t).length, JSON.stringify(await leftovers(p)));
    check('the thread starts empty with its own sentence', /Chưa có lần sửa nào/.test(await bodyText(p)) || (await turns()).length > 0);
    check('no model dropdown in the box (the setting decides)', await ev(`!document.querySelector('.prompt-edit select') && !!document.querySelector('.prompt-model-link')`));
    await both('01-idle');
    await p.resize(1280, 720); await sleep(600);
    const m = await ev(`(() => { const s = document.querySelector('#stage'), b = document.querySelector('#stage-box'), l = document.querySelector('.prompt-thread-list'), c = document.querySelector('#prompt-edit-container'); const cr = c.getBoundingClientRect(); return { stage: s.clientHeight, pic: b.getBoundingClientRect().height, picW: b.getBoundingClientRect().width, list: l.clientHeight, listOverflow: getComputedStyle(l).overflowY, boxBottom: cr.bottom, boxW: cr.width, win: innerHeight, pageScroll: document.documentElement.scrollHeight - innerHeight }; })()`);
    check('1280x720: the preview keeps at least 300 px of height', m.stage >= 300 && m.pic >= 280, JSON.stringify(m));
    check('1280x720: the thread has its own scrolling area inside the window', m.listOverflow === 'auto' && m.boxBottom <= m.win && m.pageScroll <= 1, JSON.stringify(m));
    await p.resize(1700, 1000); await sleep(400);
  });

  let T1 = null, shotIds = [];
  await step('two shots, instruction, applied card, undo', async () => {
    shotIds = await ev(`(() => { const s = __bti.store.draft.shots; const ok = (x) => __bti.ctx.tech(x.technique)?.kind !== 'card'; const out = []; for (let i = 0; i < s.length && out.length < 2; i++) if (ok(s[i])) out.push({ i, id: s[i].id }); return out; })()`);
    await clickShot(shotIds[0].i);
    check('the default scope is the selected shot, in words', /Cảnh \d+ đang chọn/.test(await scopeText()), await scopeText());
    await p.click('.prompt-multi-label');
    check('"Chọn nhiều cảnh" is on after the click', await ev(`document.querySelector('.prompt-multi').checked`));
    await clickShot(shotIds[1].i);
    const w = await scopeText();
    check('clicking a second shot adds it; the scope says "2 cảnh đang chọn"', /2 cảnh đang chọn/.test(w) && (await p.count('.prompt-shot-chip')) === 2, w);
    check('the scope words never show a shot id', !/\bs\d{4}\b/.test(await ev(`document.querySelector('.prompt-form').innerText`)));
    const playheadBefore = await ev(`__bti.ctx.t`);
    await ev(`document.querySelector('.prompt-instruction').scrollIntoView()`);
    T1 = await send('làm chậm chuyển động ở hai cảnh này và thêm một chút ánh sáng');
    check('sending creates a turn in the thread', !!T1, '');
    await p.waitFor(`!!document.querySelector('${cardOf(T1.id)}')`, 20000);
    const running = await ev(`document.querySelector('${cardOf(T1.id)}')?.dataset.status`);
    check('the turn card shows at once (running or already applied)', ['running', 'applied'].includes(running), running);
    const ok = await waitStatus(T1.id, 'applied');
    const raw = (await turns()).find((t) => t.id === T1.id);
    check('the turn ends applied', ok, JSON.stringify({ s: raw?.status, e: raw?.error, sum: raw?.summary }));
    if (!ok) { await snap('02-not-applied', '1700'); return; }
    await sleep(1500);
    const c = await cardText(T1.id);
    check('the applied card says what it did, with the badge and a 24-hour time', /Đã áp dụng/.test(c) && /\b\d\d:\d\d:\d\d\b/.test(c) && !/\b(AM|PM)\b/.test(c), c.slice(0, 200));
    const nCh = await p.count(`${cardOf(T1.id)} .prompt-change`);
    check('the card lists each change with its shot number and time', nCh >= 2 && /Cảnh \d+ · \d+:\d\d/.test(c), `${nCh} ${c.slice(0, 300)}`);
    await sleep(1500);
    const imgs = await ev(`Array.from(document.querySelectorAll('${cardOf(T1.id)} img')).map((i) => [i.naturalWidth, i.src.replace(/^https?:\\/\\/[^/]+/, '')])`);
    check('before and after thumbnails load for every change', imgs.length >= 4 && imgs.every((x) => x[0] > 0), JSON.stringify(imgs));
    check('the card has "Xem thử" and "Hoàn tác"', await ev(`!!document.querySelector('${cardOf(T1.id)} .prompt-btn-preview') && !!document.querySelector('${cardOf(T1.id)} .prompt-btn-undo')`));
    check('the card has no raw words, no English, no shot ids', !rawLooking(c).length && !/\bs\d{4}\b/.test(c) && !(await leftovers(p)).length, c.slice(0, 200));
    const sb = await serverBoard();
    const clientOk = await ev(`(() => ({ rev: __bti.store.rev, dirty: __bti.store.dirty, sel: __bti.store.sel.shot, t: __bti.ctx.t, notes: __bti.store.draft.shots.filter((s) => s.note === 'Làm chậm chuyển động (bản thử)').length }))()`);
    check('the editor took the new storyboard in: same revision as the server, nothing unsaved', clientOk.rev === sb.rev && clientOk.dirty === false, JSON.stringify({ c: clientOk.rev, s: sb.rev, dirty: clientOk.dirty }));
    check('the changed shots are in the editor', clientOk.notes >= 2, JSON.stringify(clientOk));
    check('the selection and the playhead stay where they were', shotIds.some((s) => s.id === clientOk.sel) && Math.abs(clientOk.t - playheadBefore) < 6, JSON.stringify({ sel: clientOk.sel, t: clientOk.t, before: playheadBefore }));
    const vis = await actionsVisibleAt1280(T1.id, ['Xem thử', 'Hoàn tác']);
    check('1280x720: "Xem thử" and "Hoàn tác" of the applied card are fully visible without scrolling', vis.ok, JSON.stringify(vis.r));
    await both('02-applied');
    // preview of the changed range
    p.clearLogs();
    await p.click(`${cardOf(T1.id)} .prompt-btn-preview`); await sleep(1500);
    const pv = p.net.find((r) => /\/preview$/.test(r.url) && r.method === 'POST');
    const body = pv?.body ? JSON.parse(pv.body) : null;
    check('"Xem thử" asks for a clip of the changed range (at most 10 s)', !!pv && pv.status === 200 && body.t1 > body.t0 && body.t1 - body.t0 <= 10.01, JSON.stringify({ s: pv?.status, b: body && { t0: body.t0, t1: body.t1 } }));
    const gotClip = await p.waitFor(`!!document.querySelector('.modal video')`, 90000);
    console.log('  (preview clip dialog appeared:', gotClip, ')');
    if (gotClip) await snap('03-preview-dialog', '1700');
    await ev(`document.querySelector('.modal header button')?.click()`); await sleep(500);
    // undo
    await p.click(`${cardOf(T1.id)} .prompt-btn-undo`);
    const un = await waitStatus(T1.id, 'undone', 60000);
    check('"Hoàn tác" ends with the badge "Đã hoàn tác"', un && /Đã hoàn tác/.test(await cardText(T1.id)), await cardText(T1.id));
    await sleep(1500);
    const sb2 = await serverBoard();
    const after = await ev(`({ rev: __bti.store.rev, dirty: __bti.store.dirty, notes: __bti.store.draft.shots.filter((s) => s.note === 'Làm chậm chuyển động (bản thử)').length })`);
    check('after the undo the server and the editor have the old shots back', after.rev === sb2.rev && after.notes === 0 && sb2.storyboard.shots.every((s) => s.note !== 'Làm chậm chuyển động (bản thử)') && !after.dirty, JSON.stringify(after));
    await snap('04-undone', '1700');
  });

  await step('an instruction the mock answers with "cannot"', async () => {
    await p.click('.prompt-multi-label');                                       // multi off again: the selected shot is the scope
    const n = await send('thêm một tranh mới của họa sĩ khác vào cảnh này');
    await p.waitFor(`!!document.querySelector('${cardOf(n.id)}')`, 20000);
    const ok = await waitStatus(n.id, 'no_change', 120000);
    const c = await cardText(n.id);
    check('"cannot" ends as "Không đổi" with the model\'s reason in Vietnamese', ok && /Không đổi/.test(c) && /bức tranh mới/.test(c), c.slice(0, 250));
    check('the "cannot" card offers no Hoàn tác and tells what to do next', !(await p.count(`${cardOf(n.id)} .prompt-btn-undo`)) && /nói rõ hơn/.test(c));
    const raw = (await turns()).find((t) => t.id === n.id);
    const sb = await serverBoard();
    const unchanged = await ev(`__bti.store.rev`) === sb.rev;
    check('nothing changed in the storyboard', unchanged && raw?.status === 'no_change', JSON.stringify({ rev: sb.rev, s: raw?.status }));
  });

  await step('a broken answer: failed card with "Thử lại"', async () => {
    const n = await send('làm gì đó [mock:broken]');
    const ok = await waitStatus(n.id, 'failed', 180000);
    const c = await cardText(n.id);
    const raw = (await turns()).find((t) => t.id === n.id);
    check('a failed turn says in one Vietnamese sentence what went wrong, and offers "Thử lại"', ok && /Không làm được/.test(c) && /Thử lại/.test(c) && !/spec_invalid|JSON|Traceback/.test(c.split('chi tiết')[0]), `${raw?.error} | ${c.slice(0, 300)}`);
    await both('05-failed');
    const before = (await turns()).length;
    await p.click(`${cardOf(n.id)} .prompt-btn-retry`);
    const more = await p.waitFor(`document.querySelectorAll('.prompt-turn-card').length > ${before}`, 20000);
    check('"Thử lại" sends the same instruction again (a new card appears)', more);
    await p.waitFor(`!document.querySelector('.prompt-turn-card[data-status="running"]')`, 180000);
  });

  await step('cancel a running turn', async () => {
    const n = await send('làm chậm chuyển động [mock:slow]');
    const running = await p.waitFor(`document.querySelector('${cardOf(n.id)}')?.dataset.status === 'running'`, 30000);
    check('a running card shows a progress line and a "Dừng" button', running && !!(await p.count(`${cardOf(n.id)} progress`)) && !!(await p.count(`${cardOf(n.id)} .prompt-btn-cancel`)) && /Đang/.test(await cardText(n.id)), await cardText(n.id));
    check('while a turn runs the field and the send button are off', await ev(`document.querySelector('.prompt-instruction').disabled && document.querySelector('.prompt-btn-submit').disabled`));
    await both('06-running');
    await p.click(`${cardOf(n.id)} .prompt-btn-cancel`);
    const ok = await waitStatus(n.id, 'cancelled', 60000);
    const c = await cardText(n.id);
    check('cancelling ends as "Đã hủy" with a plain sentence and no error text', ok && /Đã hủy/.test(c) && /không có gì thay đổi/i.test(c) && !/Lỗi|object Object/.test(c), c.slice(0, 200));
    check('the form is usable again after the cancel', await p.waitFor(`!document.querySelector('.prompt-instruction').disabled`, 10000));
  });

  await step('unsaved edits are merged with the applied turn', async () => {
    const other = await ev(`(() => { const s = __bti.store.draft.shots; return s[s.length - 1].id; })()`);
    await ev(`__bti.store.commit('sửa tay', (d) => { const s = d.shots[d.shots.length - 1]; s.note = 'sửa tay chưa lưu'; })`);
    check('the editor has an unsaved edit', await ev(`__bti.store.dirty`));
    await clickShot(shotIds[0].i);
    const n = await send('làm chậm chuyển động của cảnh này');
    const ok = await waitStatus(n.id, 'applied', 180000);
    await sleep(2500);
    const s = await ev(`(() => ({ dirty: __bti.store.dirty, canUndo: __bti.store.canUndo, hand: __bti.store.draft.shots.find((x) => x.id === ${JSON.stringify(other)})?.note, agent: __bti.store.draft.shots.find((x) => x.id === ${JSON.stringify(shotIds[0].id)})?.note, rev: __bti.store.rev }))()`);
    const sb = await serverBoard();
    check('with unsaved edits the turn is merged: my edit stays, the agent\'s change is in, the revision is the server\'s', ok && s.dirty && s.hand === 'sửa tay chưa lưu' && s.agent === 'Làm chậm chuyển động (bản thử)' && s.rev === sb.rev, JSON.stringify(s));
    check('the undo history starts fresh after the merge', s.canUndo === false, JSON.stringify(s));
    await ev(`__bti.store.undo()`);                                            // nothing to undo; the unsaved edit must survive
    await ev(`document.querySelector('#btn-save').click()`); await sleep(2500);
    const sb2 = await serverBoard();
    check('saving after the merge keeps both the hand edit and the agent edit', sb2.storyboard.shots.find((x) => x.id === other)?.note === 'sửa tay chưa lưu' && sb2.storyboard.shots.find((x) => x.id === shotIds[0].id)?.note === 'Làm chậm chuyển động (bản thử)', '');
    T1 = n;
  });

  await step('undo with a conflict, then force', async () => {
    const sb = await serverBoard();
    const target = shotIds[0].id;
    const nb = JSON.parse(JSON.stringify(sb.storyboard));
    nb.shots.find((x) => x.id === target).note = 'bạn sửa tay sau lần sửa';
    const put = await api.put(`/api/projects/${PID}/storyboard`, { storyboard: nb, base_rev: sb.rev });
    check('(setup) a hand edit of the same shot is saved after the turn', put.status === 200, put.text.slice(0, 160));
    await p.click(`${cardOf(T1.id)} .prompt-btn-undo`);
    const dlg = await p.waitFor(`/Hoàn tác sẽ bỏ sửa đổi của bạn/.test(document.querySelector('.modal')?.innerText || '')`, 20000);
    check('Hoàn tác with a changed shot asks first, in words, and names the shot by number', dlg && /cảnh \d+/.test(await ev(`document.querySelector('.modal').innerText`)), await ev(`document.querySelector('.modal')?.innerText || ''`));
    await snap('07-undo-conflict', '1700');
    await p.click('.modal footer button.danger');
    const ok = await waitStatus(T1.id, 'undone', 60000);
    check('"Vẫn hoàn tác" undoes it', ok, await cardText(T1.id));
    await sleep(1500);
    const sb2 = await serverBoard();
    check('the forced undo put the old shot back', sb2.storyboard.shots.find((x) => x.id === target)?.note !== 'bạn sửa tay sau lần sửa', '');
  });

  await step('the owner edited the same shot meanwhile: needs_choice, then each choice', async () => {
    const target = shotIds[1].id;
    await clickShot(shotIds[1].i);
    for (const [choice, label, finalStatus] of [['overwrite', 'Dùng bản của agent', 'applied'], ['discard', 'Giữ bản của bạn', 'cancelled']]) {
      let sb = await serverBoard();
      const pre = JSON.parse(JSON.stringify(sb.storyboard));                  // so that the agent's note differs from what is saved: the turn has something to change
      pre.shots.find((x) => x.id === target).note = `ghi chú cũ (${choice})`;
      const pp = await api.put(`/api/projects/${PID}/storyboard`, { storyboard: pre, base_rev: sb.rev });
      sb = await serverBoard();
      const r = await api.post(`/api/projects/${PID}/draft/edit`, { instruction: `làm chậm chuyển động [mock:slow] (${choice})`, scope: { shots: [target] }, mode: 'auto', base_rev: sb.rev });
      check(`(setup ${choice}) a slow turn on one shot started from outside`, r.status === 200, r.text.slice(0, 200));
      await sleep(1500);
      const nb = JSON.parse(JSON.stringify(sb.storyboard));
      nb.shots.find((x) => x.id === target).note = `sửa tay trong lúc chờ (${choice})`;
      const put = await api.put(`/api/projects/${PID}/storyboard`, { storyboard: nb, base_rev: sb.rev });
      check(`(setup ${choice}) the owner saves the same shot while the turn runs`, put.status === 200, put.text.slice(0, 160));
      const id = r.json?.turn_id;
      const got = await waitStatus(id, 'needs_choice', 90000);               // the page notices a job started elsewhere by itself
      const c = await cardText(id);
      check(`the card asks the owner to choose (${choice}): two choices in words, the shot named by number`, got && /Cần bạn chọn/.test(c) && c.includes('Dùng bản của agent') && c.includes('Giữ bản của bạn') && /cảnh \d+/.test(c), c.slice(0, 300));
      if (choice === 'overwrite') {
        const vis = await actionsVisibleAt1280(id, ['Dùng bản của agent', 'Giữ bản của bạn']);
        check('1280x720: the two choices of the needs_choice card are fully visible without scrolling', vis.ok, JSON.stringify(vis.r));
        await both('08-needs-choice');
      }
      await p.click(`${cardOf(id)} .${choice === 'overwrite' ? 'prompt-btn-overwrite' : 'prompt-btn-discard'}`);
      const done = await waitStatus(id, finalStatus, 60000);
      check(`choosing "${label}" settles the turn (${finalStatus})`, done, await cardText(id));
      await sleep(1500);
      const sb2 = await serverBoard();
      const note = sb2.storyboard.shots.find((x) => x.id === target)?.note;
      const clientRev = await ev(`__bti.store.rev`);
      if (choice === 'overwrite') check('overwrite: the agent\'s version is the saved one and the editor took it in', note === 'Làm chậm chuyển động (bản thử)' && clientRev === sb2.rev, JSON.stringify({ note, c: clientRev, s: sb2.rev }));
      else check('discard: the owner\'s version stays', note === `sửa tay trong lúc chờ (${choice})`, note);
    }
  });

  await step('a turn started from another tab shows up by itself', async () => {
    await ev(`document.activeElement?.blur?.()`);
    const sb = await serverBoard();
    const r = await api.post(`/api/projects/${PID}/draft/edit`, { instruction: 'làm chậm chuyển động ở đây', scope: { shots: [shotIds[0].id] }, mode: 'auto', base_rev: sb.rev });
    const id = r.json?.turn_id;
    const seen = await p.waitFor(`!!document.querySelector('${cardOf(id)}')`, 40000);
    check('the card of a turn started in another tab appears within seconds', seen, r.text.slice(0, 160));
    const ok = await waitStatus(id, 'applied', 180000);
    await sleep(2500);
    const sb2 = await serverBoard();
    check('and when it ends the editor takes the new storyboard in', ok && (await ev(`__bti.store.rev`)) === sb2.rev, '');
  });

  await step('the settings dialog "Mô hình cho từng việc"', async () => {
    await p.click('#btn-settings');
    const open = await p.waitFor(`/Mô hình cho từng việc/.test(document.querySelector('.modal')?.innerText || '') && document.querySelectorAll('.modal select.settings-model').length >= 6`, 20000);
    check('the top-bar entry opens the dialog with one dropdown per role', open, await ev(`document.querySelector('.modal')?.innerText || ''`));
    const txt = await ev(`document.querySelector('.modal').innerText`);
    check('the roles are named in Vietnamese and "Dùng một mô hình cho tất cả" is there', /Dàn ý kịch bản/.test(txt) && /Sửa nhanh bằng lời/.test(txt) && /Dùng một mô hình cho tất cả/.test(txt) && !/script\.outline|edit\.fast/.test(txt), txt.slice(0, 400));
    check('the model list is the normal case: display names with the id, and no "không có trong danh sách" on any row', /Gemini 3\.8 Flash \(High\) \(agy:gemini-3\.8-flash-high\)/.test(await ev(`document.querySelector('select[data-role="script.outline"]').selectedOptions[0].textContent`)) && !/không có trong danh sách/.test(txt) && !(await p.count('.settings-down')), txt.slice(0, 500));
    await both('09-settings');
    await ev(`(() => { const s = document.querySelector('select[data-role="script.outline"]'); s.value = 'mock'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await p.click('.settings-save');
    const saved = await p.waitFor(`/Đã lưu cài đặt/.test(document.querySelector('#toast-root')?.innerText || '')`, 15000);
    const g = await api.get('/api/settings/models');
    const role = (g.json?.roles || []).find((r) => r.role === 'script.outline');
    check('saving one dropdown writes that role through PUT and the dialog closes', saved && role?.model === 'mock' && role?.source === 'setting' && !(await p.count('.modal')), JSON.stringify(role));
    await p.click('#btn-settings');
    await p.waitFor(`document.querySelectorAll('.modal select.settings-model').length >= 6`, 15000);
    const shown = await ev(`document.querySelector('select[data-role="script.outline"]').value`);
    check('opened again, the dropdown shows the saved model', shown === 'mock', shown);
    await ev(`(() => { const s = document.querySelector('.modal .settings-all'); s.value = 'mock'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await p.click('.settings-all-apply');
    const vals = await ev(`Object.fromEntries(Array.from(document.querySelectorAll('.modal select.settings-model')).map((s) => [s.dataset.role, s.value]))`);
    check('"Dùng một mô hình cho tất cả" sets every role that can use it and leaves the agent roles alone', vals['edit.fast'] === 'mock' && vals['script.narration'] === 'mock' && /^agy:/.test(vals.draft) && /^agy:/.test(vals['edit.deep']), JSON.stringify(vals));
    await p.click('.settings-save');
    await p.waitFor(`!document.querySelector('.modal')`, 15000);
    const g2 = await api.get('/api/settings/models');
    check('after "all", the non-agent roles are saved as the mock model', (g2.json?.roles || []).filter((r) => !r.agentic).every((r) => r.model === 'mock'), JSON.stringify((g2.json?.roles || []).map((r) => [r.role, r.model])));
    check('the link in the edit box opens the same dialog', await (async () => { await p.click('.prompt-model-link'); const ok = await p.waitFor(`/Mô hình cho từng việc/.test(document.querySelector('.modal')?.innerText || '')`, 10000); await ev(`document.querySelector('.modal header button')?.click()`); return ok; })());
  });

  await step('clearing the history asks once', async () => {
    const n0 = await p.count('.prompt-turn-card');
    await p.click('.prompt-btn-clear'); await sleep(500);
    check('"Xóa lịch sử" opens a question first', await p.waitFor(`/Xóa danh sách các lần sửa/.test(document.querySelector('.modal')?.innerText || '')`, 8000));
    await ev(`Array.from(document.querySelectorAll('.modal footer button')).find((b) => b.textContent.trim() === 'Hủy').click()`); await sleep(400);
    check('answering Hủy keeps every turn', (await p.count('.prompt-turn-card')) === n0, '');
    await snap('10-thread-full', '1700');
    await p.click('.prompt-btn-clear'); await sleep(500);
    await p.click('.modal footer button.danger');
    check('confirming clears the thread', await p.waitFor(`document.querySelectorAll('.prompt-turn-card').length === 0 && /Chưa có lần sửa nào/.test(document.body.innerText)`, 15000));
  });

  const t = await bodyText(p);
  check('at the end: no leftovers, no raw words on the page', !(await leftovers(p)).length && !rawLooking(t).length, JSON.stringify(await leftovers(p)));
  const bad = p.bad().filter((x) => !/\/(preview|frame|thumb)|favicon|\.jpg|\/files\//.test(x) && !/^409 POST .*\/draft\/edit\/.*\/undo/.test(x));
  console.log('  (requests that failed, not counted:', JSON.stringify(bad), ')');
  console.log('  (browser log:', JSON.stringify(p.logs.slice(0, 8)), ')');
  check('no script error in the browser console', !p.logs.some((l) => /EXCEPTION|TypeError|ReferenceError/.test(l)), JSON.stringify(p.logs.slice(0, 5)));
} finally {
  closeAll();
  if (!keep && started) await down();
}
process.exit(finish());
