// Browser check of the prompt boxes on typed operations (worker c2box): step 5 "Sửa video bằng lời" and step 4 "Sửa chọn hình bằng lời", and the list
// "Lịch sử thay đổi" on both pages. Runs against a second instance of the app on the server (tests/e2e/stages/launch.py with the canned answers of
// tests/e2e/stages/box_mock.py: BTI_NO_REAL_MODELS=1, its own port and folder, data copied to a temp folder, NO real model) through an ssh tunnel, with
// headless Chrome on the Mac:
//   BTI_SSH_HOST=winbox-cmd BTI_STAGES_SUFFIX=c2box BTI_STAGES_PORT=8571 node tests/e2e/box/box.mjs [--keep-server]
// (suffix and port default to those; never 8560 or 8550). One PASS or FAIL line per check, exit code = number failing. Screenshots: .scratch/c2box/shots/.
process.env.BTI_STAGES_SUFFIX = process.env.BTI_STAGES_SUFFIX || 'c2box';
process.env.BTI_STAGES_PORT = process.env.BTI_STAGES_PORT || '8571';
const { up, down, readState } = await import('../stages/remote.mjs');
const { openBrowser, makeApi, check, finish, go, sleep, REPO, bodyText, rawLooking, leftovers } = await import('../stages/common.mjs');
const path = await import('node:path');

const SHOTS = path.join(REPO, '.scratch/c2box/shots');
const keep = process.argv.includes('--keep-server');
if (readState()) await down();                                                    // never reuse an instance that was started for another run
const st = await up({ doDeploy: true });
const base = st.base, api0 = makeApi(base);
const again = (f) => async (...a) => { for (let i = 0; ; i++) { try { return await f(...a); } catch (e) { if (i >= 3) throw e; await sleep(1500); } } };
const api = { get: again(api0.get), put: again(api0.put), post: again(api0.post), del: again(api0.del) };
const br = await openBrowser();
const p = await br.newPage();
let closed = false;
const closeAll = async () => { if (closed) return; closed = true; try { br.close(); } catch {} if (!keep) { try { await down(); } catch {} } };
process.on('exit', () => { try { br.close(); } catch {} });
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, async () => { await closeAll(); process.exit(130); });
process.on('uncaughtException', async (e) => { console.error(e); await closeAll(); process.exit(99); });

const S5 = 'arnolfini-live', S4 = 'arnolfini-from-books';
const ev = (x) => p.eval(x);
const J = JSON.stringify;
const U = (pid, tail = '') => `/api/projects/${pid}${tail}`;
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} ran to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const snap = async (name) => { await p.shot(path.join(SHOTS, `${name}.png`)); };
const until = async (fn, ms = 60000, every = 400) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = await fn(); if (v) return v; await sleep(every); } return null; };
const waitJob = async (id, path_ = '/api/jobs/') => until(async () => { const r = await api.get(path_ + id); return ['done', 'error', 'cancelled'].includes(r.json?.state) ? r.json : null; }, 180000, 1000);
const clean = async (what) => { const t = await bodyText(p); const l = await leftovers(p); check(`${what}: no leftovers, no raw words`, !l.length && !rawLooking(t).length, J(l) + J(rawLooking(t))); };
const isVi = (t) => /[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]/i.test(t || '');

/** The card of a turn of the box on the page, as the owner reads it. */
const cardText = (id) => ev(`(() => { const c = document.querySelector('.prompt-turn-card[data-turn="${id}"]'); return c ? c.innerText : ''; })()`);
const turnsOf = async (pid, picks) => (await api.get(U(pid, picks ? '/picks/edit/thread' : '/draft/thread'))).json?.turns || [];
const newTurn = async (pid, picks, before, statuses) => until(async () => (await turnsOf(pid, picks)).find((t) => !before.includes(t.id) && statuses.includes(t.status)), 90000);
/** Type a request in the box and send it with the button; returns the new turn once it has one of `statuses`. */
async function send(pid, picks, text, statuses = ['applied', 'no_change', 'failed', 'escalate']) {
  const before = (await turnsOf(pid, picks)).map((t) => t.id);
  await p.waitFor(`!document.querySelector('.prompt-instruction').disabled`, 90000);                        // a turn that ran just before has ended
  await ev(`(() => { const t = document.querySelector('.prompt-instruction'); t.value = ''; t.focus(); })()`);
  await p.insert(text); await sleep(150);
  await p.click('.prompt-btn-submit');
  const turn = await newTurn(pid, picks, before, statuses);
  if (!turn) console.log('  (note) no turn arrived; thread:', J((await turnsOf(pid, picks)).map((t) => [t.id, t.status, t.error])), 'toast:', await ev(`[...document.querySelectorAll('.toast, [class*=toast]')].map((e) => e.innerText).join(' || ')`));
  if (turn) await p.waitFor(`document.querySelector('.prompt-turn-card[data-turn="${turn.id}"]')?.dataset.status === ${J(turn.status)}`, 45000);   // the page reads the thread, draws the card
  await sleep(1200);                                                                // and takes the document in
  return turn;
}
async function clickShot(i) {
  const pt = await ev(`(() => { const s = __bti.store.draft.shots[${i}]; const r = document.querySelector('#tl-canvas').getBoundingClientRect(); const tl = window.__tl; return { x: r.x + tl.X((s._t0 + s._t1) / 2), y: r.y + tl.Y.shot + tl.R.shot / 2 }; })()`);
  await p.clickXY(pt.x, pt.y); await sleep(300);
}

