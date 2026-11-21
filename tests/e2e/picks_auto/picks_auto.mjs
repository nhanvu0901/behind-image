// Browser check of "Để agent chọn hình" on the pictures page (step 4): press the button, see the progress with its limits, cancel, run again, see the
// result sentence and the lines filled with the agent's reasons, press "Chọn lại phần còn thiếu", reload, change a note, a failing agent. Then (worker join2)
// the page as one: the grid has a place for the agent's bar AND the prompt box at 1280x720 and 1920x1080 with no horizontal scroll bar, and the joined path:
// a request of the prompt box that needs a picture the project does not have ends as "Cần làm kỹ hơn", its card hands the same line to the pictures agent
// ("Để agent chọn hình"), follows the job to its result, the line gets its picture, and a prompt-box turn is refused while the agent works.
// Runs against a second instance of the app on the server (tests/e2e/picks_auto/launch_picks_auto.py wrapping tests/e2e/stages/launch.py:
// BTI_NO_REAL_MODELS=1, its own port 8577 and folder suffix `c3p`, data copied to a temp folder, the two agents are MOCK agents carrying the names of the real two,
// the agent in a work folder is a fake runner, the picture sources are fakes; no agy, no claude, no network) through an ssh tunnel, with headless Chrome on the Mac.
//   BTI_SSH_HOST=winbox-cmd node tests/e2e/picks_auto/picks_auto.mjs [--keep-server]
// One PASS or FAIL line per check, exit code = number failing. Screenshots: .scratch/stages_ui/shots/picks_auto-*.png. The instance is stopped at the end.
process.env.BTI_STAGES_LAUNCH = 'tests\\e2e\\picks_auto\\launch_picks_auto.py';              // before remote.mjs is loaded: it reads these once
process.env.BTI_STAGES_SUFFIX = process.env.BTI_STAGES_SUFFIX || 'c3p';
process.env.BTI_STAGES_PORT = process.env.BTI_STAGES_PORT || '8577';
const { up, down, readState } = await import('../stages/remote.mjs');
const { openBrowser, makeApi, check, finish, go, sleep, REPO, bodyText, rawLooking, leftovers, clickExact, snap } = await import('../stages/common.mjs');

const keep = process.argv.includes('--keep-server');
if (readState()) await down();                                                    // never reuse an instance that does not carry the fakes
const st = await up({ doDeploy: true });
const base = st.base, api = makeApi(base);
const br = await openBrowser();
const p = await br.newPage();
let closed = false;
const closeAll = async () => { if (closed) return; closed = true; try { br.close(); } catch {} if (!keep) { try { await down(); } catch {} } };
process.on('exit', () => { try { br.close(); } catch {} });
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, async () => { await closeAll(); process.exit(130); });
process.on('uncaughtException', async (e) => { console.error(e); await closeAll(); process.exit(99); });

const PID = 'picks-demo';
const U = (tail = '') => `/api/projects/${PID}${tail}`;
const ev = (x) => p.eval(x);
const J = JSON.stringify;
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} ran to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const shot = (name) => snap(p, `picks_auto-${name}`);
const clean = async (what) => { const t = await bodyText(p); check(`${what}: no leftovers, no raw words`, !(await leftovers(p)).length && !rawLooking(t).length, J(await leftovers(p)) + J(rawLooking(t))); };
const text = (sel) => ev(`document.querySelector(${J(sel)})?.innerText?.replace(/\\s+/g, ' ').trim() || ''`);
const exists = (sel) => ev(`!!document.querySelector(${J(sel)})`);
const sentence = () => text('#pk-auto-sentence');
const barState = () => ev(`document.querySelector('#pk-auto .pk-auto-bar')?.dataset.state || ''`);
const sleepUntil = async (fn, ms = 90000, every = 300) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = await fn(); if (v) return v; await sleep(every); } return null; };
const calls = async () => (await api.post('/api/_e2e/picks_auto_calls', {})).json;
const switchAgent = (body) => api.put('/api/_e2e/picks_auto', body);
const picksDoc = async () => (await api.get(U('/picks'))).json;
const picksDoc2 = async () => (await api.get(`/api/projects/picks-join/picks`)).json;
const pickRow = (id) => ev(`(() => { const b = Array.from(document.querySelectorAll('#pk-left .pk-beat')).find((e) => e.querySelector('.bid')?.textContent === ${J(id)}); if (!b) return null; return { count: b.querySelector('.count')?.textContent || '', tag: b.querySelector('.tag')?.textContent || '' }; })()`);
const openLine = async (id) => { await p.click('#pk-left .pk-beat', id); await sleep(250); };
const whyOfLine = () => text('#pk-mid .pk-agentwhy');
const trayItems = () => ev(`Array.from(document.querySelectorAll('#pk-mid .pk-tray .pk-item')).map((i) => ({ title: i.querySelector('.pk-itemtitle')?.innerText || '', region: i.querySelector('select')?.value || '' }))`);

