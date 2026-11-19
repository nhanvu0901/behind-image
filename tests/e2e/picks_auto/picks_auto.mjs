// Browser check of "Để agent chọn hình" on the pictures page (step 4): press the button, see the progress with its limits, cancel, run again, see the
// result sentence and the lines filled with the agent's reasons, press "Chọn lại phần còn thiếu", reload, change a note, a failing agent.
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
