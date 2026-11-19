// Browser check of the two simple pages (worker c4pages): step 4 "Chọn hình" (rows with pictures, the agent's button, the request box, "Tự chọn tay") and step 5
// "Dựng hình" (the video and the list of shots in words, selecting, a request and its card, "Chỉnh tay" and back, the remembered choice, problems).
// Runs against a second instance of the app on the server (tests/e2e/picks_auto/launch_picks_auto.py wrapping tests/e2e/stages/launch.py: BTI_NO_REAL_MODELS=1, its own
// port 8585 and folder suffix `c4pages`, data copied to a temp folder, the two agents are MOCK agents carrying the names of the real two, the agent in a work folder is a
// fake runner, the picture sources are fakes, the box answers with the canned answers of tests/e2e/stages/box_mock.py; no agy, no claude, no network) through an ssh
// tunnel, with headless Chrome on the Mac:
//   BTI_SSH_HOST=winbox-cmd node tests/e2e/pages/pages.mjs [--keep-server] [--only=step4|step5]
// One PASS or FAIL line per check, exit code = number failing. Screenshots of every state at 1280x720 and 1920x1080: .scratch/c4pages/shots/. The instance is stopped at the end.
process.env.BTI_STAGES_LAUNCH = 'tests\\e2e\\picks_auto\\launch_picks_auto.py';              // before remote.mjs is loaded: it reads these once
process.env.BTI_STAGES_SUFFIX = process.env.BTI_STAGES_SUFFIX || 'c4pages';
process.env.BTI_STAGES_PORT = process.env.BTI_STAGES_PORT || '8585';
const { up, down, readState } = await import('../stages/remote.mjs');
const { openBrowser, makeApi, check, finish, go, sleep, REPO, bodyText, rawLooking, leftovers } = await import('../stages/common.mjs');
const path = await import('node:path');

const SHOTS = path.join(REPO, '.scratch/c4pages/shots');
const keep = process.argv.includes('--keep-server');
const only = (process.argv.find((a) => a.startsWith('--only=')) || '').slice(7);
if (readState()) await down();                                                    // never reuse an instance that does not carry the fakes
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

const S4 = 'picks-demo', S5 = 'arnolfini-live';
const ev = (x) => p.eval(x);
const J = JSON.stringify;
const U = (pid, tail = '') => `/api/projects/${pid}${tail}`;
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} ran to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const text = (sel) => ev(`document.querySelector(${J(sel)})?.innerText?.replace(/\\s+/g, ' ').trim() || ''`);
const exists = (sel) => ev(`!!document.querySelector(${J(sel)})`);
const until = async (fn, ms = 60000, every = 300) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = await fn(); if (v) return v; await sleep(every); } return null; };
const shot = async (name) => { await p.shot(path.join(SHOTS, `${name}.png`)); };
/** Step 5 only: the frame of the player is drawn ("khung ..." in the state line, or a note in words) and the small frames of the rows that are on the screen have loaded or failed. */
const framesReady = async () => {
  await p.waitFor(`(() => { const s = document.querySelector('#frame-state'); const t = s?.textContent || ''; return !document.querySelector('.edit-root') || /^khung /.test(t) || !!s?.classList.contains('warn') || !!document.querySelector('.stage-note:not([hidden])'); })()`, 60000);
  await p.waitFor(`[...document.querySelectorAll('.sr-frame img')].filter((i) => { const r = i.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; }).every((i) => i.complete)`, 60000);
  await sleep(500);
};
const both = async (name) => { for (const [w, h] of [[1280, 720], [1920, 1080]]) { await p.resize(w, h); await sleep(500); await framesReady(); await shot(`${name}-${w}`); } await p.resize(1280, 720); await sleep(300); };
const clean = async (what) => { const t = await bodyText(p); const l = await leftovers(p); check(`${what}: no leftovers, no raw words`, !l.length && !rawLooking(t).length, J(l) + J(rawLooking(t))); };
const isVi = (t) => /[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]/i.test(t || '');
const RAW = /\b[A-Z]{1,6}-[A-Z0-9]{1,3}\b|\bs\d{3,4}\b|\bb\d{4}\b|\w_\w|\.(jpg|png|mp4|json)\b/;            // a technique id, a shot id, a line id, an underscore name, a file name
/** A real click with the Ctrl (2) or Shift (8) key held, on the first element that matches. */
async function clickMod(sel, modifiers) {
  const r = await p.rect(sel);
  if (!r) throw new Error('clickMod: not found ' + sel);
  await p.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: r.x, y: r.y, button: 'none', buttons: 0, modifiers });
  await p.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: r.x, y: r.y, button: 'left', buttons: 1, clickCount: 1, modifiers });
  await p.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: r.x, y: r.y, button: 'left', buttons: 0, clickCount: 1, modifiers });
  await sleep(300);
}
const CTRL = 4, SHIFT = 8;                                                      // 4 is the Meta key: on a Mac a Ctrl click is a right click and never reaches the page as a click (the page takes Ctrl or Meta)
const geometry = (sels) => ev(`(() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), r: Math.round(b.right), b: Math.round(b.bottom), w: Math.round(b.width), h: Math.round(b.height) }; };
  const els = [document.scrollingElement, document.body, document.querySelector('#view'), document.querySelector('main'), ...${J(sels)}.map((s) => document.querySelector(s))].filter(Boolean);
  return { iw: innerWidth, ih: innerHeight, scrollW: els.map((e) => [e.scrollWidth, e.clientWidth]), boxes: Object.fromEntries(${J(sels)}.map((s) => [s, r(s)])) }; })()`);