try {
  await p.resize(1700, 1000);
  await step('the bar before anything is done', async () => {
    const put = await api.put('/api/settings/agent', { agent: 'gemini' });                   // what the settings box does: projects start on Gemini 3.8 Flash
    check('the machine default is Gemini 3.8 Flash (the mock agent carrying that name)', put.status === 200 && put.json.machine_default === 'gemini', put.text);
    check('the instance carries the demo project and the fakes', (await api.get('/api/projects')).status === 200 && (await api.get(U('/picks/auto'))).status === 200);
    await go(p, base, `#/project/${PID}/picks`);
    check('the bar is on the page, with the agent select of the step and the button', await p.waitFor(`!!document.querySelector('#pk-auto #pk-auto-start') && !!document.querySelector('#pk-auto .agent-pick select')`, 30000));
    await p.waitFor(`document.querySelector('#pk-auto .agent-pick select')?.options.length >= 2 && !document.querySelector('#pk-auto .agent-pick select').disabled`, 30000);
    const sel = await ev(`(() => { const s = document.querySelector('#pk-auto .agent-pick select'); return { value: s.value, options: [...s.options].map((o) => o.textContent), step: document.querySelector('#pk-auto .agent-pick').dataset.agentStep }; })()`);
    check('the select offers the two agents of the step "picks" and shows Gemini 3.8 Flash', J(sel.options) === J(['Gemini 3.8 Flash', 'Opus 5.5 High']) && sel.value === 'gemini' && sel.step === 'picks', J(sel));
    const btn = await ev(`(() => { const b = document.querySelector('#pk-auto-start'); return { text: b.textContent.trim(), disabled: b.disabled }; })()`);
    check('the button says "Để agent chọn hình" and can be pressed', btn.text === 'Để agent chọn hình' && !btn.disabled, J(btn));
    check('"Chọn lại phần còn thiếu" is not there before a run, and the intro says the agent never approves', !(await exists('#pk-auto-again')) && /không bao giờ tự duyệt/.test(await text('#pk-auto')) && (await barState()) === 'idle', await text('#pk-auto'));
    const rows = [await pickRow('b0001'), await pickRow('b0006')];
    check('the six lines are there with no pictures', rows.every((r) => r && r.count === '0') && (await ev(`document.querySelectorAll('#pk-left .pk-beat').length`)) === 6, J(rows));
    await clean('the bar at rest');
    await shot('01-before');
  });

  await step('a run shows its progress with the limits and a cancel button; cancelling keeps nothing', async () => {
    await switchAgent({ slow: true, reset: true });
    await p.click('#pk-auto-start');
    check('while it runs the state is "running", the button and the select are locked, "Dừng" is there', await p.waitFor(`document.querySelector('#pk-auto .pk-auto-bar')?.dataset.state === 'running' && !!document.querySelector('#pk-auto-cancel')`, 30000)
      && await ev(`document.querySelector('#pk-auto-start').disabled && document.querySelector('#pk-auto .agent-pick select').disabled`));
    const line = await sleepUntil(async () => { const t = await text('#pk-auto-line'); return /bước \d+\/80, \d+\/20 phút/.test(t) ? t : null; }, 40000);
    check('the progress line names the part (1/4) and shows the steps and the minutes against their limits', /^Lập danh sách hình cần tìm \(1\/4\) - Agent đang lập danh sách hình: bước \d+\/80, \d+\/20 phút\.$/.test(line || ''), line);
    check('the line "mỗi lượt tối đa 20 phút và 80 bước" is there', /tối đa 20 phút và 80 bước/.test(await text('#pk-auto')), await text('#pk-auto'));
    check('a progress bar is drawn', (await exists('#pk-auto progress')));
    check('the other buttons that start a job are not offered meanwhile (the agent is working)', (await ev(`document.querySelector('#pk-auto-start').title`)) === 'Agent đang làm việc.');
    await shot('02-running');
    await clean('the bar while it runs');
    await p.click('#pk-auto-cancel');
    check('after "Dừng" the bar says so and the button is back', await p.waitFor(`document.querySelector('#pk-auto .pk-auto-bar')?.dataset.state !== 'running' && /Đã dừng/.test(document.querySelector('#pk-auto')?.innerText || '')`, 40000)
      && await ev(`!document.querySelector('#pk-auto-start').disabled`), await text('#pk-auto'));
    const d = await picksDoc();
    check('nothing was written to the picks', J(d.picks.beats) === '{}' && d.approved === false, J(d.picks.beats).slice(0, 200));
    const jobs = (await api.get(U('/longjobs?kind=picks'))).json.items;
    check('the job is recorded as cancelled', jobs[0]?.state === 'cancelled' && jobs[0]?.meta?.action === 'auto', J(jobs[0]?.state));
    await shot('03-cancelled');
  });

  await step('a run to the end: the result sentence, the lines filled with reasons, what could not be found', async () => {
    await switchAgent({ slow: false, reset: true });
    await p.click('#pk-auto-start');
    const seen = new Set();
    const t0 = Date.now();
    while (Date.now() - t0 < 120000) {
      const t = await text('#pk-auto-line');
      const m = /\((\d)\/4\)/.exec(t); if (m) seen.add(m[1]);
      if ((await barState()) === 'result') break;
      await sleep(250);
    }
    check('the progress went through the parts of the design (at least the first one was seen), then the result', seen.has('1') && (await barState()) === 'result', J([...seen]));
    check('the result is one sentence: 5 of 6 lines, 1 without a fitting picture', (await sentence()) === 'Agent đã chọn hình cho 5/6 đoạn. 1 đoạn chưa có hình phù hợp.', await sentence());
    const detail = await text('#pk-auto .pk-auto-result .hint');
    check('the second line says what was made (2 new pictures, 2 regions, 1 line that needs nothing new)', /hình mới/.test(detail) && /vùng chi tiết/.test(detail) && /1 đoạn dùng lại hình trước/.test(detail), detail);
    check('"Chọn lại phần còn thiếu" is offered', await exists('#pk-auto-again'));
    await p.click('#pk-auto .pk-auto-without summary');
    const li = await text('#pk-auto .pk-auto-without li');
    check('the line without a picture is named with the plain reason', /^Đoạn 3: Không tìm thấy hình nào cho "Tro núi lửa Krakatoa" ở các nguồn miễn phí\.$/.test(li), li);
    await shot('04-result');
    await clean('the result');
    const rows = [];
    for (const id of ['b0001', 'b0002', 'b0003', 'b0004', 'b0005', 'b0006']) rows.push([id, (await pickRow(id))?.count, (await pickRow(id))?.tag]);
    check('the lines show their pictures: 1, 1, 0, 2, 2 and the last one "bỏ qua" (nothing new)', J(rows) === J([['b0001', '1', ''], ['b0002', '1', ''], ['b0003', '0', ''], ['b0004', '2', ''], ['b0005', '2', ''], ['b0006', '', 'bỏ qua']]), J(rows));
    await openLine('b0001');
    check('line 1 shows the whole painting with the agent\'s reason under it', (await whyOfLine()) === 'Agent: Mở bằng cả bức tranh để người xem thấy cả căn phòng.' && (await trayItems()).length === 1, await whyOfLine());
    await openLine('b0002');
    const t2 = await trayItems();
    check('line 2 shows the region MIRROR of the main painting and its reason', t2.length === 1 && t2[0].region === 'MIRROR' && /tấm gương/.test(await whyOfLine()), J(t2) + await whyOfLine());
    await shot('05-line2');
    await openLine('b0003');
    check('line 3 has no picture and no reason (it was left as it was)', (await trayItems()).length === 0 && !(await exists('#pk-mid .pk-agentwhy')));
    await openLine('b0004');
    const t4 = await trayItems();
    check('line 4 shows a map and a video clip, and its reason', t4.length === 2 && /Bản đồ Bruges/.test(t4[0].title) && /VIDEO/.test(t4[1].title) && /vị trí/.test(await whyOfLine()), J(t4) + await whyOfLine());
    await openLine('b0006');
    check('line 6 needs nothing new: skipped, with its reason', /bỏ qua/.test(await text('#pk-mid')) && /Vẫn cùng ý/.test(await whyOfLine()), await whyOfLine());
    const d = await picksDoc();
    check('the picks are not approved: the owner stays the one who approves', d.approved === false && (await text('#pk-approve')) === 'Duyệt chọn hình', await text('#pk-approve'));
    const ch = (await api.get(U('/changes?doc=picks&limit=50'))).json.changes;
    check('every write is a batch of the change log with the agent as actor', ch.length >= 2 && ch.every((c) => c.actor === 'agent:mock' && /^Agent chọn hình/.test(c.note)), J(ch.map((c) => [c.actor, c.note])));
    const c = await calls();
    check('the fake agent was asked twice for this run: plan, then choose', J(c.calls.slice(-2).map((x) => x.mode)) === J(['plan', 'choose']), J(c.calls));
  });

  await step('"Chọn lại phần còn thiếu" starts the job for the lines without pictures', async () => {
    await p.click('#pk-auto-again');
    await p.waitFor(`document.querySelector('#pk-auto .pk-auto-bar')?.dataset.state === 'running'`, 30000);
    check('it runs (the state says so)', true);
    check('and ends with a sentence about the one line it worked on', await p.waitFor(`document.querySelector('#pk-auto-sentence')?.innerText === 'Agent đã chọn hình cho 1/1 đoạn.'`, 120000), await sentence());
    check('the button is gone: no line is missing any more', !(await exists('#pk-auto-again')));
    const rows = [await pickRow('b0003')];
    check('line 3 now has its picture', rows[0].count === '1', J(rows));
    await openLine('b0003');
    check('the picture is the portrait the source found', /Chân dung/.test((await trayItems())[0]?.title || ''), J(await trayItems()));
    check('and the reason', /^Agent: Nói về họa sĩ/.test(await whyOfLine()), await whyOfLine());
    const c = await calls();
    check('a second plan and choice were made, for ONE line only (the others were not asked again)', J(c.calls.map((x) => x.mode)) === J(['plan', 'choose', 'plan', 'choose']) && c.plans === 2, J(c));
    await shot('06-again');
    await clean('after the second run');
  });

  await step('a reload keeps the result and the reasons; the owner changing a note ends the agent\'s tag on that line', async () => {
    await go(p, base, `#/project/${PID}/picks`);
    check('after a reload the last result is still there', await p.waitFor(`document.querySelector('#pk-auto-sentence')?.innerText === 'Agent đã chọn hình cho 1/1 đoạn.'`, 30000), await sentence());
    await openLine('b0001');
    check('and the reasons under the lines', /^Agent: Mở bằng cả bức tranh/.test(await whyOfLine()), await whyOfLine());
    await p.focus('#pk-mid input[placeholder^="Ghi chú cho dòng này"]');
    await p.key('End', 'End');
    await p.insert(' (bạn sửa)');
    await sleep(1500);
    check('once the owner changes the note, the line is no longer shown as the agent\'s', !(await exists('#pk-mid .pk-agentwhy')), await text('#pk-mid'));
    const d = await picksDoc();
    check('and the note was saved', /\(bạn sửa\)$/.test(d.picks.beats.b0001.note), d.picks.beats.b0001.note);
  });

  await step('every line has pictures: starting again asks first; a failing agent says so in plain words and changes nothing', async () => {
    await go(p, base, `#/project/${PID}/picks`);
    await p.waitFor(`!!document.querySelector('#pk-auto-start') && !document.querySelector('#pk-auto-start').disabled`, 30000);
    const before = await picksDoc();
    await p.click('#pk-auto-start');
    check('a dialog asks whether to choose everything again (it replaces the pictures)', await p.waitFor(`!!document.querySelector('.modal') && /Chọn lại tất cả/.test(document.querySelector('.modal')?.innerText || '')`, 10000), await text('.modal'));
    await clickExact(p, 'Hủy');
    await sleep(800);
    check('declining starts nothing', (await ev(`!document.querySelector('.modal')`)) && (await api.get(U('/longjobs?kind=picks'))).json.items.filter((j) => j.state === 'running').length === 0 && J((await picksDoc()).picks) === J(before.picks));
    await switchAgent({ fail: true, reset: true });
    await p.click('#pk-auto-start');
    await p.waitFor(`!!document.querySelector('.modal')`, 10000);
    await p.click('.modal footer .primary');
    check('a file that fails the check twice ends with the plain sentence, no raw error', await p.waitFor(`/Agent chưa chọn xong: Agent không viết được tệp kết quả dùng được/.test(document.querySelector('#pk-auto')?.innerText || '')`, 120000), await text('#pk-auto'));
    const after = await picksDoc();
    check('the pictures of the owner and of the earlier run are untouched', J(after.picks.beats) === J(before.picks.beats), '');
    await shot('07-failed');
    await clean('after a failed run');
    await switchAgent({ fail: false });
  });


  // ------------------------------------------------------------------------------------------------- join2: one page for the bar and the box
  const JOIN = 'picks-join';
  const UJ = (tail = '') => `/api/projects/${JOIN}${tail}`;
  const joinThread = async () => (await api.get(UJ('/picks/edit/thread'))).json;
  const joinCard = (id, sel = '') => `.prompt-turn-card[data-turn="${id}"] ${sel}`.trim();
  const geometry = () => ev(`(() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), r: Math.round(b.right), b: Math.round(b.bottom), w: Math.round(b.width), h: Math.round(b.height) }; };
    const root = document.querySelector('.pk-root'); const scroller = [document.scrollingElement, document.body, root, document.querySelector('main'), document.querySelector('#view'), ...['#pk-top', '#pk-auto', '#pk-left', '#pk-mid', '#pk-right', '#pk-box'].map((s) => document.querySelector(s))].filter(Boolean);        // the page AND each column: none of them has a horizontal scroll bar
    return { iw: innerWidth, ih: innerHeight, scrollW: scroller.map((e) => [e.scrollWidth, e.clientWidth]), top: r('#pk-top'), bar: r('#pk-auto'), body: r('#pk-body'), left: r('#pk-left'), mid: r('#pk-mid'), right: r('#pk-right'), box: r('#pk-box'),
      start: r('#pk-auto-start'), send: r('.prompt-edit[data-box="picks"] .prompt-btn-submit'), ta: r('.prompt-instruction') }; })()`);
  const noSideways = (g) => g.scrollW.every(([sw, cw]) => sw <= cw + 1);
  const inside = (b, g) => !!b && b.x >= 0 && b.y >= 0 && b.r <= g.iw + 1 && b.b <= g.ih + 1 && b.w > 0 && b.h > 0;

  await step('the page has a place for the agent\'s bar and for the prompt box at 1280x720 and at 1920x1080, with no horizontal scroll bar', async () => {
    for (const [w, h] of [[1280, 720], [1920, 1080]]) {
      await p.resize(w, h);
      await go(p, base, `#/project/${JOIN}/picks`);
      await p.waitFor(`!!document.querySelector('#pk-auto #pk-auto-start') && !!document.querySelector('.prompt-edit[data-box="picks"] .prompt-btn-submit') && document.querySelectorAll('#pk-left .pk-beat').length === 6`, 40000);
      await sleep(800);
      const g = await geometry();
      check(`${w}x${h}: no horizontal scroll bar anywhere on the page`, noSideways(g), J(g.scrollW));
      check(`${w}x${h}: the top bar and the agent's bar are on the screen, one above the other, with the button`, inside(g.top, g) && inside(g.bar, g) && g.bar.y >= g.top.b - 1 && inside(g.start, g) && g.bar.b <= g.body.y + 1, J([g.top, g.bar, g.start, g.body]));
      check(`${w}x${h}: the four columns each have room (lines, line, search, prompt box) and the box with its field and its send button is on the screen`,
        [g.left, g.mid, g.right, g.box].every((b) => inside(b, g) && b.w >= 220 && b.h >= 150) && inside(g.ta, g) && inside(g.send, g) && g.left.r <= g.mid.x + 1 && g.mid.r <= g.right.x + 1 && g.right.r <= g.box.x + 1, J([g.left, g.mid, g.right, g.box, g.ta, g.send]));
      check(`${w}x${h}: the columns end above the bottom of the screen (they scroll inside, the page does not)`, g.body.b <= g.ih + 1 && g.box.b <= g.ih + 1, J([g.body, g.box, g.ih]));
      await shot(`08-layout-${w}x${h}`);
    }
    await p.resize(1700, 1000);
  });

  let esc = null;
  await step('join: a request of the box that needs a picture the project does not have ends as "Cần làm kỹ hơn" and offers the pictures agent first', async () => {
    await switchAgent({ slow: false, reset: true });
    await go(p, base, `#/project/${JOIN}/picks`);
    await p.waitFor(`document.querySelectorAll('#pk-left .pk-beat').length === 6 && !!document.querySelector('.prompt-edit[data-box="picks"]')`, 40000);
    await p.click('#pk-left .pk-beat', 'b0004'); await sleep(500);
    check('the scope line of the box says the line that was clicked', /Đoạn 4 đang chọn/.test(await text('.prompt-edit[data-box="picks"] .prompt-scope-words')), await text('.prompt-edit[data-box="picks"] .prompt-scope-words'));
    const before = (await joinThread()).turns.map((t) => t.id);
    await p.waitFor(`!document.querySelector('.prompt-edit[data-box="picks"] .prompt-instruction').disabled`, 30000);
    await ev(`(() => { const t = document.querySelector('.prompt-edit[data-box="picks"] .prompt-instruction'); t.value = ''; t.focus(); })()`);
    await p.insert('thêm một tấm bản đồ Bruges cho dòng này'); await sleep(150);
    await p.click('.prompt-edit[data-box="picks"] .prompt-btn-submit');
    esc = await sleepUntil(async () => (await joinThread()).turns.find((t) => !before.includes(t.id) && t.status !== 'running'), 90000);
    check('the turn ends as "escalate": nothing written, the reason is a Vietnamese sentence', esc?.status === 'escalate' && /bản đồ/.test(esc.reason) && J((await picksDoc2()).picks.beats) === '{}', J(esc));
    await p.waitFor(`document.querySelector(${J(joinCard(esc?.id || 'x'))})?.dataset.status === 'escalate'`, 30000);
    const card = await text(joinCard(esc.id));
    check('the card says "Cần làm kỹ hơn", what is missing, and that the agent that chooses pictures can do it', /Cần làm kỹ hơn/.test(card) && /bản đồ/.test(card) && /agent chọn hình/i.test(card), card);
    const btns = await ev(`Array.from(document.querySelectorAll(${J(joinCard(esc.id, '.prompt-turn-actions button'))})).map((b) => ({ cls: b.className, text: b.textContent.trim(), title: b.title, disabled: b.disabled }))`);
    check('the first button is "Để agent chọn hình" (primary, it takes minutes) and the second is "Tìm hình bằng tay"', btns.length === 2 && btns[0].text === 'Để agent chọn hình' && /primary/.test(btns[0].cls) && /vài phút/.test(btns[0].title) && !btns[0].disabled && btns[1].text === 'Tìm hình bằng tay', J(btns));
    await shot('09-join-escalate');
    await clean('the escalated card');
  });

  await step('join: the button hands the line to the pictures agent; the card and the bar follow the same job; a box turn is refused meanwhile, in Vietnamese', async () => {
    await switchAgent({ slow: true, reset: true });
    await p.click(joinCard(esc.id, '.prompt-btn-agent'));
    check('the card turns into a running one, with "Dừng" and the sentence that it takes minutes', await p.waitFor(`document.querySelector(${J(joinCard(esc.id))})?.dataset.status === 'running' && !!document.querySelector(${J(joinCard(esc.id, '.prompt-btn-cancel'))})`, 30000)
      && /vài phút/.test(await text(joinCard(esc.id))), await text(joinCard(esc.id)));
    const t = (await joinThread()).turns.find((x) => x.id === esc.id);
    check('the turn is on the job of the agent: path "agent", the lines of the request, the agent\'s own job', t?.path === 'agent' && t.escalated === true && !!t.job_id && J(t.scope.beats) === J(['b0004']), J(t));
    const line = await sleepUntil(async () => { const x = await text(joinCard(esc.id, '.prompt-run-line')); return /\(1\/4\)/.test(x) ? x : null; }, 40000);
    check('the card names the part of the agent\'s job (1/4)', /^Lập danh sách hình cần tìm \(1\/4\)/.test(line || ''), line);
    check('the bar of the page shows the same job at once, locked, with "Dừng"', await p.waitFor(`document.querySelector('#pk-auto .pk-auto-bar')?.dataset.state === 'running' && !!document.querySelector('#pk-auto-cancel')`, 30000), await text('#pk-auto'));
    check('the send button and the field of the box are locked while it works', await ev(`document.querySelector('.prompt-edit[data-box="picks"] .prompt-btn-submit').disabled && document.querySelector('.prompt-edit[data-box="picks"] .prompt-instruction').disabled`));
    const job = (await api.get(`/api/longjobs/${t.job_id}`)).json;
    check('it is a job of kind picks, action auto, for exactly that line, with the request\'s redo', job.kind === 'picks' && job.meta?.action === 'auto' && J(job.meta.beats) === J(['b0004']) && job.meta.redo === true, J(job.meta));
    const refused = await api.post(UJ('/picks/edit'), { instruction: 'đổi hình dòng này', scope: { beats: ['b0001'] } });
    check('a box turn sent meanwhile is refused (409 agent_job_running, retry later) and nothing was recorded', refused.status === 409 && refused.json?.code === 'agent_job_running' && refused.json?.retry === 'later' && refused.json?.job_id === t.job_id && (await joinThread()).turns.length === 1, refused.text);
    const err = await ev(`(async () => { try { const m = await import('/js/errmsg.js'); return m.boxErrorText({ status: 409, body: { code: 'agent_job_running' } }).text; } catch (e) { return 'ERR ' + e.message; } })()`);
    check('and the page says it in one Vietnamese sentence: another agent job runs, wait or press Dừng', /^Agent đang làm một việc khác cho dự án này/.test(err) && /Dừng/.test(err), err);
    const bar = await api.post(UJ('/picks/auto'), {});
    check('the pictures agent cannot be started a second time either (busy)', bar.status === 409 && ['busy', 'agent_job_running'].includes(bar.json?.code), bar.text);
    await shot('10-join-running');
    await clean('the running card');
    await switchAgent({ slow: false });
  });

  await step('join: the card follows the job to its result and the line gets its pictures', async () => {
    check('the card ends as an applied one, with the sentence of the result', await p.waitFor(`document.querySelector(${J(joinCard(esc.id))})?.dataset.status === 'applied'`, 120000) && /Agent đã chọn hình cho 1\/1 đoạn\./.test(await text(joinCard(esc.id))), await text(joinCard(esc.id)));
    const card = await text(joinCard(esc.id));
    check('it lists the sentence of what was written for that line, says how it was made, and sends the owner to the list of changes for the undo', /Đoạn 4: /.test(card) && /agent chọn hình/.test(card) && /Lịch sử thay đổi/.test(card), card);
    check('the card has no "Hoàn tác" of its own (the agent wrote several batches)', !(await exists(joinCard(esc.id, '.prompt-btn-undo'))));
    const t = (await joinThread()).turns.find((x) => x.id === esc.id);
    check('the thread says the same: applied, path agent, the result, the sentences of the batches', t.status === 'applied' && t.path === 'agent' && t.summary === 'Agent đã chọn hình cho 1/1 đoạn.' && t.result?.lines_done === 1 && (t.batch_changes || []).length >= 1 && t.batch === null, J(t));
    const d = await picksDoc2();
    const items = d.picks.beats.b0004?.items || [];
    check('line 4 got its pictures: the map and the clip the agent chose, and only that line was written', items.length === 2 && J(Object.keys(d.picks.beats)) === J(['b0004']), J(d.picks.beats));
    check('the page took it in: the line shows its two pictures, and the bar says the same sentence', await p.waitFor(`/hình của dòng này \\(2\\)/i.test(document.body.innerText) && document.querySelector('#pk-auto-sentence')?.innerText === 'Agent đã chọn hình cho 1/1 đoạn.'`, 40000), await text('#pk-auto'));
    const ch = (await api.get(UJ('/changes?doc=picks&limit=50'))).json.changes;
    check('every batch is by the agent, with the owner\'s lines in its note', ch.length >= 1 && ch.every((c) => c.actor === 'agent:mock' && /^Agent chọn hình/.test(c.note)), J(ch.map((c) => [c.actor, c.note])));
    const c = await calls();
    check('the fake agent was asked twice, plan then choose, once', J(c.calls.map((x) => x.mode)) === J(['plan', 'choose']), J(c));
    check('the box is free again: the field and the send button work', await p.waitFor(`!document.querySelector('.prompt-edit[data-box="picks"] .prompt-instruction').disabled`, 20000));
    check('the card and the line, as the owner sees them, carry no leftover and no raw word', true);
    await shot('11-join-result');
    await clean('after the joined path');
  });

  await step('the state of the project and the API say the same', async () => {
    const s = (await api.get(U('/state'))).json;
    const a = s.next_actions.find((x) => x.id === 'picks.auto');
    check('the state lists picks.auto as a long job that uses a model and costs time, not money', !!a && a.long_job && a.uses_model && a.cost?.kind === 'model' && a.label === 'Để agent chọn hình', J(a));
    const o = (await api.get(U('/picks/auto'))).json;
    check('GET .../picks/auto has the last result and the reasons', /1\/1/.test(o.last?.result?.sentence || '') && Object.keys(o.reasons).length >= 5 && o.agent?.id === 'gemini', J(o).slice(0, 300));
    check('no failed request in the page (apart from the refusals the checks provoked)', p.bad().filter((x) => !/\/picks\/auto|longjobs/.test(x)).length === 0, J(p.bad()));
  });
} finally {
  const n = finish();
  await closeAll();
  process.exit(n);
}
