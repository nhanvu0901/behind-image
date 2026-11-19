// Browser check of the agent select (contract docs/design/2026-11-18-agent-choice.md, section 8): on step 2 "Kịch bản" and step 5 "Dựng hình" (the
// draft panel and the prompt box), "Dùng cho cả dự án", reload, a second project, an agent that cannot run, the quota message with its ONE button,
// and the settings box ("Agent mặc định cho dự án mới", the table of models under "Nâng cao").
// Runs against a second instance of the app on the server (tests/e2e/agent/launch_agent.py wrapping tests/e2e/stages/launch.py: BTI_NO_REAL_MODELS=1,
// port 8562, data copied to a temp folder; the two agents are MOCK agents carrying the names of the real two; no agy and no claude is started)
// through an ssh tunnel, with headless Chrome on the Mac.
//   BTI_SSH_HOST=winbox-cmd node tests/e2e/agent/agent_select.mjs [--keep-server]
// One PASS or FAIL line per check, exit code = number failing. Screenshots: .scratch/agentpick/shots/.
process.env.BTI_STAGES_LAUNCH = 'tests\\e2e\\agent\\launch_agent.py';              // before remote.mjs is loaded: it reads it once
const { up, down, readState } = await import('../stages/remote.mjs');
const { openBrowser, makeApi, check, finish, go, sleep, REPO, bodyText, rawLooking, leftovers } = await import('../stages/common.mjs');
const path = await import('node:path');

const SHOTS = path.join(REPO, '.scratch/agentpick/shots');
const keep = process.argv.includes('--keep-server');
if (readState()) await down();                                                    // never reuse an instance that does not carry the mock agents
const st = await up({ doDeploy: true });
const base = st.base, api0 = makeApi(base);
// the ssh tunnel drops a connection now and then ("fetch failed"): every call here is idempotent or checked afterwards, so it is asked again
const again = (f) => async (...a) => { for (let i = 0; ; i++) { try { return await f(...a); } catch (e) { if (i >= 3) throw e; await sleep(1500); } } };
const api = { get: again(api0.get), put: again(api0.put), post: again(api0.post) };
const br = await openBrowser();
const p = await br.newPage();
let closed = false;
const closeAll = async () => { if (closed) return; closed = true; try { br.close(); } catch {} if (!keep) { try { await down(); } catch {} } };
process.on('exit', () => { try { br.close(); } catch {} });
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, async () => { await closeAll(); process.exit(130); });
process.on('uncaughtException', async (e) => { console.error(e); await closeAll(); process.exit(99); });

const S2 = 'arnolfini-from-books', S5 = 'arnolfini-live', OTHER = 'arnolfini';
const ev = (x) => p.eval(x);
const J = JSON.stringify;
const U = (pid, tail = '') => `/api/projects/${pid}${tail}`;
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} ran to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const snap = async (name, size) => { const f = path.join(SHOTS, `${name}${size ? '-' + size : ''}.png`); await p.shot(f); return f; };
const both = async (name) => { await p.resize(1700, 1000); await sleep(500); await snap(name, '1700'); await p.resize(1280, 720); await sleep(500); await snap(name, '1280'); await p.resize(1700, 1000); await sleep(300); };
const agentDoc = async (pid) => (await api.get(U(pid, '/agent'))).json;
const jobsOf = async (pid) => (await api.get(U(pid, '/script/jobs'))).json || [];
const sleepUntil = async (fn, ms = 60000, every = 500) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = await fn(); if (v) return v; await sleep(every); } return null; };

/** What an agent select shows now: its value, its entries, the line under it, the link and the warning. `root` is a CSS path to the `.agent-pick`. */
const pickState = (root) => ev(`(() => { const r = document.querySelector(${J(root)}); if (!r) return null; const s = r.querySelector('select'), w = r.querySelector('.agent-whole'), n = r.querySelector('.agent-warn');
  return { value: s.value, shown: s.selectedOptions[0]?.textContent || '', options: [...s.options].map((o) => o.textContent), disabled: s.disabled, source: r.querySelector('.agent-source')?.textContent || '',
    whole: !!w && !w.hidden, warn: n && !n.hidden ? n.textContent : '', agent: r.dataset.agent, label: r.querySelector('.agent-label')?.textContent || '' }; })()`);
