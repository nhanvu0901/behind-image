// Browser check of D22 (d-camera): camera frames on the source view ("Ảnh gốc") of step 5, dragged with REAL mouse events.
// Runs against the second instance of the app on the server (tests/e2e/stages/launch.py: fakes, BTI_NO_REAL_MODELS=1, port 8562,
// data copied to a temp folder; the project `arnolfini` is the one used here) through an ssh tunnel, with headless Chrome on the Mac.
//   node tests/e2e/storyboard/camera_frames.mjs [--keep-server]
// One PASS or FAIL line per check, exit code = number failing. Screenshots: .scratch/dcamera/shots/.
import { up, down, readState } from '../stages/remote.mjs';
import path from 'node:path';
import { openBrowser, makeApi, check, finish, go, sleep, REPO } from '../stages/common.mjs';

const SHOTS = path.join(REPO, '.scratch/dcamera/shots');
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
const near = (a, b, eps) => Math.abs(a - b) <= eps;
const snap = async (name) => { const f = path.join(SHOTS, name + '.png'); await p.shot(f); return f; };
const both = async (name) => { await p.resize(1700, 1000); await sleep(600); await snap(name + '-1700'); await p.resize(1280, 720); await sleep(700); await snap(name + '-1280'); await p.resize(1700, 1000); await sleep(500); };
const step = async (name, fn) => { try { await fn(); } catch (e) { check(`journey: ${name} ran to the end`, false, e.message); console.log(e.stack?.split('\n').slice(0, 3).join('\n')); } };

// ---- the page, read
const shotOf = (id) => ev(`(() => { const s = __bti.store.draft.shots.find((x) => x.id === ${J(id)}); return s && JSON.parse(JSON.stringify({ technique: s.technique, params: s.params, slots: s.slots, source: s.source })); })()`);
const undoLen = () => ev(`__bti.store.undoStack.length`);
const dirty = () => ev(`__bti.store.dirty`);
/** The frames on the picture: [{k, x, y, w, h, sel}] (screen px of the page), the corner handles, the chooser and the note. */
const view = () => ev(`(() => {
  const svg = document.querySelector('#handles'), r = (e) => { const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; };
  const sb = document.querySelector('#stage-box').getBoundingClientRect(), pick = document.querySelector('.cam-pick');
  return {
    frames: [...svg.querySelectorAll('.cframe')].map((e) => ({ k: +e.dataset.k, ...r(e), sel: e.classList.contains('sel') })).sort((a, b) => a.k - b.k),
    tags: [...svg.querySelectorAll('.ctag')].map((e) => ({ k: +e.dataset.k, text: e.textContent.trim(), sel: e.classList.contains('sel') })).sort((a, b) => a.k - b.k),
    knobs: [...svg.querySelectorAll('.hknob.ck')].map((e) => ({ c: e.dataset.corner, ...r(e) })),
    box: { x: sb.x, y: sb.y, w: sb.width, h: sb.height },
    pick: pick && pick.offsetParent !== null ? { value: pick.querySelector('select').value, options: [...pick.querySelectorAll('option')].map((o) => o.value) } : null,
    note: document.querySelector('#map-note').textContent, legend: [...svg.querySelectorAll('.kleg text')].map((e) => e.textContent),
    stage: document.querySelector('#stage').clientHeight, pic: document.querySelector('#stage-box').getBoundingClientRect().height,
    formSel: [...document.querySelectorAll('#tab-body .kf')].map((e) => e.classList.contains('kf-sel')),
    formVals: [...document.querySelectorAll('#tab-body .kf')].map((e) => [...e.querySelectorAll('.kf-grid input')].map((i) => Number(i.value))),
  }; })()`);
