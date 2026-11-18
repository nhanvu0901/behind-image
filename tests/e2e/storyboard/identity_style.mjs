// Browser check of the channel identity (selector "Kiểu mở đầu và mốc chương" of step 5, its line in step 6, PUT/GET /identity).
// Runs against the second instance of the app on the server (tests/e2e/stages/launch.py: fakes, BTI_NO_REAL_MODELS=1, port 8562, data copied to
// a temp folder; the project `arnolfini` is the sample used here) through an ssh tunnel, with headless Chrome on the Mac.
//   BTI_SSH_HOST=winbox-cmd node tests/e2e/storyboard/identity_style.mjs [--keep-server]
// For each style: pick it in the dropdown, check the storyboard on the server, the page, and look at an engine frame inside the opening,
// the channel-name beat and a chapter mark. One PASS or FAIL line per check, exit code = number failing.
// Screenshots and frames: .scratch/idapply/shots/.
import { up, down, readState } from '../stages/remote.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { openBrowser, makeApi, check, finish, go, sleep, REPO, bodyText, has, rawLooking } from '../stages/common.mjs';

const SHOTS = path.join(REPO, '.scratch/idapply/shots');
const keep = process.argv.includes('--keep-server');
const started = !readState();
const st = await up({ doDeploy: started });
const base = st.base, api0 = makeApi(base);
// the ssh tunnel drops a connection now and then ("fetch failed"): every call of this check is idempotent, so it is asked again
const again = (f) => async (...a) => { for (let i = 0; ; i++) { try { return await f(...a); } catch (e) { if (i >= 3) throw e; await sleep(1500); } } };
const api = { get: again(api0.get), put: again(api0.put), post: again(api0.post) };
const br = await openBrowser();
const p = await br.newPage();
let closed = false;
const closeAll = () => { if (closed) return; closed = true; try { br.close(); } catch {} };
process.on('exit', closeAll);
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { closeAll(); process.exit(130); });
process.on('uncaughtException', (e) => { console.error(e); closeAll(); process.exit(99); });

const PID = 'arnolfini';
const J = JSON.stringify;
const ev = (x) => p.eval(x);
const U = (tail = '') => `/api/projects/${PID}${tail}`;
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} ran to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };
const snap = async (name) => p.shot(path.join(SHOTS, name + '.png'));
const canon = (o) => JSON.stringify(o, (k, v) => (k.startsWith('_') ? undefined : v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => (a < b ? -1 : 1))) : v));
fs.mkdirSync(SHOTS, { recursive: true });

