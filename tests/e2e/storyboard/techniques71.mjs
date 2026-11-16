// Save and reload for every technique of the registry, and a sample of 10 s preview clips. Run:
//   node tests/e2e/storyboard/techniques71.mjs save      (all 71, or: save HI-01 AN-03 ...)
//   node tests/e2e/storyboard/techniques71.mjs clips
// For each technique: put it on a shot of technique_lab (the page's own actions: the same code path as the gallery), fill every
// required slot with an asset of the RIGHT kind from the project, fill required text, save with the real Lưu button, reload the
// page, and compare the draft with what was saved (page state and the file on disk).
import fs from 'node:fs'; import path from 'node:path';
import { boot, sleep, REPO } from './lib.mjs';
const mode = process.argv[2] || 'save', only = process.argv.slice(3);
const T = await boot(['technique_lab']);
const { ev } = T;
const J = JSON.stringify;
await T.open('technique_lab');
const reg = await (await fetch(`${T.B}/api/styles/gae`)).json();
const techs = reg.techniques.filter((t) => !only.length || only.includes(t.id));
const SHOT = 's0031', SHOT2 = 's0032';
const disk = () => JSON.parse(fs.readFileSync(path.join(T.root, 'technique_lab/storyboard.json'), 'utf8'));
const strip = (o) => JSON.parse(J(o, (k, v) => (k.startsWith('_') ? undefined : v)));

// the page-side helper: put technique `id` where it belongs and fill what it needs. Returns what it did.
const setup = (t) => ev(`(async()=>{
  const {A,store:st,ctx}=window.__bti; const id=${J(t.id)}, kind=${J(t.kind)};
  const slotKind=(sl)=>sl.type==='mask'||(sl.type==='image'&&/^mask(_\\d+)?$/.test(sl.name))?'mask':sl.type;
  const assets=st.draft.assets; const ofKind=(k)=>Object.keys(assets).filter(a=>(assets[a].kind||'image')===k && !/^(annot_G_|annot_LEFT|annot_RIGHT)/.test(a));
  const did={slots:{},missing:[],text:[]};
  let target;
  if(kind==='transition'){ A.setTransition(${J(SHOT2)}, id); target=null; }
  else if(kind==='overlay'){ const oid=await A.addOverlayAction(${J(SHOT)}, id); target={shotId:${J(SHOT)},overlayId:oid}; }
  else { await A.setShotTechnique(${J(SHOT)}, id); target={shotId:${J(SHOT)}}; }
  if(target){
    const item=target.overlayId? st.shotById(target.shotId).overlays.find(o=>o.id===target.overlayId) : st.shotById(target.shotId);
    for(const sl of ctx.tech(id).slots){
      const k=slotKind(sl); if(k==='text') { if(sl.required){ await A.setParam(target.overlayId?'overlay':'shot', item.id, sl.name, 'Test '+sl.name); did.text.push(sl.name);} continue; }
      const has=(item.slots||{})[sl.name]?.asset || (target.overlayId && sl.name==='image' ? Object.values(st.shotById(target.shotId).slots||{}).find(v=>v.asset)?.asset : null);
      if(has) { did.slots[sl.name]=has+' (kept)'; continue; }
      if(!sl.required) continue;
      const cand=ofKind(k)[0];
      if(!cand){ did.missing.push(sl.name+':'+k); continue; }
      const ok=await A.assignSlot(target, sl.name, cand); did.slots[sl.name]=cand+(ok?'':' (refused)');
    }
  }
  return JSON.stringify(did);
})()`);
const issues = () => ev(`JSON.stringify(__bti.ctx.issues.map(i=>({level:i.level,code:i.code||null,path:i.path,message:i.message})))`);