const centre = (f) => [f.x + f.w / 2, f.y + f.h / 2];
const area = (f) => f.w * f.h;
/** A point inside frame k that the hit test (smallest frame wins) gives to k and that is not near a handle of the selected frame. */
function pointIn(v, k) {
  const f = v.frames.find((x) => x.k === k), sel = v.frames.find((x) => x.sel);
  const corners = (r) => [[r.x, r.y], [r.x + r.w, r.y], [r.x, r.y + r.h], [r.x + r.w, r.y + r.h]];
  const M = 3;                                                   // the page counts a point 2 px outside a frame as inside
  for (let gy = 0.5; gy <= 0.95; gy += 0.05) for (let gx = 0.5; gx <= 0.95; gx += 0.05) {
    const pt = [f.x + f.w * gx, f.y + f.h * gy];
    const ins = v.frames.filter((r) => pt[0] >= r.x - M && pt[0] <= r.x + r.w + M && pt[1] >= r.y - M && pt[1] <= r.y + r.h + M);
    const min = Math.min(...ins.map(area)), ties = ins.filter((r) => area(r) <= min * (1 + 1e-9));
    const nearCorner = sel && corners(sel).some((c) => Math.abs(c[0] - pt[0]) < 16 && Math.abs(c[1] - pt[1]) < 16);
    if (ties.length === 1 && ties[0].k === k && !nearCorner) return pt;
  }
  return centre(f);
}
/** Real mouse drag: press at a, move in steps (optionally pausing in the middle), release at b. */
async function drag(a, b, { steps = 12, pauseMs = 0 } = {}) {
  await p.mouse('mouseMoved', a[0], a[1], { buttons: 0 }); await sleep(60);
  await p.mouse('mousePressed', a[0], a[1]);
  for (let i = 1; i <= steps; i++) {
    await p.mouse('mouseMoved', a[0] + ((b[0] - a[0]) * i) / steps, a[1] + ((b[1] - a[1]) * i) / steps, { buttons: 1 });
    await sleep(25);
    if (pauseMs && i === Math.floor(steps / 2)) await sleep(pauseMs);
  }
  await p.mouse('mouseReleased', b[0], b[1]); await sleep(250);
}
const selectShot = async (id, source = true) => {
  await ev(`__bti.A.selectItem(${J(id)})`); await sleep(400);
  const on = await ev(`document.querySelector('#view-source').checked`);
  if (on !== source) await p.click('#view-source');
  await sleep(500);
};
const aspect = (f) => f.w / f.h;
const frameReqs = () => p.net.filter((r) => /\/frame\b/.test(r.url)).length;