// the instance keeps its data between runs (--keep-server): every run starts from the project's original storyboard (the repo's copy)
const ORIG = JSON.parse(fs.readFileSync(path.join(REPO, 'projects', PID, 'storyboard.json'), 'utf8'));
const restoreOriginal = async () => {
  const cur = (await api.get(U())).json;
  const r = await api.put(U('/storyboard'), { storyboard: ORIG, base_rev: cur.rev });
  return r.status;
};
const state = async () => (await api.get(U())).json;
const identity = async () => (await api.get(U('/identity'))).json;
const pageReady = async () => { await go(p, base, `#/project/${PID}/edit`); await p.waitFor(`!!window.__bti?.store?.draft && !!document.querySelector('#identity-select') && !document.querySelector('.identity-pick').hidden`, 40000); await sleep(800); };
const pick = async (style) => {
  await ev(`(() => { const s = document.querySelector('#identity-select'); s.value = ${J(style)}; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  return p.waitFor(`document.querySelector('.identity-pick')?.dataset.style === ${J(style)} && !document.querySelector('#identity-select').disabled && __bti.store.draft.identity?.style === ${J(style)}`, 120000);
};
const selectorNow = () => ev(`(() => { const s = document.querySelector('#identity-select'); return { value: s.value, options: [...s.options].map((o) => ({ v: o.value, t: o.textContent, d: o.disabled })), disabled: s.disabled,
  label: document.querySelector('.identity-label')?.textContent, undo: !!document.querySelector('.identity-undo') && !document.querySelector('.identity-undo').hidden, note: document.querySelector('.identity-note')?.textContent,
  skipped: document.querySelector('.identity-skipped') && !document.querySelector('.identity-skipped').hidden ? document.querySelector('.identity-skipped').textContent : '' }; })()`);

async function frame(name, t) {
  const r = await fetch(base + U(`/frame?t=${t.toFixed(2)}&width=960`));
  const buf = Buffer.from(await r.arrayBuffer());
  const f = path.join(SHOTS, name + '.jpg');
  fs.writeFileSync(f, buf);
  check(`frame ${name} (t=${t.toFixed(2)} s) is a picture`, r.status === 200 && /jpeg/.test(r.headers.get('content-type') || '') && buf.length > 5000, `${r.status} ${buf.length}`);
  return f;
}

try {
  let styleDoc = null, info0 = null;
  await step('open the project in its old look', async () => {
    const rs = await restoreOriginal();
    check('the sample project is put back to the repo copy of its storyboard (the old cards)', rs === 200, rs);
    styleDoc = (await api.get('/api/styles/gae')).json;
    info0 = await identity();
    check('GET /identity: nothing chosen yet, the default and the two options with their words from the route', info0.style === null && info0.default === styleDoc.style.identity.default_style
      && J(info0.options.map((o) => o.label)) === J(['Vệt sáng quét', 'Tối lại, hiện tên']), J(info0));
    await p.resize(1700, 1000);
    await pageReady();
    const s = await selectorNow();
    check('step 5 shows the selector "Kiểu mở đầu và mốc chương" with "Kiểu cũ" selected and not selectable, then the two styles', s.label === 'Kiểu mở đầu và mốc chương' && s.value === ''
      && J(s.options.map((o) => o.t)) === J(['Kiểu cũ', 'Vệt sáng quét', 'Tối lại, hiện tên']) && s.options[0].d === true, J(s));
    check('the old look says so in plain words', /kiểu cũ/i.test(s.note || ''), s.note);
    await snap('step5-old-look-1700');
  });

  const orig = (await state()).storyboard;
  const isStruct = (s) => s.intent === 'structure';
  const oldCards = orig.shots.filter((s) => isStruct(s) && ['X-CARD-01', 'X-CARD-02', 'TXT-01'].includes(s.technique));
  const originalRev = (await state()).rev;

  for (const style of ['raking', 'dim']) {
    const sd = styleDoc.style.identity.styles[style];
    await step(`${style}: pick it in the dropdown`, async () => {
      await restoreOriginal();
      await pageReady();
      const t0 = Date.now();
      const ok = await pick(style);
      check(`${style}: the choice is applied and the page loads the new storyboard (${Math.round((Date.now() - t0) / 100) / 10} s)`, ok, J(await selectorNow()));
      const sel = await selectorNow();
      check(`${style}: the dropdown shows "${sd.label_vi}", the old look is no longer an entry, "Hoàn tác" is there`, sel.value === style && !sel.options.some((o) => o.v === '') && sel.undo === true, J(sel));
      const s = await state();
      const sb = s.storyboard;
      check(`${style}: identity.style is saved with the video`, sb.identity?.style === style && (await identity()).style === style);
      const structure = sb.shots.filter((x) => isStruct(x) && [sd.brand, sd.mark, 'X-CARD-01', 'X-CARD-02', 'TXT-01'].includes(x.technique));
      check(`${style}: every title slot and chapter card is the style's own (${structure.length} shots, none of the old cards)`, structure.length === oldCards.length
        && structure.every((x) => [sd.brand, sd.mark].includes(x.technique)), J(structure.map((x) => x.technique)));
      const marks = structure.filter((x) => x.technique === sd.mark);
      check(`${style}: the marks read "1. Title", "2. Title", ... in order`, marks.length > 3 && marks.every((x, i) => new RegExp(`^${i + 1}\\. \\S`).test(x.params.title)), J(marks.map((x) => x.params.title)));
      check(`${style}: titles are in title case`, marks.every((x) => !/^\d+\. [A-Z' ]+$/.test(x.params.title) || x.params.title.length < 8), J(marks.map((x) => x.params.title)));
      check(`${style}: the channel-name beat says the channel name`, structure.some((x) => x.technique === sd.brand && x.params.text === styleDoc.style.identity.channel_name));
      check(`${style}: the entry transition of the marks is ${sd.mark_transition ? sd.mark_transition.technique : 'none (a hard cut)'}`, marks.every((x) => (sd.mark_transition ? x.transition_in?.technique === sd.mark_transition.technique && x.transition_in.dur === sd.mark_transition.dur : !x.transition_in)));
      const first = sb.shots[0], ids = first.overlays.filter((o) => [sd.open, sd.label].includes(o.technique)).map((o) => o.technique);
      check(`${style}: the opening overlay${sd.label ? 's (opening and label)' : ' (it carries the title)'} sit on the first shot`, J(ids.sort()) === J([sd.open, sd.label].filter(Boolean).sort()), J(first.overlays.map((o) => o.technique)));
      const others = Object.values(styleDoc.style.identity.styles).filter((x) => x !== sd).flatMap((x) => [x.open, x.label, x.brand, x.mark]).filter(Boolean);
      check(`${style}: nothing of the other style is left anywhere`, !sb.shots.some((x) => others.includes(x.technique) || x.overlays.some((o) => others.includes(o.technique))));
      const origById = Object.fromEntries(orig.shots.map((x) => [x.id, x]));
      const touched = sb.shots.filter((x) => canon(x) !== canon(origById[x.id])).map((x) => x.id);
      check(`${style}: only the first shot and the cards changed (${touched.length} of ${sb.shots.length} shots)`, touched.length === 1 + oldCards.length && touched.every((id) => id === first.id || oldCards.some((c) => c.id === id)), J(touched));
      check(`${style}: the check finds no error and no card of another style`, !s.issues.some((i) => i.level === 'error' || i.code === 'identity_technique_mismatch'), J(s.issues.filter((i) => i.level === 'error').slice(0, 3)));
      const draft = await ev(`({ dirty: __bti.store.dirty, tech: __bti.store.draft.shots.filter((x) => x.intent === 'structure').map((x) => x.technique) })`);
      check(`${style}: the page holds the new storyboard and nothing is marked unsaved`, draft.dirty === false && draft.tech.includes(sd.mark), J(draft));
      await snap(`step5-${style}-1700`);
      await p.resize(1280, 720); await sleep(500); await snap(`step5-${style}-1280`); await p.resize(1700, 1000); await sleep(300);

      // the engine's own frames: inside the opening, the channel-name beat and a chapter mark
      const sh = s.storyboard.shots, t0s = (x) => x._t0, len = (x) => x._t1 - x._t0;
      const op = sh[0].overlays.find((o) => o.technique === sd.open);
      const opT = (op._t0 ?? 0) + Math.min(3.0, (op._t1 - op._t0) * 0.45);
      await frame(`${style}-1-opening`, opT);
      const lab = sh[0].overlays.find((o) => sd.label && o.technique === sd.label);
      if (lab) await frame(`${style}-1b-label`, lab._t0 + Math.min(2.0, (lab._t1 - lab._t0) * 0.6));
      const brand = sh.find((x) => x.technique === sd.brand);
      await frame(`${style}-2-channel-name`, brand._t0 + 0.65 * len(brand));
      const mk = sh.find((x) => x.technique === sd.mark);
      await frame(`${style}-3-chapter-mark`, mk._t0 + (style === 'raking' ? 0.6 : 0.5) * len(mk));
      // and the same mark in the page's own preview
      await ev(`__bti.seek(${mk._t0 + 0.55 * len(mk)})`); await sleep(2500); await snap(`step5-${style}-mark-in-page`);
    });

    await step(`${style}: Hoàn tác puts the storyboard back`, async () => {
      await p.click('.identity-undo');
      const ok = await p.waitFor(`!__bti.store.draft.identity && document.querySelector('.identity-pick')?.dataset.style === '' && document.querySelector('#identity-select').value === ''`, 60000);
      check(`${style}: Hoàn tác brings back the old look in the page (selector says "Kiểu cũ" again)`, ok, J(await selectorNow()));
      const s = await state();
      check(`${style}: the saved storyboard is the original again (same revision, no identity)`, s.rev === originalRev && !s.storyboard.identity, `${s.rev} vs ${originalRev}`);
    });
  }

  // ============================================================ what cannot be changed is said in plain words
  await step('a locked card is skipped and the page says so', async () => {
    await restoreOriginal();
    const cur = await state();
    const doc = JSON.parse(JSON.stringify(ORIG));
    const title = doc.shots.find((x) => x.technique === 'X-CARD-02');
    title.locked = true;
    const saved = await api.put(U('/storyboard'), { storyboard: doc, base_rev: cur.rev });
    check('the title card of the sample is locked', saved.status === 200, saved.text.slice(0, 200));
    await pageReady();
    const ok = await pick('raking');
    const sel = await selectorNow();
    check('the style is applied; the locked title card is left as it is and the page says so in plain Vietnamese (a number, never an id)', ok && /đang khóa/.test(sel.skipped) && /Cảnh \d+/.test(sel.skipped) && !/s00\d\d|_/.test(sel.skipped), J(sel));
    const sb = (await state()).storyboard;
    check('the locked shot still has its old technique, the other cards changed', sb.shots.find((x) => x.id === title.id).technique === 'X-CARD-02' && sb.shots.filter((x) => x.intent === 'structure' && x.technique === 'ID-MARK-01').length === oldCards.length - 1);
    check('the check warns about the locked old card (Lỗi tab count is a warning, no error)', (await state()).issues.some((i) => i.code === 'identity_technique_mismatch') && !(await state()).issues.some((i) => i.level === 'error'));
    await snap('step5-skipped-1700');
  });

  // ============================================================ unsaved changes: the page's rule for server-side changes
  await step('choosing a style with unsaved edits', async () => {
    await restoreOriginal();
    await pageReady();
    const NOTE = 'ghi chú của chủ video';
    const target = orig.shots.find((x) => !isStruct(x) && x.id !== orig.shots[0].id && x.technique !== 'X-CARD-01').id;
    await ev(`__bti.store.commit('test', (d) => { d.shots.find((x) => x.id === ${J(target)}).note = ${J(NOTE)}; })`);
    check('an unsaved edit is in the page', (await ev(`__bti.store.dirty`)) === true);
    const ok = await pick('raking');
    check('the style is applied with the unsaved edit kept (merged, not lost), the page is still marked unsaved', ok && (await ev(`({ dirty: __bti.store.dirty, note: __bti.store.draft.shots.find((x) => x.id === ${J(target)}).note })`)).dirty === true
      && (await ev(`__bti.store.draft.shots.find((x) => x.id === ${J(target)}).note`)) === NOTE, J(await selectorNow()));
    await ev(`__bti.save()`); await p.waitFor(`!__bti.store.dirty`, 30000);
    const s = await state();
    check('after Lưu the server holds both the style and the owner\'s edit', s.storyboard.identity?.style === 'raking' && s.storyboard.shots.find((x) => x.id === target).note === NOTE);
    await snap('step5-unsaved-merge-1700');
  });

  // ============================================================ the route, as an agent uses it
  await step('the route as an agent uses it', async () => {
    await restoreOriginal();
    const cur = await state();
    const req = { style: 'dim', base_rev: cur.rev };
    const stale = await api.put(U('/identity'), { style: 'dim', base_rev: '0'.repeat(64) });
    check('PUT /identity with a stale base_rev is 409 and says the current revision', stale.status === 409 && stale.json.rev === cur.rev, stale.text);
    const bad = await api.put(U('/identity'), { style: 'sepia', base_rev: cur.rev });
    check('PUT /identity with an unknown style is 422 and names the choices', bad.status === 422 && bad.json.code === 'identity_style_unknown' && bad.json.allowed.length === 2, bad.text);
    const r = await api.put(U('/identity'), req);
    check('PUT /identity {style, base_rev} answers {rev, style, changed, skipped}', r.status === 200 && J(Object.keys(r.json).sort()) === J(['changed', 'rev', 'skipped', 'style']) && r.json.style === 'dim' && r.json.changed.length >= 3, r.text);
    fs.writeFileSync(path.join(REPO, '.scratch/idapply/route_example.txt'), `GET ${U('/identity')} (before)\n${J(info0)}\n\nPUT ${U('/identity')}\n${J(req)}\n-> ${r.status}\n${J(r.json)}\n\nPUT (stale base_rev) -> ${stale.status}\n${stale.text}\n\nPUT (unknown style) -> ${bad.status}\n${bad.text}\n`);
    const again2 = await api.put(U('/identity'), { style: 'dim', base_rev: r.json.rev });
    check('the same style again changes nothing', again2.status === 200 && again2.json.changed.length === 0 && again2.json.rev === r.json.rev, again2.text);
  });

  // ============================================================ step 6
  await step('step 6 names the style', async () => {
    const info = await identity();
    const cur = await state();
    const ap = await api.post(U('/approve'), { rev: cur.rev });                       // step 6 opens only for an approved storyboard
    check('the storyboard (in the style the route chose) is approved, so that step 6 opens', ap.status === 200, ap.text.slice(0, 200));
    await go(p, base, `#/project/${PID}/export`);
    await p.waitFor(`!!document.querySelector('[data-identity-line]')`, 30000);
    const t = await bodyText(p);
    check('step 6 says which style the video will be exported with', has(t, 'Kiểu mở đầu và mốc chương') && has(t, info.options.find((o) => o.id === info.style).label), t.slice(0, 300));
    check('nothing raw or untranslated in step 6', rawLooking(t).length === 0, rawLooking(t).join());
    await snap('step6-1700');
  });

  const logs = p.logs.filter((l) => !/favicon|Failed to load resource.*(409|422)/.test(l));
  check('no console error or exception in the browser', logs.length === 0, logs.slice(0, 3).join(' | '));
} finally {
  await restoreOriginal().catch(() => {});
  closeAll();
  if (!keep && started) await down();
}
process.exit(finish());