async function saveCheck(t) {
  T.restore('technique_lab'); await T.reload();
  const r = { id: t.id, kind: t.kind };
  const logs0 = T.logs.length;
  try {
    r.did = JSON.parse(await setup(t));
    await sleep(1500);                                                        // the page validates 700 ms after the last edit
    await ev(`document.querySelector('#btn-check').click()`); await sleep(1200);
    r.issues = JSON.parse(await issues());
    r.errors = r.issues.filter((i) => i.level === 'error').map((i) => i.message);
    r.incomplete = r.issues.filter((i) => i.code === 'incomplete').map((i) => i.message);
    const before = strip(JSON.parse(await ev(`JSON.stringify(__bti.ctx.draftPlain())`)));
    await ev(`document.querySelector('#btn-save').click()`); await sleep(2500);
    r.dirtyAfterSave = await ev('__bti.store.dirty');
    const onDisk = disk();
    const want = r.kind === 'transition' ? ((onDisk.shots.find((s) => s.id === SHOT2) || {}).transition_in || {}).technique === t.id
      : r.kind === 'overlay' ? onDisk.shots.find((s) => s.id === SHOT).overlays.some((o) => o.technique === t.id)
        : onDisk.shots.find((s) => s.id === SHOT).technique === t.id;
    r.savedOnDisk = want;
    await T.reload();
    const after = strip(JSON.parse(await ev(`JSON.stringify(__bti.ctx.draftPlain())`)));
    delete before.approvals; delete after.approvals;
    r.reloadEqual = J(before) === J(after);
    if (!r.reloadEqual) { const a = J(before), b = J(after); let i = 0; while (a[i] === b[i]) i++; r.firstDiff = `${a.slice(Math.max(0, i - 60), i + 60)}  <>  ${b.slice(Math.max(0, i - 60), i + 60)}`; }
    r.reloadDirty = await ev('__bti.store.dirty');
    r.frame = await ev(`(async()=>{try{const b=await __bti.api.frame(__bti.ctx.pid, __bti.store.shotById(${J(SHOT)})._t0+0.6, 480, __bti.ctx.draftPlain());return b.size>1000?'ok':'tiny'}catch(e){return 'error '+e.status}})()`);
  } catch (e) { r.exception = String(e.message).slice(0, 200); }
  r.consoleErrors = T.logs.slice(logs0);
  r.ok = !r.exception && r.savedOnDisk && r.reloadEqual && !r.dirtyAfterSave && !r.reloadDirty && !(r.errors || []).length && r.frame === 'ok';
  return r;
}

async function clips() {
  const sample = [['overlay', 'HI-01'], ['overlay', 'AN-01'], ['overlay', 'TXT-02'], ['overlay', 'STATIC-02'], ['overlay', 'X-ANN-01'], ['transition', 'TR-01'], ['transition', 'TR-04'], ['transition', 'X-TR-01'], ['transition', 'X-TR-02'], ['transition', 'TR-03']];
  const out = [];
  for (const [kind, id] of sample) {
    const t = techs.find((x) => x.id === id) || reg.techniques.find((x) => x.id === id);
    T.restore('technique_lab'); await T.reload();
    const r = { id, kind };
    try {
      r.did = JSON.parse(await setup(t)); await sleep(800);
      const from = kind === 'transition' ? `__bti.store.shotById(${J(SHOT2)})._t0 - 1.0` : `__bti.store.shotById(${J(SHOT)})._t0 + 0.2`;
      await ev(`__bti.seek(${from})`); await sleep(500);
      await ev(`document.querySelector('#btn-clip').click()`);
      let v = null;
      for (let i = 0; i < 120 && !v; i++) { await sleep(500); v = await ev(`(()=>{const e=document.querySelector('.modal video');return e&&e.readyState>=2?JSON.stringify({d:e.duration,w:e.videoWidth,h:e.videoHeight}):null})()`); }
      r.video = v ? JSON.parse(v) : null; r.ok = !!r.video && r.video.d > 3;
      await ev(`document.querySelector('.modal header button')?.click()`);
    } catch (e) { r.exception = String(e.message).slice(0, 200); }
    out.push(r); console.log(`${r.ok ? 'PASS' : 'FAIL'} clip ${kind} ${id} ${J(r.video)} ${r.exception || ''}`);
  }
  return out;
}

let res;
if (mode === 'clips') res = await clips();
else {
  res = [];
  for (const t of techs) {
    const r = await saveCheck(t); res.push(r);
    console.log(`${r.ok ? 'PASS' : 'FAIL'} ${t.id} (${t.kind}) slots=${J(r.did?.slots)} missing=${J(r.did?.missing)} errors=${J(r.errors)} incomplete=${(r.incomplete || []).length} saved=${r.savedOnDisk} reloadEqual=${r.reloadEqual} frame=${r.frame}${r.exception ? ' EXC ' + r.exception : ''}${r.firstDiff ? '\n   diff ' + r.firstDiff : ''}`);
  }
}
const outFile = process.env.OUT || path.join(REPO, '.scratch/fix_storyboard', mode === 'clips' ? 'clips.json' : 'techniques71.json');
fs.mkdirSync(path.dirname(outFile), { recursive: true }); fs.writeFileSync(outFile, J(res, null, 1));
const bad = res.filter((r) => !r.ok);
console.log(`\n${res.length - bad.length}/${res.length} ok`);
process.exit(bad.length ? 1 : 0);