const choose = (root, id) => ev(`(() => { const s = document.querySelector(${J(root)} + ' select'); s.value = ${J(id)}; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
const pickReady = (root) => p.waitFor(`(() => { const s = document.querySelector(${J(root)} + ' select'); return !!s && s.options.length >= 2 && !s.disabled && !/Đang tải/.test(document.querySelector(${J(root)} + ' .agent-source')?.textContent || ''); })()`, 40000);
const sourceIs = (root, text) => p.waitFor(`document.querySelector(${J(root)} + ' .agent-source')?.textContent === ${J(text)}`, 20000);
const clean = async (what) => { const t = await bodyText(p); check(`${what}: no leftovers, no raw words`, !(await leftovers(p)).length && !rawLooking(t).length, J(await leftovers(p)) + J(rawLooking(t))); };
const SCRIPT_PICK = '#agent-pick-host .agent-pick';

try {
  await p.resize(1700, 1000);
  await step('the routes and the machine default', async () => {
    const a = (await api.get('/api/agents')).json;
    check('GET /api/agents: the two agents with the names of the real two, both available', J(a.agents.map((x) => [x.id, x.label, x.available])) === J([['gemini', 'Gemini 3.8 Flash', true], ['opus', 'Opus 5.5 High', true]]) && a.default === 'gemini', J(a));
    const put = await api.put('/api/settings/agent', { agent: 'gemini' });          // what the settings box does: new projects start on Gemini
    check('PUT /api/settings/agent stores the machine default', put.status === 200 && put.json.machine_default === 'gemini', put.text);
    const d = await agentDoc(S2);
    check('a project without a choice starts on the default: "Theo mặc định"', d.agent === null && d.effective.script.id === 'gemini' && d.effective.script.source === 'default', J(d));
  });

  // ----------------------------------------------------------------------------------------------- step 2
  await step('step 2: the select replaces the model list', async () => {
    await go(p, base, `#/project/${S2}/script`);
    check('the select is on the toolbar', await pickReady(SCRIPT_PICK));
    check('the old model select is gone', await ev(`!document.querySelector('#model-pick') && !document.querySelector('#model-note')`));
    const s = await pickState(SCRIPT_PICK);
    check('it offers the two agents, shows "Gemini 3.8 Flash", the line says "Theo mặc định" and there is no link yet', J(s.options) === J(['Gemini 3.8 Flash', 'Opus 5.5 High']) && s.value === 'gemini'
      && s.source === 'Theo mặc định' && !s.whole && s.label === 'Agent:', J(s));
    await clean('step 2');
    await both('01-step2-select');
  });

  await step('step 2: a change is for this step of this project, at once, with no dialog', async () => {
    await choose(SCRIPT_PICK, 'opus');
    check('the line now says "Riêng cho bước này" and offers "Dùng cho cả dự án"', await sourceIs(SCRIPT_PICK, 'Riêng cho bước này') && (await pickState(SCRIPT_PICK)).whole);
    check('no dialog opened', !(await p.count('.modal')));
    const d = await agentDoc(S2);
    check('the server stored it for this step only', d.agent === null && J(d.steps) === J({ script: 'opus' }) && d.effective.script.id === 'opus' && d.effective.script.source === 'step'
      && d.effective.storyboard.id === 'gemini' && d.effective.storyboard.source === 'default', J(d));
    const other = await agentDoc(OTHER);
    check('a second project is not affected', other.agent === null && J(other.steps) === '{}' && other.effective.script.id === 'gemini', J(other));
    await both('02-step2-step-choice');
  });

  await step('step 2: "Dùng cho cả dự án", then a reload keeps it', async () => {
    await p.click(`${SCRIPT_PICK} .agent-whole`);
    check('the line says "Theo dự án" and the link is gone', await sourceIs(SCRIPT_PICK, 'Theo dự án') && !(await pickState(SCRIPT_PICK)).whole);
    const d = await agentDoc(S2);
    check('the server made it the project\'s agent and removed the step choices', d.agent === 'opus' && J(d.steps) === '{}' && Object.values(d.effective).every((e) => e.id === 'opus' && e.source === 'project'), J(d));
    await go(p, base, `#/project/${S2}/script`);
    await pickReady(SCRIPT_PICK);
    const s = await pickState(SCRIPT_PICK);
    check('after a reload the select still shows "Opus 5.5 High", "Theo dự án"', s.value === 'opus' && s.shown === 'Opus 5.5 High' && s.source === 'Theo dự án', J(s));
    const other = await agentDoc(OTHER);
    check('the second project is still not affected', other.agent === null && other.effective.script.id === 'gemini', J(other));
    await both('03-step2-whole-project');
  });

  await step('step 2: the page sends no model; the job and the source line name the agent', async () => {
    await choose(SCRIPT_PICK, 'gemini');
    await sourceIs(SCRIPT_PICK, 'Riêng cho bước này');
    const before = (await jobsOf(S2)).map((j) => j.id);
    await p.click('#btn-outline');
    await p.waitFor(`!!document.querySelector('.modal textarea')`, 10000);
    const dlg = await ev(`document.querySelector('.modal .body')?.innerText || ''`);
    check('the run dialog names the agent ("Agent: Gemini 3.8 Flash")', /Agent:\s*Gemini 3\.8 Flash/.test(dlg) && !/Mô hình:/.test(dlg), dlg.slice(0, 200));
    await p.click('.modal footer .primary');
    const job = await sleepUntil(async () => (await jobsOf(S2)).find((j) => !before.includes(j.id) && ['done', 'error', 'cancelled'].includes(j.state)), 90000);
    check('the job ends done and its record says the agent (id and label) next to the model, chosen by the step', !!job && job.state === 'done' && job.model === 'mock'
      && J(job.agent) === J({ id: 'gemini', label: 'Gemini 3.8 Flash', model: 'mock', source: 'step' }), J(job));
    await sleep(1200);
    const out = await ev(`document.querySelector('#out-body')?.innerText || ''`);
    check('the outline\'s source line names the agent by its label, not the model id', /Nguồn dàn ý: Gemini 3\.8 Flash,/.test(out) && !/mock/.test(out.split('Nguồn dàn ý')[1] || ''), (out.split('Nguồn dàn ý')[1] || '').slice(0, 80));
    await clean('step 2 after a job');
  });

  await step('step 2: an agent that cannot run is shown, says why, and a start says it in plain words', async () => {
    await api.put('/api/_e2e/opus', { down: true });
    await go(p, base, `#/project/${S2}/script`);
    await pickReady(SCRIPT_PICK);
    let s = await pickState(SCRIPT_PICK);
    check('the select still lists "Opus 5.5 High", marked as not usable', s.options.includes('Opus 5.5 High (chưa dùng được)') && s.options.length === 2, J(s));
    const a = (await api.get('/api/agents')).json.agents.find((x) => x.id === 'opus');
    check('GET /api/agents says available:false with the sentence', a.available === false && /^Claude Code trên máy chủ chưa đăng nhập/.test(a.reason || ''), J(a));
    await choose(SCRIPT_PICK, 'opus');
    await p.waitFor(`!!document.querySelector('${SCRIPT_PICK} .agent-warn') && !document.querySelector('${SCRIPT_PICK} .agent-warn').hidden`, 15000);
    s = await pickState(SCRIPT_PICK);
    check('choosing it is allowed and the line under it gives the reason', s.value === 'opus' && /^Opus 5\.5 High chưa dùng được: Claude Code trên máy chủ chưa đăng nhập/.test(s.warn), J(s));
    await both('04-step2-unavailable');
    const before = (await jobsOf(S2)).map((j) => j.id);
    await p.click('#btn-outline');
    await p.waitFor(`!!document.querySelector('.modal textarea')`, 10000);
    await p.click('.modal footer .primary');
    const toast = await p.waitFor(`/Claude Code trên máy chủ chưa đăng nhập/.test(document.querySelector('#toast-root')?.innerText || '')`, 20000);
    check('starting says it in Vietnamese (the server\'s sentence), and no job was started', toast && (await jobsOf(S2)).every((j) => before.includes(j.id)), await ev(`document.querySelector('#toast-root')?.innerText || ''`));
    await api.put('/api/_e2e/opus', { down: false });
  });

  await step('step 2: the quota message names the agent and the time, one button switches and runs the same request again', async () => {
    await go(p, base, `#/project/${S2}/script`);
    await pickReady(SCRIPT_PICK);
    await choose(SCRIPT_PICK, 'opus');
    await sourceIs(SCRIPT_PICK, 'Riêng cho bước này');
    const before = (await jobsOf(S2)).map((j) => j.id);
    await p.click('#btn-outline');
    await p.waitFor(`!!document.querySelector('.modal textarea')`, 10000);
    await p.focus('.modal textarea'); await p.insert('[mock:quota]');
    await p.click('.modal footer .primary');
    const shown = await p.waitFor(`!!document.querySelector('.modal .agent-quota-switch')`, 60000);
    check('the job ends with a quota answer and the message opens', shown);
    const txt = await ev(`document.querySelector('.modal')?.innerText || ''`);
    check('the sentence names the agent and the time', /Opus 5\.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút\./.test(txt), txt.slice(0, 300));
    const buttons = await ev(`[...document.querySelectorAll('.modal .body button')].map((b) => b.textContent.trim())`);
    check('exactly one button: "Chuyển sang Gemini 3.8 Flash và chạy lại"', J(buttons) === J(['Chuyển sang Gemini 3.8 Flash và chạy lại']), J(buttons));
    check('nothing switched by itself: the step still has Opus', (await agentDoc(S2)).steps.script === 'opus');
    await both('05-step2-quota');
    const failed = (await jobsOf(S2)).find((j) => !before.includes(j.id));
    check('the failed job\'s record carries the agent and the time', failed?.agent?.id === 'opus' && failed.retry_after_seconds === 16200 && !!failed.retry_at, J(failed));
    await p.click('.modal .agent-quota-switch');
    const redone = await sleepUntil(async () => (await jobsOf(S2)).find((j) => j.state === 'done' && !before.includes(j.id) && j.agent?.id === 'gemini'), 90000);
    check('the button stored Gemini as this step\'s choice and ran the same request again, which ended done', !!redone && (await agentDoc(S2)).steps.script === 'gemini', J(await jobsOf(S2)));
    check('the dialog is gone and the select shows "Gemini 3.8 Flash", "Riêng cho bước này"', await p.waitFor(`!document.querySelector('.modal')`, 20000) && (await pickState(SCRIPT_PICK)).value === 'gemini'
      && (await pickState(SCRIPT_PICK)).source === 'Riêng cho bước này', J(await pickState(SCRIPT_PICK)));
  });

  // ----------------------------------------------------------------------------------------------- step 5
  const BOX_PICK = '.prompt-agent .agent-pick', DRAFT_PICK = '.modal .draft-agent .agent-pick';
  const turns = async () => (await api.get(U(S5, '/draft/thread'))).json?.turns || [];
  const cardOf = (id) => `.prompt-turn-card[data-turn="${id}"]`;
  async function clickShot(i) {
    const pt = await ev(`(() => { const s = __bti.store.draft.shots[${i}]; const r = document.querySelector('#tl-canvas').getBoundingClientRect(); const tl = window.__tl; return { x: r.x + tl.X((s._t0 + s._t1) / 2), y: r.y + tl.Y.shot + tl.R.shot / 2 }; })()`);
    await p.clickXY(pt.x, pt.y); await sleep(300);
  }

  await step('step 5: the prompt box and the draft panel have the same select', async () => {
    // the copy of the test project has timing but its picks are not approved: approve them like the owner does at step 4, so that a draft may be built
    const pk = (await api.get(U(S5, '/picks'))).json;
    const ap = await api.post(U(S5, '/picks/approve'), { rev: pk?.rev });
    const ready = (await api.get(U(S5, '/draft'))).json?.ready;
    check('the draft of the test project can be built (voice and approved picks)', ready?.ok === true, J({ approve: ap.status, ready }) + ap.text.slice(0, 200));
    const proj = await api.get(U(S5));
    check('the step 5 test project is there', proj.status === 200 && proj.json.storyboard?.shots?.length > 3, `${proj.status} ${proj.text.slice(0, 100)}`);
    await go(p, base, `#/project/${S5}/edit`);
    await p.waitFor(`!!window.__bti?.store?.draft && !!document.querySelector('.prompt-edit')`, 40000);
    check('the prompt box has the select and no link to the settings', await pickReady(BOX_PICK) && await ev(`!document.querySelector('.prompt-model-link')`));
    let s = await pickState(BOX_PICK);
    check('it shows "Gemini 3.8 Flash", "Theo mặc định" (this project has no choice)', s.value === 'gemini' && s.source === 'Theo mặc định' && J(s.options) === J(['Gemini 3.8 Flash', 'Opus 5.5 High']), J(s));
    await both('06-step5-prompt-box');
    await p.click('#btn-draft');
    check('the draft panel has the select too, and no model list', await pickReady(DRAFT_PICK) && await ev(`!document.querySelector('.modal select.draft-model')`));
    s = await pickState(DRAFT_PICK);
    check('the draft panel shows the same agent and its source', s.value === 'gemini' && s.source === 'Theo mặc định', J(s));
    await clean('step 5 draft panel');
    await both('07-step5-draft-panel');
  });

  await step('step 5: a change in one select is seen by the other, and kept for the project', async () => {
    await choose(DRAFT_PICK, 'opus');
    await sourceIs(DRAFT_PICK, 'Riêng cho bước này');
    const d = await agentDoc(S5);
    check('the server stored the choice for the storyboard step only', J(d.steps) === J({ storyboard: 'opus' }) && d.effective.script.id === 'gemini', J(d));
    check('the select of the prompt box follows at once', await p.waitFor(`document.querySelector('${BOX_PICK} select')?.value === 'opus'`, 15000) && (await pickState(BOX_PICK)).source === 'Riêng cho bước này', J(await pickState(BOX_PICK)));
  });

  await step('step 5: the draft\'s quota message, one button, then the draft is built by the other agent', async () => {
    await p.waitFor(`!!document.querySelector('.modal .draft-panel button.primary')`, 10000);
    await p.click('.modal .draft-panel button.primary', 'Dựng bản nháp');
    if (await p.waitFor(`!!document.querySelector('.modal.ask')`, 2500)) await p.click('.modal.ask footer button:last-child');          // "the project already has a draft: build another?"
    const shown = await p.waitFor(`!!document.querySelector('.modal .draft-quota .agent-quota-switch')`, 90000);
    check('the draft job ends with a quota answer and the panel shows the message', shown);
    const txt = await ev(`document.querySelector('.modal .draft-quota')?.innerText || ''`);
    check('the sentence names the agent and the time; the button names the other agent', /Opus 5\.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút\./.test(txt) && /Chuyển sang Gemini 3\.8 Flash và chạy lại/.test(txt), txt);
    const buttons = await ev(`[...document.querySelectorAll('.modal .draft-quota .agent-quota button')].map((b) => b.textContent.trim())`);
    check('exactly one button in the message', J(buttons) === J(['Chuyển sang Gemini 3.8 Flash và chạy lại']), J(buttons));
    check('nothing switched by itself', (await agentDoc(S5)).steps.storyboard === 'opus');
    await both('08-step5-draft-quota');
    await p.click('.modal .draft-quota .agent-quota-switch');
    const done = await p.waitFor(`!!document.querySelector('.modal .draft-panel') && /Mở đề xuất/.test(document.querySelector('.modal .draft-panel').innerText) && !document.querySelector('.modal .draft-quota')`, 180000);
    const last = (await api.get(U(S5, '/draft'))).json;
    check('the draft was built again, by Gemini', done && last.last_run?.status === 'done' && last.last_run?.agent?.id === 'gemini' && last.agent.id === 'gemini', J(last.last_run) + J(last.agent));
    check('the panel names the agent that built it', /Agent: Gemini 3\.8 Flash\./.test(await ev(`document.querySelector('.modal .draft-panel')?.innerText || ''`)));
    check('the choice of the step is now Gemini, in the draft panel and in the prompt box', (await pickState(DRAFT_PICK)).value === 'gemini' && (await pickState(BOX_PICK)).value === 'gemini' && (await agentDoc(S5)).steps.storyboard === 'gemini');
    await ev(`document.querySelector('.modal header button')?.click()`); await sleep(500);
  });

  await step('step 5: the prompt box\'s quota message, one button, and the same request is sent again', async () => {
    await choose(BOX_PICK, 'opus');
    await sourceIs(BOX_PICK, 'Riêng cho bước này');
    const idx = await ev(`(() => { const s = __bti.store.draft.shots; for (let i = 0; i < s.length; i++) if (__bti.ctx.tech(s[i].technique)?.kind !== 'card') return i; return 0; })()`);
    await clickShot(idx);
    const before = (await turns()).map((t) => t.id);
    await ev(`(() => { const t = document.querySelector('.prompt-instruction'); t.value = ''; t.focus(); })()`);
    await p.insert('làm chậm chuyển động ở cảnh này [mock:quota]'); await sleep(150);
    await p.click('.prompt-btn-submit');
    const failed = await sleepUntil(async () => (await turns()).find((t) => !before.includes(t.id) && ['failed', 'applied'].includes(t.status)), 90000);
    check('the turn fails with a quota answer that carries the agent and the time', failed?.status === 'failed' && failed.agent?.id === 'opus' && failed.retry_after_seconds === 16200 && !!failed.retry_at, J(failed));
    const sel = cardOf(failed.id);
    check('the card shows the message', await p.waitFor(`!!document.querySelector('${sel} .agent-quota-switch')`, 30000));
    const txt = await ev(`document.querySelector('${sel} .prompt-turn-quota')?.innerText || ''`);
    check('the sentence names the agent and the time; the button names the other agent', /Opus 5\.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút\./.test(txt) && /Chuyển sang Gemini 3\.8 Flash và chạy lại/.test(txt), txt);
    const buttons = await ev(`[...document.querySelectorAll('${sel} .agent-quota button')].map((b) => b.textContent.trim())`);
    check('exactly one button in the message, and no "Chọn mô hình khác"', J(buttons) === J(['Chuyển sang Gemini 3.8 Flash và chạy lại']) && !/Chọn mô hình khác/.test(await ev(`document.querySelector('${sel}').innerText`)), J(buttons));
    check('nothing switched by itself', (await agentDoc(S5)).steps.storyboard === 'opus');
    await both('09-step5-prompt-quota');
    await p.click(`${sel} .agent-quota-switch`);
    const again2 = await sleepUntil(async () => (await turns()).find((t) => !before.includes(t.id) && t.id !== failed.id && ['applied', 'failed', 'no_change'].includes(t.status)), 90000);
    if (!again2 || again2.status !== 'applied') console.log('  (note) the second turn:', J(again2 && { status: again2.status, error: again2.error, summary: again2.summary?.slice(0, 120), notes: again2.notes?.slice(0, 400) }));
    check('the button stored Gemini and sent the same instruction again, which ran on Gemini and was applied', !!again2 && again2.instruction === failed.instruction && again2.agent?.id === 'gemini'
      && again2.model === 'mock' && again2.status === 'applied' && (await agentDoc(S5)).steps.storyboard === 'gemini', J(again2));
    if (!again2) return;
    await sleep(1500);
    const c = await ev(`document.querySelector('${cardOf(again2.id)}')?.innerText || ''`);
    check('the finished card names the agent by its label', /Agent: Gemini 3\.8 Flash\./.test(c), c.slice(0, 300));
    await clean('step 5 after the edits');
  });

  // ----------------------------------------------------------------------------------------------- the settings box
  await step('the settings box: the default agent on top, the table of models under a collapsed "Nâng cao"', async () => {
    await p.click('#btn-settings');
    check('the box opens with "Agent mặc định cho dự án mới"', await p.waitFor(`/Agent mặc định cho dự án mới/.test(document.querySelector('.modal')?.innerText || '') && !!document.querySelector('.modal #settings-agent-default option')`, 20000));
    const s = await ev(`(() => { const m = document.querySelector('.modal'), d = m.querySelector('details.settings-advanced'), sel = m.querySelector('#settings-agent-default');
      return { title: m.querySelector('header h3')?.textContent, value: sel.value, options: [...sel.options].map((o) => o.textContent), open: d.open, summary: d.querySelector('summary').textContent,
        hint: d.querySelector('.settings-adv-hint')?.textContent, rows: m.querySelectorAll('select.settings-model').length, topFirst: !!(sel.compareDocumentPosition(d) & Node.DOCUMENT_POSITION_FOLLOWING),
        rowsShown: /Dàn ý kịch bản/.test(m.innerText) }; })()`);          // innerText leaves out what a closed <details> hides
    check('the title is "Cài đặt"; the default agent is Gemini; the table is under "Nâng cao", collapsed, with its one hint line', s.title === 'Cài đặt' && s.value === 'gemini' && J(s.options) === J(['Gemini 3.8 Flash', 'Opus 5.5 High'])
      && s.summary === 'Nâng cao' && s.open === false && s.hint === 'Chỉ dùng khi dự án và mặc định đều chưa chọn agent.' && s.topFirst && s.rows >= 6 && s.rowsShown === false, J(s));
    await both('10-settings-top');
    await ev(`(() => { const s = document.querySelector('.modal #settings-agent-default'); s.value = 'opus'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    check('choosing Opus saves it at once', await p.waitFor(`/Đã lưu agent mặc định/.test(document.querySelector('#toast-root')?.innerText || '')`, 15000) && (await api.get('/api/agents')).json.machine_default === 'opus');
    const fresh = await agentDoc('demo_stub');
    check('a project with no choice now starts on Opus ("Theo mặc định")', fresh.agent === null && fresh.effective.script.id === 'opus' && fresh.effective.script.source === 'default', J(fresh));
    check('a project with a choice keeps it', (await agentDoc(S5)).effective.storyboard.id === 'gemini' && (await agentDoc(S5)).effective.storyboard.source === 'step');
    await p.click('.modal .settings-advanced summary');
    check('"Nâng cao" opens to the table of models per role', await p.waitFor(`document.querySelector('.modal details.settings-advanced').open && document.querySelectorAll('.modal select.settings-model').length >= 6 && /Dàn ý kịch bản/.test(document.querySelector('.modal').innerText)`, 15000));
    await clean('the settings box');
    await both('11-settings-advanced');
    await ev(`(() => { const s = document.querySelector('.modal #settings-agent-default'); s.value = 'gemini'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await p.waitFor(`/Đã lưu agent mặc định/.test(document.querySelector('#toast-root')?.innerText || '')`, 15000);
    check('put back to Gemini', (await api.get('/api/agents')).json.machine_default === 'gemini');
    await ev(`document.querySelector('.modal header button')?.click()`); await sleep(400);
  });

  await step('the answers of a stale write and a bad agent are refused in plain words', async () => {
    const d = await agentDoc(OTHER);
    const stale = await api.put(U(OTHER, '/agent'), { agent: 'opus', base_rev: 'not-the-revision' });
    check('a stale base_rev is 409 stale with the current revision', stale.status === 409 && stale.json.code === 'stale' && stale.json.rev === d.rev, stale.text);
    const bad = await api.put(U(OTHER, '/agent'), { agent: 'nope', base_rev: d.rev });
    check('an unknown agent is 422 unknown_agent; an unknown step is 422 unknown_step', bad.status === 422 && bad.json.code === 'unknown_agent'
      && (await api.put(U(OTHER, '/agent'), { steps: { nowhere: 'gemini' }, base_rev: d.rev })).json.code === 'unknown_step');
    check('nothing was written', J(await agentDoc(OTHER)) === J(d));
  });
} finally {
  const n = finish();
  await closeAll();
  process.exit(n);
}