try {
  await p.resize(1700, 1000);

  // ------------------------------------------------------------------------------------------------- step 5
  let cameraShot = -1;
  await step('step 5: the box and the list of changes are on the page, empty', async () => {
    await go(p, base, `#/project/${S5}/edit`);
    check('the page and the box are there', await p.waitFor(`!!window.__bti?.store?.draft && !!document.querySelector('.prompt-edit[data-box="storyboard"]')`, 40000));
    check('the list "Lịch sử thay đổi" is under the thread, and says there is nothing yet', await p.waitFor(`/Lịch sử thay đổi/.test(document.querySelector('.changes-list > summary')?.textContent || '')`, 20000));
    cameraShot = await ev(`(() => { const s = __bti.store.draft.shots; for (let i = 0; i < s.length; i++) if (!s[i].locked && Object.values(s[i].params || {}).some((v) => Array.isArray(v) && v.length && v[0]?.at)) return i; return -1; })()`);
    check('the test project has a shot with a camera move to slow down', cameraShot >= 0, String(cameraShot));
    await snap('01-step5-start');
  });

  let applied = null, before5 = null;
  await step('step 5: a request is applied as one batch; the card shows its sentences, the pictures, "Xem thử" and "Hoàn tác"', async () => {
    before5 = (await api.get(U(S5))).json;
    await clickShot(cameraShot);
    check('the scope line says the shot that was clicked', /Cảnh \d+ đang chọn/.test(await ev(`document.querySelector('.prompt-scope-words')?.textContent || ''`)), await ev(`document.querySelector('.prompt-scope-words')?.textContent || ''`));
    applied = await send(S5, false, 'làm chậm cú zoom ở cảnh này', ['applied', 'failed', 'no_change']);
    check('the turn is applied, with the id of its batch', applied?.status === 'applied' && /^batch_\d+$/.test(applied.batch || '') && applied.doc === 'storyboard', J(applied));
    const card = await cardText(applied.id);
    check('the card shows the summary (the agent\'s own sentence) and the sentences of the batch', card.includes('Máy quay ở cảnh này đi chậm hơn.') && /Cảnh \d+: đổi thiết lập/.test(card), card);
    check('the card says who did it and how long it took, with no technical word', /Agent: \S+/.test(card) && /sửa nhanh/.test(card) && !/batch|ops|dry|s\d{4}/.test(card), card);
    const frames = await p.waitFor(`document.querySelectorAll('.prompt-turn-card[data-turn="${applied.id}"] .prompt-frame img').length === 2 && [...document.querySelectorAll('.prompt-turn-card[data-turn="${applied.id}"] .prompt-frame img')].every((i) => i.complete && i.naturalWidth > 0)`, 60000);
    check('the pictures before and after of the changed shot are loaded', frames);
    check('the buttons "Xem thử" and "Hoàn tác" are there', await ev(`!!document.querySelector('.prompt-turn-card[data-turn="${applied.id}"] .prompt-btn-preview') && !!document.querySelector('.prompt-turn-card[data-turn="${applied.id}"] .prompt-btn-undo:not([disabled])')`));
    const after = (await api.get(U(S5))).json;
    check('the saved storyboard changed (one shot) and the editor took it in without an unsaved mark', after.rev !== before5.rev && J(after.storyboard.shots).length > 0 && (await ev(`!__bti.store.dirty && __bti.store.rev === ${J(after.rev)}`)), `${before5.rev} ${after.rev}`);
    const log = (await api.get(U(S5, '/changes?doc=storyboard'))).json.changes;
    check('the change log has one batch with the request as its note, by the agent', log.length === 1 && log[0].note === 'làm chậm cú zoom ở cảnh này' && /^agent:/.test(log[0].actor) && log[0].batch === applied.batch, J(log[0]));
    await snap('02-step5-applied');
    await clean('step 5 after a turn');
  });

  await step('step 5: "Xem thử" opens a short clip of the changed shot', async () => {
    await p.click(`.prompt-turn-card[data-turn="${applied.id}"] .prompt-btn-preview`);
    const opened = await p.waitFor(`!!document.querySelector('.modal video, .modal .preview-modal, .modal [class*=preview]')`, 90000);
    check('the preview clip opens', opened);
    await ev(`document.querySelector('.modal header button, .modal .close')?.click()`); await sleep(600);
  });

  await step('step 5: the list of changes shows the batch, with "Hoàn tác" on it; the card\'s "Hoàn tác" puts the storyboard back', async () => {
    await ev(`document.querySelector('.changes-list')?.setAttribute('open', '')`); await sleep(1500);
    const row = await ev(`(() => { const r = document.querySelector('.changes-row[data-batch="${applied.batch}"]'); return r ? { text: r.innerText, undo: !!r.querySelector('.changes-btn-undo') } : null; })()`);
    check('the row has the time, "Bạn" or the agent, the request and the sentence, and the button', !!row && /Agent mock|Gemini|Opus/.test(row.text) && /Yêu cầu: làm chậm cú zoom/.test(row.text) && /Cảnh \d+: đổi thiết lập/.test(row.text) && row.undo, J(row));
    await snap('03-step5-list');
    await p.click(`.prompt-turn-card[data-turn="${applied.id}"] .prompt-btn-undo`);
    const undone = await until(async () => (await turnsOf(S5, false)).find((t) => t.id === applied.id && t.status === 'undone'), 60000);
    check('the turn becomes "Đã hoàn tác"', !!undone, J(await turnsOf(S5, false)));
    await sleep(1500);
    const now = (await api.get(U(S5))).json;
    check('the storyboard is exactly as before the request', J(now.storyboard.shots.map(({ _t0, _t1, ...s }) => s)) === J(before5.storyboard.shots.map(({ _t0, _t1, ...s }) => s)));
    const txt = await ev(`document.querySelector('.changes-row')?.innerText || ''`);
    check('the list now shows the undo and marks the first batch as undone', /Hoàn tác một lần sửa/.test(txt) && /đã hoàn tác/.test(await ev(`document.querySelector('.changes-list')?.innerText || ''`)), txt);
    await snap('04-step5-undone');
  });

  await step('step 5: a request the agent cannot do changes nothing and says why in Vietnamese', async () => {
    const rev = (await api.get(U(S5))).json.rev;
    const t = await send(S5, false, 'thay bằng một bức tranh mới của họa sĩ khác');
    const card = await cardText(t.id);
    check('the turn is "Không đổi" and the card gives the reason', t.status === 'no_change' && /Không đổi/.test(card) && /bức tranh mới/.test(card) && isVi(card), card);
    check('nothing was written', (await api.get(U(S5))).json.rev === rev);
  });

  await step('step 5: a request for the slower way offers one button that says it takes minutes', async () => {
    const t = await send(S5, false, 'zoom vào chiếc nhẫn [mock:escalate]');
    const card = await cardText(t.id);
    check('the card says what is missing and that the slower way takes a few minutes', t.status === 'escalate' && /Cần làm kỹ hơn/.test(card) && /chưa có vùng nào/.test(card) && /mất vài phút/.test(card), card);
    check('the button "Làm kỹ hơn" is there', await ev(`!!document.querySelector('.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-slower')`));
    await snap('05-step5-escalate');
    const beforeIds = (await turnsOf(S5, false)).map((x) => x.id);
    await p.click(`.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-slower`);
    const second = await newTurn(S5, false, beforeIds, ['failed', 'applied', 'running', 'no_change', 'needs_choice']);
    const toast = await ev(`[...document.querySelectorAll('.toast, [class*=toast]')].map((e) => e.innerText).join(' || ')`);
    console.log('  (note) after "Làm kỹ hơn":', J(second && { status: second.status, path: second.path, error: second.error }), toast);
    check('pressing it sends the same request to the slow way (this test instance has no agent program: the answer is a plain sentence)', (!!second && second.path === 'deep') || (/agy|Antigravity|Chưa cài/i.test(toast) && isVi(toast)), J(second) + toast);
  });

  await step('step 5: a request the server refuses shows one plain sentence, writes nothing, and can be sent again', async () => {
    const rev = (await api.get(U(S5))).json.rev;
    const t = await send(S5, false, 'làm chậm hơn nữa [mock:refuse]');
    const card = await cardText(t.id);
    check('the turn failed with a plain Vietnamese sentence', t.status === 'failed' && /Không làm được/.test(card) && /không có trong storyboard/.test(card) && isVi(card), card);
    check('no code, no id, no English on the card', !/unknown_|s9999|\bshot\b|\bop\b/i.test(card.split('chi tiết')[0]), card);
    check('nothing was written and the button "Thử lại" is there', (await api.get(U(S5))).json.rev === rev && (await ev(`!!document.querySelector('.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-retry')`)));
    await snap('06-step5-refused');
    await clean('step 5 refusals');
  });

  // ------------------------------------------------------------------------------------------------- step 4
  await step('step 4: the project gets an approved narration and a main picture (the page\'s own routes)', async () => {
    let r = await api.post(U(S4, '/outline/generate'), {});
    check('the outline starts', r.status === 200, r.text.slice(0, 200));
    const o = await until(async () => { const x = (await api.get(U(S4, '/outline'))).json; return x?.outline ? x : null; }, 180000, 1500);
    check('and is written', !!o);
    check('the outline is approved', (await api.post(U(S4, '/outline/approve'), { rev: o.rev })).status === 200);
    // the narration is pasted (the page's own route for it): the generation by the mock model is not what this check is about
    const chs = o?.outline?.chapters || [];
    const per = Math.max(8, Math.round(2000 / Math.max(1, chs.length) / 8));          // about the target of 2000 words, so that the narration can be approved
    const beat = (i, k) => `Câu ${k + 1} của chương ${i + 1}: ` + Array.from({ length: per - 5 }, (_, w) => 'chữ' + w).join(' ') + '.';
    const text = 'FINAL SCRIPT\n' + chs.map((c, i) => `## ${c.id} ${c.title}\n` + Array.from({ length: 8 }, (_, k) => beat(i, k)).join('\n')).join('\n');
    r = await api.post(U(S4, '/narration/import'), { text });
    check('the narration is pasted', r.status === 200, r.text.slice(0, 300));
    const n = (await api.get(U(S4, '/narration'))).json;
    const ap = await api.post(U(S4, '/narration/approve'), { rev: n.rev });
    check('the narration is approved', ap.status === 200, ap.text.slice(0, 400));
    const s = await api.post(U(S4, '/picks/search'), { query: 'Arnolfini Portrait', sources: ['commons'] });
    const item = (s.json?.items || [])[0];
    check('the fake Commons answers a search', !!item, s.text.slice(0, 200));
    const im = await api.post(U(S4, '/picks/import'), { source: item?.source || 'commons', source_id: item?.source_id, as_main: true });
    check('the main picture is imported', im.status === 200 && !!im.json.picks.main_asset, im.text.slice(0, 200));
    const key = im.json.picks.main_asset;
    const rg = await api.put(U(S4, `/picks/assets/${key}/regions`), { regions: { FACE: { x: 300, y: 300, rx: 80, ry: 80, label: 'khuôn mặt' } }, base_rev: im.json.rev });
    check('and has one region', rg.status === 200 && !!rg.json.picks.assets[key].regions.FACE, rg.text.slice(0, 200));
  });

  let pk = null, beatBefore = null, beatId = null;
  await step('step 4: the box is on the page; a request is applied as one batch and the line shows the new pictures', async () => {
    await go(p, base, `#/project/${S4}/picks`);
    check('the box and its list of changes are there', await p.waitFor(`!!document.querySelector('.prompt-edit[data-box="picks"]') && !!document.querySelector('.prompt-edit[data-box="picks"] .changes-list')`, 40000));
    beatId = await ev(`document.querySelectorAll('button.pk-beat')[2]?.querySelector('.bid')?.textContent || ''`);
    await ev(`document.querySelectorAll('button.pk-beat')[2]?.click()`); await sleep(600);
    check('the scope line says the line that was clicked', /Dòng 3 đang chọn/.test(await ev(`document.querySelector('.prompt-edit[data-box="picks"] .prompt-scope-words')?.textContent || ''`)), await ev(`document.querySelector('.prompt-edit[data-box="picks"] .prompt-scope-words')?.textContent || ''`));
    pk = (await api.get(U(S4, '/picks'))).json;
    beatBefore = pk.picks.beats[beatId] || null;
    const t = await send(S4, true, 'dòng này cho xem cả bức tranh rồi chi tiết khuôn mặt');
    check('the turn is applied, with its batch', t?.status === 'applied' && /^batch_\d+$/.test(t.batch || '') && t.doc === 'picks', J(t));
    const card = await cardText(t.id);
    check('the card shows the summary and the sentence of the batch, with no picture frames', card.includes('Dòng này giờ cho xem cả bức tranh') && /Đoạn 3: thay 2 hình/.test(card) && !(await ev(`!!document.querySelector('.prompt-edit[data-box="picks"] .prompt-frame')`)), card);
    const now = (await api.get(U(S4, '/picks'))).json;
    check('picks.json has the two pictures on that line', (now.picks.beats[beatId]?.items || []).length === 2 && now.picks.beats[beatId].items[1].region === 'FACE', J(now.picks.beats[beatId]));
    check('the page took it in: the tray of the line shows two pictures', await p.waitFor(`/hình của dòng này \\(2\\)/i.test(document.body.innerText)`, 30000));
    const log = (await api.get(U(S4, '/changes?doc=picks'))).json.changes;
    check('the change log has the batch with the request as its note', log[0]?.batch === t.batch && log[0].note === 'dòng này cho xem cả bức tranh rồi chi tiết khuôn mặt' && /^agent:/.test(log[0].actor), J(log[0]));
    await snap('07-step4-applied');
    await clean('step 4 after a turn');
    // the list of changes and the undo of the card
    await ev(`document.querySelector('.prompt-edit[data-box="picks"] .changes-list')?.setAttribute('open', '')`); await sleep(1200);
    check('the list shows the batch with "Hoàn tác"', await ev(`!!document.querySelector('.prompt-edit[data-box="picks"] .changes-row[data-batch="${t.batch}"] .changes-btn-undo')`));
    await p.click(`.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-undo`);
    const undone = await until(async () => (await turnsOf(S4, true)).find((x) => x.id === t.id && x.status === 'undone'), 60000);
    await sleep(1500);
    const back = (await api.get(U(S4, '/picks'))).json;
    check('the card\'s undo puts the line back as it was', !!undone && J(back.picks.beats[beatId] || null) === J(beatBefore), J(back.picks.beats[beatId]));
    check('and the page shows it', await p.waitFor(`!/hình của dòng này \\(2\\)/i.test(document.body.innerText)`, 30000));
    await snap('08-step4-undone');
  });

  await step('step 4: a request that needs a picture the project does not have says so and offers the search by hand', async () => {
    const raw = J((await api.get(U(S4, '/picks'))).json.picks);
    const t = await send(S4, true, 'thêm một tấm bản đồ Bruges cho dòng này');
    const card = await cardText(t.id);
    check('the card says the picture is missing and that the agent of the pictures does not exist yet', t.status === 'escalate' && /Cần làm kỹ hơn/.test(card) && /bản đồ/.test(card) && /Agent chọn hình chưa có/.test(card), card);
    check('the button "Tìm hình bằng tay" is there and opens the search', await ev(`!!document.querySelector('.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-manual')`));
    await p.click(`.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-manual`); await sleep(600);
    check('the search of the page is shown', await ev(`!!document.querySelector('#pk-right .pk-searchform')`));
    check('nothing was written', J((await api.get(U(S4, '/picks'))).json.picks) === raw);
    await snap('09-step4-escalate');
  });

  await step('step 4: a request the server refuses shows one plain sentence and writes nothing', async () => {
    const raw = J((await api.get(U(S4, '/picks'))).json.picks);
    const t = await send(S4, true, 'sắp lại hình [mock:refuse]');
    const card = await cardText(t.id);
    check('the turn failed with a plain Vietnamese sentence', t.status === 'failed' && /Không làm được/.test(card) && /không có trong danh sách hình/.test(card) && isVi(card), card);
    check('no code, no id, no English on the card', !/unknown_|b9999|\bbeat\b|\bop\b/i.test(card.split('chi tiết')[0]), card);
    check('nothing was written', J((await api.get(U(S4, '/picks'))).json.picks) === raw);
    await snap('10-step4-refused');
    await clean('step 4 refusals');
  });
} finally {
  const failing = finish();
  await closeAll();
  process.exit(failing);
}
