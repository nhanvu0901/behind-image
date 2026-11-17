// Round 3 UI checks. Run alone:  node tests/e2e/round3/run.mjs [R3U-001 ...]
// One PASS or FAIL line per check; exit code = number of FAIL. Each check asserts the CORRECT behaviour, so it FAILS while its bug exists.
import { setup, sleep, SHOTS, fs, path } from './common.mjs';
const only = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const T = await setup(); const { B, br, J, JS, job, openEdit, open, own } = T;
let failed = 0;
const check = async (id, title, fn) => {
  if (only.length && !only.includes(id)) return;
  let ok = false, note = '';
  try { const r = await fn(); ok = r === true; note = ok ? '' : String(r); } catch (e) { note = 'ERROR ' + String(e.message).slice(0, 200); }
  console.log(`${ok ? 'PASS' : 'FAIL'} ${id} ${title}${note ? '  -> ' + note : ''}`); if (!ok) failed++;
};
const closeExtra = () => { while (br.pages.length > 1) { const p = br.pages.pop(); p.close(); } };

try {
  await check('R3U-001', 'shot tab: an intent the list does not know (or none) is not shown as the first intent', async () => {
    const p = await br.newPage(); await openEdit(p, 'arnolfini_edit');
    await p.eval(`__bti.store.commit('x', d=>{ d.shots[0].intent='dance'; d.shots[1].intent=null; })`);
    const out = [];
    for (const i of [0, 1]) {
      await p.eval(`__bti.store.select(__bti.store.draft.shots[${i}].id)`); await p.click('#tabs button', 'Shot'); await sleep(300);
      out.push(await p.eval(`(()=>{const r=[...document.querySelectorAll('#tab-body .row')].find(r=>/Ý đồ/.test(r.textContent)); const s=r.querySelector('select'); return s.selectedOptions[0]?.textContent||''})()`));
    }
    p.close(); closeExtra();
    return (!/Giới thiệu bối cảnh/.test(out[0]) && !/Giới thiệu bối cảnh/.test(out[1])) || `selected labels ${JSON.stringify(out)}`; });

  await check('R3U-002', 'script: a chapter that only the narration has can be removed from the narration on the page', async () => {
    const s = await own(); const slug = 'r3_f'; const A = (m, u, b) => J(m, u, b, s.base);
    await A('POST', '/api/library/projects', { artwork_key: 'munch-the-scream', slug });
    let r = await A('POST', `/api/projects/${slug}/outline/generate`, { model: 'mock' }); await job(r.job_id, s.base);
    let o = await A('GET', `/api/projects/${slug}/outline`); await A('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev });
    r = await A('POST', `/api/projects/${slug}/narration/generate`, { model: 'mock' }); await job(r.job_id, s.base);
    const n = await A('GET', `/api/projects/${slug}/narration`); await A('POST', `/api/projects/${slug}/narration/approve`, { rev: n.rev });
    o = await A('GET', `/api/projects/${slug}/outline`); const last = o.outline.chapters.pop().id;
    await A('PUT', `/api/projects/${slug}/outline`, { outline: o.outline, base_rev: o.rev });
    o = await A('GET', `/api/projects/${slug}/outline`); await A('POST', `/api/projects/${slug}/outline/approve`, { rev: o.rev });
    const p = await br.newPage(); await open(p, `#/project/${slug}/script`, '#nar-badge', s.base); await sleep(1500);
    const hdr = await p.eval(`[...document.querySelectorAll('#chap-${last} .chap-h button')].map(b=>b.textContent.trim())`);
    p.close(); closeExtra();
    return hdr.some((t) => /xóa|bỏ chương|gỡ/i.test(t)) || `the header of chapter ${last} has only: ${hdr.join(' | ')}; the refusal tells the owner to delete it`; });

  const corrupt = async () => {
    const s = await own(); const p = await br.newPage(); await openEdit(p, 'arnolfini_edit', s.base);
    fs.writeFileSync(path.join(s.projects, 'arnolfini_edit', 'media/durer.jpg'), 'this is not an image');
    return { s, p };
  };
  await check('R3U-003', 'storyboard: clicking an issue about an image file leads to a shot that uses it (or the pictures tab), not shot 1', async () => {
    const { p } = await corrupt();
    await p.click('#btn-approve'); await p.waitFor(`document.querySelector('#btn-approve').textContent!=='Đang duyệt...'`, 90000); await sleep(800);
    await p.click('#tab-body .list-item.error'); await sleep(1500);
    const sel = await p.eval('__bti.store.sel.shot'), tab = await p.eval(`document.querySelector('#tabs button.active, #tabs button.on')?.textContent||''`);
    p.close(); closeExtra();
    return (sel === 's0080' || /Hình/.test(tab)) || `selected ${sel}, tab "${tab}" (shot s0080 uses the image)`; });

  await check('R3U-004', 'storyboard: when the preview frame of a shot cannot be drawn, the Shot tab says so and the old picture is not left on screen', async () => {
    const { p } = await corrupt();
    await p.eval(`__bti.store.select('s0080')`); await sleep(2500);
    await p.click('#tabs button', 'Shot'); await sleep(500);
    const banner = await p.eval(`document.querySelector('#tab-body .render-fail')?.textContent||''`);
    await p.shot(SHOTS + 'run_r3u004.png');
    p.close(); closeExtra();
    return banner.length > 10 || 'the preview line explains, the Shot tab has no explanation'; });

  await check('R3U-005', 'storyboard: the first Ctrl+Z after "Đã ghép với bản sửa ở nơi khác" does not throw away what the other tab saved', async () => {
    const s = await own(); const a = await br.newPage(), b = await br.newPage();
    await openEdit(a, 'arnolfini_edit', s.base); await openEdit(b, 'arnolfini_edit', s.base);
    await a.eval(`__bti.store.commit('e', d=>{ d.shots[3].note='a1'; }); 1`); await a.click('#btn-save'); await sleep(2200);
    await b.eval(`__bti.store.commit('e', d=>{ d.shots[9].note='b1'; }); 1`); await b.click('#btn-save'); await sleep(3000);   // merged: B now also holds a1
    const merged = await b.eval(`[__bti.store.draft.shots[3].note, __bti.store.draft.shots[9].note, __bti.store.dirty]`);
    await b.eval(`__bti.store.undo(); 1`);
    const after = await b.eval(`[__bti.store.draft.shots[3].note, __bti.store.draft.shots[9].note, __bti.store.dirty]`);
    a.close(); b.close(); closeExtra();
    // what the other tab saved (a1) must survive an undo; an undo may only take back what THIS tab did (b1)
    return (merged[0] === 'a1' && after[0] === 'a1') || `after merge ${JSON.stringify(merged)}; after one Ctrl+Z ${JSON.stringify(after)} (the other tab's a1 is gone from the draft and a save would overwrite it)`; });
} finally { /* cleanup on exit */ }
console.log(failed ? `\n${failed} check(s) FAIL` : '\nall checks PASS');
process.exit(failed);