const noSideways = (g) => g.scrollW.every(([sw, cw]) => sw <= cw + 1);
const inside = (b, g) => !!b && b.x >= 0 && b.y >= 0 && b.r <= g.iw + 1 && b.b <= g.ih + 1 && b.w > 0 && b.h > 0;
const first = async () => { await p.send('Page.navigate', { url: base + '/#/' }); await sleep(1200); };      // the first address has no ?mode: the pages open on their simple face (go() adds ?mode=hand only on a first navigation)

const sendReq = async (pid, picks, words, statuses = ['applied', 'no_change', 'failed', 'escalate']) => {
  const turns = async () => (await api.get(U(pid, picks ? '/picks/edit/thread' : '/draft/thread'))).json?.turns || [];
  const before = (await turns()).map((t) => t.id);
  await p.waitFor(`!document.querySelector('.prompt-instruction').disabled`, 90000);
  await ev(`(() => { const t = document.querySelector('.prompt-instruction'); t.value = ''; t.focus(); })()`);
  await p.insert(words); await sleep(150);
  await p.click('.prompt-btn-submit');
  const turn = await until(async () => (await turns()).find((t) => !before.includes(t.id) && statuses.includes(t.status)), 90000);
  if (turn) await p.waitFor(`document.querySelector('.prompt-turn-card[data-turn="${turn.id}"]')?.dataset.status === ${J(turn.status)}`, 45000);
  await sleep(1500);                                                              // the page reads the thread, draws the card and takes the document in
  return turn;
};
const cardText = (id) => ev(`(() => { const c = document.querySelector('.prompt-turn-card[data-turn="${id}"]'); return c ? c.innerText : ''; })()`);
const strip = (o) => (Array.isArray(o) ? o.map(strip) : o && typeof o === 'object' ? Object.fromEntries(Object.entries(o).filter(([k]) => !k.startsWith('_')).map(([k, v]) => [k, strip(v)])) : o);