// the instance keeps its data between runs (--keep-server): every run starts from the project's original storyboard (the repo's copy)
import fs from 'node:fs';
const restoreOriginal = async () => {
  const cur = (await api.get(`/api/projects/${PID}`)).json;
  const orig = JSON.parse(fs.readFileSync(path.join(REPO, 'projects', PID, 'storyboard.json'), 'utf8'));
  const r = await api.put(`/api/projects/${PID}/storyboard`, { storyboard: orig, base_rev: cur.rev });
  return r.status;
};
const rs = await restoreOriginal();
const SB_SHOT = (await api.get(`/api/projects/${PID}`)).json?.storyboard;
try {
  let three = null, lay = null;
  await step('open the project', async () => {
    check('the test project is there with a storyboard', !!SB_SHOT?.shots?.length, 'no storyboard');
    await p.resize(1700, 1000);
    await go(p, base, `#/project/${PID}/edit`);
    await p.waitFor(`!!window.__bti?.store?.draft && !!document.querySelector('#handles') && !!document.querySelector('.prompt-edit')`, 40000);
    await sleep(1200);
    const found = await ev(`(() => { const s = __bti.store.draft.shots; const n = (x, k) => (x.params?.[k] || []).length;
      const a = s.find((x) => x.technique === 'CAM-05' && n(x, 'camera') === 3), l = s.find((x) => x.technique === 'LAY-01' && n(x, 'camera_left') >= 3 && n(x, 'camera_right') >= 3);
      return { three: a?.id || null, lay: l?.id || null }; })()`);
    three = found.three; lay = found.lay;
    check('the project has a CAM-05 shot with three keys and a LAY-01 shot with keys in both cameras', !!three && !!lay, J(found));
  });

  // ============================================================ a shot with three keys
  let before = null;
  await step('three keys: the frames', async () => {
    if (!three) return;
    await selectShot(three);
    const sh = await shotOf(three), keys = sh.params.camera;
    const v = await view();
    check('three keys: three frames on the picture, labelled K1 K2 K3', v.frames.length === 3 && v.tags.map((t) => t.text).join() === 'K1,K2,K3', J(v.tags));
    check('three keys: every frame has the aspect of the video frame (16:9)', v.frames.every((f) => near(aspect(f), 16 / 9, 0.02)), J(v.frames.map(aspect)));
    // the size follows from the zoom: width of a frame in the picture = 1920 / zoom source px, the same scale for all three
    const k0 = v.frames[0].w * keys[0].zoom, ok = v.frames.every((f, i) => near(f.w * keys[i].zoom, k0, k0 * 0.01));
    check('three keys: frame sizes are in the ratio of the zooms (size = frame / zoom)', ok, J(v.frames.map((f, i) => f.w * keys[i].zoom)));
    check('three keys: exactly one frame is highlighted (K1) and the form marks the same key', v.frames.filter((f) => f.sel).map((f) => f.k).join() === '1' && v.tags.filter((t) => t.sel).map((t) => t.k).join() === '1' && v.formSel.join() === 'true,false,false', J([v.frames.map((f) => f.sel), v.formSel]));
    check('three keys: the legend lists the numbers and zooms', v.legend.length === 3 && /K1\s+zoom 0\.72/.test(v.legend[0]), J(v.legend));
    check('three keys: four corner handles on the selected frame, no chooser visible (one camera)', v.knobs.length === 4 && v.pick === null, J([v.knobs.length, v.pick]));
    check('three keys: the stage is at least 300 px high at 1700x1000', v.stage >= 300, v.stage);
    await both('three-keys');
  });

  await step('three keys: drag the centre of K2 (an unselected frame) with the mouse', async () => {
    if (!three) return;
    await selectShot(three);
    const sh0 = await shotOf(three), v0 = await view(), u0 = await undoLen(), reqs0 = frameReqs();
    const pt = pointIn(v0, 2), f2 = v0.frames.find((f) => f.k === 2);
    const dx = 40, dy = -30;
    await p.mouse('mouseMoved', pt[0], pt[1], { buttons: 0 });
    const cur = await ev(`document.querySelector('#handles').style.cursor`);
    check('hovering a frame shows the move cursor', cur === 'move', cur);
    await drag(pt, [pt[0] + dx, pt[1] + dy]);
    const sh1 = await shotOf(three), v1 = await view(), k = f2.w / (1920 / sh0.params.camera[1].zoom);
    const c0 = sh0.params.camera[1], c1 = sh1.params.camera[1];
    check('centre drag: K2 centre moved by the mouse movement (source px = screen px / scale)', near(c1.cx, c0.cx + dx / k, 1.5) && near(c1.cy, c0.cy + dy / k, 1.5), J([c0, c1, k]));
    check('centre drag: K2 zoom, time and ease untouched; K1 and K3 untouched', c1.zoom === c0.zoom && J(c1.at) === J(c0.at) && c1.ease === c0.ease && J(sh1.params.camera[0]) === J(sh0.params.camera[0]) && J(sh1.params.camera[2]) === J(sh0.params.camera[2]));
    check('centre drag: the drag selected K2 (picture and form)', v1.frames.filter((f) => f.sel).map((f) => f.k).join() === '2' && v1.formSel.join() === 'false,true,false', J([v1.frames.map((f) => f.sel), v1.formSel]));
    check('centre drag: exactly ONE undo step', (await undoLen()) === u0 + 1, `${u0} -> ${await undoLen()}`);
    check('centre drag: the storyboard is marked changed and the shot is the owner\'s edit', (await dirty()) === true && sh1.source === 'human');
    check('centre drag: the number fields of K2 show the new numbers', v1.formVals[1] && near(v1.formVals[1][0], c1.cx, 0.06) && near(v1.formVals[1][1], c1.cy, 0.06) && near(v1.formVals[1][2], c1.zoom, 0.0006), J([v1.formVals, c1]));
    check('centre drag: no request for a picture from the server during the drag (source view)', frameReqs() === reqs0, `${reqs0} -> ${frameReqs()}`);
    before = sh1;
  });

  await step('three keys: drag a corner of the selected frame, with a long pause in the middle', async () => {
    if (!three) return;
    const sh0 = await shotOf(three), v0 = await view(), u0 = await undoLen();
    const f = v0.frames.find((x) => x.sel), kn = v0.knobs.find((x) => x.c === 'se'), start = centre(kn);
    const dxs = 60, dys = 60 * (f.h / f.w);
    await p.mouse('mouseMoved', start[0], start[1], { buttons: 0 });
    const cur = await ev(`document.querySelector('#handles').style.cursor`);
    check('hovering a corner shows a resize cursor', /resize/.test(cur), cur);
    await drag(start, [start[0] + dxs, start[1] + dys], { steps: 14, pauseMs: 1300 });
    const sh1 = await shotOf(three), v1 = await view();
    const c0 = sh0.params.camera[1], c1 = sh1.params.camera[1];
    const s = ((f.w / 2 + dxs) / (f.w / 2) + (f.h / 2 + dys) / (f.h / 2)) / 2;
    check('corner drag: the zoom changed as the corner moved (diagonal projection), the centre is kept', near(c1.zoom, c0.zoom / s, c0.zoom * 0.02) && c1.cx === c0.cx && c1.cy === c0.cy, J([c0, c1, s]));
    const f1 = v1.frames.find((x) => x.sel);
    check('corner drag: the frame keeps the aspect and its centre on the picture', near(aspect(f1), 16 / 9, 0.02) && near(centre(f1)[0], centre(f)[0], 1.5) && near(centre(f1)[1], centre(f)[1], 1.5), J([f, f1]));
    check('corner drag: ONE undo step although the pointer rested more than a second in the middle', (await undoLen()) === u0 + 1, `${u0} -> ${await undoLen()}`);
    check('corner drag: the number fields show the new zoom', near(v1.formVals[1][2], c1.zoom, 0.0006), J(v1.formVals));
    await both('three-keys-after-corner');
    // one Hoàn tác (the real button) takes back exactly that drag
    await p.click('#btn-undo'); await sleep(400);
    const back = await shotOf(three);
    check('undo: one click on Hoàn tác restores the zoom from before the corner drag, centre drag still there', J(back.params.camera) === J(sh0.params.camera), J([back.params.camera[1], sh0.params.camera[1]]));
    await p.click('#btn-redo'); await sleep(300);
    check('redo brings the corner drag back', J((await shotOf(three)).params.camera) === J(sh1.params.camera));
  });

  await step('three keys: a click without movement selects, a click on K3 selects K3 and changes nothing', async () => {
    if (!three) return;
    const sh0 = await shotOf(three), v0 = await view(), u0 = await undoLen();
    const pt = pointIn(v0, 3);
    await p.clickXY(pt[0], pt[1]); await sleep(300);
    const v1 = await view();
    check('click: K3 is selected on the picture and in the form, the data and the undo stack are unchanged', v1.frames.filter((f) => f.sel).map((f) => f.k).join() === '3' && v1.formSel.join() === 'false,false,true' && J((await shotOf(three)).params) === J(sh0.params) && (await undoLen()) === u0, J([v1.frames.map((f) => f.sel), v1.formSel]));
    // clicking in a field of K1 in the form selects K1 on the picture
    await p.click('#tab-body .kf:nth-of-type(1) .kf-grid input'); await sleep(300);
    const v2 = await view();
    check('form -> picture: focusing a field of K1 selects K1 on the picture', v2.frames.filter((f) => f.sel).map((f) => f.k).join() === '1', J(v2.frames.map((f) => f.sel)));
    await ev(`document.activeElement && document.activeElement.blur()`);
  });

  await step('three keys: overlapping frames stay usable (a small frame inside a large one)', async () => {
    if (!three) return;
    // make K1 huge and K3 tiny by typing zooms into the form with the real keyboard; K2 stays in between
    const typeZoom = async (k, val) => {
      await p.click(`#tab-body .kf:nth-of-type(${k}) .kf-grid div:nth-child(3) input`);
      await ev(`document.activeElement.select()`);
      await p.insert(String(val)); await p.key('Tab', 'Tab'); await sleep(300);
    };
    await typeZoom(1, 0.2); await typeZoom(3, 1.5);
    await ev(`document.activeElement && document.activeElement.blur()`);
    // bring the three centres together so that K3 lies inside K2 inside K1
    for (const k of [1, 2, 3]) {
      await ev(`(() => { const sb = __bti.store; sb.commit('test', (d) => { const s = d.shots.find((x) => x.id === ${J(three)}); s.params.camera[${k - 1}].cx = 2200; s.params.camera[${k - 1}].cy = 1700; }); })()`);
    }
    await sleep(500);
    const v = await view();
    const [f1, f2, f3] = [1, 2, 3].map((k) => v.frames.find((f) => f.k === k));
    const nested = f3.w < f2.w && f2.w < f1.w && f3.x > f2.x && f2.x > f1.x;
    check('overlap setup: K3 inside K2 inside K1 on the picture', nested, J([f1, f2, f3].map((f) => [f.x, f.w])));
    await p.click('#tab-body .kf:nth-of-type(1) .kf-grid input'); await ev(`document.activeElement.blur()`); await sleep(200);   // select K1
    const inK3 = centre(f3), ring2 = [f2.x + 8, f2.y + f2.h / 2], ring1 = [f1.x + 8, f1.y + f1.h / 2];
    await p.clickXY(...inK3); await sleep(250);
    const s3 = (await view()).frames.find((f) => f.sel)?.k;
    await p.clickXY(...ring2); await sleep(250);
    const s2 = (await view()).frames.find((f) => f.sel)?.k;
    await p.clickXY(...ring1); await sleep(250);
    const s1 = (await view()).frames.find((f) => f.sel)?.k;
    check('overlap: a click inside the small frame picks K3, on the ring of K2 picks K2, on the outer ring picks K1', s3 === 3 && s2 === 2 && s1 === 1, J([s3, s2, s1]));
    // the handles of the selected key win: select K1 (the largest), its handle lies far from the others; select K3 and drag its corner out of K2
    await p.clickXY(...inK3); await sleep(250);
    const v3 = await view(), kn = v3.knobs.find((x) => x.c === 'se'), sh0 = await shotOf(three);
    const start = centre(kn);
    await drag(start, [start[0] + 30, start[1] + 17]);
    const sh1 = await shotOf(three);
    check('overlap: with K3 selected its corner handle (inside the larger frames) resizes K3, not the frames around it', sh1.params.camera[2].zoom < sh0.params.camera[2].zoom && sh1.params.camera[0].zoom === sh0.params.camera[0].zoom && sh1.params.camera[1].zoom === sh0.params.camera[1].zoom, J([sh0.params.camera.map((k) => k.zoom), sh1.params.camera.map((k) => k.zoom)]));
    await both('overlap');
  });

  await step('three keys: save and compare with the stored storyboard', async () => {
    if (!three) return;
    const mem = await shotOf(three);
    await p.click('#btn-save'); await sleep(2500);
    const saved = (await api.get(`/api/projects/${PID}`)).json?.storyboard?.shots?.find((s) => s.id === three);
    const same = J(saved?.params?.camera?.map(({ at, cx, cy, zoom, ease }) => ({ at, cx, cy, zoom, ease }))) === J(mem.params.camera.map(({ at, cx, cy, zoom, ease }) => ({ at, cx, cy, zoom, ease })));
    check('save: the stored storyboard has the dragged keys (cx, cy, zoom of the three keys)', same, J([saved?.params?.camera, mem.params.camera]));
    check('save: the shot is stored as the owner\'s edit, and the page says nothing is unsaved', saved?.source === 'human' && (await dirty()) === false);
  });

  // ============================================================ a LAY-01 shot: the picture occupies only a cell of the frame
  await step('LAY-01: left and right cameras, the cell aspect', async () => {
    if (!lay) return;
    await selectShot(lay);
    const sh = await shotOf(lay);
    const P = { w: sh.params.panel_w_px ?? 900, h: sh.params.panel_h_px ?? 740 };
    const v = await view();
    check('LAY-01: a chooser with the two cameras, camera_left first', v.pick && v.pick.options.join() === 'camera_left,camera_right' && v.pick.value === 'camera_left', J(v.pick));
    check('LAY-01: camera_left has three frames labelled K1 K2 K3', v.frames.length === sh.params.camera_left.length && v.tags[0]?.text === 'K1', J(v.tags));
    check(`LAY-01: the frames have the aspect of the cell (${P.w} x ${P.h}), not of the whole frame`, v.frames.every((f) => near(aspect(f), P.w / P.h, 0.02)) && !v.frames.some((f) => near(aspect(f), 16 / 9, 0.05)), J(v.frames.map(aspect)));
    const k0 = v.frames[0].w * sh.params.camera_left[0].zoom;
    check('LAY-01: frame size = cell / zoom (same scale for all keys)', v.frames.every((f, i) => near(f.w * sh.params.camera_left[i].zoom, k0, k0 * 0.01)), J(v.frames.map((f, i) => f.w * sh.params.camera_left[i].zoom)));
    await both('lay01-left');
    // K1 and K2 of this shot are the same frame (a camera that holds still first): drag K3, then walk through the stack by clicking
    const u0 = await undoLen(), pt = pointIn(v, 3);
    const f3 = v.frames.find((f) => f.k === 3), ks = f3.w / (P.w / sh.params.camera_left[2].zoom);
    await drag(pt, [pt[0] - 25, pt[1] + 35]);
    const sh1 = await shotOf(lay), a = sh.params.camera_left[2], b = sh1.params.camera_left[2];
    check('LAY-01: centre drag moves the centre of camera_left K3 by the mouse movement', near(b.cx, a.cx - 25 / ks, 1.5) && near(b.cy, a.cy + 35 / ks, 1.5) && b.zoom === a.zoom, J([a, b, ks]));
    check('LAY-01: camera_right and the other keys untouched; one undo step', J(sh1.params.camera_right) === J(sh.params.camera_right) && J(sh1.params.camera_left[0]) === J(sh.params.camera_left[0]) && J(sh1.params.camera_left[1]) === J(sh.params.camera_left[1]) && (await undoLen()) === u0 + 1, `${u0} -> ${await undoLen()}`);
    const v1 = await view(), kn = v1.knobs.find((x) => x.c === 'nw'), st0 = centre(kn), fsel = v1.frames.find((f) => f.sel);
    await drag(st0, [st0[0] - 40, st0[1] - 40 * (fsel.h / fsel.w)]);
    const sh2 = await shotOf(lay), c = sh2.params.camera_left[2];
    check('LAY-01: dragging the nw corner outwards lowers the zoom of that key and keeps its centre', c.zoom < b.zoom && c.cx === b.cx && c.cy === b.cy && (await undoLen()) === u0 + 2, J([b, c]));
    // K1 and K2 are one stack of equal frames
    const vs = await view(), f1 = vs.frames.find((f) => f.k === 1), f2s = vs.frames.find((f) => f.k === 2), fk3 = vs.frames.find((f) => f.k === 3);
    check('LAY-01: K1 and K2 are drawn on top of each other (equal keys)', near(f1.x, f2s.x, 0.6) && near(f1.w, f2s.w, 0.6));
    const stackPt = [f1.x + f1.w * 0.03, f1.y + f1.h * 0.5];
    const picked = [];
    for (let i = 0; i < 3; i++) { await p.clickXY(...stackPt); await sleep(250); picked.push((await view()).frames.find((f) => f.sel)?.k); }
    check('LAY-01: clicks on a stack of equal frames walk through it (K2, K1, K2), nothing is edited', J(picked) === '[2,1,2]' && J((await shotOf(lay)).params.camera_left) === J(sh2.params.camera_left) && (await undoLen()) === u0 + 2, J(picked));
    const vd = await view(), pd = [stackPt[0], stackPt[1]];
    await drag(pd, [pd[0] + 18, pd[1] + 12], { steps: 5 });
    const sh2b = await shotOf(lay), moved2 = sh2b.params.camera_left.map((k, i) => (J(k) !== J(sh2.params.camera_left[i]) ? i + 1 : 0)).filter(Boolean);
    check('LAY-01: a drag on a stack moves the selected key only (K2), not its twin', J(moved2) === '[2]' && vd.frames.find((f) => f.sel)?.k === 2, J([moved2, vd.frames.find((f) => f.sel)?.k]));
    // the other camera
    await ev(`(() => { const s = document.querySelector('.cam-pick select'); s.value = 'camera_right'; s.dispatchEvent(new Event('change')); })()`); await sleep(500);
    const vr = await view();
    check('LAY-01: choosing camera_right shows its keys as frames of the same cell aspect, K1 selected', vr.pick.value === 'camera_right' && vr.frames.length === sh.params.camera_right.length && vr.frames.every((f) => near(aspect(f), P.w / P.h, 0.02)) && vr.frames.find((f) => f.sel)?.k === 1 && vr.formSel.length === sh.params.camera_right.length + sh.params.camera_left.length, J([vr.pick, vr.frames.length, vr.formSel]));
    const ptR = pointIn(vr, 3), fr3 = vr.frames.find((f) => f.k === 3), kr = fr3.w / (P.w / sh.params.camera_right[2].zoom);
    await drag(ptR, [ptR[0] + 20, ptR[1] + 20]);
    const sh3 = await shotOf(lay), ra = sh.params.camera_right[2], rb = sh3.params.camera_right[2];
    check('LAY-01: a drag on camera_right K3 changes camera_right only', near(rb.cx, ra.cx + 20 / kr, 1.5) && J(sh3.params.camera_left) === J(sh2b.params.camera_left), J([ra, rb]));
    const vf = await view();
    check('LAY-01: the form marks K3 of camera_right (and no key of camera_left)', vf.formSel.slice(0, sh.params.camera_left.length).every((x) => !x) && vf.formSel[sh.params.camera_left.length + 2] === true, J(vf.formSel));
    await both('lay01-right');
    // frame view: the cell is not the frame, so the page says to switch to "Ảnh gốc" instead of drawing frames in the wrong place
    await p.click('#view-source'); await sleep(900);
    const vn = await view();
    check('LAY-01 in the frame view: no frames in the wrong place, and a note says to switch to Ảnh gốc', vn.frames.length === 0 && /Ảnh gốc/.test(vn.note), J([vn.frames.length, vn.note]));
    await p.click('#view-source'); await sleep(400);
  });

  // ============================================================ every technique with a camera parameter
  const EXPECT = {   // technique -> camera param -> aspect of its panel, from the engine code and the registry defaults
    'CAM-01': { camera: 16 / 9 }, 'CAM-03': { camera: 16 / 9 }, 'CAM-04': { camera: 16 / 9 }, 'CAM-05': { camera: 16 / 9 }, 'CAM-06': { camera: 16 / 9 },
    'STATIC-01': { camera: 16 / 9 }, 'X-LAY-01': { camera: 16 / 9 }, 'AN-07': { camera: 16 / 9 }, 'HI-02': { camera: 16 / 9 },
    'CAM-02': { fg_camera: 16 / 9, bg_camera: 16 / 9 },
    'LAY-01': { camera_left: 900 / 740, camera_right: 900 / 740 },
    'LAY-02': { camera_1: 930 / 520, camera_2: 930 / 520, camera_3: 930 / 520, camera_4: 930 / 520 },
    'LAY-04': { camera: 16 / 9, inset_camera: 560 / 315 },
    'LAY-05': { camera: 16 / 9, camera_bg_1: 16 / 9, camera_bg_2: 16 / 9, camera_bg_3: 16 / 9, camera_bg_4: 16 / 9 },
    'LAY-06': { camera_base: 16 / 9 },
    'LAY-07': { camera_1: 16 / 9, camera_2: 16 / 9, camera_3: 16 / 9, camera_4: 16 / 9, camera_5: 16 / 9, camera_6: 16 / 9, object_camera: 16 / 9 },   // six tiles in 2 columns: 960 x 360 ... see below
    'LAY-08': { camera: 480 / 540 },
    'CMP-01': { camera: 930 / 800 }, 'CMP-02': { finished_camera: 1, stage_camera: 1 }, 'CMP-03': { camera: 610 / 900 }, 'CMP-04': { camera: 1 },
    'CMP-05': { camera: 16 / 9 }, 'X-CMP-01': { camera_anchor: 900 / 740 }, 'X-CMP-02': { camera: 16 / 9 },
  };
  EXPECT['LAY-07'] = { ...Object.fromEntries([1, 2, 3, 4, 5, 6].map((i) => ['camera_' + i, 960 / 360])), object_camera: 16 / 9 };   // all six tiles filled: 3 rows of 2 columns = 960 x 360
  await step('every technique with a camera parameter: three keys, the right aspect, a drag', async () => {
    const victim = await ev(`__bti.store.draft.shots.find((s) => s.id !== ${J(three)} && s.id !== ${J(lay)} && __bti.ctx.tech(s.technique)?.kind === 'base').id`);
    const regCams = await ev(`__bti.ctx.reg.list.filter((t) => t.params.some((p) => p.type === 'camera')).map((t) => ({ id: t.id, cams: t.params.filter((p) => p.type === 'camera').map((p) => p.name), slots: t.slots.map((s) => s.name), defaults: Object.fromEntries(t.params.map((p) => [p.name, p.default])) }))`);
    check(`the registry has ${Object.keys(EXPECT).length} techniques with a camera parameter and the check knows each of them`, regCams.length === Object.keys(EXPECT).length && regCams.every((t) => EXPECT[t.id] && t.cams.every((c) => EXPECT[t.id][c])), J(regCams.map((t) => t.id)));
    let bad = [], dragged = 0, total = 0;
    for (const t of regCams) {
      await ev(`__bti.store.commit('sweep', (d) => { const s = d.shots.find((x) => x.id === ${J(victim)}); s.technique = ${J(t.id)}; s.slots = Object.fromEntries(${J(t.slots)}.map((n) => [n, { asset: 'A' }]));
        s.params = ${J(t.defaults)}; for (const c of ${J(t.cams)}) s.params[c] = [0, 0.5, 1].map((r, i) => ({ at: { rel: r }, cx: 2100 + i * 150, cy: 2900 + i * 120, zoom: [0.5, 0.65, 0.9][i], ease: 'linear' })); })`);
      await selectShot(victim); await sleep(300);
      for (const c of t.cams) {
        total++;
        const pickIt = await ev(`(() => { const s = document.querySelector('.cam-pick select'); if (!s || s.closest('.cam-pick').hidden) return ${J(t.cams.length === 1)}; s.value = ${J(c)}; s.dispatchEvent(new Event('change')); return true; })()`);
        await sleep(250);
        const v = await view();
        const ok = pickIt && v.frames.length === 3 && v.tags.map((x) => x.text).join() === 'K1,K2,K3' && v.frames.every((f) => near(aspect(f), EXPECT[t.id][c], EXPECT[t.id][c] * 0.02)) && v.frames.filter((f) => f.sel).length === 1;
        if (!ok) { bad.push(`${t.id}.${c}: ${v.frames.length} frames, aspects ${v.frames.map((f) => aspect(f).toFixed(3))} want ${EXPECT[t.id][c].toFixed(3)} pick=${pickIt}`); continue; }
        if (c === t.cams[0] || t.id === 'CMP-02') {                // a real drag for the first camera of every technique (and both of CMP-02)
          const before = (await shotOf(victim)).params[c];
          const pt = pointIn(v, 3);
          await drag(pt, [pt[0] + 14, pt[1] + 9], { steps: 5 });
          const after = (await shotOf(victim)).params[c];
          if (after[2].cx === before[2].cx && after[2].cy === before[2].cy) bad.push(`${t.id}.${c}: the drag did not move K3`); else dragged++;
        }
      }
    }
    check(`all ${total} camera parameters of the ${regCams.length} techniques show three frames of the aspect of their panel (and a real drag moved K3 in ${dragged} of them)`, !bad.length, bad.join(' | '));
    await ev(`__bti.store.commit('sweep', (d) => { const s = d.shots.find((x) => x.id === ${J(victim)}); s.technique = 'LAY-01'; })`);
  });

  // ============================================================ many keys, and the rest of step 5
  await step('many keys and an unusual number of keys', async () => {
    // a reload drops the sweep edits (nothing was saved)
    await go(p, base, `#/project/${PID}/edit`);
    await p.waitFor(`!!window.__bti?.store?.draft && !!document.querySelector('.prompt-edit')`, 40000); await sleep(1200);
    const many = await ev(`__bti.store.draft.shots.find((x) => (x.params?.camera || []).length >= 40)?.id || null`);
    if (!many) { check('a shot with many keys exists', false, 'none'); return; }
    await selectShot(many);
    const sh = await shotOf(many), v = await view();
    check(`${sh.params.camera.length} keys: ${sh.params.camera.length} frames, numbered, one selected, the legend is left out when there are too many`, v.frames.length === sh.params.camera.length && v.tags.length === v.frames.length && v.frames.filter((f) => f.sel).length === 1 && v.legend.length === 0, J([v.frames.length, v.legend.length]));
    const u0 = await undoLen(), pt = pointIn(v, 30);
    await drag(pt, [pt[0] + 25, pt[1] + 10], { steps: 6 });
    const sh1 = await shotOf(many), changed = sh1.params.camera.map((k, i) => (J(k) !== J(sh.params.camera[i]) ? i + 1 : 0)).filter(Boolean);
    check('many keys: a drag moves exactly one key, in one undo step', changed.length === 1 && (await undoLen()) === u0 + 1, J([changed, u0, await undoLen()]));
    await p.click('#btn-undo'); await sleep(300);
  });
  await step('the rest of step 5 still works', async () => {
    const three2 = three;
    await selectShot(three2, false); await sleep(900);
    const vf = await view();
    check('frame view: the frames of a camera over the whole frame are drawn through the playhead camera (three of them) and are dragged the same way', vf.frames.length === 3, J(vf.frames.length));
    await p.resize(1280, 720); await sleep(800);
    const m = await ev(`(() => { const s = document.querySelector('#stage'), b = document.querySelector('#stage-box'), c = document.querySelector('#prompt-edit-container'); const r = c.getBoundingClientRect(); return { stage: s.clientHeight, pic: b.getBoundingClientRect().height, boxRight: r.left, hasBox: !!document.querySelector('.prompt-instruction'), tools: document.querySelector('#preview-tools').scrollWidth <= document.querySelector('#preview-tools').clientWidth + 1, tl: !!document.querySelector('#tl-canvas') }; })()`);
    check('1280x720: the preview keeps at least 300 px, the instruction box is still next to it and the tool row does not overflow', m.stage >= 300 && m.pic >= 280 && m.hasBox && m.tools, J(m));
    await selectShot(lay, true); await sleep(600);
    await snap('lay01-1280-source');
    await p.resize(1700, 1000); await sleep(500);
    // the timeline: a click on a shot band still selects it
    const pt = await ev(`(() => { const s = __bti.store.draft.shots.find((x) => x.id === ${J(three2)}); const r = document.querySelector('#tl-canvas').getBoundingClientRect(); const tl = window.__tl; return { x: r.x + tl.X((s._t0 + s._t1) / 2), y: r.y + tl.Y.shot + tl.R.shot / 2 }; })()`);
    await p.clickXY(pt.x, pt.y); await sleep(400);
    check('timeline: a click on a shot band still selects that shot', (await ev(`__bti.store.sel.shot`)) === three2);
    // the "Hình" tab, then back to Shot
    await p.click('#tabs button', 'Hình'); await sleep(500);
    check('the Hình tab still opens', await ev(`!!document.querySelector('#tab-body') && /Hình/.test(document.querySelector('#tabs button.active')?.textContent || '')`));
    await p.click('#tabs button', 'Shot'); await sleep(300);
    const bad = (await ev(`1`), p.logs.filter((l) => /EXCEPTION|Uncaught|TypeError|ReferenceError/.test(l)));
    check('no script error during the whole run', !bad.length, J(bad.slice(0, 3)));
  });
} finally {
  try { await restoreOriginal(); } catch {}
  closeAll();
  const n = finish();
  if (!keep && started) await down();
  process.exit(n);
}