try {
  await first();

  // ================================================================================================= step 4
  if (!only || only === 'step4') {
    await step('step 4: the page opens on the rows, with the count and the button', async () => {
      await api.put('/api/settings/agent', { agent: 'gemini' });
      await p.resize(1280, 720);
      await go(p, base, `#/project/${S4}/picks`);
      check('the rows are there, one per narration line, and the hand tools are not on the screen', await p.waitFor(`document.querySelector('.pk-root')?.dataset.mode === 'simple' && document.querySelectorAll('.pr-row').length === 6`, 40000) && !(await ev(`!!document.querySelector('#pk-left')?.offsetParent`)), await text('#pk-rows-col'));
      const top = await text('#pk-top');
      check('the header has the name of the project, "0/6 đoạn đã có hình", "6 đoạn chưa có hình" and the approval button', /Chọn hình/.test(top) && /0\/6 đoạn đã có hình/.test(top) && /6 đoạn chưa có hình/.test(top) && /Duyệt chọn hình/.test(top), top);
      check('every row says in words that it has no picture', (await ev(`[...document.querySelectorAll('.pr-row')].every((r) => /Chưa có hình/.test(r.innerText))`)));
      check('the button "Để agent chọn hình" is there and can be pressed', (await text('#pk-auto-start')) === 'Để agent chọn hình' && (await ev(`!document.querySelector('#pk-auto-start').disabled`)));
      check('the first line is selected and the request box says so, in "đoạn"', /Đoạn 1 đang chọn/.test(await text('.prompt-edit[data-box="picks"] .prompt-scope-words')), await text('.prompt-edit[data-box="picks"] .prompt-scope-words'));
      check('the box has one agent select (the bar\'s), not two', (await ev(`[...document.querySelectorAll('.agent-select')].filter((e) => e.offsetParent).length`)) === 1);
      await clean('step 4 at rest');
      await both('01-step4-rest');
    });

    await step('step 4: the count of lines without a picture jumps to them', async () => {
      await p.click('#pk-missing'); await sleep(300);
      const a = await ev(`[...document.querySelectorAll('.pr-row.sel')].map((e) => e.dataset.id).join(',')`);
      await p.click('#pk-missing'); await sleep(300);
      const b = await ev(`[...document.querySelectorAll('.pr-row.sel')].map((e) => e.dataset.id).join(',')`);
      check('the first press selects the first line without a picture, the second the next one', a === 'b0001' && b === 'b0002', `${a} ${b}`);
    });

    await step('step 4: the agent button runs, shows its progress and fills the lines, with the reason under each', async () => {
      await api.put('/api/_e2e/picks_auto', { slow: false, fail: false, reset: true });
      await p.click('#pk-auto-start');
      check('while it runs the bar says so, with the part and the limits', await p.waitFor(`document.querySelector('#pk-auto .pk-auto-bar')?.dataset.state === 'running' && /\\(\\d\\/4\\)/.test(document.querySelector('#pk-auto-line')?.innerText || '')`, 60000), await text('#pk-auto'));
      await shot('02-step4-running-1280');
      check('it ends with one sentence, 5 of 6 lines and the line that has no picture', await p.waitFor(`/Agent đã chọn hình cho 5\\/6 đoạn\\. 1 đoạn chưa có hình phù hợp/.test(document.querySelector('#pk-auto-sentence')?.innerText || '')`, 180000), await text('#pk-auto'));
      await sleep(1000);
      const rows = await ev(`[...document.querySelectorAll('.pr-row')].map((r) => ({ id: r.dataset.id, pics: [...r.querySelectorAll('.pr-cap')].map((c) => c.innerText.trim()), reason: r.querySelector('.pr-reason')?.innerText || '', empty: /Chưa có hình/.test(r.innerText) }))`);
      check('line 1 shows the whole painting and its reason', rows[0].pics[0] === 'Cả bức tranh' && /^Agent: Mở bằng cả bức tranh/.test(rows[0].reason), J(rows[0]));
      check('line 2 shows a close-up of a region with a plain caption', /^Cận cảnh: /.test(rows[1].pics[0]) && /^Agent: /.test(rows[1].reason), J(rows[1]));
      check('line 3 still has no picture and says so, with the reason of the agent', rows[2].empty && rows[2].pics.length === 0, J(rows[2]));
      check('line 4 shows a map and a clip with its length, each with a caption', rows[3].pics.some((c) => /^Bản đồ: /.test(c)) && rows[3].pics.some((c) => /^Clip( \d+ giây)?: /.test(c)), J(rows[3]));
      check('the header counts again: 5/6 pictures, 1 line without', /5\/6 đoạn đã có hình/.test(await text('#pk-top')) && /1 đoạn chưa có hình/.test(await text('#pk-top')), await text('#pk-top'));
      check('"Chọn lại phần còn thiếu" is offered', await exists('#pk-auto-again'));
      await p.click('#pk-missing'); await sleep(300);
      check('and the count jumps to the line that is missing', (await ev(`document.querySelector('.pr-row.sel')?.dataset.id`)) === 'b0003');
      check('no row shows a raw word, a line id or a file name', !(await ev(`[...document.querySelectorAll('.pr-row')].some((r) => ${RAW}.test(r.innerText.replace(/Đoạn \\d+/g, '')))`)));
      await clean('step 4 after the agent');
      await both('03-step4-agent-done');
    });

    await step('step 4: Ctrl and Shift select several lines, a chapter header a whole chapter; the box says it in words', async () => {
      await p.click('.pr-row[data-id="b0002"] .pr-text'); await sleep(300);
      check('one click selects one line', /Đoạn 2 đang chọn/.test(await text('.prompt-edit[data-box="picks"] .prompt-scope-words')), await text('.prompt-edit[data-box="picks"] .prompt-scope-words'));
      await clickMod('.pr-row[data-id="b0004"] .pr-text', CTRL);
      check('Ctrl adds a line', /2 đoạn đang chọn \(2, 4\)/.test(await text('.prompt-edit[data-box="picks"] .prompt-scope-words')), await text('.prompt-edit[data-box="picks"] .prompt-scope-words'));
      await p.click('.pr-row[data-id="b0001"] .pr-text'); await sleep(200);
      await clickMod('.pr-row[data-id="b0003"] .pr-text', SHIFT);
      check('Shift selects the run between two lines', /3 đoạn đang chọn \(1, 2, 3\)/.test(await text('.prompt-edit[data-box="picks"] .prompt-scope-words')), await text('.prompt-edit[data-box="picks"] .prompt-scope-words'));
      await p.click('.chap-sel');
      check('"Chọn cả chương" selects the whole chapter and the box says "Chương"', /Chương/.test(await text('.prompt-edit[data-box="picks"] .prompt-scope-words')) && (await ev(`document.querySelectorAll('.pr-row.sel').length`)) >= 1, await text('.prompt-edit[data-box="picks"] .prompt-scope-words'));
      await p.click('.pr-row[data-id="b0005"] .pr-text'); await sleep(200);
    });

    let line5 = null;
    await step('step 4: a request changes a line, the row shows it, and the card undoes it', async () => {
      line5 = (await api.get(U(S4, '/picks'))).json.picks.beats.b0005 || null;
      await p.click('.pr-row[data-id="b0005"] .pr-text'); await sleep(300);
      const t = await sendReq(S4, true, 'đoạn này cho xem cả bức tranh rồi chi tiết khuôn mặt');
      check('the turn is applied as one batch', t?.status === 'applied' && /^batch_\d+$/.test(t.batch || ''), J(t));
      const firstCaption = () => text('.pr-row[data-id="b0005"] .pr-cap');
      check('the row now shows the whole painting first (before the request its first picture was a close-up)', await p.waitFor(`document.querySelector('.pr-row[data-id="b0005"] .pr-cap')?.innerText.trim() === 'Cả bức tranh'`, 30000), await firstCaption());
      check('the card is in plain words with "Hoàn tác"', !!t && /Hoàn tác/.test(await cardText(t.id)) && isVi(await cardText(t.id)), await cardText(t.id));
      await shot('04-step4-request-1280');
      await p.click(`.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-undo`);
      check('the card undoes it and the row goes back as it was', await p.waitFor(`document.querySelector('.prompt-turn-card[data-turn="${t.id}"]')?.dataset.status === 'undone'`, 60000), '');
      await sleep(1500);
      const now = (await api.get(U(S4, '/picks'))).json.picks.beats.b0005 || null;
      check('the picks document is what it was before the request', J(now) === J(line5), J(now) + J(line5));
      check('and the row shows its first picture again', await p.waitFor(`/^Cận cảnh: /.test(document.querySelector('.pr-row[data-id="b0005"] .pr-cap')?.innerText.trim() || '')`, 30000), await firstCaption());
      await clean('step 4 after a request');
    });

    await step('step 4: "+" adds a picture to a line, Escape closes the menu', async () => {
      await p.click('.pr-add[data-id="b0003"]'); await sleep(300);
      const items = await ev(`[...document.querySelectorAll('.pr-menu-item')].map((e) => e.innerText.trim())`);
      check('the menu offers the whole painting, each region and "Tìm hình khác"', items[0] === 'Cả bức tranh' && items.some((x) => /^Cận cảnh: /.test(x)) && /Tìm hình khác/.test(items[items.length - 1]), J(items));
      await p.key('Escape', 'Escape'); await sleep(200);
      check('Escape closes the menu and the focus is back on "+"', !(await exists('.pr-menu')) && (await ev(`document.activeElement?.classList?.contains('pr-add')`)));
      await p.click('.pr-add[data-id="b0003"]'); await sleep(200);
      await p.click('.pr-menu-item', 'Cả bức tranh'); await sleep(1500);
      check('the line shows the picture that was added', /Cả bức tranh/.test(await text('.pr-row[data-id="b0003"]')), await text('.pr-row[data-id="b0003"]'));
      check('and it was saved', ((await api.get(U(S4, '/picks'))).json.picks.beats.b0003?.items || []).length === 1);
      check('the foot of the list says what was added and offers "Hoàn tác"', /Đã thêm "Cả bức tranh" vào đoạn 3/.test(await text('#pk-added')) && (await exists('#pk-added-undo')), await text('#pk-added'));
      await p.click('#pk-added-undo'); await sleep(1500);
      check('"Hoàn tác" takes the picture away again, in the page and in the saved picks', (await ev(`document.querySelectorAll('.pr-row[data-id="b0003"] .pr-pic').length`)) === 0 && ((await api.get(U(S4, '/picks'))).json.picks.beats.b0003?.items || []).length === 0);
      await p.click('.pr-add[data-id="b0003"]'); await sleep(200);
      await p.click('.pr-menu-item', 'Cả bức tranh'); await sleep(1500);
      check('adding it again works (the next steps rely on it)', ((await api.get(U(S4, '/picks'))).json.picks.beats.b0003?.items || []).length === 1);
    });

    await step('step 4: "Tự chọn tay" opens the tools of the line; a search works; Escape goes back', async () => {
      await p.click('.pr-hand[data-id="b0003"]'); await sleep(800);
      check('the hand tools are there for that line: the lines, the line and the tabs', (await ev(`document.querySelector('.pk-root').dataset.mode`)) === 'hand' && /b0003/.test(await text('#pk-mid')) && !!(await ev(`document.querySelector('#pk-left')?.offsetParent`)) && (await exists('#pk-right .tabs')), await text('#pk-mid'));
      check('the way back is a button in plain words', (await text('#pk-back')) === 'Về danh sách đoạn');
      await p.click('#pk-right .tabs button', 'Tìm kiếm'); await sleep(300);
      await ev(`(() => { const q = document.querySelector('#pk-right input[type=search]'); q.value = ''; q.focus(); })()`);
      await p.insert('portrait'); await p.click('#pk-right .pk-searchform button.primary'); 
      check('a search in the sources answers with pictures', await p.waitFor(`document.querySelectorAll('#pk-right .pk-card').length >= 1`, 60000));
      await both('05-step4-hand');
      await p.click('#pk-right .pk-card .pk-cardbtns button.primary'); await sleep(2000);
      check('a picture found is added to the line (the tray of the line shows it)', /hình của dòng này \(2\)/i.test(await text('#pk-mid')), await text('#pk-mid'));
      await ev(`document.activeElement?.blur()`); await p.key('Escape', 'Escape'); await sleep(600);
      check('Escape closes the hand tools and the rows are back, with the new picture', (await ev(`document.querySelector('.pk-root').dataset.mode`)) === 'simple' && (await ev(`document.querySelectorAll('#pk-rows-col .pr-row[data-id="b0003"] .pr-pic').length`)) === 2, await text('.pr-row[data-id="b0003"]'));
    });

    await step('step 4: the three lists of what the project has, each with where it is used', async () => {
      await p.click('.ps-tab', 'Vùng'); await sleep(300);
      const regions = await text('.ps-body');
      check('the regions of the main painting are listed with the lines that use them', /Tấm gương lồi|Khuôn mặt/.test(regions) && /Dùng ở đoạn|Chưa đoạn nào dùng/.test(regions), regions);
      await p.click('.ps-tab', 'Hình bối cảnh'); await sleep(300);
      check('the context pictures are listed', (await ev(`document.querySelectorAll('.ps-body .ps-item').length`)) >= 1, await text('.ps-body'));
      await p.click('.ps-tab', 'Clip'); await sleep(300);
      check('the clips are listed with their length', /giây/.test(await text('.ps-body')) || /Chưa có clip/.test(await text('.ps-body')), await text('.ps-body'));
      await both('06-step4-sections');
      await p.click('.ps-tab', 'Clip'); await sleep(200);
    });

    await step('step 4: the list of changes is one click away and shows the batches of the agent, each with "Hoàn tác"', async () => {
      await ev(`document.querySelector('.prompt-edit[data-box="picks"] .changes-list')?.setAttribute('open', '')`); await sleep(1500);
      const rows = await ev(`[...document.querySelectorAll('.prompt-edit[data-box="picks"] .changes-row')].map((r) => r.innerText)`);
      check('the log has rows with the sentences of the agent\'s writes', rows.length >= 2 && rows.some((t) => /Agent|Gemini/.test(t)), J(rows).slice(0, 300));
      await shot('07-step4-changes-1280');
    });

    await step('step 4: at 1280x720 and 1920x1080 nothing scrolls sideways and the rows, the box and the buttons are on the screen', async () => {
      for (const [w, h] of [[1280, 720], [1920, 1080]]) {
        await p.resize(w, h);
        await go(p, base, `#/project/${S4}/picks`);
        await p.waitFor(`document.querySelectorAll('.pr-row').length === 6 && !!document.querySelector('.prompt-edit[data-box="picks"] .prompt-btn-submit')`, 40000);
        await sleep(800);
        const g = await geometry(['#pk-top', '#pk-auto', '#pk-rows-col', '#pk-box', '#pk-auto-start', '.prompt-edit[data-box="picks"] .prompt-btn-submit', '.prompt-instruction', '#pk-approve', '#pk-sections']);
        const b = g.boxes;
        check(`${w}x${h}: no horizontal scroll bar anywhere`, noSideways(g), J(g.scrollW));
        check(`${w}x${h}: the header, the agent's bar, the rows and the box are on the screen, the rows at least 220 px high`, [b['#pk-top'], b['#pk-auto'], b['#pk-rows-col'], b['#pk-box']].every((x) => inside(x, g)) && b['#pk-rows-col'].h >= 220, J(b));
        check(`${w}x${h}: the agent button, the approval, the field and the send button are on the screen`, [b['#pk-auto-start'], b['#pk-approve'], b['.prompt-instruction'], b['.prompt-edit[data-box="picks"] .prompt-btn-submit']].every((x) => inside(x, g)), J(b));
        check(`${w}x${h}: the lists of the project are on the screen under the rows`, inside(b['#pk-sections'], g) && b['#pk-sections'].y >= b['#pk-rows-col'].y, J(b['#pk-sections']));
      }
      await p.resize(1280, 720);
    });
  }

  // ================================================================================================= step 5
  if (!only || only === 'step5') {
    let shots = [], target = -1, before5 = null;
    await step('step 5: the page opens on the video and the list of shots in plain words', async () => {
      await p.resize(1280, 720);
      await go(p, base, `#/project/${S5}/edit`);
      check('the simple face is showing, with a row for every shot', await p.waitFor(`document.querySelector('.edit-root')?.dataset.mode === 'simple' && !!window.__bti?.store?.draft && document.querySelectorAll('.shot-row').length === window.__bti.store.draft.shots.length`, 60000));
      shots = await ev(`__bti.store.draft.shots.map((s) => ({ id: s.id, t0: s._t0, t1: s._t1, locked: !!s.locked, camera: Object.values(s.params || {}).some((v) => Array.isArray(v) && v.length && v[0]?.at) }))`);
      check('the header says the number of shots and the length', /^\d+ cảnh · \d+:\d\d$/.test(await text('#sb-sum')), await text('#sb-sum'));
      const sentences = await ev(`[...document.querySelectorAll('.sr-sentence')].map((e) => e.innerText)`);
      check('every shot has one sentence, in Vietnamese, with no technique id, shot id or underscore name', sentences.length === shots.length && sentences.every((s) => s.length > 3 && isVi(s) && !RAW.test(s)), J(sentences.filter((s) => !isVi(s) || RAW.test(s)).slice(0, 8)));
      check('the player is the same as in the editor: the stage, the frame and the transport are there', (await exists('#stage-box #frame')) && (await exists('#transport #t-play')));
      check('the timeline, the inspector and the tool buttons of the editor are not on the screen', !(await ev(`!!document.querySelector('#timeline-wrap')?.offsetParent || !!document.querySelector('#inspector')?.offsetParent || !!document.querySelector('#ebar')?.offsetParent`)));
      check('no id or file name is visible anywhere on the page', !RAW.test((await ev(`[...document.querySelectorAll('#sbar, #shots-col, #sel-panel, #transport')].map((e) => e.innerText).join(' ')`)).replace(/\bs\d{4}\b\s*\|[^\n]*/g, '')), '');
      await clean('step 5 at rest');
      await both('09-step5-simple');
    });

    await step('step 5: the preview keeps at least 300 px of height at 1280x720, and nothing scrolls sideways at the two sizes', async () => {
      for (const [w, h] of [[1280, 720], [1920, 1080]]) {
        await p.resize(w, h); await sleep(900);
        const g = await geometry(['#stage', '#stage-box', '#shots-col', '#prompt-edit-container', '#sbar', '#sel-panel', '#sb-hand']);
        const b = g.boxes;
        check(`${w}x${h}: no horizontal scroll bar`, noSideways(g), J(g.scrollW));
        check(`${w}x${h}: the header, the player, the list, the box and the button "Chỉnh tay" are on the screen`, ['#sbar', '#stage', '#shots-col', '#prompt-edit-container', '#sb-hand'].every((s) => inside(b[s], g)), J(b));
        if (w === 1280) check('1280x720: the preview keeps at least 300 px of height', b['#stage'].h >= 300 && b['#stage-box'].h >= 280, J([b['#stage'], b['#stage-box']]));
        check(`${w}x${h}: the three zones sit side by side: player, list, box`, b['#stage'].r <= b['#shots-col'].x + 1 && b['#shots-col'].r <= b['#prompt-edit-container'].x + 1, J(b));
      }
      await p.resize(1280, 720);
    });

    await step('step 5: clicking a row selects it and moves the player there; Ctrl and Shift select several; a chapter header a whole chapter', async () => {
      const k = Math.min(4, shots.length - 1);
      await p.click(`.shot-row[data-id="${shots[k].id}"]`); await sleep(500);
      const t = await ev(`__bti.ctx.t`);
      check('the player is inside that shot', t >= shots[k].t0 - 0.02 && t < shots[k].t1 + 0.02, `${t} ${shots[k].t0} ${shots[k].t1}`);
      check('the row is marked as selected and the box says "Cảnh N đang chọn"', (await exists(`.shot-row.sel[data-id="${shots[k].id}"]`)) && new RegExp(`Cảnh ${k + 1} đang chọn`).test(await text('.prompt-scope-words')), await text('.prompt-scope-words'));
      check('under the player the shot is described in words', (await text('#sel-panel')).includes(await text(`.shot-row[data-id="${shots[k].id}"] .sr-sentence`)), await text('#sel-panel'));
      await clickMod(`.shot-row[data-id="${shots[k + 2]?.id || shots[k].id}"]`, CTRL);
      check('Ctrl adds a shot', new RegExp(`2 cảnh đang chọn \\(${k + 1}, ${k + 3}\\)`).test(await text('.prompt-scope-words')), await text('.prompt-scope-words'));
      await p.click(`.shot-row[data-id="${shots[0].id}"]`); await sleep(200);
      await clickMod(`.shot-row[data-id="${shots[Math.min(3, shots.length - 1)].id}"]`, SHIFT);
      check('Shift selects the run', /4 cảnh đang chọn \(1, 2, 3, 4\)/.test(await text('.prompt-scope-words')), await text('.prompt-scope-words'));
      const chapters = await ev(`document.querySelectorAll('.chap-head').length`);
      if (chapters) {
        await p.click('.chap-sel');
        check('"Chọn cả chương" selects the whole chapter and the box says "Chương"', /Chương/.test(await text('.prompt-scope-words')) && (await ev(`document.querySelectorAll('.shot-row.sel').length`)) >= 1, await text('.prompt-scope-words'));
        await p.click('.chap-toggle'); await sleep(300);
        check('a chapter can be folded and opened again', (await ev(`!!document.querySelector('.chap-rows[hidden]')`)));
        await p.click('.chap-toggle'); await sleep(300);
      }
      await both('10-step5-selected');
    });

    await step('step 5: a request changes a shot, its card shows the sentences and the frames, and "Hoàn tác" puts it back', async () => {
      target = shots.findIndex((s) => s.camera && !s.locked);
      check('the test project has a shot with a camera move to slow down', target >= 0, String(target));
      before5 = (await api.get(U(S5))).json;
      await p.click(`.shot-row[data-id="${shots[target].id}"]`); await sleep(400);
      await p.key('/', 'Slash'); await sleep(100);
      const t = await sendReq(S5, false, 'làm chậm cú zoom ở cảnh này', ['applied', 'failed', 'no_change']);
      check('the turn is applied as one batch', t?.status === 'applied' && /^batch_\d+$/.test(t.batch || ''), J(t));
      const card = await cardText(t.id);
      check('the card says what changed in words, who did it, and has "Xem thử" and "Hoàn tác"', /Máy quay ở cảnh này đi chậm hơn/.test(card) && /Hoàn tác/.test(card) && /Xem thử/.test(card) && isVi(card), card);
      check('the frames before and after are loaded', await p.waitFor(`document.querySelectorAll('.prompt-turn-card[data-turn="${t.id}"] .prompt-frame img').length === 2 && [...document.querySelectorAll('.prompt-turn-card[data-turn="${t.id}"] .prompt-frame img')].every((i) => i.complete && i.naturalWidth > 0)`, 60000));
      check('the page took the new storyboard in and the same shot is still selected', (await ev(`!__bti.store.dirty`)) && (await exists(`.shot-row.sel[data-id="${shots[target].id}"]`)));
      await shot('11-step5-card-1280');
      await clean('step 5 after a request');
      await p.click(`.prompt-turn-card[data-turn="${t.id}"] .prompt-btn-undo`);
      check('the card undoes it', await p.waitFor(`document.querySelector('.prompt-turn-card[data-turn="${t.id}"]')?.dataset.status === 'undone'`, 60000));
      await sleep(1500);
      const now = (await api.get(U(S5))).json;
      check('the storyboard is exactly as before the request', J(strip(now.storyboard.shots)) === J(strip(before5.storyboard.shots)));
    });

    let pickedShot = null;
    await step('step 5: "Chỉnh tay" shows the editor as it is, and the way back keeps the selection', async () => {
      pickedShot = shots[Math.min(2, shots.length - 1)].id;
      await p.click(`.shot-row[data-id="${pickedShot}"]`); await sleep(400);
      await p.click('#sb-hand'); await sleep(900);
      check('the editor is there: the tool buttons, the timeline with a size, the inspector', (await ev(`document.querySelector('.edit-root').dataset.mode`)) === 'hand' && (await ev(`!!document.querySelector('#ebar')?.offsetParent && !!document.querySelector('#inspector')?.offsetParent && window.__tl.W > 0 && document.querySelector('#tl-canvas').width > 0`)));
      check('the timeline was fitted (it draws the shots)', (await ev(`Number.isFinite(window.__tl.view.t0) && window.__tl.view.pps > 0`)));
      check('the selection is the same shot', (await ev(`__bti.store.sel.shot`)) === pickedShot, await ev(`__bti.store.sel.shot`));
      check('the page remembers the choice for this project', (await ev(`localStorage.getItem('bti.edit.mode.${S5}')`)) === 'hand');
      check('the preview still keeps 300 px at 1280x720 (as before)', (await ev(`document.querySelector('#stage').clientHeight`)) >= 300);
      await both('12-step5-hand');
      await p.eval(`location.reload()`); await sleep(1500);
      check('after a reload the editor is still the face that opens', await p.waitFor(`document.querySelector('.edit-root')?.dataset.mode === 'hand' && !!window.__bti?.store?.draft`, 60000));
      await p.click('#btn-simple'); await sleep(700);
      check('the button back shows the list again with the same shot selected', (await ev(`document.querySelector('.edit-root').dataset.mode`)) === 'simple' && (await exists(`.shot-row.sel[data-id="${await ev(`__bti.store.sel.shot`)}"]`)));
      check('and the choice is remembered again', (await ev(`localStorage.getItem('bti.edit.mode.${S5}')`)) === 'simple');
      await p.eval(`location.reload()`); await sleep(1500);
      check('after a reload the list is what opens', await p.waitFor(`document.querySelector('.edit-root')?.dataset.mode === 'simple' && document.querySelectorAll('.shot-row').length > 0`, 60000));
    });

    await step('step 5: a link that needs the editor (?select=) opens it there', async () => {
      await p.send('Page.navigate', { url: `${base}/?select=${shots[1]?.id || shots[0].id}#/project/${S5}/edit` });
      check('the editor opens with that shot selected', await p.waitFor(`document.querySelector('.edit-root')?.dataset.mode === 'hand' && window.__bti?.store?.sel?.shot === ${J(shots[1]?.id || shots[0].id)}`, 60000));
      await p.send('Page.navigate', { url: `${base}/#/` }); await sleep(800);
    });

    await step('step 5: a shot with a problem is counted, found, and explained in words; the editor is one click away', async () => {
      const orig = (await api.get(U(S5))).json;
      const sb = strip(orig.storyboard);
      const i = shots.findIndex((s) => s.camera && !s.locked);
      const bad = JSON.parse(J(sb)); bad.shots[i].slots = {};
      const put = await api.put(U(S5, '/storyboard'), { storyboard: bad, base_rev: orig.rev });
      check('a shot without its picture can be saved (an unfinished shot is not an invalid one)', put.status === 200, put.text.slice(0, 200));
      await go(p, base, `#/project/${S5}/edit`);
      await p.waitFor(`document.querySelector('.edit-root')?.dataset.mode === 'simple' && !!document.querySelector('#sb-problems')`, 60000);
      check('the header says "1 cảnh cần sửa"', /^1 cảnh cần sửa$/.test(await text('#sb-problems')), await text('#sb-problems'));
      await p.click('#sb-problems'); await sleep(500);
      check('it jumps to that shot and selects it', (await exists(`.shot-row.sel[data-id="${shots[i].id}"]`)));
      check('the row and the panel under the player say it in a Vietnamese sentence with no id', /còn thiếu một hình hoặc một thông tin bắt buộc/.test(await text(`.shot-row[data-id="${shots[i].id}"]`)) && /Cảnh \d+: còn thiếu/.test(await text('#sel-panel')) && !RAW.test((await text('#sel-panel')).replace(/\bs\d{4}\b/g, '')), await text('#sel-panel'));
      check('the player says in words that this shot cannot be drawn, with no technique id on it', await p.waitFor(`!!document.querySelector('.stage-note:not([hidden])')`, 20000) && /Cảnh \d+ chưa vẽ được: còn thiếu/.test(await text('.stage-note')) && !RAW.test(await text('.stage-note')), await text('.stage-note'));
      check('"Duyệt" tells what is missing instead of approving', /cảnh cần sửa nên chưa duyệt được/.test(await text('#sb-why')), await text('#sb-why'));
      await both('13-step5-problem');
      await p.click('#sb-approve'); await sleep(600);
      check('pressing it opens the list of problems in words, with "Xem" and "Sửa ở Chỉnh tay"', (await exists('.prob-dialog')) && /Cảnh \d+: còn thiếu/.test(await text('.prob-dialog')) && /Sửa ở Chỉnh tay/.test(await text('.prob-dialog')), await text('.prob-dialog'));
      await p.click('.prob-dialog button', 'Sửa ở Chỉnh tay'); await sleep(900);
      check('"Sửa ở Chỉnh tay" opens the editor on that shot', (await ev(`document.querySelector('.edit-root').dataset.mode`)) === 'hand' && (await ev(`__bti.store.sel.shot`)) === shots[i].id);
      const now = (await api.get(U(S5))).json;
      const back = await api.put(U(S5, '/storyboard'), { storyboard: sb, base_rev: now.rev });
      check('the storyboard is put back as it was', back.status === 200, back.text.slice(0, 200));
      await p.click('#btn-simple'); await sleep(400);
    });
  }
  check('no failed request in the pages (apart from the refusals the checks provoked)', p.bad().filter((x) => !/\/picks\/auto|longjobs|\/frame|thumb|\/suggestions|\/waveform|\/t\/[^/]+$/.test(x)).length === 0, J(p.bad()));
} finally {
  const n = finish();
  await closeAll();
  process.exit(n);
}
